# Hugging Face Space (Docker SDK). This file and README.md are the only files the Space repo needs.
# The Space build fetches the app source from GitHub at REPO_REF, so there is one source of truth.
ARG SOURCE=github
ARG REPO_REF=main

FROM python:3.12-slim AS src-github
ARG REPO_REF
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir /src \
 && curl -fsSL "https://codeload.github.com/SolomonSmith-dev/soc-triage-ai/tar.gz/${REPO_REF}" | tar xz -C /src --strip-components=1

FROM python:3.12-slim AS src-local
COPY . /src

FROM src-${SOURCE} AS source

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/home/user/hf TOKENIZERS_PARALLELISM=false TQDM_DISABLE=1

RUN apt-get update && apt-get install -y --no-install-recommends nginx \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 user

WORKDIR /home/user/app
COPY --from=source /src/packages/contracts packages/contracts
COPY --from=source /src/services/triage-worker services/triage-worker
COPY --from=source /src/apps/demo apps/demo
COPY --from=source /src/deploy/hf-space deploy/hf-space

# CPU-only torch keeps the image to roughly 2 GB instead of 5 GB.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install ./packages/contracts ./services/triage-worker "./apps/demo[ui]" \
 && python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2')" \
 && chown -R user:user /home/user

USER user
EXPOSE 7860
CMD ["bash", "deploy/hf-space/start.sh"]
