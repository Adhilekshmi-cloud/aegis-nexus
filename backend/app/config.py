from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aegis Knowledge Ingestion"
    api_prefix: str = "/api"
    dataset_path: str = "./aegis-dataset"
    database_url: str = "sqlite:///./data/aegis_kb.db"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
