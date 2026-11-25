from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

_CLIENT_META_DESC = (
    "Comment position, one of: Vector {x, y} (absolute canvas coordinates); "
    "FrameOffset {node_id, node_offset: {x, y}} (offset from the frame's top-left corner); "
    "Region {x, y, region_height, region_width, comment_pin_corner}; "
    "FrameOffsetRegion {node_id, node_offset: {x, y}, region_height, region_width, comment_pin_corner}. "
    "comment_pin_corner is top-left, top-right, bottom-left or bottom-right (default bottom-right)."
)
_EMOJI_DESC = "Reaction emoji as a shortcode, e.g. `:heart:` or `:+1::skin-tone-2:`."


class CommentReaction(BaseModel):
    model_config = ConfigDict(extra="allow")

    user: dict[str, Any] = Field(description="User who left the reaction: id, handle, img_url.")
    emoji: str = Field(description=_EMOJI_DESC)
    created_at: str


class Comment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    client_meta: dict[str, Any] | None = Field(default=None, description=_CLIENT_META_DESC)
    file_key: str
    parent_id: str | None = Field(
        default=None,
        description="ID of the root comment this is a reply to. Empty string or absent on root comments.",
    )
    user: dict[str, Any] = Field(description="User who left the comment: id, handle, img_url.")
    created_at: str
    resolved_at: str | None = Field(
        default=None, description="UTC ISO 8601 time the comment was resolved; null if unresolved."
    )
    message: str = Field(description="Text content of the comment.")
    order_id: str | None = Field(
        default=None,
        description="Number shown with the comment in the UI, as a string. Only set on root comments.",
    )
    reactions: list[CommentReaction] = Field(default_factory=list)


class CommentListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    comments: list[Comment]


class CommentListResult(ToolResult):
    data: CommentListData | None = None


class CreateCommentData(Comment):
    pass


class CreateCommentResult(ToolResult):
    data: CreateCommentData | None = None


class DeleteCommentData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool


class DeleteCommentResult(ToolResult):
    data: DeleteCommentData | None = None


class CommentReactionPagination(BaseModel):
    model_config = ConfigDict(extra="allow")

    prev_page: str | None = Field(default=None, description="URL that calls the previous page.")
    next_page: str | None = Field(
        default=None, description="URL that calls the next page; absent on the last page."
    )


class CommentReactionListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    reactions: list[CommentReaction]
    pagination: CommentReactionPagination = Field(default_factory=CommentReactionPagination)


class CommentReactionListResult(ToolResult):
    data: CommentReactionListData | None = None


class CreateCommentReactionData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool


class CreateCommentReactionResult(ToolResult):
    data: CreateCommentReactionData | None = None


class DeleteCommentReactionData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool


class DeleteCommentReactionResult(ToolResult):
    data: DeleteCommentReactionData | None = None
