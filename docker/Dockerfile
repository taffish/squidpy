ARG SQUIDPY_VERSION=1.8.3
ARG SQUIDPY_WHEEL_URL=https://files.pythonhosted.org/packages/2b/5c/3c5e524ee2aa8acdd05b298dd285ef7abbbdb3333b15e29738d34e0372bc/squidpy-1.8.3-py3-none-any.whl
ARG SQUIDPY_WHEEL_SHA256=05fd5da00db697e6d0dbb91ff543ff5b27d0046666ce5a7348548076b3310efc
ARG DOCREP_VERSION=0.3.2
ARG DOCREP_SOURCE_URL=https://files.pythonhosted.org/packages/44/8e/250fab1cafeea43f4eb11f1d64cd6313f639965ff62cb0d9da3883655781/docrep-0.3.2.tar.gz
ARG DOCREP_SOURCE_SHA256=ed8a17e201abd829ef8da78a0b6f4d51fb99a4cbd0554adbed3309297f964314
ARG SQUIDPY_CONSTRAINTS_SHA256=0a33978dca71c6f1f302eeec1cf3f90cf94f343649ea854bc35064f112604541

FROM python:3.12.13-slim-bookworm AS builder

ARG SQUIDPY_VERSION
ARG SQUIDPY_WHEEL_URL
ARG SQUIDPY_WHEEL_SHA256
ARG DOCREP_VERSION
ARG DOCREP_SOURCE_URL
ARG DOCREP_SOURCE_SHA256
ARG SQUIDPY_CONSTRAINTS_SHA256
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=5
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MPLBACKEND=Agg
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV NUMBA_CACHE_DIR=/tmp/numba-cache
ENV XDG_CACHE_HOME=/tmp/xdg-cache
ENV DASK_TEMPORARY_DIRECTORY=/tmp/dask-worker-space
ENV PATH=/opt/squidpy/bin:${PATH}

COPY docker/constraints.txt /tmp/squidpy-constraints.txt

RUN set -eux; \
    echo "${SQUIDPY_CONSTRAINTS_SHA256}  /tmp/squidpy-constraints.txt" | sha256sum -c -; \
    python -m venv /opt/squidpy; \
    python -m pip install 'pip==26.2.1'; \
    python -m pip install 'setuptools==84.0.0'; \
    python -m pip install --no-build-isolation \
      --constraint /tmp/squidpy-constraints.txt \
      "docrep @ ${DOCREP_SOURCE_URL}#sha256=${DOCREP_SOURCE_SHA256}"; \
    python -m pip install --only-binary=:all: \
      --constraint /tmp/squidpy-constraints.txt \
      "squidpy[leiden] @ ${SQUIDPY_WHEEL_URL}#sha256=${SQUIDPY_WHEEL_SHA256}"; \
    python -m pip check; \
    mkdir -p /opt/squidpy/share/doc/squidpy /opt/squidpy/share/testdata; \
    python -m pip freeze --all > /opt/squidpy/share/doc/squidpy/requirements.freeze.txt; \
    cp /opt/squidpy/lib/python3.12/site-packages/squidpy-${SQUIDPY_VERSION}.dist-info/licenses/LICENSE \
      /opt/squidpy/share/doc/squidpy/LICENSE.upstream; \
    cp /tmp/squidpy-constraints.txt \
      /opt/squidpy/share/doc/squidpy/constraints.txt; \
    printf '%s\n' \
      'upstream_repo=https://github.com/scverse/squidpy' \
      'upstream_tag=v1.8.3' \
      'upstream_commit=005c9056fea7c5432fb220abc9b48a384fb8c090' \
      "upstream_version=${SQUIDPY_VERSION}" \
      "wheel_url=${SQUIDPY_WHEEL_URL}" \
      "wheel_sha256=${SQUIDPY_WHEEL_SHA256}" \
      "docrep_version=${DOCREP_VERSION}" \
      "docrep_source_url=${DOCREP_SOURCE_URL}" \
      "docrep_source_sha256=${DOCREP_SOURCE_SHA256}" \
      "constraints_sha256=${SQUIDPY_CONSTRAINTS_SHA256}" \
      'python_requirement=>=3.12' \
      'scope=Squidpy core runtime plus the complete official leiden extra' \
      'gui=Squidpy interactive module was removed upstream; use napari-spatialdata' \
      'boundary=official datasets and default OmniPath ligand-receptor interactions require network access' \
      > /opt/squidpy/share/doc/squidpy/SOURCE

COPY docker/squidpy_smoke.py /opt/squidpy/share/testdata/squidpy_smoke.py

RUN set -eux; \
    chmod 0755 /opt/squidpy/share/testdata/squidpy_smoke.py; \
    test "$(python -c 'import importlib.metadata as md; print(md.version("squidpy"))')" = "${SQUIDPY_VERSION}"; \
    python /opt/squidpy/share/testdata/squidpy_smoke.py identity \
      | grep -Fx "squidpy=${SQUIDPY_VERSION}" >/dev/null; \
    SQUIDPY_BUILDTIME=1 \
      python /opt/squidpy/share/testdata/squidpy_smoke.py image /tmp/squidpy-buildtime \
      | grep -Fx 'image=ok' >/dev/null; \
    grep -Fx "wheel_sha256=${SQUIDPY_WHEEL_SHA256}" \
      /opt/squidpy/share/doc/squidpy/SOURCE >/dev/null; \
    find /opt/squidpy/lib/python3.12/site-packages -type d \
      \( -name test -o -name tests \) -prune -exec rm -rf '{}' +; \
    rm -rf \
      /opt/squidpy/lib/python3.12/site-packages/numpy/_core/include \
      /opt/squidpy/lib/python3.12/site-packages/pyarrow/include; \
    find /opt/squidpy/lib/python3.12/site-packages -type f \
      \( -name '*.a' -o -name '*.so.debug' \) -delete; \
    find /opt/squidpy -type d -name '__pycache__' -prune -exec rm -rf '{}' +; \
    find /opt/squidpy -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete; \
    rm -rf /tmp/squidpy-buildtime /tmp/numba-cache /tmp/xdg-cache /tmp/dask-worker-space /root/.cache

FROM python:3.12.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MPLBACKEND=Agg
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV NUMBA_CACHE_DIR=/tmp/numba-cache
ENV XDG_CACHE_HOME=/tmp/xdg-cache
ENV DASK_TEMPORARY_DIRECTORY=/tmp/dask-worker-space
ENV PATH=/opt/squidpy/bin:${PATH}
ENV SQUIDPY_HOME=/opt/squidpy
ENV SQUIDPY_TESTDATA=/opt/squidpy/share/testdata

RUN set -eux; \
    runtime_tbb=''; \
    if [ "$(dpkg --print-architecture)" = 'amd64' ]; then \
      runtime_tbb='libtbb12'; \
    fi; \
    for attempt in 1 2 3; do \
      if apt-get -o Acquire::Retries=3 update \
       && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
            bash \
            ca-certificates \
            fontconfig \
            fonts-dejavu-core \
            libgfortran5 \
            libgomp1 \
            libstdc++6 \
            $runtime_tbb; then \
        break; \
      fi; \
      if [ "$attempt" = '3' ]; then exit 1; fi; \
      apt-get clean; \
      rm -rf /var/lib/apt/lists/*; \
      sleep 5; \
    done; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

COPY --from=builder /opt/squidpy /opt/squidpy

RUN set -eux; \
    python -m pip check; \
    test "$(python -c 'import importlib.metadata as md; print(md.version("squidpy"))')" = '1.8.3'; \
    python /opt/squidpy/share/testdata/squidpy_smoke.py identity \
      | grep -Fx 'squidpy=1.8.3' >/dev/null; \
    : > /tmp/squidpy-ldd.txt; \
    ldd "$(command -v python)" >> /tmp/squidpy-ldd.txt 2>&1; \
    python -c 'import h5py._errors, imagecodecs._imcd, igraph._igraph, matplotlib._path, numpy._core._multiarray_umath, pyarrow.lib, pyogrio._ogr, scipy._lib._ccallback_c, shapely.lib; print("\n".join(m.__file__ for m in (h5py._errors, imagecodecs._imcd, igraph._igraph, matplotlib._path, numpy._core._multiarray_umath, pyarrow.lib, pyogrio._ogr, scipy._lib._ccallback_c, shapely.lib) if ".so" in m.__file__))' \
      | while IFS= read -r extension; do ldd "$extension" >> /tmp/squidpy-ldd.txt 2>&1; done; \
    if grep -F 'not found' /tmp/squidpy-ldd.txt; then exit 1; fi; \
    rm -rf /tmp/squidpy-ldd.txt /tmp/numba-cache /tmp/xdg-cache /tmp/dask-worker-space /root/.cache; \
    test -z "$(find /opt/squidpy -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -quit)"

WORKDIR /root

ENV TAFFISH_ENV=TAFFISH
ENV TAFFISH_NAME=squidpy
