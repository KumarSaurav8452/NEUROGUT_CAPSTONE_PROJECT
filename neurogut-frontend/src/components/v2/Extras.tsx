"use client";
// SVM baseline and SHAP explanations of the deployed model (research/.../scz-ml, python -m sczml.extras).
import { Section, Table, Bars, COBALT, TEAL, fmt } from "@/components/v2/ui";

type Scores = { roc_auc: number; roc_auc_sd: number; roc_auc_ci95?: [number, number]; accuracy: number; precision: number; recall: number; f1: number };
export type ExtrasData = {
  internal: Record<string, Scores>;
  external: Record<string, Scores> | null;
  shap: { taxon: string; mean_abs_shap: number; raises_score_when: "higher" | "lower" }[];
} | null;

const pretty = (t: string) => t.replace(/^[a-z]__/, "").replace(/_/g, " ");

export default function Extras({ x, disease }: { x: ExtrasData; disease: string }) {
  if (!x) return null;
  const rows = (["internal", "external"] as const).flatMap((split) =>
    Object.entries(x[split] ?? {}).map(([model, s]) => [
      split === "internal" ? "5-fold CV" : "Unseen cohort (LOSO)", <b key="m">{model}</b>,
      `${fmt(s.roc_auc)} ± ${fmt(s.roc_auc_sd, 2)}`, s.roc_auc_ci95 ? `${fmt(s.roc_auc_ci95[0], 2)}–${fmt(s.roc_auc_ci95[1], 2)}` : "–", fmt(s.accuracy), fmt(s.precision), fmt(s.recall), fmt(s.f1)]));
  const top = x.shap.slice(0, 12).reverse();
  return (
    <>
      <Section title="SVM compared with the deployed model" sub="Same 30-taxon features, same folds (seed 42). 95% CI: bootstrap of the mean fold AUC (1,000 resamples). Accuracy, precision, recall and F1 at the Youden threshold.">
        <Table cols={["Validation", "Model", "ROC-AUC", "95% CI", "Accuracy", "Precision", "Recall", "F1"]} rows={rows} />
      </Section>
      <Section title="SHAP: what drives the deployed model" sub={`Mean |SHAP| of the deployed XGBoost model. Cobalt: a higher amount raises the ${disease} score; teal: a lower amount does.`}>
        <Bars horizontal height={380} yTitle="mean |SHAP| (log-odds)" series={[{
          name: "SHAP", x: top.map((t) => pretty(t.taxon)), y: top.map((t) => t.mean_abs_shap),
          color: top.map((t) => (t.raises_score_when === "higher" ? COBALT : TEAL)),
        }]} />
      </Section>
    </>
  );
}
