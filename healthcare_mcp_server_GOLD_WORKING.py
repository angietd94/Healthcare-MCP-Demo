#!/usr/bin/env python3
"""
Healthcare MCP Server using FastMCP
Rewritten for proper MCP SSE protocol compliance
"""

import httpx
import json
import asyncio
from typing import Dict, Any, List, Optional
import fastmcp as mcp

# Configure server
mcp = mcp.FastMCP("Healthcare MCP Server")

# Backend service configuration
HEALTHCARE_BASE_URL = "http://localhost:3002"

async def call_backend_api(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call the Node.js backend service"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{HEALTHCARE_BASE_URL}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Backend service timeout", "code": -32603}
    except httpx.RequestError as e:
        return {"error": f"Backend service unavailable: {e}", "code": -32603}
    except Exception as e:
        return {"error": f"Unexpected error: {e}", "code": -32603}

@mcp.tool()
async def fda_drug_lookup(drug_name: str, search_type: str = "general") -> str:
    """
    Look up FDA drug information
    
    Args:
        drug_name: Name of the drug to search for
        search_type: Type of search (general, label, adverse_events)
    """
    result = await call_backend_api("/api/fda", {
        "drug_name": drug_name,
        "search_type": search_type
    })
    
    if "error" in result:
        return json.dumps({"error": result["error"]})
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def pubmed_search(query: str, max_results: int = 5, date_range: str = "") -> str:
    """
    Search PubMed for medical literature
    
    Args:
        query: Search query for medical literature
        max_results: Maximum number of results to return (default: 5)
        date_range: Limit by years (e.g. '5') (default: "")
    """
    result = await call_backend_api("/api/pubmed", {
        "query": query,
        "max_results": max_results,
        "date_range": date_range
    })
    
    if "error" in result:
        return json.dumps({"error": result["error"]})
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def health_topics(topic: str, language: str = "en") -> str:
    """
    Get health topic information from Health.gov
    
    Args:
        topic: Health topic to search for
        language: Language code (en or es) (default: "en")
    """
    result = await call_backend_api("/api/health-topics", {
        "topic": topic,
        "language": language
    })
    
    if "error" in result:
        return json.dumps({"error": result["error"]})
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def clinical_trials_search(condition: str, status: str = "recruiting", max_results: int = 10) -> str:
    """
    Search for clinical trials
    
    Args:
        condition: Medical condition or disease
        status: Trial status (recruiting, completed, active, not_recruiting, all) (default: "recruiting")
        max_results: Maximum number of results (default: 10)
    """
    result = await call_backend_api("/api/clinical-trials", {
        "condition": condition,
        "status": status,
        "max_results": max_results
    })
    
    if "error" in result:
        return json.dumps({"error": result["error"]})
    
    return json.dumps(result, indent=2)

@mcp.tool()
async def lookup_icd_code(code: str = "", description: str = "", max_results: int = 10) -> str:
    """
    Look up ICD-10 codes and medical terminology
    
    Args:
        code: ICD-10 code to look up (optional)
        description: Condition to search for (optional)
        max_results: Maximum number of results (default: 10)
    """
    params = {"max_results": max_results}
    if code:
        params["code"] = code
    if description:
        params["description"] = description
        
    result = await call_backend_api("/api/icd", params)
    
    if "error" in result:
        return json.dumps({"error": result["error"]})
    
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    # Use proper MCP SSE transport as recommended by Tim Fan
    mcp.run(transport="sse", host="0.0.0.0", port=4000)
