from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    groq_api_key: str = ""
    groq_proxy_url: str = "socks5h://mvm:Gdansk2026px@37.28.156.30:17580"
    groq_model: str = "llama-3.3-70b-versatile"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "brt_book"
    database_path: str = "data/brt.db"
    pdf_path: str = "../Энергоинформационная медицина(скан).pdf"
    data_dir: str = "data"
    cors_origins: str = "http://localhost:3003,https://brt.mvm.st"
    jwt_secret: str = "brt-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720  # 30 days

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
