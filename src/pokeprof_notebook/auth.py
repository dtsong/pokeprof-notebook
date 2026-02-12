"""Authentication helpers for PokeProf Notebook.

V1 goals:
- Cloud Run service is publicly reachable (no Cloud Run IAM invoker gating).
- App-level access control is enforced via Firebase Auth + Firestore allowlist.
- SSE is authenticated via an HttpOnly session cookie (EventSource cannot
  set Authorization headers).

Environment variables:
- FIREBASE_PROJECT_ID: Optional explicit Firebase project ID. Defaults to
  GOOGLE_CLOUD_PROJECT when running on GCP.
- POKEPROF_SESSION_SECRET: Secret used to sign session cookies. Required in
  production. In dev, a stable default is used when POKEPROF_DEV is set.
- POKEPROF_COOKIE_SECURE: 'true'|'false'|'auto' (default auto).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


COOKIE_NAME = "pokeprof_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class SessionUser:
    uid: str
    email: str
    role: str = "judge"
    name: str = ""


_serializer: URLSafeTimedSerializer | None = None


def _firebase_project_id() -> str | None:
    return os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )


def _ensure_firebase_initialized() -> None:
    if firebase_admin._apps:  # type: ignore[attr-defined]
        return
    project_id = _firebase_project_id()
    options: dict[str, Any] | None = None
    if project_id:
        options = {"projectId": project_id}
    firebase_admin.initialize_app(options=options)
    logger.info("Firebase admin initialized (project_id=%s)", project_id or "(default)")


_firestore_client: firestore.Client | None = None


def _firestore() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        project_id = _firebase_project_id()
        _firestore_client = (
            firestore.Client(project=project_id) if project_id else firestore.Client()
        )
    return _firestore_client


def _session_secret() -> str:
    secret = os.environ.get("POKEPROF_SESSION_SECRET")
    if secret:
        return secret
    if os.environ.get("POKEPROF_DEV"):
        # Stable local dev secret to avoid constant logouts on reload.
        return "pokeprof-dev-session-secret"
    raise RuntimeError("POKEPROF_SESSION_SECRET not set")


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(
            _session_secret(), salt="pokeprof-session-v1"
        )
    return _serializer


def create_session_cookie(user: SessionUser) -> str:
    s = _get_serializer()
    payload = {
        "uid": user.uid,
        "email": user.email,
        "role": user.role,
        "name": user.name,
    }
    return s.dumps(payload)


def verify_session_cookie(value: str) -> SessionUser | None:
    s = _get_serializer()
    try:
        data = s.loads(value, max_age=SESSION_TTL_SECONDS)
        return SessionUser(
            uid=str(data.get("uid", "")),
            email=str(data.get("email", "")),
            role=str(data.get("role", "judge")),
            name=str(data.get("name", "")),
        )
    except (BadTimeSignature, BadSignature):
        return None


def cookie_secure(request: Request) -> bool:
    v = os.environ.get("POKEPROF_COOKIE_SECURE", "auto").strip().lower()
    if v in {"1", "true", "yes"}:
        return True
    if v in {"0", "false", "no"}:
        return False
    return request.url.scheme == "https"


def require_session(request: Request) -> SessionUser:
    if os.environ.get("POKEPROF_DEV") and os.environ.get("POKEPROF_AUTH_DISABLED"):
        return SessionUser(uid="dev", email="dev@local", role="admin", name="Dev")
    cookie_val = request.cookies.get(COOKIE_NAME)
    if not cookie_val:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = verify_session_cookie(cookie_val)
    if not user or not user.uid or not user.email:
        raise HTTPException(status_code=401, detail="Session expired")
    return user


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    _ensure_firebase_initialized()
    try:
        return fb_auth.verify_id_token(id_token)
    except Exception as e:
        logger.info("Firebase token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Firebase token")


def require_allowlisted_user(decoded: dict[str, Any]) -> SessionUser:
    email = (decoded.get("email") or "").strip().lower()
    uid = (decoded.get("uid") or "").strip()
    name = (decoded.get("name") or "").strip()
    if not email or not uid:
        raise HTTPException(status_code=400, detail="Token missing email/uid")

    # Enforce verified email for Email/Password users.
    provider = ((decoded.get("firebase") or {}).get("sign_in_provider") or "").strip()
    if provider == "password" and not decoded.get("email_verified"):
        raise HTTPException(status_code=403, detail="Email not verified")

    doc = _firestore().collection("allowlist").document(email).get()
    if not doc.exists:
        raise HTTPException(status_code=403, detail="Not invited")
    data = doc.to_dict() or {}
    if not data.get("enabled", False):
        raise HTTPException(status_code=403, detail="Access disabled")

    role = str(data.get("role") or "judge")
    return SessionUser(uid=uid, email=email, role=role, name=name)
