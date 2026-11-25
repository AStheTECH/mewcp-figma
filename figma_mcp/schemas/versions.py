from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult


class VersionUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    handle: str
    img_url: str


class FileVersion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Version ID; pass as `version` to get_file, get_file_nodes or render_images.")
    created_at: str
    label: str | None = None
    description: str | None = None
    user: VersionUser
    thumbnail_url: str | None = None


class VersionPagination(BaseModel):
    model_config = ConfigDict(extra="allow")

    prev_page: str | None = Field(default=None, description="URL of the previous page; pass as `page_url` to fetch it.")
    next_page: str | None = Field(default=None, description="URL of the next page; pass as `page_url` to fetch it.")


class FileVersionListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    versions: list[FileVersion]
    pagination: VersionPagination | None = None


class FileVersionListResult(ToolResult):
    data: FileVersionListData | None = None
