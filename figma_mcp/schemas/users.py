"""Schemas for the users group."""

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult


class CurrentUserData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Unique stable id of the user; matches `user.id` on comments and reactions.")
    handle: str = Field(description="Name of the user.")
    img_url: str
    email: str


class CurrentUserResult(ToolResult):
    data: CurrentUserData | None = None
