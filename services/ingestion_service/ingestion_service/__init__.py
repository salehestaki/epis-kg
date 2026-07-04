"""Epis-KG data ingestion layer.

Consumes raw text from pluggable sources, sanitises it, and publishes
:class:`~graph_schema.RawDocument` payloads onto a Redis Stream that the
reasoning layer consumes. This isolation prevents the expensive LLM layer
from blocking high-throughput data streams.
"""

from ingestion_service.broker import RedisStreamBroker
from ingestion_service.sanitize import sanitize

__all__ = ["RedisStreamBroker", "sanitize"]
