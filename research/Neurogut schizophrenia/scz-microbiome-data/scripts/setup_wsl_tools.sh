#!/usr/bin/env bash
# One-time setup of the Phase 3 tools inside WSL (Ubuntu). Run from Windows with:
#   wsl.exe -d Ubuntu -- bash "/mnt/c/Neurogut schizophrenia/scz-microbiome-data/scripts/setup_wsl_tools.sh"
#
# Downloads: micromamba (~15 MB), fastp + bowtie2 from bioconda (~100 MB),
#            GRCh38 no-alt bowtie2 index from the Langmead lab bucket (~3.5 GB zip, ~4 GB unpacked).
# The index lives inside WSL (~/scz-ref) for speed; it grows the WSL virtual disk on C: by ~4 GB permanently.
set -euo pipefail

ENV=scz-qc
REF="$HOME/scz-ref"
INDEX_URL="https://genome-idx.s3.amazonaws.com/bt/GRCh38_noalt_as.zip"
# The 3.7 GB zip is downloaded to the *Windows* side (repo data/cache/ref) and deleted after extraction:
# a temporary file inside the WSL virtual disk would keep occupying C: even after deletion.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP_DIR="$REPO/data/cache/ref"

if ! command -v micromamba >/dev/null && [ ! -x "$HOME/.local/bin/micromamba" ]; then
  echo "== installing micromamba"
  mkdir -p "$HOME/.local/bin"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C "$HOME/.local" bin/micromamba
fi
MM="$(command -v micromamba || echo "$HOME/.local/bin/micromamba")"
export MAMBA_ROOT_PREFIX="$HOME/micromamba"

if [ ! -x "$MAMBA_ROOT_PREFIX/envs/$ENV/bin/bowtie2" ]; then
  echo "== creating env $ENV (versions as in GutMIND Methods)"
  "$MM" create -y -n "$ENV" -c conda-forge -c bioconda fastp=0.23.2 bowtie2=2.5.3 pigz
  "$MM" clean -y --all >/dev/null   # drop the package cache: it would otherwise stay in the WSL disk
fi

if ! ls "$REF/GRCh38_noalt_as.rev.2.bt2" >/dev/null 2>&1; then   # zip extracts flat into $REF
  echo "== downloading GRCh38 bowtie2 index"
  mkdir -p "$REF" "$ZIP_DIR"
  wget -c -nv -O "$ZIP_DIR/GRCh38_noalt_as.zip" "$INDEX_URL"
  echo "== verifying + extracting into $REF"
  # unzip is not installed by default on Ubuntu WSL; python3's zipfile is (and testzip checks every CRC).
  python3 - "$ZIP_DIR/GRCh38_noalt_as.zip" "$REF" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    bad = z.testzip()
    if bad:
        sys.exit(f"corrupt member in zip: {bad}")
    z.extractall(sys.argv[2])
PY
  rm "$ZIP_DIR/GRCh38_noalt_as.zip"
fi

"$MAMBA_ROOT_PREFIX/envs/$ENV/bin/fastp" --version
"$MAMBA_ROOT_PREFIX/envs/$ENV/bin/bowtie2" --version | head -1
ls -lh "$REF"/GRCh38_noalt_as.*
echo "== done. Check from Windows: python -m scz_data check-tools"
