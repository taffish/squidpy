squidpy 1.8.3-r1

Purpose:
  Analyze spatial molecular data with Squidpy graphs, statistics, microscopy
  image processing, ligand-receptor methods, and static plotting.

Usage:
  taf-squidpy -- --help
  taf-squidpy python analysis.py
  taf-squidpy python -c '"import squidpy as sq; print(sq.__version__)"'
  taf-squidpy python -m pip list

Important command behavior:
  Squidpy 1.8.3 has no squidpy console executable. The default command is the
  Python 3.12 interpreter, and analyses use the Squidpy Python API.
  Use the explicit "python" command for scripts and one-line expressions.

Common workflow:
  1. Prepare a Python script and local AnnData, image, or SpatialData input.
  2. Store spatial coordinates in adata.obsm["spatial"] when required.
  3. Call squidpy.gr, squidpy.im, squidpy.pl, or squidpy.read functions.
  4. Choose output paths in the script, then run:
       taf-squidpy python analysis.py
  5. Inspect the H5AD, Zarr, table, image, plot, or log outputs you selected.

Packaged runtime:
  python             Default Python 3.12 interpreter.
  squidpy 1.8.3      Spatial graph, image, statistics, and plotting APIs.
  scanpy 1.12.3      AnnData preprocessing and single-cell analysis.
  spatialdata 0.8.0  Multimodal spatial data model and Zarr support.
  spatialleiden      Official Squidpy leiden extra; version 0.4.0.

Typical inputs:
  analysis.py        Python program using the packaged APIs.
  *.h5ad             AnnData matrix, annotations, and spatial coordinates.
  *.tif or *.tiff    Microscopy image accepted by ImageContainer.
  *.zarr             Local Zarr or SpatialData store.

Key outputs:
  *.h5ad or *.zarr   Modified analysis objects written by your script.
  *.tsv or *.csv     Statistics and graph summaries selected by your script.
  *.png/*.svg/*.pdf  Static Matplotlib plots using the headless Agg backend.
  Output locations and overwrite behavior are controlled by your script.

Paths with spaces:
  Preserve literal quotes through automatic command mode:
  taf-squidpy python "'scripts/spatial analysis.py'"

Networking and offline use:
  squidpy.datasets downloads official examples on first use.
  sq.gr.ligrec fetches OmniPath data when no interaction table is supplied.
  For an offline run, stage inputs locally and pass a local interaction
  DataFrame. Remote object stores need network access and user credentials.

Interactive visualization:
  Squidpy removed its original interactive module upstream. This app provides
  static plots, not napari, Qt, noVNC, or a browser service. Use the separate
  taf-spatialdata spatialdata-gui command for napari-spatialdata viewing.

Platform and resources:
  Native linux/amd64 and linux/arm64 images are provided. No GPU/CUDA runtime,
  Jupyter server, datasets, reference atlas, or credentials are included.
  Large images, permutations, and Dask jobs may need substantial RAM, CPU,
  temporary disk, and output storage. Numerical threads default to one.
  Docker is verified; Podman and Apptainer follow the generic wrapper contract
  but remain backend-specific validation boundaries for this release.

Boundaries:
  Tiny integration checks do not establish scientific correctness or
  production-scale performance. API options and input schemas remain defined
  by the upstream Squidpy documentation.

Detailed documentation:
  https://github.com/taffish/squidpy
  https://squidpy.readthedocs.io/en/stable/

Wrapper options:
  taf-squidpy --help       Show this TAFFISH help.
  taf-squidpy --version    Show TAFFISH wrapper version.
  taf-squidpy --compile    Print generated shell code.
  taf-squidpy -- --help    Pass --help to the default Python interpreter.
