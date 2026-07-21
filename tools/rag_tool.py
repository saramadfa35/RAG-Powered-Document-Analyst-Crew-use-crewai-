"""
Custom RAG Tool for CrewAI
===========================
Implements the full RAG pipeline manually (no external embedding API,
no SerperDev / web search):

    1. CHUNKING   -> _load_and_chunk()
    2. EMBEDDING  -> TfidfVectorizer (fit once at init time, local/offline)
    3. RETRIEVAL  -> _run() : query -> vector -> cosine similarity -> top-k chunks

This file is the "bridge" between CrewAI and the RAG pipeline: CrewAI only
ever sees a BaseTool with a name/description/_run() signature. Everything
RAG-specific is encapsulated inside this class.
"""

import os
import glob
import numpy as np
from typing import Type
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from crewai.tools import BaseTool
except ImportError:
    from crewai_tools import BaseTool


KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")

CHUNK_SIZE_WORDS = 120
CHUNK_OVERLAP_WORDS = 20
TOP_K = 4


class DocSearchInput(BaseModel):
    query: str = Field(
        ..., description="The natural-language question to search for inside the company's internal documents."
    )


class DocumentRAGTool(BaseTool):
    """Custom RAG tool: chunk local docs, TF-IDF embed them, retrieve by cosine similarity."""

    name: str = "doc_search"
    description: str = (
        "Searches the company's internal knowledge base (employee handbook, product spec, "
        "quarterly financial summary) and returns the most relevant text chunks, each tagged "
        "with its source document and chunk id. Use this tool to answer ANY question about "
        "internal company policy, product features, or financial performance. "
        "Do NOT use general knowledge or the internet — only what this tool returns."
    )
    args_schema: Type[BaseModel] = DocSearchInput

    # Pydantic (BaseTool) needs these declared to allow arbitrary attribute assignment
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._chunks: list[str] = []
        self._metadata: list[dict] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._build_index()

    # ------------------------------------------------------------------
    # STEP 1: CHUNKING
    # ------------------------------------------------------------------
    def _load_and_chunk(self):
        """Read every file in knowledge/, split into overlapping word-chunks."""
        filepaths = sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md"))) + \
                    sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "*.txt")))

        for path in filepaths:
            source_name = os.path.basename(path)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            # First split on markdown section headers to keep semantically
            # related content together, then hard-wrap long sections.
            sections = text.split("\n## ")
            for section in sections:
                words = section.split()
                if not words:
                    continue
                start = 0
                while start < len(words):
                    end = start + CHUNK_SIZE_WORDS
                    chunk_words = words[start:end]
                    chunk_text = " ".join(chunk_words)
                    self._chunks.append(chunk_text)
                    self._metadata.append({
                        "source": source_name,
                        "chunk_id": len(self._chunks) - 1,
                    })
                    if end >= len(words):
                        break
                    start = end - CHUNK_OVERLAP_WORDS  # overlap

    # ------------------------------------------------------------------
    # STEP 2: EMBEDDING (fit once, local, no external API)
    # ------------------------------------------------------------------
    def _build_index(self):
        self._load_and_chunk()
        if not self._chunks:
            raise RuntimeError(f"No documents found in {KNOWLEDGE_DIR}")

        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(self._chunks)  # embedding happens here

    # ------------------------------------------------------------------
    # STEP 3: RETRIEVAL (called every time the agent invokes the tool)
    # ------------------------------------------------------------------
    def _run(self, query: str) -> str:
        query_vec = self._vectorizer.transform([query])           # embed the query
        sims = cosine_similarity(query_vec, self._matrix)[0]       # similarity search
        top_idx = np.argsort(sims)[::-1][:TOP_K]

        results = []
        for idx in top_idx:
            score = sims[idx]
            if score <= 0.0:
                continue
            meta = self._metadata[idx]
            results.append(
                f"[Source: {meta['source']} | chunk #{meta['chunk_id']} | relevance: {score:.3f}]\n"
                f"{self._chunks[idx]}"
            )

        if not results:
            return (
                "NO_RELEVANT_CHUNKS_FOUND: The internal documents do not appear to contain "
                "information relevant to this query."
            )

        return "\n\n---\n\n".join(results)