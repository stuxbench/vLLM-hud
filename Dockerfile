# vLLM CPU Dockerfile with MCP server integration
# Supports both AMD x86_64 (HUD) and ARM64 (Mac) architectures

######################### COMMON BASE IMAGE #########################
FROM ubuntu:22.04 AS base-common

WORKDIR /workspace/

ARG PYTHON_VERSION=3.12
ARG PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"

# Install minimal dependencies and uv
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -y \
    && apt-get install -y --no-install-recommends ccache git curl wget ca-certificates \
    gcc-12 g++-12 libtcmalloc-minimal4 libnuma-dev ffmpeg libsm6 libxext6 libgl1 jq lsof \
    sudo build-essential python3-pip \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 10 --slave /usr/bin/g++ g++ /usr/bin/g++-12 \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV CCACHE_DIR=/root/.cache/ccache
ENV CMAKE_CXX_COMPILER_LAUNCHER=ccache

ENV PATH="/root/.local/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python
RUN uv venv --python ${PYTHON_VERSION} --seed ${VIRTUAL_ENV}
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV UV_HTTP_TIMEOUT=500

######################### x86_64 BASE IMAGE #########################
FROM base-common AS base-amd64

ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4:/opt/venv/lib/libiomp5.so"

######################### arm64 BASE IMAGE #########################
FROM base-common AS base-arm64

ENV LD_PRELOAD="/usr/lib/aarch64-linux-gnu/libtcmalloc_minimal.so.4"

######################### BASE IMAGE #########################
ARG TARGETARCH
FROM base-${TARGETARCH} AS base

RUN echo 'ulimit -c 0' >> ~/.bashrc

######################### vLLM BUILD STAGE #########################
FROM base AS vllm-build

# Support for building with non-AVX512 vLLM
ARG VLLM_CPU_DISABLE_AVX512=0
ENV VLLM_CPU_DISABLE_AVX512=${VLLM_CPU_DISABLE_AVX512}
# Support for building with AVX512BF16 ISA
ARG VLLM_CPU_AVX512BF16=0
ENV VLLM_CPU_AVX512BF16=${VLLM_CPU_AVX512BF16}
# Support for building with AVX512VNNI ISA
ARG VLLM_CPU_AVX512VNNI=0
ENV VLLM_CPU_AVX512VNNI=${VLLM_CPU_AVX512VNNI}

# Clone vllm repository with GitHub credentials
# ENV GITHUB_TOKEN_BASE64="place personal github token here"
# ENV GITHUB_USERNAME="place github username here"
WORKDIR /workspace
RUN GITHUB_TOKEN=$(echo "$GITHUB_TOKEN_BASE64" | base64 -d); \
    git clone https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/stuxbench/vLLM-clone vllm

WORKDIR /workspace/vllm

# Install Python dependencies for CPU
ENV PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
ENV UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
ENV UV_INDEX_STRATEGY="unsafe-best-match"
ENV UV_LINK_MODE="copy"

# Install build dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --upgrade pip wheel setuptools setuptools-scm cmake ninja packaging torch==2.8.0 jinja2

# Checkout branches and create patches (commented for now)
ARG VULN_BRANCH=baseline
# RUN git checkout $VULN_BRANCH

ARG TEST_BRANCH=test
ARG GOLDEN_BRANCH=golden  
# RUN git checkout $TEST_BRANCH
# RUN git checkout $GOLDEN_BRANCH

# Create test patch (adds the test back to vulnerable code)
# RUN mkdir -p /home/root
# RUN git diff $VULN_BRANCH $GOLDEN_BRANCH > /home/root/test.patch
# RUN chmod 600 /home/root/test.patch

# Go back to baseline state (vulnerable state without tests)
# RUN git checkout $VULN_BRANCH
# RUN rm -rf .git
# RUN git init && \
#     git config --global user.email "test@example.com" && \
#     git config --global user.name "Test User"
# RUN git add .
# RUN git commit -m "Initial commit"

# Build vLLM for CPU (limit parallel jobs to reduce memory usage)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/ccache \
    --mount=type=cache,target=/workspace/vllm/.deps,sharing=locked \
    MAX_JOBS=4 VLLM_TARGET_DEVICE=cpu python3 setup.py bdist_wheel

######################### MCP SERVER STAGE #########################
FROM base AS mcp-server

WORKDIR /app

# Copy vLLM source code -- only needed for current trivial task
COPY --from=vllm-build /workspace/vllm /workspace/vllm

# Install vLLM from build stage
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,from=vllm-build,src=/workspace/vllm/dist,target=dist \
    uv pip install dist/*.whl

# Install additional testing dependencies  
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install pytest mcp hud-python

# Copy MCP server code and shared utilities
COPY src/ /app/src/
COPY shared/ /app/shared/
COPY pyproject.toml /app/pyproject.toml

# Install MCP server dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -e .

# Start services
CMD ["sh", "-c", "python3 -m src.controller.env & sleep 2 && exec python3 -m src.controller.server"]