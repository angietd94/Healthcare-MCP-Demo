#!/usr/bin/env bash

# Quick MCP Server Test
HOST="${1:-localhost}"
PORT="${2:-4000}"
HOSTPORT="http://${HOST}:${PORT}"

echo "=== Quick MCP Server Test ==="
echo "Testing: $HOSTPORT"
echo

# Test 1: Health
echo "1. Health Check:"
curl -sf --max-time 5 "$HOSTPORT/health" | jq -r '.status // "ERROR"' 2>/dev/null || echo "FAILED"
echo

# Test 2: SSE Format
echo "2. SSE Format:"
SSE_OUTPUT=$(timeout 3 curl -sN -H 'Accept: text/event-stream' "$HOSTPORT/sse" 2>/dev/null | head -n 4)
if echo "$SSE_OUTPUT" | grep -q "event: endpoint" && echo "$SSE_OUTPUT" | grep -q "data: /sse/message"; then
    echo "✅ CORRECT SSE FORMAT"
    SESSION_ID=$(echo "$SSE_OUTPUT" | grep "data: /sse/message" | sed 's/.*sessionId=//')
    echo "Session ID: ${SESSION_ID:0:16}..."
else
    echo "❌ WRONG SSE FORMAT"
    echo "Got: $SSE_OUTPUT"
    exit 1
fi

# Test 3: Quick MCP Test
echo
echo "3. Quick MCP Test:"
PRIMARY_EP="${HOSTPORT}/sse/message?sessionId=${SESSION_ID}"

# Ping test
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PRIMARY_EP" --max-time 5)
if [[ "$HTTP_CODE" == "202" ]]; then
    echo "✅ MCP ENDPOINT RESPONDING (HTTP $HTTP_CODE)"
else
    echo "❌ MCP ENDPOINT FAILED (HTTP $HTTP_CODE)"
    exit 1
fi

# Initialize test
INIT_PAYLOAD='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}'
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PRIMARY_EP" -H 'Content-Type: application/json' -d "$INIT_PAYLOAD" --max-time 5)
if [[ "$HTTP_CODE" == "202" ]]; then
    echo "✅ MCP INITIALIZE OK (HTTP $HTTP_CODE)"
else
    echo "❌ MCP INITIALIZE FAILED (HTTP $HTTP_CODE)"
    exit 1
fi

echo
echo "🎉 ALL QUICK TESTS PASSED!"
echo "Full test command: ./test_mcp_server.sh $HOST $PORT"
echo
echo "🔧 CORRECT CURL COMMANDS:"
echo "  Health: curl -v http://$HOST:$PORT/health"
echo "  SSE:    curl -vN -H 'Accept: text/event-stream' http://$HOST:$PORT/sse"
echo
echo "❌ WRONG (double http://): curl -vN -H 'Accept: text/event-stream' http://http://$HOST:$PORT/sse"
echo "✅ RIGHT (single http://):  curl -vN -H 'Accept: text/event-stream' http://$HOST:$PORT/sse"
