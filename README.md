# squidpy

`squidpy` packages the official Squidpy 1.8.3 Python environment for TAFFISH.

Package identity:

- name: `squidpy`
- command: `taf-squidpy`
- kind: `tool`
- version: `1.8.3-r1`
- image: `ghcr.io/taffish/squidpy:1.8.3-r1`
- platforms: native `linux/amd64` and `linux/arm64`
- app license: Apache-2.0
- upstream: [scverse/squidpy v1.8.3](https://github.com/scverse/squidpy/releases/tag/v1.8.3)

## Installation

Install the current release from the TAFFISH Hub:

```sh
taf install squidpy 1.8.3-r1
```

## What This App Packages

Squidpy analyzes spatial molecular data using AnnData/Scanpy objects, spatial
graphs, spatial statistics, ligand-receptor interactions, microscopy images,
and static plots. Upstream 1.8.3 has no console entry point, so the thin
TAFFISH default is `python`; automatic command mode remains available for
explicit packaged executables.

The image contains the full declared Squidpy runtime dependency closure and
the complete official `leiden` extra (`leidenalg` and `spatialleiden`). The
official Squidpy wheel, its pure-Python `docrep` source dependency, the
dependency constraints, upstream license, source identity, and installed
requirements are recorded under `/opt/squidpy/share/doc/squidpy/`.

## Scope

This app supports:

- spatial neighbor graphs, neighborhood enrichment, co-occurrence,
  centrality, autocorrelation, ligand-receptor analysis, and related plots;
- `ImageContainer` loading, image processing, segmentation, features, TIFF,
  Zarr, HDF5/AnnData, and static Matplotlib output;
- Scanpy, SpatialData, spatialdata-plot, and the official SpatialLeiden extra;
- ordinary Python scripts and packaged command-mode executables.

This app does not bundle datasets, a Jupyter server, napari/Qt, a browser
service, cloud credentials, or GPU/CUDA libraries.

## Container Contents

- `python` / `python3`: default Python 3.12 analysis runtime.
- `pip`: package inventory and environment inspection; the environment is
  otherwise release-pinned and should be treated as immutable.
- Squidpy 1.8.3, Scanpy 1.12.3, SpatialData 0.8.0,
  spatialdata-plot 0.4.1, SpatialLeiden 0.4.0, and frozen required packages.
- DejaVu fonts and a headless Matplotlib `Agg` backend for static plots.

## Usage

Run a Python analysis script in the packaged environment:

```sh
taf-squidpy python analysis.py
```

Inspect package versions or run a short expression:

```sh
taf-squidpy python -c '"import squidpy as sq; print(sq.__version__)"'
taf-squidpy python -m pip list
```

Use `taf-squidpy -- --help` for the default Python interpreter help. Squidpy
itself intentionally has no upstream command-line program, so analysis is
performed through its Python API rather than a `squidpy` executable.

Automatic command mode reconstructs a shell command. Preserve literal quotes
as part of a path containing spaces:

```sh
taf-squidpy python "'scripts/spatial analysis.py'"
```

A minimal script can build and analyze a spatial graph:

```python
import scanpy as sc
import squidpy as sq

adata = sc.read_h5ad("local-input.h5ad")
sq.gr.spatial_neighbors_grid(adata, n_neighs=6)
sq.gr.spatial_autocorr(adata, mode="moran")
adata.write_h5ad("result.h5ad")
```

This form is offline when `local-input.h5ad` and all requested resources are
already present.

## Inputs and Outputs

Common inputs are Python scripts, AnnData/H5AD matrices with coordinates in
`adata.obsm["spatial"]`, categorical annotations in `adata.obs`, microscopy
images such as TIFF, and local Zarr/SpatialData stores. Exact schema and
coordinate requirements belong to the selected upstream API.

Outputs are selected by the script: modified H5AD or Zarr objects, TIFF/image
artifacts, PNG/SVG/PDF static plots, TSV/CSV tables, and standard output or
logs. TAFFISH does not choose an output directory or overwrite policy for an
arbitrary Python program.

## Interactive Visualization

Squidpy removed its original interactive module upstream in 1.6.1 and now
directs users to `napari-spatialdata`. This app therefore does not duplicate a
Qt/noVNC GUI stack or expose a long-running browser service. For interactive
SpatialData viewing, use the separate `taf-spatialdata spatialdata-gui`
interface and its documented port, security, and Ctrl-C lifecycle contract.
Static Squidpy plotting is fully supported here through Matplotlib `Agg`.

## Resources, Networking, and Platform

Both declared architectures are native. Numerical threads default to one to
avoid container oversubscription; scripts may choose their own supported
parallelism. Large images, graph permutations, Dask computations, and
materialized Zarr arrays can require substantial RAM, CPU, temporary disk, and
output storage. No GPU runtime is included.

Docker is the release-test backend. Podman and Apptainer use the same generic
TAFFISH container contract but have not been separately validated for this
release; input-path visibility and site policy remain backend responsibilities.

Most local analysis is offline-safe. `squidpy.datasets` downloads official
examples from `exampledata.scverse.org`, and `sq.gr.ligrec` fetches OmniPath
interactions when no interaction table is provided. Fully offline work must
stage its input data locally and pass a local interaction DataFrame to
`sq.gr.ligrec`. Remote object stores likewise need backend network access and
user-provided credentials.

The multi-stage image removes dependency tests, NumPy/PyArrow development
headers, static/debug archives, bytecode, resolver caches, and apt indexes in
their producing layers. The remaining large native wheels implement the
supported numerical, geospatial, image-codec, Dask, SpatialData, and plotting
surface; removing them would break advertised upstream functionality.

## Boundaries and Troubleshooting

- `No module named squidpy` usually means `python` ran outside this app; use
  `taf-squidpy python ...`.
- A dataset download or default ligand-receptor lookup fails under an offline
  backend by design; stage the data and interactions before the run.
- No `squidpy` executable is expected. Use the Python API.
- For an interactive napari view, use `taf-spatialdata`; this app supplies
  static plotting, not a GUI server.
- Tiny synthetic validation cannot establish scientific correctness,
  production-scale performance, or compatibility with every external store.

## Testing

Four independent offline smoke paths cover exact package/provenance identity
and Python help; a tiny spatial graph/statistics/SpatialLeiden workflow with
H5AD and plot output; ligand-receptor permutations using a local interaction
DataFrame rather than OmniPath; and TIFF loading, smoothing, watershed
segmentation, PNG rendering, Zarr save, and reload. Dockerfile self-checks use
only stable identity and lightweight image operations so QEMU builds are not
gated by full plotting, ligand-receptor permutations, or JIT-heavy analysis.

## License and Citation

TAFFISH app packaging is Apache-2.0. Squidpy remains BSD-3-Clause. Cite:

Palla et al. “Squidpy: a scalable framework for spatial omics analysis.”
*Nature Methods* 19, 171–178 (2022).
[doi:10.1038/s41592-021-01358-2](https://doi.org/10.1038/s41592-021-01358-2),
PMID 35102346.
