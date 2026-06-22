"""Simple session-cookie authentication.

Set ``FAH_PASSWORD`` in the environment to enable. When unset the app runs open (development
mode). The password is never stored; only its SHA-256 hex digest is placed in the session cookie.

Routes exempt from auth:
  GET  /login    — login form
  POST /login    — credential check
  GET  /logout   — clears cookie
  GET  /health   — readiness probe
  /static/*      — CSS / JS assets
"""

from __future__ import annotations

import hashlib
import logging
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("fah.auth")

_EXEMPT_PREFIXES = ("/login", "/logout", "/health", "/static")
_COOKIE = "fah_session"

router = APIRouter(tags=["auth"])


def _token() -> str | None:
    """Return the expected cookie value (SHA-256 of the password), or None if auth is off."""
    pw = os.environ.get("FAH_PASSWORD", "").strip()
    return hashlib.sha256(pw.encode()).hexdigest() if pw else None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object):  # type: ignore[override]
        expected = _token()
        if expected is None:
            return await call_next(request)  # auth disabled

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        if request.cookies.get(_COOKIE) == expected:
            return await call_next(request)

        # Redirect to login, preserving the original destination.
        return RedirectResponse(f"/login?next={path}", status_code=303)


_LOGIN_HTML = """\
<!DOCTYPE html><html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>FAH Explorer — Login</title>
  <link rel="stylesheet" href="/static/css/app.css"/>
  <style>
    body{{display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f1c24}}
    .login-box{{background:#162535;border:1px solid #1e3a52;border-radius:8px;padding:2rem 2.5rem;width:320px}}
    h1{{margin-top:0;font-size:1.2rem;color:#e8f0f7}}
    .err{{color:#FF4136;font-size:.9rem;margin-bottom:.75rem}}
  </style>
</head>
<body>
  <div class="login-box">
    <h1>FAH Explorer</h1>
    {error}
    <form method="post" action="/login">
      <input type="hidden" name="next" value="{next_url}"/>
      <label>Password</label>
      <input type="password" name="password" autofocus required/>
      <p style="margin-top:1rem"><button type="submit" style="width:100%">Sign in</button></p>
    </form>
  </div>
</body></html>
"""


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, next: str = "/") -> HTMLResponse:
    if _token() is None:
        return RedirectResponse("/")
    return HTMLResponse(_LOGIN_HTML.format(error="", next_url=next))


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    password: str = Form(...),
    next: str = Form("/"),
) -> Response:
    expected = _token()
    if expected is None or hashlib.sha256(password.encode()).hexdigest() == expected:
        resp = RedirectResponse(next or "/", status_code=303)
        resp.set_cookie(_COOKIE, expected or "", httponly=True, samesite="lax")
        return resp
    html = _LOGIN_HTML.format(error='<p class="err">Incorrect password.</p>', next_url=next)
    return HTMLResponse(html, status_code=401)


@router.get("/logout", include_in_schema=False)
def logout() -> Response:
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(_COOKIE)
    return resp
