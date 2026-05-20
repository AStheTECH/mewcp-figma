from typing import Optional
from typing_extensions import TypedDict


class FigmaImageExportParams(TypedDict, total=False):
    ids: str          # Comma-separated list of node IDs to export
    scale: float      # Scale factor (0.01 – 4)
    format: str       # "jpg", "png", "svg", "pdf"
    svg_include_id: bool
    svg_simplify_stroke: bool
    use_absolute_bounds: bool
    version: str      # Specific version to export
