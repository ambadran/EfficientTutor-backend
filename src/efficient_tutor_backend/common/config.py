'''
Holds all the configurations
'''
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Manages application configuration using environment variables.
    """
    # Application Metadata
    APP_NAME: str = "EfficientTutor Backend"
    APP_VERSION: str = "0.3.0"
    APP_DESCRIPTION: str = "The backend API for the EfficientTutor platform."
    TEST_MODE: bool = False

    # Database URL
    DATABASE_URL_PROD: str
    DATABASE_URL_TEST: str
    DATABASE_URL_PROD_CLI: str
    DATABASE_URL_TEST_CLI: str
    @property
    def database_url(self) -> str:
        """
        Dynamically returns the correct database URL based on the test_mode flag.
        """
        if self.TEST_MODE:
            return self.DATABASE_URL_TEST
        return self.DATABASE_URL_PROD

    # JWT Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Other settings
    FIRST_DAY_OF_WEEK: int = 5  # 5 is Saturday

    class Config:
        env_file = ".env" # automatically loads the .env

# Create a single, importable instance of the settings
settings = Settings()
