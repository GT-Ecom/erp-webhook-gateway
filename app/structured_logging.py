import json
import uuid
import logging
import time
import requests
from typing import Any, Dict, Optional
from contextvars import ContextVar
import graypy

from .config import settings

correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class SlackHandler(logging.Handler):
    """Send error logs to Slack channel"""
    
    def __init__(self, webhook_url: str, channel: str):
        super().__init__()
        self.webhook_url = webhook_url
        self.channel = channel
        self.setLevel(logging.ERROR)
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            
            shop_domain = getattr(record, 'shop_domain', 'unknown')
            site_name = getattr(record, 'site_name', 'unknown')
            source = getattr(record, 'source', 'unknown')
            topic = getattr(record, 'topic', 'unknown')
            event_id = getattr(record, 'event_id', 'unknown')
            cid = correlation_id.get() or 'unknown'
            
            slack_message = {
                "channel": self.channel,
                "username": "ERP Webhook Gateway Alert",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": "danger",
                        "title": f"Error in {settings.environment.upper()} environment",
                        "fields": [
                            {"title": "Level", "value": record.levelname, "short": True},
                            {"title": "Logger", "value": record.name, "short": True},
                            {"title": "Shop Domain", "value": shop_domain, "short": True},
                            {"title": "Site Name", "value": site_name, "short": True},
                            {"title": "Source", "value": source, "short": True},
                            {"title": "Topic", "value": topic, "short": True},
                            {"title": "Event ID", "value": event_id, "short": True},
                            {"title": "Correlation ID", "value": cid, "short": True},
                            {"title": "Message", "value": message, "short": False}
                        ],
                        "footer": "ERP Webhook Gateway",
                        "ts": int(time.time())
                    }
                ]
            }
            
            if record.exc_info:
                exception_text = self.formatter.formatException(record.exc_info)
                slack_message["attachments"][0]["fields"].append({
                    "title": "Exception",
                    "value": f"```{exception_text}```",
                    "short": False
                })
            
            requests.post(self.webhook_url, json=slack_message, timeout=5)
            
        except Exception:
            self.handleError(record)


class WebhookGatewayFilter(logging.Filter):
    """Inject context fields into each log record"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        environment = settings.environment
        record._environment = environment
        record._app = "erp-webhook-gateway"
        record._tag = f"ERP-WEBHOOK-GATEWAY-{environment.upper()}"
        return True


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime()),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': correlation_id.get(),
            'environment': settings.environment,
        }
        
        for attr in ['event_id', 'shop_domain', 'topic', 'source', 'site_name', 'duration_ms']:
            value = getattr(record, attr, None)
            if value is not None:
                log_data[attr] = value
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def get_graylog_handler() -> Optional[graypy.GELFTCPHandler]:
    """Get configured Graylog handler"""
    if not settings.graylog_enabled or not settings.graylog_host:
        return None
    
    try:
        handler = graypy.GELFTCPHandler(
            settings.graylog_host,
            settings.graylog_port,
            extra_fields={
                "_app": "erp-webhook-gateway",
                "_environment": settings.environment,
            }
        )
        handler.setLevel(logging.INFO)
        handler.addFilter(WebhookGatewayFilter())
        return handler
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to configure Graylog handler: {e}")
        return None


def get_slack_handler() -> Optional[SlackHandler]:
    """Get configured Slack handler for error alerts"""
    if not settings.slack_enabled or not settings.slack_webhook_url:
        return None
    
    try:
        handler = SlackHandler(settings.slack_webhook_url, settings.slack_channel)
        handler.setLevel(logging.ERROR)
        return handler
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to configure Slack handler: {e}")
        return None


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured JSON logging with Graylog and Slack support"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    handlers = []
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    handlers.append(console_handler)
    
    graylog_handler = get_graylog_handler()
    if graylog_handler:
        handlers.append(graylog_handler)
    
    slack_handler = get_slack_handler()
    if slack_handler:
        handlers.append(slack_handler)
    
    root_logger.handlers = handlers


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for current context"""
    cid = cid or generate_correlation_id()
    correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id.get()


class LogContext:
    """Context manager for adding extra fields to log records"""
    
    def __init__(self, logger: logging.Logger, **kwargs: Any):
        self.logger = logger
        self.extra = kwargs
    
    def info(self, msg: str) -> None:
        self._log(logging.INFO, msg)
    
    def error(self, msg: str, exc_info: bool = False) -> None:
        self._log(logging.ERROR, msg, exc_info=exc_info)
    
    def warning(self, msg: str) -> None:
        self._log(logging.WARNING, msg)
    
    def debug(self, msg: str) -> None:
        self._log(logging.DEBUG, msg)
    
    def _log(self, level: int, msg: str, exc_info: bool = False) -> None:
        record = self.logger.makeRecord(
            self.logger.name, level, '', 0, msg, (), None
        )
        for key, value in self.extra.items():
            setattr(record, key, value)
        if exc_info:
            import sys
            record.exc_info = sys.exc_info()
        self.logger.handle(record)
