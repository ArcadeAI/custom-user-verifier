# Custom User Verifier for Arcade.dev

A minimal Flask server that implements a [custom user verifier](https://docs.arcade.dev/en/guides/user-facing-agents/secure-auth-production) for Arcade.dev.

When your app's users authorize a tool, Arcade redirects their browser to this server's `/auth/verify` endpoint with a `flow_id`. The server confirms the user's identity back to Arcade using the [Arcade Python SDK](https://github.com/ArcadeAI/arcade-py), then renders a success or error page.

## How it works

1. A user sets their ID on the home page (or via `/login/<user_id>`)
2. The ID is stored in a session cookie
3. When Arcade redirects to `/auth/verify?flow_id=...`, the server reads the user ID from the session and calls `client.auth.confirm_user(flow_id, user_id)`
4. Arcade validates the user ID matches the one that started the auth flow
5. On success, the server renders a confirmation page

The user ID used here **must match** the `user_id` passed when your app starts the authorization flow (e.g. via `client.tools.authorize(tool_name=..., user_id=...)` or the `Arcade-User-ID` header on a gateway).

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ArcadeAI/custom-user-verifier.git
cd custom-user-verifier
uv sync
```

## Configuration

Copy the example env file and add your Arcade API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
ARCADE_API_KEY=your_arcade_api_key_here
FLASK_SECRET_KEY=change-this-to-a-random-secret
```

| Variable | Required | Description |
|---|---|---|
| `ARCADE_API_KEY` | Yes | Your Arcade project API key |
| `FLASK_SECRET_KEY` | No | Secret for signing session cookies (has a dev fallback) |
| `PORT` | No | Server port (default: `5001`) |
| `FLASK_DEBUG` | No | Enable debug mode (default: `true`) |

## Run locally

```bash
uv run python app.py
```

The server starts at `http://localhost:5001`.

## Expose with ngrok (for testing)

Arcade needs to redirect to a public URL. Use [ngrok](https://ngrok.com/) to expose the local server:

```bash
ngrok http 5001
```

Then in the [Arcade Dashboard > Auth > Settings](https://api.arcade.dev/dashboard/auth/settings), set the custom verifier URL to:

```
https://your-ngrok-url.ngrok-free.app/auth/verify
```

## Routes

| Route | Method | Description |
|---|---|---|
| `/` | GET, POST | Home page with user ID input form |
| `/auth/verify` | GET | Verifier endpoint (called by Arcade) |
| `/login/<user_id>` | GET | Quick login via URL (convenience shortcut) |

## Learn more

- [Secure Auth in Production](https://docs.arcade.dev/en/guides/user-facing-agents/secure-auth-production) - Arcade docs on custom user verifiers
- [Arcade Python SDK](https://github.com/ArcadeAI/arcade-py)
