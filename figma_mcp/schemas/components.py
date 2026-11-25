"""Schemas for the components group (published components, component sets and styles)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult


class LibraryUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    handle: str
    img_url: str


# Field naming/typing unconfirmed live (docs: node_id + string sets; spec: nodeId + objects).
class FrameInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    nodeId: str | None = Field(default=None, description="ID of the containing frame node within the file.")
    name: str | None = None
    backgroundColor: str | None = None
    pageId: str | None = None
    pageName: str | None = None
    containingStateGroup: dict[str, Any] | str | None = Field(
        default=None, description="Deprecated — use containingComponentSet.")
    containingComponentSet: dict[str, Any] | str | None = Field(
        default=None, description="Component set node that contains the frame ({nodeId, name}), or null.")


class PublishedComponent(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="Library-wide unique key of the published asset; input to the get tool.")
    file_key: str = Field(description="Key of the Figma file that contains the asset.")
    node_id: str = Field(description="ID of the asset's node within that file.")
    thumbnail_url: str | None = None
    name: str
    description: str
    created_at: str
    updated_at: str
    user: LibraryUser = Field(description="User who last updated the asset.")
    containing_frame: FrameInfo | None = None


class PublishedStyle(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="Library-wide unique key of the published style; input to get_style.")
    file_key: str = Field(description="Key of the Figma file that contains the style.")
    node_id: str = Field(description="ID of the style node within that file.")
    style_type: str = Field(description="One of FILL, TEXT, EFFECT, GRID.")
    thumbnail_url: str | None = None
    name: str
    description: str
    created_at: str
    updated_at: str
    user: LibraryUser = Field(description="User who last updated the style.")
    sort_position: str = Field(description="User-specified order string by which the style can be sorted.")


class PageCursor(BaseModel):
    model_config = ConfigDict(extra="allow")

    before: int | None = Field(default=None, description="Pass back as `before` to fetch the previous page.")
    after: int | None = Field(default=None, description="Pass back as `after` to fetch the next page. Absent when there are no results.")


# list_team_components

class TeamComponentListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    components: list[PublishedComponent]
    cursor: PageCursor | None = None


class TeamComponentListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: TeamComponentListMeta


class TeamComponentListResult(ToolResult):
    data: TeamComponentListData | None = None


# list_file_components

class FileComponentListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    components: list[PublishedComponent]


class FileComponentListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: FileComponentListMeta


class FileComponentListResult(ToolResult):
    data: FileComponentListData | None = None


# get_component

class ComponentData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: PublishedComponent


class ComponentResult(ToolResult):
    data: ComponentData | None = None


# list_team_component_sets

class TeamComponentSetListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    component_sets: list[PublishedComponent]
    cursor: PageCursor | None = None


class TeamComponentSetListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: TeamComponentSetListMeta


class TeamComponentSetListResult(ToolResult):
    data: TeamComponentSetListData | None = None


# list_file_component_sets

class FileComponentSetListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    component_sets: list[PublishedComponent]


class FileComponentSetListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: FileComponentSetListMeta


class FileComponentSetListResult(ToolResult):
    data: FileComponentSetListData | None = None


# get_component_set

class ComponentSetData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: PublishedComponent


class ComponentSetResult(ToolResult):
    data: ComponentSetData | None = None


# list_team_styles

class TeamStyleListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    styles: list[PublishedStyle]
    cursor: PageCursor | None = None


class TeamStyleListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: TeamStyleListMeta


class TeamStyleListResult(ToolResult):
    data: TeamStyleListData | None = None


# list_file_styles

class FileStyleListMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    styles: list[PublishedStyle]


class FileStyleListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: FileStyleListMeta


class FileStyleListResult(ToolResult):
    data: FileStyleListData | None = None


# get_style

class StyleData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int
    error: bool
    meta: PublishedStyle


class StyleResult(ToolResult):
    data: StyleData | None = None
