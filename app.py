"""
app.py
======
Minimal Streamlit interface for the RAG-Powered Document Analyst Crew.

Usage:
    streamlit run app.py

Type a question, click Run, and the same 3-agent crew (Document Researcher
-> Fact Checker -> Report Writer) that runs from main.py executes here,
and the resulting report is shown + downloadable.
"""

import os
import glob

import streamlit as st

from crew import build_crew

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")

st.set_page_config(page_title="Document Analyst Crew", page_icon="📄", layout="centered")

# ---------------------------------------------------------------------
# Sidebar: show what's actually in the knowledge base, for transparency
# ---------------------------------------------------------------------
with st.sidebar:
    st.subheader("Knowledge base")
    st.caption("These are the only files the crew is allowed to answer from.")
    kb_files = sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "*")))
    if kb_files:
        for f in kb_files:
            st.markdown(f"- `{os.path.basename(f)}`")
    else:
        st.warning("No files found in knowledge/.")

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
st.title("📄 Document Analyst Crew")
st.caption(
    "Ask a question about the company. It's answered strictly from the "
    "internal documents on the left — no web search, no outside knowledge."
)

question = st.text_area(
    "Your question",
    placeholder="e.g. What is the company's remote work policy and how did Q3 revenue compare to Q2?",
    height=90,
)

run_clicked = st.button("Run", type="primary", disabled=not question.strip())

if run_clicked:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with st.spinner("Researching → fact-checking → writing report... this can take a minute or two."):
        try:
            crew = build_crew(question.strip())
            crew.kickoff()

            report_path = os.path.join(OUTPUT_DIR, "report.md")
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    st.session_state["last_report"] = f.read()
                st.session_state["last_question"] = question.strip()
            else:
                st.error("The crew finished but output/report.md wasn't created.")
        except Exception as e:
            st.error(f"Run failed: {e}")

if "last_report" in st.session_state:
    st.divider()
    st.subheader("Report")
    st.caption(f"Question: {st.session_state['last_question']}")
    st.markdown(st.session_state["last_report"])
    st.download_button(
        "⬇️ Download as .md",
        data=st.session_state["last_report"],
        file_name="report.md",
        mime="text/markdown",
    )