"""
NEUROGUT v2.0 -- Cohort Benchmark Job
========================================
Computes per-taxa percentile distributions grouped by risk_tier.
Runs on startup and can be triggered periodically.
"""

import uuid
import numpy as np
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import (
    MicrobiomeSample, Prediction, CohortBenchmark,
)

TAXA_COLUMNS = [
    "lachnospira", "ruthenibacterium", "veillonella", "gardnerella",
    "pseudobutyrivibrio", "kocuria", "trueperella", "lancefieldella",
    "fructilactobacillus", "lachnoanaerobaculum", "corynebacterium",
    "raoultella", "lawsonella",
]

RISK_TIERS = ["healthy", "depression_only", "anxiety_only", "comorbid"]


def compute_cohort_benchmarks(db: Session | None = None):
    """Compute cohort benchmark stats for all 13 taxa × 4 risk tiers.

    For each (taxon, risk_tier), calculates mean, std, p25, p50, p75
    from all samples whose prediction has that risk tier.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Query all samples with their predictions
        results = (
            db.query(MicrobiomeSample, Prediction)
            .join(Prediction, Prediction.sample_id == MicrobiomeSample.id)
            .all()
        )

        if not results:
            print("[Benchmark] No samples found, skipping.")
            return

        # Group sample values by risk_tier
        tier_data: dict[str, list[dict]] = {t: [] for t in RISK_TIERS}
        for sample, pred in results:
            if pred.risk_tier in tier_data:
                row = {col: getattr(sample, col) for col in TAXA_COLUMNS}
                tier_data[pred.risk_tier].append(row)

        now = datetime.now(timezone.utc)
        count = 0

        for tier in RISK_TIERS:
            rows = tier_data[tier]
            if not rows:
                continue

            for taxon in TAXA_COLUMNS:
                values = np.array([r[taxon] for r in rows])

                # Upsert benchmark
                existing = db.query(CohortBenchmark).filter(
                    CohortBenchmark.taxon_name == taxon,
                    CohortBenchmark.risk_tier == tier,
                ).first()

                stats = {
                    "sample_count": len(values),
                    "mean_value": float(np.mean(values)),
                    "std_value": float(np.std(values)),
                    "p25_value": float(np.percentile(values, 25)),
                    "p50_value": float(np.percentile(values, 50)),
                    "p75_value": float(np.percentile(values, 75)),
                    "computed_at": now,
                }

                if existing:
                    for k, v in stats.items():
                        setattr(existing, k, v)
                else:
                    bm = CohortBenchmark(
                        id=str(uuid.uuid4()),
                        taxon_name=taxon,
                        risk_tier=tier,
                        **stats,
                    )
                    db.add(bm)
                count += 1

        db.commit()
        print(f"[Benchmark] Computed {count} benchmarks across {len(results)} samples.")

    finally:
        if close_db:
            db.close()
