# Squidpy for TAFFISH

Run spatial graph statistics, ligand–receptor permutations and microscopy image analysis with the official [Squidpy 1.8.4 release](https://github.com/scverse/squidpy/releases/tag/v1.8.4). This tool packages Python 3.12, the required dependencies and the official `leiden` extra. There is no upstream `squidpy` executable.

## Install and run

```sh
taf install squidpy 1.8.4-r1
taf-squidpy --help
taf-squidpy python analysis.py
taf-squidpy python "'scripts/spatial analysis.py'"
```

The working directory is mounted by the wrapper. Automatic command mode reconstructs a shell command: pass literal inner quotes for an argument containing spaces. With a local AnnData object containing coordinates in `obsm["spatial"]`, a script can run entirely offline:

```python
import anndata as ad
import squidpy as sq

adata = ad.read_h5ad("local-input.h5ad")
sq.gr.spatial_neighbors_grid(adata, n_neighs=6)
sq.gr.spatial_autocorr(adata, mode="moran")
adata.write_h5ad("result.h5ad")
```

Use scripts to select H5AD, TIFF, Zarr/SpatialData, tables and output files. Version 1.8.4 adds experimental per-cell features (`sq.experimental.im.calculate_image_features`) and conditional/COZI neighborhood enrichment. Use `rng=` for seeded permutations. `cp_measure`, Scanpy, SpatialData, spatialdata-plot and SpatialLeiden are in the image. Matplotlib uses headless Agg; write PNG/SVG/PDF to the working directory. For a desktop viewer use the separate [TAFFISH SpatialData app](https://github.com/taffish/spatialdata). This package does not start a GUI, Jupyter server or GPU service.

For Squidpy plotting methods that accept `save=`, relative names are placed under `scanpy.settings.figdir`. Pass an absolute path, such as `Path("results/image.png").resolve()`, to select the exact project output location.

## Choose a resource

No datasets, models, database dumps, OmniPath snapshots or credentials are bundled. Your own project files need no managed library. For a reusable example, select a name with `taf-squidpy squidpy-data catalog`; preview `install --dataset NAME --dry-run`. A Visium count/spatial member and its optional `--hires` variant are separate snapshots. Preview lists sources, expected bytes (or why unknown), SHA-256, rights, destination and free-space reserve. Allocate space for both verified transport bytes and the installed copy, plus scratch for analysis and unpacking.

The registry is the YAML inside the fixed Squidpy wheel. Only the reviewed [10x Visium fluorescent section 2 dataset](https://www.10xgenomics.com/datasets/adult-mouse-brain-section-2-coronal-stains-dapi-anti-gfap-anti-neu-n-1-standard-1-1-0) and its registered Squidpy derivatives permit managed public fetch: `visium_fluo_adata_crop`, `visium_fluo_adata`, `visium_fluo_image_crop`, and `V1_Adult_Mouse_Brain_Coronal_Section_2`. Retain source attribution under CC BY 4.0. For other entries review the provider's terms (including shared/site use), obtain the named files yourself, and use `--source-dir` with `--rights-file`. A missing upstream digest can only be pinned from authorized local bytes; that digest is not a provider signature. No bulk mirror or redistribution permission is implied.

### Install once; consume read-only

Use a dedicated new directory owned by the installer, mode 0755. For a personal installation use `$HOME/.local/share/taffish/datasets/squidpy`. For a system installation the administrator prepares `/usr/local/share/taffish/datasets/squidpy` (or `/opt/taffish/datasets/squidpy`) **once**, using their own authorized container runtime. Ordinary users do not need to install or write to it. Do not chmod a shared parent or an unrelated data directory.

The three equivalent preparation commands are shown in `taf-squidpy --help`. Only the installer mounts the library read-write at `/dataset-install`; during installation disable automatic discovery. Subsequent Python processes check the entire selected library before loading it. A read-only bind at `/datasets/squidpy` is required. Explicit `TAFFISH_SQUIDPY_DATASET_PATH` wins, followed by personal, system and /opt; an invalid higher-priority root does not fall through. A valid root symlink resolves to its physical directory; a broken link is an error. To process unrelated local files, set `TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT=0`. For spaces use a quoted manual bind (paths containing a mount delimiter such as a colon are unsuitable):

```sh
export TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT=0
LIB="/absolute/path with spaces/squidpy"
TAFFISH_CONTAINER_BACKEND=docker TAFFISH_DOCKER_RUN_ARGS="-v '$LIB:/datasets/squidpy:ro'" taf-squidpy squidpy-data verify
TAFFISH_CONTAINER_BACKEND=podman TAFFISH_PODMAN_RUN_ARGS="--userns keep-id -v '$LIB:/datasets/squidpy:ro'" taf-squidpy squidpy-data verify
TAFFISH_CONTAINER_BACKEND=apptainer TAFFISH_APPTAINER_RUN_ARGS="--bind '$LIB:/datasets/squidpy:ro'" taf-squidpy squidpy-data verify
unset TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT
```

Each published member contains its file list, URLs, SHA-256, sizes, rights notice and READY fingerprint. Installation, idempotent reuse and discovery validate all installed members, not just the selected ID. An interruption leaves valid members intact. Repeat the identical command: a private partial can resume on a range-capable HTTPS source or from identical local bytes. A persistent lock filename does not mean a live process holds the kernel lock. On checksum, ownership or conflicting-recipe failure, stop and inspect the named object; do not force replace, delete a lock, or clear the library. Restore the authorized bytes or install in a new dedicated root. Per-user plotting/JIT and archive extraction use private scratch, not the shared install directory.

### Local ligand–receptor tables

Pass a DataFrame with source and target columns to `sq.gr.ligrec(..., interactions=table)`. Leaving it unspecified now fails before the upstream default OmniPath lookup. [OmniPath](https://omnipathdb.org/) integrates sources with different terms: review the provider's actual rights and intended use. Never put credentials, private source URLs, or license keys into a shareable recipe. A private local file can be read without a recipe. For an authorized reusable table:

```sh
taf-squidpy squidpy-data pin-table --id my-panel --file interactions.tsv --url https://example.org/fixed-release/interactions.tsv --rights-file NOTICE.txt > panel.json
```

Replace the example URL with the real public, fixed origin. With the installation bind above, use `install --table-recipe panel.json --source-dir .` from the directory containing the file named `interactions.tsv`. For an explicitly authorized pinned online table use `--fetch` instead. The installed table is `/datasets/squidpy/table.my-panel/interactions.tsv`; use `pandas.read_csv(path, sep="\t")`. The helper verifies identity and transport, not the scientific meaning of a table.

### Optional private example cache

Prefer verified installation. To deliberately use the upstream example downloader in a **separate private cache**, choose a dataset you may obtain and use, create an empty directory you own with mode 0700, disable discovery, and pass the opt-in **into the container**. Choose one row; never use a prepared library for this writable cache.

```sh
CACHE="$HOME/.cache/squidpy-online"; mkdir -p "$CACHE" && chmod 0700 "$CACHE"
export TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT=0
TAFFISH_CONTAINER_BACKEND=docker TAFFISH_DOCKER_RUN_ARGS="--user $(id -u):$(id -g) --env TAFFISH_SQUIDPY_ALLOW_NETWORK=1 -v '$CACHE:/squidpy-network:rw'" taf-squidpy python analysis.py
TAFFISH_CONTAINER_BACKEND=podman TAFFISH_PODMAN_RUN_ARGS="--userns keep-id --user $(id -u):$(id -g) --env TAFFISH_SQUIDPY_ALLOW_NETWORK=1 -v '$CACHE:/squidpy-network:rw'" taf-squidpy python analysis.py
TAFFISH_CONTAINER_BACKEND=apptainer TAFFISH_APPTAINER_RUN_ARGS="--env TAFFISH_SQUIDPY_ALLOW_NETWORK=1 --bind '$CACHE:/squidpy-network:rw'" taf-squidpy python analysis.py
unset TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT
```

This opt-in changes example acquisition only. It is not an offline sandbox for arbitrary Python, a grant of dataset rights, or a way to enable implicit OmniPath calls. Consult site network policy for remote object stores. Use local files or a verified read-only installation for repeatable offline operation.

## Packaging and attribution

Image: `ghcr.io/taffish/squidpy:1.8.4-r1`, native Linux amd64/arm64. The official Squidpy wheel is unmodified. `cp-measure 0.2.0` requires centrosome, whose current official release caps Pillow below 12 ([upstream issue #136](https://github.com/CellProfiler/centrosome/issues/136)). This app builds the explicitly marked dependency `centrosome 1.3.4+taffish.1`: its metadata pins Pillow 13.0.0, its grayscale reader uses current byte APIs and the declared byte order, and it passes 8-bit L pixels to the floating-point fitter without changing their 0–255 values. Background fitting, normalization and all Squidpy numerical routines are unchanged. This is a downstream compatibility patch, not an official centrosome release. Both centrosome and mahotas are compiled for the target CPU.

The final uncompressed image measures 1,293,892,003 bytes on amd64 and 1,340,197,687 on arm64 (about 4% more than 1.8.3-r1). The runtime keeps the libraries used by spatial, geospatial and image APIs, including llvmlite, PyArrow, Pyogrio, SciPy, imagecodecs and the new native extensions; the development compiler toolchain and download cache are not part of the image.

Fixed sources, constraints, installed versions, patch and third-party notices are under `/opt/squidpy/share/doc/squidpy`. The multistage build leaves compilers outside the runtime; tested large test suites, development headers, static/debug archives and bytecode are pruned. Runtime-imported modules (including mahotas.tests) stay. Python wheels and Debian repositories remain external build inputs, not a permanent mirror. Numerical threads default to one. Plan RAM, scratch and output space for your image size and permutation count. Tiny offline checks demonstrate supported interfaces, not scientific or production-scale validity.

Native validation covered Docker/Podman on Linux arm64 and Docker/Podman/Apptainer on x86-64 Linux, using the built wrapper, offline analyses and actual host bind mounts. The x86-64 site fixture was prepared once by container root and read offline by ordinary users on all three engines. The reviewed fluorescent crop was verified and loaded as 704 × 16,562; the rest of the catalog is not claimed individually validated. A separate private-cache download and checked offline reuse were also exercised. The 8-bit and 16-bit grayscale reader results were compared with the same pixels supplied as floating-point TIFFs.

Packaging: Apache-2.0; Squidpy: BSD-3-Clause. Dataset terms are separate. Cite Palla et al., *Nature Methods* 19, 171–178 (2022), [doi:10.1038/s41592-021-01358-2](https://doi.org/10.1038/s41592-021-01358-2). See also the [Squidpy user guide](https://squidpy.readthedocs.io/en/stable/).
