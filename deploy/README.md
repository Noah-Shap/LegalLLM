# Deployment (C14)

Two targets, both reading secrets from the environment only (never from the repo):

| target | what runs | entry | secrets / env |
|---|---|---|---|
| **Hugging Face Space** (D4, the public demo) | Streamlit UI, extraction in-process | `deploy/hf_space/` | `ANTHROPIC_API_KEY`; optional `LEGALLM_DEFAULT_METHOD` (`llm-v5`; `llm-v3` is the faster, cheaper span-only choice), `LEGALLM_UI_MAX_PER_SESSION` (20), `LEGALLM_GUARD_MODE` (`flag`\|`block`) |
| **API container** (Render / Fly / Cloud Run / any Docker host) | FastAPI `POST /extract`, `GET /health` | `Dockerfile` | same, plus `LEGALLM_RATE_LIMIT_PER_MIN` (20), `LEGALLM_MAX_UPLOAD_MB` (20), `LEGALLM_REQUEST_LOG` |

Locally the extractors run on the claude.ai subscription through `LEGALLM_LLM_BACKEND=claude-cli`; a hosted demo
cannot use that login, so both targets use the Messages API (`LEGALLM_LLM_BACKEND=api`) and **need a funded
`ANTHROPIC_API_KEY`**. Cost per document at list prices: about $0.27 (llm-v2) / $0.33 (llm-v3) / $0.43 (llm-v5, the default:
structured record citations, ≈ 73 s per document); see `evals/RESULTS.md`. Without a key the UI and API still serve `rules_v2` and report
`llm_available: false` on `/health`.

## Hugging Face Space (Streamlit)

1. Create a Space: **Streamlit** SDK, hardware *CPU basic*, name e.g. `legal-facts-extraction`.
2. Copy the three files in `deploy/hf_space/` (`README.md` with the Space front-matter, `app.py`,
   `requirements.txt`) to the Space repo root and push. `requirements.txt` installs this repo from GitHub `main`
   (`legallm[api,label]`), so the Space tracks the published code; pin a tag instead of `@main` for a frozen demo.
3. Space **Settings → Variables and secrets**: secret `ANTHROPIC_API_KEY`; variables `LEGALLM_LLM_BACKEND=api`,
   `LEGALLM_DEFAULT_METHOD=llm-v5`, `LEGALLM_UI_MAX_PER_SESSION=20`.
4. Open the Space, run `rules_v2` on a brief to check the build, then `llm-v5`.
5. Put the Space URL in the README (C16) and keep the Space *public* only after step 4 — R3 applies.

Limits: the UI caps requests per browser session (`LEGALLM_UI_MAX_PER_SESSION`) and refuses `llm-*` methods when
no key is configured; request metadata goes to `logs/requests.jsonl` inside the Space container (ephemeral) —
never the document text.

## API container

```bash
docker build -t legallm-api .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-... legallm-api
curl -s localhost:8000/health
curl -s -F file=@brief.pdf -F method=llm-v5 localhost:8000/extract | jq .result.extraction.facts_span.start
```

On Render: *New → Web Service → Docker*, add the env vars above as secrets, health check path `/health`. The
container listens on `$PORT`. Rate limiting is in-process (per client IP, sliding minute window); put a real
limiter in front of it if the service is exposed beyond a demo.

## What is deliberately not deployed

The CourtListener pipeline (R5), the eval harness, the judge, and the labeler stay local: they need the data
directory, the resolver cache, and (for the judge) the subscription backend.
