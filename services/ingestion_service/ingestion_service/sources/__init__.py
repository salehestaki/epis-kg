"""Pluggable ingestion sources.

Each source yields :class:`~graph_schema.RawDocument` payloads. Add new
providers (X/Twitter, RSS, News APIs) by subclassing :class:`BaseSource`.
"""

from ingestion_service.sources.base import BaseSource
from ingestion_service.sources.file_source import FileSource
from ingestion_service.sources.http_source import HttpJSONSource

__all__ = ["BaseSource", "FileSource", "HttpJSONSource"]
