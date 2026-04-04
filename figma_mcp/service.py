import logging
from typing import Any, Optional

import httpx

from .config import FIGMA_API_BASE

logger = logging.getLogger("figma-mcp-server")


def _headers(access_token: str) -> dict[str, str]:
    """Build Figma API request headers from a PAT or OAuth2 bearer token."""
    return {"X-Figma-Token": access_token}


def _get(access_token: str, path: str, params: Optional[dict] = None) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=_headers(access_token), params=params)
        response.raise_for_status()
        return response.json()


def _post(access_token: str, path: str, body: dict) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=_headers(access_token), json=body)
        response.raise_for_status()
        return response.json()


# --- User ---

def get_me(access_token: str) -> dict[str, Any]:
    return _get(access_token, "/me")


# --- Files ---

def get_file(access_token: str, file_key: str, depth: Optional[int] = None) -> dict[str, Any]:
    params = {}
    if depth is not None:
        params["depth"] = depth
    return _get(access_token, f"/files/{file_key}", params or None)


def get_file_nodes(
    access_token: str, file_key: str, node_ids: str, depth: Optional[int] = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"ids": node_ids}
    if depth is not None:
        params["depth"] = depth
    return _get(access_token, f"/files/{file_key}/nodes", params)


def get_file_components(access_token: str, file_key: str) -> dict[str, Any]:
    return _get(access_token, f"/files/{file_key}/components")


def get_file_styles(access_token: str, file_key: str) -> dict[str, Any]:
    return _get(access_token, f"/files/{file_key}/styles")


def get_file_versions(access_token: str, file_key: str) -> dict[str, Any]:
    return _get(access_token, f"/files/{file_key}/versions")


# --- Images ---

def get_images(
    access_token: str,
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
    return _get(access_token, f"/images/{file_key}", params)


def get_image_fills(access_token: str, file_key: str) -> dict[str, Any]:
    return _get(access_token, f"/files/{file_key}/images")


# --- Comments ---

def get_comments(access_token: str, file_key: str) -> dict[str, Any]:
    return _get(access_token, f"/files/{file_key}/comments")


def post_comment(
    access_token: str, file_key: str, message: str, client_meta: Optional[dict] = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"message": message}
    if client_meta:
        body["client_meta"] = client_meta
    return _post(access_token, f"/files/{file_key}/comments", body)


# --- Teams & Projects ---

def get_team_projects(access_token: str, team_id: str) -> dict[str, Any]:
    return _get(access_token, f"/teams/{team_id}/projects")


def get_project_files(access_token: str, project_id: str) -> dict[str, Any]:
    return _get(access_token, f"/projects/{project_id}/files")


# --- Components ---

def get_team_components(access_token: str, team_id: str) -> dict[str, Any]:
    return _get(access_token, f"/teams/{team_id}/components")


def get_component(access_token: str, component_key: str) -> dict[str, Any]:
    return _get(access_token, f"/components/{component_key}")
