# MCP Healthcare Server

A Model Context Protocol (MCP) server that provides healthcare-related tools including FDA drug lookups, PubMed searches, health topics, clinical trials, and ICD-10 code lookups.

## 🚀 Quick Start

### Installation

1. **Clone or copy the files:**
   - [`healthcare_mcp_server.py`](healthcare_mcp_server.py) - Main server application
   - [`launch_script.sh`](launch_script.sh) - Deployment script

2. **Deploy the server:**
   ```bash
   sudo bash launch_script.sh healthcare_mcp_server.py
   ```

### Testing

```bash
# Check server health
curl http://localhost:4000/health

# Test SSE endpoint (should show event: endpoint and data: /sse/message?sessionId=...)
curl -sN -H 'Accept: text/event-stream' http://localhost:4000/sse | head -n 5
```

## 🔧 Recent Fixes & Root Cause Analysis

### TL;DR
The `/sse` endpoint was returning `null` with `Content-Type: application/json`, preventing SnapLogic from receiving the endpoint line needed to start JSON-RPC communication. This caused "Error listing tools... timed out" errors.

### Root Causes Fixed

1. **Wrong SSE behavior**: The `/sse` handler was sending JSON instead of the expected Server-Sent Events format
2. **Module path confusion**: systemd/uvicorn imported a different module copy, so live server didn't have intended `/sse` code
3. **Custom signal handler**: Produced extra SystemExit/CancelledError noise on restarts

### What Was Changed

#### 1. Fixed SSE Implementation
- **Before**: Returned JSON with `Content-Type: application/json`
- **After**: Proper SSE format with `Content-Type: text/event-stream`:
  ```
  event: endpoint
  data: /sse/message?sessionId=<64hex>
  
  event: ping
  data: ping
  ```

#### 2. Hardened systemd Configuration
- **Before**: Used direct Python execution with potential module conflicts
- **After**: Proper Uvicorn command with hardened paths:
  ```ini
  WorkingDirectory=/opt/healthcare-mcp
  Environment=PYTHONPATH=/opt/healthcare-mcp
  Environment=PATH=/opt/healthcare-mcp/venv/bin
  ExecStart=/opt/healthcare-mcp/venv/bin/uvicorn healthcare_mcp_server:app --host 0.0.0.0 --port 4000 --log-level debug --access-log --app-dir /opt/healthcare-mcp
  ```

#### 3. Removed Custom Signal Handler
- **Before**: Custom SIGINT/SIGTERM handler caused noisy restarts
- **After**: Let Uvicorn handle shutdowns cleanly

## 🛠️ Available Tools

The server provides 5 healthcare tools:

### 1. FDA Drug Lookup
```json
{
  "name": "fda_drug_lookup",
  "description": "Look up FDA drug information",
  "parameters": {
    "drug_name": "string (required)",
    "search_type": "general|label|adverse_events (default: general)"
  }
}
```

### 2. PubMed Search
```json
{
  "name": "pubmed_search", 
  "description": "Search PubMed for medical literature",
  "parameters": {
    "query": "string (required)",
    "max_results": "integer (default: 5)",
    "date_range": "string (optional, e.g. '5' for last 5 years)"
  }
}
```

### 3. Health Topics
```json
{
  "name": "health_topics",
  "description": "Get health topic information from Health.gov", 
  "parameters": {
    "topic": "string (required)",
    "language": "en|es (default: en)"
  }
}
```

### 4. Clinical Trials Search
```json
{
  "name": "clinical_trials_search",
  "description": "Search for clinical trials",
  "parameters": {
    "condition": "string (required)",
    "status": "recruiting|completed|active|not_recruiting|all (default: recruiting)",
    "max_results": "integer (default: 10)"
  }
}
```

### 5. ICD-10 Code Lookup
```json
{
  "name": "lookup_icd_code",
  "description": "Look up ICD-10 codes and medical terminology",
  "parameters": {
    "code": "string (optional)",
    "description": "string (optional)",
    "max_results": "integer (default: 10)"
  }
}
```

## 🔌 API Endpoints

### Health Check
```bash
GET /health
```
Returns server status and available tools count.

### MCP Root
```bash
GET /
```
Returns server info, capabilities, and available tools.

### Server-Sent Events (SSE)
```bash
GET /sse
```
Establishes SSE connection and returns session endpoint:
```
event: endpoint
data: /sse/message?sessionId=<session_id>
```

### Message Handling
```bash
POST /sse/message?sessionId=<session_id>
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

## 🧪 Testing the MCP Protocol

### 1. Initialize Connection
```bash
# Get session ID from SSE
SESSION_ID=$(curl -sN -H 'Accept: text/event-stream' http://localhost:4000/sse | grep -m1 "data:" | cut -d'=' -f2)

# Initialize MCP
curl -X POST "http://localhost:4000/sse/message?sessionId=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {}
    }
  }'
```

### 2. List Tools
```bash
curl -X POST "http://localhost:4000/sse/message?sessionId=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

### 3. Call a Tool
```bash
curl -X POST "http://localhost:4000/sse/message?sessionId=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "fda_drug_lookup",
      "arguments": {
        "drug_name": "aspirin",
        "search_type": "general"
      }
    }
  }'
```

## 🏗️ Architecture

### Transport Layer
- **FastAPI** web framework
- **Server-Sent Events (SSE)** for real-time communication
- **Session-based** message routing
- **Async queue** system for message buffering

### Protocol Support
- **JSON-RPC 2.0** over SSE
- **MCP Protocol Version**: 2024-11-05
- **Capabilities**: Tools with listChanged support

### Backend Integration
- **HTTP client** (`httpx`) for healthcare API calls
- **Base URL**: `http://localhost:3002` (configurable)
- **Timeout**: 30 seconds per request

## 🐛 Troubleshooting

### Server Won't Start
```bash
# Check if port is in use
netstat -tlnp | grep :4000

# Check service status
sudo systemctl status healthcare-mcp

# View logs
sudo journalctl -u healthcare-mcp -f --no-pager
```

### SSE Connection Issues
```bash
# Test SSE manually
curl -vN -H 'Accept: text/event-stream' http://localhost:4000/sse

# Should return:
# HTTP/1.1 200 OK
# content-type: text/event-stream
# 
# event: endpoint
# data: /sse/message?sessionId=<64hex>
```

### Tool Execution Failures
```bash
# Check backend service
curl http://localhost:3002/health

# Check specific API endpoint
curl "http://localhost:3002/api/fda?drug_name=aspirin"
```

### SnapLogic Integration Issues
1. **Verify SSE format**: Must be `text/event-stream`, not `application/json`
2. **Check endpoint path**: Must be relative (`/sse/message?sessionId=...`)
3. **Confirm MCP protocol**: Must support JSON-RPC 2.0

## 📝 Configuration

### Environment Variables
- `HOST`: Server host (default: `0.0.0.0`)
- `SERVER_PORT`: Server port (default: `4000`)
- `HEALTHCARE_BASE_URL`: Backend API URL (default: `http://localhost:3002`)
- `MCP_PROTOCOL_VERSION`: Protocol version (default: `2024-11-05`)
- `PING_SEC`: SSE ping interval (default: `10` seconds)

### systemd Service
Location: `/etc/systemd/system/healthcare-mcp.service`

View configuration:
```bash
sudo systemctl cat healthcare-mcp
```

## 🔒 Security Notes

- Server runs on all interfaces (`0.0.0.0:4000`)
- No authentication implemented (add reverse proxy with auth if needed)
- Uses system Python virtual environment in `/opt/healthcare-mcp/venv`
- Service runs with default systemd security restrictions

## 📖 MCP Specification

This server implements the Model Context Protocol (MCP) specification:
- **Protocol Version**: 2024-11-05
- **Transport**: Server-Sent Events (SSE)
- **Message Format**: JSON-RPC 2.0
- **Capabilities**: Tools with change notifications

For more details, see the [MCP specification](https://spec.modelcontextprotocol.io/).

## 🧪 Automated Testing

### Quick Test
```bash
./quick_test.sh [host] [port]
```
Example:
```bash
./quick_test.sh localhost 4000
./quick_test.sh 13.37.217.70 4000
```

### Comprehensive Test Suite
```bash
./test_mcp_server.sh [host] [port]
```

This runs a complete test suite including:
- Process and port checks
- Health endpoint validation
- SSE format verification
- MCP protocol tests (initialize, tools/list, tool calls)
- Response analysis

Expected output for working server:
```
🎉 ALL QUICK TESTS PASSED!
```

## 📞 Remote Testing

For testing from your local machine to a remote server:

```bash
# Test remote server
./quick_test.sh 13.37.217.70 4000

# Manual remote tests - CORRECT format (single http://)
curl -v http://13.37.217.70:4000/health
curl -vN -H 'Accept: text/event-stream' http://13.37.217.70:4000/sse --max-time 5

# ❌ WRONG (double http://):
# curl -vN -H 'Accept: text/event-stream' http://http://13.37.217.70:4000/sse

# ✅ CORRECT (single http://):
# curl -vN -H 'Accept: text/event-stream' http://13.37.217.70:4000/sse
```

## 🔍 Debug Logging

The server now includes comprehensive debug logging:

- **Client information**: IP addresses, User-Agent headers
- **Request details**: Content-Type, body length, payload parsing
- **SSE lifecycle**: Connection open/close, message delivery, ping events
- **MCP protocol**: Message handling, responses, auto tools/list
- **Session management**: Queue operations, pending messages

### View Debug Logs
```bash
# Live logs
sudo journalctl -u healthcare-mcp -f --no-pager

# Recent logs with debug level
sudo journalctl -u healthcare-mcp --since "1 hour ago" --no-pager

# Filter for specific session
sudo journalctl -u healthcare-mcp | grep "sid=abc123"
```
