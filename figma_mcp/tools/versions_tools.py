"""Versions group: list_file_versions"""

import logging
import re
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.versions import FileVersionListData, FileVersionListResult
from ._helpers import _err, _handle_request_exc, _upstream_err

logger = logging.getLogger("figma-mcp.tools.versions")

_PAGE_PATH_RE = re.compile(r"/files/([^/]+)/versions/?$")


def register_versions_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_file_versions",
        description=(
            "Lists a Figma file's version history, ordered by creation time. Returns `versions` "
            "(each with `id`, `created_at`, `label`, `description`, `user` and, when present, "
            "`thumbnail_url`; `label`/`description` can be null) and `pagination` with optional "
            "`next_page`/`prev_page` URLs (either may be absent). To get another page, pass a "
            "`pagination.next_page` or `prev_page` URL back as `page_url` — its query string is "
            "replayed unchanged, since Figma's paging URLs page by timestamp rather than version "
            "ID; `before`/`after` take a version ID as Figma's spec describes. An empty `versions` "
            "list can still come with paging URLs: stop paging as soon as a page returns no "
            "versions. A version `id` is the `version` param of get_file, get_file_nodes and "
            "render_images. Needs the `file_versions:read` scope (Tier 2 rate limit); a 404 means "
            "the file was not found."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_file_versions(
        file_key: str = Field(description=(
            "File to get version history from: a file key or a branch key. Get a branch key from "
            "get_file with `branch_data` set."
        )),
        page_size: int | None = Field(default=None, description=(
            "Number of versions per page (1–50). Omit for Figma's default of 30. Not combinable "
            "with `page_url`."
        )),
        before: int | None = Field(default=None, description=(
            "A version ID from the history; returns versions before it. Omit for the first page. "
            "Not combinable with `page_url`."
        )),
        after: int | None = Field(default=None, description=(
            "A version ID from the history; returns versions after it. Omit for the first page. "
            "Not combinable with `page_url`."
        )),
        page_url: str | None = Field(default=None, description=(
            "A `pagination.next_page` or `pagination.prev_page` URL from a previous "
            "list_file_versions response for the same file, passed back as-is. Its query "
            "parameters are forwarded unchanged. Omit for the first page."
        )),
    ) -> FileVersionListResult:
        tlog = ToolLogger(logger, "list_file_versions")

        if not file_key.strip():
            return _err(FileVersionListResult, tlog, "VALIDATION_ERROR",
                        "file_key must not be empty", 400)
        if page_size is not None and not 1 <= page_size <= 50:
            return _err(FileVersionListResult, tlog, "VALIDATION_ERROR",
                        "page_size must be between 1 and 50", 400)

        if page_url is not None:
            if page_size is not None or before is not None or after is not None:
                return _err(FileVersionListResult, tlog, "VALIDATION_ERROR",
                            "page_url replays a paging URL as-is; don't combine it with "
                            "page_size, before or after", 400)
            parts = urlsplit(page_url.strip())
            match = _PAGE_PATH_RE.search(parts.path)
            if not match or not parts.query:
                return _err(FileVersionListResult, tlog, "VALIDATION_ERROR",
                            "page_url must be a pagination.next_page or prev_page URL "
                            "(.../v1/files/<file_key>/versions?...)", 400)
            if unquote(match.group(1)) != file_key:
                return _err(FileVersionListResult, tlog, "VALIDATION_ERROR",
                            "page_url belongs to a different file than file_key", 400)
            params = dict(parse_qsl(parts.query, keep_blank_values=True))
        else:
            params = {}
            if page_size is not None:
                params["page_size"] = page_size
            if before is not None:
                params["before"] = before
            if after is not None:
                params["after"] = after

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}/versions",
                params=params or None,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = FileVersionListResult(success=True, statusCode=status,
                                               data=FileVersionListData(**data))
                tlog.success()
                return result
            return _upstream_err(FileVersionListResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(FileVersionListResult, tlog, exc)
