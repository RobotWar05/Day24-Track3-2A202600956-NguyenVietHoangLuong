from __future__ import annotations

"""
Module 5: Enrichment Pipeline
==============================
Làm giàu chunks TRƯỚC khi embed: Summarize, HyQA, Contextual Prepend, Auto Metadata.

Test: pytest tests/test_m5.py
"""

import os, sys, json, re
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


def _chat_completion(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    """Call the configured OpenAI-compatible provider and return plain text."""
    if not OPENAI_API_KEY:
        return ""

    from openai import OpenAI

    client_kwargs = {"api_key": OPENAI_API_KEY, "timeout": 60.0}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL

    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def _parse_json_object(raw_text: str) -> dict:
    """Parse a JSON object even when the model wraps it in a Markdown fence."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model response does not contain a JSON object")
    parsed = json.loads(raw_text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object")
    return parsed


def _fallback_summary(text: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        if sentence.strip()
    ]
    return " ".join(sentences[:2]) if sentences else text.strip()


def _fallback_questions(text: str, n_questions: int) -> list[str]:
    sentences = [
        sentence.strip().rstrip(".!?")
        for sentence in re.split(r"[.!?\n]+", text)
        if len(sentence.strip()) > 10
    ]
    return [f"{sentence}?" for sentence in sentences[:max(n_questions, 0)]]


def _fallback_context(text: str, document_title: str) -> str:
    if not text:
        return ""
    prefix = f"Trích từ tài liệu {document_title}." if document_title else "Trích từ tài liệu nội bộ."
    return f"{prefix}\n\n{text}"


def _fallback_metadata() -> dict:
    return {
        "topic": "general",
        "entities": [],
        "category": "policy",
        "language": "vi",
    }


@dataclass
class EnrichedChunk:
    """Chunk đã được làm giàu."""
    original_text: str
    enriched_text: str
    summary: str
    hypothesis_questions: list[str]
    auto_metadata: dict
    method: str  # "contextual", "summary", "hyqa", "full"


# ─── Technique 1: Chunk Summarization ────────────────────


def summarize_chunk(text: str) -> str:
    """
    Tạo summary ngắn cho chunk.
    Embed summary thay vì (hoặc cùng với) raw chunk → giảm noise.
    """
    if not text.strip():
        return ""
    if OPENAI_API_KEY:
        try:
            summary = _chat_completion(
                "Tóm tắt đoạn văn trong tối đa 2 câu ngắn gọn bằng tiếng Việt. Không thêm thông tin.",
                text,
                max_tokens=150,
            )
            if summary and len(summary) <= len(text) * 2:
                return summary
        except Exception as exc:
            print(f"  ⚠️  Summarization failed, using fallback: {type(exc).__name__}: {exc}")
    return _fallback_summary(text)


# ─── Technique 2: Hypothesis Question-Answer (HyQA) ─────


def generate_hypothesis_questions(text: str, n_questions: int = 3) -> list[str]:
    """
    Generate câu hỏi mà chunk có thể trả lời.
    Index cả questions lẫn chunk → query match tốt hơn (bridge vocabulary gap).
    """
    if not text.strip() or n_questions <= 0:
        return []
    if OPENAI_API_KEY:
        try:
            raw_questions = _chat_completion(
                f"Tạo đúng {n_questions} câu hỏi tiếng Việt mà đoạn văn có thể trả lời. Mỗi dòng một câu hỏi, không giải thích.",
                text,
                max_tokens=200,
            )
            questions = []
            for line in raw_questions.splitlines():
                question = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
                if question:
                    questions.append(question)
            if questions:
                return questions[:n_questions]
        except Exception as exc:
            print(f"  ⚠️  HyQA failed, using fallback: {type(exc).__name__}: {exc}")
    return _fallback_questions(text, n_questions)


# ─── Technique 3: Contextual Prepend (Anthropic style) ──


def contextual_prepend(text: str, document_title: str = "") -> str:
    """
    Prepend context giải thích chunk nằm ở đâu trong document.
    Anthropic benchmark: giảm 49% retrieval failure (alone).
    """
    if not text:
        return ""
    if OPENAI_API_KEY:
        try:
            context = _chat_completion(
                "Viết đúng 1 câu tiếng Việt mô tả đoạn văn thuộc tài liệu nào và nói về chủ đề gì. Không thêm dữ kiện.",
                f"Tài liệu: {document_title or 'Không rõ'}\n\nĐoạn văn:\n{text}",
                max_tokens=80,
            )
            if context:
                return f"{context}\n\n{text}"
        except Exception as exc:
            print(f"  ⚠️  Contextual prepend failed, using fallback: {type(exc).__name__}: {exc}")
    return _fallback_context(text, document_title)


# ─── Technique 4: Auto Metadata Extraction ──────────────


def extract_metadata(text: str) -> dict:
    """
    LLM extract metadata tự động: topic, entities, date_range, category.
    """
    if not text.strip():
        return _fallback_metadata()
    if OPENAI_API_KEY:
        try:
            raw_metadata = _chat_completion(
                'Chỉ trả về JSON hợp lệ: {"topic":"...","entities":["..."],"category":"policy|hr|it|finance","language":"vi|en"}.',
                text,
                max_tokens=150,
            )
            metadata = _parse_json_object(raw_metadata)
            if isinstance(metadata.get("entities", []), list):
                return metadata
        except Exception as exc:
            print(f"  ⚠️  Metadata extraction failed, using fallback: {type(exc).__name__}: {exc}")
    return _fallback_metadata()


# ─── Combined Single-Call Mode ───────────────────────────


def _enrich_single_call(text: str, source: str) -> dict:
    """Single LLM call to get summary + questions + context + metadata.

    ⚠️ Cost optimization: 1 API call thay vì 4 calls riêng lẻ.
    """
    fallback = {
        "summary": _fallback_summary(text),
        "questions": _fallback_questions(text, 3),
        "context": f"Trích từ tài liệu {source}." if source else "Trích từ tài liệu nội bộ.",
        "metadata": _fallback_metadata(),
    }
    if not text.strip() or not OPENAI_API_KEY:
        return fallback

    try:
        raw_result = _chat_completion(
            """Phân tích đoạn văn và chỉ trả về một JSON hợp lệ theo schema:
{"summary":"tóm tắt tối đa 2 câu","questions":["câu hỏi 1","câu hỏi 2","câu hỏi 3"],"context":"một câu mô tả vị trí và chủ đề","metadata":{"topic":"...","entities":["..."],"category":"policy|hr|it|finance","language":"vi|en"}}""",
            f"Tài liệu: {source or 'Không rõ'}\n\nĐoạn văn:\n{text}",
            max_tokens=400,
        )
        result = _parse_json_object(raw_result)
        if not isinstance(result.get("questions"), list):
            raise ValueError("questions must be a list")
        if not isinstance(result.get("metadata"), dict):
            raise ValueError("metadata must be an object")
        return {
            "summary": str(result.get("summary", fallback["summary"])),
            "questions": [str(item) for item in result["questions"][:3]],
            "context": str(result.get("context", fallback["context"])),
            "metadata": result["metadata"],
        }
    except Exception as exc:
        print(f"  ⚠️  Combined enrichment failed, using fallback: {type(exc).__name__}: {exc}")
        return fallback


# ─── Full Enrichment Pipeline ────────────────────────────


def enrich_chunks(
    chunks: list[dict],
    methods: list[str] | None = None,
) -> list[EnrichedChunk]:
    """
    Chạy enrichment pipeline trên danh sách chunks. (Đã implement sẵn — dùng functions ở trên)

    Có 2 chế độ:
    - methods cụ thể (["summary"], ["contextual"]...): gọi từng function riêng (tốt cho học/debug)
    - methods=["combined"] hoặc None: 1 API call duy nhất cho tất cả (tốt cho production)

    Args:
        chunks: List of {"text": str, "metadata": dict}
        methods: Default None → combined mode (1 call/chunk).
                 Options: "summary", "hyqa", "contextual", "metadata", "combined"
    """
    if methods is None:
        methods = ["combined"]

    valid_methods = {"summary", "hyqa", "contextual", "metadata", "combined"}
    unknown_methods = set(methods) - valid_methods
    if unknown_methods:
        raise ValueError(f"Unknown enrichment methods: {sorted(unknown_methods)}")

    use_combined = "combined" in methods

    enriched = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        source = chunk.get("metadata", {}).get("source", "")

        if use_combined:
            result = _enrich_single_call(text, source)
            summary = result.get("summary", "")
            questions = result.get("questions", [])
            context_line = result.get("context", "")
            enriched_text = f"{context_line}\n\n{text}" if context_line else text
            auto_meta = result.get("metadata", {})
        else:
            summary = summarize_chunk(text) if "summary" in methods else ""
            questions = generate_hypothesis_questions(text) if "hyqa" in methods else []
            enriched_text = contextual_prepend(text, source) if "contextual" in methods else text
            auto_meta = extract_metadata(text) if "metadata" in methods else {}

        enriched.append(EnrichedChunk(
            original_text=text,
            enriched_text=enriched_text,
            summary=summary,
            hypothesis_questions=questions,
            auto_metadata={**chunk.get("metadata", {}), **auto_meta},
            method="+".join(methods),
        ))

        if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
            print(f"  Enriched {i + 1}/{len(chunks)} chunks...", flush=True)

    return enriched


# ─── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    sample = "Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm. Số ngày nghỉ phép tăng thêm 1 ngày cho mỗi 5 năm thâm niên công tác."

    print("=== Enrichment Pipeline Demo ===\n")
    print(f"Original: {sample}\n")

    s = summarize_chunk(sample)
    print(f"Summary: {s}\n")

    qs = generate_hypothesis_questions(sample)
    print(f"HyQA questions: {qs}\n")

    ctx = contextual_prepend(sample, "Sổ tay nhân viên VinUni 2024")
    print(f"Contextual: {ctx}\n")

    meta = extract_metadata(sample)
    print(f"Auto metadata: {meta}")
