"""Shared error helpers for all tool modules."""

import re

import pydantic
import requests
from fastmcp_credentials import CredentialError

from ..logging_utils import ToolLogger
from ..schemas import ToolError
from ..service import UPGRADE_LINK_KEY

_MAX_MSG = 500

_SCOPE_RE = re.compile(r"requires the (?:\S+ or )?(\S+) scope")

_ENTERPRISE = "a private OAuth app on an Enterprise plan"
_PRO_PLUS = "a private OAuth app on a Professional, Organization or Enterprise plan"
_NOT_PUBLIC = "a private OAuth app (not available to public OAuth apps)"

_PRIVATE_ONLY_SCOPES = {
    "teams:read": _PRO_PLUS,
    "teams:write": _ENTERPRISE,
    "team_members:write": _ENTERPRISE,
    "folders:write": _ENTERPRISE,
    "file_duplicate:write": _ENTERPRISE,
    "folders:read": _NOT_PUBLIC,
}

# tool -> (plan requirement, resource noun)
_PRIVATE_APP_TOOLS = {
    "duplicate_file": (_ENTERPRISE, "file"),
    "create_folder": (_ENTERPRISE, "team"),
    "create_team": (_ENTERPRISE, "organization"),
    "invite_team_members": (_ENTERPRISE, "team"),
    "get_team": (_PRO_PLUS, "team"),
    "list_team_folders": (_NOT_PUBLIC, "team"),
    "list_subfolders": (_NOT_PUBLIC, "folder"),
    "list_folder_files": (_NOT_PUBLIC, "folder"),
}

# Figma answers these with 404 "...or the endpoint is not enabled".
_PRIVATE_APP_404_TOOLS = {"duplicate_file", "invite_team_members"}

_ENTERPRISE_403_MEANINGS = (
    ("limited by figma plan",
     "The file is not in a Figma Enterprise plan; this API is Enterprise-only."),
    ("incorrect account type",
     "The signed-in user's seat can't use this API (reads need an organization member; "
     "variable writes need a Full seat or admin; guests can't use the API)."),
    ("invalid scope",
     "The Figma connection wasn't granted the scope this endpoint needs "
     "(file_variables:read / file_variables:write, or library_analytics:read) — "
     "reconnect Figma and grant it."),
    ("insufficient file permissions",
     "Writing variables needs edit access to the file."),
    ("api only available for design files",
     "The file is not a Figma Design file."),
)


def _err(result_class, tlog, code, message, status, retriable=False, retry_after=None):
    tlog.failure(code, message)
    return result_class(
        success=False, statusCode=status, retriable=retriable,
        retry_after_seconds=retry_after,
        error=ToolError(code=code, message=message),
    )


def _handle_request_exc(result_class, tlog, exc):
    if isinstance(exc, requests.ConnectTimeout):
        tlog.failure("UPSTREAM_ERROR", "Connection timeout")
        return result_class(success=False, statusCode=408, retriable=False,
            error=ToolError(code="UPSTREAM_ERROR", message="Connection timeout"))
    if isinstance(exc, requests.ReadTimeout):
        tlog.failure("UPSTREAM_ERROR", "Read timeout")
        return result_class(success=False, statusCode=504, retriable=False,
            error=ToolError(code="UPSTREAM_ERROR", message="Read timeout"))
    if isinstance(exc, requests.RequestException):
        tlog.failure("UPSTREAM_ERROR", "Network error")
        return result_class(success=False, statusCode=503, retriable=True,
            error=ToolError(code="UPSTREAM_ERROR", message=str(exc)))
    # Must precede ValueError — ValidationError subclasses it.
    if isinstance(exc, pydantic.ValidationError):
        tlog.failure("UPSTREAM_ERROR", "Response validation failed")  # str(exc) embeds response field values — never log it
        return result_class(success=False, statusCode=502, retriable=False,
            error=ToolError(code="UPSTREAM_ERROR",
                            message="Upstream response did not match the expected schema"))
    # CredentialError subclasses Exception, not ValueError.
    if isinstance(exc, (CredentialError, ValueError)):
        tlog.failure("AUTH_ERROR", str(exc))
        return result_class(success=False, statusCode=401, retriable=False,
            error=ToolError(code="AUTH_ERROR", message=str(exc)))
    tlog.failure("SERVER_ERROR", str(exc))  # log full detail internally
    return result_class(success=False, statusCode=500, retriable=False,
        error=ToolError(code="SERVER_ERROR", message="Unexpected server error"))


def _figma_message(data) -> str:
    # {status, err} | {status, error: true, message} | non-JSON fallback {error: "<text>"}
    if isinstance(data, dict):
        for key in ("err", "message", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:_MAX_MSG]
    return ""


def _required_scope(figma_msg: str) -> str | None:
    match = _SCOPE_RE.search(figma_msg)
    return match.group(1).rstrip(".,;") if match else None


def _default_explanation(status, figma_msg, details):
    if status == 401:
        if "missing credentials" in figma_msg.lower():
            return ("Figma did not accept the connection's token. Besides an absent or expired "
                    "token, this also happens when the endpoint doesn't accept this token type "
                    "(some endpoints only accept OAuth or plan access tokens).")
        return "Figma rejected the connection's token — reconnect Figma."
    if status == 403:
        scope = _required_scope(figma_msg)
        if scope:
            details["required_scope"] = scope
            requirement = _PRIVATE_ONLY_SCOPES.get(scope)
            if requirement:
                return (f"This endpoint needs the `{scope}` scope, which Figma only grants to "
                        f"{requirement}. If this connection was made through a public OAuth app, "
                        "that is the cause — reconnect with your organization's private OAuth app.")
            return (f"The Figma connection wasn't granted the `{scope}` scope this endpoint "
                    "needs — reconnect Figma and grant it.")
    if status == 429:
        return "Figma rate limit reached."
    return None


def _upstream_err(result_class, tlog, status, data, retry_after=None, explanation=None):
    retriable = status in (429, 500, 502, 503)
    code = "AUTH_ERROR" if status in (401, 403) else "UPSTREAM_ERROR"
    tlog.failure(code, f"HTTP {status}")
    figma_msg = _figma_message(data)
    details = {"figma_status": status}
    if figma_msg:
        details["figma_message"] = figma_msg
    default = _default_explanation(status, figma_msg, details)
    if explanation is None:
        explanation = default
    elif status == 401 and default and "missing credentials" in figma_msg.lower():
        explanation = f"{explanation} {default}"
    said = f"{status} {figma_msg}" if figma_msg else f"HTTP {status}"
    if explanation:
        msg = f"{explanation} Figma said: {said}"
    else:
        msg = f"Figma returned HTTP {status}: {figma_msg}" if figma_msg else f"Figma returned HTTP {status}"
    if status == 429:
        if retry_after is not None:
            msg += f". Retry after {retry_after} seconds"
        link = data.get(UPGRADE_LINK_KEY) if isinstance(data, dict) else None
        if link:
            details["upgrade_link"] = link
            msg += f". A higher seat or plan raises the limit: {link}"
    return result_class(
        success=False, statusCode=status, retriable=retriable,
        retry_after_seconds=retry_after,
        error=ToolError(code=code, message=msg, details=details),
    )


def _private_app_err(result_class, tlog, tool, status, data, retry_after=None):
    spec = _PRIVATE_APP_TOOLS.get(tool)
    statuses = (401, 403, 404) if tool in _PRIVATE_APP_404_TOOLS else (401, 403)
    if spec is None or status not in statuses:
        return _upstream_err(result_class, tlog, status, data, retry_after)
    scope = _required_scope(_figma_message(data))
    if scope and scope not in _PRIVATE_ONLY_SCOPES:
        return _upstream_err(result_class, tlog, status, data, retry_after)
    requirement, resource = spec
    explanation = (
        f"Figma refused `{tool}`. This endpoint only works when Figma is connected through "
        f"{requirement}. If this connection was made through a public OAuth app, that is the "
        "cause — reconnect with your organization's private OAuth app. Otherwise the signed-in "
        f"user lacks permission for this {resource}."
    )
    return _upstream_err(result_class, tlog, status, data, retry_after, explanation=explanation)


def _enterprise_api_err(result_class, tlog, status, data, retry_after=None):
    if status != 403:
        return _upstream_err(result_class, tlog, status, data, retry_after)
    figma_msg = _figma_message(data)
    if _required_scope(figma_msg):
        return _upstream_err(result_class, tlog, status, data, retry_after)
    lowered = figma_msg.lower()
    for needle, meaning in _ENTERPRISE_403_MEANINGS:
        if needle in lowered:
            return _upstream_err(result_class, tlog, status, data, retry_after,
                                 explanation=meaning)
    return _upstream_err(result_class, tlog, status, data, retry_after)
