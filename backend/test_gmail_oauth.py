import asyncio
import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx

import app as app_module
import gmail_oauth
from models import ExtractedOffer


def check_session_secret_setup():
    with tempfile.TemporaryDirectory() as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text("GEMINI_API_KEY=preserve-me\nSESSION_SECRET=\n", encoding="utf-8")
        with patch.object(app_module, "ENV_FILE", env_file), patch.dict(os.environ, {"SESSION_SECRET": ""}):
            app_module.ensure_session_secret()
            generated = os.environ["SESSION_SECRET"]
            lines = env_file.read_text(encoding="utf-8").splitlines()
        assert len(generated) >= 60
        assert lines[0] == "GEMINI_API_KEY=preserve-me"
        assert lines[-1] == f"SESSION_SECRET={generated}"


def _encoded_body(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


class FakeGoogleClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def post(self, url, data=None, headers=None):
        assert url == gmail_oauth.GOOGLE_TOKEN_URL
        token = "test-access-token"
        if data["grant_type"] == "refresh_token":
            assert data["refresh_token"] == "test-refresh-token"
            token = "refreshed-access-token"
        else:
            assert data["grant_type"] == "authorization_code"
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "access_token": token,
                "refresh_token": "test-refresh-token" if data["grant_type"] == "authorization_code" else None,
                "expires_in": 3600,
            },
            request=request,
        )

    async def get(self, url, params=None, headers=None):
        assert headers["Authorization"] in {
            "Bearer test-access-token",
            "Bearer refreshed-access-token",
        }
        request = httpx.Request("GET", url)
        if url.endswith("/messages"):
            assert params["maxResults"] == "15"
            assert "internship" in params["q"]
            return httpx.Response(200, json={"messages": [{"id": "message-1"}]}, request=request)
        assert url.endswith("/messages/message-1")
        return httpx.Response(
            200,
            json={
                "id": "message-1",
                "snippet": "An internship offer",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [
                        {"name": "From", "value": "Recruiter <jobs@example.org>"},
                        {"name": "Reply-To", "value": "reply@gmail.com"},
                        {"name": "Received-SPF", "value": "pass"},
                        {"name": "Authentication-Results", "value": "mx.example; dkim=fail"},
                        {"name": "Subject", "value": "Internship offer"},
                        {"name": "Date", "value": "Sat, 21 Nov 2026 10:00:00 +0000"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/html",
                            "body": {"data": _encoded_body("<p>HTML fallback</p>")},
                        },
                        {
                            "mimeType": "text/plain",
                            "body": {"data": _encoded_body("Role: Data Intern\nStipend: Rs 12,000")},
                        },
                    ],
                },
            },
            request=request,
        )


async def run_gmail_oauth_checks():
    check_session_secret_setup()
    test_config = {
        "SESSION_SECRET": "test-session-secret",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_REDIRECT_URI": gmail_oauth.DEFAULT_REDIRECT_URI,
    }
    gmail_oauth.sessions.clear()
    gmail_oauth.pending_states.clear()
    transport = httpx.ASGITransport(app=app_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch.dict(os.environ, test_config):
            with patch.object(gmail_oauth.httpx, "AsyncClient", FakeGoogleClient):
                start = await client.get("/auth/google/start")
                assert start.status_code == 302
                authorization = urlparse(start.headers["location"])
                params = parse_qs(authorization.query)
                assert authorization.netloc == "accounts.google.com"
                assert params["scope"] == [gmail_oauth.GMAIL_SCOPE]
                assert params["access_type"] == ["offline"]
                assert params["redirect_uri"] == [gmail_oauth.DEFAULT_REDIRECT_URI]
                state = params["state"][0]
                assert client.cookies.get(gmail_oauth.STATE_COOKIE) == state

                callback = await client.get(
                    "/auth/google/callback",
                    params={"code": "test-auth-code", "state": state},
                )
                assert callback.status_code == 303
                assert callback.headers["location"] == "/"
                assert "httponly" in callback.headers["set-cookie"].lower()
                assert client.cookies.get(gmail_oauth.SESSION_COOKIE)

                status = await client.get("/api/gmail/status")
                assert status.json() == {"configured": True, "connected": True}

                messages = await client.get("/api/gmail/messages")
                assert messages.status_code == 200
                message = messages.json()["messages"][0]
                assert message["sender"] == "Recruiter <jobs@example.org>"
                assert message["subject"] == "Internship offer"
                assert message["date"] == "Sat, 21 Nov 2026 10:00:00 +0000"
                assert message["snippet"] == "An internship offer"
                assert message["body"] == "Role: Data Intern\nStipend: Rs 12,000"
                session_id = next(iter(gmail_oauth.sessions))
                gmail_oauth.sessions[session_id].expires_at = 0
                refreshed = await client.get("/api/gmail/messages")
                assert refreshed.status_code == 200
                assert gmail_oauth.sessions[session_id].access_token == "refreshed-access-token"
                offer_text, header_flags = await gmail_oauth.load_gmail_offer_text(
                    session_id,
                    "message-1",
                )
                assert "Stipend: Rs 12,000" in offer_text
                assert header_flags == ["Reply-To does not match From", "DKIM failed"]

                captured_flags = []

                async def fake_extract_offer(text, hints):
                    assert "Role: Data Intern" in text
                    return ExtractedOffer(company="Example", role="Data Intern"), False

                async def fake_investigate(company, role, website, domain, progress):
                    return []

                async def fake_compose_report(offer, evidence, findings, flags, verdict, language, offer_text):
                    captured_flags.extend(flags)
                    return {
                        "verdict_level": verdict,
                        "headline": "Email reviewed",
                        "summary": "Email details were included.",
                        "claims": [],
                        "sources": [],
                        "cant_verify": [],
                        "do_this": [],
                        "ask_them": [],
                    }

                with (
                    patch.object(app_module, "extract_offer", fake_extract_offer),
                    patch.object(app_module, "investigate", fake_investigate),
                    patch.object(app_module, "process_evidence", lambda groups, offer: []),
                    patch.object(app_module, "build_findings", lambda offer, evidence, text: ([], [], "UNVERIFIED")),
                    patch.object(app_module, "compose_report", fake_compose_report),
                ):
                    started = await client.post(
                        "/analyze",
                        data={
                            "text": "Internship offer",
                            "gmail_message_id": "message-1",
                        },
                    )
                    assert started.status_code == 202
                    stream = await client.get(f"/stream/{started.json()['job_id']}")
                assert stream.status_code == 200
                assert "Email reviewed" in stream.text
                assert captured_flags == ["Reply-To does not match From", "DKIM failed"]

                disconnected = await client.post("/api/gmail/disconnect")
                assert disconnected.status_code == 200
                assert disconnected.json() == {"connected": False}
                status = await client.get("/api/gmail/status")
                assert status.json()["connected"] is False
                messages = await client.get("/api/gmail/messages")
                assert messages.status_code == 401
                assert messages.json()["detail"] == "Connect Gmail to view your messages."

                with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
                    unconfigured = await client.get("/api/gmail/status")
                    assert unconfigured.json() == {"configured": False, "connected": False}
                    start = await client.get("/auth/google/start")
                    assert start.headers["location"] == "/?gmail_error=not_configured"

    print("gmail_oauth: session secret, signed state, OAuth, email import, and disconnect passed")


if __name__ == "__main__":
    asyncio.run(run_gmail_oauth_checks())
