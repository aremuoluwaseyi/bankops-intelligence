# BankOps Intelligence — Public Interactive Demonstration

**Status:** In development, Phase 10 Step 7 (October 2026).  
**Purpose:** Interactive synthetic digital banking operations incident analytics and service dependency investigation.

## Launch the public demo
Once deployed, use the Streamlit Community Cloud app URL. This repository does not yet have a verified public demo link.

## What you can explore
- Historical synthetic alert records and incident filtering
- Evidence-grounded investigation details and diagnostic checks
- Declared service/infrastructure dependencies and component status observations
- Timestamped synthetic health-check replay

**Important:** All data and institutions are fictional. This is a **historical synthetic demonstration**, not a live production monitoring system. Suspected components are hypotheses, not confirmed root causes. No external alerts or remediation actions occur.

## Run locally
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Deploy with Streamlit Community Cloud
1. Create a public GitHub repository named `bankops-intelligence`.
2. Upload **the contents of this folder** to the repository root (not the ZIP file itself).
3. In https://share.streamlit.io click **Create app** → **Deploy a public app from GitHub**.
4. Select your repository, branch `main`, and main file `app.py`.
5. Deploy, then test chart clicks, incident selection, topology, and replay in a private browser window.
6. Copy the actual deployed URL into your portfolio's **Launch Live Demo** link.

## Hosting and privacy
The included SQLite outbox is a **synthetic, read-only demonstration snapshot**. Streamlit Community Cloud may restart or sleep. User session selections should not be treated as durable data; do not enter personal or banking information. This demo is not connected to banking systems.

## Tech stack
Python, Streamlit, pandas, Altair, Graphviz, SQLite, deterministic evidence-grounded investigation.
