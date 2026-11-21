import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass
from email.header import decode_header, make_header
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from email_headers import email_header_flags


router = APIRouter()

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8000/auth/google/callback"
SESSION_COOKIE = "offercheck_gmail_session"
STATE_COOKIE = "offercheck_gmail_oauth_state"
STATE_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_EMAIL_BODY_CHARS = 20000
GMAIL_SEARCH_QUERY = "newer_than:30d {job internship offer recruiter hiring}"


@dataclass
class GmailSession:
    access_token: str
    refresh_token: str | None
    expires_at: float


sessions: dict[str, GmailSession] = {}
pending_states: dict[str, float] = {}


def _session_secret() -> bytes | None:
    value = os.getenv("SESSION_SECRET", "").strip()
    return value.encode("utf-8") if value else None


def _oauth_config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip() or DEFAULT_REDIRECT_URI
    return client_id, client_secret, redirect_uri


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signature(value: str, secret: bytes) -> str:
    digest = hmac.new(secret, value.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _create_state(secret: bytes) -> str:
    now = time.time()
    for state, expires_at in list(pending_states.items()):
        if expires_at <= now:
            pending_states.pop(state, None)

    payload = f"{int(now)}.{secrets.token_urlsafe(24)}"
    state = f"{_b64encode(payload.encode('utf-8'))}.{_signature(payload, secret)}"
    pending_states[state] = now + STATE_TTL_SECONDS
    return state


def _consume_state(state: str, secret: bytes) -> bool:
    expires_at = pending_states.pop(state, None)
    if expires_at is None or expires_at <= time.time():
        return False
    try:
        payload_part, supplied_signature = state.split(".", 1)
        payload = _b64decode(payload_part).decode("utf-8")
        issued_at = int(payload.split(".", 1)[0])
    except (ValueError, UnicodeDecodeError):
        return False
    if issued_at > time.time() or time.time() - issued_at > STATE_TTL_SECONDS:
        return False
    expected_signature = _signature(payload, secret)
    return hmac.compare_digest(supplied_signature, expected_signature)


def _session_id_from_cookie(cookie_value: str | None) -> str | None:
    secret = _session_secret()
    if not secret or not cookie_value:
        return None
    try:
        session_id, supplied_signature = cookie_value.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(supplied_signature, _signature(session_id, secret)):
        return None
    return session_id if session_id in sessions else None


def gmail_session_id_from_request(request: Request) -> str | None:
    return _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))


def _redirect_error(code: str) -> RedirectResponse:
    response = RedirectResponse(f"/?gmail_error={quote(code)}", status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/auth/google/callback")
    return response


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
    )


@router.get("/auth/google/start")
async def google_oauth_start():
    client_id, client_secret, redirect_uri = _oauth_config()
    secret = _session_secret()
    if not client_id or not client_secret:
        return _redirect_error("not_configured")
    if not secret:
        return _redirect_error("session_secret_missing")

    state = _create_state(secret)
    authorization_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': GMAIL_SCOPE,
        'access_type': 'offline',
        'include_granted_scopes': 'true',
        'prompt': 'consent',
        'state': state,
    }
    authorization_url = f"{GOOGLE_AUTHORIZE_URL}?{urlencode(authorization_params)}"
    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=redirect_uri.lower().startswith("https://"),
        samesite="lax",
        path="/auth/google/callback",
    )
    return response


@router.get("/auth/google/callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    secret = _session_secret()
    cookie_state = request.cookies.get(STATE_COOKIE)
    if (
        not secret
        or not state
        or not cookie_state
        or not hmac.compare_digest(state, cookie_state)
        or not _consume_state(state, secret)
    ):
        return _redirect_error("state_invalid")
    if error:
        return _redirect_error("cancelled")
    if not code:
        return _redirect_error("authorization_failed")

    client_id, client_secret, redirect_uri = _oauth_config()
    if not client_id or not client_secret:
        return _redirect_error("not_configured")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
            token_data = token_response.json()
    except httpx.HTTPError:
        return _redirect_error("token_exchange_failed")
    except ValueError:
        return _redirect_error("token_exchange_failed")

    if not isinstance(token_data, dict):
        return _redirect_error("token_exchange_failed")
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        return _redirect_error("token_exchange_failed")

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = GmailSession(
        access_token=access_token,
        refresh_token=token_data.get("refresh_token"),
        expires_at=time.time() + int(token_data.get("expires_in", 3600)),
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        f"{session_id}.{_signature(session_id, secret)}",
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=redirect_uri.lower().startswith("https://"),
        samesite="lax",
        path="/",
    )
    response.delete_cookie(STATE_COOKIE, path="/auth/google/callback")
    return response


@router.get("/api/gmail/status")
async def gmail_status(request: Request):
    client_id, client_secret, _ = _oauth_config()
    configured = bool(client_id and client_secret and _session_secret())
    session_id = _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    return {"configured": configured, "connected": session_id is not None}


async def _refresh_access_token(session_id: str) -> GmailSession:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Connect Gmail to view your messages.")
    if session.expires_at > time.time() + 30:
        return session
    if not session.refresh_token:
        sessions.pop(session_id, None)
        raise HTTPException(
            status_code=401,
            detail="Your Gmail session expired. Connect Gmail again to continue.",
        )

    client_id, client_secret, _ = _oauth_config()
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Gmail OAuth is not configured.")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": session.refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {400, 401}:
            sessions.pop(session_id, None)
            raise HTTPException(
                status_code=401,
                detail="Your Gmail session expired. Connect Gmail again to continue.",
            ) from error
        raise HTTPException(status_code=502, detail="Gmail could not refresh its connection.") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Gmail could not refresh its connection.") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail="Gmail returned an unreadable token response.") from error

    if not isinstance(token_data, dict):
        raise HTTPException(status_code=502, detail="Gmail returned an unreadable token response.")
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        sessions.pop(session_id, None)
        raise HTTPException(
            status_code=401,
            detail="Your Gmail session expired. Connect Gmail again to continue.",
        )
    refreshed = GmailSession(
        access_token=access_token,
        refresh_token=session.refresh_token,
        expires_at=time.time() + int(token_data.get("expires_in", 3600)),
    )
    sessions[session_id] = refreshed
    return refreshed


async def _gmail_api_get(session_id: str, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    session = await _refresh_access_token(session_id)
    url = f"{GMAIL_API_ROOT}/{path}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {session.access_token}"},
            )
            if response.status_code == 401 and session.refresh_token:
                session = await _refresh_access_token_after_unauthorized(session_id)
                response = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {session.access_token}"},
                )
            if response.status_code == 401:
                sessions.pop(session_id, None)
                raise HTTPException(
                    status_code=401,
                    detail="Gmail authorization expired. Connect Gmail again to continue.",
                )
            if response.status_code == 403:
                raise HTTPException(
                    status_code=502,
                    detail="Gmail API access was denied. Check that the Gmail API is enabled in Google Cloud.",
                )
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Gmail could not load messages right now. Please try again.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail="Gmail returned an unreadable response.") from error


async def _refresh_access_token_after_unauthorized(session_id: str) -> GmailSession:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Connect Gmail to view your messages.")
    session.expires_at = 0
    return await _refresh_access_token(session_id)


def _decode_base64url(value: str) -> str:
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return decoded.decode("utf-8", errors="replace")


def _find_part_data(payload: dict[str, Any], mime_type: str) -> str | None:
    if payload.get("mimeType") == mime_type:
        body_data = payload.get("body", {}).get("data")
        if isinstance(body_data, str):
            return _decode_base64url(body_data)
    for part in payload.get("parts", []):
        if isinstance(part, dict):
            body_data = _find_part_data(part, mime_type)
            if body_data:
                return body_data
    return None


class _HTMLToText(HTMLParser):
    BLOCK_TAGS = {"br", "div", "li", "p", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)


def _plain_body(payload: dict[str, Any]) -> str:
    plain_text = _find_part_data(payload, "text/plain")
    if plain_text is None:
        html_text = _find_part_data(payload, "text/html")
        if html_text is None:
            return ""
        parser = _HTMLToText()
        parser.feed(html_text)
        plain_text = "".join(parser.chunks)
    normalized = re.sub(r"\n{3,}", "\n\n", plain_text).strip()
    if len(normalized) > MAX_EMAIL_BODY_CHARS:
        return normalized[:MAX_EMAIL_BODY_CHARS] + "\n\n[Email body truncated]"
    return normalized


def _header_value(headers: list[dict[str, Any]], name: str) -> str:
    raw_value = next(
        (str(header.get("value", "")) for header in headers if header.get("name", "").lower() == name.lower()),
        "",
    )
    try:
        return str(make_header(decode_header(raw_value)))
    except (LookupError, UnicodeDecodeError, ValueError):
        return raw_value


def _header_map(headers: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(header.get("name", "")).lower(): str(header.get("value", ""))
        for header in headers
        if header.get("name")
    }


def _email_message(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    return {
        "id": str(message.get("id", "")),
        "sender": _header_value(headers, "From"),
        "subject": _header_value(headers, "Subject") or "(no subject)",
        "date": _header_value(headers, "Date"),
        "snippet": str(message.get("snippet", "")),
        "body": _plain_body(payload),
    }


async def load_gmail_offer_text(session_id: str, message_id: str) -> tuple[str, list[str]]:
    message = await _gmail_api_get(
        session_id,
        f"messages/{quote(message_id, safe='')}",
        {"format": "full"},
    )
    payload = message.get("payload", {})
    headers = _header_map(payload.get("headers", []))
    parsed = _email_message(message)
    text = (
        f"Subject: {parsed['subject']}\n"
        f"From: {parsed['sender']}\n"
        f"Date: {parsed['date']}\n\n"
        f"{parsed['body'] or parsed['snippet']}"
    ).strip()
    return text, email_header_flags(headers)


@router.get("/api/gmail/messages")
async def gmail_messages(request: Request):
    session_id = _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    if not session_id:
        raise HTTPException(status_code=401, detail="Connect Gmail to view your messages.")

    listing = await _gmail_api_get(
        session_id,
        "messages",
        {"q": GMAIL_SEARCH_QUERY, "maxResults": "15"},
    )
    messages = listing.get("messages", [])
    if not isinstance(messages, list):
        raise HTTPException(status_code=502, detail="Gmail returned an invalid message list.")
    if not messages:
        return {"messages": []}

    semaphore = asyncio.Semaphore(5)

    async def load_message(item: dict[str, Any]) -> dict[str, str]:
        message_id = item.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise HTTPException(status_code=502, detail="Gmail returned an invalid message reference.")
        async with semaphore:
            message = await _gmail_api_get(session_id, f"messages/{quote(message_id, safe='')}", {"format": "full"})
        return _email_message(message)

    return {"messages": await asyncio.gather(*(load_message(item) for item in messages))}


@router.post("/api/gmail/disconnect")
async def gmail_disconnect(request: Request):
    session_id = _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    if session_id:
        sessions.pop(session_id, None)
    response = Response(content='{"connected":false}', media_type="application/json")
    _clear_session_cookie(response)
    return response
