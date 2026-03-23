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
    
    graylog_host: Optional[str] = None
    graylog_port: int = 12201
    graylog_enabled: bool = False
    
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#erp-graylog-alerts"
    slack_enabled: bool = False
    
    environment: str = "production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
