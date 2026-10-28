"""Config loading and per-stage logging."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Settings:
    root: Path
    cfg: dict[str, Any]

    def path(self, key: str) -> Path:
        return self.root / self.cfg["paths"][key]

    def resolve(self, rel: str | Path) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.root / p


def load_settings(root: str | Path = ".", config: str = "config/config.yaml") -> Settings:
    root = Path(root).resolve()
    with open(root / config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return Settings(root=root, cfg=cfg)


def load_studies(settings: Settings) -> list[dict[str, Any]]:
    path = settings.path("studies")
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run the 'config' stage first")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["studies"]


def get_logger(settings: Settings, stage: str, study_id: str) -> logging.Logger:
    """Logger writing to logs/<stage>/<StudyID>.log and to the console (PRD §6.2)."""
    name = f"scz_data.{stage}.{study_id}"
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    log_dir = settings.path("logs") / stage
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    fh = logging.FileHandler(log_dir / f"{study_id}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(f"[{stage}:{study_id}] %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
