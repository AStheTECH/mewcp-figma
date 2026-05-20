import json
import logging
from typing import Optional

from fastmcp import FastMCP
from pydantic import Field

from . import service

logger = logging.getLogger("figma-mcp-server")


def register_tools(mcp: FastMCP) -> None:

    # ------------------------------------------------------------------ #
    # Health                                                               #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="health_check",
        description="Check server readiness and basic connectivity.",
    )
    def health_check() -> str:
        return json.dumps({"status": "ok", "server": "CL Figma MCP Server"})

    # ------------------------------------------------------------------ #
    # User                                                                 #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_me",
        description="Return the authenticated Figma user's profile information.",
    )
    def get_me() -> str:
        try:
            result = service.get_me()
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_me: {e}")
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------ #
    # Files                                                                #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_file",
        description="Retrieve a Figma file document tree by its file key.",
    )
    def get_file(
        file_key: str = Field(..., description="The unique key identifying the Figma file (found in the file URL)"),
        depth: Optional[int] = Field(None, description="Depth of the node tree to return (default: full tree)"),
    ) -> str:
        try:
            result = service.get_file(file_key, depth)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_file for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_file_nodes",
        description="Retrieve specific nodes from a Figma file by their IDs.",
    )
    def get_file_nodes(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
        node_ids: str = Field(..., description="Comma-separated list of node IDs to retrieve (e.g. '1:2,3:4')"),
        depth: Optional[int] = Field(None, description="Depth of the node subtree to return"),
    ) -> str:
        try:
            result = service.get_file_nodes(file_key, node_ids, depth)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_file_nodes for file '{file_key}', nodes '{node_ids}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_file_components",
        description="List all local components defined in a Figma file.",
    )
    def get_file_components(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
    ) -> str:
        try:
            result = service.get_file_components(file_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_file_components for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_file_styles",
        description="List all local styles (colors, text, effects, grids) defined in a Figma file.",
    )
    def get_file_styles(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
    ) -> str:
        try:
            result = service.get_file_styles(file_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_file_styles for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_file_versions",
        description="Retrieve the version history of a Figma file.",
    )
    def get_file_versions(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
    ) -> str:
        try:
            result = service.get_file_versions(file_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_file_versions for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------ #
    # Images / Exports                                                     #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_images",
        description="Export one or more nodes from a Figma file as rendered image URLs.",
    )
    def get_images(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
        node_ids: str = Field(..., description="Comma-separated list of node IDs to export (e.g. '1:2,3:4')"),
        scale: Optional[float] = Field(None, description="Export scale factor between 0.01 and 4 (default: 1)"),
        format: Optional[str] = Field(None, description="Image format: 'jpg', 'png', 'svg', or 'pdf' (default: 'png')"),
    ) -> str:
        try:
            result = service.get_images(file_key, node_ids, scale, format)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_images for file '{file_key}', nodes '{node_ids}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_image_fills",
        description="Retrieve download URLs for all images embedded in a Figma file as fills.",
    )
    def get_image_fills(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
    ) -> str:
        try:
            result = service.get_image_fills(file_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_image_fills for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------ #
    # Comments                                                             #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_comments",
        description="List all comments on a Figma file.",
    )
    def get_comments(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
    ) -> str:
        try:
            result = service.get_comments(file_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_comments for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="post_comment",
        description="Post a new comment on a Figma file.",
    )
    def post_comment(
        file_key: str = Field(..., description="The unique key identifying the Figma file"),
        message: str = Field(..., description="The comment text to post"),
    ) -> str:
        try:
            result = service.post_comment(file_key, message)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed post_comment for '{file_key}': {e}")
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------ #
    # Teams & Projects                                                     #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_team_projects",
        description="List all projects belonging to a Figma team.",
    )
    def get_team_projects(
        team_id: str = Field(..., description="The Figma team ID"),
    ) -> str:
        try:
            result = service.get_team_projects(team_id)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_team_projects for team '{team_id}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_project_files",
        description="List all files within a Figma project.",
    )
    def get_project_files(
        project_id: str = Field(..., description="The Figma project ID"),
    ) -> str:
        try:
            result = service.get_project_files(project_id)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_project_files for project '{project_id}': {e}")
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------ #
    # Components                                                           #
    # ------------------------------------------------------------------ #

    @mcp.tool(
        name="get_team_components",
        description="List all published components in a Figma team library.",
    )
    def get_team_components(
        team_id: str = Field(..., description="The Figma team ID"),
    ) -> str:
        try:
            result = service.get_team_components(team_id)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_team_components for team '{team_id}': {e}")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="get_component",
        description="Retrieve metadata for a specific published Figma component by its key.",
    )
    def get_component(
        component_key: str = Field(..., description="The unique key of the published component"),
    ) -> str:
        try:
            result = service.get_component(component_key)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Failed get_component for '{component_key}': {e}")
            return json.dumps({"error": str(e)})
