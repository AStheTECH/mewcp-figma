"""MewCP Figma tool registration."""

from fastmcp import FastMCP

from .comments_tools import register_comments_tools
from .components_tools import register_components_tools
from .dev_resources_tools import register_dev_resources_tools
from .files_tools import register_files_tools
from .folders_tools import register_folders_tools
from .library_analytics_tools import register_library_analytics_tools
from .teams_tools import register_teams_tools
from .users_tools import register_users_tools
from .variables_tools import register_variables_tools
from .versions_tools import register_versions_tools


def register_tools(mcp: FastMCP) -> None:
    register_files_tools(mcp)
    register_versions_tools(mcp)
    register_comments_tools(mcp)
    register_users_tools(mcp)
    register_teams_tools(mcp)
    register_folders_tools(mcp)
    register_components_tools(mcp)
    register_variables_tools(mcp)
    register_dev_resources_tools(mcp)
    register_library_analytics_tools(mcp)
