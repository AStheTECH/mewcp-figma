"""Users group: get_current_user"""

import logging

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.users import CurrentUserData, CurrentUserResult
from ._helpers import _handle_request_exc, _upstream_err

logger = logging.getLogger("figma-mcp.tools.users")


def register_users_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_current_user",
        description=(
            "Gets the Figma user the connection is authorized as. Returns the user's `id`, "
            "`handle` (name), `img_url` (profile image URL) and `email`. This is the only "
            "endpoint that returns `email`: user objects embedded in comments, versions and "
            "components carry only `id`, `handle` and `img_url`. The `id` matches `user.id` on "
            "comments and reactions, so use it to tell which ones the user authored (only the "
            "author can delete a comment or reaction). Requires the `current_user:read` scope; "
            "Tier 3 rate limit."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_current_user() -> CurrentUserResult:
        tlog = ToolLogger(logger, "get_current_user")
        try:
            data, status, retry_after = service.api_request(
                "GET", "/v1/me", timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return CurrentUserResult(success=True, statusCode=status,
                                         data=CurrentUserData(**data))
            return _upstream_err(CurrentUserResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CurrentUserResult, tlog, exc)
