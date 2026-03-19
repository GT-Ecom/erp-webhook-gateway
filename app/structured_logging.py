import json
import uuid
import logging
import time
from typing import Any, Dict, Optional
from contextvars import ContextVar

correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime()),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': correlation_id.get(),
        }
        
        for attr in ['event_id', 'shop_domain', 'topic', 'source', 'site_name', 'duration_ms']:
            value = getattr(record, attr, None)
            if value is not None:
                log_data[attr] = value
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured JSON logging"""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]


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
