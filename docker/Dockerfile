# Fix the multi-platform base, not future APT/PyPI availability. Check TLS,
# index status and architecture before replacing anything; restoring a pinned
# artifact requires the same hash, not a new digest for different bytes.
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS base

FROM base AS native-wheels
# Both extensions are required by the upstream image-feature API. An x86 wheel
# is not an ARM binary; build from pristine, checksummed sdists on both runners.
RUN sed -i 's|http://deb.debian.org/|https://deb.debian.org/|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends g++ patchelf && rm -rf /var/lib/apt/lists/*
RUN python -m venv /tmp/wheel-env && /tmp/wheel-env/bin/python -m pip install --no-cache-dir \
    'setuptools==70.3.0' 'wheel==0.45.1' 'Cython==3.0.12' 'numpy==2.0.2' 'pytest==8.4.2' \
    'meson-python==0.17.1' 'meson==1.9.1' 'ninja==1.13.0'
ADD --checksum=sha256:c18ce6958197710ebce48584efc9a49fbdad44ff40ea89ed77f3a0cb602a1f3c https://files.pythonhosted.org/packages/30/82/66760622339251859a60f555b9e8c7a396a9030fd73b726111f25280876a/centrosome-1.3.4.tar.gz /tmp/src/centrosome.tar.gz
ADD --checksum=sha256:3d820f12497aba0bc962343b80b8d4620739e010f3ad0bbdd0390fccbdb1d9a0 https://files.pythonhosted.org/packages/62/e1/4e6c6568a4efd2e91472238159cc675ccb1cd842643ba44d03f3c61f2632/mahotas-1.4.19.tar.gz /tmp/src/mahotas-1.4.19.tar.gz
COPY docker/patch-centrosome.py /tmp/patch-centrosome.py
ENV PATH=/tmp/wheel-env/bin:$PATH
RUN set -eu; cd /tmp/src; tar -xzf centrosome.tar.gz; cd centrosome-1.3.4; \
    python /tmp/patch-centrosome.py; \
    /tmp/wheel-env/bin/python -m pip wheel --no-index --no-deps --no-build-isolation -w /wheels . ../mahotas-1.4.19.tar.gz; \
    mkdir -p /notices; cp LICENSE /notices/centrosome-LICENSE; cp centrosome/include/*.hpp /notices/; \
    tar -xOf ../mahotas-1.4.19.tar.gz mahotas-1.4.19/COPYING > /notices/mahotas-COPYING; \
    cp /tmp/patch-centrosome.py /notices/patch-centrosome.py

FROM base AS python-deps
ARG TARGETARCH
ARG SQUIDPY_WHEEL_URL=https://files.pythonhosted.org/packages/70/08/dc10dbbbb823abb351b5d4f00d1c6066117d6bc4fc33f9f39a1be3bb1498/squidpy-1.8.4-py3-none-any.whl
ARG SQUIDPY_WHEEL_SHA256=e9458f9e09d9bb491210a1382727edc37d223a4a98352fbb0693aea34e241823
ARG CP_WHEEL_URL=https://files.pythonhosted.org/packages/2f/c5/93e75d32d468eff9a4a8966ab4dcdd6d5d241303076cf0b87ac71436698a/cp_measure-0.2.0-py3-none-any.whl
ARG CP_WHEEL_SHA256=efbbd3b7f006dabd73ef452abc231dc87a249512140fb4652cab4ca304daf07d
ARG DOCREP_SOURCE_URL=https://files.pythonhosted.org/packages/44/8e/250fab1cafeea43f4eb11f1d64cd6313f639965ff62cb0d9da3883655781/docrep-0.3.2.tar.gz
ARG DOCREP_SOURCE_SHA256=ed8a17e201abd829ef8da78a0b6f4d51fb99a4cbd0554adbed3309297f964314
ARG CONSTRAINTS_SHA256=30a094e11a66da237dac097d3570270b3f5e47d773c595deb465a85fc482ec6f
ENV PATH=/opt/squidpy/bin:$PATH PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=4 PYTHONDONTWRITEBYTECODE=1
COPY docker/constraints.txt /tmp/constraints.txt
COPY --from=native-wheels /wheels/ /tmp/wheels/
COPY --from=native-wheels /notices/ /opt/squidpy/share/doc/squidpy/third-party/
# Constraints align package versions, not every transitive wheel's bytes. Never
# solve a disappearance/conflict by ignoring dependencies or downgrading Pillow.
# Review an upstream fix, then rebuild both architectures and test the real APIs.
RUN --mount=type=cache,id=squidpy-pip-${TARGETARCH},target=/root/.cache/pip,sharing=locked \
    set -eu; echo "${CONSTRAINTS_SHA256}  /tmp/constraints.txt" | sha256sum -c -; \
    python -m venv /opt/squidpy; python -m pip install 'pip==26.2.1' 'setuptools==84.0.0'; \
    python -m pip install --no-build-isolation -c /tmp/constraints.txt "docrep @ ${DOCREP_SOURCE_URL}#sha256=${DOCREP_SOURCE_SHA256}"; \
    for attempt in 1 2 3; do \
      python -m pip install --only-binary=:all: -c /tmp/constraints.txt /tmp/wheels/*.whl \
        "squidpy[leiden] @ ${SQUIDPY_WHEEL_URL}#sha256=${SQUIDPY_WHEEL_SHA256}" "cp-measure @ ${CP_WHEEL_URL}#sha256=${CP_WHEEL_SHA256}" && break; \
      test "$attempt" != 3 || exit 1; sleep 2; done; \
    python -m pip check; docs=/opt/squidpy/share/doc/squidpy; \
    python -c 'import importlib.metadata as m; print("\n".join(sorted(d.metadata["Name"]+"=="+d.version for d in m.distributions())))' > "$docs/requirements.freeze.txt"; \
    cp /tmp/constraints.txt "$docs/constraints.txt"; cp /opt/squidpy/lib/python3.12/site-packages/squidpy-1.8.4.dist-info/licenses/LICENSE "$docs/LICENSE.upstream"; \
    printf '%s\n' 'upstream_tag=v1.8.4' 'upstream_commit=a27c14f24ee55e4d86f1aea6b77287316f816bcb' \
      "wheel_sha256=${SQUIDPY_WHEEL_SHA256}" "wheel_url=${SQUIDPY_WHEEL_URL}" "constraints_sha256=${CONSTRAINTS_SHA256}" \
      "docrep_source_sha256=${DOCREP_SOURCE_SHA256}" "cp_measure_wheel_sha256=${CP_WHEEL_SHA256}" \
      'centrosome=1.3.4+taffish.1' 'centrosome_source_sha256=c18ce6958197710ebce48584efc9a49fbdad44ff40ea89ed77f3a0cb602a1f3c' \
      'mahotas_source_sha256=3d820f12497aba0bc962343b80b8d4620739e010f3ad0bbdd0390fccbdb1d9a0' > "$docs/SOURCE"
# Restrict pruning to audited large suites. In particular mahotas imports its
# own tests package at runtime; a blanket directory-name rule breaks the API.
RUN set -eu; site=/opt/squidpy/lib/python3.12/site-packages; \
    for name in numpy scipy pyarrow pandas sklearn skimage matplotlib; do \
      find "$site/$name" -type d \( -name tests -o -name test \) -prune -exec rm -rf '{}' +; done; \
    rm -rf /opt/squidpy/lib/python3.12/site-packages/numpy/_core/include /opt/squidpy/lib/python3.12/site-packages/pyarrow/include; \
    find /opt/squidpy/lib/python3.12/site-packages -type f \( -name '*.a' -o -name '*.so.debug' \) -delete; \
    find /opt/squidpy -type d -name __pycache__ -prune -exec rm -rf '{}' +

FROM base
ENV PATH=/opt/squidpy/bin:$PATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
ENV SQUIDPY_HOME=/opt/squidpy SQUIDPY_TESTDATA=/opt/squidpy/share/testdata TAFFISH_ENV=TAFFISH TAFFISH_NAME=squidpy
# The signed Debian suite still moves independently of the base digest. Check
# repository/TLS/architecture issues first; a replacement is a new tested input.
RUN set -eu; tbb=''; if [ "$(dpkg --print-architecture)" = amd64 ]; then tbb=libtbb12; fi; \
    sed -i 's|http://deb.debian.org/|https://deb.debian.org/|g' /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::Retries=3 update; apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    bash ca-certificates curl fontconfig fonts-dejavu-core libgfortran5 libgomp1 libstdc++6 $tbb; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
    install -d -m 0755 /opt/squidpy/share/testdata /opt/squidpy/share/taffish /dataset-install /datasets/squidpy /squidpy-network
COPY --from=python-deps /opt/squidpy /opt/squidpy
COPY docker/squidpy_smoke.py /opt/squidpy/share/testdata/squidpy_smoke.py
COPY docker/squidpy_data.py docker/squidpy_store.py docker/squidpy_policy.py /opt/squidpy/lib/python3.12/site-packages/
COPY docker/squidpy-sitecustomize.py /opt/squidpy/lib/python3.12/site-packages/sitecustomize.py
COPY docker/squidpy-data /opt/squidpy/bin/squidpy-data
# Only stable metadata and a tiny, non-rendering native extension call belong
# here. Plotting, JIT, process timing and actual resource mounts are runtime gates.
RUN set -eu; python -m pip check; \
    python -c 'from importlib.metadata import version; assert [version(n) for n in ("squidpy","centrosome","Pillow","mahotas","cp-measure")] == ["1.8.4","1.3.4+taffish.1","13.0.0","1.4.19","0.2.0"]; import numpy as np, mahotas; import centrosome._lapjv; assert mahotas.label(np.array([[0,1],[0,0]],dtype=bool))[1] == 1'; \
    chmod 0755 /opt/squidpy/share/testdata/squidpy_smoke.py /opt/squidpy/bin/squidpy-data; squidpy-data --version
WORKDIR /root
