from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'senai_crm.db'}"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    stream_rate: float = 1.0  # emails per second
    stream_dataset: str = str(PROJECT_ROOT / "data" / "email-data-advanced.json")
    knowledge_dir: str = str(PROJECT_ROOT / "knowledge")
    confidence_human_threshold: float = 0.70
    max_body_chars: int = 10000
    vector_dims: int = 384

    class Config:
        env_file = ".env"


settings = Settings()
