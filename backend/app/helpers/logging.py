import logging
import sys
from contextvars import ContextVar
from typing import Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
error_code_var: ContextVar[str] = ContextVar("error_code", default="-")


class StructuredLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_id = request_id_var.get()
        self.error_code = error_code_var.get()


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        if not hasattr(record, "error_code"):
            record.error_code = error_code_var.get()

        prefix = f"{record.levelname}"
        if record.error_code and record.error_code != "-":
            prefix += f" [{record.error_code}]"
        prefix += f" request_id={record.request_id}"

        # Combine with message and format
        original_msg = super().format(record)
        return f"{prefix} {original_msg}"


def setup_logging(level: str = "INFO"):
    logging.setLogRecordFactory(StructuredLogRecord)
    handler = logging.StreamHandler(sys.stdout)
    formatter = StructuredFormatter("%(name)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = [handler]

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("gyros")
