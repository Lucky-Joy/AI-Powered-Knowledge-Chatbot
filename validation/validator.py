"""
Validation module — KnowSure.

Evaluates retrieval confidence based on cosine similarity scores
and decides whether the response is confident enough to return directly
or should be escalated to an SME.

Confidence is derived from ChromaDB's cosine distance scores.
ChromaDB returns distance (lower = more similar), so we convert:
    confidence = 1 - cosine_distance

The CONFIDENCE_THRESHOLD is a hyperparameter in config/settings.py.
Default: 0.75 — queries scoring below this are flagged for SME escalation.
"""

from __future__ import annotations
from config.settings import CONFIDENCE_THRESHOLD, MIN_CHUNKS_REQUIRED
from utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Holds the outcome of a validation check."""

    def __init__(
        self,
        confidence_score: float,
        is_confident: bool,
        escalate_to_sme: bool,
        reason: str,
    ):
        self.confidence_score = round(confidence_score, 4)
        self.is_confident = is_confident
        self.escalate_to_sme = escalate_to_sme
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "confidence_score": self.confidence_score,
            "is_confident":     self.is_confident,
            "escalate_to_sme":  self.escalate_to_sme,
            "reason":           self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"ValidationResult(score={self.confidence_score}, "
            f"confident={self.is_confident}, escalate={self.escalate_to_sme})"
        )


def validate(
    chunks: list[dict],
    threshold: float | None = None,
) -> ValidationResult:
    """
    Validate retrieval quality and determine confidence level.

    Args:
        chunks:    Retrieved chunks from ChromaDB, each with a 'score' field
                   (cosine distance — lower is better).
        threshold: Override the default CONFIDENCE_THRESHOLD for this call.
                   If None, uses the value from settings (hyperparameter).

    Returns:
        ValidationResult with confidence score and escalation decision.
    """
    effective_threshold = threshold if threshold is not None else CONFIDENCE_THRESHOLD

    # No chunks retrieved at all
    if not chunks or len(chunks) < MIN_CHUNKS_REQUIRED:
        logger.warning("Validation: No chunks retrieved. Escalating to SME.")
        return ValidationResult(
            confidence_score=0.0,
            is_confident=False,
            escalate_to_sme=True,
            reason="No relevant content found in knowledge base.",
        )

    # Convert cosine distances to similarity scores
    # ChromaDB cosine distance: 0 = identical, 2 = opposite
    # We use: confidence = 1 - distance (clamped to [0, 1])
    similarity_scores = [
        max(0.0, 1.0 - chunk.get("score", 1.0))
        for chunk in chunks
    ]

    # Use the best (highest) similarity score as the confidence signal
    best_score = max(similarity_scores)
    avg_score  = sum(similarity_scores) / len(similarity_scores)

    # Primary confidence metric: best chunk similarity
    confidence = best_score

    logger.info(
        "Validation: best_score=%.4f avg_score=%.4f threshold=%.4f",
        best_score, avg_score, effective_threshold,
    )

    if confidence >= effective_threshold:
        return ValidationResult(
            confidence_score=confidence,
            is_confident=True,
            escalate_to_sme=False,
            reason=f"Confidence {confidence:.2%} meets threshold {effective_threshold:.2%}.",
        )
    else:
        logger.warning(
            "Validation: confidence %.4f below threshold %.4f — SME escalation triggered.",
            confidence, effective_threshold,
        )
        return ValidationResult(
            confidence_score=confidence,
            is_confident=False,
            escalate_to_sme=True,
            reason=(
                f"Confidence {confidence:.2%} is below threshold {effective_threshold:.2%}. "
                f"Query escalated to SME for verified response."
            ),
        )


def confidence_label(score: float) -> str:
    """
    Return a human-readable confidence label for display in the UI.

    Args:
        score: Confidence score between 0.0 and 1.0.

    Returns:
        String label: High / Medium / Low / Very Low
    """
    if score >= 0.85:
        return "🟢 High"
    elif score >= 0.75:
        return "🟡 Medium"
    elif score >= 0.50:
        return "🟠 Low"
    else:
        return "🔴 Very Low"