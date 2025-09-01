#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from typing import Optional, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------
# Config & Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("healthcare-mcp-fastmcp")

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "4000"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3002")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

# ---------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------
mcp = FastMCP("healthcare_mcp", host=HOST, port=PORT)

# Reusable HTTP client factory (one per call to keep it simple & safe)
def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": "healthcare-mcp/1.0"})

async def _backend_get(path: str, params: dict):
    """Proxy a GET to the backend and return parsed JSON (or raise)."""
    url = f"{BACKEND_URL}{path}"
    # remove None values
    params = {k: v for k, v in params.items() if v is not None}
    async with _make_client() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception as e:
            # If backend doesn't return JSON
            raise httpx.HTTPError(f"Invalid JSON from backend: {e}") from e

# ---------------------------------------------------------------------
# Schemas (for nicer prompts & validation)
# ---------------------------------------------------------------------
class FDALookupArgs(BaseModel):
    drug_name: str = Field(..., description="Name of the drug to search for")
    search_type: Literal["general", "label", "adverse_events"] = Field(
        "general", description="Type of search to perform"
    )

class PubMedArgs(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(5, description="Max results")
    date_range: Optional[str] = Field("", description="Limit by years (e.g. '5')")

class HealthTopicsArgs(BaseModel):
    topic: str = Field(..., description="Topic to search")
    language: Literal["en", "es"] = Field("en", description="Language")

class ClinicalTrialsArgs(BaseModel):
    condition: str = Field(..., description="Medical condition")
    status: str = Field("recruiting", description="recruiting, completed, etc.")
    max_results: int = Field(10, description="Max results")

class ICDLookupArgs(BaseModel):
    code: Optional[str] = Field(None, description="ICD-10 code")
    description: Optional[str] = Field(None, description="Condition description")
    max_results: int = Field(10, description="Max results")

# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------
@mcp.tool()
async def fda_drug_lookup(drug_name: str, search_type: Literal["general","label","adverse_events"]="general"):
    """
    Search FDA drug information database.
    Args:
      drug_name: Name of the drug to search for.
      search_type: One of ["general", "label", "adverse_events"].
    """
    try:
        args = FDALookupArgs(drug_name=drug_name, search_type=search_type)
        data = await _backend_get("/api/fda", args.model_dump())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except ValidationError as ve:
        return {"error": f"Invalid arguments: {ve}"}
    except httpx.HTTPError as e:
        log.error("FDA lookup error: %s", e)
        return {"error": f"Backend error: {e}"}

@mcp.tool()
async def pubmed_search(query: str, max_results: int = 5, date_range: str = ""):
    """
    Search PubMed for medical literature.
    Args:
      query: Search query.
      max_results: Max results.
      date_range: Limit by years (e.g. '5').
    """
    try:
        args = PubMedArgs(query=query, max_results=max_results, date_range=date_range)
        data = await _backend_get("/api/pubmed", args.model_dump())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except ValidationError as ve:
        return {"error": f"Invalid arguments: {ve}"}
    except httpx.HTTPError as e:
        log.error("PubMed search error: %s", e)
        return {"error": f"Backend error: {e}"}

@mcp.tool()
async def health_topics(topic: str, language: Literal["en","es"]="en"):
    """
    Get health topic information.
    Args:
      topic: Topic to search.
      language: 'en' or 'es'.
    """
    try:
        args = HealthTopicsArgs(topic=topic, language=language)
        data = await _backend_get("/api/health_finder", args.model_dump())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except ValidationError as ve:
        return {"error": f"Invalid arguments: {ve}"}
    except httpx.HTTPError as e:
        log.error("Health topics error: %s", e)
        return {"error": f"Backend error: {e}"}

@mcp.tool()
async def clinical_trials_search(condition: str, status: str = "recruiting", max_results: int = 10):
    """
    Search clinical trials database.
    Args:
      condition: Medical condition.
      status: recruiting, completed, etc.
      max_results: Max results.
    """
    try:
        args = ClinicalTrialsArgs(condition=condition, status=status, max_results=max_results)
        data = await _backend_get("/api/clinical_trials", args.model_dump())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except ValidationError as ve:
        return {"error": f"Invalid arguments: {ve}"}
    except httpx.HTTPError as e:
        log.error("Clinical trials error: %s", e)
        return {"error": f"Backend error: {e}"}

@mcp.tool()
async def lookup_icd_code(code: Optional[str] = None, description: Optional[str] = None, max_results: int = 10):
    """
    Look up ICD medical codes.
    Args:
      code: ICD-10 code (optional).
      description: Condition description (optional).
      max_results: Max results.
    """
    try:
        if not code and not description:
            return {"error": "Provide at least one of: code or description."}
        args = ICDLookupArgs(code=code, description=description, max_results=max_results)
        data = await _backend_get("/api/medical_terminology", args.model_dump())
        return json.dumps(data, ensure_ascii=False, indent=2)
    except ValidationError as ve:
        return {"error": f"Invalid arguments: {ve}"}
    except httpx.HTTPError as e:
        log.error("ICD lookup error: %s", e)
        return {"error": f"Backend error: {e}"}

# ---------------------------------------------------------------------
# Health tool (opcional, útil para pruebas desde el cliente MCP)
# ---------------------------------------------------------------------
@mcp.tool()
async def health():
    """
    Simple health check that also pings the backend /health if available.
    """
    ok = False
    try:
        async with _make_client() as client:
            r = await client.get(f"{BACKEND_URL}/health")
            ok = (r.status_code == 200)
    except Exception:
        ok = False
    return {
        "server": "ok",
        "backend": "ok" if ok else "unhealthy",
        "protocolVersion": "2024-11-05",
        "port": PORT,
    }

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # Transport SSE (FastMCP se encarga del endpoint /sse y /messages)
    # Esto es lo que funcionó en tu ejemplo del weather server.
    mcp.run(transport="sse")
