from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ldap_people_table: str = "ldap_people"
    ldap_people_id_column: str = "userid"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    servicenow_instance_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""

    # Override with DATABASE_URL in .env (recommended if you avoid credentials in code).
    database_url: str = (
        "postgresql+psycopg2://postgres:password@localhost:5432/ai_poc"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
