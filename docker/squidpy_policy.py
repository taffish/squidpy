"""Adapt resource acquisition only. Numerical routines and the official wheel stay intact."""
import functools
import importlib.abc
import importlib.machinery
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile

import squidpy_data as data

_temp = None


def scratch():
    global _temp
    if _temp is None:
        _temp = tempfile.TemporaryDirectory(prefix="taf-squidpy-")
        for var, part in (("MPLCONFIGDIR","mpl"),("NUMBA_CACHE_DIR","numba"),("DASK_TEMPORARY_DIRECTORY","dask"),("XDG_CACHE_HOME","cache")):
            os.environ.setdefault(var, str(Path(_temp.name)/part))
    return Path(_temp.name)


def extract(src, dest, zip_format):
    # Only fixed/pinned input from a verified RO library is unpacked, into
    # a fresh private directory. Never extract into the shared library.
    members = []
    seen = set()
    with (zipfile.ZipFile(src) if zip_format else tarfile.open(src, "r:gz")) as archive:
        for item in (archive.infolist() if zip_format else archive):
            raw = item.filename if zip_format else item.name
            path = PurePosixPath(raw)
            data.require(not path.is_absolute() and ".." not in path.parts and "\\" not in raw, "unsafe archive path")
            if path == PurePosixPath("."):
                continue
            key = path.as_posix()
            data.require(key not in seen, "duplicate archive path");seen.add(key)
            if zip_format:
                kind = stat.S_IFMT(item.external_attr >> 16)
                data.require(kind in (0,stat.S_IFDIR,stat.S_IFREG) and not item.flag_bits & 1, "unsupported archive member")
                directory, size = item.is_dir(), item.file_size
            else:
                data.require(item.isdir() or (item.isreg() and not item.issparse()), "refusing archive links/special files")
                directory, size = item.isdir(), item.size
            members.append((item, dest/key, directory, size))
            data.require(len(members) <= 500000, "too many archive entries")
        data.require(sum(size for _,_,d,size in members if not d) + 64*1024**2 <= shutil.disk_usage(dest).free, "insufficient scratch space to unpack this dataset")
        for item,target,directory,size in members:
            if directory:
                target.mkdir(parents=True, exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with (archive.open(item) if zip_format else archive.extractfile(item)) as inp, target.open("xb") as out:
                shutil.copyfileobj(inp,out,1024**2)
            data.require(target.stat().st_size == size,"incomplete scratch extraction")


def adapt_datasets(module):
    original = module.download
    @functools.wraps(original)
    def download(name, path=None, **kwargs):
        online=data.network_root()
        if online is not None:
            if path is not None and Path(path).resolve() != online:
                raise ValueError("online example downloads require the explicitly bound /squidpy-network directory")
            return original(name,online,**kwargs)
        root=data.exposed()
        if root is None:
            raise FileNotFoundError("no prepared Squidpy resource library; use squidpy-data install or read a local H5AD/TIFF/Zarr explicitly")
        if path is not None and Path(path).resolve() != root:
            raise ValueError("prepared dataset cache is read-only at /datasets/squidpy; read project files explicitly instead")
        hires=kwargs.pop("include_hires_tiff",False)
        unit=data.name(name)+(".hires" if hires else "")
        member=root/unit
        if not member.is_dir():
            raise FileNotFoundError(f"dataset {unit} missing in selected library; install it or explicitly select a different prepared root")
        entry=module.get_registry()[name]
        if entry.type in ("anndata","image"):
            loader=module._load_anndata if entry.type=="anndata" else module._load_image
            return loader(entry,member,lambda f: str(member/f.name),**kwargs)
        dest=Path(tempfile.mkdtemp(prefix="read-",dir=scratch()))
        if entry.type=="spatialdata":
            import spatialdata as sd
            extract(member/entry.file(suffix=".zip").name,dest,True)
            stores=list(dest.glob("*.zarr"));data.require(len(stores)==1,"expected one .zarr store")
            return sd.read_zarr(stores[0],**kwargs)
        data.require(entry.type=="visium_10x","unsupported dataset type")
        from squidpy.read import visium
        # read.visium expects its count file adjacent to its spatial/ tree.
        # Both sides are private scratch or verified read-only input.
        folder=dest/name;folder.mkdir()
        (folder/"filtered_feature_bc_matrix.h5").symlink_to(member/"filtered_feature_bc_matrix.h5")
        extract(member/"spatial.tar.gz",folder,False)
        image=next((member/f.name for f in entry.files if f.name.startswith("image.")),None) if hires else None
        return visium(folder,source_image_path=image,**kwargs)
    module.download=download


def adapt_ligrec(module):
    original=module.PermutationTest.prepare
    @functools.wraps(original)
    def prepare(self,interactions=None,*args,**kwargs):
        if interactions is None:
            raise ValueError("squidpy: provide interactions= from an authorized local table; default live OmniPath acquisition is disabled")
        return original(self,interactions,*args,**kwargs)
    module.PermutationTest.prepare=prepare


class Loader:
    def __init__(self,inner,after): self.inner,self.after=inner,after
    def create_module(self,spec): return self.inner.create_module(spec)
    def exec_module(self,module):
        self.inner.exec_module(module); self.after(module)
    def __getattr__(self,name): return getattr(self.inner,name)


class PolicyFinder(importlib.abc.MetaPathFinder):
    callbacks={"squidpy.datasets._downloader":adapt_datasets,"squidpy.gr._ligrec":adapt_ligrec}
    def find_spec(self,fullname,path,target=None):
        if fullname in {"squidpy","scanpy","matplotlib","spatialdata","numba","dask"}: scratch()
        if fullname not in self.callbacks:return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path,target)
        if spec is None or spec.loader is None:raise ImportError("Squidpy policy could not locate "+fullname)
        spec.loader=Loader(spec.loader,self.callbacks[fullname]);return spec


def configure():
    data.network_root()
    data.exposed()
    sys.meta_path.insert(0,PolicyFinder())
