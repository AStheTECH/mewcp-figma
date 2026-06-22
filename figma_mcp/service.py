import hashlib
import json
import logging
import os
from typing import Any, Optional

import httpx
from fastmcp_credentials import get_credentials

from .config import FIGMA_API_BASE

logger = logging.getLogger("figma-mcp-server")

# ---------------------------------------------------------------------------
# Figma REST API client
# ---------------------------------------------------------------------------

_403_HINTS: list[tuple[str, str]] = [
    ("/me",          "403 Forbidden — Token is invalid or has been deleted. "
                     "Go to Figma → Settings → Account → Personal access tokens, "
                     "generate a new token, and update FIGMA_ACCESS_TOKEN in your .env file."),
    ("/comments",    "403 Forbidden — Token missing Comments scope. "
                     "Go to Figma → Settings → Account → Personal access tokens, "
                     "regenerate your token, and enable Comments (Read + Write)."),
    ("/teams/",      "403 Forbidden — Team endpoints require a paid Figma plan "
                     "(Professional or Organization) and team membership."),
    ("/projects/",   "403 Forbidden — Project endpoints require a paid Figma plan "
                     "(Professional or Organization) and team membership."),
    ("/components/", "403 Forbidden — Component not found or not published to a team library. "
                     "Ensure the component_key is from a published library component."),
]

_404_HINTS: list[tuple[str, str]] = [
    ("/files/",      "404 Not Found — File not found. Check the file_key is correct and "
                     "you have access to the file."),
    ("/components/", "404 Not Found — Component not found. Ensure the component_key is "
                     "from a published Figma library component."),
]


def _headers() -> dict[str, str]:
    token = None
    try:
        cred = get_credentials()
        token = cred.access_token
    except Exception:
        pass

    if not token:
        token = os.environ.get("FIGMA_ACCESS_TOKEN")

    if not token:
        raise ValueError(
            "No OAuth access token available. "
            "Set FIGMA_ACCESS_TOKEN env var for local testing."
        )

    if token.startswith("figd_"):
        return {"X-Figma-Token": token}
    return {"Authorization": f"Bearer {token}"}


def _raise_for_status(response: httpx.Response, path: str) -> None:
    if response.status_code == 403:
        hint = next(
            (msg for key, msg in _403_HINTS if key in path),
            "403 Forbidden — Check your token scopes and Figma plan.",
        )
        raise PermissionError(hint)
    if response.status_code == 404:
        hint = next(
            (msg for key, msg in _404_HINTS if key in path),
            "404 Not Found — Resource not found. Check your input parameters.",
        )
        raise LookupError(hint)
    response.raise_for_status()


def _get(path: str, params: Optional[dict] = None) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=_headers(), params=params)
        _raise_for_status(response, path)
        return response.json()


def _post(path: str, body: dict) -> dict[str, Any]:
    url = f"{FIGMA_API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=_headers(), json=body)
        _raise_for_status(response, path)
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
    if project_id.startswith("http") or "/" in project_id:
        raise ValueError(
            "project_id must be a numeric Figma project ID (e.g. '123456789'), not a URL. "
            "In Figma, open a project folder — the number after '/project/' in the URL is the project ID."
        )
    return _get(f"/projects/{project_id}/files")


# --- Components ---

def get_team_components(team_id: str) -> dict[str, Any]:
    return _get(f"/teams/{team_id}/components")


def get_component(component_key: str) -> dict[str, Any]:
    if component_key.startswith("http") or "/" in component_key:
        raise ValueError(
            "component_key must be an alphanumeric component key, not a URL. "
            "In Figma, select a published component → Inspect panel → copy the component key."
        )
    return _get(f"/components/{component_key}")


# ---------------------------------------------------------------------------
# Figma data simplification pipeline
# ---------------------------------------------------------------------------
# Transforms raw API responses into a compact, LLM-friendly format by:
#   - Filtering invisible nodes (preserving component-definition bool-prop nodes)
#   - Extracting layout, text, fill, stroke, effect, and component metadata
#   - Deduplicating shared styles via content-addressed SHA-1 IDs in globalVars
#   - Collapsing pure-vector containers into IMAGE-SVG
# ---------------------------------------------------------------------------

_SVG_ELIGIBLE_TYPES = {
    "IMAGE-SVG", "BOOLEAN_OPERATION", "STAR", "LINE",
    "ELLIPSE", "REGULAR_POLYGON", "RECTANGLE",
}
_COLLAPSIBLE_CONTAINER_TYPES = {"FRAME", "GROUP", "INSTANCE", "BOOLEAN_OPERATION"}
_SVG_COLLAPSE_AUTOLAYOUT_THRESHOLD = 10


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _find_or_create_var(global_vars: dict, cache: dict, value: Any, prefix: str) -> str:
    key = _stable_json(value)
    if key in cache:
        return cache[key]
    hash_hex = hashlib.sha1(key.encode()).hexdigest()
    length = 8
    var_id = f"{prefix}_{hash_hex[:length]}"
    while var_id in global_vars:
        length += 4
        var_id = f"{prefix}_{hash_hex[:length]}"
    global_vars[var_id] = value
    cache[key] = var_id
    return var_id


def _color_to_css(color: dict, opacity_override: float = 1.0) -> str:
    r = round(color.get("r", 0) * 255)
    g = round(color.get("g", 0) * 255)
    b = round(color.get("b", 0) * 255)
    a = round(color.get("a", 1) * opacity_override, 4)
    if a >= 1.0:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r},{g},{b},{a})"


def _parse_paint(paint: dict) -> Optional[Any]:
    ptype = paint.get("type", "")
    opacity = paint.get("opacity", 1.0)

    if ptype == "SOLID":
        return _color_to_css(paint.get("color", {}), opacity)

    if ptype in ("GRADIENT_LINEAR", "GRADIENT_RADIAL", "GRADIENT_ANGULAR", "GRADIENT_DIAMOND"):
        stops = paint.get("gradientStops", [])
        stop_strs = [
            f"{_color_to_css(s['color'])} {round(s['position'] * 100)}%"
            for s in stops
        ]
        grad_fn = {
            "GRADIENT_LINEAR": "linear-gradient",
            "GRADIENT_RADIAL": "radial-gradient",
            "GRADIENT_ANGULAR": "conic-gradient",
            "GRADIENT_DIAMOND": "radial-gradient",
        }.get(ptype, "linear-gradient")
        return {"gradient": f"{grad_fn}({', '.join(stop_strs)})"}

    if ptype == "IMAGE":
        result: dict = {"type": "IMAGE"}
        if paint.get("imageRef"):
            result["imageRef"] = paint["imageRef"]
        scale_mode = paint.get("scaleMode", "FILL")
        if scale_mode != "FILL":
            result["scaleMode"] = scale_mode
        if opacity < 1.0:
            result["opacity"] = round(opacity, 4)
        return result

    return None


def _simplify_layout(node: dict) -> Optional[dict]:
    if node.get("type") not in ("FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE"):
        return None
    mode_map = {"HORIZONTAL": "row", "VERTICAL": "column", "GRID": "grid"}
    mode = mode_map.get(node.get("layoutMode", "NONE"))
    if not mode:
        return None

    layout: dict = {"mode": mode}
    pt = node.get("paddingTop", 0) or 0
    pr = node.get("paddingRight", 0) or 0
    pb = node.get("paddingBottom", 0) or 0
    pl = node.get("paddingLeft", 0) or 0
    if pt or pr or pb or pl:
        if pt == pb and pr == pl:
            layout["padding"] = f"{pt}px" if pt == pr else f"{pt}px {pr}px"
        else:
            layout["padding"] = f"{pt}px {pr}px {pb}px {pl}px"

    if mode == "grid":
        cols = (node.get("gridColumnsSizing") or "").strip()
        if cols:
            layout["gridTemplateColumns"] = cols
        rows = (node.get("gridRowsSizing") or "").strip()
        if rows:
            layout["gridTemplateRows"] = rows
        rg = node.get("gridRowGap", 0) or 0
        cg = node.get("gridColumnGap", 0) or 0
        if rg or cg:
            layout["gap"] = f"{rg}px" if rg == cg else f"{rg}px {cg}px"
    else:
        gap = node.get("itemSpacing", 0) or 0
        if gap:
            layout["gap"] = f"{gap}px"
        primary_map = {
            "MAX": "flex-end", "CENTER": "center", "SPACE_BETWEEN": "space-between",
        }
        jc = primary_map.get(node.get("primaryAxisAlignItems", "MIN"))
        if jc:
            layout["justifyContent"] = jc
        counter_map = {"MAX": "flex-end", "CENTER": "center", "BASELINE": "baseline"}
        ai = counter_map.get(node.get("counterAxisAlignItems", "MIN"))
        if ai:
            layout["alignItems"] = ai
        if node.get("layoutWrap") == "WRAP":
            layout["wrap"] = True

    return layout


def _simplify_fills(node: dict) -> Optional[list]:
    visible = [f for f in node.get("fills", []) if f.get("visible", True)]
    if not visible:
        return None
    parsed = [_parse_paint(f) for f in reversed(visible)]
    result = [p for p in parsed if p is not None]
    return result or None


def _simplify_strokes(node: dict) -> Optional[dict]:
    visible = [s for s in node.get("strokes", []) if s.get("visible", True)]
    if not visible:
        return None
    colors = [p for p in (_parse_paint(s) for s in reversed(visible)) if p is not None]
    if not colors:
        return None
    result: dict = {"colors": colors}
    sw = node.get("strokeWeight")
    if sw and isinstance(sw, (int, float)) and sw > 0:
        result["strokeWeight"] = f"{sw}px"
    isw = node.get("individualStrokeWeights")
    if isw and isinstance(isw, dict):
        t, r, b, l = isw.get("top", 0), isw.get("right", 0), isw.get("bottom", 0), isw.get("left", 0)
        result["strokeWeight"] = f"{t}px {r}px {b}px {l}px"
    dashes = node.get("strokeDashes")
    if dashes:
        result["strokeDashes"] = dashes
    align = node.get("strokeAlign")
    if align in ("OUTSIDE", "CENTER"):
        result["strokeAlign"] = align
    return result


def _simplify_effects(node: dict) -> Optional[dict]:
    visible = [e for e in node.get("effects", []) if e.get("visible", True)]
    if not visible:
        return None
    shadows: list[str] = []
    blurs: list[dict] = []
    for effect in visible:
        etype = effect.get("type", "")
        if etype in ("DROP_SHADOW", "INNER_SHADOW"):
            offset = effect.get("offset", {"x": 0, "y": 0})
            radius = effect.get("radius", 0)
            spread = effect.get("spread", 0)
            color_str = _color_to_css(effect.get("color", {}))
            parts = [f"{offset.get('x',0)}px", f"{offset.get('y',0)}px", f"{radius}px"]
            if spread:
                parts.append(f"{spread}px")
            parts.append(color_str)
            shadow = " ".join(parts)
            if etype == "INNER_SHADOW":
                shadow = "inset " + shadow
            shadows.append(shadow)
        elif etype == "LAYER_BLUR":
            blurs.append({"type": "blur", "radius": effect.get("radius", 0)})
        elif etype == "BACKGROUND_BLUR":
            blurs.append({"type": "backgroundBlur", "radius": effect.get("radius", 0)})
    result: dict = {}
    if shadows:
        result["boxShadow"] = ", ".join(shadows)
    if blurs:
        result["filter"] = blurs
    return result or None


def _simplify_text_style(node: dict) -> Optional[dict]:
    style = node.get("style", {})
    ts: dict = {}
    if ff := style.get("fontFamily"):
        ts["fontFamily"] = ff
    if fs := style.get("fontSize"):
        ts["fontSize"] = f"{fs}px"
    fw = style.get("fontWeight")
    if fw and fw != 400:
        ts["fontWeight"] = fw
    if style.get("italic"):
        ts["fontStyle"] = "italic"
    if lh := style.get("lineHeightPx"):
        ts["lineHeight"] = f"{round(lh, 2)}px"
    if ls := style.get("letterSpacing"):
        ts["letterSpacing"] = f"{ls}px"
    align_map = {"CENTER": "center", "RIGHT": "right", "JUSTIFIED": "justify"}
    if ta := align_map.get(style.get("textAlignHorizontal", "")):
        ts["textAlign"] = ta
    decor_map = {"UNDERLINE": "underline", "STRIKETHROUGH": "line-through"}
    if td := decor_map.get(style.get("textDecoration", "")):
        ts["textDecoration"] = td
    case_map = {"UPPER": "uppercase", "LOWER": "lowercase", "TITLE": "capitalize"}
    if tc := case_map.get(style.get("textCase", "")):
        ts["textTransform"] = tc
    return ts or None


def _process_node(
    node: dict,
    global_vars: dict,
    cache: dict,
    depth: int,
    max_depth: Optional[int],
    inside_component_def: bool,
) -> Optional[dict]:
    if not node.get("visible", True):
        prop_refs = node.get("componentPropertyReferences")
        has_visible_ref = isinstance(prop_refs, dict) and "visible" in prop_refs
        if not (has_visible_ref and inside_component_def):
            return None

    raw_type = node.get("type", "FRAME")
    node_type = "IMAGE-SVG" if raw_type == "VECTOR" else raw_type

    result: dict = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "type": node_type,
    }

    layout = _simplify_layout(node)
    if layout:
        result["layout"] = _find_or_create_var(global_vars, cache, layout, "layout")

    if raw_type == "TEXT":
        if text := node.get("characters"):
            result["text"] = text
        if ts := _simplify_text_style(node):
            result["textStyle"] = _find_or_create_var(global_vars, cache, ts, "style")

    fills = _simplify_fills(node)
    if fills:
        result["fills"] = _find_or_create_var(global_vars, cache, fills, "fill")

    strokes = _simplify_strokes(node)
    if strokes:
        colors = strokes.get("colors", [])
        if colors:
            result["strokes"] = _find_or_create_var(global_vars, cache, colors, "fill")
        for k in ("strokeWeight", "strokeDashes", "strokeAlign"):
            if k in strokes:
                result[k] = strokes[k]

    effects = _simplify_effects(node)
    if effects:
        result["effects"] = _find_or_create_var(global_vars, cache, effects, "effect")

    opacity = node.get("opacity")
    if opacity is not None and opacity != 1:
        result["opacity"] = round(opacity, 4)

    cr = node.get("cornerRadius")
    if cr is not None and isinstance(cr, (int, float)):
        result["borderRadius"] = f"{cr}px"
    rr = node.get("rectangleCornerRadii")
    if rr and isinstance(rr, list) and len(rr) == 4:
        result["borderRadius"] = " ".join(f"{v}px" for v in rr)

    if raw_type == "INSTANCE":
        if cid := node.get("componentId"):
            result["componentId"] = cid
        cp = node.get("componentProperties")
        if cp and isinstance(cp, dict):
            simplified = {
                k: v.get("value") if isinstance(v, dict) else v
                for k, v in cp.items()
            }
            if simplified:
                result["componentProperties"] = simplified

    children_data = node.get("children", [])
    if children_data and (max_depth is None or depth < max_depth):
        if raw_type in ("COMPONENT", "COMPONENT_SET"):
            next_inside = True
        elif raw_type == "INSTANCE":
            next_inside = False
        else:
            next_inside = inside_component_def

        processed: list[dict] = []
        for child in children_data:
            r = _process_node(child, global_vars, cache, depth + 1, max_depth, next_inside)
            if r is not None:
                processed.append(r)

        if processed and node_type in _COLLAPSIBLE_CONTAINER_TYPES:
            all_svg = all(c.get("type", "") in _SVG_ELIGIBLE_TYPES for c in processed)
            has_img = any(f.get("type") == "IMAGE" for f in node.get("fills", []))
            has_auto_layout = node.get("layoutMode") in ("HORIZONTAL", "VERTICAL", "GRID")
            if all_svg and not has_img and (
                not has_auto_layout or len(processed) >= _SVG_COLLAPSE_AUTOLAYOUT_THRESHOLD
            ):
                result["type"] = "IMAGE-SVG"
                processed = []

        if processed:
            result["children"] = processed

    return result


def get_figma_data(
    file_key: str,
    node_id: Optional[str] = None,
    depth: Optional[int] = None,
) -> dict[str, Any]:
    """Fetch and simplify a Figma file or node into an LLM-friendly format."""
    nid = node_id.replace("-", ":") if node_id else None
    raw = get_file_nodes(file_key, nid, depth) if nid else get_file(file_key, depth)

    global_vars: dict = {}
    cache: dict = {}
    name = raw.get("name", "")

    if "nodes" in raw:
        raw_nodes = [
            nd["document"]
            for nd in raw["nodes"].values()
            if nd and "document" in nd
        ]
    else:
        raw_nodes = raw.get("document", {}).get("children", [])

    nodes = [
        r for node in raw_nodes
        if (r := _process_node(node, global_vars, cache, 0, depth, False)) is not None
    ]

    return {"name": name, "nodes": nodes, "globalVars": global_vars}


# ---------------------------------------------------------------------------
# Image download service
# ---------------------------------------------------------------------------

def download_figma_images(
    file_key: str,
    nodes: list[dict],
    local_path: str,
    png_scale: float = 2.0,
) -> dict[str, Any]:
    """
    Download Figma image nodes to a local directory on the server filesystem.

    Each node dict must have nodeId and fileName; optionally imageRef, gifRef,
    or filenameSuffix. Returns savedPath, successCount, totalCount, and a
    per-file downloads list with status 'ok' or 'error'.
    """
    resolved = (
        os.path.normpath(local_path)
        if os.path.isabs(local_path)
        else os.path.normpath(os.path.join(os.getcwd(), local_path))
    )
    os.makedirs(resolved, exist_ok=True)

    fill_nodes, render_png_nodes, render_svg_nodes = [], [], []
    for node in nodes:
        if node.get("imageRef") or node.get("gifRef"):
            fill_nodes.append(node)
        elif (node.get("fileName", "")).lower().endswith(".svg"):
            render_svg_nodes.append(node)
        else:
            render_png_nodes.append(node)

    fill_url_map: dict[str, str] = {}
    if fill_nodes:
        try:
            data = get_image_fills(file_key)
            fill_url_map = data.get("meta", {}).get("images", {})
        except Exception as exc:
            logger.warning("Failed to fetch image fills for %s: %s", file_key, exc)

    render_png_map: dict[str, str] = {}
    if render_png_nodes:
        ids = ",".join(n["nodeId"].replace("-", ":") for n in render_png_nodes)
        try:
            data = get_images(file_key, ids, scale=png_scale, format="png")
            render_png_map = data.get("images", {})
        except Exception as exc:
            logger.warning("Failed to fetch PNG renders for %s: %s", file_key, exc)

    render_svg_map: dict[str, str] = {}
    if render_svg_nodes:
        ids = ",".join(n["nodeId"].replace("-", ":") for n in render_svg_nodes)
        try:
            data = get_images(file_key, ids, scale=1.0, format="svg")
            render_svg_map = data.get("images", {})
        except Exception as exc:
            logger.warning("Failed to fetch SVG renders for %s: %s", file_key, exc)

    downloads: list[dict] = []
    with httpx.Client(timeout=60) as client:
        for node in nodes:
            node_id = node.get("nodeId", "").replace("-", ":")
            fname = node.get("fileName", "file.png")
            suffix = node.get("filenameSuffix", "")
            if suffix and suffix not in fname:
                parts = fname.rsplit(".", 1)
                fname = f"{parts[0]}-{suffix}.{parts[1]}" if len(parts) == 2 else f"{fname}-{suffix}"

            ref = node.get("imageRef") or node.get("gifRef")
            if ref:
                url = fill_url_map.get(ref)
            elif fname.lower().endswith(".svg"):
                url = render_svg_map.get(node_id)
            else:
                url = render_png_map.get(node_id)

            if not url:
                downloads.append({"fileName": fname, "status": "error", "error": "No URL resolved"})
                continue

            try:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
                dest = os.path.join(resolved, fname)
                with open(dest, "wb") as fh:
                    fh.write(resp.content)
                downloads.append({"fileName": fname, "status": "ok"})
            except Exception as exc:
                downloads.append({"fileName": fname, "status": "error", "error": str(exc)})

    success_count = sum(1 for d in downloads if d["status"] == "ok")
    return {
        "savedPath": resolved,
        "successCount": success_count,
        "totalCount": len(downloads),
        "downloads": downloads,
    }
