set -euo pipefail
export PATH="$HOME/micromamba/envs/scz-qc/bin":"$PATH"
PATH="$HOME/micromamba/envs/scz-mpa3/bin":"$PATH"
ls "$HOME/scz-ref/mpa3"/mpa_v30_CHOCOPhlAn_201901.rev.2.bt2 "$HOME/scz-ref/mpa3"/mpa_v30_CHOCOPhlAn_201901.pkl >/dev/null 2>&1 && echo index=ok || echo index=missing
metaphlan --version 2>&1 | tail -1
