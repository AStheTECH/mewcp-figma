from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

SharingAudience = Literal["org_view", "org_edit", "invite_only", "workspace_view", "workspace_edit"]
TeamRole = Literal["viewer", "editor", "admin"]


class TeamData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    sharing_audience_control: SharingAudience = Field(
        description="The audience that can discover and join the team: org_view, org_edit, "
                    "invite_only, workspace_view or workspace_edit.")
    org_discoverability: Literal["hidden", "discoverable"] | None = Field(
        default=None,
        description="Whether organization members can discover an invite-only team: hidden or "
                    "discoverable. Null unless sharing_audience_control is invite_only.")
    workspace_id: str | None = Field(default=None, description="The workspace containing the team.")
    owner_user_id: str | None = Field(default=None, description="The ID of the user who owns the team.")
    created_at: str = Field(description="The time at which the team was created (ISO 8601 date-time).")


class GetTeamData(TeamData):
    pass


class GetTeamResult(ToolResult):
    data: GetTeamData | None = None


class CreateTeamData(TeamData):
    pass


class CreateTeamResult(ToolResult):
    data: CreateTeamData | None = None


class TeamInvite(BaseModel):
    model_config = ConfigDict(extra="allow")

    email: str = Field(description="The normalized email address that was invited.")
    role: TeamRole = Field(
        description="The requested team role (viewer, editor or admin). Existing roles are never "
                    "downgraded, so a user already on the team can hold a higher role.")


class TeamInviteError(BaseModel):
    model_config = ConfigDict(extra="allow")

    email: str = Field(description="The normalized email address that could not be invited.")
    error: str = Field(description="A human-readable explanation of the failure.")


class InviteTeamMembersData(BaseModel):
    model_config = ConfigDict(extra="allow")

    invites: list[TeamInvite] = Field(
        default_factory=list,
        description="Addresses that were invited, including users already on the team. An "
                    "invitation can still require organization-admin approval before the user joins.")
    errors: list[TeamInviteError] = Field(
        default_factory=list,
        description="Addresses that could not be invited; the other addresses were still processed. "
                    "Always check this — it can be non-empty on a successful call.")


class InviteTeamMembersResult(ToolResult):
    data: InviteTeamMembersData | None = None
