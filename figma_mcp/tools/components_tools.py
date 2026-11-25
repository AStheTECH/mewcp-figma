"""Components group: list_team_components, list_file_components, get_component,
list_team_component_sets, list_file_component_sets, get_component_set,
list_team_styles, list_file_styles, get_style."""

import logging
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.components import (
    ComponentData,
    ComponentResult,
    ComponentSetData,
    ComponentSetResult,
    FileComponentListData,
    FileComponentListResult,
    FileComponentSetListData,
    FileComponentSetListResult,
    FileStyleListData,
    FileStyleListResult,
    StyleData,
    StyleResult,
    TeamComponentListData,
    TeamComponentListResult,
    TeamComponentSetListData,
    TeamComponentSetListResult,
    TeamStyleListData,
    TeamStyleListResult,
)
from ._helpers import _err, _handle_request_exc, _upstream_err

logger = logging.getLogger("figma-mcp.tools.components")

_READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)

_TEAM_ID_DESC = (
    "ID of the team whose library to list. Team IDs can't be obtained through the API — the user "
    "copies it from the team page URL in the Figma browser app."
)
_FILE_KEY_DESC = (
    "Key of the library file to list from. Must be a main file key, not a branch key — "
    "it is not possible to publish from branches."
)
_CURSOR_NOTE = (
    "Opaque integer cursor from `meta.cursor.{}` of the previous response; it doesn't correspond "
    "to any ID. Exclusive with `{}`. Omit for the first page."
)


def _not_published(kind: str, get_file_hint: str) -> str:
    return (
        f"No published {kind} was found for this key. Either the key doesn't exist, or the {kind} "
        f"exists only locally and isn't published to a team library — this endpoint only resolves "
        f"published {kind}s. For local, unpublished {kind}s use {get_file_hint}."
    )


def _paging_guard(result_cls, tlog, page_size, after, before, max_page_size=None):
    if after is not None and before is not None:
        return _err(result_cls, tlog, "VALIDATION_ERROR",
                    "`after` and `before` are mutually exclusive — pass only one.", 400)
    if page_size < 1:
        return _err(result_cls, tlog, "VALIDATION_ERROR", "page_size must be at least 1.", 400)
    if max_page_size is not None and page_size > max_page_size:
        return _err(result_cls, tlog, "VALIDATION_ERROR",
                    f"page_size must be at most {max_page_size}.", 400)
    return None


def _blank_guard(result_cls, tlog, name, value):
    if not value or not value.strip():
        return _err(result_cls, tlog, "VALIDATION_ERROR", f"`{name}` must not be empty.", 400)
    return None


def _paging_params(page_size, after, before):
    params = {"page_size": page_size}
    if after is not None:
        params["after"] = after
    if before is not None:
        params["before"] = before
    return params


def _fetch(result_cls, data_cls, tlog, endpoint, params=None, not_found=None):
    try:
        data, status, retry_after = service.api_request(
            "GET", endpoint, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        if 200 <= status < 300:
            result = result_cls(success=True, statusCode=status, data=data_cls(**data))
            tlog.success()
            return result
        explanation = not_found if status == 404 else None
        return _upstream_err(result_cls, tlog, status, data, retry_after, explanation=explanation)
    except Exception as exc:
        return _handle_request_exc(result_cls, tlog, exc)


def register_components_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_team_components",
        description=(
            "Lists the components published to a team's library, one page at a time. Returns "
            "`meta.components` (each with `key`, `file_key`, `node_id`, name, description, "
            "thumbnail, timestamps, last-updating user and `containing_frame`) and `meta.cursor`. "
            "Only library-published components are returned — local or unpublished components "
            "appear only in get_file (full depth). To page, pass `meta.cursor.after` back as "
            "`after` (or `meta.cursor.before` as `before`); `meta.cursor` is `{}` when there are "
            "no results. Each `key` feeds get_component; `file_key` + `node_id` feed "
            "get_file_nodes and render_images."
        ),
        annotations=_READ,
    )
    def list_team_components(
        team_id: str = Field(description=_TEAM_ID_DESC),
        page_size: int = Field(default=30, description="Items per page, 1–1000. Defaults to 30."),
        after: int | None = Field(default=None, description=_CURSOR_NOTE.format("after", "before")),
        before: int | None = Field(default=None, description=_CURSOR_NOTE.format("before", "after")),
    ) -> TeamComponentListResult:
        tlog = ToolLogger(logger, "list_team_components")
        if err := _blank_guard(TeamComponentListResult, tlog, "team_id", team_id):
            return err
        if err := _paging_guard(TeamComponentListResult, tlog, page_size, after, before, 1000):
            return err
        return _fetch(TeamComponentListResult, TeamComponentListData, tlog,
                      f"/v1/teams/{quote(team_id.strip(), safe='')}/components",
                      params=_paging_params(page_size, after, before))

    @mcp.tool(
        name="list_file_components",
        description=(
            "Lists the components published from a library file. Returns `meta.components` (each "
            "with `key`, `file_key`, `node_id`, name, description, thumbnail, timestamps, "
            "last-updating user and `containing_frame`). Only library-published components are "
            "returned — a file whose components aren't published returns an empty list; use "
            "get_file (full depth) for local, unpublished components. `file_key` must be a main "
            "file key, not a branch key. Each `key` feeds get_component; `file_key` + `node_id` "
            "feed get_file_nodes and render_images."
        ),
        annotations=_READ,
    )
    def list_file_components(
        file_key: str = Field(description=_FILE_KEY_DESC),
    ) -> FileComponentListResult:
        tlog = ToolLogger(logger, "list_file_components")
        if err := _blank_guard(FileComponentListResult, tlog, "file_key", file_key):
            return err
        return _fetch(FileComponentListResult, FileComponentListData, tlog,
                      f"/v1/files/{quote(file_key.strip(), safe='')}/components")

    @mcp.tool(
        name="get_component",
        description=(
            "Gets metadata for one published component by its key. Returns `meta` with `key`, "
            "`file_key`, `node_id`, name, description, thumbnail, timestamps, last-updating user "
            "and `containing_frame`. Only components published to a team library resolve: a 404 "
            "means the key doesn't exist or the component isn't published (keys of local "
            "components from get_file also 404 here); use get_file (full depth) for local "
            "components. Keys come from list_team_components / list_file_components, or the "
            "`components` map in get_file."
        ),
        annotations=_READ,
    )
    def get_component(
        key: str = Field(description="Unique key of the published component (not its node ID)."),
    ) -> ComponentResult:
        tlog = ToolLogger(logger, "get_component")
        if err := _blank_guard(ComponentResult, tlog, "key", key):
            return err
        return _fetch(ComponentResult, ComponentData, tlog,
                      f"/v1/components/{quote(key.strip(), safe='')}",
                      not_found=_not_published("component", "get_file at full depth (no `depth` limit)"))

    @mcp.tool(
        name="list_team_component_sets",
        description=(
            "Lists the component sets (variant groups) published to a team's library, one page at "
            "a time. Returns `meta.component_sets` (each with `key`, `file_key`, `node_id`, name, "
            "description, thumbnail, timestamps, last-updating user and `containing_frame`) and "
            "`meta.cursor`. Only library-published component sets are returned — local or "
            "unpublished ones appear only in get_file (full depth). To page, pass "
            "`meta.cursor.after` back as `after` (or `meta.cursor.before` as `before`); "
            "`meta.cursor` is `{}` when there are no results. Each `key` feeds get_component_set; "
            "`file_key` + `node_id` feed get_file_nodes and render_images."
        ),
        annotations=_READ,
    )
    def list_team_component_sets(
        team_id: str = Field(description=_TEAM_ID_DESC),
        page_size: int = Field(default=30, description="Items per page. Defaults to 30."),
        after: int | None = Field(default=None, description=_CURSOR_NOTE.format("after", "before")),
        before: int | None = Field(default=None, description=_CURSOR_NOTE.format("before", "after")),
    ) -> TeamComponentSetListResult:
        tlog = ToolLogger(logger, "list_team_component_sets")
        if err := _blank_guard(TeamComponentSetListResult, tlog, "team_id", team_id):
            return err
        if err := _paging_guard(TeamComponentSetListResult, tlog, page_size, after, before):
            return err
        return _fetch(TeamComponentSetListResult, TeamComponentSetListData, tlog,
                      f"/v1/teams/{quote(team_id.strip(), safe='')}/component_sets",
                      params=_paging_params(page_size, after, before))

    @mcp.tool(
        name="list_file_component_sets",
        description=(
            "Lists the component sets (variant groups) published from a library file. Returns "
            "`meta.component_sets` (each with `key`, `file_key`, `node_id`, name, description, "
            "thumbnail, timestamps, last-updating user and `containing_frame`). Only "
            "library-published component sets are returned — a file whose component sets aren't "
            "published returns an empty list; use get_file (full depth) for local, unpublished "
            "ones. `file_key` must be a main file key, not a branch key. Each `key` feeds "
            "get_component_set; `file_key` + `node_id` feed get_file_nodes and render_images."
        ),
        annotations=_READ,
    )
    def list_file_component_sets(
        file_key: str = Field(description=_FILE_KEY_DESC),
    ) -> FileComponentSetListResult:
        tlog = ToolLogger(logger, "list_file_component_sets")
        if err := _blank_guard(FileComponentSetListResult, tlog, "file_key", file_key):
            return err
        return _fetch(FileComponentSetListResult, FileComponentSetListData, tlog,
                      f"/v1/files/{quote(file_key.strip(), safe='')}/component_sets")

    @mcp.tool(
        name="get_component_set",
        description=(
            "Gets metadata for one published component set by its key. Returns `meta` with `key`, "
            "`file_key`, `node_id`, name, description, thumbnail, timestamps, last-updating user "
            "and `containing_frame`. Only component sets published to a team library resolve: a "
            "404 means the key doesn't exist or the component set isn't published; use get_file "
            "(full depth) for local component sets. Keys come from list_team_component_sets / "
            "list_file_component_sets, or the `componentSets` map in get_file."
        ),
        annotations=_READ,
    )
    def get_component_set(
        key: str = Field(description="Unique key of the published component set (not its node ID)."),
    ) -> ComponentSetResult:
        tlog = ToolLogger(logger, "get_component_set")
        if err := _blank_guard(ComponentSetResult, tlog, "key", key):
            return err
        return _fetch(ComponentSetResult, ComponentSetData, tlog,
                      f"/v1/component_sets/{quote(key.strip(), safe='')}",
                      not_found=_not_published("component set", "get_file at full depth (no `depth` limit)"))

    @mcp.tool(
        name="list_team_styles",
        description=(
            "Lists the styles published to a team's library, one page at a time. Returns "
            "`meta.styles` (each with `key`, `file_key`, `node_id`, `style_type` FILL/TEXT/EFFECT/"
            "GRID, name, description, thumbnail, timestamps, last-updating user and "
            "`sort_position`) and `meta.cursor`. Only library-published styles are returned — "
            "local styles appear only in get_file. To page, pass `meta.cursor.after` back as "
            "`after` (or `meta.cursor.before` as `before`); `meta.cursor` is `{}` when there are "
            "no results. Each `key` feeds get_style; `file_key` + `node_id` feed get_file_nodes "
            "and render_images."
        ),
        annotations=_READ,
    )
    def list_team_styles(
        team_id: str = Field(description=_TEAM_ID_DESC),
        page_size: int = Field(default=30, description="Items per page. Defaults to 30."),
        after: int | None = Field(default=None, description=_CURSOR_NOTE.format("after", "before")),
        before: int | None = Field(default=None, description=_CURSOR_NOTE.format("before", "after")),
    ) -> TeamStyleListResult:
        tlog = ToolLogger(logger, "list_team_styles")
        if err := _blank_guard(TeamStyleListResult, tlog, "team_id", team_id):
            return err
        if err := _paging_guard(TeamStyleListResult, tlog, page_size, after, before):
            return err
        return _fetch(TeamStyleListResult, TeamStyleListData, tlog,
                      f"/v1/teams/{quote(team_id.strip(), safe='')}/styles",
                      params=_paging_params(page_size, after, before))

    @mcp.tool(
        name="list_file_styles",
        description=(
            "Lists the styles published from a library file. Returns `meta.styles` (each with "
            "`key`, `file_key`, `node_id`, `style_type` FILL/TEXT/EFFECT/GRID, name, description, "
            "thumbnail, timestamps, last-updating user and `sort_position`). Only library-published "
            "styles are returned; use get_file for local styles. `file_key` must be a main file "
            "key, not a branch key. Each `key` feeds get_style; `file_key` + `node_id` feed "
            "get_file_nodes and render_images."
        ),
        annotations=_READ,
    )
    def list_file_styles(
        file_key: str = Field(description=_FILE_KEY_DESC),
    ) -> FileStyleListResult:
        tlog = ToolLogger(logger, "list_file_styles")
        if err := _blank_guard(FileStyleListResult, tlog, "file_key", file_key):
            return err
        return _fetch(FileStyleListResult, FileStyleListData, tlog,
                      f"/v1/files/{quote(file_key.strip(), safe='')}/styles")

    @mcp.tool(
        name="get_style",
        description=(
            "Gets metadata for one published style by its key. Returns `meta` with `key`, "
            "`file_key`, `node_id`, `style_type` FILL/TEXT/EFFECT/GRID, name, description, "
            "thumbnail, timestamps, last-updating user and `sort_position`. Only styles published "
            "to a team library are covered by this endpoint; use get_file for local styles. Keys "
            "come from list_team_styles / list_file_styles, or the `styles` map in get_file."
        ),
        annotations=_READ,
    )
    def get_style(
        key: str = Field(description="Unique key of the published style (not its node ID)."),
    ) -> StyleResult:
        tlog = ToolLogger(logger, "get_style")
        if err := _blank_guard(StyleResult, tlog, "key", key):
            return err
        return _fetch(StyleResult, StyleData, tlog,
                      f"/v1/styles/{quote(key.strip(), safe='')}",
                      not_found=_not_published("style", "get_file"))
