"""Library analytics group: list_library_component_actions, list_library_component_usages,
list_library_style_actions, list_library_style_usages, list_library_variable_actions,
list_library_variable_usages."""

import datetime
import logging
import re
from typing import Literal
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.library_analytics import (
    LibraryComponentActionListData,
    LibraryComponentActionListResult,
    LibraryComponentUsageListData,
    LibraryComponentUsageListResult,
    LibraryStyleActionListData,
    LibraryStyleActionListResult,
    LibraryStyleUsageListData,
    LibraryStyleUsageListResult,
    LibraryVariableActionListData,
    LibraryVariableActionListResult,
    LibraryVariableUsageListData,
    LibraryVariableUsageListResult,
)
from ._helpers import _enterprise_api_err, _err, _handle_request_exc

logger = logging.getLogger("figma-mcp.tools.library_analytics")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_ACCESS = (
    "Enterprise plan only: the signed-in user needs a seat in a Figma Enterprise organization and the "
    "connection needs the `library_analytics:read` scope; otherwise Figma returns 403 (Limited by Figma "
    "plan / Incorrect account type / Invalid scope). Only data the user may access is returned; teams "
    "and files they can't see appear as 'Team not visible' / 'File not visible', and activity outside "
    "the organization is excluded. Data is recalculated daily at 00:00 UTC."
)
_ACTIONS_RANGE = (
    "Time series in descending order (most recent week first), covering up to one year; only weeks "
    "with data are returned."
)
_USAGES_SNAPSHOT = "A snapshot of current usage, not a time series (no date filters)."
_PAGING = (
    "Pages hold up to 1,000 rows: while `next_page` is true, call again with the same arguments and "
    "`cursor` set to the returned `cursor` (absent on the last page)."
)

_FILE_KEY_DESC = (
    "File key of the library to fetch analytics data for — the library file's main key, e.g. "
    "`file_key` from list_team_components, list_team_styles or list_folder_files."
)
_CURSOR_DESC = (
    "Cursor for the page to fetch, taken from the `cursor` of the previous response. "
    "Omit for the first page."
)
_START_DESC = (
    "Earliest week to include, as an ISO 8601 date (YYYY-MM-DD). Rounded back to the nearest start "
    "of a week. Omit to start one year prior."
)
_END_DESC = (
    "Latest week to include, as an ISO 8601 date (YYYY-MM-DD). Rounded forward to the nearest end "
    "of a week. Omit to end at the latest computed week."
)


def _bad_date(value: str | None) -> bool:
    if value is None:
        return False
    if not _DATE_RE.match(value):
        return True
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return True
    return False


def _validate(result_cls, tlog, file_key, start_date=None, end_date=None):
    if not file_key.strip():
        return _err(result_cls, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        if _bad_date(value):
            return _err(result_cls, tlog, "VALIDATION_ERROR",
                        f"{name} must be an ISO 8601 date (YYYY-MM-DD)", 400)
    return None


def _fetch(result_cls, data_cls, tlog, file_key, resource, params):
    endpoint = f"/v1/analytics/libraries/{quote(file_key, safe='')}/{resource}"
    try:
        data, status, retry_after = service.api_request(
            "GET", endpoint, params={k: v for k, v in params.items() if v is not None},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        if 200 <= status < 300:
            result = result_cls(success=True, statusCode=status, data=data_cls(**data))
            tlog.success()
            return result
        return _enterprise_api_err(result_cls, tlog, status, data, retry_after)
    except Exception as exc:
        return _handle_request_exc(result_cls, tlog, exc)


def register_library_analytics_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_library_component_actions",
        description=(
            "Lists weekly insertion and detachment counts for a library's components, grouped by "
            "component (`group_by=component`: component key/name, component set) or by the team using "
            "the library (`group_by=team`: team and workspace name). Returns `rows` (shape depends on "
            "`group_by`), `next_page` and `cursor`. Insertions count every time a library component "
            "was inserted into a document (from the assets panel, by copy-pasting or by duplicating "
            "an instance); detachments count detach events. "
            f"{_ACTIONS_RANGE} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_component_actions(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["component", "team"] = Field(
            description="Dimension to group rows by: `component` (per component) or `team` (per team using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
        start_date: str | None = Field(default=None, description=_START_DESC),
        end_date: str | None = Field(default=None, description=_END_DESC),
    ) -> LibraryComponentActionListResult:
        tlog = ToolLogger(logger, "list_library_component_actions")
        if err := _validate(LibraryComponentActionListResult, tlog, file_key, start_date, end_date):
            return err
        return _fetch(LibraryComponentActionListResult, LibraryComponentActionListData, tlog,
                      file_key, "component/actions",
                      {"group_by": group_by, "cursor": cursor,
                       "start_date": start_date, "end_date": end_date})

    @mcp.tool(
        name="list_library_component_usages",
        description=(
            "Lists how a library's components are currently used, grouped by component "
            "(`group_by=component`: instances, teams using and files using each component; unused "
            "components are excluded) or by file (`group_by=file`: file, team and workspace name with "
            "the count of the library's component instances in that file). Returns `rows` (shape "
            "depends on `group_by`), `next_page` and `cursor`. "
            f"{_USAGES_SNAPSHOT} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_component_usages(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["component", "file"] = Field(
            description="Dimension to group rows by: `component` (per component) or `file` (per file using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
    ) -> LibraryComponentUsageListResult:
        tlog = ToolLogger(logger, "list_library_component_usages")
        if err := _validate(LibraryComponentUsageListResult, tlog, file_key):
            return err
        return _fetch(LibraryComponentUsageListResult, LibraryComponentUsageListData, tlog,
                      file_key, "component/usages", {"group_by": group_by, "cursor": cursor})

    @mcp.tool(
        name="list_library_style_actions",
        description=(
            "Lists weekly insertion and detachment counts for a library's styles, grouped by style "
            "(`group_by=style`: style key, name and type) or by the team using the library "
            "(`group_by=team`: team and workspace name). Returns `rows` (shape depends on `group_by`), "
            "`next_page` and `cursor`. "
            f"{_ACTIONS_RANGE} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_style_actions(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["style", "team"] = Field(
            description="Dimension to group rows by: `style` (per style) or `team` (per team using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
        start_date: str | None = Field(default=None, description=_START_DESC),
        end_date: str | None = Field(default=None, description=_END_DESC),
    ) -> LibraryStyleActionListResult:
        tlog = ToolLogger(logger, "list_library_style_actions")
        if err := _validate(LibraryStyleActionListResult, tlog, file_key, start_date, end_date):
            return err
        return _fetch(LibraryStyleActionListResult, LibraryStyleActionListData, tlog,
                      file_key, "style/actions",
                      {"group_by": group_by, "cursor": cursor,
                       "start_date": start_date, "end_date": end_date})

    @mcp.tool(
        name="list_library_style_usages",
        description=(
            "Lists how a library's styles are currently used, grouped by style (`group_by=style`: "
            "usages, teams using and files using each style) or by file (`group_by=file`: file, team "
            "and workspace name with how many times the library's styles are used in that file). "
            "Returns `rows` (shape depends on `group_by`), `next_page` and `cursor`. "
            f"{_USAGES_SNAPSHOT} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_style_usages(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["style", "file"] = Field(
            description="Dimension to group rows by: `style` (per style) or `file` (per file using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
    ) -> LibraryStyleUsageListResult:
        tlog = ToolLogger(logger, "list_library_style_usages")
        if err := _validate(LibraryStyleUsageListResult, tlog, file_key):
            return err
        return _fetch(LibraryStyleUsageListResult, LibraryStyleUsageListData, tlog,
                      file_key, "style/usages", {"group_by": group_by, "cursor": cursor})

    @mcp.tool(
        name="list_library_variable_actions",
        description=(
            "Lists weekly insertion and detachment counts for a library's variables, grouped by "
            "variable (`group_by=variable`: variable key, name and type plus its collection) or by the "
            "team using the library (`group_by=team`: team and workspace name). Returns `rows` (shape "
            "depends on `group_by`), `next_page` and `cursor`. "
            f"{_ACTIONS_RANGE} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_variable_actions(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["variable", "team"] = Field(
            description="Dimension to group rows by: `variable` (per variable) or `team` (per team using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
        start_date: str | None = Field(default=None, description=_START_DESC),
        end_date: str | None = Field(default=None, description=_END_DESC),
    ) -> LibraryVariableActionListResult:
        tlog = ToolLogger(logger, "list_library_variable_actions")
        if err := _validate(LibraryVariableActionListResult, tlog, file_key, start_date, end_date):
            return err
        return _fetch(LibraryVariableActionListResult, LibraryVariableActionListData, tlog,
                      file_key, "variable/actions",
                      {"group_by": group_by, "cursor": cursor,
                       "start_date": start_date, "end_date": end_date})

    @mcp.tool(
        name="list_library_variable_usages",
        description=(
            "Lists how a library's variables are currently used, grouped by variable "
            "(`group_by=variable`: usages, teams using and files using each variable, with its "
            "collection) or by file (`group_by=file`: file, team and workspace name with how many "
            "times the library's variables are used in that file). Returns `rows` (shape depends on "
            "`group_by`), `next_page` and `cursor`. "
            f"{_USAGES_SNAPSHOT} {_ACCESS} {_PAGING}"
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def list_library_variable_usages(
        file_key: str = Field(description=_FILE_KEY_DESC),
        group_by: Literal["variable", "file"] = Field(
            description="Dimension to group rows by: `variable` (per variable) or `file` (per file using the library)."),
        cursor: str | None = Field(default=None, description=_CURSOR_DESC),
    ) -> LibraryVariableUsageListResult:
        tlog = ToolLogger(logger, "list_library_variable_usages")
        if err := _validate(LibraryVariableUsageListResult, tlog, file_key):
            return err
        return _fetch(LibraryVariableUsageListResult, LibraryVariableUsageListData, tlog,
                      file_key, "variable/usages", {"group_by": group_by, "cursor": cursor})
