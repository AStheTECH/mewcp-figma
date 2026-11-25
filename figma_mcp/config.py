"""Configuration for MewCP Figma MCP Server."""

import logging
import os

SERVER_VERSION = "v1.0.0"
BREAKING_CHANGES: list[dict] = []

SCOPES = [
    "current_user:read",
    "file_content:read",
    "file_metadata:read",
    "file_versions:read",
    "file_comments:read",
    "file_comments:write",
    "file_dev_resources:read",
    "file_dev_resources:write",
    "file_variables:read",
    "file_variables:write",
    "library_analytics:read",
    "library_assets:read",
    "library_content:read",
    "team_library_content:read",
    "folders:read",
    "folder_metadata:read",
    "teams:read",
    "file_duplicate:write",
    "folders:write",
    "teams:write",
    "team_members:write",
]

FIGMA_API_BASE = "https://api.figma.com"  # endpoint paths carry their own /v1 or /v2

CONNECT_TIMEOUT = 5    # TCP connection — fixed across all servers
READ_TIMEOUT = 60      # no published SLA; large file/node/image-render requests are slow


def configure_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    try:
        from pythonjsonlogger.json import JsonFormatter
        handler = logging.StreamHandler()
        handler.setFormatter(
            JsonFormatter(fmt="%(asctime)s %(name)s %(levelname)s %(message)s")
        )
    except ImportError:
        handler = logging.StreamHandler()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)
