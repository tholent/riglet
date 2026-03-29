# Implementation Plan

## Feature: Session-Based Authentication

Single-user, password-based session authentication. Password hash stored in a
separate secrets file (`~/.config/riglet/secrets.yaml`). When no secrets file
exists the system operates in unauthenticated/setup mode (first-run). The setup
wizard gains a "Set Password" step. All protected routes return 401 when no
valid session cookie is present; the frontend intercepts 401 and redirects to
`/login`.

## Task Summary

| # | Task | Priority | Agent | Status | Depends On | Notes |
|:--|:-----|:---------|:------|:-------|:-----------|:------|
| 1 | Add `passlib[bcrypt]` and `itsdangerous` to backend deps | P0 | @developer | [x] | -- | |
| 2 | Create `server/auth.py` -- secrets I/O, hashing, session tokens, middleware | P0 | @developer | [x] | 1 | Core auth module |
| 3 | Create `server/routers/auth.py` -- login, logout, status, set-password endpoints | P0 | @developer | [x] | 2 | |
| 4 | Register auth middleware and router in `server/main.py` | P0 | @developer | [x] | 2, 3 | |
| 5 | Write `server/tests/test_auth.py` -- unit and integration tests | P0 | @developer | [x] in-process | 2, 3, 4 | |
| 6 | Create `ui/src/routes/login/+page.svelte` -- login form | P1 | @developer | [x] | -- | Frontend, no backend dep |
| 7 | Update `ui/src/lib/api.ts` -- 401 intercept and auth API functions | P1 | @developer | [x] | 3 | |
| 8 | Add auth guards to `+page.svelte` and `setup/+page.svelte` | P1 | @developer | [x] | 7 | |
| 9 | Add logout button to main UI top bar | P1 | @developer | [x] | 7 | |
| 10 | Create `StepSetPassword.svelte` and wire into setup wizard | P1 | @developer | [x] | 7 | |

---

## Parallelization Strategy

**Wave 1** (no dependencies between them):
- Task 1 -- add Python dependencies
- Task 6 -- create login page (pure frontend, no backend calls needed yet)

**Wave 2** (depends on Wave 1):
- Task 2 -- `server/auth.py` (needs deps from Task 1)

**Wave 3** (depends on Wave 2):
- Task 3 -- `server/routers/auth.py` (needs auth module from Task 2)

**Wave 4** (depends on Wave 3):
- Task 4 -- wire middleware/router into `main.py`
- Task 7 -- update `api.ts` with 401 intercept + auth API functions

**Wave 5** (depends on Wave 4; all frontend tasks are independent of each other):
- Task 5 -- backend tests
- Task 8 -- auth guards in pages
- Task 9 -- logout button
- Task 10 -- setup wizard password step

---

## Task Descriptions

### Task 1: Add `passlib[bcrypt]` and `itsdangerous` to backend dependencies

**File:** `/Users/wells/Projects/riglet/server/pyproject.toml`

**Changes:**
- Add `"passlib[bcrypt]"` to the `dependencies` list (runtime dep).
- Add `"itsdangerous"` to the `dependencies` list (runtime dep).

**Acceptance criteria:**
- `uv sync` succeeds.
- `uv run python -c "from passlib.hash import bcrypt; from itsdangerous import TimestampSigner; print('ok')"` prints `ok`.
- `uv run mypy .` still passes (no new type errors from these packages).

---

### Task 2: Create `server/auth.py` -- secrets I/O, hashing, session tokens, middleware

**File:** `/Users/wells/Projects/riglet/server/auth.py` (new)

**Constants:**
- `_DEFAULT_SECRETS_PATH`: `Path(os.environ.get("RIGLET_SECRETS", Path.home() / ".config" / "riglet" / "secrets.yaml"))` -- mirrors `config.py` pattern, respects env var.
- `SESSION_COOKIE_NAME = "riglet_session"`
- `SESSION_MAX_AGE = 86400` (24 hours, in seconds)
- `_PUBLIC_PATHS`: a `frozenset` containing the exact paths that skip auth: `{"/api/auth/login", "/api/auth/status", "/api/status"}`. Also, any path starting with `/api/auth/set-password` is public only when no password is configured.

**Functions:**

1. `hash_password(password: str) -> str`
   - Uses `passlib.hash.bcrypt.hash(password)`.
   - Returns the bcrypt hash string.

2. `verify_password(password: str, hashed: str) -> bool`
   - Uses `passlib.hash.bcrypt.verify(password, hashed)`.
   - Returns `True` if match.

3. `load_secrets(path: Path = _DEFAULT_SECRETS_PATH) -> dict[str, str] | None`
   - Returns `None` if file does not exist.
   - Reads YAML, expects `{"password_hash": "<bcrypt string>"}`.
   - Returns the dict.

4. `save_secrets(data: dict[str, str], path: Path = _DEFAULT_SECRETS_PATH) -> None`
   - Atomic write via tempfile (same pattern as `save_config` in `config.py`).
   - Creates parent dirs if needed.
   - File permissions `0o600` on the final file.

5. `create_session_token(secret_key: str) -> str`
   - Uses `itsdangerous.TimestampSigner(secret_key).sign("session").decode("utf-8")`.
   - `secret_key` is derived from (or stored alongside) the password hash -- use the password hash itself as the signing key so that changing the password invalidates all sessions.

6. `verify_session_token(token: str, secret_key: str, max_age: int = SESSION_MAX_AGE) -> bool`
   - Uses `TimestampSigner(secret_key).unsign(token, max_age=max_age)`.
   - Returns `True` on success, `False` on `SignatureExpired` or `BadSignature`.

**Class: `SessionAuthMiddleware(BaseHTTPMiddleware)`**

- Constructor takes `app` and `secrets_path: Path = _DEFAULT_SECRETS_PATH`.
- `async def dispatch(self, request: Request, call_next)`:
  1. Load secrets via `load_secrets(self.secrets_path)`.
  2. If secrets is `None` (no password file): call `call_next(request)` -- unauthenticated/setup mode, all requests pass through.
  3. If the request path is in `_PUBLIC_PATHS`: call `call_next(request)`.
  4. If the path matches `/api/auth/set-password` and secrets is `None`: pass through (handled above by step 2, but be explicit).
  5. For WebSocket requests (`scope["type"] == "websocket"`): read cookie from `request.cookies.get(SESSION_COOKIE_NAME)`, verify token. If invalid, close with 4401 code. (Note: WebSocket upgrade is HTTP initially, so cookies are available.)
  6. For HTTP requests: read cookie, verify. If invalid, return `JSONResponse(status_code=401, content={"detail": "Not authenticated"})`.
  7. Static file paths (not starting with `/api/`) should also pass through so the SPA HTML/JS/CSS loads. The middleware only protects paths starting with `/api/` (except the public ones listed above).

**Type annotations:** Full mypy strict compliance. Use `from __future__ import annotations`.

**Acceptance criteria:**
- File passes `ruff check` and `mypy --strict`.
- `hash_password` / `verify_password` round-trip correctly.
- `create_session_token` / `verify_session_token` round-trip correctly.
- `load_secrets` returns `None` when file does not exist.
- `save_secrets` creates the file with `0o600` permissions.
- Middleware passes through when no secrets file exists.
- Middleware blocks `/api/config` with 401 when secrets exist and no cookie.
- Middleware allows `/api/status` without cookie.
- Middleware allows `/api/auth/login` without cookie.
- Middleware passes through non-`/api/` paths (static files).

---

### Task 3: Create `server/routers/auth.py` -- login, logout, status, set-password

**File:** `/Users/wells/Projects/riglet/server/routers/auth.py` (new)

**Router:** `router = APIRouter(prefix="/auth")`

**Endpoints:**

1. `POST /api/auth/login`
   - Request body: `{"password": "..."}` (JSON).
   - Load secrets. If no secrets file, return 400 `{"detail": "No password configured"}`.
   - Verify password against stored hash.
   - On failure: return 401 `{"detail": "Invalid password"}`.
   - On success: create session token (using password hash as secret key), set cookie:
     ```python
     response.set_cookie(
         key=SESSION_COOKIE_NAME,
         value=token,
         httponly=True,
         samesite="strict",
         max_age=SESSION_MAX_AGE,
         path="/",
     )
     ```
   - Return 200 `{"status": "ok"}`.

2. `POST /api/auth/logout`
   - Delete the session cookie by setting it with `max_age=0`.
   - Return 200 `{"status": "ok"}`.
   - This endpoint is accessible even without auth (deleting a cookie is harmless).

3. `GET /api/auth/status`
   - Load secrets. If `None`: return `{"authenticated": false, "password_set": false}`.
   - If secrets exist: check cookie for valid session. Return `{"authenticated": <bool>, "password_set": true}`.

4. `POST /api/auth/set-password`
   - Load secrets. If secrets already exist: return 403 `{"detail": "Password already set. Use change-password instead."}`.
   - Request body: `{"password": "..."}`.
   - Validate password is at least 8 characters. If not, return 422 `{"detail": "Password must be at least 8 characters"}`.
   - Hash password, save to secrets file.
   - Create session token, set cookie (same as login).
   - Return 200 `{"status": "ok"}`.

**Acceptance criteria:**
- File passes `ruff check` and `mypy --strict`.
- Login with correct password returns 200 and sets HttpOnly cookie.
- Login with wrong password returns 401.
- Login when no password file returns 400.
- Status returns `password_set: false` when no secrets file.
- Status returns `authenticated: true` when valid cookie present.
- Set-password works on first run, returns 403 on second call.
- Set-password rejects passwords shorter than 8 characters.
- Logout clears cookie.

---

### Task 4: Register auth middleware and router in `server/main.py`

**File:** `/Users/wells/Projects/riglet/server/main.py`

**Changes:**

1. Import `SessionAuthMiddleware` from `auth` and `router as _auth_router` from `routers.auth`.
2. Add the auth router with prefix `/api`:
   ```python
   app.include_router(_auth_router, prefix="/api")
   ```
   Place it before the other routers (order does not strictly matter for FastAPI routers, but convention is auth first).
3. Add middleware **after** app creation but before routers are processed:
   ```python
   app.add_middleware(SessionAuthMiddleware)
   ```
   Note: Starlette middleware wraps the entire app including routers, so registration order relative to `include_router` does not matter for middleware.

**Acceptance criteria:**
- `uv run mypy .` passes.
- `uv run ruff check .` passes.
- Server starts without errors: `uv run uvicorn main:app --reload` (in `server/`).
- `GET /api/auth/status` returns 200 (proves router is mounted and middleware passes it through).
- When no secrets file: all API calls still work (middleware passthrough).

---

### Task 5: Write `server/tests/test_auth.py`

**File:** `/Users/wells/Projects/riglet/server/tests/test_auth.py` (new)

**Test categories:**

1. **Unit tests for `auth.py` functions** (no HTTP):
   - `test_hash_and_verify_password` -- round-trip.
   - `test_verify_password_wrong` -- wrong password returns `False`.
   - `test_create_and_verify_session_token` -- round-trip.
   - `test_verify_expired_token` -- token with `max_age=0` fails.
   - `test_load_secrets_missing_file` -- returns `None`.
   - `test_save_and_load_secrets` -- round-trip to a temp file, verify `0o600` permissions.

2. **Integration tests using `httpx.AsyncClient`** (same pattern as `test_api.py`):
   - `test_auth_status_no_password` -- `GET /api/auth/status` returns `password_set: false`.
   - `test_set_password_first_run` -- `POST /api/auth/set-password` with valid password returns 200 and sets cookie.
   - `test_set_password_too_short` -- returns 422.
   - `test_set_password_already_set` -- returns 403.
   - `test_login_success` -- returns 200 with cookie.
   - `test_login_wrong_password` -- returns 401.
   - `test_login_no_password_configured` -- returns 400.
   - `test_protected_route_without_cookie` -- `GET /api/config` returns 401 when password is set.
   - `test_protected_route_with_cookie` -- `GET /api/config` returns 200 when valid cookie sent.
   - `test_public_route_without_cookie` -- `GET /api/status` returns 200 always.
   - `test_logout_clears_session` -- after logout, protected routes return 401.
   - `test_auth_status_authenticated` -- returns `authenticated: true` with valid cookie.

**Test setup:** Use `tmp_path` fixture to create an isolated secrets file path. Override the secrets path via env var `RIGLET_SECRETS` or by passing `secrets_path` to middleware/functions. Follow the existing conftest pattern from `tests/`.

**Acceptance criteria:**
- `uv run pytest tests/test_auth.py -v` -- all tests pass.
- `uv run pytest` -- full suite still passes (no regressions).
- `uv run mypy .` passes.
- `uv run ruff check .` passes.

---

### Task 6: Create login page `ui/src/routes/login/+page.svelte`

**File:** `/Users/wells/Projects/riglet/ui/src/routes/login/+page.svelte` (new)

**UI spec:**
- Full-page centered card with dark background (matches existing setup wizard aesthetic: `#111` bg, `#1a1a1a` card, `#4a9eff` accent).
- "Riglet" brand heading.
- Single password `<input type="password">` with label "Password".
- Submit button labeled "Log In" (`.primary` class, same as wizard).
- Error message area (red text) shown on failed login.
- On successful login (`POST /api/auth/login` returns 200), redirect to `/` via `goto('/')`.
- On submit, disable button and show "Logging in..." state.
- Pressing Enter in the password field submits the form.

**Script logic:**
- Import `goto` from `$app/navigation`.
- Import `loginApi` from `$lib/api.js` (or inline fetch if api.ts changes are not yet available -- but prefer using the api module).
- On mount: check `GET /api/auth/status`. If `authenticated: true`, redirect to `/`. If `password_set: false`, redirect to `/setup`.

**Acceptance criteria:**
- `npm run build` succeeds.
- Page renders at `/login` in dev server.
- Password field is focused on load.
- Submitting wrong password shows error.
- Submitting correct password redirects to `/`.
- If already authenticated, page redirects to `/`.

---

### Task 7: Update `ui/src/lib/api.ts` -- 401 intercept and auth functions

**File:** `/Users/wells/Projects/riglet/ui/src/lib/api.ts`

**Changes:**

1. In the `request<T>()` function, add a 401 check before the generic error throw:
   ```typescript
   if (res.status === 401) {
       // Avoid redirect loop if already on /login
       if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
           window.location.href = '/login';
       }
       throw new Error('Not authenticated');
   }
   ```

2. Add new exported functions:
   ```typescript
   export function getAuthStatus(): Promise<{ authenticated: boolean; password_set: boolean }> {
       return request<{ authenticated: boolean; password_set: boolean }>('/api/auth/status');
   }

   export function postLogin(password: string): Promise<{ status: string }> {
       return request<{ status: string }>('/api/auth/login', json('POST', { password }));
   }

   export function postLogout(): Promise<{ status: string }> {
       return request<{ status: string }>('/api/auth/logout', { method: 'POST' });
   }

   export function postSetPassword(password: string): Promise<{ status: string }> {
       return request<{ status: string }>('/api/auth/set-password', json('POST', { password }));
   }
   ```

**Acceptance criteria:**
- `npm run build` succeeds with no type errors.
- 401 responses from any API call trigger redirect to `/login`.
- The redirect does not fire if already on `/login` (no infinite loop).
- All four new functions are exported and typed.

---

### Task 8: Add auth guards to `+page.svelte` and `setup/+page.svelte`

**Files:**
- `/Users/wells/Projects/riglet/ui/src/routes/+page.svelte`
- `/Users/wells/Projects/riglet/ui/src/routes/setup/+page.svelte`

**Changes to `+page.svelte`:**
- In the `onMount` handler, before calling `getStatus()`, add an auth check:
  ```typescript
  const auth = await getAuthStatus();
  if (auth.password_set && !auth.authenticated) {
      await goto('/login');
      return;
  }
  ```
- Import `getAuthStatus` from `$lib/api.js`.

**Changes to `setup/+page.svelte`:**
- In the `$effect` block (or add an `onMount`), add auth check:
  ```typescript
  const auth = await getAuthStatus();
  if (auth.password_set && !auth.authenticated) {
      await goto('/login');
      return;
  }
  ```
- Import `getAuthStatus` from `$lib/api.js` and `onMount` from `svelte`.

**Acceptance criteria:**
- When password is set and user is not authenticated, both pages redirect to `/login`.
- When no password is set (first-run), pages load normally.
- When authenticated, pages load normally.
- `npm run build` succeeds.

---

### Task 9: Add logout button to main UI top bar

**File:** `/Users/wells/Projects/riglet/ui/src/routes/+page.svelte`

**Changes:**
- Import `postLogout` from `$lib/api.js`.
- Add a logout button in the `.topbar` header, between the theme button and the setup link (or after the setup link):
  ```svelte
  <button
      class="theme-btn"
      onclick={handleLogout}
      title="Log out"
      aria-label="Log out"
  >out</button>
  ```
  Use text "out" or a simple icon. Style with existing `.theme-btn` class.
- Add handler:
  ```typescript
  async function handleLogout() {
      await postLogout();
      await goto('/login');
  }
  ```
- Import `goto` from `$app/navigation` (already imported).

**Acceptance criteria:**
- Logout button visible in top bar.
- Clicking it calls `POST /api/auth/logout` and redirects to `/login`.
- `npm run build` succeeds.

---

### Task 10: Create `StepSetPassword.svelte` and wire into setup wizard

**Files:**
- `/Users/wells/Projects/riglet/ui/src/lib/components/wizard/StepSetPassword.svelte` (new)
- `/Users/wells/Projects/riglet/ui/src/routes/setup/+page.svelte` (modify)

**`StepSetPassword.svelte` spec:**
- Props: `onPasswordSet: () => void` callback.
- Two password fields: "Password" and "Confirm Password".
- Client-side validation: minimum 8 characters, fields must match.
- Submit button: calls `postSetPassword(password)` from `$lib/api.js`.
- On success: calls `onPasswordSet()`.
- On error: shows error message.
- If password is already set (check via `getAuthStatus()`), show a green checkmark and "Password already configured" message instead of the form.

**Setup wizard changes (`setup/+page.svelte`):**
- Add "Set Password" as the new final step (step index 5), after "Review & Apply" (step 4).
  Update `STEPS` array:
  ```typescript
  const STEPS = ['Welcome', 'Detect Radios', 'Map Audio', 'PTT Method', 'Review & Apply', 'Set Password'];
  ```
  Alternatively, insert it as step 4 (before Review & Apply) if that makes more sense for UX -- but the requirement says it is a new step, so append it at the end.

  Actually, the better UX is: set password comes *after* Review & Apply succeeds. When `applyAndStart()` completes successfully, advance to the Set Password step instead of redirecting to `/`. Then the Set Password step's `onPasswordSet` callback does the redirect.

- Import `StepSetPassword` component.
- Add rendering for the new step:
  ```svelte
  {:else if step === 5}
      <StepSetPassword onPasswordSet={() => goto('/')} />
  ```
- Modify `applyAndStart()`: on success, instead of `goto('/')`, set `step = 5`.

**Acceptance criteria:**
- Password step renders in wizard after successful apply.
- Submitting matching 8+ char passwords calls the API and redirects to `/`.
- Mismatched passwords show client-side error.
- Short passwords show client-side error (and API returns 422 as backstop).
- If password already set, shows confirmation message.
- `npm run build` succeeds.
