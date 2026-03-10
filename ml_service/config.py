"""
Configuration – loads environment variables for the ML service.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_URL: str = os.getenv("DB_URL", "")
if not DB_URL:
    raise ValueError("DB_URL not found in environment variables")

MODEL_STORAGE_PATH: Path = Path(os.getenv("MODEL_STORAGE_PATH", str(Path(__file__).parent / "models")))
MODEL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

ML_SERVICE_PORT: int = int(os.getenv("ML_SERVICE_PORT", "8100"))

# Minimum days of data required to train a model
MIN_TRAINING_DAYS: int = 30
