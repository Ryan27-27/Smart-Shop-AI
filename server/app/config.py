from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name: str = "ShopSmart AI"
    secret_key: str = "change-this-secret-before-deploying"
    database_url: str = "sqlite:///./shopsmart.db"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    llm_provider: str = "groq"
    chroma_path: str = "./data/chroma"
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
