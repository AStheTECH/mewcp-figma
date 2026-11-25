"""Schemas for the library_analytics group."""

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

Number = int | float


class _Row(BaseModel):
    model_config = ConfigDict(extra="allow")


class _ActionRow(_Row):
    week: str | None = Field(default=None, description="Week date in ISO 8601 format, e.g. 2023-12-13.")
    team_name: str | None = Field(default=None, description="Team using the library. Set when group_by=team.")
    workspace_name: str | None = Field(default=None, description="Workspace the team belongs to. Only on group_by=team rows; may be absent.")
    detachments: Number | None = Field(default=None, description="Detach events in this week.")
    insertions: Number | None = Field(default=None, description="Insertion events in this week.")


class _UsageRow(_Row):
    file_name: str | None = Field(default=None, description="File using the library. Set when group_by=file.")
    team_name: str | None = Field(default=None, description="Team the file belongs to. Set when group_by=file.")
    workspace_name: str | None = Field(default=None, description="Workspace the file belongs to. Only on group_by=file rows; may be absent.")
    teams_using: Number | None = Field(default=None, description="Teams using the asset within the organization. Not set on group_by=file rows.")
    files_using: Number | None = Field(default=None, description="Files using the asset within the organization. Not set on group_by=file rows.")


class _PageData(BaseModel):
    model_config = ConfigDict(extra="allow")

    next_page: bool
    cursor: str | None = Field(default=None, description="Pass as `cursor` to fetch the next page. Absent when next_page is false.")


# --- component ---

class LibraryComponentActionRow(_ActionRow):
    component_key: str | None = Field(default=None, description="Set when group_by=component.")
    component_name: str | None = Field(default=None, description="Set when group_by=component.")
    component_set_key: str | None = Field(default=None, description="Component set the component belongs to. group_by=component only; may be absent.")
    component_set_name: str | None = Field(default=None, description="Component set the component belongs to. group_by=component only; may be absent.")


class LibraryComponentActionListData(_PageData):
    rows: list[LibraryComponentActionRow]


class LibraryComponentActionListResult(ToolResult):
    data: LibraryComponentActionListData | None = None


class LibraryComponentUsageRow(_UsageRow):
    component_key: str | None = Field(default=None, description="Set when group_by=component.")
    component_name: str | None = Field(default=None, description="Set when group_by=component.")
    component_set_key: str | None = Field(default=None, description="Component set the component belongs to. group_by=component only; may be absent.")
    component_set_name: str | None = Field(default=None, description="Component set the component belongs to. group_by=component only; may be absent.")
    usages: Number | None = Field(default=None, description="group_by=component: instances of the component within the organization. group_by=file: component instances from the library used within the file.")


class LibraryComponentUsageListData(_PageData):
    rows: list[LibraryComponentUsageRow]


class LibraryComponentUsageListResult(ToolResult):
    data: LibraryComponentUsageListData | None = None


# --- style ---

class LibraryStyleActionRow(_ActionRow):
    style_key: str | None = Field(default=None, description="Set when group_by=style.")
    style_name: str | None = Field(default=None, description="Set when group_by=style.")
    style_type: str | None = Field(default=None, description="Set when group_by=style.")


class LibraryStyleActionListData(_PageData):
    rows: list[LibraryStyleActionRow]


class LibraryStyleActionListResult(ToolResult):
    data: LibraryStyleActionListData | None = None


class LibraryStyleUsageRow(_UsageRow):
    style_key: str | None = Field(default=None, description="Set when group_by=style.")
    style_name: str | None = Field(default=None, description="Set when group_by=style.")
    style_type: str | None = Field(default=None, description="Set when group_by=style.")
    usages: Number | None = Field(default=None, description="group_by=style: usages of the style within the organization. group_by=file: times styles from this library are used within the file.")


class LibraryStyleUsageListData(_PageData):
    rows: list[LibraryStyleUsageRow]


class LibraryStyleUsageListResult(ToolResult):
    data: LibraryStyleUsageListData | None = None


# --- variable ---

class LibraryVariableActionRow(_ActionRow):
    variable_key: str | None = Field(default=None, description="Set when group_by=variable.")
    variable_name: str | None = Field(default=None, description="Set when group_by=variable.")
    variable_type: str | None = Field(default=None, description="Set when group_by=variable.")
    collection_key: str | None = Field(default=None, description="Collection the variable belongs to. Set when group_by=variable.")
    collection_name: str | None = Field(default=None, description="Collection the variable belongs to. Set when group_by=variable.")


class LibraryVariableActionListData(_PageData):
    rows: list[LibraryVariableActionRow]


class LibraryVariableActionListResult(ToolResult):
    data: LibraryVariableActionListData | None = None


class LibraryVariableUsageRow(_UsageRow):
    variable_key: str | None = Field(default=None, description="Set when group_by=variable.")
    variable_name: str | None = Field(default=None, description="Set when group_by=variable.")
    variable_type: str | None = Field(default=None, description="Set when group_by=variable.")
    collection_key: str | None = Field(default=None, description="Collection the variable belongs to. Set when group_by=variable.")
    collection_name: str | None = Field(default=None, description="Collection the variable belongs to. Set when group_by=variable.")
    usages: Number | None = Field(default=None, description="group_by=variable: usages of the variable within the organization. group_by=file: times variables from this library are used within the file.")


class LibraryVariableUsageListData(_PageData):
    rows: list[LibraryVariableUsageRow]


class LibraryVariableUsageListResult(ToolResult):
    data: LibraryVariableUsageListData | None = None
