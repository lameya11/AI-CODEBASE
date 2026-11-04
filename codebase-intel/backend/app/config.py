"""Application configuration using pydantic-settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./codebase_intel.db"
    LLM_PROVIDER: str = "none"  # openai | anthropic | none
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    MAX_FILES: int = 2000
    MAX_FILE_BYTES: int = 1_048_576  # 1 MB
    MAX_ZIP_BYTES: int = 209_715_200  # 200 MB
    TOP_K: int = 8
    IMPACT_MAX_DEPTH: int = 4
    COMPLEXITY_THRESHOLD: int = 10
    TOKEN_BUDGET: int = 6000
    DATA_DIR: str = "./data"

    def get_data_dir(self) -> Path:
        p = Path(self.DATA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_index_dir(self, repo_id: str) -> Path:
        p = self.get_data_dir() / "indexes" / repo_id
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
