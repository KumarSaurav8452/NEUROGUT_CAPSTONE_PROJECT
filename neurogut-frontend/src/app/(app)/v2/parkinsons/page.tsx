"use client";
import { Microscope } from "lucide-react";
import pd from "@/data/v2/pd.json";
import Extras, { type ExtrasData } from "@/components/v2/Extras";
import { Header, Metric, Section, Table, Bars, Foot, COBALT, TEAL, SERIES, fmt } from "@/components/v2/ui";

type Row = { model: string; roc_auc: number | null; roc_auc_sd?: number | null; pr_auc?: number | null; f1?: number | null };

export default function ParkinsonsPage() {
  const ablations = Object.entries(pd.ablations as Record<string, Row[]>);
  const models = ["Random Forest", "XGBoost", "CatBoost"];
  const strata = pd.constipation_strata as { stratum: string; model: string; roc_auc: number }[];
  return (
    <>
      <Header title="Parkinson's disease" sub="NEUROGUT PD pipeline (v5–v12): genus/species/pathway features, network and UniFrac-style features, nested CV"
        icon={<Microscope size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <div className="v2-grid">
          <Metric k="Internal AUC (frozen ensemble)" v={fmt(pd.reported.internal_auc)} s="microbiome-only, as reported by the PD team" teal />
          <Metric k="External AUC" v={fmt(pd.reported.external_auc)} s="held-out validation" />
          <Metric k="Elastic Net, external" v={fmt(pd.reported.elasticnet_external_auc)} s="best external single model" teal />
          <Metric k="Samples" v={String(pd.n_samples)} s={`${pd.n_pd} PD / ${pd.n_control} controls`} />
        </div>

        <Section title="Nested cross-validation (v5, genus + pathways + covariates)" sub="5 outer folds, Boruta → Elastic Net selection inside each fold.">
          <Table cols={["Model", "ROC-AUC", "PR-AUC", "F1"]} rows={(pd.nested_cv as Row[]).map((r) => [
            <b key="m">{r.model}</b>, `${fmt(r.roc_auc)} ± ${fmt(r.roc_auc_sd, 2)}`, fmt(r.pr_auc), fmt(r.f1)])} />
        </Section>

        <Section title="Ablations" sub="Mean ROC-AUC over folds. Covariates alone come close to the full model: much of the signal is constipation, not the microbiome.">
          <Bars yRange={[0.5, 0.9]} series={models.map((m, i) => ({
            name: m, x: ablations.map(([k]) => k), y: ablations.map(([, rows]) => rows.find((r) => r.model === m)?.roc_auc ?? null),
            color: [COBALT, TEAL, SERIES[2]][i],
          }))} />
        </Section>

        <Section title="Constipation-stratified models" sub="ROC-AUC within each stratum: does the microbiome signal hold beyond constipation?">
          <Table cols={["Stratum", ...models]} rows={[...new Set(strata.map((s) => s.stratum))].map((st) => [
            <b key="s">{st}</b>, ...models.map((m) => fmt(strata.find((s) => s.stratum === st && s.model === m)?.roc_auc))])} />
        </Section>

        <Extras x={pd.extras as ExtrasData} disease="Parkinson's" />

        <div className="v2-note">
          <b>PD team conclusion.</b> Species-level features gave small, consistent gains and pointed to SCFA-producing bacteria,
          but generalisation was limited, with no conclusive evidence that the microbiome predicts PD beyond the constipation effect.
        </div>
        <Foot source={pd.source} generated={pd.generated} />
      </div>
    </>
  );
}
