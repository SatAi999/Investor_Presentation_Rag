import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Investor Presentation RAG",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Investor Presentation Q&A")
st.caption("Upload an investor presentation PDF, then ask analyst-style questions with citations.")

# ── Sidebar: Upload & Ingest ──────────────────────────────────────────────────
with st.sidebar:
    st.header("1. Upload Presentation")
    uploaded = st.file_uploader("Choose a PDF", type=["pdf"])
    top_k = st.slider("Chunks to retrieve (top_k)", min_value=1, max_value=10, value=5)

    if uploaded and st.button("Ingest PDF", type="primary"):
        with st.spinner("Parsing, embedding, and storing chunks..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/ingest",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"✅ {data['message']}")
                    st.session_state["ingested"] = True
                    st.session_state["doc_name"] = data["document"]
                    st.session_state["chunk_count"] = data["chunk_count"]
                else:
                    st.error(f"Error: {resp.json().get('detail', resp.text)}")
            except requests.exceptions.ConnectionError:
                st.error(
                    "Cannot connect to API. Start the server with:\n"
                    "`uvicorn app.main:app --reload`"
                )

    if st.session_state.get("ingested"):
        st.info(
            f"📄 **{st.session_state.get('doc_name', 'document')}**\n\n"
            f"{st.session_state.get('chunk_count', 0)} chunks indexed"
        )

    st.divider()
    st.header("API Health")
    if st.button("Check Health"):
        try:
            h = requests.get(f"{API_BASE}/health", timeout=5)
            st.json(h.json())
        except Exception as e:
            st.error(str(e))

# ── Main: Q&A ─────────────────────────────────────────────────────────────────
st.subheader("Ask a Question")

question = st.text_input(
    "Question",
    placeholder="e.g. What was the revenue in the latest reported period?",
    label_visibility="collapsed",
)

if st.button("Ask", type="primary") and question:
    if not st.session_state.get("ingested"):
        st.warning("Please upload and ingest a PDF first using the sidebar.")
    else:
        with st.spinner("Retrieving evidence and generating answer..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/query",
                    json={"question": question, "top_k": top_k},
                    timeout=180,
                )
                if resp.status_code == 200:
                    data = resp.json()

                    st.subheader("Answer")
                    st.write(data["answer"])

                    if data["limitations"]:
                        for lim in data["limitations"]:
                            st.warning(f"⚠️ {lim}")

                    st.subheader("Citations")
                    if data["citations"]:
                        for c in data["citations"]:
                            with st.expander(f"📄 Page {c['page']}"):
                                st.caption(f"Chunk ID: `{c['chunk_id']}`")
                                st.write(c["excerpt"])
                    else:
                        st.info("No citations returned.")

                    with st.expander("Retrieval Details"):
                        st.json(data["retrieval"])
                else:
                    st.error(resp.json().get("detail", resp.text))
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to API. Make sure it is running.")
