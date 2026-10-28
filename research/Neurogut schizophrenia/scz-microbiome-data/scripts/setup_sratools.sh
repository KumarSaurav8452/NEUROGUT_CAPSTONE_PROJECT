#!/usr/bin/env bash
# sra-tools for reading the first N reads of an SRA run straight from NCBI's AWS copy (Thirion: ENA slowed to
# ~35 KB/s on 27 Oct 2026, while sra-pub-run-odp.s3.amazonaws.com gave 2 MB/s). Downloads ~100 MB from bioconda.
set -euo pipefail
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
MM="$(command -v micromamba || echo "$HOME/.local/bin/micromamba")"
ENV=scz-sra
if [ ! -x "$MAMBA_ROOT_PREFIX/envs/$ENV/bin/fastq-dump" ]; then
  "$MM" create -y -n "$ENV" -c conda-forge -c bioconda "sra-tools>=3.1"
fi
"$MAMBA_ROOT_PREFIX/envs/$ENV/bin/fastq-dump" --version
