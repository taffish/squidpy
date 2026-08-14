#!/usr/bin/env python3
"""Small, deterministic, offline runtime checks for the Squidpy image."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import importlib.resources as resources
from pathlib import Path


def identity() -> None:
    import anndata
    import dask.array
    import dask_image
    import h5py
    import imagecodecs
    import leidenalg
    import matplotlib
    import networkx
    import numba
    import numpy
    import pandas
    import scanpy
    import scipy
    import skimage
    import sklearn
    import spatialdata
    import spatialdata_plot
    import spatialleiden
    import squidpy
    import statsmodels
    import tifffile
    import xarray
    import zarr

    del (
        anndata,
        dask.array,
        dask_image,
        h5py,
        imagecodecs,
        leidenalg,
        matplotlib,
        networkx,
        numba,
        numpy,
        pandas,
        scanpy,
        scipy,
        skimage,
        sklearn,
        spatialdata,
        spatialdata_plot,
        spatialleiden,
        statsmodels,
        tifffile,
        xarray,
        zarr,
    )

    assert squidpy.__version__ == "1.8.3"
    assert metadata.version("omnipath") == "1.0.12"
    dist = metadata.distribution("squidpy")
    assert not list(dist.entry_points), "Squidpy 1.8.3 unexpectedly gained an entry point"
    registry = resources.files("squidpy.datasets").joinpath("datasets.yaml").read_text()
    assert "https://exampledata.scverse.org/squidpy/" in registry
    try:
        import squidpy.pl._interactive  # noqa: F401
    except ImportError as exc:
        assert "napari-spatialdata" in str(exc)
    else:
        raise AssertionError("removed Squidpy interactive module unexpectedly imported")

    print(f"squidpy={squidpy.__version__}")
    print(f"scanpy={metadata.version('scanpy')}")
    print(f"spatialdata={metadata.version('spatialdata')}")
    print(f"spatialdata-plot={metadata.version('spatialdata-plot')}")
    print(f"spatialleiden={metadata.version('spatialleiden')}")
    print("interactive=napari-spatialdata replacement required")


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
        adata, cluster_key="region", n_perms=12, seed=0, n_jobs=1
    )
    moran = sq.gr.spatial_autocorr(
        adata, mode="moran", genes=["gene_x", "gene_y"], n_perms=12,
        seed=0, n_jobs=1, copy=True
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
        seed=0,
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
        processed.show(layer="image_smooth", save=outdir / "image.png", dpi=90)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("identity", "graph", "ligrec", "image"))
    parser.add_argument("outdir", nargs="?", type=Path)
    args = parser.parse_args()
    if args.mode == "identity":
        identity()
        return
    if args.outdir is None:
        parser.error("graph and image modes require OUTDIR")
    if args.mode == "graph":
        graph(args.outdir)
    elif args.mode == "ligrec":
        ligrec(args.outdir)
    else:
        image(args.outdir)


if __name__ == "__main__":
    main()
