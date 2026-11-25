"""Teams group: get_team, create_team, invite_team_members"""

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
from ..schemas.teams import (
    CreateTeamData,
    CreateTeamResult,
    GetTeamData,
    GetTeamResult,
    InviteTeamMembersData,
    InviteTeamMembersResult,
)
from ._helpers import _err, _handle_request_exc, _private_app_err

logger = logging.getLogger("figma-mcp.tools.teams")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WORKSPACE_AUDIENCES = ("workspace_view", "workspace_edit")


def register_teams_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_team",
        description=(
            "Returns a Figma team's metadata: id, name, description, sharing_audience_control, "
            "org_discoverability (null unless the team is invite_only), workspace_id, owner_user_id "
            "and created_at. Works only when Figma is connected through a private OAuth app on a "
            "Professional, Organization or Enterprise plan (plan access tokens: Organization or "
            "Enterprise only); public OAuth app connections are refused with 401/403. Team IDs "
            "cannot be listed through the API — take the ID from the team page URL in the Figma "
            "browser app, or use the `id` returned by `create_team`."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_team(
        team_id: str = Field(
            description="The ID of the team, from the team page URL in Figma or the `id` "
                        "returned by `create_team`."),
    ) -> GetTeamResult:
        tlog = ToolLogger(logger, "get_team")

        if not team_id.strip():
            return _err(GetTeamResult, tlog, "VALIDATION_ERROR", "team_id must not be empty", 400)

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/teams/{quote(team_id.strip(), safe='')}",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return GetTeamResult(success=True, statusCode=status, data=GetTeamData(**data))
            return _private_app_err(GetTeamResult, tlog, "get_team", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(GetTeamResult, tlog, exc)

    @mcp.tool(
        name="create_team",
        description=(
            "Creates a team in the Enterprise plan the connection's private OAuth app belongs to, "
            "making the signed-in user the team owner, and returns the created team (same fields as "
            "`get_team`, including the new `id`). Works only when Figma is connected through a "
            "private OAuth app on an Enterprise plan; public OAuth app connections are refused with "
            "a generic 403. The request is subject to the same team-creation controls and "
            "permissions as creating a team in Figma. `org_discoverability` is required when "
            "`sharing_audience_control` is invite_only and must be omitted otherwise; `workspace_id` "
            "is required for workspace_view and workspace_edit (read it from `get_team` on an "
            "existing team in that workspace)."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def create_team(
        name: str = Field(description="The name of the team."),
        sharing_audience_control: Literal[
            "org_view", "org_edit", "invite_only", "workspace_view", "workspace_edit"
        ] = Field(
            description="The audience that can discover and join the team: org_view, org_edit, "
                        "invite_only, workspace_view or workspace_edit. Workspace audiences need "
                        "`workspace_id`; invite_only needs `org_discoverability`."),
        description: str | None = Field(
            default=None, description="A description of the team. Omit to leave it unset."),
        org_discoverability: Literal["hidden", "discoverable"] | None = Field(
            default=None,
            description="Whether organization members can discover the invite-only team: hidden or "
                        "discoverable. Needed when sharing_audience_control is invite_only; leave "
                        "it out for every other audience."),
        workspace_id: str | None = Field(
            default=None,
            description="The workspace to create the team in. Needed for workspace_view and "
                        "workspace_edit; omit otherwise."),
    ) -> CreateTeamResult:
        tlog = ToolLogger(logger, "create_team")

        if not name.strip():
            return _err(CreateTeamResult, tlog, "VALIDATION_ERROR", "name must not be empty", 400)
        if sharing_audience_control == "invite_only" and org_discoverability is None:
            return _err(CreateTeamResult, tlog, "VALIDATION_ERROR",
                        "org_discoverability (hidden or discoverable) is required when "
                        "sharing_audience_control is invite_only", 400)
        if sharing_audience_control != "invite_only" and org_discoverability is not None:
            return _err(CreateTeamResult, tlog, "VALIDATION_ERROR",
                        "org_discoverability is only accepted when sharing_audience_control is "
                        "invite_only — omit it", 400)
        if sharing_audience_control in _WORKSPACE_AUDIENCES and not (workspace_id or "").strip():
            return _err(CreateTeamResult, tlog, "VALIDATION_ERROR",
                        f"workspace_id is required when sharing_audience_control is "
                        f"{sharing_audience_control}", 400)

        body: dict = {"name": name, "sharing_audience_control": sharing_audience_control}
        if description is not None:
            body["description"] = description
        if org_discoverability is not None:
            body["org_discoverability"] = org_discoverability
        if workspace_id is not None:
            body["workspace_id"] = workspace_id

        try:
            data, status, retry_after = service.api_request(
                "POST", "/v1/teams", body=body,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return CreateTeamResult(success=True, statusCode=status, data=CreateTeamData(**data))
            return _private_app_err(CreateTeamResult, tlog, "create_team", status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(CreateTeamResult, tlog, exc)

    @mcp.tool(
        name="invite_team_members",
        description=(
            "Invites 1–99 email addresses to a Figma team with the given role and returns `invites` "
            "(addresses invited, including existing members) and `errors` (addresses that could "
            "not be invited, each with a reason). Each address is processed independently, so a "
            "successful call can still carry failures in `errors`, even when `invites` is empty. "
            "Existing members are never downgraded, and an "
            "invitation can still need organization-admin approval before the user joins. Works "
            "only when Figma is connected through a private OAuth app on an Enterprise plan, for a "
            "team in that plan, and the signed-in user must be allowed to grant the role; public "
            "OAuth app connections are refused with a 403 or a 404 'endpoint is not enabled'. Team "
            "IDs cannot be listed through the API — use the team page URL in Figma or the `id` "
            "from `create_team`."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def invite_team_members(
        team_id: str = Field(
            description="The ID of the team to invite users to, from the team page URL in Figma "
                        "or the `id` returned by `create_team`."),
        emails: list[str] = Field(description="The email addresses to invite (1–99 addresses)."),
        role: Literal["viewer", "editor", "admin"] = Field(
            description="The team role to grant each invited address: viewer, editor or admin. "
                        "Existing members with a higher role keep it."),
    ) -> InviteTeamMembersResult:
        tlog = ToolLogger(logger, "invite_team_members")

        if not team_id.strip():
            return _err(InviteTeamMembersResult, tlog, "VALIDATION_ERROR",
                        "team_id must not be empty", 400)
        if not 1 <= len(emails) <= 99:
            return _err(InviteTeamMembersResult, tlog, "VALIDATION_ERROR",
                        f"emails must contain 1–99 addresses (got {len(emails)})", 400)
        bad = [e for e in emails if not _EMAIL_RE.match(e.strip())]
        if bad:
            return _err(InviteTeamMembersResult, tlog, "VALIDATION_ERROR",
                        f"{len(bad)} value(s) in emails are not valid email addresses", 400)

        body = {"emails": [e.strip() for e in emails], "role": role}

        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/teams/{quote(team_id.strip(), safe='')}/invites", body=body,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                result = InviteTeamMembersResult(
                    success=True, statusCode=status, data=InviteTeamMembersData(**data))
                if result.data.errors:
                    logger.warning("tool=invite_team_members partial_failures=%d of=%d",
                                   len(result.data.errors), len(emails))
                tlog.success()
                return result
            return _private_app_err(InviteTeamMembersResult, tlog, "invite_team_members",
                                    status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(InviteTeamMembersResult, tlog, exc)
