import os
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Self-Healing CI/CD Dashboard", layout="wide")
st.title("Self-Healing CI/CD Incident Dashboard")

col_btn, col_info = st.columns([1, 4])
with col_btn:
    if st.button("Refresh Incidents", use_container_width=True):
        st.rerun()
with col_info:
    st.caption(f"Connected Orchestrator: `{ORCHESTRATOR_URL}`")

try:
    response = httpx.get(f"{ORCHESTRATOR_URL}/incidents", timeout=5.0)
    response.raise_for_status()
    incidents = response.json()
except Exception as exc:
    st.error(f"Could not connect to Orchestrator at {ORCHESTRATOR_URL}: {exc}")
    incidents = []

col1, col2, col3 = st.columns(3)
col1.metric("Total Incidents", len(incidents))
col2.metric(
    "Auto-Rollbacks Succeeded",
    sum(1 for i in incidents if i.get("rollback_status") == "SUCCESS"),
)
col3.metric(
    "Tickets Opened",
    sum(1 for i in incidents if i.get("issue_url")),
)

st.divider()

if not incidents:
    st.info("No incidents recorded yet. Push a broken commit to trigger the self-healing pipeline.")

for inc in incidents:
    commit_short = (inc.get("commit_sha") or "")[:7]
    prev_short = (inc.get("previous_good_sha") or "")[:7]
    rollback_short = (inc.get("rollback_commit_sha") or "")[:7]
    header = (
        f"[{inc.get('status', 'UNKNOWN')}] {inc.get('id')} — "
        f"Commit {commit_short} | Severity: {inc.get('severity', 'UNKNOWN')}"
    )
    with st.expander(header, expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Rollback Status:** `{inc.get('rollback_status', 'PENDING')}`")
        c2.write(f"**Restored Snapshot:** `{prev_short or 'N/A'}`")
        c3.write(f"**Rollback Commit:** `{rollback_short or 'N/A'}`")

        st.markdown(f"**Root Cause:** {inc.get('root_cause') or 'Pending analysis...'}")
        if inc.get("suggested_fix"):
            st.markdown(f"**Suggested Fix:**\n\n{inc['suggested_fix']}")
        if inc.get("issue_url"):
            st.markdown(f"[Open GitHub Ticket]({inc['issue_url']})")
