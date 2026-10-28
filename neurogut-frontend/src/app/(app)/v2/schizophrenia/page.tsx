"use client";
import { Brain } from "lucide-react";
import scz from "@/data/v2/scz.json";
import { Header, Metric, Section, Table, Bars, Foot, COBALT, TEAL, fmt, studyLabel } from "@/components/v2/ui";

type Row = { model: string; roc_auc: number | null; roc_auc_sd: number | null; pr_auc: number | null; bal_acc: number | null; f1: number | null };
const modelRows = (rows: Row[]) => rows.map((r) => [
  <b key="m" style={{ color: r.model.startsWith("Ensemble") ? COBALT : undefined }}>{r.model}</b>,
  `${fmt(r.roc_auc)} ± ${fmt(r.roc_auc_sd, 2)}`, fmt(r.pr_auc), fmt(r.bal_acc), fmt(r.f1),
]);

export default function SchizophreniaPage() {
  const ensI = scz.internal.find((r) => r.model === scz.ensemble)!;
  const ensE = scz.external.find((r) => r.model === scz.ensemble)!;
  const byStudy = scz.external_by_study as Record<string, number | string | null>[];
  const worst = Math.min(...byStudy.map((s) => s[scz.ensemble] as number));
  const top = scz.top_features;
  return (
    <>
      <Header title="Schizophrenia" sub={`Final model: ${scz.final_experiment} (ensemble of Random Forest, XGBoost, CatBoost)`}
        icon={<Brain size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <div className="v2-grid">
          <Metric k="Internal ROC-AUC" v={fmt(ensI.roc_auc)} s={`5-fold nested CV, ± ${fmt(ensI.roc_auc_sd, 2)}`} />
          <Metric k="New-cohort ROC-AUC" v={fmt(ensE.roc_auc)} s="leave-one-study-out mean" teal />
          <Metric k="Worst held-out study" v={fmt(worst)} s="was ≈ 0.50 before harmonisation" />
          <Metric k="Training samples" v={String(scz.n_samples)} s="4 case-control cohorts" teal />
        </div>

        <Section title="Cohorts" sub="Included samples after the GutMIND filters. Xu 2020 has no controls, so it is kept out of training.">
          <Table cols={["Study", "Country", "Platform", "Healthy", "SCZ", "Role"]}
            rows={scz.cohort.map((c) => [<b key="s">{studyLabel(c.study_id)}</b>, c.country, c.platform, c.healthy, c.scz,
              c.healthy > 0 ? <span key="r" className="v2-pill cobalt">train + test</span> : <span key="r" className="v2-pill teal">case-only check</span>])} />
        </Section>

        <div className="v2-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))" }}>
          <Section title="Internal benchmarks" sub="Every cohort seen in training (optimistic).">
            <Table cols={["Model", "ROC-AUC", "PR-AUC", "Bal. acc.", "F1"]} rows={modelRows(scz.internal)} />
          </Section>
          <Section title="New-cohort benchmarks" sub="Train on 3 cohorts, test on the 4th; mean over the 4 (honest estimate).">
            <Table cols={["Model", "ROC-AUC", "PR-AUC", "Bal. acc.", "F1"]} rows={modelRows(scz.external)} />
          </Section>
        </div>

        <Section title="ROC-AUC per held-out cohort" sub="Dotted line = chance (0.5).">
          <Bars yRange={[0.3, 0.85]} refLine={0.5} series={[
            { name: "Ensemble", x: byStudy.map((s) => `${studyLabel(String(s.study))} (n=${s.n})`), y: byStudy.map((s) => s[scz.ensemble] as number), color: COBALT },
            { name: "Elastic Net", x: byStudy.map((s) => `${studyLabel(String(s.study))} (n=${s.n})`), y: byStudy.map((s) => s["ElasticNet"] as number), color: TEAL },
          ]} />
        </Section>

        <Section title="Preprocessing experiments" sub="Ensemble ROC-AUC. E4–E8 put all cohorts on one level (common detection floor, shared taxa, per-study scaling, balanced weights); E6 adds species+genus+family and cross-cohort consistent features.">
          <Bars yRange={[0.4, 0.8]} refLine={0.5} series={[
            { name: "Internal", x: scz.experiments.map((e) => e.experiment.split(" ")[0]), y: scz.experiments.map((e) => e.internal), color: COBALT },
            { name: "New cohort (mean)", x: scz.experiments.map((e) => e.experiment.split(" ")[0]), y: scz.experiments.map((e) => e.external), color: TEAL },
            { name: "New cohort (worst)", x: scz.experiments.map((e) => e.experiment.split(" ")[0]), y: scz.experiments.map((e) => e.external_worst), color: "#94A3B8" },
          ]} />
          <Table cols={["Code", "Experiment"]} rows={scz.experiments.map((e) => [e.experiment.split(" ")[0], e.experiment.split(" ").slice(1).join(" ")])} />
        </Section>

        <Section title="Top microbial signals (frozen model)" sub="Random Forest importance; cobalt = higher in schizophrenia, teal = higher in healthy controls.">
          <Bars horizontal height={560} yTitle="importance" series={[{
            name: "importance", x: top.map((t) => t.feature.replace(/^[a-z]__/, "").replace(/_/g, " ")),
            y: top.map((t) => t.importance), color: top.map((t) => (t.higher_in === "SCZ" ? COBALT : TEAL)),
          }]} />
        </Section>

        <Section title="Checks">
          <ul style={{ fontSize: 13, margin: 0, paddingLeft: 18, lineHeight: 1.8 }}>
            <li>Cohort identity is easy to predict from the microbiome (AUC {fmt(scz.checks.batch_auc)}; {fmt(scz.checks.batch_auc_harmonised)} after per-study scaling), so balanced weights and cross-cohort feature selection are used.</li>
            <li>Age + sex + BMI alone reach AUC {fmt(scz.checks.covariate_auc)} in the Zhu cohorts; they are missing for Li and Thirion, so the model is microbiome-only.</li>
            <li>The 0.5 threshold under-calls schizophrenia (minority class): F1 and balanced accuracy can improve with a tuned threshold.</li>
          </ul>
        </Section>
        <Foot source={scz.source} generated={scz.generated} />
      </div>
    </>
  );
}
