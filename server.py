#!/usr/bin/env python3
"""MCP Server for Figma API."""

import logging
import os

import uvicorn
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP
from fastmcp_credentials import CredentialMiddleware, HeaderCredentialBackend
from starlette.middleware.cors import CORSMiddleware

from figma_mcp.config import configure_logging
from figma_mcp.tools import register_tools

configure_logging()
logger = logging.getLogger("figma-mcp-server")

# Skip gateway credential middleware when a local token is provided via env var
_middleware = []
if not os.environ.get("FIGMA_ACCESS_TOKEN"):
    backend = HeaderCredentialBackend()
    _middleware.append(CredentialMiddleware(backend, "oauth"))

mcp = FastMCP("MewCP Figma MCP Server", middleware=_middleware)
register_tools(mcp)

# ASGI app — used both for local uvicorn and hosted deployments (Vercel, etc.)
app = mcp.http_app(path="/mcp", transport="streamable-http", stateless_http=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))

    logger.info("=" * 60)
    logger.info("Figma MCP Server Starting")
    logger.info(f"Listening on http://{host}:{port}/mcp")
    logger.info("=" * 60)

    uvicorn.run(app, host=host, port=port)
