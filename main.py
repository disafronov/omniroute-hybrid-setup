#!/usr/bin/env python3
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from subprocess import CalledProcessError, run  # nosec
from typing import Any, NoReturn, cast

API_KEY = os.environ.get("LOCAL_API_KEY")
CLOUD_KEY = os.environ.get("CLOUD_API_KEY")
CLOUD_URL = os.environ.get("CLOUD_BASE_URL")
LOCAL_URL = os.environ.get("LOCAL_BASE_URL")
OLLAMA_URL = os.environ.get("LOCAL_OLLAMA_URL", "http://host.docker.internal:11434/v1")

LOCAL_CODING = os.environ.get("LOCAL_CODING")
LOCAL_FAST = os.environ.get("LOCAL_FAST")
LOCAL_REASONING = os.environ.get("LOCAL_REASONING")


def fail(msg: str) -> NoReturn:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def req(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    if API_KEY is None:
        raise AssertionError("API_KEY not set")
    url = f"{LOCAL_URL}{path}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
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
    if not API_KEY:
        fail("set LOCAL_API_KEY (local omniroute API key)")
    if not CLOUD_KEY:
        fail("set CLOUD_API_KEY (upstream omniroute API key)")
    if not CLOUD_URL:
        fail("set CLOUD_BASE_URL (upstream omniroute base URL)")
    if not LOCAL_URL:
        fail("set LOCAL_BASE_URL (local omniroute base URL)")
    if not LOCAL_CODING:
        fail("set LOCAL_CODING (ollama model for coding combo)")
    if not LOCAL_FAST:
        fail("set LOCAL_FAST (ollama model for fast combo)")
    if not LOCAL_REASONING:
        fail("set LOCAL_REASONING (ollama model for reasoning combo)")
    if (
        API_KEY is None
        or CLOUD_KEY is None
        or CLOUD_URL is None
        or LOCAL_URL is None
        or LOCAL_CODING is None
        or LOCAL_FAST is None
        or LOCAL_REASONING is None
    ):
        raise AssertionError("env vars not set")

    print("=== OmniRoute Hybrid Setup ===")

    # ── Step 0: Pull ollama models ──
    print("--- Step 0: Ensure ollama models are present ---")
    ollama_bin = shutil.which("ollama") or "ollama"
    try:
        r = run(
            [ollama_bin, "list"], capture_output=True, text=True, check=True
        )  # nosec
        existing = [
            line.split()[0] for line in r.stdout.strip().split("\n")[1:] if line.strip()
        ]
    except (CalledProcessError, FileNotFoundError):
        existing = []
    for model in [LOCAL_CODING, LOCAL_FAST, LOCAL_REASONING]:
        if model in existing:
            print(f"  {model} already exists, skipping")
        else:
            print(f"  Pulling {model}...")
            run([ollama_bin, "pull", model], check=True)  # nosec
    print()

    print(f"Local Base URL:    {LOCAL_URL}")
    print(f"Cloud Base URL:    {CLOUD_URL}")
    print(f"Local Ollama URL:  {OLLAMA_URL}")
    print(f"Coding model:      {LOCAL_CODING}")
    print(f"Fast model:        {LOCAL_FAST}")
    print(f"Reasoning model:   {LOCAL_REASONING}")
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
            "apiType": "responses",
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

    # ── Step 2: Ollama provider node + connection ──
    print("--- Step 2: Ollama provider ---")

    target_ollama = OLLAMA_URL.rstrip("/").lower()
    ollama_node_id = upsert_node(
        nodes,
        {
            "name": "Local Ollama",
            "prefix": "local_ollama",
            "apiType": "chat",
            "baseUrl": OLLAMA_URL,
            "type": "openai-compatible",
        },
        lambda n: (n.get("apiType") or "").lower() == "chat"
        and (n.get("baseUrl") or "").rstrip("/").lower()
        in (target_ollama, target_ollama + "/"),
    )

    ollama_conn_id = upsert_connection(
        ollama_node_id,
        {
            "name": "Local Ollama",
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

    TIERS = [
        ("auto/best-coding", "auto/best-coding", LOCAL_CODING),
        ("auto/best-fast", "auto/best-fast", LOCAL_FAST),
        ("auto/best-reasoning", "auto/best-reasoning", LOCAL_REASONING),
    ]

    combos_data = req("GET", "/api/combos")
    combo_list = (
        combos_data.get("combos", combos_data)
        if isinstance(combos_data, dict)
        else combos_data
    )

    for name, cloud_model, local_model in TIERS:
        print(f"Processing combo: {name}")

        safe = name.replace("/", "-")

        payload = {
            "name": name,
            "strategy": "priority",
            "models": [
                {
                    "id": f"{safe}-model-1-cloud",
                    "kind": "model",
                    "model": f"{cloud_node_id}/{cloud_model}",
                    "providerId": cloud_node_id,
                    "connectionId": cloud_conn_id,
                    "weight": 100,
                },
                {
                    "id": f"{safe}-model-2-ollama",
                    "kind": "model",
                    "model": f"{ollama_node_id}/{local_model}",
                    "providerId": ollama_node_id,
                    "connectionId": ollama_conn_id,
                    "weight": 0,
                },
            ],
        }

        existing_id = None
        for c in combo_list if isinstance(combo_list, list) else []:
            if c.get("name") == name:
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

    # ── Step 4: Smoke test ──
    print("--- Step 4: Smoke test ---")

    import urllib.request as url_req

    for model_name, combo_name in [
        (LOCAL_FAST, "auto/best-fast"),
        (LOCAL_CODING, "auto/best-coding"),
    ]:
        print(f"  Testing: {combo_name} ({model_name})")
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        base_body = {
            "model": combo_name,
            "messages": [{"role": "user", "content": "say hi in 2 words"}],
        }

        try:
            body = {**base_body, "stream": False}
            r = url_req.Request(LOCAL_URL + "/v1/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(r, timeout=120) as resp:
                data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                print(f"    ✓ non-streaming: {content!r}")
            else:
                print(f"    ✗ non-streaming: empty content")
                continue
        except Exception as e:
            print(f"    ✗ non-streaming: {e}")
            continue

        try:
            body = {**base_body, "stream": True}
            r = url_req.Request(LOCAL_URL + "/v1/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(r, timeout=120) as resp:
                first_line = resp.readline().decode().strip()
            if first_line.startswith("data: ") and "choices" in first_line:
                print(f"    ✓ streaming: first chunk received")
            else:
                print(f"    ? streaming: unexpected first line: {first_line[:80]}")
        except Exception as e:
            print(f"    ✗ streaming: {e}")

    print()

    print("=== Done ===")

    print()
    print("Manual smoke test:")
    print(f"  curl -s -H 'Authorization: Bearer {API_KEY}' -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"model\":\"auto/best-fast\",\"messages\":[{{\"role\":\"user\",\"content\":\"hi\"}}],\"stream\":false}}' \\")
    print(f"    {LOCAL_URL}/v1/chat/completions | python3 -m json.tool")


if __name__ == "__main__":
    main()
