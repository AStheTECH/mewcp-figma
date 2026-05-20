import logging
from typing import Any, Optional

import httpx
from fastmcp_credentials import get_credentials

from .config import FIGMA_API_BASE

logger = logging.getLogger("figma-mcp-server")


def _headers() -> dict[str, str]:
    """Build Figma API request headers from the injected credential."""
    cred = get_credentials()
    if not cred.access_token:
        raise ValueError("No OAuth access token available in credentials")
    return {"X-Figma-Token": cred.access_token}


def _get(path: str, params: Optional[dict] = None) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=_headers(), params=params)
        response.raise_for_status()
        return response.json()


def _post(path: str, body: dict) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=_headers(), json=body)
        response.raise_for_status()
        return response.json()


# --- User ---

def get_me() -> dict[str, Any]:
    return _get("/me")


# --- Files ---

def get_file(file_key: str, depth: Optional[int] = None) -> dict[str, Any]:
    params = {}
    if depth is not None:
        params["depth"] = depth
    return _get(f"/files/{file_key}", params or None)


def get_file_nodes(
    file_key: str, node_ids: str, depth: Optional[int] = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"ids": node_ids}
    if depth is not None:
        params["depth"] = depth
    return _get(f"/files/{file_key}/nodes", params)


def get_file_components(file_key: str) -> dict[str, Any]:
    return _get(f"/files/{file_key}/components")


def get_file_styles(file_key: str) -> dict[str, Any]:
    return _get(f"/files/{file_key}/styles")


def get_file_versions(file_key: str) -> dict[str, Any]:
    return _get(f"/files/{file_key}/versions")


# --- Images ---

def get_images(
    file_key: str,
    node_ids: str,
    scale: Optional[float] = None,
    format: Optional[str] = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"ids": node_ids}
    if scale is not None:
        params["scale"] = scale
    if format is not None:
        params["format"] = format
    return _get(f"/images/{file_key}", params)


def get_image_fills(file_key: str) -> dict[str, Any]:
    return _get(f"/files/{file_key}/images")


# --- Comments ---

def get_comments(file_key: str) -> dict[str, Any]:
    return _get(f"/files/{file_key}/comments")


def post_comment(
    file_key: str, message: str, client_meta: Optional[dict] = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"message": message}
    if client_meta:
        body["client_meta"] = client_meta
    return _post(f"/files/{file_key}/comments", body)


# --- Teams & Projects ---

def get_team_projects(team_id: str) -> dict[str, Any]:
    return _get(f"/teams/{team_id}/projects")


def get_project_files(project_id: str) -> dict[str, Any]:
    return _get(f"/projects/{project_id}/files")


# --- Components ---

def get_team_components(team_id: str) -> dict[str, Any]:
    return _get(f"/teams/{team_id}/components")


def get_component(component_key: str) -> dict[str, Any]:
    return _get(f"/components/{component_key}")
