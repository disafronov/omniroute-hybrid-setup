# omniroute-hybrid-setup

Local OmniRoute (Docker) acting as a proxy in front of a cloud OmniRoute
with fallback to local ollama models when the cloud is unavailable.

## How it works

```
Claude Code (or any client)
  → localhost:20128 (Docker: omniroute container)
    → auto/best-* combo (priority routing)
      → 1. Cloud OmniRoute
      → 2. (fallback) Ollama local (host.docker.internal:11434/v1)
```

## Requirements

- Docker (compose v2)
- [ollama](https://ollama.com/) with models pulled
- Access to an upstream OmniRoute API

## Quick start

```bash
# 1. Start local OmniRoute
#    OMNIROUTE_API_KEY — from shell env (not from project .env)
OMNIROUTE_API_KEY=ololo docker compose up -d

# 2. Make sure ollama is running and models are available
ollama list

# 3. Configure combos (cloud → ollama)
LOCAL_API_KEY=ololo CLOUD_API_KEY="sk-..." bash setup.sh
```

## Combos

The script creates 3 priority combos with a primary cloud target and ollama fallback:

| Combo                | Cloud model              | Local model         |
|----------------------|--------------------------|---------------------|
| `auto/best-coding`   | `auto/best-coding`       | `qwen2.5-coder:14b` |
| `auto/best-fast`     | `auto/best-fast`         | `qwen2.5:7b`        |
| `auto/best-reasoning`| `auto/best-reasoning`    | `deepseek-r1:14b`   |

## Environment variables

| Variable           | Required | Description                              |
|--------------------|----------|------------------------------------------|
| `CLOUD_API_KEY`    | **yes**  | API key for the upstream cloud OmniRoute |
| `LOCAL_API_KEY`    | **yes**  | API key for the local OmniRoute instance |

Tip: use a `.env` file to store `LOCAL_API_KEY`. Docker compose reads it automatically.
