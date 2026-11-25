"""Schemas for the files group."""

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

_ROLE = "Requesting user's role on the file: owner, editor or viewer."
_GET_FILE_EDITOR = "Editor type of the file: figma or figjam."
_WIDE_EDITOR = "Editor type of the file: figma, figjam, slides, buzz, sites or make."
_COMPONENTS = ("Component node ID -> {key, name, description, componentSetId, documentationLinks, "
               "remote}. Only covers components inside the returned tree.")
_COMPONENT_SETS = ("Component set node ID -> {key, name, description, documentationLinks, remote}. "
                   "Only covers component sets inside the returned tree.")
_STYLES = "Style ID -> {key, name, description, remote, styleType (FILL, TEXT, EFFECT or GRID)}."


# get_file

class FileBranch(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(description="Branch key; can be passed back as `file_key`.")
    name: str
    thumbnail_url: str
    last_modified: str


class GetFileData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    role: str = Field(description=_ROLE)
    lastModified: str
    editorType: str = Field(description=_GET_FILE_EDITOR)
    thumbnailUrl: str | None = None
    version: str = Field(description="File version number; changes whenever the file is modified.")
    document: dict = Field(description="Root DOCUMENT node; pages (CANVAS) and layers nest under `children`.")
    components: dict[str, dict] = Field(description=_COMPONENTS)
    componentSets: dict[str, dict] = Field(description=_COMPONENT_SETS)
    schemaVersion: float = 0
    styles: dict[str, dict] = Field(description=_STYLES)
    linkAccess: str | None = Field(default=None, description="Share permission level of the file link.")
    mainFileKey: str | None = Field(
        default=None, description="Key of the main file; present when this file is a branch.")
    branches: list[FileBranch] | None = Field(
        default=None, description="Branches of this file; only returned with `branch_data=true`.")


class GetFileResult(ToolResult):
    data: GetFileData | None = None


# get_file_nodes

class FileNodeEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    document: dict = Field(description="The requested node with its subtree under `children`.")
    components: dict[str, dict] = Field(description=_COMPONENTS)
    componentSets: dict[str, dict] = Field(description=_COMPONENT_SETS)
    schemaVersion: float = 0
    styles: dict[str, dict] = Field(description=_STYLES)


class GetFileNodesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    role: str = Field(description=_ROLE)
    lastModified: str
    editorType: str = Field(description=_GET_FILE_EDITOR)
    thumbnailUrl: str
    version: str = Field(description="File version number; changes whenever the file is modified.")
    nodes: dict[str, FileNodeEntry | None] = Field(
        description="Requested node ID -> node entry; null when the node ID doesn't exist in the file.")


class GetFileNodesResult(ToolResult):
    data: GetFileNodesData | None = None


# render_images

class RenderImagesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    err: str | None = Field(default=None, description="Always null on success.")
    images: dict[str, str | None] = Field(
        description="Node ID -> rendered image URL (expires after 30 days); null when that node "
                    "failed to render.")


class RenderImagesResult(ToolResult):
    data: RenderImagesData | None = None


# get_image_fills

class ImageFillsMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    images: dict[str, str] = Field(
        description="imageRef -> image fill download URL (expires within 14 days).")


class GetImageFillsData(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: bool = Field(description="Always false on success.")
    status: float
    meta: ImageFillsMeta


class GetImageFillsResult(ToolResult):
    data: GetImageFillsData | None = None


# get_file_metadata

class FileMetadataUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    handle: str
    img_url: str


class FileMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    folder_name: str | None = Field(default=None, description="Name of the project containing the file.")
    last_touched_at: str = Field(description="UTC ISO 8601 time the file content was last modified.")
    creator: FileMetadataUser
    last_touched_by: FileMetadataUser | None = None
    thumbnail_url: str | None = None
    editorType: str = Field(description=_WIDE_EDITOR)
    role: str | None = Field(default=None, description=_ROLE)
    link_access: str | None = Field(
        default=None, description="Link access policy: view, edit, org_view, org_edit or inherit.")
    url: str | None = None
    version: str | None = Field(
        default=None, description="File version number; changes whenever the file is modified.")


class GetFileMetadataData(BaseModel):
    model_config = ConfigDict(extra="allow")

    file: FileMetadata


class GetFileMetadataResult(ToolResult):
    data: GetFileMetadataData | None = None


# duplicate_file

class DuplicateFileData(BaseModel):
    model_config = ConfigDict(extra="allow")

    file_key: str = Field(description="Key of the newly created standalone file.")
    name: str
    folder_id: str = Field(description="ID of the folder containing the duplicated file.")
    editor_type: str = Field(description="Editor type: figma, figjam, slides, buzz or make.")
    created_at: str


class DuplicateFileResult(ToolResult):
    data: DuplicateFileData | None = None
