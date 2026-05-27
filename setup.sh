#!/usr/bin/env bash
set -euo pipefail

# Idempotent setup: creates/updates cloud parent + ollama provider nodes
# and 3 tier combos (auto/best-coding, auto/best-fast, auto/best-reasoning).
# Safe to run multiple times.
#
# Usage:
#   CLOUD_API_KEY="sk-..." bash setup.sh
#   CLOUD_API_KEY="sk-..." LOCAL_API_KEY="ololo" bash setup.sh
#   CLOUD_API_KEY="sk-..." LOCAL_CODING="qwen2.5-coder:32b" bash setup.sh

LOCAL_API_KEY="${LOCAL_API_KEY:?set LOCAL_API_KEY (local omniroute API key)}"
CLOUD_API_KEY="${CLOUD_API_KEY:?set CLOUD_API_KEY (upstream omniroute API key)}"
LOCAL_BASE_URL="${LOCAL_BASE_URL:-http://127.0.0.1:20128}"
CLOUD_BASE_URL="${CLOUD_BASE_URL:?set CLOUD_BASE_URL (upstream omniroute base URL)}"
LOCAL_OLLAMA_URL="${LOCAL_OLLAMA_URL:-http://host.docker.internal:11434/v1}"

LOCAL_CODING="${LOCAL_CODING:-qwen2.5-coder:14b}"
LOCAL_FAST="${LOCAL_FAST:-qwen2.5:7b}"
LOCAL_REASONING="${LOCAL_REASONING:-deepseek-r1:14b}"

AUTH="Authorization: Bearer $LOCAL_API_KEY"

echo "=== OmniRoute Hybrid Setup ==="

# ── 0. Pull ollama models ──
echo "--- Step 0: Ensure ollama models are present ---"
for model in "$LOCAL_CODING" "$LOCAL_FAST" "$LOCAL_REASONING"; do
  if ollama list 2>/dev/null | grep -q "^${model}[[:space:]]"; then
    echo "  $model already exists, skipping"
  else
    echo "  Pulling $model..."
    ollama pull "$model"
  fi
done
echo ""
echo "Local Base URL:    $LOCAL_BASE_URL"
echo "Cloud Base URL:    $CLOUD_BASE_URL"
echo "Local Ollama URL:  $LOCAL_OLLAMA_URL"
echo "Coding model:      $LOCAL_CODING"
echo "Fast model:        $LOCAL_FAST"
echo "Reasoning model:   $LOCAL_REASONING"
echo ""

# ── 1. Cloud parent provider node + connection ──
echo "--- Step 1: Cloud parent provider ---"

CLOUD_NODE_ID=$(curl -sf -H "$AUTH" "$LOCAL_BASE_URL/api/provider-nodes" 2>/dev/null | \
  python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
nodes = d.get('nodes', [])
for n in nodes:
    base = (n.get('baseUrl') or '').lower()
    if 'omniroute.cyberbrain.cc' in base:
        print(n['id'])
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

CLOUD_PREFIX="cloud_omniroute"
if [ -z "$CLOUD_NODE_ID" ]; then
  echo "Creating cloud provider node..."
  CLOUD_NODE_ID=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d '{
  "name": "Cloud OmniRoute",
  "prefix": "'"$CLOUD_PREFIX"'",
  "apiType": "responses",
  "baseUrl": "'"$CLOUD_BASE_URL"'",
  "type": "openai-compatible"
}' "$LOCAL_BASE_URL/api/provider-nodes" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('node',{}).get('id',''))")
  echo "Created node: $CLOUD_NODE_ID"
else
  echo "Using existing node: $CLOUD_NODE_ID"
fi

CLOUD_CONN_ID=$(curl -sf -H "$AUTH" "$LOCAL_BASE_URL/api/providers" 2>/dev/null | \
  python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
providers = d if isinstance(d, list) else d.get('providers', d.get('connections', []))
for p in providers:
    if p.get('provider') == '$CLOUD_NODE_ID':
        print(p.get('id', ''))
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

if [ -z "$CLOUD_CONN_ID" ]; then
  echo "Creating cloud connection..."
  CLOUD_CONN_ID=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d '{
  "provider": "'"$CLOUD_NODE_ID"'",
  "name": "Cloud OmniRoute",
  "authType": "apikey",
  "apiKey": "'"$CLOUD_API_KEY"'",
  "priority": 1
}' "$LOCAL_BASE_URL/api/providers" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('connection',{}).get('id',''))")
  echo "Created connection: $CLOUD_CONN_ID"
else
  echo "Using existing connection: $CLOUD_CONN_ID"
fi

# Always sync API key
curl -sf -X PUT -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"apiKey": "'"$CLOUD_API_KEY"'"}' \
  "$LOCAL_BASE_URL/api/providers/$CLOUD_CONN_ID" > /dev/null 2>&1 || true
echo ""

# ── 2. Ollama provider node + connection ──
echo "--- Step 2: Ollama provider ---"

OLLAMA_NODE_ID=$(curl -sf -H "$AUTH" "$LOCAL_BASE_URL/api/provider-nodes" 2>/dev/null | \
  python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
nodes = d.get('nodes', [])
for n in nodes:
    base = (n.get('baseUrl') or '').lower()
    at = (n.get('apiType') or '').lower()
    if at == 'chat' and ('ollama' in base or 'host.docker.internal' in base or '11434' in base):
        print(n['id'])
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

if [ -z "$OLLAMA_NODE_ID" ]; then
  echo "Creating ollama provider node..."
  OLLAMA_NODE_ID=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d '{
  "name": "Ollama Local Chat",
  "prefix": "ollama_local",
  "apiType": "chat",
  "baseUrl": "'"$LOCAL_OLLAMA_URL"'",
  "type": "openai-compatible"
}' "$LOCAL_BASE_URL/api/provider-nodes" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('node',{}).get('id',''))")
  echo "Created node: $OLLAMA_NODE_ID"
else
  echo "Using existing node: $OLLAMA_NODE_ID"
fi

OLLAMA_CONN_ID=$(curl -sf -H "$AUTH" "$LOCAL_BASE_URL/api/providers" 2>/dev/null | \
  python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
providers = d if isinstance(d, list) else d.get('providers', d.get('connections', []))
for p in providers:
    if p.get('provider') == '$OLLAMA_NODE_ID':
        print(p.get('id', ''))
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

  if [ -z "$OLLAMA_CONN_ID" ]; then
    echo "Creating ollama connection..."
    OLLAMA_CONN_ID=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
      -d '{
    "provider": "'"$OLLAMA_NODE_ID"'",
    "name": "Ollama Local Chat",
    "authType": "apikey",
    "apiKey": "empty",
    "priority": 1,
    "providerSpecificData": {
      "disableStreamOptions": true
    }
  }' "$LOCAL_BASE_URL/api/providers" | \
      python3 -c "import sys,json; print(json.load(sys.stdin).get('connection',{}).get('id',''))")
    echo "Created connection: $OLLAMA_CONN_ID"
  else
    echo "Using existing connection: $OLLAMA_CONN_ID"
  fi

  # Always sync disableStreamOptions
  curl -sf -X PUT -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"providerSpecificData": {"disableStreamOptions": true}}' \
    "$LOCAL_BASE_URL/api/providers/$OLLAMA_CONN_ID" > /dev/null 2>&1 || true

  # Test cloud connection to clear stale error state
  echo "  Testing cloud connection..."
  curl -sf -X POST -H "$AUTH" "$LOCAL_BASE_URL/api/providers/$CLOUD_CONN_ID/test" > /dev/null 2>&1 || true
echo ""

# ── 3. Create/update tier combos ──
echo "--- Step 3: Tier combos ---"

TIERS=(
  "auto/best-coding:auto/best-coding:$LOCAL_CODING"
  "auto/best-fast:auto/best-fast:$LOCAL_FAST"
  "auto/best-reasoning:auto/best-reasoning:$LOCAL_REASONING"
)

for entry in "${TIERS[@]}"; do
  IFS=":" read -r name cloud_model local_model <<< "$entry"
  echo "Processing combo: $name"

  local_model_str="${OLLAMA_NODE_ID}/${local_model}"
  cloud_model_str="${CLOUD_NODE_ID}/${cloud_model}"

  existing_id=$(curl -sf -H "$AUTH" "$LOCAL_BASE_URL/api/combos" 2>/dev/null | \
    python3 -c "
  import sys, json
  d = json.loads(sys.stdin.read())
  combos = d.get('combos', d) if isinstance(d, dict) else d
  for c in combos if isinstance(combos, list) else []:
      if c.get('name') == '$name':
          print(c.get('id', ''))
          sys.exit(0)
  print('')
  " 2>/dev/null || echo "")

  safe_name=$(echo "$name" | sed 's/[^a-zA-Z0-9_-]/-/g')

  if [ -n "$existing_id" ]; then
    echo "  Updating existing combo (id=$existing_id)..."
    curl -sf -X PUT -H "$AUTH" -H "Content-Type: application/json" \
      -d "$(cat << PAYLOAD
{
  "models": [
    {
      "id": "${safe_name}-model-1-cloud",
      "kind": "model",
      "model": "${cloud_model_str}",
      "providerId": "${CLOUD_NODE_ID}",
      "connectionId": "${CLOUD_CONN_ID}",
      "weight": 0
    },
    {
      "id": "${safe_name}-model-2-ollama",
      "kind": "model",
      "model": "${local_model_str}",
      "providerId": "${OLLAMA_NODE_ID}",
      "connectionId": "${OLLAMA_CONN_ID}",
      "weight": 0
    }
  ]
}
PAYLOAD
)" "$LOCAL_BASE_URL/api/combos/$existing_id" > /dev/null
    echo "  Updated"
  else
    echo "  Creating new combo..."
    curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
      -d "$(cat << CREATEPAYLOAD
{
  "name": "${name}",
  "strategy": "priority",
  "models": [
    {
      "id": "${safe_name}-model-1-cloud",
      "kind": "model",
      "model": "${cloud_model_str}",
      "providerId": "${CLOUD_NODE_ID}",
      "connectionId": "${CLOUD_CONN_ID}",
      "weight": 0
    },
    {
      "id": "${safe_name}-model-2-ollama",
      "kind": "model",
      "model": "${local_model_str}",
      "providerId": "${OLLAMA_NODE_ID}",
      "connectionId": "${OLLAMA_CONN_ID}",
      "weight": 0
    }
  ]
}
CREATEPAYLOAD
)" "$LOCAL_BASE_URL/api/combos" > /dev/null
    echo "  Created"
  fi
done

echo ""
echo "=== Done ==="
echo ""
echo "To test:"
echo "  curl -s -H 'Authorization: Bearer $LOCAL_API_KEY' -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\":\"auto/best-coding\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}' \\"
echo "    $LOCAL_BASE_URL/v1/responses | python3 -m json.tool"
