"""Dev resources group: list_dev_resources, create_dev_resources, update_dev_resources, delete_dev_resource."""

import logging
from typing import Any
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.dev_resources import (
    CreateDevResourcesData,
    CreateDevResourcesResult,
    DeleteDevResourceData,
    DeleteDevResourceResult,
    DevResourceListData,
    DevResourceListResult,
    UpdateDevResourcesData,
    UpdateDevResourcesResult,
)
from ._helpers import _err, _handle_request_exc, _upstream_err

logger = logging.getLogger("figma-mcp.tools.dev_resources")

_NOT_FOUND_EXPLANATION = (
    "Figma could not find the {what}. If the file exists and opens in Figma, the likely cause is "
    "that dev resources (a Dev Mode feature) aren't available for this file's plan or the "
    "signed-in user's seat (unconfirmed). Also check that `file_key` is a main file key, not a "
    "branch key."
)

_DEV_MODE_NOTE = (
    "An `errors` entry of \"File not found\" for a file that exists most likely means dev "
    "resources (a Dev Mode feature) aren't available for that file's plan or the user's seat."
)

_CREATE_KEYS = ("name", "url", "file_key", "node_id")


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def register_dev_resources_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_dev_resources",
        description=(
            "Lists the dev resources (developer links attached to nodes and shown in Figma Dev "
            "Mode) in a file, optionally only those on given nodes. Returns each resource's id, "
            "name, url, file_key and node_id; the id feeds `update_dev_resources` and "
            "`delete_dev_resource`. `file_key` must be a main file key, not a branch key. A 404 "
            "\"File not found\" on a file that exists most likely means dev resources aren't "
            "available for that file's plan or the user's seat."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    def list_dev_resources(
        file_key: str = Field(
            description="Key of the file to get dev resources from (from a file URL or `list_folder_files`). Must be a main file key, not a branch key."
        ),
        node_ids: str | None = Field(
            default=None,
            description="Comma-separated node IDs (from `get_file` / `get_file_nodes`), e.g. '1:2,3:4'. Only dev resources attached to these nodes are returned. Omit to return all dev resources in the file.",
        ),
    ) -> DevResourceListResult:
        tlog = ToolLogger(logger, "list_dev_resources")

        if not _is_text(file_key):
            return _err(DevResourceListResult, tlog, "VALIDATION_ERROR",
                        "file_key must be a non-empty string", 400)

        params = {"node_ids": node_ids} if node_ids else None
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}/dev_resources", params=params,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return DevResourceListResult(success=True, statusCode=status,
                                             data=DevResourceListData(**data))
            explanation = _NOT_FOUND_EXPLANATION.format(what="file") if status == 404 else None
            return _upstream_err(DevResourceListResult, tlog, status, data, retry_after,
                                 explanation=explanation)
        except Exception as exc:
            return _handle_request_exc(DevResourceListResult, tlog, exc)

    @mcp.tool(
        name="create_dev_resources",
        description=(
            "Creates dev resources (developer links shown in Figma Dev Mode) on nodes across one "
            "or more files in a single call; they are available immediately, with no publishing "
            "step. Returns the created resources in `links_created` and any that failed in "
            "`errors` (with `file_key` / `node_id` possibly null). The call can succeed with a "
            "200 while some or all items fail, so always check `errors`: failures include a "
            "file_key that can't be found, a node that already has the maximum of 10 dev "
            "resources, and a node that already has a dev resource with the same url. "
            + _DEV_MODE_NOTE
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def create_dev_resources(
        dev_resources: list[dict[str, Any]] = Field(
            description=(
                "Dev resources to create. Each item is an object with keys: name (str, the "
                "dev resource's name), url (str, the link), file_key (str, file the resource "
                "belongs to; must be a main file key, not a branch key) and node_id (str, the "
                "node to attach it to, from `get_file` / `get_file_nodes`)."
            )
        ),
    ) -> CreateDevResourcesResult:
        tlog = ToolLogger(logger, "create_dev_resources")

        if not dev_resources:
            return _err(CreateDevResourcesResult, tlog, "VALIDATION_ERROR",
                        "dev_resources must contain at least one item", 400)
        for i, item in enumerate(dev_resources):
            if not isinstance(item, dict):
                return _err(CreateDevResourcesResult, tlog, "VALIDATION_ERROR",
                            f"dev_resources[{i}] must be an object", 400)
            missing = [k for k in _CREATE_KEYS if not _is_text(item.get(k))]
            if missing:
                return _err(CreateDevResourcesResult, tlog, "VALIDATION_ERROR",
                            f"dev_resources[{i}] is missing non-empty string value(s) for: "
                            f"{', '.join(missing)}", 400)

        try:
            data, status, retry_after = service.api_request(
                "POST", "/v1/dev_resources", body={"dev_resources": dev_resources},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return CreateDevResourcesResult(success=True, statusCode=status,
                                                data=CreateDevResourcesData(**data))
            return _upstream_err(CreateDevResourcesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CreateDevResourcesResult, tlog, exc)

    @mcp.tool(
        name="update_dev_resources",
        description=(
            "DESTRUCTIVE — REQUIRES EXPLICIT USER CONFIRMATION BEFORE CALLING. "
            "Overwrites the name and/or url of every listed dev resource, across one or more "
            "files, in a single call; changes are visible in Dev Mode immediately. The file and "
            "node a dev resource is attached to cannot be changed. The previous names and urls "
            "are not returned and cannot be recovered from this call (read them first with "
            "`list_dev_resources` if a record is needed). "
            "NEVER call this tool autonomously or as part of an automated flow. "
            "You MUST stop, tell the user exactly how many dev resources will be affected and "
            "what will change, and wait for their explicit written confirmation before "
            "proceeding. Returns the updated resources in `links_updated` and any that failed in "
            "`errors`; the call can succeed with a 200 while some or all items fail, so always "
            "check `errors`. " + _DEV_MODE_NOTE
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
    )
    def update_dev_resources(
        dev_resources: list[dict[str, Any]] = Field(
            description=(
                "Dev resources to update. Each item is an object with key id (str, the dev "
                "resource's id from `list_dev_resources` or `create_dev_resources`) and optional "
                "keys name (str, new name) and url (str, new link). The file and node cannot be "
                "changed."
            )
        ),
    ) -> UpdateDevResourcesResult:
        tlog = ToolLogger(logger, "update_dev_resources")

        if not dev_resources:
            return _err(UpdateDevResourcesResult, tlog, "VALIDATION_ERROR",
                        "dev_resources must contain at least one item", 400)
        for i, item in enumerate(dev_resources):
            if not isinstance(item, dict):
                return _err(UpdateDevResourcesResult, tlog, "VALIDATION_ERROR",
                            f"dev_resources[{i}] must be an object", 400)
            if not _is_text(item.get("id")):
                return _err(UpdateDevResourcesResult, tlog, "VALIDATION_ERROR",
                            f"dev_resources[{i}].id must be a non-empty string", 400)
            for key in ("name", "url"):
                if key in item and not _is_text(item[key]):
                    return _err(UpdateDevResourcesResult, tlog, "VALIDATION_ERROR",
                                f"dev_resources[{i}].{key} must be a non-empty string", 400)

        try:
            data, status, retry_after = service.api_request(
                "PUT", "/v1/dev_resources", body={"dev_resources": dev_resources},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return UpdateDevResourcesResult(success=True, statusCode=status,
                                                data=UpdateDevResourcesData(**data))
            return _upstream_err(UpdateDevResourcesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(UpdateDevResourcesResult, tlog, exc)

    @mcp.tool(
        name="delete_dev_resource",
        description=(
            "DESTRUCTIVE — REQUIRES EXPLICIT USER CONFIRMATION BEFORE CALLING. "
            "Permanently deletes one dev resource (a developer link shown in Figma Dev Mode) "
            "from its node in a file. "
            "This action is irreversible: the link, its name and its id are removed with no way "
            "to recover them. "
            "NEVER call this tool autonomously or as part of an automated flow. "
            "You MUST stop, tell the user exactly which dev resource will be deleted and that it "
            "is permanent, and wait for their explicit written confirmation before proceeding. "
            "Figma returns no body; on success the result echoes `file_key` and "
            "`dev_resource_id`. A 404 means the dev resource or file was not found; \"File not "
            "found\" on a file that exists most likely means dev resources aren't available for "
            "that file's plan or the user's seat."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
    )
    def delete_dev_resource(
        file_key: str = Field(
            description="Key of the file the dev resource belongs to (`dev_resources[].file_key` from `list_dev_resources`). Must be a main file key, not a branch key."
        ),
        dev_resource_id: str = Field(
            description="ID of the dev resource to delete (`dev_resources[].id` from `list_dev_resources`)."
        ),
    ) -> DeleteDevResourceResult:
        tlog = ToolLogger(logger, "delete_dev_resource")

        if not _is_text(file_key):
            return _err(DeleteDevResourceResult, tlog, "VALIDATION_ERROR",
                        "file_key must be a non-empty string", 400)
        if not _is_text(dev_resource_id):
            return _err(DeleteDevResourceResult, tlog, "VALIDATION_ERROR",
                        "dev_resource_id must be a non-empty string", 400)

        try:
            data, status, retry_after = service.api_request(
                "DELETE",
                f"/v1/files/{quote(file_key, safe='')}/dev_resources/"
                f"{quote(dev_resource_id, safe='')}",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return DeleteDevResourceResult(
                    success=True, statusCode=status,
                    data=DeleteDevResourceData(file_key=file_key, dev_resource_id=dev_resource_id),
                )
            explanation = (_NOT_FOUND_EXPLANATION.format(what="dev resource or file")
                           if status == 404 else None)
            return _upstream_err(DeleteDevResourceResult, tlog, status, data, retry_after,
                                 explanation=explanation)
        except Exception as exc:
            return _handle_request_exc(DeleteDevResourceResult, tlog, exc)
