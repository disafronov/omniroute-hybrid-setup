# omniroute-hybrid-setup

Local [OmniRoute](https://github.com/diegosouzapw/OmniRoute) (Docker) acting as a proxy in front of a cloud one
with fallback to local ollama models when the cloud is unavailable.

## How it works

```text
Claude Code (or any client)
  → localhost:20128 (Docker: omniroute container)
    → auto/best-* combo (priority routing)
      → 1. Cloud OmniRoute
      → 2. (fallback) Ollama local (host.docker.internal:11434/v1)
```

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker (compose v2)
- [ollama](https://ollama.com/) with models pulled
- Access to an upstream OmniRoute API

## Combos

The script creates priority combos with a primary cloud target and ollama fallback.
Local models are set via `LOCAL_CODING`, `LOCAL_FAST`, `LOCAL_REASONING`, `LOCAL_VISION` — see [Environment variables](#environment-variables).

| Combo | Cloud model | Env var |
| --- | --- | --- |
| `auto/best-coding` | `auto/best-coding` | `LOCAL_CODING` |
| `auto/best-fast` | `auto/best-fast` | `LOCAL_FAST` |
| `auto/best-reasoning` | `auto/best-reasoning` | `LOCAL_REASONING` |
| `auto/best-vision` | `auto/best-vision` | `LOCAL_VISION` |

## Environment variables

All variables — including models and endpoints — are set in [`.env.example`](.env.example).
Copy it and fill in your keys & other values:

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `LOCAL_API_KEY` | API key for the local OmniRoute instance |
| `CLOUD_API_KEY` | API key for the upstream cloud OmniRoute |
| `CLOUD_BASE_URL` | Base URL of the upstream cloud OmniRoute |
| `LOCAL_BASE_URL` | Local OmniRoute URL |
| `LOCAL_OLLAMA_URL` | Ollama endpoint |
| `LOCAL_CODING` | Ollama model for coding combo |
| `LOCAL_FAST` | Ollama model for fast combo |
| `LOCAL_REASONING` | Ollama model for reasoning combo |
| `LOCAL_VISION` | Ollama model for vision combo |

## Run

```bash
# 1. Install runtime dependencies
make runtime

# 2. Start local OmniRoute (requires .env — see above)
docker compose up -d

# 3. Configure combos
make run
```
