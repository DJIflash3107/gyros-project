from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/gyros_db?charset=utf8mb4"
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-32-characters-minimum-for-hs256!"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    APP_NAME: str = "GyrosProject"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # AMD Token Factory Configuration
    AMD_API_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    AMD_API_KEY: str = ""
    AMD_DEFAULT_MODEL: str = "DeepSeek-V4-Flash"
    AMD_REQUEST_TIMEOUT: int = 600
    AMD_STREAM_CHUNK_TIMEOUT: int = 600
    AMD_MAX_RETRIES: int = 3

    # Agent Configuration
    AGENT_MAX_TURNS: int = 10
    AGENT_REQUEST_TIMEOUT: int = 120
    AGENT_MAX_TOKENS: int = 4096
    AGENT_TEMPERATURE: float = 0.3

    # Vision Configuration
    VISION_MODEL_OVERRIDE: str = ""
    VISION_MAX_IMAGE_SIZE_MB: int = 5
    VISION_EXTRACTION_TEMPERATURE: float = 0.1

    # Semantic Mapping Configuration
    SEMANTIC_MAPPING_ENABLED: bool = True
    SEMANTIC_MAPPING_MODEL: str = ""
    SEMANTIC_MAPPING_TEMPERATURE: float = 0.0
    SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
