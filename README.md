# omniroute-hybrid-setup

Local [OmniRoute](https://github.com/diegosouzapw/OmniRoute) (Docker) acting as a proxy in front of a cloud one
with fallback to local runtime models when the cloud is unavailable.

## How it works

```text
Any client, including OpenCode agent)
  → localhost:20128 (Docker: omniroute container)
    → best-* combo (priority routing)
      → 1. Cloud OmniRoute (auto/best-* model)
      → 2. (fallback) Local runtime (host.docker.internal:11434/v1)

### OpenCode Integration

To use with OpenCode, configure your `opencode.json` to point to the local OmniRoute instance and use the combo names as model IDs:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "omniroute/best-coding",
  "small_model": "omniroute/best-fast",
  "provider": {
    "omniroute": {
      "options": {
        "baseUrl": "http://127.0.0.1:20128",
        "apiKey": "${OMNIROUTE_LOCAL_API_KEY}"
      }
    }
  }
}
```

Ensure `OMNIROUTE_LOCAL_API_KEY` is set in your environment or in the `opencode.json` directly.
```

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker (compose v2)
- Local runtime (e.g. Ollama, vLLM) with models pulled
- Access to an upstream OmniRoute API

## Combos

The script creates priority combos with a primary cloud target and runtime fallback.
Local models are set via `LOCAL_CODING`, `LOCAL_FAST`, `LOCAL_REASONING`, `LOCAL_VISION` — see [Environment variables](#environment-variables).

| Combo | Cloud model | Env var |
| --- | --- | --- |
| `best-coding` | `auto/best-coding` | `LOCAL_CODING` |
| `best-coding-fast` | `auto/best-coding-fast` | `LOCAL_CODING` |
| `best-fast` | `auto/best-fast` | `LOCAL_FAST` |
| `best-vision` | `auto/best-vision` | `LOCAL_VISION` |
| `best-reasoning` | `auto/best-reasoning` | `LOCAL_REASONING` |
| `best-chat` | `auto/best-chat` | `LOCAL_REASONING` |

## Environment variables

All variables — including models and endpoints — are set in [`.env.example`](.env.example).
Copy it and fill in your keys & other values:

```bash
cp env.example .env
```

| Variable | Description |
| --- | --- |
| `LOCAL_API_KEY` | API key for the local OmniRoute instance |
| `CLOUD_API_KEY` | API key for the upstream cloud OmniRoute |
| `CLOUD_BASE_URL` | Base URL of the upstream cloud OmniRoute |
| `LOCAL_BASE_URL` | Local OmniRoute URL |
| `LOCAL_RUNTIME_URL` | Runtime endpoint |
| `LOCAL_CODING` | Runtime model for coding combo |
| `LOCAL_FAST` | Runtime model for fast combo |
| `LOCAL_REASONING` | Runtime model for reasoning combo |
| `LOCAL_VISION` | Runtime model for vision combo |

## Run

```bash
# 1. Install runtime dependencies
make runtime

# 2. Start local OmniRoute (requires .env — see above)
docker compose up -d

# 3. Configure combos
make run
```
