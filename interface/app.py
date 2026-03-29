"""
Web Interface — KnowSure Banking Operations Knowledge Assistant.

Features:
  - Chat interface with confidence scoring display
  - SME escalation notification
  - Source citations (page-level)
  - Follow-up question suggestion buttons
  - Audit log dashboard (second tab)
  - Enter to send, Shift+Enter for newline (fixed)
  - Collection selector
"""

from __future__ import annotations
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr

from orchestration.orchestrator import process_query
from database.audit_db import get_recent_logs, get_summary_stats, initialize_db
from config.settings import ACTIVE_COLLECTION, CHROMA_COLLECTIONS
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Core query handler ────────────────────────────────────────────────────────

def answer_query(user_message, history, selected_collection):
    """Main query handler — routes through orchestrator."""
    if not user_message.strip():
        return "", history, "", _empty_followup_updates()

    logger.info("UI: query received: '%s'", user_message[:80])

    result = process_query(
        query=user_message,
        collection_name=selected_collection,
    )

    # Format sources for display
    sources_text = _format_sources(result.sources, result.from_sme_cache)

    # Append to history
    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": result.answer})

    # Build follow-up button updates
    btn_updates = _build_followup_updates(result.followups)

    return ("", history, sources_text) + tuple(btn_updates)


def _format_sources(sources: list[str], from_cache: bool) -> str:
    if from_cache:
        prefix = "✅ **Verified SME Answer — Sources:**\n"
    else:
        prefix = "**Sources referenced:**\n"

    if not sources:
        return prefix + "_No sources cited._"

    lines = [prefix]
    for i, src in enumerate(sources, 1):
        lines.append(f"{i}. {src}")
    return "\n".join(lines)


def _empty_followup_updates():
    return tuple(gr.update(value="", visible=False) for _ in range(4))


def _build_followup_updates(followups: list[str]):
    updates = []
    for i in range(4):
        if i < len(followups):
            updates.append(gr.update(value=followups[i], visible=True))
        else:
            updates.append(gr.update(value="", visible=False))
    return updates


# ── Audit tab data loader ─────────────────────────────────────────────────────

def load_audit_data():
    """Load recent audit logs for the dashboard tab."""
    try:
        stats = get_summary_stats()
        logs  = get_recent_logs(limit=50)

        stats_md = (
            f"### 📊 Summary\n"
            f"- **Total Queries:** {stats['total_queries']}\n"
            f"- **SME Escalations:** {stats['total_escalations']}\n"
            f"- **Avg Confidence:** {stats['avg_confidence']:.0%}\n"
            f"- **Avg Response Time:** {stats['avg_response_ms']:.0f}ms\n"
        )

        if not logs:
            return stats_md, []

        table_data = []
        for log in logs:
            sources_str = ", ".join(log["sources"][:2]) if log["sources"] else "—"
            table_data.append([
                log["timestamp"],
                log["query"][:60] + ("..." if len(log["query"]) > 60 else ""),
                f"{log['confidence_score']:.0%}",
                log["confidence_label"],
                "Yes" if log["escalated"] else "No",
                sources_str,
                f"{log['total_ms']:.0f}ms",
            ])

        return stats_md, table_data

    except Exception as exc:
        logger.error("Audit tab load error: %s", exc)
        return "Audit log unavailable.", []


# ── UI Builder ────────────────────────────────────────────────────────────────

def build_interface():
    collection_choices = list(CHROMA_COLLECTIONS.values())

    with gr.Blocks(title="KnowSure — Banking Knowledge Assistant") as demo:

        # ── Tab 1: Chat ───────────────────────────────────────────────────────
        with gr.Tab("💬 Knowledge Assistant"):

            gr.Markdown("""
            # 🏦 KnowSure — Banking Operations Knowledge Assistant
            Ask questions about RBI policies, master directions, and regulatory circulars.
            Answers are generated only from the indexed knowledge base with confidence scoring.
            """)

            # Collection selector — no chunk count shown
            with gr.Row():
                collection_dropdown = gr.Dropdown(
                    choices=collection_choices,
                    value=ACTIVE_COLLECTION,
                    label="Knowledge Base Collection",
                    scale=3,
                )

            # Chat window
            chatbot = gr.Chatbot(
                label="Conversation",
                height=450,
                type="messages",
            )

            # Query input — Enter sends, Shift+Enter for newline
            # This is achieved by using lines=1 and submit on enter
            with gr.Row():
                query_input = gr.Textbox(
                    placeholder="Ask a question... (Enter to send, Shift+Enter for new line)",
                    label="Your Question",
                    scale=5,
                    lines=1,       # single line — Enter sends
                    max_lines=5,   # expands up to 5 lines as user types
                )
                submit_btn = gr.Button("Ask ➤", variant="primary", scale=1)

            # Sources panel
            sources_display = gr.Markdown(value="")

            # Follow-up suggestions
            gr.Markdown("### 💡 Suggested Follow-up Questions")
            with gr.Row():
                fq1 = gr.Button("", visible=False, variant="secondary", size="sm")
                fq2 = gr.Button("", visible=False, variant="secondary", size="sm")
            with gr.Row():
                fq3 = gr.Button("", visible=False, variant="secondary", size="sm")
                fq4 = gr.Button("", visible=False, variant="secondary", size="sm")

            followup_btns = [fq1, fq2, fq3, fq4]

            clear_btn = gr.Button("🗑️ Clear Conversation", variant="secondary")

            gr.Markdown(
                "_⚠️ Always verify critical regulatory decisions with original source documents. "
                "Confidence score is based on semantic similarity of retrieved content._"
            )

        # ── Tab 2: Audit Log ──────────────────────────────────────────────────
        with gr.Tab("📋 Audit Log"):

            gr.Markdown("## 📋 Query Audit Dashboard\nAll queries, confidence scores, and SME escalations are recorded here.")

            refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
            stats_display = gr.Markdown(value="Loading...")

            audit_table = gr.Dataframe(
                headers=[
                    "Timestamp", "Query", "Confidence",
                    "Level", "Escalated", "Sources", "Response Time"
                ],
                datatype=["str", "str", "str", "str", "str", "str", "str"],
                label="Recent Queries",
                interactive=False,
                wrap=True,
            )

            def refresh_audit():
                stats_md, table_data = load_audit_data()
                return stats_md, table_data

            refresh_btn.click(
                fn=refresh_audit,
                outputs=[stats_display, audit_table],
            )

            demo.load(
                fn=refresh_audit,
                outputs=[stats_display, audit_table],
            )

        # ── Event wiring ──────────────────────────────────────────────────────
        submit_inputs  = [query_input, chatbot, collection_dropdown]
        submit_outputs = [query_input, chatbot, sources_display] + followup_btns

        submit_btn.click(
            fn=answer_query,
            inputs=submit_inputs,
            outputs=submit_outputs,
        )

        # Enter key submits (lines=1 means Enter triggers submit by default in Gradio)
        query_input.submit(
            fn=answer_query,
            inputs=submit_inputs,
            outputs=submit_outputs,
        )

        # Follow-up buttons populate the input box
        for btn in followup_btns:
            btn.click(
                fn=lambda text: text,
                inputs=btn,
                outputs=query_input,
            )

        clear_btn.click(
            fn=lambda: (
                [],
                "",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            ),
            outputs=[chatbot, sources_display] + followup_btns,
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting KnowSure Banking Knowledge Assistant...")

    # Initialize databases
    initialize_db()
    logger.info("Audit database ready.")

    # Pre-load embedding model at startup — eliminates 17s cold start
    logger.info("Warming up embedding model (this takes ~17 seconds)...")
    t0 = time.time()
    from embeddings.embedder import _get_model
    _get_model()
    logger.info("Embedding model ready in %.1fs.", time.time() - t0)

    app = build_interface()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )