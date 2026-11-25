"""Comments group: list_comments, create_comment, delete_comment, list_comment_reactions,
create_comment_reaction, delete_comment_reaction"""

import logging
from typing import Any
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.comments import (
    CommentListData,
    CommentListResult,
    CommentReactionListData,
    CommentReactionListResult,
    CreateCommentData,
    CreateCommentReactionData,
    CreateCommentReactionResult,
    CreateCommentResult,
    DeleteCommentData,
    DeleteCommentReactionData,
    DeleteCommentReactionResult,
    DeleteCommentResult,
)
from ._helpers import _err, _handle_request_exc, _upstream_err

logger = logging.getLogger("figma-mcp.tools.comments")

_PIN_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")

_FILE_KEY_DESC = (
    "Key of the Figma file (from the file URL or `files[].key` of list_folder_files). "
    "A branch key also works; get it from `branches[].key` of get_file with `branch_data` enabled."
)
_EMOJI_DESC = (
    "Reaction emoji as a shortcode, e.g. `:heart:` or `:+1::skin-tone-2:`. Accepted shortcodes are the "
    "top-level `emojis` and `aliases` entries of "
    "https://raw.githubusercontent.com/missive/emoji-mart/main/packages/emoji-mart-data/sets/14/native.json, "
    "with optional skin tone modifiers."
)


def _seg(value: str) -> str:
    return quote(value, safe="")


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _client_meta_error(cm: dict[str, Any]) -> str | None:
    has_vector = "x" in cm or "y" in cm
    has_frame = "node_id" in cm or "node_offset" in cm
    if has_vector == has_frame:
        return ("client_meta must use either x and y (Vector / Region) or node_id and node_offset "
                "(FrameOffset / FrameOffsetRegion)")
    if has_vector and not (_is_num(cm.get("x")) and _is_num(cm.get("y"))):
        return "client_meta x and y must both be numbers"
    if has_frame:
        if not isinstance(cm.get("node_id"), str) or not cm["node_id"]:
            return "client_meta node_id must be a non-empty string"
        offset = cm.get("node_offset")
        if not (isinstance(offset, dict) and _is_num(offset.get("x")) and _is_num(offset.get("y"))):
            return "client_meta node_offset must be an object with numeric x and y"
    if "region_height" in cm or "region_width" in cm:
        for key in ("region_height", "region_width"):
            if not (_is_num(cm.get(key)) and cm[key] > 0):
                return f"client_meta {key} must be a number greater than 0 for a region comment"
    elif "comment_pin_corner" in cm:
        return "client_meta comment_pin_corner needs region_height and region_width"
    if "comment_pin_corner" in cm and cm["comment_pin_corner"] not in _PIN_CORNERS:
        return f"client_meta comment_pin_corner must be one of: {', '.join(_PIN_CORNERS)}"
    return None


def _ack(data: dict[str, Any], status: int) -> dict[str, Any]:
    out = {k: v for k, v in data.items() if k not in ("status", "error")}
    out["status"] = data["status"] if _is_num(data.get("status")) else status
    out["error"] = data["error"] if isinstance(data.get("error"), bool) else False
    return out


def register_comments_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_comments",
        description=(
            "Lists every comment and reply on a Figma file. Returns each comment's `id`, text "
            "(`message`), position (`client_meta`), author (`user`), `created_at`, `resolved_at` "
            "(null if unresolved), `order_id` (the number shown in the UI, root comments only) and "
            "inline `reactions`. A comment is a reply only when `parent_id` is a non-empty string; "
            "root comments return `parent_id` as an empty string. `id` is the `comment_id` for "
            "delete_comment, the reaction tools and replies via create_comment. Needs the "
            "`file_comments:read` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_comments(
        file_key: str = Field(description=_FILE_KEY_DESC),
        as_md: bool | None = Field(
            default=None,
            description="If true, returns comment text as its markdown equivalent where applicable. "
                        "Omit for plain text.",
        ),
    ) -> CommentListResult:
        tlog = ToolLogger(logger, "list_comments")
        if not file_key.strip():
            return _err(CommentListResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        params = {"as_md": "true" if as_md else "false"} if as_md is not None else None
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{_seg(file_key)}/comments", params=params,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = CommentListResult(success=True, statusCode=status, data=CommentListData(**data))
                tlog.success()
                return result
            return _upstream_err(CommentListResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CommentListResult, tlog, exc)

    @mcp.tool(
        name="create_comment",
        description=(
            "Posts a comment on a Figma file and returns the created comment (same shape as a "
            "list_comments item, including its `id`). Set `comment_id` to reply to a root comment; "
            "replies to replies are not allowed. Set `client_meta` to pin the comment to canvas "
            "coordinates, a frame (node ids from get_file / get_file_nodes) or a region. Needs the "
            "`file_comments:write` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def create_comment(
        file_key: str = Field(description=_FILE_KEY_DESC),
        message: str = Field(description="Text content of the comment to post."),
        comment_id: str | None = Field(
            default=None,
            description="ID of the comment to reply to (`comments[].id` from list_comments). Must be a "
                        "root comment, i.e. one whose `parent_id` is empty. Omit to post a new root comment.",
        ),
        client_meta: dict[str, Any] | None = Field(
            default=None,
            description=(
                "Where to place the comment, as an object in one of four shapes: "
                "Vector {\"x\": number, \"y\": number} for absolute canvas coordinates; "
                "FrameOffset {\"node_id\": str, \"node_offset\": {\"x\": number, \"y\": number}} for an "
                "offset from the top-left corner of a frame; "
                "Region {\"x\", \"y\", \"region_height\", \"region_width\", \"comment_pin_corner\"} for a "
                "region on the canvas; "
                "FrameOffsetRegion {\"node_id\", \"node_offset\": {\"x\", \"y\"}, \"region_height\", "
                "\"region_width\", \"comment_pin_corner\"} for a region relative to a frame. "
                "region_height and region_width must be greater than 0; comment_pin_corner is one of "
                "top-left, top-right, bottom-left, bottom-right (default bottom-right). "
                "Omit to let Figma place the comment."
            ),
        ),
    ) -> CreateCommentResult:
        tlog = ToolLogger(logger, "create_comment")
        if not file_key.strip():
            return _err(CreateCommentResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        if not message.strip():
            return _err(CreateCommentResult, tlog, "VALIDATION_ERROR", "message must not be empty", 400)
        if client_meta is not None:
            problem = _client_meta_error(client_meta)
            if problem:
                return _err(CreateCommentResult, tlog, "VALIDATION_ERROR", problem, 400)
        body: dict[str, Any] = {"message": message}
        if comment_id is not None:
            body["comment_id"] = comment_id
        if client_meta is not None:
            body["client_meta"] = client_meta
        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/files/{_seg(file_key)}/comments", body=body,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = CreateCommentResult(success=True, statusCode=status, data=CreateCommentData(**data))
                tlog.success()
                return result
            return _upstream_err(CreateCommentResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CreateCommentResult, tlog, exc)

    @mcp.tool(
        name="delete_comment",
        description=(
            "DESTRUCTIVE — REQUIRES EXPLICIT USER CONFIRMATION BEFORE CALLING. "
            "Permanently deletes one comment from a Figma file. "
            "This action is irreversible — the comment and its text cannot be recovered. "
            "NEVER call this tool autonomously or as part of an automated flow. "
            "You MUST stop, tell the user exactly what will be deleted and that it is permanent, "
            "and wait for their explicit written confirmation before proceeding. "
            "Only the comment's author can delete it: compare `comments[].user.id` from list_comments "
            "with `id` from get_current_user first. Returns a `{status, error}` acknowledgement. "
            "Needs the `file_comments:write` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
    )
    def delete_comment(
        file_key: str = Field(description=_FILE_KEY_DESC),
        comment_id: str = Field(description="ID of the comment to delete (`comments[].id` from list_comments)."),
    ) -> DeleteCommentResult:
        tlog = ToolLogger(logger, "delete_comment")
        if not file_key.strip() or not comment_id.strip():
            return _err(DeleteCommentResult, tlog, "VALIDATION_ERROR",
                        "file_key and comment_id must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "DELETE", f"/v1/files/{_seg(file_key)}/comments/{_seg(comment_id)}",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = DeleteCommentResult(success=True, statusCode=status,
                                             data=DeleteCommentData(**_ack(data, status)))
                tlog.success()
                return result
            return _upstream_err(DeleteCommentResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(DeleteCommentResult, tlog, exc)

    @mcp.tool(
        name="list_comment_reactions",
        description=(
            "Lists the reactions on one comment of a Figma file, one page at a time. Returns each "
            "reaction's `emoji` shortcode, `user` (id, handle, img_url) and `created_at`, plus "
            "`pagination` with `next_page` / `prev_page` URLs. When `pagination.next_page` is absent "
            "there are no more pages. The same reactions also appear inline in list_comments. Needs "
            "the `file_comments:read` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_comment_reactions(
        file_key: str = Field(description=_FILE_KEY_DESC),
        comment_id: str = Field(
            description="ID of the comment to get reactions from (`comments[].id` from list_comments)."
        ),
        cursor: str | None = Field(
            default=None,
            description="Pagination cursor retrieved from the previous call's response "
                        "(`pagination.next_page` is the URL of the next page). Omit for the first page.",
        ),
    ) -> CommentReactionListResult:
        tlog = ToolLogger(logger, "list_comment_reactions")
        if not file_key.strip() or not comment_id.strip():
            return _err(CommentReactionListResult, tlog, "VALIDATION_ERROR",
                        "file_key and comment_id must not be empty", 400)
        params = {"cursor": cursor} if cursor is not None else None
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{_seg(file_key)}/comments/{_seg(comment_id)}/reactions",
                params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = CommentReactionListResult(success=True, statusCode=status,
                                                   data=CommentReactionListData(**data))
                tlog.success()
                return result
            return _upstream_err(CommentReactionListResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CommentReactionListResult, tlog, exc)

    @mcp.tool(
        name="create_comment_reaction",
        description=(
            "Adds an emoji reaction to a comment on a Figma file and returns a `{status, error}` "
            "acknowledgement. `emoji` must be a valid shortcode such as `:heart:` or "
            "`:+1::skin-tone-2:`; an unknown shortcode returns 400 \"Invalid emoji.\". `comment_id` "
            "is `comments[].id` from list_comments. Needs the `file_comments:write` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def create_comment_reaction(
        file_key: str = Field(description=_FILE_KEY_DESC),
        comment_id: str = Field(description="ID of the comment to react to (`comments[].id` from list_comments)."),
        emoji: str = Field(description=_EMOJI_DESC),
    ) -> CreateCommentReactionResult:
        tlog = ToolLogger(logger, "create_comment_reaction")
        if not file_key.strip() or not comment_id.strip() or not emoji.strip():
            return _err(CreateCommentReactionResult, tlog, "VALIDATION_ERROR",
                        "file_key, comment_id and emoji must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/files/{_seg(file_key)}/comments/{_seg(comment_id)}/reactions",
                body={"emoji": emoji}, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = CreateCommentReactionResult(success=True, statusCode=status,
                                                     data=CreateCommentReactionData(**_ack(data, status)))
                tlog.success()
                return result
            return _upstream_err(CreateCommentReactionResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CreateCommentReactionResult, tlog, exc)

    @mcp.tool(
        name="delete_comment_reaction",
        description=(
            "DESTRUCTIVE — REQUIRES EXPLICIT USER CONFIRMATION BEFORE CALLING. "
            "Permanently deletes one emoji reaction from a comment on a Figma file. "
            "This action is irreversible — the reaction cannot be recovered. "
            "NEVER call this tool autonomously or as part of an automated flow. "
            "You MUST stop, tell the user exactly what will be deleted and that it is permanent, "
            "and wait for their explicit written confirmation before proceeding. "
            "Only the reaction's author can delete it; find the reaction's `emoji` and `user.id` with "
            "list_comment_reactions or `comments[].reactions` from list_comments. Returns a "
            "`{status, error}` acknowledgement. Needs the `file_comments:write` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
    )
    def delete_comment_reaction(
        file_key: str = Field(description=_FILE_KEY_DESC),
        comment_id: str = Field(
            description="ID of the comment to delete the reaction from (`comments[].id` from list_comments)."
        ),
        emoji: str = Field(description=f"Shortcode of the reaction to remove. {_EMOJI_DESC}"),
    ) -> DeleteCommentReactionResult:
        tlog = ToolLogger(logger, "delete_comment_reaction")
        if not file_key.strip() or not comment_id.strip() or not emoji.strip():
            return _err(DeleteCommentReactionResult, tlog, "VALIDATION_ERROR",
                        "file_key, comment_id and emoji must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "DELETE", f"/v1/files/{_seg(file_key)}/comments/{_seg(comment_id)}/reactions",
                params={"emoji": emoji}, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = DeleteCommentReactionResult(success=True, statusCode=status,
                                                     data=DeleteCommentReactionData(**_ack(data, status)))
                tlog.success()
                return result
            return _upstream_err(DeleteCommentReactionResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(DeleteCommentReactionResult, tlog, exc)
