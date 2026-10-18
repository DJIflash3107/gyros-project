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
    AMD_RPM_LIMIT: int = 18
    AMD_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AMD_MAX_CONCURRENT_REQUESTS: int = 4

    # Agent Configuration
    AGENT_MAX_TURNS: int = 10
    AGENT_REQUEST_TIMEOUT: int = 120
    AGENT_MAX_TOKENS: int = 4096
    AGENT_TEMPERATURE: float = 0.3

    # Vision Configuration
    VISION_MODEL_OVERRIDE: str = ""
    VISION_MAX_IMAGE_SIZE_MB: int = 5
    VISION_MAX_IMAGES_PER_SUBMISSION: int = 10
    VISION_EXTRACTION_TEMPERATURE: float = 0.1

    # Semantic Mapping Configuration
    SEMANTIC_MAPPING_ENABLED: bool = True
    SEMANTIC_MAPPING_MODEL: str = ""
    SEMANTIC_MAPPING_TEMPERATURE: float = 0.0
    SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD: float = 0.7

    # Storage Configuration
    ARTIFACT_STORAGE_BACKEND: str = "local"
    ARTIFACT_STORAGE_LOCAL_DIR: str = "storage/artifacts"
    ARTIFACT_MAX_FILE_SIZE_MB: int = 50
    ARTIFACT_DOWNLOAD_URL_EXPIRY_SECONDS: int = 3600
    ARTIFACT_STORAGE_S3_BUCKET: str = ""
    ARTIFACT_STORAGE_S3_REGION: str = "us-east-1"
    ARTIFACT_STORAGE_S3_ENDPOINT: str = ""
    ARTIFACT_STORAGE_S3_ACCESS_KEY: str = ""
    ARTIFACT_STORAGE_S3_SECRET_KEY: str = ""

    BACKGROUND_JOB_STORAGE_DIR: str = "storage/background-jobs"

    # Image Generation Configuration
    IMAGE_GEN_ENABLED: bool = True
    IMAGE_GEN_PROVIDER: str = "amd"
    IMAGE_GEN_MODEL: str = ""
    IMAGE_GEN_FALLBACK_MODEL: str = ""
    IMAGE_GEN_REQUEST_TIMEOUT: int = 120
    IMAGE_GEN_MAX_RETRIES: int = 2
    IMAGE_GEN_DEFAULT_SIZE: str = "1024x1024"
    IMAGE_GEN_DEFAULT_QUALITY: str = "standard"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
