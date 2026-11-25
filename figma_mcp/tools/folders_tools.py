"""Folders group: create_folder, list_team_folders, list_subfolders, list_folder_files, get_folder_metadata"""

import logging
from typing import Literal
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.folders import (
    CreateFolderData,
    CreateFolderResult,
    FolderFileListData,
    FolderFileListResult,
    FolderMetadataData,
    FolderMetadataResult,
    SubfolderListData,
    SubfolderListResult,
    TeamFolderListData,
    TeamFolderListResult,
)
from ._helpers import _err, _handle_request_exc, _private_app_err, _upstream_err

logger = logging.getLogger("figma-mcp.tools.folders")

_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

_OWN_ORG = "Use only for folders and files in your own Figma organization."


def register_folders_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="create_folder",
        description=(
            "Creates a new top-level folder in a team and returns the created folder (id, name, "
            "parent_folder_id = null, sharing_audience_control, created_at). Works only when Figma "
            "is connected through a private OAuth app on an Enterprise plan (folders:write scope); "
            "the team must belong to that Enterprise plan and the signed-in user must be allowed to "
            "create folders in it, otherwise Figma returns a generic 403. Workspace audiences "
            "(workspace_view, workspace_edit) require the team to belong to a workspace. The "
            "returned id is the folder_id for list_folder_files, list_subfolders and get_folder_metadata."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def create_folder(
        team_id: str = Field(description=(
            "The ID of the team in which to create the folder: the number after /team/ in the "
            "team page URL in the Figma file browser, or the id returned by create_team."
        )),
        name: str = Field(description="The name of the folder."),
        sharing_audience_control: Literal[
            "plan_view", "plan_edit", "invite_only", "workspace_view", "workspace_edit"
        ] = Field(description=(
            "The audience that can access the folder: plan_view, plan_edit, invite_only, "
            "workspace_view or workspace_edit. Workspace audiences require the specified team to "
            "belong to a workspace."
        )),
    ) -> CreateFolderResult:
        tlog = ToolLogger(logger, "create_folder")
        if not team_id.strip():
            return _err(CreateFolderResult, tlog, "VALIDATION_ERROR", "team_id must not be empty", 400)
        if not name.strip():
            return _err(CreateFolderResult, tlog, "VALIDATION_ERROR", "name must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/teams/{quote(team_id.strip(), safe='')}/folders",
                body={"name": name, "sharing_audience_control": sharing_audience_control},
                timeout=_TIMEOUT,
            )
            if 200 <= status < 300:
                tlog.success()
                return CreateFolderResult(success=True, statusCode=status, data=CreateFolderData(**data))
            return _private_app_err(CreateFolderResult, tlog, "create_folder", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CreateFolderResult, tlog, exc)

    @mcp.tool(
        name="list_team_folders",
        description=(
            "Lists the top-level folders (previously called \"projects\") in a team. Returns the "
            "team's name and its folders (id, name, parent_folder_id = null; sharing_audience_control "
            "and created_at may be absent). Only folders visible to the signed-in user are returned; "
            "no paging. Requires the folders:read scope, which Figma never grants to public OAuth "
            "apps — a public-app connection gets a generic 403. team_id cannot be looked up through "
            "the API: take it from the team page URL or from create_team. Each folders[].id is the "
            f"folder_id for list_subfolders, list_folder_files and get_folder_metadata. {_OWN_ORG}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_team_folders(
        team_id: str = Field(description=(
            "ID of the team to list folders from. Not obtainable programmatically: it is the number "
            "after /team/ in the team page URL in the Figma file browser (e.g. 1535685101263221741 in "
            "https://www.figma.com/files/181033233908053158/team/1535685101263221741), or the id "
            "returned by create_team."
        )),
    ) -> TeamFolderListResult:
        tlog = ToolLogger(logger, "list_team_folders")
        if not team_id.strip():
            return _err(TeamFolderListResult, tlog, "VALIDATION_ERROR", "team_id must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v2/teams/{quote(team_id.strip(), safe='')}/folders", timeout=_TIMEOUT,
            )
            if 200 <= status < 300:
                tlog.success()
                return TeamFolderListResult(success=True, statusCode=status, data=TeamFolderListData(**data))
            return _private_app_err(TeamFolderListResult, tlog, "list_team_folders", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(TeamFolderListResult, tlog, exc)

    @mcp.tool(
        name="list_subfolders",
        description=(
            "Lists the direct subfolders of a folder. Returns the parent folder's name and its "
            "subfolders (id, name, parent_folder_id; sharing_audience_control and created_at may be "
            "absent). Direct children only — call again on each returned id to walk deeper. Only "
            "folders visible to the signed-in user are returned. Requires the folders:read scope, "
            "which Figma never grants to public OAuth apps — a public-app connection gets a generic "
            "403. folder_id comes from list_team_folders, create_folder or a previous call to this "
            f"tool. {_OWN_ORG}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_subfolders(
        folder_id: str = Field(description=(
            "ID of the parent folder to list subfolders from (folders[].id from list_team_folders "
            "or list_subfolders, or id from create_folder)."
        )),
    ) -> SubfolderListResult:
        tlog = ToolLogger(logger, "list_subfolders")
        if not folder_id.strip():
            return _err(SubfolderListResult, tlog, "VALIDATION_ERROR", "folder_id must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v2/folders/{quote(folder_id.strip(), safe='')}/folders", timeout=_TIMEOUT,
            )
            if 200 <= status < 300:
                tlog.success()
                return SubfolderListResult(success=True, statusCode=status, data=SubfolderListData(**data))
            return _private_app_err(SubfolderListResult, tlog, "list_subfolders", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(SubfolderListResult, tlog, exc)

    @mcp.tool(
        name="list_folder_files",
        description=(
            "Lists the files directly in a folder. Returns the folder's name and its files (key, "
            "name, thumbnail_url, last_modified, plus branches when branch_data is true and the file "
            "has branches). Files in subfolders are not included — use list_subfolders to walk the "
            "tree. Only files visible to the signed-in user are returned. Requires the folders:read "
            "scope, which Figma never grants to public OAuth apps — a public-app connection gets a "
            "generic 403. Each files[].key (and branches[].key) is the file_key for the file, "
            f"comment, version and variable tools. {_OWN_ORG}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_folder_files(
        folder_id: str = Field(description=(
            "ID of the folder to list files from (folders[].id from list_team_folders or "
            "list_subfolders, or id from create_folder)."
        )),
        branch_data: bool = Field(default=False, description=(
            "Returns branch metadata in the response for each main file with a branch inside the "
            "folder. Defaults to false (no branches)."
        )),
    ) -> FolderFileListResult:
        tlog = ToolLogger(logger, "list_folder_files")
        if not folder_id.strip():
            return _err(FolderFileListResult, tlog, "VALIDATION_ERROR", "folder_id must not be empty", 400)
        params = {"branch_data": "true"} if branch_data else None
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v2/folders/{quote(folder_id.strip(), safe='')}/files",
                params=params, timeout=_TIMEOUT,
            )
            if 200 <= status < 300:
                tlog.success()
                return FolderFileListResult(success=True, statusCode=status, data=FolderFileListData(**data))
            return _private_app_err(FolderFileListResult, tlog, "list_folder_files", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(FolderFileListResult, tlog, exc)

    @mcp.tool(
        name="get_folder_metadata",
        description=(
            "Gets a folder's metadata without listing its files. Returns id, name, thumbnail_url "
            "(null when the folder has no files), file_count, updated_at and created_at. Requires the "
            "folder_metadata:read scope and works with any OAuth app, including public ones — the "
            "only folders tool a public-app connection can use, so there the user must supply "
            "folder_id; otherwise it comes from list_team_folders, list_subfolders or create_folder. "
            f"{_OWN_ORG}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_folder_metadata(
        folder_id: str = Field(description=(
            "ID of the folder to get metadata for (folders[].id from list_team_folders or "
            "list_subfolders, id from create_folder, or supplied by the user)."
        )),
    ) -> FolderMetadataResult:
        tlog = ToolLogger(logger, "get_folder_metadata")
        if not folder_id.strip():
            return _err(FolderMetadataResult, tlog, "VALIDATION_ERROR", "folder_id must not be empty", 400)
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v2/folders/{quote(folder_id.strip(), safe='')}/meta", timeout=_TIMEOUT,
            )
            if 200 <= status < 300:
                tlog.success()
                return FolderMetadataResult(success=True, statusCode=status, data=FolderMetadataData(**data))
            return _upstream_err(FolderMetadataResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(FolderMetadataResult, tlog, exc)
