from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    google_cloud_project: str
    pubsub_topic_shopify: str
    pubsub_topic_parcel_panel: str
    port: int = 8080
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
