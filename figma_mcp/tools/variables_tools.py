"""Variables group: get_local_variables, get_published_variables, update_variables"""

import logging
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.variables import (
    LocalVariablesData,
    LocalVariablesResult,
    PublishedVariablesData,
    PublishedVariablesResult,
    UpdateVariablesData,
    UpdateVariablesResult,
)
from ._helpers import _enterprise_api_err, _err, _handle_request_exc

logger = logging.getLogger("figma-mcp.tools.variables")

_ACTIONS = ("CREATE", "UPDATE", "DELETE")
_MODE_VALUE_KEYS = ("variableId", "modeId", "value")


def _check_actions(name: str, items: list[dict] | None) -> str | None:
    for i, item in enumerate(items or []):
        if not isinstance(item, dict) or item.get("action") not in _ACTIONS:
            return f"{name}[{i}].action must be one of CREATE, UPDATE, DELETE"
    return None


def _check_mode_values(items: list[dict] | None) -> str | None:
    for i, item in enumerate(items or []):
        if not isinstance(item, dict) or any(k not in item for k in _MODE_VALUE_KEYS):
            return f"variableModeValues[{i}] must include variableId, modeId and value"
    return None


def register_variables_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_local_variables",
        description=(
            "Lists the local variables created in a Figma file and the remote variables used in it "
            "(remote ones are referenced by their subscribed_id). Returns `meta.variables` (map of variable id "
            "to id, name, key, variableCollectionId, resolvedType, per-mode valuesByMode, remote, description, "
            "hiddenFromPublishing, scopes, codeSyntax) and `meta.variableCollections` (map of collection id to "
            "id, name, key, modes, defaultModeId, remote, hiddenFromPublishing, variableIds; extended "
            "collections also carry isExtension, parentVariableCollectionId, rootVariableCollectionId and "
            "variableOverrides, and use encoded mode ids like `VariableCollectionId:1:2/3:4`). "
            "Enterprise plan only: Figma requires a Full seat in an Enterprise org (its requirements table lists "
            "any organization member for reads), view access to the file, and the `file_variables:read` scope; "
            "guests cannot use the API. This is the only way to read mode values — get_published_variables "
            "omits modes. Resolve a `boundVariables` variableId from get_file here; the ids feed update_variables."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_local_variables(
        file_key: str = Field(
            description="File to get variables from: a file key or branch key. Get the branch key from "
                        "get_file with the `branch_data` query param."),
    ) -> LocalVariablesResult:
        tlog = ToolLogger(logger, "get_local_variables")
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{file_key}/variables/local",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = LocalVariablesResult(success=True, statusCode=status, data=LocalVariablesData(**data))
                tlog.success()
                return result
            return _enterprise_api_err(LocalVariablesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(LocalVariablesResult, tlog, exc)

    @mcp.tool(
        name="get_published_variables",
        description=(
            "Lists the variables and variable collections published from a Figma file. Returns "
            "`meta.variables` (map of variable id to id, subscribed_id, name, key, variableCollectionId, "
            "resolvedDataType, updatedAt) and `meta.variableCollections` (map of collection id to id, "
            "subscribed_id, name, key, updatedAt). `id` and `key` are stable; `subscribed_id` is the id "
            "subscribing files use and changes every time the variable or collection is modified and published; "
            "`updatedAt` is the last publish time (for a collection it changes whenever any of its variables "
            "changes). Modes and values are not returned — call get_local_variables on the same file for those. "
            "The type field is `resolvedDataType` in Figma's spec but `resolvedType` in its docs; read whichever "
            "is present. Enterprise plan only: Figma requires a Full seat in an Enterprise org (its requirements "
            "table lists any organization member for reads), view access to the file, and the "
            "`file_variables:read` scope; guests cannot use the API."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_published_variables(
        file_key: str = Field(
            description="File to get published variables from. Must be a main file key, not a branch key — "
                        "variables cannot be published from branches."),
    ) -> PublishedVariablesResult:
        tlog = ToolLogger(logger, "get_published_variables")
        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{file_key}/variables/published",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = PublishedVariablesResult(
                    success=True, statusCode=status, data=PublishedVariablesData(**data))
                tlog.success()
                return result
            return _enterprise_api_err(PublishedVariablesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(PublishedVariablesResult, tlog, exc)

    @mcp.tool(
        name="update_variables",
        description=(
            "DESTRUCTIVE — REQUIRES EXPLICIT USER CONFIRMATION BEFORE CALLING. "
            "Bulk creates, updates and deletes variable collections, modes, variables and per-mode variable "
            "values in a Figma file in one request. DELETE actions permanently remove the collection, mode or "
            "variable, and UPDATE actions and variableModeValues overwrite current names, settings and values — "
            "the previous state is not returned and cannot be recovered from this call. "
            "NEVER call this tool autonomously or as part of an automated flow. "
            "You MUST stop, tell the user exactly which collections, modes, variables and values will be "
            "created, changed or deleted, and wait for their explicit written confirmation before proceeding. "
            "Pass at least one of variableCollections, variableModes, variables, variableModeValues. Changes "
            "apply in that order, each array in item order, as one atomic operation: any validation failure "
            "returns 400 and nothing is saved. Temporary ids set on CREATE items (and a collection's "
            "initialModeId — new collections always come with one mode) can be referenced later in the same "
            "request; returns `meta.tempIdToRealId` mapping each temporary id to the real id. Get existing ids "
            "from get_local_variables. Limits: 40 modes per collection, mode names up to 40 characters, 5000 "
            "variables per collection, variable names unique within a collection and without characters like "
            "`.{}`, request body up to 4MB (413 otherwise). Modes and variables cannot be created in extended "
            "collections; remote variables and collections cannot be updated; resolvedType is ignored on UPDATE; "
            "properties settable only at CREATE cannot be changed later; a variable cannot alias itself or form "
            "an alias cycle; a string variable bound to text that uses an organization shared font cannot be "
            "updated (400). Updated variables must be published before other files can use them. Enterprise "
            "plan only: needs a Full seat or admin in an Enterprise org (guests cannot use the API), edit access "
            "to the file, and the `file_variables:write` scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True),
    )
    def update_variables(
        file_key: str = Field(
            description="File to modify variables in: a file key or branch key. Get the branch key from "
                        "get_file with the `branch_data` query param."),
        variableCollections: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Collections to create, update or delete. Each item is one of: "
                "CREATE {action: \"CREATE\", name (required), id? (temporary id), initialModeId? (temporary id "
                "for the default mode), hiddenFromPublishing? (default false), parentVariableCollectionId? "
                "(collection to extend), initialModeIdToParentModeIdMapping? (object mapping inherited parent "
                "modes to initial mode ids on the extended collection; used instead of initialModeId)}; "
                "UPDATE {action: \"UPDATE\", id (required), name?, hiddenFromPublishing?}; "
                "DELETE {action: \"DELETE\", id (required)}. Omit to leave collections unchanged."
            ),
        ),
        variableModes: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Modes to create, update or delete within collections. Each item is one of: "
                "CREATE {action: \"CREATE\", name (required), variableCollectionId (required; may be a temporary "
                "id; not extended collections), id? (temporary id)}; UPDATE {action: \"UPDATE\", id (required), "
                "variableCollectionId (required; not extended collections), name?}; DELETE {action: \"DELETE\", "
                "id (required); not on extended collections unless the parent mode was deleted}. "
                "Omit to leave modes unchanged."
            ),
        ),
        variables: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Variables to create, update or delete. Each item is one of: "
                "CREATE {action: \"CREATE\", name (required), variableCollectionId (required; may be a temporary "
                "id), resolvedType (required; BOOLEAN | FLOAT | STRING | COLOR), id? (temporary id), "
                "description?, hiddenFromPublishing? (default false), scopes? (list of strings), codeSyntax? "
                "({WEB?, ANDROID?, iOS?})}; UPDATE {action: \"UPDATE\", id (required), name?, description?, "
                "hiddenFromPublishing?, scopes?, codeSyntax?}; DELETE {action: \"DELETE\", id (required)}. "
                "Omit to leave variables unchanged."
            ),
        ),
        variableModeValues: list[dict[str, Any]] | None = Field(
            default=None,
            description=(
                "Values to set for a variable in a mode. Each item needs all of: variableId (may be a temporary "
                "id), modeId (a mode in the variable's collection; an original mode id like `1:0` updates the "
                "root collection, an extended mode id like `VariableCollectionId:2:5/2:0` creates or updates an "
                "override), value (boolean | number | string | RGBA {r,g,b,a} with 0-1 channels | VariableAlias "
                "{type: \"VARIABLE_ALIAS\", id} | VariableComposedColor {color, opacity} | null — null removes "
                "an override and only works with extended mode ids). Omit to leave values unchanged."
            ),
        ),
    ) -> UpdateVariablesResult:
        tlog = ToolLogger(logger, "update_variables")

        arrays = {
            "variableCollections": variableCollections,
            "variableModes": variableModes,
            "variables": variables,
            "variableModeValues": variableModeValues,
        }
        body = {k: v for k, v in arrays.items() if v is not None}
        if not body:
            return _err(UpdateVariablesResult, tlog, "VALIDATION_ERROR",
                        "Provide at least one of variableCollections, variableModes, variables, "
                        "variableModeValues", 400)
        problem = (
            _check_actions("variableCollections", variableCollections)
            or _check_actions("variableModes", variableModes)
            or _check_actions("variables", variables)
            or _check_mode_values(variableModeValues)
        )
        if problem:
            return _err(UpdateVariablesResult, tlog, "VALIDATION_ERROR", problem, 400)

        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/files/{file_key}/variables", body=body,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = UpdateVariablesResult(success=True, statusCode=status, data=UpdateVariablesData(**data))
                tlog.success()
                return result
            return _enterprise_api_err(UpdateVariablesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(UpdateVariablesResult, tlog, exc)
