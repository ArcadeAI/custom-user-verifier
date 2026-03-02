"""
Flask app implementing a custom user verifier route for Arcade.dev

This route handles the redirect from Arcade.dev after a user has authorized a tool,
verifies the user's identity, and confirms it back to Arcade.
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, redirect, session, render_template
from arcadepy import Arcade

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize the Arcade client (uses ARCADE_API_KEY env var by default)
arcade_client = Arcade()


@app.route("/auth/verify")
def verify_user():
    """
    Custom user verifier route for Arcade.dev.
    
    This route is called by Arcade.dev after a user authorizes a tool.
    It verifies that the user completing the auth flow is the same user
    who started it.
    """
    # Get flow_id from query string
    flow_id = request.args.get("flow_id")
    
    # Validate required parameters
    if not flow_id:
        return render_template(
            "error.html",
            message="Missing required parameter.",
            detail="flow_id is required"
        ), 400
    
    # Get the user's ID from your app's session
    # This must match the user_id specified when starting the auth flow
    user_id = session.get("user_id")
    
    if not user_id:
        return render_template(
            "error.html",
            message="You must be signed in to complete authorization.",
            detail="No user session found"
        ), 401
    
    # Confirm the user's identity with Arcade
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
    
    # Option 1: Redirect to Arcade's next_uri
    # return redirect(result.next_uri)
    
    # Option 2: Wait for completion and render a success page
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
        # Even if wait_for_completion fails, the auth might have succeeded
        # You could redirect to next_uri as a fallback
        if hasattr(result, 'next_uri') and result.next_uri:
            return redirect(result.next_uri)
        return render_template(
            "error.html",
            message="Could not confirm authorization status.",
            detail=str(error) if app.debug else None
        ), 500


@app.route("/login/<user_id>")
def login(user_id: str):
    """Quick login via URL path (kept for convenience/scripting)."""
    session["user_id"] = user_id
    return redirect("/")


@app.route("/", methods=["GET", "POST"])
def index():
    """Home page with login form."""
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        if user_id:
            session["user_id"] = user_id
        else:
            session.pop("user_id", None)
        return redirect("/")

    user_id = session.get("user_id")
    logged_in = user_id is not None
    return render_template("index.html", user_id=user_id, logged_in=logged_in)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)

