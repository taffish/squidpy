#!/usr/bin/env python3
"""Small, deterministic, offline runtime checks for the Squidpy image."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import importlib.resources as resources
from pathlib import Path


def identity() -> None:
    from importlib import import_module
    from importlib.util import find_spec

    for module in ("anndata","dask.array","dask_image","h5py","imagecodecs","leidenalg",
                   "matplotlib","networkx","numba","numpy","pandas","scanpy","scipy",
                   "skimage","sklearn","spatialdata","spatialdata_plot","spatialleiden",
                   "squidpy","statsmodels","tifffile","xarray","zarr","numba_progress",
                   "mahotas","centrosome._lapjv","cp_measure.featurizer"):
        import_module(module)
    import squidpy
    assert squidpy.__version__ == metadata.version("squidpy") == "1.8.4"
    assert metadata.version("omnipath") == "1.0.12"
    assert metadata.version("centrosome") == "1.3.4+taffish.1"
    assert metadata.version("Pillow") == "13.0.0"
    assert not list(metadata.distribution("squidpy").entry_points)
    assert find_spec("napari") is None
    registry = resources.files("squidpy.datasets").joinpath("datasets.yaml").read_bytes()
    import hashlib
    assert hashlib.sha256(registry).hexdigest() == "24675c06910cb9f4cfd8549fa31311f1d05c5a61fe9f32f4dc6c0ac8d531ba4d"
    try:
        import_module("squidpy.pl._interactive")
    except ImportError as exc:
        assert "napari-spatialdata" in str(exc)
    else:
        raise AssertionError("unexpected interactive module")
    print("squidpy=1.8.4")


def graph(outdir: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import scanpy as sc
    import squidpy as sq
    from anndata import AnnData

    outdir.mkdir(parents=True, exist_ok=False)
    coords = np.array([(x, y) for y in range(4) for x in range(4)], dtype=float)
    values = np.column_stack(
        [
            coords[:, 0] + 1,
            coords[:, 1] + 1,
            (coords[:, 0] == coords[:, 1]).astype(float) + 1,
            np.arange(len(coords), dtype=float) % 3 + 1,
        ]
    )
    adata = AnnData(values)
    adata.var_names = ["gene_x", "gene_y", "gene_diag", "gene_cycle"]
    adata.obs_names = [f"spot_{i:02d}" for i in range(adata.n_obs)]
    adata.obs["region"] = pd.Categorical(
        ["left" if x < 2 else "right" for x, _ in coords]
    )
    adata.obsm["spatial"] = coords

    sq.gr.spatial_neighbors_grid(adata, n_neighs=4, n_rings=1)
    assert adata.obsp["spatial_connectivities"].nnz > 0
    sq.gr.nhood_enrichment(
        adata, cluster_key="region", n_perms=12, rng=0, n_jobs=1, show_progress_bar=False
    )
    params = dict(cluster_key="region", n_perms=7, rng=31, normalization="conditional",
                  copy=True, show_progress_bar=False)
    one = sq.gr.nhood_enrichment(adata, n_jobs=1, **params)
    two = sq.gr.nhood_enrichment(adata, n_jobs=2, **params)
    for key in ("counts", "zscore", "conditional_ratio"):
        np.testing.assert_allclose(getattr(one,key), getattr(two,key), equal_nan=True)
    assert one.conditional_ratio is not None
    moran = sq.gr.spatial_autocorr(
        adata, mode="moran", genes=["gene_x", "gene_y"], n_perms=12,
        rng=0, n_jobs=1, copy=True
    )
    centrality = sq.gr.centrality_scores(adata, cluster_key="region", copy=True)

    sc.pp.pca(adata, n_comps=2)
    sc.pp.neighbors(adata, n_neighbors=4, n_pcs=2)
    import spatialleiden

    spatialleiden.spatialleiden(
        adata, resolution=(0.4, 0.4), random_state=0, key_added="spatialleiden"
    )
    assert "spatialleiden" in adata.obs

    sq.pl.nhood_enrichment(adata, cluster_key="region")
    plt.savefig(outdir / "nhood_enrichment.png", dpi=90, bbox_inches="tight")
    plt.close("all")
    moran.to_csv(outdir / "moran.tsv", sep="\t")
    centrality.to_csv(outdir / "centrality.tsv", sep="\t")
    adata.write_h5ad(outdir / "squidpy_graph.h5ad")
    (outdir / "versions.tsv").write_text(
        "package\tversion\n"
        f"squidpy\t{metadata.version('squidpy')}\n"
        f"scanpy\t{metadata.version('scanpy')}\n"
        f"spatialleiden\t{metadata.version('spatialleiden')}\n"
    )
    print("graph=ok")


def ligrec(outdir: Path) -> None:
    import numpy as np
    import pandas as pd
    import squidpy as sq
    from anndata import AnnData

    outdir.mkdir(parents=True, exist_ok=False)
    adata = AnnData(
        np.array(
            [
                [7, 1, 2],
                [6, 2, 2],
                [8, 1, 3],
                [7, 2, 3],
                [1, 7, 2],
                [2, 6, 2],
                [1, 8, 3],
                [2, 7, 3],
            ],
            dtype=float,
        )
    )
    adata.var_names = ["LIGAND", "RECEPTOR", "CONTROL"]
    adata.obs_names = [f"cell_{i:02d}" for i in range(adata.n_obs)]
    adata.obs["cluster"] = pd.Categorical(["sender"] * 4 + ["receiver"] * 4)
    interactions = pd.DataFrame(
        {"source": ["LIGAND"], "target": ["RECEPTOR"]}
    )

    result = sq.gr.ligrec(
        adata,
        cluster_key="cluster",
        interactions=interactions,
        use_raw=False,
        n_perms=8,
        rng=0,
        n_jobs=1,
        threshold=0,
        copy=True,
    )
    assert result is not None
    assert set(result) == {"means", "metadata", "pvalues"}
    assert result["means"].shape == (1, 4)
    assert result["pvalues"].shape == (1, 4)
    result["means"].to_csv(outdir / "ligrec-means.tsv", sep="\t")
    result["pvalues"].to_csv(outdir / "ligrec-pvalues.tsv", sep="\t")
    interactions.to_csv(outdir / "local-interactions.tsv", sep="\t", index=False)
    (outdir / "ligrec-summary.tsv").write_text(
        "field\tvalue\n"
        f"squidpy\t{metadata.version('squidpy')}\n"
        f"interactions\t{result['means'].shape[0]}\n"
        f"cluster_pairs\t{result['means'].shape[1]}\n"
        "interaction_source\tlocal-dataframe\n"
    )
    print("ligrec=ok")


def image(outdir: Path) -> None:
    import numpy as np
    import squidpy as sq
    import tifffile

    outdir.mkdir(parents=True, exist_ok=False)
    y, x = np.mgrid[:32, :32]
    rgb = np.stack(
        [x * 8, y * 8, ((x + y) % 32) * 8], axis=-1
    ).astype(np.uint8)
    tifffile.imwrite(outdir / "input.tiff", rgb)

    image = sq.im.ImageContainer(outdir / "input.tiff", lazy=False)
    processed = sq.im.process(image, method="smooth", sigma=1, copy=True)
    assert processed is not None and "image_smooth" in processed
    segmented = sq.im.segment(
        processed, layer="image_smooth", method="watershed", channel=0,
        thresh=96, copy=True
    )
    assert segmented is not None and "segmented_watershed" in segmented

    if not bool(int(__import__("os").environ.get("SQUIDPY_BUILDTIME", "0"))):
        # Squidpy resolves relative plot paths under scanpy.settings.figdir.
        processed.show(layer="image_smooth", save=(outdir / "image.png").resolve(), dpi=90)
        assert (outdir / "image.png").stat().st_size > 0
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Consolidated metadata is currently not part"
            )
            processed.save(outdir / "image.zarr")
        loaded = sq.im.ImageContainer.load(outdir / "image.zarr", lazy=False)
        assert loaded.shape == processed.shape

    (outdir / "image-summary.tsv").write_text(
        "field\tvalue\n"
        f"shape\t{processed.shape}\n"
        f"segmentation_max\t{int(segmented['segmented_watershed'].max())}\n"
    )
    print("image=ok")


def features(outdir: Path) -> None:
    import numpy as np
    import xarray as xr
    import squidpy as sq
    from spatialdata import SpatialData
    from spatialdata.models import Image2DModel, Labels2DModel
    from PIL import Image
    from centrosome.bg_compensate import bg_compensate

    outdir.mkdir(parents=True, exist_ok=False)
    y, x = np.mgrid[:64, :64]
    labels = np.zeros((64, 64), dtype=np.int32)
    labels[8:24, 8:22] = 1
    labels[34:56, 35:55] = 2
    plane = ((x + 2 * y + (labels > 0) * 55) % 250).astype(np.uint8)
    sdata = SpatialData(images={"img":Image2DModel.parse(xr.DataArray(plane[None],dims=("c","y","x")))},
                       labels={"lbl":Labels2DModel.parse(xr.DataArray(labels,dims=("y","x")))})
    result = sq.experimental.im.calculate_image_features(
        sdata, image_key="img", labels_key="lbl", features=["cp_measure:intensity","skimage:morphology:area"],
        inplace=False, drop_constant_features=False)
    assert result.n_obs == 2 and any("Intensity_MeanIntensity" in v for v in result.var_names)
    result.write_h5ad(outdir / "features.h5ad")
    # Exercise the actual grayscale reader and unchanged background fitter.
    # Reconstruction checks the original 8-bit and 16-bit normalization semantics.
    import tifffile
    for depth, pixels, divisor in [("8", plane, 1), ("12", plane.astype(np.uint16)*15, 4095),
                                 ("16", plane.astype(np.uint16)*257, 65535),
                                 ("16be", (plane.astype(np.uint16)*257).astype(">u2"), 65535),
                                 ("16tag", plane.astype(np.uint16)*7, 2047)]:
        dest = outdir / f"gray{depth}.tiff"
        tifffile.imwrite(dest, pixels, byteorder=">" if depth=="16be" else "<",
                         extratags=[(281,"H",1,2047,False)] if depth=="16tag" else [])
        corrected, background = bg_compensate(str(dest), sigma=1, splinepoints=5, scale=1)
        expected = pixels.astype(np.float32)/divisor
        reference = outdir / f"float-{depth}.tiff"
        Image.fromarray(expected).save(reference)
        reference_pair = bg_compensate(str(reference), sigma=1, splinepoints=5, scale=1)
        assert corrected.shape == background.shape == pixels.shape
        assert np.isfinite(corrected).all() and np.isfinite(background).all()
        np.testing.assert_allclose(corrected, reference_pair[0], rtol=0, atol=1e-5)
        np.testing.assert_allclose(background, reference_pair[1], rtol=0, atol=1e-5)
        np.testing.assert_allclose(corrected + background, expected, atol=1e-5)
    print("features=ok")


def resource() -> None:
    import tempfile
    import subprocess
    import squidpy as sq
    with tempfile.TemporaryDirectory() as work:
        base=Path(work);lib=base/"lib";lib.mkdir(mode=0o755);lib.chmod(0o755)
        table=base/"interactions.tsv";table.write_text("source\ttarget\nA\tB\n")
        terms=base/"NOTICE";terms.write_text("Synthetic fixture made for this smoke; CC0.")
        recipe=base/"recipe.json"
        with recipe.open("wb") as out:
            subprocess.run(["squidpy-data","pin-table","--file",str(table),"--id","tiny",
                "--url","https://example.invalid/interactions.tsv","--rights-file",str(terms)],stdout=out,check=True)
        cmd=["squidpy-data","install","--table-recipe",str(recipe),"--source-dir",str(base),"--resource-root",str(lib),"--reserve-mib","0"]
        subprocess.run(cmd,check=True)
        assert "already complete" in subprocess.check_output(cmd,text=True)
        assert (lib/"table.tiny/interactions.tsv").read_bytes()==table.read_bytes()
        try: sq.datasets.imc()
        except FileNotFoundError as error: assert "prepared" in str(error)
        else: raise AssertionError("unexpected implicit dataset acquisition")
    print("resource=ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("identity", "graph", "ligrec", "image", "features","resource"))
    parser.add_argument("outdir", nargs="?", type=Path)
    args = parser.parse_args()
    if args.mode == "identity":
        identity()
        return
    if args.mode == "resource":
        resource()
        return
    if args.outdir is None:
        parser.error("functional modes require OUTDIR")
    if args.mode == "graph":
        graph(args.outdir)
    elif args.mode == "ligrec":
        ligrec(args.outdir)
    elif args.mode == "features":
        features(args.outdir)
    else:
        image(args.outdir)


if __name__ == "__main__":
    main()
