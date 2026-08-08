# Party Check-In System — Streamlit Conversion Plan

## Goal
Convert the existing Flask Party Check-In app from Render hosting to Streamlit Community Cloud (free hosting). Test all features locally, enhance code, and update documentation.

## Current Architecture (Flask)
- **Backend**: Flask + SQLAlchemy + Flask-Mail
- **Database**: SQLite (local) / PostgreSQL via Supabase (production)
- **Templates**: Jinja2 HTML templates (5 pages)
- **Features**: Guest registration, QR generation, Stripe payment, email sending, QR scanner, admin dashboard, CSV export, wristband tracking, audio announcements
- **Hosting**: Render + Supabase

## Target Architecture (Streamlit)
- **Backend**: Pure Python with Streamlit widgets
- **Database**: SQLite (local) / PostgreSQL via Supabase (production via `st.secrets`)
- **UI**: Streamlit native components (no templates)
- **Hosting**: Streamlit Community Cloud (free) — streamlit.io
- **QR Scanner**: `st.camera_input` + `pyzbar` for photo-based scanning + manual fallback
- **Audio**: `st.components.v1.html` with JavaScript Web Speech API
- **State**: `st.session_state` for form persistence, pending registrations
- **Navigation**: `st.sidebar.radio` for page switching

## Stage-by-Stage Execution

### Stage 1 — Core Infrastructure
**Files to create/modify:**
1. `utils.py` — Database models (SQLAlchemy, Flask-free), QR generation, email (smtplib), helpers
2. `streamlit_app.py` — Main entry point with sidebar navigation and all page functions
3. `requirements.txt` — Update to Streamlit stack
4. `.streamlit/config.toml` — Streamlit theme and layout config

**Key decisions:**
- Use SQLAlchemy ORM directly (no Flask-SQLAlchemy) — keep same Guest/CheckInLog models
- Replace Flask-Mail with Python `smtplib` + `email.mime`
- Replace Flask `session` with `st.session_state`
- Replace Jinja templates with Streamlit widgets (`st.text_input`, `st.form`, `st.dataframe`, etc.)
- Replace `request.form` with `st.form_submit_button` + `st.text_input`
- Replace `request.args` with `st.query_params` (Streamlit 1.30+)
- Replace `send_file` with `st.download_button`
- Replace `render_template` with direct Streamlit widget calls
- Stripe: Simplify to Zelle-only flow (primary flow per README) — no webhook routes needed in Streamlit
- QR Scanner: `st.camera_input` + `pyzbar` decode + manual text input fallback
- Audio: `st.components.v1.html` with JS `speechSynthesis` triggered by button clicks

### Stage 2 — Page Implementation
Each page is a function in `streamlit_app.py`:

1. **Home** — Stats cards with `st.metric`, navigation cards with `st.columns` + `st.button`
2. **Register** — `st.form` with name, email, ticket count; Zelle payment info; generate QR + send email
3. **My QR** — Display generated QR code with `st.image`, download/print options
4. **Scanner** — `st.camera_input` for photo scanning + `pyzbar` decode + `st.text_input` manual entry + `st.button` mark band given + JS audio announcement
5. **Admin** — `st.dataframe` with guest list, `st.metric` for stats, `st.download_button` for CSV, search/filter

### Stage 3 — Local Testing
- Run `streamlit run streamlit_app.py`
- Test all pages: registration, QR generation, email, scanning, admin, CSV export
- Verify database persistence
- Verify state management
- Write automated test script

### Stage 4 — Browser Testing
- Use Kimi WebBridge to test the Streamlit app in browser
- Or use Playwright to run automated E2E tests
- Capture screenshots for verification

### Stage 5 — Documentation
- Update `README.md` with Streamlit Cloud deployment instructions
- Add `.streamlit/secrets.toml` example
- Add troubleshooting section for Streamlit-specific issues
- Remove Render-specific references
- Add Streamlit Cloud URL format

## File Propagation
- Stage 1 outputs → Stage 2 (utils.py is imported by streamlit_app.py)
- Stage 2 outputs → Stage 3 (test the complete app)
- Stage 3 outputs → Stage 4 (browser testing)
- Stage 4 outputs → Stage 5 (document test results)

## Streamlit Cloud Deployment Notes
- Entry point: `streamlit_app.py` (auto-detected by Streamlit Cloud)
- Secrets: Set via Streamlit Cloud dashboard → Secrets
- Database: SQLite works for ephemeral events; Supabase PostgreSQL for persistence
- No `Procfile`, `gunicorn`, `render.yaml`, `railway.toml` needed
- GitHub repo connected to Streamlit Cloud for auto-deploy
- Free tier: 1GB RAM, 1 CPU, sleeps after inactivity (same as Render)

## Quality Gates
- [ ] All 5 pages render correctly in Streamlit
- [ ] Guest registration creates DB record + generates QR
- [ ] QR code can be scanned (camera input + decode)
- [ ] Check-in updates database and shows audio announcement
- [ ] Admin shows live stats, searchable guest list, CSV download
- [ ] Email sends successfully (with valid SMTP credentials)
- [ ] Database persists across Streamlit reruns
- [ ] Documentation is complete and accurate
