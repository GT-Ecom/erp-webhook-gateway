from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    google_cloud_project: str
    pubsub_topic_shopify: str
    pubsub_topic_parcel_panel: str
    port: int = 8080
    
    max_payload_size_bytes: int = 10 * 1024 * 1024
    rate_limit_per_shop: int = 100
    rate_limit_window_seconds: int = 60
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
