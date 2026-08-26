from __future__ import annotations

from pathlib import Path

import yaml

from backend.config import ROOT

_DEFAULT = ROOT / "configs" / "default.yaml"


def load_pipeline_config(path: Path | None = None) -> dict:
    target = path or _DEFAULT
    with target.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
