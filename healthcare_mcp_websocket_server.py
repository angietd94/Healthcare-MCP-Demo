#!/usr/bin/env python3

import json
import asyncio
import logging
import sys
import signal
import requests
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/healthcare_mcp.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Healthcare MCP WebSocket Server",
    description="Model Context Protocol server for healthcare data with WebSocket support",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcare server base URL
HEALTHCARE_BASE_URL = "http://localhost:3002"
SERVER_PORT = 4000

# MCP Protocol Implementation
MCP_PROTOCOL_VERSION = "2024-11-05"

def make_request(endpoint: str, params: dict = None) -> Dict[Any, Any]:
    """Make a request to the healthcare server"""
    try:
        url = f"{HEALTHCARE_BASE_URL}{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

# MCP Server Capabilities
def get_server_capabilities():
    """Return MCP server capabilities"""
    return {
        "tools": {
            "listChanged": True
        },
        "resources": {
            "subscribe": False,
            "listChanged": False
        },
        "prompts": {
            "listChanged": False
        },
        "logging": {}
    }

# Available MCP Tools
def get_available_tools():
    """Return list of available MCP tools"""
    return [
        {
            "name": "fda_drug_lookup",
            "description": "Look up FDA drug information",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "drug_name": {
                        "type": "string",
                        "description": "Name of the drug to search for"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Type of search (general, label, adverse_events)",
                        "default": "general"
                    }
                },
                "required": ["drug_name"]
            }
        },
        {
            "name": "pubmed_search",
            "description": "Search PubMed for medical literature",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for medical literature"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    },
                    "date_range": {
                        "type": "string",
                        "description": "Limit to articles published within years (e.g. '5' for last 5 years)",
                        "default": ""
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "health_topics",
            "description": "Get health topic information from Health.gov",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Health topic to search for"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for content (en or es)",
                        "default": "en"
                    }
                },
                "required": ["topic"]
            }
        },
        {
            "name": "clinical_trials_search",
            "description": "Search for clinical trials",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "description": "Medical condition or disease to search for"
                    },
                    "status": {
                        "type": "string",
                        "description": "Trial status (recruiting, completed, active, not_recruiting, or all)",
                        "default": "recruiting"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["condition"]
            }
        },
        {
            "name": "lookup_icd_code",
            "description": "Look up ICD-10 codes and medical terminology",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "ICD-10 code to look up"
                    },
                    "description": {
                        "type": "string",
                        "description": "Medical condition description to search for"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                }
            }
        }
    ]

# MCP Tool Execution
async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an MCP tool"""
    logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")
    
    try:
        if tool_name == "fda_drug_lookup":
            result = make_request("/api/fda", {
                "drug_name": arguments.get("drug_name"),
                "search_type": arguments.get("search_type", "general")
            })
        elif tool_name == "pubmed_search":
            result = make_request("/api/pubmed", {
                "query": arguments.get("query"),
                "max_results": arguments.get("max_results", 5),
                "date_range": arguments.get("date_range", "")
            })
        elif tool_name == "health_topics":
            result = make_request("/api/health_finder", {
                "topic": arguments.get("topic"),
                "language": arguments.get("language", "en")
            })
        elif tool_name == "clinical_trials_search":
            result = make_request("/api/clinical_trials", {
                "condition": arguments.get("condition"),
                "status": arguments.get("status", "recruiting"),
                "max_results": arguments.get("max_results", 10)
            })
        elif tool_name == "lookup_icd_code":
            params = {"max_results": arguments.get("max_results", 10)}
            if arguments.get("code"):
                params["code"] = arguments["code"]
            if arguments.get("description"):
                params["description"] = arguments["description"]
            result = make_request("/api/medical_terminology", params)
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            "error": {
                "code": -32603,
                "message": f"Tool execution failed: {str(e)}"
            }
        }

# MCP Message Handler
async def handle_mcp_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming MCP JSON-RPC messages"""
    method = message.get("method")
    params = message.get("params", {})
    message_id = message.get("id")
    
    logger.info(f"Handling MCP message: {method} with ID: {message_id}")
    
    response = {
        "jsonrpc": "2.0",
        "id": message_id
    }
    
    try:
        if method == "initialize":
            response["result"] = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": get_server_capabilities(),
                "serverInfo": {
                    "name": "Healthcare MCP Server",
                    "version": "1.0.0"
                }
            }
        elif method == "tools/list":
            response["result"] = {
                "tools": get_available_tools()
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = await execute_tool(tool_name, arguments)
            response["result"] = result
        elif method == "ping":
            response["result"] = {}
        elif method == "notifications/initialized":
            # Client notifies server that initialization is complete
            logger.info("Client initialization complete")
            return None  # No response needed for notifications
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
    except Exception as e:
        logger.error(f"Error handling MCP message: {str(e)}")
        response["error"] = {
            "code": -32603,
            "message": f"Internal error: {str(e)}"
        }
    
    return response

@app.get("/")
async def root():
    """Root endpoint with MCP server information"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Healthcare MCP Server</title>
    </head>
    <body>
        <h1>Healthcare MCP Server</h1>
        <p><strong>Protocol:</strong> Model Context Protocol</p>
        <p><strong>Version:</strong> 1.0.0</p>
        <p><strong>WebSocket URL:</strong> ws://13.37.217.70:4000/sse</p>
        <p><strong>Health Check:</strong> <a href="/health">/health</a></p>
        <p><strong>Tools Available:</strong> 5</p>
        <ul>
            <li>fda_drug_lookup</li>
            <li>pubmed_search</li>
            <li>health_topics</li>
            <li>clinical_trials_search</li>
            <li>lookup_icd_code</li>
        </ul>
    </body>
    </html>
    """)

@app.websocket("/sse")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP protocol communication"""
    await websocket.accept()
    logger.info("WebSocket connection established for MCP protocol")
    
    # Send MCP server capabilities immediately upon connection
    server_init = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": get_server_capabilities(),
            "serverInfo": {
                "name": "Healthcare MCP Server",
                "version": "1.0.0"
            }
        }
    }
    await websocket.send_text(json.dumps(server_init))
    
    try:
        while True:
            # Receive message from client
            message_text = await websocket.receive_text()
            logger.info(f"Received MCP message: {message_text[:200]}...")
            
            try:
                message = json.loads(message_text)
                response = await handle_mcp_message(message)
                
                if response is not None:
                    response_text = json.dumps(response)
                    logger.info(f"Sending MCP response: {response_text[:200]}...")
                    await websocket.send_text(response_text)
                    
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    },
                    "id": None
                }
                await websocket.send_text(json.dumps(error_response))
                
    except WebSocketDisconnect:
        logger.info("MCP WebSocket connection disconnected")
    except Exception as e:
        logger.error(f"MCP WebSocket error: {str(e)}")

@app.get("/events")
async def sse_fallback():
    """SSE fallback endpoint for non-WebSocket clients"""
    
    async def event_stream():
        # Send initial server info
        server_info = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "serverInfo": {
                    "name": "Healthcare MCP Server",
                    "version": "1.0.0"
                },
                "capabilities": get_server_capabilities(),
                "tools": get_available_tools()
            }
        }
        yield f"data: {json.dumps(server_info)}\n\n"
        
        # Send periodic status
        while True:
            backend_health = make_request("/health")
            
            status_message = {
                "jsonrpc": "2.0",
                "method": "notifications/status",
                "params": {
                    "timestamp": datetime.now().isoformat(),
                    "status": "healthy" if "error" not in backend_health else "unhealthy",
                    "backend": backend_health,
                    "capabilities": get_server_capabilities(),
                    "tools_count": len(get_available_tools())
                }
            }
            
            yield f"data: {json.dumps(status_message)}\n\n"
            await asyncio.sleep(30)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    backend_health = make_request("/health")
    return {
        "status": "healthy" if "error" not in backend_health else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "protocol": "MCP",
        "version": MCP_PROTOCOL_VERSION,
        "backend": backend_health,
        "tools_available": len(get_available_tools()),
        "websocket_url": f"ws://13.37.217.70:{SERVER_PORT}/sse"
    }

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    logger.info(f"Starting Healthcare MCP WebSocket Server on port {SERVER_PORT}")
    try:
        uvicorn.run(
            "healthcare_mcp_websocket_server:app",
            host="0.0.0.0",
            port=SERVER_PORT,
            reload=False,
            access_log=True,
            log_level="info",
            ws_ping_interval=30,
            ws_ping_timeout=30
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)