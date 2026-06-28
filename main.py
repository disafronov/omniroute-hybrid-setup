#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, NoReturn, cast

CLOUD_KEY = os.environ.get("OMNIROUTE_CLOUD_API_KEY")
CLOUD_URL = os.environ.get("OMNIROUTE_CLOUD_BASE_URL")

LOCAL_KEY = os.environ.get("OMNIROUTE_LOCAL_API_KEY")
LOCAL_URL = os.environ.get("OMNIROUTE_LOCAL_BASE_URL")

LOCAL_RUNTIME_URL = os.environ.get(
    "OMNIROUTE_LOCAL_RUNTIME_URL", "http://host.docker.internal:11434/v1"
)

LOCAL_RUNTIME_CODING = os.environ.get("OMNIROUTE_LOCAL_RUNTIME_MODEL_CODING")
LOCAL_RUNTIME_FAST = os.environ.get("OMNIROUTE_LOCAL_RUNTIME_MODEL_FAST")
LOCAL_RUNTIME_REASONING = os.environ.get("OMNIROUTE_LOCAL_RUNTIME_MODEL_REASONING")
LOCAL_RUNTIME_VISION = os.environ.get("OMNIROUTE_LOCAL_RUNTIME_MODEL_VISION")


def fail(msg: str) -> NoReturn:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def req(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    if LOCAL_KEY is None:
        raise AssertionError("LOCAL_KEY not set")
    url = f"{LOCAL_URL}{path}"
    headers = {
        "Authorization": f"Bearer {LOCAL_KEY}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    try:
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(r) as resp:  # nosec
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(
            f"  HTTP {e.code} on {method} {path}: {e.read().decode()}", file=sys.stderr
        )
    except Exception as e:
        print(f"  Error on {method} {path}: {e}", file=sys.stderr)
    return {}


def find_connection(node_id: str) -> str | None:
    data = req("GET", "/api/providers")
    providers: Any = (
        data
        if isinstance(data, list)
        else data.get("providers", data.get("connections", []))
    )
    for p in providers:
        if p.get("provider") == node_id:
            return cast(str, p.get("id", ""))
    return None


def upsert_node(
    nodes: list[dict[str, Any]],
    create_body: dict[str, Any],
    search: Callable[[dict[str, Any]], bool],
) -> str:
    for n in nodes:
        if search(n):
            node_id: str = n["id"]
            print(f"  Syncing existing node: {node_id}")
            req("PUT", f"/api/provider-nodes/{node_id}", create_body)
            return node_id
    print(f"Creating {create_body['name']} provider node...")
    resp = req("POST", "/api/provider-nodes", create_body)
    node_id = resp.get("node", {}).get("id", "")
    print(f"  Created node: {node_id}")
    return node_id


def upsert_connection(node_id: str, body: dict[str, Any]) -> str:
    conn_id = find_connection(node_id)
    if conn_id:
        print(f"  Syncing existing connection: {conn_id}")
    else:
        print(f"Creating {body['name']} connection...")
        resp = req("POST", "/api/providers", {**body, "provider": node_id})
        conn_id = resp.get("connection", {}).get("id", "")
        print(f"  Created connection: {conn_id}")
    req("PUT", f"/api/providers/{conn_id}", {**body, "provider": node_id})
    return conn_id


def main() -> None:
    if not LOCAL_KEY:
        fail("set OMNIROUTE_LOCAL_API_KEY (local omniroute API key)")
    if not CLOUD_KEY:
        fail("set OMNIROUTE_CLOUD_API_KEY (upstream omniroute API key)")
    if not CLOUD_URL:
        fail("set OMNIROUTE_CLOUD_BASE_URL (upstream omniroute base URL)")
    if not LOCAL_URL:
        fail("set OMNIROUTE_LOCAL_BASE_URL (local omniroute base URL)")
    if not LOCAL_RUNTIME_CODING:
        fail("set OMNIROUTE_LOCAL_RUNTIME_MODEL_CODING (runtime model for coding combo)")
    if not LOCAL_RUNTIME_FAST:
        fail("set OMNIROUTE_LOCAL_RUNTIME_MODEL_FAST (runtime model for fast combo)")
    if not LOCAL_RUNTIME_REASONING:
        fail("set OMNIROUTE_LOCAL_RUNTIME_MODEL_REASONING (runtime reasoning model)")
    if not LOCAL_RUNTIME_VISION:
        fail("set OMNIROUTE_LOCAL_RUNTIME_MODEL_VISION (runtime model for vision combo)")
    if (
        LOCAL_KEY is None
        or CLOUD_KEY is None
        or CLOUD_URL is None
        or LOCAL_URL is None
        or LOCAL_RUNTIME_CODING is None
        or LOCAL_RUNTIME_FAST is None
        or LOCAL_RUNTIME_REASONING is None
        or LOCAL_RUNTIME_VISION is None
    ):
        raise AssertionError("env vars not set")

    print("=== OmniRoute Hybrid Setup ===")

    print(f"Local Base URL:    {LOCAL_URL}")
    print(f"Cloud Base URL:    {CLOUD_URL}")
    print(f"Local Runtime URL: {LOCAL_RUNTIME_URL}")
    print(f"Coding model:      {LOCAL_RUNTIME_CODING}")
    print(f"Fast model:        {LOCAL_RUNTIME_FAST}")
    print(f"Reasoning model:   {LOCAL_RUNTIME_REASONING}")
    print(f"Vision model:      {LOCAL_RUNTIME_VISION}")
    print()

    # ── Step 1: Cloud parent provider node + connection ──
    print("--- Step 1: Cloud parent provider ---")

    nodes_data = req("GET", "/api/provider-nodes")
    nodes = nodes_data.get("nodes", [])

    target = CLOUD_URL.rstrip("/").lower()
    cloud_node_id = upsert_node(
        nodes,
        {
            "name": "Cloud OmniRoute",
            "prefix": "cloud_omniroute",
            "apiType": "chat",
            "baseUrl": CLOUD_URL,
            "type": "openai-compatible",
        },
        lambda n: (n.get("baseUrl") or "").rstrip("/").lower()
        in (target, target + "/"),
    )

    cloud_conn_id = upsert_connection(
        cloud_node_id,
        {
            "name": "Cloud OmniRoute",
            "authType": "apikey",
            "apiKey": CLOUD_KEY,
            "priority": 1,
        },
    )
    print()

    # ── Step 2: Runtime provider node + connection ──
    print("--- Step 2: Runtime provider ---")

    target_runtime = LOCAL_RUNTIME_URL.rstrip("/").lower()
    runtime_node_id = upsert_node(
        nodes,
        {
            "name": "Local Runtime",
            "prefix": "local_runtime",
            "apiType": "chat",
            "baseUrl": LOCAL_RUNTIME_URL,
            "type": "openai-compatible",
        },
        lambda n: (n.get("apiType") or "").lower() == "chat"
        and (n.get("baseUrl") or "").rstrip("/").lower()
        in (target_runtime, target_runtime + "/"),
    )

    runtime_conn_id = upsert_connection(
        runtime_node_id,
        {
            "name": "Local Runtime",
            "authType": "apikey",
            "apiKey": "empty",
            "priority": 1,
        },
    )

    print("  Testing cloud connection...")
    req("POST", f"/api/providers/{cloud_conn_id}/test")
    print()

    # ── Step 3: Create/update tier combos ──
    print("--- Step 3: Tier combos ---")

    # Cloud combo names (auto/best-*) → which runtime model to use as fallback.
    # Local combo name = cloud name with "auto/" prefix stripped (no slashes).
    COMBO_FALLBACK: dict[str, str] = {
        "auto/best-coding": LOCAL_RUNTIME_CODING,
        "auto/best-coding-fast": LOCAL_RUNTIME_CODING,
        "auto/best-fast": LOCAL_RUNTIME_FAST,
        "auto/best-vision": LOCAL_RUNTIME_VISION,
        "auto/best-reasoning": LOCAL_RUNTIME_REASONING,
        "auto/best-chat": LOCAL_RUNTIME_FAST,
    }

    combos_data = req("GET", "/api/combos")
    combo_list = (
        combos_data.get("combos", combos_data)
        if isinstance(combos_data, dict)
        else combos_data
    )

    for name, local_model in COMBO_FALLBACK.items():
        local_name = name.removeprefix("auto/")
        print(f"Processing combo: {local_name} (cloud: {name})")

        payload = {
            "name": local_name,
            "strategy": "priority",
            "models": [
                {
                    "id": f"{local_name}-model-1-cloud",
                    "kind": "model",
                    "model": f"{cloud_node_id}/{name}",
                    "providerId": cloud_node_id,
                    "connectionId": cloud_conn_id,
                    "weight": 100,
                },
                {
                    "id": f"{local_name}-model-2-runtime",
                    "kind": "model",
                    "model": f"{runtime_node_id}/{local_model}",
                    "providerId": runtime_node_id,
                    "connectionId": runtime_conn_id,
                    "weight": 0,
                },
            ],
        }

        existing_id = None
        for c in combo_list if isinstance(combo_list, list) else []:
            if c.get("name") == local_name:
                existing_id = c.get("id", "")
                break

        if existing_id:
            print(f"  Updating existing combo (id={existing_id})...")
            req("PUT", f"/api/combos/{existing_id}", payload)
            print("  Updated")
        else:
            print("  Creating new combo...")
            req("POST", "/api/combos", payload)
            print("  Created")

    print()
    print("=== Done ===")
    print()
    print("Manual smoke test:")
    tokens = (
        "curl -s",
        f"-H 'Authorization: Bearer {LOCAL_KEY}'",
        "-H 'Content-Type: application/json'",
    )
    print(f"  {' '.join(tokens)} \\")
    print(
        '    -d \'{"model":"best-fast",'
        '"messages":[{"role":"user","content":"hi"}],'
        '"stream":false}\' \\'
    )
    print(f"    {LOCAL_URL}/v1/chat/completions | python3 -m json.tool")


if __name__ == "__main__":
    main()
