from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Configuration class to manage environment variables using Pydantic.
    """
    DATABASE_URL: str
    FRESHSERVICE_DOMAIN: str
    FRESHSERVICE_API_KEY: str
    DATTO_API_ENDPOINT: str
    DATTO_API_KEY: str
    DATTO_API_SECRET: str

    class Config:
        env_file = ".env"

settings = Settings()
