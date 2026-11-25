"""Files group: get_file, get_file_nodes, render_images, get_image_fills, get_file_metadata, duplicate_file"""

import logging
from typing import Literal
from urllib.parse import quote

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .. import service
from ..config import CONNECT_TIMEOUT, READ_TIMEOUT
from ..logging_utils import ToolLogger
from ..schemas.files import (
    DuplicateFileData,
    DuplicateFileResult,
    GetFileData,
    GetFileMetadataData,
    GetFileMetadataResult,
    GetFileNodesData,
    GetFileNodesResult,
    GetFileResult,
    GetImageFillsData,
    GetImageFillsResult,
    RenderImagesData,
    RenderImagesResult,
)
from ._helpers import _err, _handle_request_exc, _private_app_err, _upstream_err

logger = logging.getLogger("figma-mcp.tools.files")

_FILE_KEY_DESC = (
    "Key of the Figma file or branch, as in https://www.figma.com/:file_type/:file_key/:file_name. "
    "Branch keys come from get_file with `branch_data=true` (`branches[].key`)."
)
_VERSION_DESC = ("Version ID to read (from list_file_versions). Omit to get the current version.")
_GEOMETRY_DESC = "Set to 'paths' to include vector data. Omit to return no vector data."
_PLUGIN_DATA_DESC = (
    "Comma-separated plugin IDs and/or 'shared'. Data those plugins wrote is returned in the nodes' "
    "`pluginData` and `sharedPluginData` properties. Omit to return no plugin data."
)


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _blank(value: str | None) -> bool:
    return value is None or not value.strip()


def register_files_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_file",
        description=(
            "Returns a Figma file as JSON: its document layer tree (DOCUMENT -> pages (CANVAS) -> "
            "layers, nested via `children`), the `components`, `componentSets` and `styles` maps, "
            "and file metadata (name, role, editorType, version, lastModified, thumbnailUrl). "
            "Full-file responses can be very large and may fail with a 400 timeout - limit them with "
            "`depth` (1 = pages only, 2 = pages plus their top-level layers) or `ids`, or use "
            "get_file_nodes when the node IDs are known; vector data is only included with "
            "`geometry='paths'`. The `components` / `componentSets` maps only cover nodes inside the "
            "returned tree (empty at depth=1), so omit `depth` to list all local components. "
            "Pass `branch_data=true` to also get `mainFileKey` and `branches`. "
            "Node IDs from the tree feed get_file_nodes and render_images; `imageRef` values on fills "
            "resolve through get_image_fills. Tier 1 rate limit; needs the file_content:read scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_file(
        file_key: str = Field(description=_FILE_KEY_DESC),
        version: str | None = Field(default=None, description=_VERSION_DESC),
        ids: str | None = Field(
            default=None,
            description=(
                "Comma-separated node IDs (e.g. '1:2,1:3'). Returns only those nodes, their children "
                "and their ancestor chains, plus dependencies such as local components they use; "
                "top-level pages are always returned. Omit to return the whole document."
            ),
        ),
        depth: int | None = Field(
            default=None,
            description=(
                "Positive integer: how deep into the document tree to traverse, counted from the "
                "document root. 1 returns only pages; 2 returns pages and their top-level objects. "
                "Omit to return all nodes."
            ),
        ),
        geometry: Literal["paths"] | None = Field(default=None, description=_GEOMETRY_DESC),
        plugin_data: str | None = Field(default=None, description=_PLUGIN_DATA_DESC),
        branch_data: bool | None = Field(
            default=None,
            description=(
                "If true, returns branch metadata: `mainFileKey` when the file is a branch, and "
                "`branches` when the file has branches. Defaults to false."
            ),
        ),
    ) -> GetFileResult:
        tlog = ToolLogger(logger, "get_file")

        if _blank(file_key):
            return _err(GetFileResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        if depth is not None and depth < 1:
            return _err(GetFileResult, tlog, "VALIDATION_ERROR", "depth must be a positive integer", 400)

        params = {}
        if version is not None:
            params["version"] = version
        if ids is not None:
            params["ids"] = ids
        if depth is not None:
            params["depth"] = depth
        if geometry is not None:
            params["geometry"] = geometry
        if plugin_data is not None:
            params["plugin_data"] = plugin_data
        if branch_data is not None:
            params["branch_data"] = _bool(branch_data)

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}", params=params or None,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return GetFileResult(success=True, statusCode=status, data=GetFileData(**data))
            return _upstream_err(GetFileResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(GetFileResult, tlog, exc)

    @mcp.tool(
        name="get_file_nodes",
        description=(
            "Returns specific nodes of a Figma file as JSON: a `nodes` map from each requested node ID "
            "to {document (the node and its subtree via `children`), components, componentSets, "
            "schemaVersion, styles}, plus the file's name, role, editorType, version, lastModified and "
            "thumbnailUrl. A `nodes` value is null when that ID doesn't exist in the file - check each "
            "one. Prefer this over get_file when the node IDs are known; keep responses small with "
            "`depth` (counted from each requested node, 1 = direct children only). Vector data is only "
            "included with `geometry='paths'`. Node IDs come from get_file or the `node-id` query "
            "param of a Figma node URL. Tier 1 rate limit; needs the file_content:read scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_file_nodes(
        file_key: str = Field(description=_FILE_KEY_DESC),
        ids: str = Field(description="Comma-separated node IDs to retrieve (e.g. '1:2,1:3')."),
        version: str | None = Field(default=None, description=_VERSION_DESC),
        depth: int | None = Field(
            default=None,
            description=(
                "Positive integer: how deep below each requested node to traverse (counted from that "
                "node, not the document root). 1 returns only the nodes' direct children. Omit to "
                "return full subtrees."
            ),
        ),
        geometry: Literal["paths"] | None = Field(default=None, description=_GEOMETRY_DESC),
        plugin_data: str | None = Field(default=None, description=_PLUGIN_DATA_DESC),
    ) -> GetFileNodesResult:
        tlog = ToolLogger(logger, "get_file_nodes")

        if _blank(file_key):
            return _err(GetFileNodesResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        if _blank(ids):
            return _err(GetFileNodesResult, tlog, "VALIDATION_ERROR", "ids must not be empty", 400)
        if depth is not None and depth < 1:
            return _err(GetFileNodesResult, tlog, "VALIDATION_ERROR",
                        "depth must be a positive integer", 400)

        params = {"ids": ids}
        if version is not None:
            params["version"] = version
        if depth is not None:
            params["depth"] = depth
        if geometry is not None:
            params["geometry"] = geometry
        if plugin_data is not None:
            params["plugin_data"] = plugin_data

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}/nodes", params=params,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return GetFileNodesResult(success=True, statusCode=status,
                                          data=GetFileNodesData(**data))
            return _upstream_err(GetFileNodesResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(GetFileNodesResult, tlog, exc)

    @mcp.tool(
        name="render_images",
        description=(
            "Renders nodes of a Figma file as jpg, png (default), svg or pdf images and returns "
            "`images`, a map from each requested node ID to its image URL; URLs expire after 30 days. "
            "A value is null when that node failed to render (ID not in the file, invisible, 0% "
            "opacity, or nothing renderable) - every requested ID appears in the map, so check each "
            "value. Images over 32 megapixels are scaled down; very large render requests can fail "
            "with 500 - reduce the number or size of nodes. Read-only: nothing is created in the file. "
            "Node IDs come from get_file / get_file_nodes. Tier 1 rate limit; needs the "
            "file_content:read scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def render_images(
        file_key: str = Field(description=_FILE_KEY_DESC),
        ids: str = Field(description="Comma-separated node IDs to render (e.g. '1:2,1:3,1:4')."),
        version: str | None = Field(default=None, description=_VERSION_DESC),
        scale: float | None = Field(
            default=None, description="Image scaling factor between 0.01 and 4. Omit for Figma's default."),
        format: Literal["jpg", "png", "svg", "pdf"] | None = Field(
            default=None, description="Image output format: jpg, png, svg or pdf. Defaults to png."),
        svg_outline_text: bool | None = Field(
            default=None,
            description=(
                "SVG only. True renders text as outlines (vector paths), so it looks exactly as in "
                "Figma; false renders `<text>` elements, which are selectable but rely on the "
                "browser's text rendering, so visual accuracy is not guaranteed. Defaults to true."
            ),
        ),
        svg_include_id: bool | None = Field(
            default=None,
            description="SVG only. If true, adds the layer name to each SVG element's `id` attribute. Defaults to false.",
        ),
        svg_include_node_id: bool | None = Field(
            default=None,
            description="SVG only. If true, adds the node ID to each SVG element's `data-node-id` attribute. Defaults to false.",
        ),
        svg_simplify_stroke: bool | None = Field(
            default=None,
            description="SVG only. If true, simplifies inside/outside strokes and uses the stroke attribute instead of `<mask>` where possible. Defaults to true.",
        ),
        contents_only: bool | None = Field(
            default=None,
            description=(
                "If true, excludes content that overlaps the node from the render. False renders "
                "overlaps, which may increase processing time. Defaults to true."
            ),
        ),
        use_absolute_bounds: bool | None = Field(
            default=None,
            description=(
                "If true, uses the node's full dimensions even if it is cropped or surrounded by empty "
                "space; use it to export text nodes without cropping. Defaults to false."
            ),
        ),
    ) -> RenderImagesResult:
        tlog = ToolLogger(logger, "render_images")

        if _blank(file_key):
            return _err(RenderImagesResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        if _blank(ids):
            return _err(RenderImagesResult, tlog, "VALIDATION_ERROR", "ids must not be empty", 400)
        if scale is not None and not 0.01 <= scale <= 4:
            return _err(RenderImagesResult, tlog, "VALIDATION_ERROR",
                        "scale must be between 0.01 and 4", 400)

        params = {"ids": ids}
        if version is not None:
            params["version"] = version
        if scale is not None:
            params["scale"] = scale
        if format is not None:
            params["format"] = format
        for key, value in (
            ("svg_outline_text", svg_outline_text),
            ("svg_include_id", svg_include_id),
            ("svg_include_node_id", svg_include_node_id),
            ("svg_simplify_stroke", svg_simplify_stroke),
            ("contents_only", contents_only),
            ("use_absolute_bounds", use_absolute_bounds),
        ):
            if value is not None:
                params[key] = _bool(value)

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/images/{quote(file_key, safe='')}", params=params,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return RenderImagesResult(success=True, statusCode=status,
                                          data=RenderImagesData(**data))
            explanation = None
            if status == 500:
                explanation = ("Figma could not complete the render; this most often happens with very "
                               "large render requests - reduce the number and size of nodes.")
            return _upstream_err(RenderImagesResult, tlog, status, data, retry_after,
                                 explanation=explanation)
        except Exception as exc:
            return _handle_request_exc(RenderImagesResult, tlog, exc)

    @mcp.tool(
        name="get_image_fills",
        description=(
            "Returns download URLs for every image used in image fills in a Figma file, as "
            "`meta.images`, a map from imageRef to URL; URLs expire within 14 days. imageRef values "
            "appear as `imageRef` on Paint fills in get_file / get_file_nodes output. To render a node "
            "as an image, use render_images instead. Tier 2 rate limit; needs the file_content:read scope."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_image_fills(
        file_key: str = Field(description=_FILE_KEY_DESC),
    ) -> GetImageFillsResult:
        tlog = ToolLogger(logger, "get_image_fills")

        if _blank(file_key):
            return _err(GetImageFillsResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}/images",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return GetImageFillsResult(success=True, statusCode=status,
                                           data=GetImageFillsData(**data))
            return _upstream_err(GetImageFillsResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(GetImageFillsResult, tlog, exc)

    @mcp.tool(
        name="get_file_metadata",
        description=(
            "Returns a Figma file's metadata without its content: name, project (folder_name), "
            "creator, last_touched_at and last_touched_by, thumbnail_url, editorType, the caller's "
            "role, link_access, url and version. Cheaper than get_file (Tier 3 vs Tier 1) for "
            "name, owner, last-modified or version checks; `version` changes whenever the file is "
            "modified. Needs the file_metadata:read scope, unlike the other file tools "
            "(file_content:read)."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    def get_file_metadata(
        file_key: str = Field(description=_FILE_KEY_DESC),
    ) -> GetFileMetadataResult:
        tlog = ToolLogger(logger, "get_file_metadata")

        if _blank(file_key):
            return _err(GetFileMetadataResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)

        try:
            data, status, retry_after = service.api_request(
                "GET", f"/v1/files/{quote(file_key, safe='')}/meta",
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return GetFileMetadataResult(success=True, statusCode=status,
                                             data=GetFileMetadataData(**data))
            return _upstream_err(GetFileMetadataResult, tlog, status, data, retry_after)
        except Exception as exc:
            return _handle_request_exc(GetFileMetadataResult, tlog, exc)

    @mcp.tool(
        name="duplicate_file",
        description=(
            "Duplicates a Figma main file or branch into a folder as a new standalone file and returns "
            "the new file's file_key, name, folder_id, editor_type and created_at. Only works when "
            "Figma is connected through a private OAuth app on an Enterprise plan (scope "
            "file_duplicate:write); public-app connections are refused with 403 or 404. The source "
            "file and destination folder must belong to that Enterprise plan, and the user must be "
            "able to export the source file, edit the folder and create files of the source editor "
            "type (Figma Design, FigJam, Slides, Buzz or Make). The copy uses the source's latest "
            "saved checkpoint, so recent unsaved changes may be missing. `folder_id` comes from "
            "list_team_folders / list_subfolders. Tier 2 rate limit."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def duplicate_file(
        file_key: str = Field(description="Key of the main file or branch to duplicate."),
        folder_id: str = Field(
            description="ID of the folder to create the duplicate in (from list_team_folders / list_subfolders)."),
    ) -> DuplicateFileResult:
        tlog = ToolLogger(logger, "duplicate_file")

        if _blank(file_key):
            return _err(DuplicateFileResult, tlog, "VALIDATION_ERROR", "file_key must not be empty", 400)
        if _blank(folder_id):
            return _err(DuplicateFileResult, tlog, "VALIDATION_ERROR", "folder_id must not be empty", 400)

        try:
            data, status, retry_after = service.api_request(
                "POST", f"/v1/files/{quote(file_key, safe='')}/duplicate",
                body={"folder_id": folder_id},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            if 200 <= status < 300:
                tlog.success()
                return DuplicateFileResult(success=True, statusCode=status,
                                           data=DuplicateFileData(**data))
            return _private_app_err(DuplicateFileResult, tlog, "duplicate_file", status, data,
                                    retry_after)
        except Exception as exc:
            return _handle_request_exc(DuplicateFileResult, tlog, exc)
