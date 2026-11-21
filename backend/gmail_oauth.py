import asyncio
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass
from email.header import decode_header, make_header
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

if __package__:
    from .email_headers import email_header_flags
else:
    from email_headers import email_header_flags


router = APIRouter()

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8000/auth/google/callback"
GOOGLE_CLIENT_SECRET_FILES = (
    Path(__file__).resolve().parent / "client_secret.json",
    Path(__file__).resolve().parent.parent / "client_secret.json",
    Path("/etc/secrets/client_secret.json"),
)
SESSION_COOKIE = "offercheck_gmail_session"
STATE_COOKIE = "offercheck_gmail_oauth_state"
STATE_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_EMAIL_BODY_CHARS = 20000
MAX_EMAIL_URL_CHARS = 180
GMAIL_PAGE_SIZE = 25
GMAIL_MAX_RESULTS = 10
EMAIL_HTML_MARKUP = re.compile(
    r"</?\s*(?:html|head|body|style|script|noscript|template|blockquote|"
    r"address|article|section|nav|main|header|footer|div|span|p|br|"
    r"ul|ol|li|table|thead|tbody|tfoot|tr|td|th|caption|a|img|"
    r"form|input|label|button|iframe|title|meta|link|hr|pre|"
    r"strong|em|b|i|font|center|small|sup|sub|h[1-6])\b",
    re.IGNORECASE,
)
EMAIL_URL = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
EMAIL_QUOTED_REPLY = re.compile(
    r"^\s*(?:On\s+.+\bwrote:\s*$|[-_ ]*Original Message[-_ ]*|Begin forwarded message:)",
    re.IGNORECASE,
)
EMAIL_FOOTER = re.compile(
    r"\b(?:unsubscribe|manage\s+(?:your\s+)?(?:email\s+)?preferences|"
    r"update\s+(?:your\s+)?preferences|view\s+(?:this\s+)?(?:email\s+)?in\s+(?:your\s+)?browser|"
    r"you are receiving this email because|don't want to receive|do not want to receive|"
    r"email preferences|privacy policy|all rights reserved)\b",
    re.IGNORECASE,
)
GMAIL_SEARCH_QUERY = (
    'newer_than:30d {offer internship job hiring hired interview selected stipend '
    'freelance contract onboarding "appointment letter" recruiter} '
    '-category:promotions -category:social'
)
JOB_CONTEXT = re.compile(
    r"\b(?:jobs?|intern(?:ship)?|freelanc(?:e|er|ing)|recruit(?:er|ment|ing)|"
    r"hiring|interview|candidate|vacanc(?:y|ies)|career(?:s)?|employment|stipend)\b",
    re.IGNORECASE,
)
OFFER_CONTEXT = re.compile(
    r"\b(?:offer(?:\s+letter)?|selected|selection|appointment|onboarding|contract)\b",
    re.IGNORECASE,
)
EMPLOYMENT_CONTEXT = re.compile(
    r"\b(?:job|intern(?:ship)?|freelanc(?:e|er|ing)|role|position|salary|stipend|"
    r"recruiter|candidate|employment|employee|employer|joining)\b",
    re.IGNORECASE,
)


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
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

    file_client_id = ""
    file_client_secret = ""
    file_redirect_uri = ""
    if not client_id or not client_secret:
        for path in GOOGLE_CLIENT_SECRET_FILES:
            if not path.is_file():
                continue
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError("Could not read Google OAuth client_secret.json.") from error
            if not isinstance(document, dict):
                raise RuntimeError("Google OAuth client_secret.json must contain a JSON object.")
            credentials = document.get("web") or document.get("installed") or document
            if not isinstance(credentials, dict):
                raise RuntimeError("Google OAuth client_secret.json has an invalid credentials section.")
            file_client_id = str(credentials.get("client_id") or "").strip()
            file_client_secret = str(credentials.get("client_secret") or "").strip()
            redirect_uris = credentials.get("redirect_uris") or []
            if isinstance(redirect_uris, list):
                file_redirect_uri = next(
                    (
                        uri
                        for uri in redirect_uris
                        if isinstance(uri, str)
                        and urlsplit(uri).path.rstrip("/") == "/auth/google/callback"
                    ),
                    "",
                )
            if file_client_id and file_client_secret:
                break

    client_id = client_id or file_client_id
    client_secret = client_secret or file_client_secret
    redirect_uri = redirect_uri or file_redirect_uri or DEFAULT_REDIRECT_URI
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
    BLOCK_TAGS = {
        "address", "article", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "p", "section", "tr",
    }
    IGNORED_TAGS = {"blockquote", "head", "noscript", "script", "style", "template"}
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }
    HIDDEN_STYLE = re.compile(
        r"(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\D|$))",
        re.IGNORECASE,
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.ignored_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.ignored_tags:
            if tag not in self.VOID_TAGS:
                self.ignored_tags.append(tag)
            return
        attributes = dict(attrs)
        hidden = (
            tag in self.IGNORED_TAGS
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").lower() == "true"
            or bool(self.HIDDEN_STYLE.search(attributes.get("style") or ""))
        )
        if hidden:
            if tag not in self.VOID_TAGS:
                self.ignored_tags.append(tag)
            return
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")
        if tag == "li":
            self.chunks.append("• ")

    def handle_endtag(self, tag: str) -> None:
        if self.ignored_tags:
            for index in range(len(self.ignored_tags) - 1, -1, -1):
                if self.ignored_tags[index] == tag:
                    del self.ignored_tags[index:]
                    break
            return
        if tag in self.BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_tags:
            self.chunks.append(data)


def _strip_email_url(match: re.Match[str]) -> str:
    value = match.group(0)
    suffix = ""
    while value and value[-1] in ".,;:!?)]}":
        suffix = value[-1] + suffix
        value = value[:-1]
    if len(value) > MAX_EMAIL_URL_CHARS:
        return suffix
    try:
        parsed = urlsplit(value)
        value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        value = value.split("?", 1)[0].split("#", 1)[0]
    return value + suffix


def _clean_email_body(value: str) -> str:
    if not value:
        return ""
    if EMAIL_HTML_MARKUP.search(value):
        parser = _HTMLToText()
        parser.feed(value)
        parser.close()
        value = "".join(parser.chunks)
    else:
        value = html.unescape(value)

    printable = []
    for character in value:
        if character in "\r\n\t":
            printable.append(character)
        elif character in "\u2028\u2029":
            printable.append("\n")
        elif unicodedata.category(character).startswith("C"):
            continue
        elif character == "\u00a0":
            printable.append(" ")
        else:
            printable.append(character)

    value = EMAIL_URL.sub(_strip_email_url, "".join(printable))
    lines = []
    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if EMAIL_QUOTED_REPLY.match(line) or EMAIL_FOOTER.search(line):
            break
        if re.match(r"^\s*>", line):
            break
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
        else:
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _format_email_text(subject: str, sender: str, body: str) -> str:
    lines = []
    if subject:
        lines.append(f"Subject: {subject}")
    if sender:
        lines.append(f"From: {sender}")
    if body:
        if lines:
            lines.append("")
        lines.extend(body.splitlines())
    return "\n".join(lines).strip()


def _plain_body(payload: dict[str, Any]) -> str:
    plain_text = _find_part_data(payload, "text/plain")
    if plain_text is None:
        html_text = _find_part_data(payload, "text/html")
        if html_text is None:
            return ""
        plain_text = html_text
    normalized = _clean_email_body(plain_text)
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
    subject = _header_value(headers, "Subject") or "(no subject)"
    sender = _header_value(headers, "From")
    body = _plain_body(payload)
    snippet = _clean_email_body(str(message.get("snippet", "")))
    return {
        "id": str(message.get("id", "")),
        "sender": sender,
        "subject": subject,
        "date": _header_value(headers, "Date"),
        "snippet": snippet,
        "body": body,
        "offer_text": _format_email_text(subject, sender, body or snippet),
    }


def is_job_related_email(message: dict[str, str]) -> bool:
    text = " ".join(
        message.get(field, "")
        for field in ("subject", "snippet", "body")
    )
    return bool(JOB_CONTEXT.search(text) or (
        OFFER_CONTEXT.search(text) and EMPLOYMENT_CONTEXT.search(text)
    ))


def _internal_date(message: dict[str, Any]) -> int:
    try:
        return int(message.get("internalDate", 0))
    except (TypeError, ValueError):
        return 0


async def load_gmail_offer_text(session_id: str, message_id: str) -> tuple[str, list[str]]:
    message = await _gmail_api_get(
        session_id,
        f"messages/{quote(message_id, safe='')}",
        {"format": "full"},
    )
    payload = message.get("payload", {})
    headers = _header_map(payload.get("headers", []))
    parsed = _email_message(message)
    return parsed["offer_text"], email_header_flags(headers)


@router.get("/api/gmail/messages")
async def gmail_messages(request: Request):
    session_id = _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    if not session_id:
        raise HTTPException(status_code=401, detail="Connect Gmail to view your messages.")

    semaphore = asyncio.Semaphore(5)

    async def load_message(item: dict[str, Any]) -> dict[str, Any]:
        message_id = item.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise HTTPException(status_code=502, detail="Gmail returned an invalid message reference.")
        async with semaphore:
            return await _gmail_api_get(
                session_id,
                f"messages/{quote(message_id, safe='')}",
                {"format": "full"},
            )

    matches = []
    page_token = None
    while len(matches) < GMAIL_MAX_RESULTS:
        params = {
            "q": GMAIL_SEARCH_QUERY,
            "maxResults": str(GMAIL_PAGE_SIZE),
        }
        if page_token:
            params["pageToken"] = page_token
        listing = await _gmail_api_get(session_id, "messages", params)
        candidates = listing.get("messages", [])
        if not isinstance(candidates, list):
            raise HTTPException(status_code=502, detail="Gmail returned an invalid message list.")
        if candidates:
            full_messages = await asyncio.gather(*(load_message(item) for item in candidates))
            full_messages.sort(key=_internal_date, reverse=True)
            for full_message in full_messages:
                message = _email_message(full_message)
                if is_job_related_email(message):
                    matches.append(message)
                    if len(matches) == GMAIL_MAX_RESULTS:
                        break
        page_token = listing.get("nextPageToken")
        if not page_token:
            break
    return {"messages": matches}


@router.post("/api/gmail/disconnect")
async def gmail_disconnect(request: Request):
    session_id = _session_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    if session_id:
        sessions.pop(session_id, None)
    response = Response(content='{"connected":false}', media_type="application/json")
    _clear_session_cookie(response)
    return response
