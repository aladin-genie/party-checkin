# Party Check-In — Project Agent Notes

## Live App
- **Streamlit Cloud:** `https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/`
- **GitHub repo:** `git@github.com:aladin-genie/party-checkin.git` (branch `main`, entry `streamlit_app.py`)
- **Streamlit Cloud account:** `aladin-genie` (yvh1225@gmail.com Chrome session)
- **Supabase project:** `zqpdpbyxohqthoikzotv`
- **Current admin password:** `party2026` (set via Streamlit Cloud secrets)

## Required Streamlit Cloud Secrets
- `DATABASE_URL` → Supabase connection (use the Pooler URL)
- `TICKET_PRICE_CENTS` → e.g. `2000` for $20.00
- `ZELLE_INFO` → e.g. `dallashudugaru@gmail.com`
- `ADMIN_PASSWORD` → e.g. `party2026`
- `SECRET_KEY` → random secret
- Email secrets (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`) only if using QR email.

## Local Development
- Run: `source venv/bin/activate && streamlit run streamlit_app.py`
- Tests: `python -m unittest test_party_checkin -v`
- Do **not** commit `.streamlit/secrets.toml`.

## Common Verification Flow
1. Push changes to `main`.
2. In Streamlit Cloud app header → **Manage app** → **Reboot app** (or wait for auto-deploy).
3. Verify no DB warning banner.
4. Verify hero banner date/venue and Zelle info.
5. On Register page, change ticket count and confirm **Total to Pay** updates immediately.
6. Verify admin dashboard loads and stats/traffic counters work.

## Known Pitfalls
- Supabase direct `db.*.supabase.co` host may not resolve; use the **Pooler** host from Supabase dashboard settings.
- `datetime.utcnow()` is deprecated; use the `_utc_now()` helper in `utils.py` or `datetime.now(timezone.utc).replace(tzinfo=None)`.
- The registration ticket count must be rendered **outside** the `st.form(...)` block for live total updates.

## Reusable Skill & Agent Dispatch
- Load the user-scope skill **`party-checkin-deploy`** for the standard deploy-verify workflow.
- When delegating to a subagent, use `subagent_type: "coder"` and pass this prompt template:

```
You are handling a deploy/verify task for the Party Check-In app.
Context:
- Repo: aladin-genie/party-checkin, branch main, entry streamlit_app.py
- Local path: /Users/yash/Downloads/party-checkin-master
- Live app: https://party-checkin-hqedxmr3wfmtsdfxr9zjlq.streamlit.app/
- Streamlit Cloud workspace: aladin-genie (yvh1225@gmail.com account)
- Supabase project: zqpdpbyxohqthoikzotv
- Admin password is in AGENTS.md
- Read AGENTS.md and README.md first, then follow the party-checkin-deploy skill.
Task: {{task}}
Required:
1. Run local tests and fix any failures before deploying.
2. Push changes to main (do not force-push).
3. Verify the live app via Kimi WebBridge (use session party-checkin-verify).
4. Clean up any test registrations you create.
5. Report verified stats and any issues.
```
