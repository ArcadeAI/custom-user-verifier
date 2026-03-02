"""
Flask app implementing a custom user verifier route for Arcade.dev

Supports two modes:
  - flexible: users set their own user ID (for solo testing/demos)
  - protected: admin generates signed JWT links per user (for multi-user demos)

Set the mode via VERIFIER_MODE env var or --mode CLI arg.
"""

import hashlib
import hmac
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from dotenv import load_dotenv
from flask import Flask, make_response, request, redirect, session, render_template, abort
from arcadepy import Arcade

load_dotenv()


def get_mode():
    """Resolve mode from CLI arg (--mode) or env var (VERIFIER_MODE)."""
    for i, arg in enumerate(sys.argv):
        if arg == "--mode" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.environ.get("VERIFIER_MODE", "protected")


MODE = get_mode()
assert MODE in ("flexible", "protected"), f"Invalid mode: {MODE!r}. Must be 'flexible' or 'protected'."

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

JWT_SECRET = os.environ.get("JWT_SECRET", app.secret_key)
ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

if MODE == "protected" and not ADMIN_SECRET:
    raise RuntimeError("ADMIN_SECRET env var is required in protected mode")

arcade_client = Arcade()

# Track single-use JTIs (in-memory, sufficient for dev/demo)
used_jtis: set[str] = set()


# ---------------------------------------------------------------------------
# Verification endpoint (both modes)
# ---------------------------------------------------------------------------

@app.route("/auth/verify")
def verify_user():
    """
    Custom user verifier route for Arcade.dev.

    Called by Arcade after a user authorizes a tool. Verifies that the user
    completing the auth flow is the same user who started it.
    """
    flow_id = request.args.get("flow_id")

    if not flow_id:
        return render_template(
            "error.html",
            message="Missing required parameter.",
            detail="flow_id is required"
        ), 400

    user_id = session.get("user_id")

    if not user_id:
        return render_template(
            "error.html",
            message="You must be signed in to complete authorization.",
            detail="No user session found"
        ), 401

    try:
        result = arcade_client.auth.confirm_user(
            flow_id=flow_id,
            user_id=user_id,
        )
    except Exception as error:
        print("Error during verification:", error)
        error_detail = str(error) if app.debug else None
        return render_template(
            "error.html",
            message="Failed to verify the request. Please try again.",
            detail=error_detail
        ), 400

    try:
        auth_response = arcade_client.auth.wait_for_completion(result.auth_id)

        if auth_response.status == "completed":
            return render_template("success.html")
        else:
            return render_template(
                "error.html",
                message="Authorization was not completed. Please try again.",
                detail=f"Status: {auth_response.status}"
            ), 400
    except Exception as error:
        print("Error waiting for auth completion:", error)
        if hasattr(result, 'next_uri') and result.next_uri:
            return redirect(result.next_uri)
        return render_template(
            "error.html",
            message="Could not confirm authorization status.",
            detail=str(error) if app.debug else None
        ), 500


# ---------------------------------------------------------------------------
# Protected mode: admin generates JWT links, users activate them
# ---------------------------------------------------------------------------

def _make_admin_token():
    """Create an HMAC signature of the admin secret for cookie verification."""
    return hmac.new(
        app.secret_key.encode(), ADMIN_SECRET.encode(), hashlib.sha256
    ).hexdigest()


def _is_admin():
    """Check if the current request has a valid admin cookie."""
    token = request.cookies.get("admin_token")
    return token is not None and hmac.compare_digest(token, _make_admin_token())


def require_admin(f):
    """Redirect to admin login if not authenticated as admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if MODE != "protected":
            return redirect("/")
        if not _is_admin():
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page (protected mode only)."""
    if MODE != "protected":
        return redirect("/")

    if _is_admin():
        return redirect("/admin")

    error = None
    if request.method == "POST":
        secret = request.form.get("admin_secret", "")
        if secret == ADMIN_SECRET:
            resp = make_response(redirect("/admin"))
            resp.set_cookie(
                "admin_token",
                _make_admin_token(),
                max_age=60 * 60 * 24 * 30,  # 30 days
                httponly=True,
                samesite="Lax",
            )
            return resp
        error = "Invalid admin secret."

    return render_template("admin_login.html", error=error)


@app.route("/admin", methods=["GET", "POST"])
@require_admin
def admin():
    """Admin page for generating activation links (protected mode only)."""
    generated_link = None
    generated_user_id = None

    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        if user_id:
            token = jwt.encode(
                {
                    "sub": user_id,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=24),
                    "jti": str(uuid.uuid4()),
                },
                JWT_SECRET,
                algorithm="HS256",
            )
            generated_link = f"{request.host_url}auth/activate?token={token}"
            generated_user_id = user_id

    return render_template(
        "admin.html",
        generated_link=generated_link,
        generated_user_id=generated_user_id,
    )


@app.route("/auth/activate")
def activate():
    """Activate a session from a signed JWT link. Works in any mode."""
    token = request.args.get("token")
    if not token:
        return render_template(
            "error.html",
            message="Missing activation token.",
        ), 400

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return render_template(
            "error.html",
            message="This activation link has expired.",
            detail="Please ask your admin for a new link."
        ), 400
    except jwt.InvalidTokenError:
        return render_template(
            "error.html",
            message="Invalid activation link.",
        ), 400

    jti = payload.get("jti")
    if jti in used_jtis:
        return render_template(
            "error.html",
            message="This activation link has already been used.",
            detail="Please ask your admin for a new link."
        ), 400

    used_jtis.add(jti)
    user_id = payload["sub"]
    session["user_id"] = user_id

    return render_template("activated.html", user_id=user_id)


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

@app.route("/logout", methods=["POST"])
def logout():
    """Clear the user session and redirect home."""
    session.pop("user_id", None)
    return redirect("/")


@app.route("/", methods=["GET", "POST"])
def index():
    """Home page. In flexible mode, allows setting user ID. In protected mode, shows status only."""
    if request.method == "POST" and MODE == "flexible":
        user_id = request.form.get("user_id", "").strip()
        if user_id:
            session["user_id"] = user_id
        else:
            session.pop("user_id", None)
        return redirect("/")

    user_id = session.get("user_id")
    logged_in = user_id is not None
    return render_template("index.html", user_id=user_id, logged_in=logged_in, mode=MODE)


if __name__ == "__main__":
    print(f"Starting in {MODE} mode")
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
