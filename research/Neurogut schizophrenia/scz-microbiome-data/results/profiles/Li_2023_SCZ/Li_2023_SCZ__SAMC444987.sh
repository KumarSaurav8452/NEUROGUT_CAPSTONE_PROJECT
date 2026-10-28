set -euo pipefail
export PATH="$HOME/micromamba/envs/scz-qc/bin":"$PATH"
alias_dir=$(mktemp -d)
trap 'rm -rf "$alias_dir"' EXIT
ln -s '/mnt/c/Neurogut schizophrenia/scz-microbiome-data/data/subsample/Li_2023_SCZ__SAMC444987' "$alias_dir/w"
rm -f "$alias_dir/w/Li_2023_SCZ__SAMC444987.bt2.bz2" "$alias_dir/w/Li_2023_SCZ__SAMC444987.profile.txt"
fastp --stdout -w 8 --length_required 50 --detect_adapter_for_pe -j "$alias_dir/w/Li_2023_SCZ__SAMC444987.fastp.json" -h "$alias_dir/w/Li_2023_SCZ__SAMC444987.fastp.html" -i '/mnt/c/Neurogut schizophrenia/scz-microbiome-data/data/subsample/Li_2023_SCZ__SAMC444987/Li_2023_SCZ__SAMC444987.sub.R1.fq.gz' -I '/mnt/c/Neurogut schizophrenia/scz-microbiome-data/data/subsample/Li_2023_SCZ__SAMC444987/Li_2023_SCZ__SAMC444987.sub.R2.fq.gz' 2> "$alias_dir/w/Li_2023_SCZ__SAMC444987.fastp.log" \
  | bowtie2 -p 8 --sensitive -x "$HOME/scz-ref/GRCh38_noalt_as" --interleaved - --un-conc-gz "$alias_dir/w/Li_2023_SCZ__SAMC444987.hr.R%.fq.gz" -S /dev/null 2> "$alias_dir/w/Li_2023_SCZ__SAMC444987.bowtie2.log"
PATH="$HOME/micromamba/envs/scz-mpa3/bin":"$PATH" metaphlan "$alias_dir/w/Li_2023_SCZ__SAMC444987.hr.R1.fq.gz,$alias_dir/w/Li_2023_SCZ__SAMC444987.hr.R2.fq.gz" --input_type fastq --bowtie2db "$HOME/scz-ref/mpa3" --index mpa_v30_CHOCOPhlAn_201901 --nproc 8 --unknown_estimation --bowtie2out "$alias_dir/w/Li_2023_SCZ__SAMC444987.bt2.bz2" -o "$alias_dir/w/Li_2023_SCZ__SAMC444987.profile.txt" 2> "$alias_dir/w/Li_2023_SCZ__SAMC444987.metaphlan.log"
