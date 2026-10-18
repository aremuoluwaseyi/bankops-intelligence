# Publishing checklist

- [ ] Upload the **unzipped contents** at the repository root.
- [ ] Check `app.py`, `requirements.txt`, `src/`, `data/raw/`, and `data/processed/phase9_step3_alert_outbox.sqlite` appear on GitHub.
- [ ] Confirm the repo contains **synthetic data only**; do not upload `.env`, real bank logs, secrets, or local customer data.
- [ ] Deploy on Streamlit Community Cloud from branch `main`, entrypoint `app.py`.
- [ ] Wait for build, open the public URL, and check all views and controls.
- [ ] Check in a private/incognito window (not logged into GitHub) that the app is accessible.
- [ ] Add the real URL to your portfolio project card.
- [ ] If deployment errors, use **Manage app → Logs**, copy the error, and ask for help; don't upload passwords or tokens.

Note: The demo includes a snapshot of generated synthetic SQLite alerts. This is not a live data source or durable multiuser database.
