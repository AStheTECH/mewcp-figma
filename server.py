#!/usr/bin/env python3
"""MewCP Figma MCP Server."""

import logging

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from fastmcp_credentials import CredentialMiddleware, HeaderCredentialBackend

from figma_mcp.cli import parse_args
from figma_mcp.config import BREAKING_CHANGES, SERVER_VERSION, configure_logging
from figma_mcp.tools import register_tools

configure_logging()
logger = logging.getLogger("figma-mcp")

backend = HeaderCredentialBackend()
mcp = FastMCP("MewCP Figma MCP Server", version=SERVER_VERSION,
              middleware=[CredentialMiddleware(backend, "oauth")])

register_tools(mcp)


# /health MUST come before mcp.http_app() — routes are baked at http_app() time
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "service": mcp.name,
        "version": SERVER_VERSION,
        "breaking_changes": BREAKING_CHANGES,
    })


app = mcp.http_app(path="/mcp", transport="streamable-http", stateless_http=True)
# stateless_http=True is about HTTP session-affinity for horizontal scaling — a
# separate concern from the MCP protocol itself. With fastmcp-credentials>=0.2.0
# (Phase 8) — which controls the resolved fastmcp version, not requirements.txt's
# own bare `fastmcp` line — this same app speaks MCP's modern, stateless
# 2026-07-28 protocol automatically. No code changes needed here.


if __name__ == "__main__":
    args = parse_args()
    run_kwargs = {}
    if args.transport:
        run_kwargs["transport"] = args.transport
    if args.host:
        run_kwargs["host"] = args.host
    if args.port:
        run_kwargs["port"] = args.port
    try:
        mcp.run(**run_kwargs)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server crashed: %s", e, exc_info=True)
        raise
