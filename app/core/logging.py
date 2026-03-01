import logging
import json
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict

# Context variable to store trace ID
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "trace_id": trace_id_var.get()
        }
        
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    logger = logging.getLogger("support_portal")
    logger.setLevel(level)
    logger.addHandler(handler)
    # Prevent propagation to root logger to avoid duplicate logs if root is configured
    logger.propagate = False
    return logger

logger = setup_logging()

def set_trace_id(trace_id: str = None):
    if not trace_id:
        trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    return trace_id

def get_trace_id():
    return trace_id_var.get()

class LogLatency:
    def __init__(self, module_name: str, action_name: str, extra: dict = None):
        self.module_name = module_name
        self.action_name = action_name
        self.extra = extra or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency = (time.time() - self.start_time) * 1000
        extra = {
            "extra_data": {
                "module": self.module_name,
                "action": self.action_name,
                "latency_ms": round(latency, 2),
                "status": "error" if exc_type else "success",
                **self.extra
            }
        }
        logger.info(f"Latency log: {self.module_name}.{self.action_name}", extra=extra)
