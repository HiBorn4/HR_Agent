"""
app/services/text_processing.py
--------------------------------
Pure text-transformation helpers used by the /chat endpoint.
No FastAPI, no I/O — these are synchronous functions plus one async helper.
"""

import asyncio
import json
import re

import google.generativeai as genai

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Markdown table → JSON
# ---------------------------------------------------------------------------

def parse_markdown_tables(text: str) -> tuple[str, list[dict]]:
    """
    Extract Markdown pipe-tables from *text*, convert each row to a dict,
    and return (text_with_tables_removed, list_of_row_dicts).
    """
    tables: list[dict] = []
    table_pattern = re.compile(r"((\s*\|.*\|\s*\n)+)", re.MULTILINE)

    for match in table_pattern.findall(text):
        full_table_str: str = match[0]
        lines = [line.strip() for line in full_table_str.strip().split("\n")]

        if len(lines) < 3:
            continue

        headers = [h.strip() for h in lines[0].strip("|").split("|")]

        # Second line must be a separator row (---|---|---)
        if not re.match(r"^[\s:|,-]+$", lines[1].strip("|")):
            continue

        for row_line in lines[2:]:
            values = [v.strip() for v in row_line.strip("|").split("|")]
            row: dict = {}
            for i, header in enumerate(headers):
                raw_val = values[i] if i < len(values) else ""
                row[header] = _coerce_numeric(raw_val)
            tables.append(row)

        text = text.replace(full_table_str, "")

    return text.strip(), tables


def _coerce_numeric(value: str) -> int | float | str:
    """Try to coerce a string to int or float; fall back to the original string."""
    if value.replace(".", "", 1).isdigit():
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            pass
    return value


# ---------------------------------------------------------------------------
# LLM response filtering — strip internal reasoning artefacts
# ---------------------------------------------------------------------------

def filter_llm_response(raw_text: str) -> tuple[str, str]:
    """
    Strip internal reasoning blocks from an LLM response.

    Returns:
        (clean_text, debug_log)
        where *debug_log* contains the stripped content (for Glass Box UI).
    """
    if not raw_text:
        return "", ""

    # Collect "thought" blocks for the debug pane
    thought_patterns = [
        r"<(thought|thinking|plan|analysis)>(.*?)</\1>",
        r"(```sql.*?```)",
        r"(```python.*?```)",
    ]
    thoughts: list[str] = []
    for pattern in thought_patterns:
        for m in re.findall(pattern, raw_text, flags=re.IGNORECASE | re.DOTALL):
            thoughts.append((m[1] if isinstance(m, tuple) else m).strip())
    debug_log = "\n\n".join(thoughts)

    text = raw_text
    text = re.sub(r"<(thought|thinking|plan|analysis)[\s\S]*?</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r'"thought_signature"\s*:\s*"[^"]*"', "", text, flags=re.IGNORECASE)
    text = re.sub(r"(#\s*Thought[\s\S]*?)(?=\n\w|\Z)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(#\s*Plan[\s\S]*?)(?=\n\w|\Z)", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(Reasoning|Analysis|Thought Process|Deliberate)[\s\S]*?:",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # If the response is a JSON function-call object, return it directly
    if fc_match := re.search(r"(\{[\s\S]*?\"function_call\"[\s\S]*?\})", text, flags=re.IGNORECASE):
        try:
            return json.dumps(json.loads(fc_match[1])), debug_log
        except Exception:
            return fc_match[1].strip(), debug_log

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Safety net: if filtering removed everything, surface the raw content
    if not text.strip() and raw_text.strip():
        return raw_text, debug_log

    return text, debug_log


# ---------------------------------------------------------------------------
# Smart follow-up suggestion generation
# ---------------------------------------------------------------------------

_SUGGESTIONS_MODEL = "gemini-2.5-flash"
_SUGGESTIONS_PROMPT = """
User asked: "{question}"
System answered: "{answer}"

Based on this interaction, suggest 3 short analytical follow-up questions.
Return ONLY a JSON array of strings.
Example: ["Break down by region", "Compare to last year", "Show trend"]
"""


async def generate_smart_suggestions(question: str, answer: str) -> list[str]:
    """
    Asynchronously generate 3 follow-up question suggestions via Gemini.
    Returns an empty list on any failure — never raises.
    """
    if len(answer) < 20:
        return []

    try:
        model = genai.GenerativeModel(_SUGGESTIONS_MODEL)
        prompt = _SUGGESTIONS_PROMPT.format(question=question, answer=answer)
        response = await asyncio.to_thread(model.generate_content, prompt)

        if json_match := re.search(r"\[.*\]", response.text, re.DOTALL):
            return json.loads(json_match.group(0))

    except Exception:
        logger.warning("Failed to generate smart suggestions", exc_info=True)

    return []
