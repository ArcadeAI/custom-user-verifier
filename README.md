# Custom User Verifier for Arcade.dev

A minimal Flask server that implements a [custom user verifier](https://docs.arcade.dev/en/guides/user-facing-agents/secure-auth-production) for Arcade.dev.

When your app's users authorize a tool, Arcade redirects their browser to this server's `/auth/verify` endpoint with a `flow_id`. The server confirms the user's identity back to Arcade using the [Arcade Python SDK](https://github.com/ArcadeAI/arcade-py), then renders a success or error page.

## Modes

The server supports two operating modes:

### Protected mode (default)

Best for multi-user demos and shared environments. An admin generates signed, single-use activation links for each user. End users click the link to get a session -- they never choose their own ID.

```bash
uv run python app.py
# or explicitly:
uv run python app.py --mode protected
```

### Flexible mode

Best for solo testing and quick demos. The home page has a free-text input where you type any user ID to set your session.

```bash
uv run python app.py --mode flexible
```

**Admin flow:**

1. Visit `/admin` and sign in with the admin secret (remembered for 30 days)
2. Enter a user ID and copy the generated activation link
3. Share the link with the user
4. The user clicks the link, which sets their session cookie automatically

Links are single-use and expire after 24 hours.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ArcadeAI/custom-user-verifier.git
cd custom-user-verifier
uv sync
```

## Configuration

Copy the example env file and add your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
ARCADE_API_KEY=your_arcade_api_key_here
VERIFIER_MODE=protected
ADMIN_SECRET=choose-a-strong-secret
```

| Variable | Required | Description |
|---|---|---|
| `ARCADE_API_KEY` | Yes | Your Arcade project API key |
| `VERIFIER_MODE` | No | `protected` (default) or `flexible` |
| `ADMIN_SECRET` | In protected mode | Secret for the admin page |
| `JWT_SECRET` | No | Secret for signing activation tokens (falls back to `FLASK_SECRET_KEY`) |
| `FLASK_SECRET_KEY` | No | Secret for signing session cookies (has a dev fallback) |
| `PORT` | No | Server port (default: `5001`) |
| `FLASK_DEBUG` | No | Enable debug mode (default: `true`) |

The mode can also be set via CLI: `--mode flexible` or `--mode protected` (overrides the env var).

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

| Route | Method | Modes | Description |
|---|---|---|---|
| `/` | GET, POST | Both | Home page (input form in flexible, status in protected) |
| `/auth/verify` | GET | Both | Verifier endpoint (called by Arcade) |
| `/auth/activate` | GET | Both | Activates a session from a signed JWT link |
| `/admin/login` | GET, POST | Protected | Admin sign-in (cookie-based, 30-day expiry) |
| `/admin` | GET, POST | Protected | Generate activation links (requires admin login) |
| `/logout` | POST | Both | Clears the user session |

## How verification works

1. A user's session contains their `user_id` (set via the form in flexible mode, or via an activation link in protected mode)
2. When Arcade redirects to `/auth/verify?flow_id=...`, the server reads `user_id` from the session
3. The server calls `client.auth.confirm_user(flow_id, user_id)` via the Arcade SDK
4. Arcade validates the `user_id` matches the one that started the auth flow
5. On success, the server renders a confirmation page

The `user_id` here **must match** the `user_id` passed when your app starts the authorization flow (e.g. via `client.tools.authorize(tool_name=..., user_id=...)` or the `Arcade-User-ID` header on a gateway).

## Learn more

- [Secure Auth in Production](https://docs.arcade.dev/en/guides/user-facing-agents/secure-auth-production) -- Arcade docs on custom user verifiers
- [Arcade Python SDK](https://github.com/ArcadeAI/arcade-py)
