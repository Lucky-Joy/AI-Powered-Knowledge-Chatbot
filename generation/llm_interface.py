from __future__ import annotations
import os
from config.settings import LLM_PROVIDER, MAX_TOKENS
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_response(query, context, retrieved_chunks=None):
    provider = LLM_PROVIDER.lower()
    if provider == "groq":
        return _generate_groq(query, context, retrieved_chunks)
    elif provider == "gemini":
        return _generate_gemini(query, context, retrieved_chunks)
    elif provider == "anthropic":
        return _generate_anthropic(query, context, retrieved_chunks)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'")


def _generate_groq(query, context, retrieved_chunks):
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    model = "llama-3.3-70b-versatile"
    response = client.chat.completions.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user",   "content": _build_prompt(query, context)},
        ],
    )
    return {
        "answer":  response.choices[0].message.content.strip(),
        "sources": _extract_sources(retrieved_chunks or []),
        "model":   model,
    }


def _generate_gemini(query, context, retrieved_chunks):
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    model_name = "gemini-1.5-flash"
    model = genai.GenerativeModel(model_name, system_instruction=_system_prompt())
    response = model.generate_content(_build_prompt(query, context))
    return {
        "answer":  response.text.strip(),
        "sources": _extract_sources(retrieved_chunks or []),
        "model":   model_name,
    }


def _generate_anthropic(query, context, retrieved_chunks):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    model = "claude-sonnet-4-20250514"
    message = client.messages.create(
        model=model, max_tokens=MAX_TOKENS,
        system=_system_prompt(),
        messages=[{"role": "user", "content": _build_prompt(query, context)}],
    )
    return {
        "answer":  message.content[0].text.strip(),
        "sources": _extract_sources(retrieved_chunks or []),
        "model":   model,
    }


def _system_prompt():
    return (
        "You are an internal knowledge assistant for a banking operations team. "
        "Answer ONLY based on the context provided. Do not use external knowledge. "
        "If the answer is not in the context, say so clearly. "
        "Cite source documents where relevant."
    )


def _build_prompt(query, context):
    return (
        f"RETRIEVED CONTEXT:\n{'='*60}\n{context}\n{'='*60}\n\n"
        f"QUESTION: {query}\n\n"
        f"Answer based solely on the context above and cite sources."
    )


def _extract_sources(chunks):
    seen, sources = set(), []
    for chunk in chunks:
        citation = f"{chunk.get('source','Unknown')} (Page {chunk.get('page','N/A')})"
        if citation not in seen:
            seen.add(citation)
            sources.append(citation)
    return sources
def generate_followups(query: str, answer: str) -> list:
    """
    Generate 4 relevant follow-up questions based on the query and answer.
    Uses a cheaper/faster call since this is supplementary.
    """
    try:
        provider = LLM_PROVIDER.lower()

        prompt = (
            f"A user asked: '{query}'\n\n"
            f"The answer was: '{answer[:500]}'\n\n"
            f"Generate exactly 4 short, specific follow-up questions the user might ask next. "
            f"Each question should be on a new line. No numbering, no bullets, just the questions. "
            f"Keep each question under 15 words. Focus on banking and regulatory context."
        )

        if provider == "groq":
            from groq import Groq
            client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content.strip()

        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
            model = genai.GenerativeModel("gemini-1.5-flash")
            raw = model.generate_content(prompt).text.strip()

        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
        else:
            return []

        # Parse lines into list, take first 4 non-empty ones
        questions = [q.strip() for q in raw.split("\n") if q.strip()][:4]
        return questions

    except Exception as exc:
        logger.warning("Follow-up generation failed: %s", exc)
        return []