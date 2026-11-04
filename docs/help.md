squidpy 1.8.4-r1

Quick start:
  taf-squidpy python analysis.py
  taf-squidpy python "'scripts/spatial analysis.py'"
  taf-squidpy python -c '"import squidpy as sq; print(sq.__version__)"'
  taf-squidpy -- --help
  The default command is Python, not a squidpy executable. Pass literal inner
  quotes around paths containing spaces in automatic command mode.

Inputs and outputs:
  Read local H5AD, TIFF or SpatialData/Zarr files from your working directory.
  Graph methods usually need adata.obsm["spatial"]; image feature extraction
  needs aligned images and labels. Your script chooses output paths for H5AD,
  Zarr, tables or plots; allow writable scratch space for large images.
  Save PNG/SVG/PDF via Matplotlib. To explore SpatialData interactively,
  use the separate taf-spatialdata spatialdata-gui command.

Examples and interaction tables:
  Working with project files does not require a dataset library.
  taf-squidpy squidpy-data catalog
  taf-squidpy squidpy-data install --dataset visium_fluo_adata_crop --dry-run
  Choose individual datasets. Preview size, source, rights and destination;
  allow for the private download cache, installed copy and free-space reserve.

Prepare once (run one backend command):
  LIB="$HOME/.local/share/taffish/datasets/squidpy"
  mkdir -p "$LIB" && chmod 0755 "$LIB"
  export TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT=0
  TAFFISH_CONTAINER_BACKEND=docker TAFFISH_DOCKER_RUN_ARGS="--user $(id -u):$(id -g) -v '$LIB:/dataset-install:rw'" taf-squidpy squidpy-data install --dataset visium_fluo_adata_crop --fetch
  TAFFISH_CONTAINER_BACKEND=podman TAFFISH_PODMAN_RUN_ARGS="--userns keep-id --user $(id -u):$(id -g) -v '$LIB:/dataset-install:rw'" taf-squidpy squidpy-data install --dataset visium_fluo_adata_crop --fetch
  TAFFISH_CONTAINER_BACKEND=apptainer TAFFISH_APPTAINER_RUN_ARGS="--bind '$LIB:/dataset-install:rw'" taf-squidpy squidpy-data install --dataset visium_fluo_adata_crop --fetch
  unset TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT
  Use a dedicated directory you own. An administrator can instead prepare
  /usr/local/share/taffish/datasets/squidpy once for ordinary users.
  Repeat the same install after an interruption; do not remove the lock,
  recovery files or completed members. Never overwrite a conflicting snapshot.

Use offline:
  taf-squidpy squidpy-data verify
  taf-squidpy python -c '"import squidpy as sq; print(sq.datasets.visium_fluo_adata_crop().shape)"'
  Discovery mounts the first selected library at /datasets/squidpy read-only:
  explicit TAFFISH_SQUIDPY_DATASET_PATH, then the personal path above, then
  /usr/local/share/taffish/datasets/squidpy and /opt/taffish/datasets/squidpy.
  A bad selected library fails; no other library is silently substituted.
  For a path with spaces, set TAFFISH_SQUIDPY_DATASET_AUTO_MOUNT=0 and use
  the same backend bind syntax above with '$LIB:/datasets/squidpy:ro'.
  An absent dataset fails without downloading. For names outside the reviewed
  fetch list, supply --source-dir and --rights-file with authorized local files.
  For sq.gr.ligrec, pass interactions= with source/target columns in a local
  DataFrame. No live OmniPath table is selected for you. For a reusable table:
  taf-squidpy squidpy-data pin-table --help
  See README for table recipes and explicitly enabled private online caches.

Help:
  taf-squidpy --help                 Installed usage help
  taf-squidpy --version              Wrapper version
  taf-squidpy squidpy-data --help    Resource helper commands
  https://github.com/taffish/squidpy
