from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

_AUDIENCE_DESC = (
    "The audience that can access the folder: plan_view, plan_edit, invite_only, "
    "workspace_view or workspace_edit."
)
_PARENT_DESC = (
    "The ID of the folder's parent folder, or null if the folder is a top-level folder in the team."
)


class FolderItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    parent_folder_id: str | None = Field(description=_PARENT_DESC)
    sharing_audience_control: str | None = Field(default=None, description=_AUDIENCE_DESC)
    created_at: str | None = None


class CreateFolderData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    parent_folder_id: str | None = Field(description=_PARENT_DESC)
    sharing_audience_control: str = Field(description=_AUDIENCE_DESC)
    created_at: str


class CreateFolderResult(ToolResult):
    data: CreateFolderData | None = None


class TeamFolderListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(description="The team's name.")
    folders: list[FolderItem] = Field(
        description="The team's top-level folders; each folder's parent_folder_id is null."
    )


class TeamFolderListResult(ToolResult):
    data: TeamFolderListData | None = None


class SubfolderListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(description="The parent folder's name.")
    folders: list[FolderItem] = Field(
        description="The folder's direct subfolders; each subfolder's parent_folder_id equals the requested folder's ID."
    )


class SubfolderListResult(ToolResult):
    data: SubfolderListData | None = None


class FolderFileBranch(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="The branch's file key.")
    name: str
    thumbnail_url: str | None = None
    last_modified: str


class FolderFileItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="The file's key (the file_key used by file tools).")
    name: str
    thumbnail_url: str | None = None
    last_modified: str
    branches: list[FolderFileBranch] | None = Field(
        default=None,
        description="The file's branches; present only when branch_data is true and the file has branches.",
    )


class FolderFileListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(description="The folder's name.")
    files: list[FolderFileItem]


class FolderFileListResult(ToolResult):
    data: FolderFileListData | None = None


class FolderMetadataData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    thumbnail_url: str | None = Field(
        default=None, description="A URL to a thumbnail image of the folder; null if the folder has no files."
    )
    file_count: int
    updated_at: str
    created_at: str


class FolderMetadataResult(ToolResult):
    data: FolderMetadataData | None = None
