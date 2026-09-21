"""Personal Garmin export service: authenticated, stateless MCP on Vercel."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
import jwt
from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel

SKILL = Path(__file__).resolve().parent / "skills" / "garmin-workout"
sys.path.insert(0, str(SKILL / "scripts"))
from garmin import GarminReferenceError, to_garmin_workout  # noqa: E402
from workout import WorkoutValidationError, duration_seconds, validate_workout  # noqa: E402

DOWNLOAD_TTL = 900
REQUIRED_ENV = (
    "PUBLIC_BASE_URL", "DOWNLOAD_ENCRYPTION_KEY",
    "OAUTH_ISSUER", "OAUTH_JWKS_URL", "OAUTH_AUDIENCE", "OAUTH_ALLOWED_SUBJECT",
)


class WorkoutDownload(BaseModel):
    workout_name: str
    duration_seconds: int
    download_url: str
    expires_in_seconds: int


class OAuthVerifier:
    """Validate provider-issued access tokens for this personal resource server."""

    def __init__(self, settings):
        self.settings = settings
        self.jwks = jwt.PyJWKClient(settings["OAUTH_JWKS_URL"], timeout=5)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            key = await asyncio.to_thread(self.jwks.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token, key.key, algorithms=["RS256"],
                issuer=self.settings["OAUTH_ISSUER"],
                audience=self.settings["OAUTH_AUDIENCE"],
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            if claims["sub"] != self.settings["OAUTH_ALLOWED_SUBJECT"]:
                return None
            scope = claims.get("scope", "")
            if not isinstance(scope, str):
                return None
            return AccessToken(
                token=token, client_id=claims.get("azp") or claims.get("client_id") or claims["sub"],
                subject=claims["sub"], scopes=scope.split(), expires_at=claims["exp"],
                resource=self.settings["PUBLIC_BASE_URL"] + "/mcp",
                claims={"iss": claims["iss"]},
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            return None


def create_app(settings=None, *, token_verifier=None):
    settings = dict(os.environ if settings is None else settings)
    missing = [name for name in REQUIRED_ENV if not settings.get(name)]
    if missing:
        closed_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @closed_app.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
        async def unconfigured(path: str):
            return JSONResponse({"error": "Server configuration incomplete", "missing": missing}, status_code=503)

        return closed_app

    base = settings["PUBLIC_BASE_URL"].rstrip("/")
    settings["PUBLIC_BASE_URL"] = base
    origin = urlsplit(base)
    if (origin.scheme != "https" and not (
        origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}
    )) or origin.path or origin.query or origin.fragment or origin.username or not origin.hostname:
        raise ValueError("PUBLIC_BASE_URL must be an HTTPS origin (HTTP localhost is allowed).")
    for name in ("OAUTH_ISSUER", "OAUTH_JWKS_URL"):
        if urlsplit(settings[name]).scheme != "https":
            raise ValueError(f"{name} must use HTTPS.")
    reference = json.loads((SKILL / "assets" / "garmin-reference.json").read_text())
    cipher = Fernet(settings["DOWNLOAD_ENCRYPTION_KEY"].encode())
    scope = settings.get("OAUTH_REQUIRED_SCOPE") or "workouts:export"
    mcp = MCPServer(
        "Garmin Workout Builder",
        instructions="Call get_workout_contract before create_workout. Ask for missing workout details; never invent FTP. Return the download URL and calculated duration. This creates a file, not an import into Garmin.",
        token_verifier=token_verifier or OAuthVerifier(settings),
        auth=AuthSettings(
            issuer_url=settings["OAUTH_ISSUER"], resource_server_url=base + "/mcp",
            required_scopes=[scope], validate_token_resource=True,
        ),
    )
    annotations = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

    @mcp.tool(annotations=annotations)
    def get_workout_contract() -> str:
        """Read the supported cycling workout JSON format before exporting a workout."""
        return (SKILL / "references" / "workout-contract.md").read_text()

    @mcp.tool(annotations=annotations)
    def create_workout(workout: dict) -> WorkoutDownload:
        """Validate and export a cycling workout using the get_workout_contract schema.

        Pass the internal workout object, not Garmin DTO fields. Supports warmup,
        interval, recovery, cooldown and at most one non-nested repeat block.
        Returns a private download link valid for 15 minutes. No Garmin account
        is contacted and no workout is saved to Garmin.
        """
        try:
            normalized = validate_workout(workout)
            to_garmin_workout(normalized, reference)  # Check template compatibility before issuing a link.
            payload = json.dumps(workout, allow_nan=False, separators=(",", ":")).encode()
        except (WorkoutValidationError, GarminReferenceError, ValueError) as error:
            raise ToolError(str(error)) from error
        # Encrypt the authored document, not the larger bundled Garmin reference.
        token = cipher.encrypt(payload).decode()
        if len(token) > 6000:
            raise ToolError("Workout is too large for a download link; shorten its text or step list.")
        return WorkoutDownload(
            workout_name=normalized["name"], duration_seconds=duration_seconds(normalized),
            download_url=f"{base}/downloads/{token}/workout.json", expires_in_seconds=DOWNLOAD_TTL,
        )

    mcp_app = mcp.streamable_http_app(
        stateless_http=True, json_response=True, max_request_body_size=65536,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=[origin.netloc], allowed_origins=[base],
        ),
    )

    @asynccontextmanager
    async def lifespan(app):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    application = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    @application.get("/downloads/{token}/workout.json")
    async def download(token: str):
        if len(token) > 6000:
            raise HTTPException(404, "Download unavailable or expired")
        try:
            document = json.loads(cipher.decrypt(token.encode(), ttl=DOWNLOAD_TTL))
        except (InvalidToken, ValueError):
            raise HTTPException(404, "Download unavailable or expired") from None
        exported = to_garmin_workout(validate_workout(document), reference)
        return Response(
            json.dumps(exported, ensure_ascii=False, allow_nan=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="workout.json"',
                "Cache-Control": "private, no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    application.mount("/", mcp_app)
    return application


app = create_app()
