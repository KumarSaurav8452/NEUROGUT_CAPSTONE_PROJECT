"use client";
import { BookOpen } from "lucide-react";
import { Header, Section } from "@/components/v2/ui";

const STEPS: [string, string][] = [
  ["Data retrieval", "Six schizophrenia cohorts from GutMIND Table S1; five public (ENA, NCBI SRA, CNGB, GSA), Vasileva 2024 awaiting access. Labels only from archive metadata or paper supplements."],
  ["Filtering", "Shotgun only, one platform per study, baseline samples, BMI ≤ 30 where published, ≥ 10 M host-removed reads. Every excluded sample keeps one reason."],
  ["QC and profiling", "fastp → bowtie2 host removal (GRCh38) → MetaPhlAn 3.0.14 (mpa_v30) on 300–500 k-read subsamples; Zhu A from curatedMetagenomicData at full depth."],
  ["Harmonisation", "Common 0.01 % detection floor, taxa shared by ≥ half of the training cohorts, every feature centred and scaled within its cohort (label-free), study × group balanced sample weights."],
  ["Features", "Species + genus + family, CLR per rank; optional diversity, Bray-Curtis/UniFrac-style distance to training controls and co-occurrence network loads (all fit inside each fold)."],
  ["Feature selection", "Cross-cohort consistency: per-cohort standardised effect, Stouffer-combined, direction must agree in every training cohort; top 40 kept."],
  ["Models", "Random Forest, XGBoost, CatBoost (inner grid search), Elastic-Net logistic regression; mean-probability ensemble."],
  ["Validation", "5-fold nested CV stratified by cohort × group (internal) and leave-one-study-out (new cohort). Seeds fixed; nothing tuned on test folds."],
];

const LIMITS = [
  "Subsampled profiles miss rare species; only Zhu A is full depth.",
  "MetaPhlAn 3 instead of MetaPhlAn 4; no pathway (HUMAnN) features for schizophrenia.",
  "Clinical covariates missing for half the schizophrenia cohort, so models are microbiome-only.",
  "Picking the best of 8 experiments by new-cohort AUC is mildly optimistic.",
];

export default function MethodsPage() {
  return (
    <>
      <Header title="Methods" sub="How the v2 numbers were produced, end to end"
        icon={<BookOpen size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <Section title="Schizophrenia pipeline">
          <ol className="v2-steps">{STEPS.map(([t, d]) => <li key={t}><b>{t}.</b> {d}</li>)}</ol>
        </Section>
        <Section title="Limitations">
          <ul style={{ fontSize: 13, margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
        </Section>
        <Section title="Reproduce" sub="All code and specifications live in research/ in this repository.">
          <ul style={{ fontSize: 13, margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            <li><code>research/Neurogut schizophrenia/PRD_SCZ_Data_Retrieval.md</code>: data retrieval spec</li>
            <li><code>research/Neurogut schizophrenia/PRD_SCZ_ML_Training.md</code>: training spec</li>
            <li><code>research/Neurogut schizophrenia/scz-ml/run_all.bat</code>: retrains everything</li>
            <li><code>python scripts/export_v2_data.py</code>: refreshes this website&apos;s numbers</li>
          </ul>
        </Section>
      </div>
    </>
  );
}
