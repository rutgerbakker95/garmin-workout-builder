# Garmin Workout Builder

This ChatGPT/Codex plugin turns a planned cycling workout into Garmin Connect workout JSON. Import the generated file through the Chrome extension **Share your Garmin Connect workout**; this project does not connect to Garmin accounts or APIs.

## What it supports

- Warmup, intervals, recovery, cooldown, and single-level repeat blocks.
- FTP percentage ranges and steps with no power target.
- A short instruction in the generated ChatGPT summary; embedding it in Garmin waits for a proven reference export.
- Duration calculated from the authored steps, including repeat iterations.

## Run locally

Create an internal workout JSON using the contract in [workout-contract.md](skills/garmin-workout/references/workout-contract.md), then run:

```bash
python3 skills/garmin-workout/scripts/export_workout.py \
  --input workout.json \
  --output workout.garmin.json
```

The command prints the file path and calculated duration as JSON. It leaves no output file when validation fails. The public template at `skills/garmin-workout/assets/garmin-reference.json` is included by default. It contains synthetic identifiers and no original user profile data. Use `--reference /path/to/export.json` only to explicitly override it for local testing. The sanitized template still needs a live Garmin import test.

## Upload to ChatGPT

Package only `skills/garmin-workout/`, including its public `assets/garmin-reference.json`, as a ZIP with a top-level `garmin-workout/` folder. Exclude Python caches. Upload it through **Plugins → Skills → Create → Upload from your computer**. The ZIP can be shared; generated ZIPs remain excluded from version control.

The skill resolves its scripts and reference within its own folder and requires Python execution. Verify a generated download in ChatGPT after uploading; local export tests do not verify cloud execution or Garmin import.

## MCP server on Vercel

`server.py` exposes a stateless Streamable HTTP MCP endpoint at `/mcp` using the official Python MCP SDK. Vercel detects the FastAPI application; `vercel.json` selects that framework and `.python-version` selects Python 3.12. The CLI and uploaded skill keep working independently.

Tools:

- `get_workout_contract`: returns the input format, without Garmin DTO fields.
- `create_workout`: validates an internal workout object using the existing exporter and returns its name, duration, and a download URL valid for 15 minutes.

Downloads use the bundled public template with synthetic account and workout identifiers. Access remains configured as a **personal, single-user server**; making the template public does not disable authentication. MCP requires OAuth and accepts only the configured user's subject. Downloads use encrypted, expiring bearer links: anyone holding a link can download that export until it expires. Treat links and request logs as private. No database, local output files, Garmin connection, or OpenAI API key is required.

### Local setup

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env.local
```

Fill in `.env.local` with the values described below, using `http://127.0.0.1:8000` as the local `PUBLIC_BASE_URL`. Load it with:

```bash
.venv/bin/python -m uvicorn server:app --env-file .env.local --host 127.0.0.1 --port 8000 --no-access-log
```

Without required configuration, requests return HTTP 503 rather than opening an unauthenticated exporter. With configuration, `/health` returns HTTP 200; unauthenticated `/mcp` requests return HTTP 401 with OAuth discovery metadata. Local tests use signed test tokens and synthetic Garmin fixtures, so a live identity provider is not needed to run the suite.

### Configure OAuth before deployment

Use an external OAuth/OIDC provider that supports authorization code with PKCE and OAuth authorization-server discovery. This repository implements the MCP **resource server**, not a login service. Provider setup is still required before the ChatGPT connection can work.

1. Register an API/resource audience for the stable MCP URL, such as `https://your-project.vercel.app/mcp`, with the `workouts:export` scope and RS256 JWT access tokens.
2. Register the ChatGPT OAuth client, or enable dynamic client registration if supported. For a manually registered client, enter its client ID and secret in ChatGPT's advanced OAuth settings. Register the exact redirect URI shown by ChatGPT with the provider.
3. Ensure access tokens contain `iss`, `aud`, `sub`, `exp`, and a space-delimited `scope` including `workouts:export`. The provider must issue the configured audience; ID tokens are not a substitute for API access tokens.
4. Set `OAUTH_ISSUER` exactly as issued (including any trailing slash), `OAUTH_JWKS_URL`, `OAUTH_AUDIENCE`, and `OAUTH_ALLOWED_SUBJECT` to your own exact user `sub`. Other users are rejected even if they can log in to the same provider.

### Prepare Vercel and connect ChatGPT

1. Import this repository as a Vercel project using its root directory and the FastAPI framework. Deploy only when ready; preparing these files does not deploy anything.
2. Add all variables from `.env.example` in Vercel. Set `PUBLIC_BASE_URL` to the stable HTTPS origin, without `/mcp`. The public Garmin template is bundled automatically; no `GARMIN_REFERENCE_JSON` variable is needed. ZIPs, local environment files, and legacy private root-level reference files are excluded from deployment uploads.
3. Generate `DOWNLOAD_ENCRYPTION_KEY` once with the command in `.env.example`. Keep the same key and reference across instances so issued downloads survive cold starts. Rotating the key invalidates existing download links.
4. Deploy and verify `/health`, the HTTP 401 response from `/mcp`, and `/.well-known/oauth-protected-resource/mcp`. ChatGPT must be able to reach the service without a Vercel login interstitial; configure deployment protection accordingly while retaining application OAuth.
5. In ChatGPT, open **Plugins → App maken**, enter `https://your-project.vercel.app/mcp`, and select **OAuth**. Complete your provider's login and test a workout request in a new conversation.
6. Open the returned download and perform a Garmin extension import before treating the deployment as verified. Nothing is imported into Garmin automatically.

The SDK's tool discovery and calls, token validation, error responses, and downloads are tested locally. Vercel deployment, a real provider's OAuth flow, ChatGPT rendering, and Garmin import require live acceptance testing. This is preparation for a personal MCP connection, not publication in the public plugin directory.

References: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [ChatGPT MCP connections](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## Validate

```bash
.venv/bin/python -m unittest discover -s tests -v
python3 /Users/rutgerbakker/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

The test suite checks the 90-minute 3×10 reference workout, reference-template DTO mapping, no-target output, the CLI failure boundary, and the MCP/OAuth/download flow. The live acceptance test imports generated examples with the Chrome extension and re-exports them from Garmin Connect.
