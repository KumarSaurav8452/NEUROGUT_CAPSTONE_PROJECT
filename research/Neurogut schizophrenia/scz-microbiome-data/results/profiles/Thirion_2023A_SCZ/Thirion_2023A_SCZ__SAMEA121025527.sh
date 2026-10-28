set -euo pipefail
export PATH="$HOME/micromamba/envs/scz-qc/bin":"$PATH"
alias_dir=$(mktemp -d)
trap 'rm -rf "$alias_dir"' EXIT
ln -s '/mnt/c/Neurogut schizophrenia/scz-microbiome-data/data/subsample/Thirion_2023A_SCZ__SAMEA121025527' "$alias_dir/w"
rm -f "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.bt2.bz2" "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.profile.txt"
fastp --stdout -w 8 --length_required 50 --disable_trim_poly_g -j "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.fastp.json" -h "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.fastp.html" -i '/mnt/c/Neurogut schizophrenia/scz-microbiome-data/data/subsample/Thirion_2023A_SCZ__SAMEA121025527/Thirion_2023A_SCZ__SAMEA121025527.sub.SE.fq.gz' 2> "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.fastp.log" \
  | bowtie2 -p 8 --sensitive -x "$HOME/scz-ref/GRCh38_noalt_as" -U - --un-gz "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.hr.fq.gz" -S /dev/null 2> "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.bowtie2.log"
PATH="$HOME/micromamba/envs/scz-mpa3/bin":"$PATH" metaphlan "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.hr.fq.gz" --input_type fastq --bowtie2db "$HOME/scz-ref/mpa3" --index mpa_v30_CHOCOPhlAn_201901 --nproc 8 --unknown_estimation --bowtie2out "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.bt2.bz2" -o "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.profile.txt" 2> "$alias_dir/w/Thirion_2023A_SCZ__SAMEA121025527.metaphlan.log"
