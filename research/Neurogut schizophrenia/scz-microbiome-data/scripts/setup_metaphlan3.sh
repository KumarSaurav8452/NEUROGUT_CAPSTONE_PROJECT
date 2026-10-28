#!/usr/bin/env bash
# One-time setup of MetaPhlAn 3 inside WSL, with the same database curatedMetagenomicData used (mpa_v30),
# so our profiles are directly comparable with cMD's Zhu_2020A profiles.
#   wsl.exe -d Ubuntu -- bash "/mnt/c/Neurogut schizophrenia/scz-microbiome-data/scripts/setup_metaphlan3.sh"
# Downloads ~0.4 GB (database tar) + ~150 MB (packages); builds the bowtie2 marker index locally
# (no prebuilt index is published for mpa_v30). Ends at ~1.5 GB inside WSL (~/scz-ref/mpa3).
#
# Why not MetaPhlAn 4 (GutMIND's choice): its prebuilt index is 21 GB and building it needs far more RAM
# than this machine's WSL (7 GB) - see docs/phase3b.md.
set -euo pipefail

ENV=scz-mpa3
DB="$HOME/scz-ref/mpa3"
INDEX=mpa_v30_CHOCOPhlAn_201901
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
MM="$(command -v micromamba || echo "$HOME/.local/bin/micromamba")"

if [ ! -x "$MAMBA_ROOT_PREFIX/envs/$ENV/bin/metaphlan" ]; then
  echo "== creating env $ENV"
  "$MM" create -y -n "$ENV" -c conda-forge -c bioconda metaphlan=3.0.14 bowtie2=2.5.3
  "$MM" clean -y --all >/dev/null
fi
export PATH="$MAMBA_ROOT_PREFIX/envs/$ENV/bin:$PATH"

if ! ls "$DB/$INDEX.rev.2.bt2" >/dev/null 2>&1; then
  echo "== downloading $INDEX and building its bowtie2 index (this is the slow part)"
  mkdir -p "$DB"
  metaphlan --install --index "$INDEX" --bowtie2db "$DB" --nproc "$(nproc)"
  rm -f "$DB/$INDEX.tar" "$DB/$INDEX.fna.bz2" "$DB/$INDEX.fna"   # keep only the index + pkl
fi
metaphlan --version
ls -lh "$DB"
echo "== done"
