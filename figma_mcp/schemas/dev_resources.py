from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult


class DevResource(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    url: str
    file_key: str
    node_id: str = Field(description="The node the dev resource is attached to.")


class DevResourceListData(BaseModel):
    model_config = ConfigDict(extra="allow")

    dev_resources: list[DevResource]


class DevResourceListResult(ToolResult):
    data: DevResourceListData | None = None


class CreateDevResourceError(BaseModel):
    model_config = ConfigDict(extra="allow")

    file_key: str | None = None
    node_id: str | None = None
    error: str


class CreateDevResourcesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    links_created: list[DevResource] | None = None
    errors: list[CreateDevResourceError] | None = Field(
        default=None,
        description="Dev resources that could not be created; present even on a 200 response.",
    )


class CreateDevResourcesResult(ToolResult):
    data: CreateDevResourcesData | None = None


class UpdateDevResourceError(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    error: str


class UpdateDevResourcesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    links_updated: list[dict[str, Any] | str] | None = Field(
        default=None,
        description=(
            "Updated dev resources: full objects (id, name, url, file_key, node_id) per the spec, "
            "or bare ids per Figma's docs."
        ),
    )
    errors: list[UpdateDevResourceError] | None = Field(
        default=None,
        description="Dev resources that could not be updated; present even on a 200 response.",
    )


class UpdateDevResourcesResult(ToolResult):
    data: UpdateDevResourcesData | None = None


class DeleteDevResourceData(BaseModel):
    model_config = ConfigDict(extra="allow")

    file_key: str
    dev_resource_id: str


class DeleteDevResourceResult(ToolResult):
    data: DeleteDevResourceData | None = None
