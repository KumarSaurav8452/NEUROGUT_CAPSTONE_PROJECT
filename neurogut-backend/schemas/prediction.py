"""
NEUROGUT -- Prediction Schemas (Pydantic)
==========================================
"""

from typing import Optional
from pydantic import BaseModel, Field


class PredictionInput(BaseModel):
    """13 bacterial taxa -- the PRD specifies [0,1] but the actual training data
    uses CLR-transformed values which can be negative. We accept any float."""
    lachnospira: float = Field(..., description="Lachnospira abundance")
    ruthenibacterium: float = Field(..., description="Ruthenibacterium abundance")
    veillonella: float = Field(..., description="Veillonella abundance")
    gardnerella: float = Field(..., description="Gardnerella abundance")
    pseudobutyrivibrio: float = Field(..., description="Pseudobutyrivibrio abundance")
    kocuria: float = Field(..., description="Kocuria abundance")
    trueperella: float = Field(..., description="Trueperella abundance")
    lancefieldella: float = Field(..., description="Lancefieldella abundance")
    fructilactobacillus: float = Field(..., description="Fructilactobacillus abundance")
    lachnoanaerobaculum: float = Field(..., description="Lachnoanaerobaculum abundance")
    corynebacterium: float = Field(..., description="Corynebacterium abundance")
    raoultella: float = Field(..., description="Raoultella abundance")
    lawsonella: float = Field(..., description="Lawsonella abundance")

    def to_feature_list(self) -> list[float]:
        """Return features in canonical order matching FEATURE_NAMES."""
        return [
            self.lachnospira, self.ruthenibacterium, self.veillonella,
            self.gardnerella, self.pseudobutyrivibrio, self.kocuria,
            self.trueperella, self.lancefieldella, self.fructilactobacillus,
            self.lachnoanaerobaculum, self.corynebacterium, self.raoultella,
            self.lawsonella,
        ]


class PredictionOutput(BaseModel):
    prediction_id: str
    sample_id: str
    depression_prob: float
    anxiety_prob: float
    depression_label: int
    anxiety_label: int
    risk_tier: str
    rf_importances: dict[str, float]
    xgb_importances: dict[str, float]
    consensus_features: list[str]
    processing_time_ms: int
    model_version: str
    # v2.0: Confidence intervals
    depression_ci_low: float | None = None
    depression_ci_high: float | None = None
    anxiety_ci_low: float | None = None
    anxiety_ci_high: float | None = None
    bootstrap_iterations: int | None = None


class BatchPredictionInput(BaseModel):
    """For batch CSV upload -- list of samples."""
    samples: list[PredictionInput]


class ModelHealthResponse(BaseModel):
    model_version: str
    model_loaded: bool
    feature_count: int
    prediction_count: int = 0
    avg_latency_ms: float = 0.0
