import os
from pathlib import Path

import yaml
from pydantic import BaseModel


class Settings(BaseModel):
    mode: str = "demo"
    data_adapter: str = "fake"
    ai_adapter: str = "fallback"
    ml_enabled: bool = True
    model_path: str = "models/kronos2"
    forecast_context_days: int = 730

    @staticmethod
    def load(path: str | None = None) -> "Settings":
        p = Path(path or os.getenv("FC_CONFIG", "config/demo.yml"))
        if p.exists():
            with open(p) as f:
                data = yaml.safe_load(f) or {}
            return Settings(**data)
        return Settings()
