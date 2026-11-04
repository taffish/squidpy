"""Squidpy's fixed dataset registry and explicit, immutable shared snapshots."""
import argparse
import fcntl
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from squidpy_store import (Directory, Interrupted, blocked_signals, canonical, check_directory,
                          durable_mode, inode, interrupt, obtain, promote, require)

VERSION = "1.8.4-r1"
CATALOG_SHA = "24675c06910cb9f4cfd8549fa31311f1d05c5a61fe9f32f4dc6c0ac8d531ba4d"
RECIPE = "taffish.squidpy.resource.v1"
MANIFEST = "taffish.squidpy.member.v1"
READ_ROOT = Path("/datasets/squidpy")
INSTALL = Path("/dataset-install")
ONLINE = Path("/squidpy-network")
SOURCE = "https://exampledata.scverse.org/squidpy/"
FLUO = "https://www.10xgenomics.com/datasets/adult-mouse-brain-section-2-coronal-stains-dapi-anti-gfap-anti-neu-n-1-standard-1-1-0"
AUTO_IDS = {"visium_fluo_image_crop", "visium_fluo_adata", "visium_fluo_adata_crop", "V1_Adult_Mouse_Brain_Coronal_Section_2"}
RIGHTS = "10x Genomics, Adult Mouse Brain Section 2 (Coronal); CC BY 4.0; source: " + FLUO + "; Squidpy/scverse preprocessing or cropping where indicated."
META = {"manifest.json", "READY", "RESOURCE_LICENSE.txt"}
KNOWN_BYTES = {"visium_fluo_adata_crop.h5ad": 68673654}


def name(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", value)
            and ".." not in value, "unsafe resource identifier or filename")
    return value


@lru_cache(maxsize=1)
def catalog():
    from importlib.metadata import distribution
    import yaml
    content = distribution("squidpy").locate_file("squidpy/datasets/datasets.yaml").read_bytes()
    require(hashlib.sha256(content).hexdigest() == CATALOG_SHA, "upstream catalog checksum mismatch")
    data = yaml.safe_load(content)
    require(data["s3_base_url"] == SOURCE, "unexpected dataset source")
    return data["datasets"]


def mount_info(path):
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if fields[4] == str(path):
            return (fields[2], fields[3], fields[5].split(","))
    return None


def exposed():
    mount = mount_info(READ_ROOT)
    if not mount and os.environ.get("TAFFISH_SQUIDPY_DATASET_ACTIVE") != "1":
        return None
    require(mount and "ro" in mount[2], "prepared library requires an actual read-only bind at /datasets/squidpy")
    with Directory(READ_ROOT) as root:
        verify_root(root)
    return READ_ROOT


def network_root():
    flag = os.environ.get("TAFFISH_SQUIDPY_ALLOW_NETWORK", "0")
    require(flag in ("0", "1"), "TAFFISH_SQUIDPY_ALLOW_NETWORK must be 0 or 1")
    if flag == "0":
        return None
    m = mount_info(ONLINE)
    require(m and "rw" in m[2] and mount_info(READ_ROOT) is None, "online access needs a separate writable /squidpy-network bind and disabled discovery")
    with Directory(ONLINE) as root:
        check_directory(root, writable=True, mode=0o700)
        require(not any(root.exists(n) for n in [".downloads", ".install.lock", "manifest.json", "READY"]), "refusing prepared or transactional root as online cache")
    return ONLINE


def clean_url(url):
    p = urlsplit(url)
    require(p.scheme == "https" and p.hostname and not p.username and not p.password and not p.fragment and not p.query,
            "expected a public, credential-free HTTPS source")
    return url


def layout(dataset, hires):
    data = catalog()
    require(dataset in data, "unknown upstream dataset: " + dataset)
    entry = data[dataset]
    require(type(hires) is bool and (not hires or entry["type"] == "visium_10x"), "--hires is only for a 10x Visium member")
    files = [f for f in entry["files"] if entry["type"] != "visium_10x" or hires or not f["name"].startswith("image.")]
    if hires:
        require(any(f["name"].startswith("image.") for f in files), "this dataset has no hires image")
    return entry["type"], [(name(f["name"]), clean_url(SOURCE + f["s3_key"]), f["sha256"]) for f in files]


def rights_text(path):
    require(path is not None, "a reviewed --rights-file covering this acquisition and intended site/individual use is required")
    with Directory(path.absolute().parent) as parent:
        value = parent.read(path.name, 65536).decode().strip()
    require(bool(value), "empty rights notice")
    return value


class HTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        clean_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def plan(dataset, hires, local, rights, header=False, previous=None):
    kind, entries = layout(dataset, hires)
    automatic = dataset in AUTO_IDS and all(f[2] for f in entries)
    notice = RIGHTS if automatic else rights_text(rights)
    files = []
    for filename, url, expected in entries:
        size = KNOWN_BYTES.get(filename)
        if local is not None:
            with Directory(local) as folder:
                size, observed = folder.digest(filename)
            require(expected is None or observed == expected, "upstream file checksum mismatch: " + filename)
            expected = observed
        elif previous is not None:
            prior=next((f for f in previous["files"] if f["name"]==filename and f["sha256"]==expected and f["url"]==url),None)
            if prior is not None: size=prior["size"]
        if local is None and header:
            require(automatic, "authorized local import only: provide --source-dir and --rights-file")
            if size is None:
                with build_opener(HTTPSRedirect()).open(Request(url, method="HEAD"), timeout=30) as response:
                    clean_url(response.geturl())
                    size = int(response.headers["Content-Length"])
        files.append(dict(name=filename, url=url, sha256=expected, size=size))
    return dict(schema=RECIPE, unit=dataset + (".hires" if hires else ""), dataset=dataset,
                kind=kind, hires=hires, catalog_sha256=CATALOG_SHA, license=notice, files=files,
                acquisition="reviewed-provider" if automatic else "authorized-local")


def validate(recipe):
    keys = {"schema","unit","dataset","kind","hires","catalog_sha256","license","files","acquisition"}
    require(isinstance(recipe,dict) and set(recipe) == keys and recipe["schema"] == RECIPE, "invalid member recipe")
    unit = name(recipe["unit"])
    require(isinstance(recipe["license"],str) and 0 < len(recipe["license"]) <= 65536, "invalid rights notice")
    files = recipe["files"]
    require(isinstance(files,list) and files, "resource has no files")
    for f in files:
        require(isinstance(f,dict) and set(f) == {"name","url","sha256","size"} and name(f["name"]) not in META, "invalid payload record")
        require(type(f["size"]) is int and f["size"] > 0 and re.fullmatch("[a-f0-9]{64}",f["sha256"]), "positive size and SHA256 required")
    require(len(set(f["name"] for f in files)) == len(files), "duplicate payload")
    if recipe["kind"] == "interaction-table":
        require(unit == "table."+name(recipe["dataset"]) and recipe["catalog_sha256"] is None and recipe["hires"] is False
                and recipe["acquisition"] == "operator-pinned" and len(files) == 1 and files[0]["name"] == "interactions.tsv", "invalid local interaction table identity")
        clean_url(files[0]["url"])
        return
    dataset, hires = name(recipe["dataset"]), recipe["hires"]
    kind, entries = layout(dataset, hires)
    require(recipe["catalog_sha256"] == CATALOG_SHA and unit == dataset + (".hires" if hires else "")
            and recipe["kind"] == kind and len(files) == len(entries), "official dataset/registry identity mismatch")
    for f,(n,url,digest) in zip(files,entries,strict=True):
        require((f["name"],f["url"]) == (n,url) and (digest is None or f["sha256"] == digest), "dataset inventory/source hash mismatch")
        if n in KNOWN_BYTES:
            require(f["size"] == KNOWN_BYTES[n], "official dataset size mismatch")
    automatic = dataset in AUTO_IDS and all(f[2] for f in entries)
    require(recipe["acquisition"] == ("reviewed-provider" if automatic else "authorized-local"), "invalid acquisition policy")
    require(not automatic or recipe["license"] == RIGHTS, "provider/attribution mismatch")


def table_recipe(args):
    with Directory(args.file.absolute().parent) as parent:
        size,digest = parent.digest(args.file.name)
    record = dict(schema=RECIPE, unit="table."+name(args.id), dataset=args.id, kind="interaction-table", hires=False,
                  catalog_sha256=None, license=rights_text(args.rights_file), acquisition="operator-pinned",
                  files=[dict(name="interactions.tsv",size=size,sha256=digest,url=clean_url(args.url))])
    validate(record)
    return record


def verify_member(opened, unit):
    check_directory(opened,mode=0o755)
    raw = opened.read("manifest.json")
    recipe = json.loads(raw)
    validate(recipe)
    require(recipe["unit"] == unit and raw == canonical(recipe)+b"\n", "resource ID/manifest mismatch")
    require(opened.read("READY") == (hashlib.sha256(raw).hexdigest()+"\n").encode(), "READY/manifest mismatch")
    require(opened.read("RESOURCE_LICENSE.txt") == (recipe["license"]+"\n").encode(), "resource rights notice mismatch")
    require(set(opened.names()) == META | {f["name"] for f in recipe["files"]}, "missing or extra resource file")
    for f in recipe["files"]:
        require(opened.digest(f["name"]) == (f["size"], f["sha256"]), "resource checksum/size mismatch: "+f["name"])
    owner = os.fstat(opened.fd).st_uid
    for n in opened.names():
        s = opened.info(n)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == owner and stat.S_IMODE(s.st_mode) == 0o644,
                "resource file ownership or permissions changed: "+n)
    return recipe


def verify_root(root, allow_empty=False):
    check_directory(root)
    owner=os.fstat(root.fd).st_uid
    records={}
    for n in root.names():
        s=root.info(n)
        if n == ".install.lock":
            require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o600 and s.st_uid==owner, "invalid installation lock; do not delete")
        elif n == ".downloads":
            require(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==owner, "invalid private recovery directory")
        elif re.fullmatch(r"\.stage-[0-9a-f]{24}", n):
            # SIGKILL may land after the final chmod and before no-replace rename.
            # Ignore only an owned, non-writable-to-others staging directory;
            # never enter, repair, publish, or remove an older transaction.
            require(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode) in (0o700,0o755) and s.st_uid==owner, "invalid retained staging directory")
        else:
            name(n)
            require(s.st_uid == owner, "resource owner differs from library owner: "+n)
            with Directory(parent=root,name=n) as member:
                records[n] = verify_member(member,n)
    require(allow_empty or records, "no verified member in selected resource root")
    return records


def install(path, recipe, local, reserve):
    validate(recipe)
    require(path.is_absolute() and path.resolve(strict=True) != Path("/"), "explicit existing library directory required")
    if path.resolve(strict=True)==INSTALL:
        m=mount_info(INSTALL); require(m and "rw" in m[2], "actual writable bind at /dataset-install required")
    require(reserve >= 0, "negative free space reserve")
    if local is None:
        require(recipe["acquisition"] in ("operator-pinned","reviewed-provider"), "this member requires authorized local files")
    with Directory(path) as root:
        check_directory(root,writable=True,mode=0o755)
        verify_root(root,True)
        lock=root.file(".install.lock",os.O_RDWR|os.O_CREAT)
        stage=None
        try:
            s=os.fstat(lock);require(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o600,"lock must be private")
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError("an installer holds the lock; do not delete it")
            records=verify_root(root,True)
            unit=recipe["unit"]
            if unit in records:
                require(records[unit]==recipe,"existing member has a different recipe; never overwritten")
                print("already complete:",unit);return
            if not root.exists(".downloads"): os.mkdir(".downloads",0o700,dir_fd=root.fd)
            with Directory(parent=root,name=".downloads") as cache:
                check_directory(cache,writable=True,mode=0o700)
                needed = reserve + sum(f["size"]*(1 if cache.exists(f["sha256"]) else 2) for f in recipe["files"])
                space=os.fstatvfs(root.fd); require(space.f_bavail*space.f_frsize >= needed,f"insufficient space: need {needed} bytes")
                blobs=[(f,obtain(f,cache,local)) for f in recipe["files"]]
                with blocked_signals():
                    key=".stage-"+os.urandom(12).hex(); os.mkdir(key,0o700,dir_fd=root.fd)
                    stage=Directory(parent=root,name=key)
                for f,blob in blobs:
                    with os.fdopen(cache.file(blob),"rb") as src, stage.create(f["name"]) as dest:
                        shutil.copyfileobj(src,dest,1024**2); dest.flush()
                        durable_mode(dest.fileno(),0o644,lambda:stage.info(f["name"]))
            raw=canonical(recipe)+b"\n"
            stage.write("manifest.json",raw); stage.write("READY",(hashlib.sha256(raw).hexdigest()+"\n").encode())
            stage.write("RESOURCE_LICENSE.txt",(recipe["license"]+"\n").encode())
            durable_mode(stage.fd,0o755,lambda:root.info(stage.name))
            verify_member(stage,unit)
            with blocked_signals():
                stage.guard(); promote(root,stage.name,unit); os.close(stage.fd); stage=None
            os.fsync(root.fd); print("installed:",unit)
        finally:
            try:
                if stage is not None:
                    try:
                        stage.clean_owned()
                    except BaseException:
                        print("squidpy-data: stage=cleanup; retained for inspection:",stage.path,file=sys.stderr);raise
                    finally: os.close(stage.fd)
            finally: os.close(lock)


def main():
    p=argparse.ArgumentParser(description="Prepare selected, immutable Squidpy resources; never all datasets.")
    p.add_argument("--version",action="version",version="squidpy-data "+VERSION)
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("catalog",help="list the wheel's registry, without network access")
    pin=sub.add_parser("pin-table",help="pin an authorized local interaction table (TSV); verify rights first")
    pin.add_argument("--id",required=True);pin.add_argument("--file",required=True,type=Path)
    pin.add_argument("--url",required=True);pin.add_argument("--rights-file",required=True,type=Path)
    for command in ("install","verify","list"):
        s=sub.add_parser(command)
        s.add_argument("--resource-root",type=Path,default=INSTALL if command=="install" else READ_ROOT)
        if command=="install":
            select=s.add_mutually_exclusive_group(required=True)
            select.add_argument("--dataset");select.add_argument("--table-recipe",type=Path)
            s.add_argument("--hires",action="store_true");s.add_argument("--rights-file",type=Path)
            s.add_argument("--source-dir",type=Path,help="verified local files; no network")
            s.add_argument("--fetch",action="store_true",help="explicit HTTPS acquisition, never implicit")
            s.add_argument("--reserve-mib",type=int,default=1024);s.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    if args.command=="catalog":
        print("\n".join(sorted(catalog())));return
    if args.command=="pin-table":
        print(json.dumps(table_recipe(args),indent=2));return
    require(args.resource_root.is_absolute(),"absolute --resource-root required")
    if args.command!="install":
        with Directory(args.resource_root) as root: records=verify_root(root)
        print(json.dumps(sorted(records) if args.command=="list" else {"verified":sorted(records)}));return
    require(0<=args.reserve_mib<=2**30,"invalid reserve")
    require(not (args.fetch and args.source_dir is not None),"choose either --source-dir or --fetch")
    require(args.dry_run or args.fetch or args.source_dir is not None,"choose --source-dir for offline import or --fetch for deliberate network access")
    if args.table_recipe:
        require(not args.hires and not args.rights_file,"table rights and source are already pinned")
        with Directory(args.table_recipe.absolute().parent) as parent: recipe=json.loads(parent.read(args.table_recipe.name))
        validate(recipe);require(recipe["kind"]=="interaction-table","expected a pinned interaction table")
    else:
        previous=None
        if not args.dry_run:
            with Directory(args.resource_root) as root:
                check_directory(root,writable=True,mode=0o755)
                previous=verify_root(root,True).get(args.dataset+(".hires" if args.hires else ""))
        recipe=plan(args.dataset,args.hires,args.source_dir,args.rights_file,header=args.fetch and not args.dry_run,previous=previous)
    if args.dry_run:
        print(json.dumps({"recipe":recipe,"destination":str(args.resource_root/recipe["unit"]),"reserve_mib":args.reserve_mib,
            "size_policy":"null = not provided by upstream; resolve HTTPS Content-Length or measure authorized local input before install; budget cache + installed bytes",
            "network_performed":False},indent=2));return
    install(args.resource_root,recipe,args.source_dir,args.reserve_mib*1024**2)


def cli():
    try:
        for s in (signal.SIGINT,signal.SIGTERM): signal.signal(s,interrupt)
        main()
    except Interrupted as exc:
        print(f"squidpy-data: interrupted exit={128+exc.signum}; verified old resources retained",file=sys.stderr)
        raise SystemExit(128+exc.signum)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print("squidpy-data: stage=prepare-or-verify:",exc,file=sys.stderr);raise SystemExit(1)
