from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 30
    database_url: str = "sqlite:///./sevacrm.db"
    upload_dir: str = "uploads"
    yahoo_finance_api: str = "https://query1.finance.yahoo.com/v8/finance/chart"

    class Config:
        env_file = ".env"


settings = Settings()
