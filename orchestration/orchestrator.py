"""
Agent Orchestrator — KnowSure.

Central controller that coordinates the full query pipeline:

  1. SME Cache Check      → return cached answer if similar query exists
  2. Retrieval            → embed query, search ChromaDB
  3. Validation           → compute confidence, decide escalation
  4. LLM Generation       → generate grounded response
  5. SME Escalation       → flag low-confidence queries
  6. Audit Logging        → record everything

This module is the single entry point called by the UI.
The UI does not call retriever, LLM, or validator directly.
"""

from __future__ import annotations
import time

from retrieval.retriever import retrieve, format_context
from generation.llm_interface import generate_response, generate_followups
from validation.validator import validate, confidence_label
from database.audit_db import log_query
from database.sme_cache import find_cached_answer
from embeddings.embedder import embed_query
from config.settings import LLM_PROVIDER, CONFIDENCE_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)


class OrchestratorResult:
    """Structured result returned to the UI after full pipeline execution."""

    def __init__(
        self,
        answer: str,
        sources: list[str],
        confidence_score: float,
        confidence_label_str: str,
        escalated: bool,
        from_sme_cache: bool,
        followups: list[str],
        timing: dict,
    ):
        self.answer               = answer
        self.sources              = sources
        self.confidence_score     = confidence_score
        self.confidence_label_str = confidence_label_str
        self.escalated            = escalated
        self.from_sme_cache       = from_sme_cache
        self.followups            = followups
        self.timing               = timing


def process_query(
    query: str,
    collection_name: str | None = None,
    confidence_threshold: float | None = None,
) -> OrchestratorResult:
    """
    Execute the full KnowSure pipeline for a user query.

    Args:
        query:                User's natural language question.
        collection_name:      ChromaDB collection to search.
        confidence_threshold: Override default threshold for this query.

    Returns:
        OrchestratorResult with answer, sources, confidence, and metadata.
    """
    t_total_start = time.time()
    threshold = confidence_threshold if confidence_threshold is not None else CONFIDENCE_THRESHOLD

    logger.info("Orchestrator: processing query '%s'", query[:80])

    # ── Step 1: Embed query (needed for SME cache check) ──────────────────────
    t0 = time.time()
    query_embedding = embed_query(query)
    t_embed = (time.time() - t0) * 1000

    # ── Step 2: SME Cache Check ───────────────────────────────────────────────
    cached = find_cached_answer(query_embedding)

    if cached:
        logger.info("Orchestrator: SME cache hit — returning cached answer.")
        t_total = (time.time() - t_total_start) * 1000

        log_query(
            query=query,
            collection=collection_name or "default",
            confidence_score=cached["similarity_score"],
            confidence_label=confidence_label(cached["similarity_score"]),
            escalated=False,
            sources=cached["sources"],
            answer_snippet=cached["sme_answer"],
            llm_provider="sme_cache",
            total_ms=t_total,
        )

        return OrchestratorResult(
            answer=f"✅ **Verified SME Answer**\n\n{cached['sme_answer']}",
            sources=cached["sources"],
            confidence_score=cached["similarity_score"],
            confidence_label_str=confidence_label(cached["similarity_score"]),
            escalated=False,
            from_sme_cache=True,
            followups=[],
            timing={"embed_ms": t_embed, "total_ms": t_total},
        )

    # ── Step 3: Vector Retrieval ──────────────────────────────────────────────
    t0 = time.time()
    chunks = retrieve(
        query=query,
        collection_name=collection_name,
        query_embedding=query_embedding,   # reuse already-computed embedding
    )
    t_retrieval = (time.time() - t0) * 1000
    logger.info("TIMING | Retrieval: %.1fms", t_retrieval)

    # ── Step 4: Validation & Confidence Scoring ───────────────────────────────
    validation = validate(chunks, threshold=threshold)
    conf_label = confidence_label(validation.confidence_score)

    logger.info(
        "Orchestrator: confidence=%.4f label=%s escalate=%s",
        validation.confidence_score, conf_label, validation.escalate_to_sme,
    )

    # ── Step 5: SME Escalation Path ───────────────────────────────────────────
    if validation.escalate_to_sme:
        t_total = (time.time() - t_total_start) * 1000

        escalation_answer = (
            f"⚠️ **Low Confidence Response** ({conf_label} — {validation.confidence_score:.0%})\n\n"
            f"{validation.reason}\n\n"
            "📧 **Contacting SME...** This query has been flagged and forwarded to a subject "
            "matter expert for a verified response. The SME's answer will be stored and "
            "used to respond to similar queries in the future.\n\n"
            "_Please check back later or consult your compliance team directly._"
        )

        escalation_sources = [c.get("source", "Unknown") for c in chunks[:2]] if chunks else []

        log_query(
            query=query,
            collection=collection_name or "default",
            confidence_score=validation.confidence_score,
            confidence_label=conf_label,
            escalated=True,
            sources=escalation_sources,
            answer_snippet=escalation_answer,
            llm_provider="escalated",
            retrieval_ms=t_retrieval,
            total_ms=t_total,
        )

        return OrchestratorResult(
            answer=escalation_answer,
            sources=escalation_sources,
            confidence_score=validation.confidence_score,
            confidence_label_str=conf_label,
            escalated=True,
            from_sme_cache=False,
            followups=[],
            timing={"embed_ms": t_embed, "retrieval_ms": t_retrieval, "total_ms": t_total},
        )

    # ── Step 6: LLM Response Generation ──────────────────────────────────────
    context = format_context(chunks)

    t0 = time.time()
    result = generate_response(
        query=query,
        context=context,
        retrieved_chunks=chunks,
    )
    t_llm = (time.time() - t0) * 1000
    logger.info("TIMING | LLM: %.1fms", t_llm)

    answer  = result["answer"]
    sources = result["sources"]

    # Prepend confidence indicator to the answer
    answer_with_confidence = (
        f"{conf_label} Confidence ({validation.confidence_score:.0%})\n\n"
        f"{answer}"
    )

    # ── Step 7: Follow-up Question Generation ────────────────────────────────
    t0 = time.time()
    followups = generate_followups(query=query, answer=answer)
    t_followup = (time.time() - t0) * 1000
    logger.info("TIMING | Follow-ups: %.1fms", t_followup)

    # ── Step 8: Audit Logging ─────────────────────────────────────────────────
    t_total = (time.time() - t_total_start) * 1000
    logger.info("TIMING | Total: %.1fms", t_total)

    log_query(
        query=query,
        collection=collection_name or "default",
        confidence_score=validation.confidence_score,
        confidence_label=conf_label,
        escalated=False,
        sources=sources,
        answer_snippet=answer,
        llm_provider=LLM_PROVIDER,
        retrieval_ms=t_retrieval,
        llm_ms=t_llm,
        total_ms=t_total,
    )

    return OrchestratorResult(
        answer=answer_with_confidence,
        sources=sources,
        confidence_score=validation.confidence_score,
        confidence_label_str=conf_label,
        escalated=False,
        from_sme_cache=False,
        followups=followups,
        timing={
            "embed_ms":     t_embed,
            "retrieval_ms": t_retrieval,
            "llm_ms":       t_llm,
            "followup_ms":  t_followup,
            "total_ms":     t_total,
        },
    )