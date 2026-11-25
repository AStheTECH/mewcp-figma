from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._base import ToolResult

_TYPE_VALUES = "One of BOOLEAN, FLOAT, STRING, COLOR."


class VariableMode(BaseModel):
    model_config = ConfigDict(extra="allow")

    modeId: str
    name: str
    parentModeId: str | None = Field(
        default=None, description="Mode inherited from the parent collection; extended collections only.")


class LocalVariable(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    key: str
    variableCollectionId: str
    resolvedType: str | None = Field(default=None, description=_TYPE_VALUES)
    valuesByMode: dict[str, Any] | None = Field(
        default=None,
        description="Map of modeId to value: boolean, number, string, RGBA {r,g,b,a}, "
                    "VariableAlias {type: VARIABLE_ALIAS, id} or VariableComposedColor {color, opacity}.")
    remote: bool | None = None
    description: str | None = None
    hiddenFromPublishing: bool | None = None
    scopes: list[str] | None = None
    codeSyntax: dict[str, Any] | None = Field(default=None, description="Keys WEB, ANDROID, iOS.")
    deletedButReferenced: bool | None = None


class LocalVariableCollection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    key: str
    modes: list[VariableMode] | None = None
    defaultModeId: str | None = None
    remote: bool | None = None
    isExtension: bool | None = None
    parentVariableCollectionId: str | None = None
    rootVariableCollectionId: str | None = None
    variableOverrides: dict[str, dict[str, Any]] | None = Field(
        default=None, description="Map of variableId to (map of modeId to override value or null).")
    hiddenFromPublishing: bool | None = None
    variableIds: list[str] | None = None


class LocalVariablesMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    variables: dict[str, LocalVariable] = Field(default_factory=dict, description="Map of variable id to variable.")
    variableCollections: dict[str, LocalVariableCollection] = Field(
        default_factory=dict, description="Map of variable collection id to collection.")


class LocalVariablesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int | None = None
    error: bool | None = None
    meta: LocalVariablesMeta


class LocalVariablesResult(ToolResult):
    data: LocalVariablesData | None = None


class PublishedVariable(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    subscribed_id: str | None = Field(
        default=None, description="Id used by subscribing files; changes on every modify-and-publish.")
    name: str
    key: str
    variableCollectionId: str
    resolvedDataType: str | None = Field(default=None, description=f"{_TYPE_VALUES} Name per the OpenAPI spec.")
    resolvedType: str | None = Field(default=None, description=f"{_TYPE_VALUES} Name per the docs page.")
    updatedAt: str | None = Field(default=None, description="ISO 8601 time the variable was last published.")


class PublishedVariableCollection(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    subscribed_id: str | None = Field(
        default=None, description="Id used by subscribing files; changes on every modify-and-publish.")
    name: str
    key: str
    updatedAt: str | None = Field(
        default=None, description="ISO 8601 time of the last published change to any variable in the collection.")


class PublishedVariablesMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    variables: dict[str, PublishedVariable] = Field(default_factory=dict, description="Map of variable id to variable.")
    variableCollections: dict[str, PublishedVariableCollection] = Field(
        default_factory=dict, description="Map of variable collection id to collection.")


class PublishedVariablesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int | None = None
    error: bool | None = None
    meta: PublishedVariablesMeta


class PublishedVariablesResult(ToolResult):
    data: PublishedVariablesData | None = None


class UpdateVariablesMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    tempIdToRealId: dict[str, str] = Field(
        default_factory=dict, description="Map of temporary ids in the request to real ids of the created objects.")


class UpdateVariablesData(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: int | None = None
    error: bool | None = None
    meta: UpdateVariablesMeta


class UpdateVariablesResult(ToolResult):
    data: UpdateVariablesData | None = None
