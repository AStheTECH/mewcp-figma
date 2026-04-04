from typing import Optional
from typing_extensions import TypedDict


class FigmaTokenData(TypedDict, total=False):
    """Figma authentication token data.

    Supports both Personal Access Tokens (PAT) and OAuth2 Bearer tokens.
    - For PAT: set `access_token` to your personal access token.
    - For OAuth2: set `access_token` to the OAuth2 bearer token.
    """

    access_token: str


class FigmaImageExportParams(TypedDict, total=False):
    ids: str          # Comma-separated list of node IDs to export
    scale: float      # Scale factor (0.01 – 4)
    format: str       # "jpg", "png", "svg", "pdf"
    svg_include_id: bool
    svg_simplify_stroke: bool
    use_absolute_bounds: bool
    version: str      # Specific version to export
