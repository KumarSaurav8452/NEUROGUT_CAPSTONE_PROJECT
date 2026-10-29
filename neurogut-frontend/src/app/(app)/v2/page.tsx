"use client";
import Link from "next/link";
import { Sparkles, Brain, Microscope, ArrowRight } from "lucide-react";
import scz from "@/data/v2/scz.json";
import pd from "@/data/v2/pd.json";
import { Header, Section, Bars, COBALT, TEAL, fmt } from "@/components/v2/ui";

const ens = (rows: { model: string; roc_auc: number | null }[]) => rows.find((r) => r.model.startsWith("Ensemble"))?.roc_auc ?? null;
const best = (rows: { roc_auc: number }[]) => Math.max(...rows.map((r) => r.roc_auc));

// One stat card holding the schizophrenia value (cobalt) next to the Parkinson's value (teal)
function Pair({ k, scz, pd }: { k: string; scz: [string, string]; pd: [string, string] }) {
  const half = (label: string, [v, s]: [string, string], teal?: boolean) => (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: teal ? TEAL : COBALT }}>{label}</div>
      <div className={`v ${teal ? "teal" : ""}`}>{v}</div>
      <div className="s">{s}</div>
    </div>
  );
  return (
    <div className="card v2-metric">
      <div className="k">{k}</div>
      <div style={{ display: "flex", gap: 16 }}>{half("SCHIZOPHRENIA", scz)}{half("PARKINSON'S", pd, true)}</div>
    </div>
  );
}

export default function V2Overview() {
  const sczInt = ens(scz.internal), sczExt = ens(scz.external);
  const nStudies = scz.cohort.filter((c) => c.healthy > 0).length;
  return (
    <>
      <Header title="NeuroGut v2" sub="Gut-microbiome classifiers for Parkinson's disease and schizophrenia"
        icon={<Sparkles size={22} style={{ verticalAlign: "middle", marginRight: 8 }} />} />
      <div className="page-body">
        <div className="v2-hero">
          <h2>Can the gut microbiome tell patients from healthy controls?</h2>
          <p>Two disease arms, one method: MetaPhlAn profiles → harmonised features → Random Forest, XGBoost and CatBoost
            ensembles, scored on held-out folds and on cohorts the model never saw.</p>
        </div>

        <div className="v2-grid">
          <Link href="/v2/schizophrenia" className="card v2-section" style={{ textDecoration: "none", color: "inherit" }}>
            <span className="v2-pill cobalt"><Brain size={11} style={{ verticalAlign: "-1px" }} /> Schizophrenia</span>
            <div style={{ display: "flex", gap: 24, marginTop: 12 }}>
              <div><div className="k" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>INTERNAL AUC</div>
                <div style={{ fontSize: 30, fontWeight: 800, color: COBALT }}>{fmt(sczInt, 2)}</div></div>
              <div><div className="k" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>NEW-COHORT AUC</div>
                <div style={{ fontSize: 30, fontWeight: 800, color: COBALT }}>{fmt(sczExt, 2)}</div></div>
            </div>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "8px 0 0" }}>
              {scz.n_samples} samples · {nStudies} public cohorts (China, Denmark) · shotgun metagenomes
              <ArrowRight size={13} style={{ verticalAlign: "-2px", marginLeft: 6 }} />
            </p>
          </Link>
          <Link href="/v2/parkinsons" className="card v2-section" style={{ textDecoration: "none", color: "inherit" }}>
            <span className="v2-pill teal"><Microscope size={11} style={{ verticalAlign: "-1px" }} /> Parkinson&apos;s disease</span>
            <div style={{ display: "flex", gap: 24, marginTop: 12 }}>
              <div><div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>INTERNAL AUC</div>
                <div style={{ fontSize: 30, fontWeight: 800, color: TEAL }}>{fmt(pd.reported.internal_auc, 2)}</div></div>
              <div><div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>EXTERNAL AUC</div>
                <div style={{ fontSize: 30, fontWeight: 800, color: TEAL }}>{fmt(pd.reported.external_auc, 2)}</div></div>
            </div>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "8px 0 0" }}>
              {pd.n_samples} samples ({pd.n_pd} PD / {pd.n_control} controls) · frozen microbiome-only ensemble
              <ArrowRight size={13} style={{ verticalAlign: "-2px", marginLeft: 6 }} />
            </p>
          </Link>
        </div>

        <Section title="Side by side" sub="Internal = cross-validation with every cohort seen in training. External = a cohort held out entirely.">
          <Bars yRange={[0.4, 0.8]} refLine={0.5} series={[
            { name: "Schizophrenia", x: ["Internal", "External / new cohort"], y: [sczInt, sczExt], color: COBALT },
            { name: "Parkinson's", x: ["Internal", "External / new cohort"], y: [pd.reported.internal_auc, pd.reported.external_auc], color: TEAL },
          ]} />
        </Section>

        <div className="v2-grid">
          <Pair k="Confound check"
            scz={[fmt(scz.checks.batch_auc, 2), "cohorts told apart: strong batch effect"]}
            pd={[fmt(best(pd.ablations["Constipation dropped"]), 2), "AUC with constipation removed"]} />
          <Pair k="Demographics only"
            scz={[fmt(scz.checks.covariate_auc, 2), "age + sex + BMI (Zhu cohorts)"]}
            pd={[fmt(best(pd.ablations["Covariates only"]), 2), "age, sex, BMI, constipation, laxatives"]} />
          <Pair k="Models compared"
            scz={["8 × 5", "preprocessing experiments × models"]}
            pd={[`${Object.keys(pd.ablations).length} × ${pd.nested_cv.length}`, "ablations × models"]} />
        </div>

        <div className="v2-note">
          <b>What this means.</b> Both diseases show a real but modest microbiome signal (about 0.6 AUC on unseen cohorts).
          Gains seen inside one dataset shrink across countries and sequencers, so these models are research tools, not diagnostics.
        </div>
      </div>
    </>
  );
}
