"""Cross-cutting observability helpers for Epis-KG.

Provides:
* :func:`configure_logging` / :func:`get_logger` - structured JSON logging.
* :func:`traced` - a decorator that emits a span (OpenTelemetry if installed,
  otherwise a structured log entry) around any sync or async callable.
* :func:`langsmith_enabled` - single source of truth for LangSmith tracing.
"""

from observability.logging import configure_logging, get_logger
from observability.tracing import langsmith_enabled, traced

__all__ = ["configure_logging", "get_logger", "traced", "langsmith_enabled"]
