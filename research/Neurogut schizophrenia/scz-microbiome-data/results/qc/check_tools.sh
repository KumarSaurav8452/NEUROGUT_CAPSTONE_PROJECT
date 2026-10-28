set -euo pipefail
export PATH="$HOME/micromamba/envs/scz-qc/bin":"$PATH"
if command -v fastp >/dev/null; then echo fastp=$(fastp --version 2>&1 | head -1); else echo fastp=missing; fi
if command -v bowtie2 >/dev/null; then echo bowtie2=$(bowtie2 --version 2>&1 | head -1 | awk '{print $NF}'); else echo bowtie2=missing; fi
if ls "$HOME/scz-ref/GRCh38_noalt_as".1.bt2 >/dev/null 2>&1 || ls "$HOME/scz-ref/GRCh38_noalt_as".1.bt2l >/dev/null 2>&1; then echo index=ok; else echo index=missing; fi
