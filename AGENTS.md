# Party Check-In — Project Agent Notes

## ⚠️ Read this first

`.streamlit/secrets.toml` in a local checkout may contain the **production** Supabase
`DATABASE_URL` and **real Gmail SMTP credentials**. Streamlit loads secrets from
`./.streamlit/secrets.toml` relative to the **current working directory**, so running
`streamlit run streamlit_app.py` from the project root connects to the live guest list and
sends real email.

**To exercise the UI safely, run the app from a different working directory** that has its own
`.streamlit/secrets.toml` pointing at `sqlite:///local.db` with `MAIL_USERNAME` blank:

```bash
mkdir -p /tmp/pc-sandbox/.streamlit
cat > /tmp/pc-sandbox/.streamlit/secrets.toml <<'EOF'
DATABASE_URL = "sqlite:///local_e2e.db"
MAIL_USERNAME = ""
MAIL_PASSWORD = ""
ADMIN_PASSWORD = "testadmin123"
TICKET_PRICE_CENTS = "2000"
ZELLE_INFO = "test-zelle@example.com"
EOF
cd /tmp/pc-sandbox && python -m streamlit run /path/to/party-checkin/streamlit_app.py --server.port 8599
```

The `tests/e2e` suite does exactly this automatically.

## Live App
- **Streamlit Cloud:** `https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/`
- **GitHub repo:** `git@github.com:aladin-genie/party-checkin.git` (branch `main`, entry `streamlit_app.py`)
- **Streamlit Cloud account:** `aladin-genie` (yvh1225@gmail.com Chrome session)
- **Supabase project:** `zqpdpbyxohqthoikzotv`
- **Python version:** 3.12 (set in Streamlit Cloud → Advanced settings)

## Required Streamlit Cloud Secrets
`DATABASE_URL` (Supabase **Pooler** URL), `ADMIN_PASSWORD`, `TICKET_PRICE_CENTS`, `ZELLE_INFO`,
`SECRET_KEY`, `APP_URL`, and the mail block (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`,
`MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`).

`ADMIN_PASSWORD` is **mandatory** — `verify_admin_password` fails closed, so an unset secret
locks everyone out of the admin dashboard rather than letting everyone in.

## Code Layout
| File | Rule |
|------|------|
| `config.py` | The only place that reads config secrets and the only place event date/venue/name strings live. Never hardcode them elsewhere. |
| `utils.py` | Models + service layer + validation + email. **No Streamlit UI code.** |
| `theme.py` | All CSS and HTML component builders. Builders return HTML strings and `html.escape()` their inputs. |
| `streamlit_app.py` | Pages and navigation only. Must not open DB sessions or touch the ORM — call a service function in `utils.py` instead. |

## Local Development
- Tests: `python -m unittest test_party_checkin -v`
- E2E: `python -m pytest tests/e2e -v` (needs `pytest`, `playwright`, `playwright install chromium`)
- Do **not** commit `.streamlit/secrets.toml`.

## Behavior worth knowing before you change things
- **Check-in is gated by an event-time window.** `utils.check_in_by_code()` refuses outside it
  and returns `status="not_open"`. Mode is persisted in the `app_settings` table
  (`checkin_mode` = `auto` | `open` | `closed`, default `auto`). Tests must call
  `utils.set_checkin_mode(utils.CHECKIN_MODE_OPEN)` in `setUp` — otherwise every check-in test
  fails, because the real window doesn't open until Oct 9, 2026. Admin-initiated check-ins pass
  `bypass_window=True`.
- **Registration email is fire-and-forget** (`utils.send_qr_email_async`). It snapshots the SMTP
  secrets on the calling thread; the worker must never touch `st.*`. Don't assume a synchronous
  result. `send_qr_email()` stays synchronous for the Resend buttons.
- **`plus_one_name` holds up to 20 newline-joined names**, not one. The column is
  `VARCHAR(1000)` and `init_db()` widens it on Postgres. Validate through
  `utils.sanitize_guest_names()`.
- **`st.data_editor` paints cells on a canvas** with no accessibility mirror, so E2E tests
  cannot read cell text. Assert on the app's own "N of M guests shown" caption instead, and
  cover mutations through `utils.apply_guest_changes()` at the service level.
- **Never call `st.success()` immediately before `st.rerun()`** — the rerun discards the frame
  and the message is never painted. Use `_set_flash()` / `_render_flash()`.
- **Streamlit checkboxes can't be driven by Playwright's `.check()`** (the real input is
  zero-width). Click the visible `<label>` and assert on `aria-checked`.

## Known Pitfalls
- **Streamlit re-runs the whole script on every interaction.** Anything expensive at module
  scope runs on every click. `init_db()` is therefore wrapped in `ensure_db_ready()`
  (`@st.cache_resource`), and stats reads are wrapped in `@st.cache_data(ttl=10)` in
  `streamlit_app.py`. Call `st.cache_data.clear()` after any mutation or the numbers go stale.
- Supabase direct `db.*.supabase.co` host may not resolve; use the **Pooler** host.
- `datetime.utcnow()` is deprecated; use `_utc_now()` in `utils.py`.
- The registration ticket count must be rendered **outside** the `st.form(...)` block so the
  live total updates.
- `checkin_time` can be NULL while `checked_in` is true. Never call `.strftime()` on it
  directly — use `utils.format_dt()`.
- Python 3.14 cannot import `altair`, so `st.bar_chart` breaks there. Develop on 3.12.
- Streamlit is pinned to 1.40.0. `st.pills`, `st.segmented_control`, `st.badge`, and
  `st.metric(border=...)` do **not** exist in it.

## Common Verification Flow
1. Run unit tests, then the E2E suite.
2. Push to `main`.
3. Streamlit Cloud → **Manage app** → **Reboot app** (or wait for auto-deploy).
4. Verify: no DB warning banner; hero date/venue and Zelle info correct; ticket count updates
   the total live; admin login works and the tabs render.
5. Delete any test registrations you created.
