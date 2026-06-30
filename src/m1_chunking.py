from __future__ import annotations

"""
Module 1: Advanced Chunking Strategies
=======================================
Implement semantic, hierarchical, và structure-aware chunking.
So sánh với basic chunking (baseline) để thấy improvement.

Test: pytest tests/test_m1.py
"""

import os, sys, glob, re
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (DATA_DIR, HIERARCHICAL_PARENT_SIZE, HIERARCHICAL_CHILD_SIZE,
                    SEMANTIC_THRESHOLD)


_SEMANTIC_MODEL = None


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    parent_id: str | None = None


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """Load toàn bộ tài liệu Markdown từ data/."""
    docs = []
    for fp in sorted(glob.glob(os.path.join(data_dir, "*.md"))):
        with open(fp, encoding="utf-8") as f:
            docs.append({"text": f.read(), "metadata": {"source": os.path.basename(fp)}})
    return docs


# ─── Baseline: Basic Chunking (để so sánh) ──────────────


def chunk_basic(text: str, chunk_size: int = 500, metadata: dict | None = None) -> list[Chunk]:
    """
    Basic chunking: split theo paragraph (\\n\\n).
    Đây là baseline — KHÔNG phải mục tiêu của module này.
    (Đã implement sẵn)
    """
    metadata = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for i, para in enumerate(paragraphs):
        if len(current) + len(para) > chunk_size and current:
            chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
    return chunks


# ─── Strategy 1: Semantic Chunking ───────────────────────


def chunk_semantic(text: str, threshold: float = SEMANTIC_THRESHOLD,
                   metadata: dict | None = None) -> list[Chunk]:
    """
    Split text by sentence similarity — nhóm câu cùng chủ đề.
    Tốt hơn basic vì không cắt giữa ý.
    """
    global _SEMANTIC_MODEL

    metadata = metadata or {}
    text = text.strip()
    if not text:
        return []

    # Header Markdown được gắn vào câu ngay sau nó để embedding có thêm ngữ cảnh,
    # thay vì coi một dòng header ngắn là một câu độc lập.
    units = []
    pending_headers = []
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]

    for block in blocks:
        if re.fullmatch(r"#{1,6}\s+.+", block):
            pending_headers.append(block)
            continue

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", block)
            if sentence.strip()
        ]
        if not sentences:
            continue

        if pending_headers:
            sentences[0] = "\n".join([*pending_headers, sentences[0]])
            pending_headers.clear()
        units.extend(sentences)

    # Tài liệu chỉ có header vẫn phải sinh được chunk hợp lệ.
    if pending_headers:
        units.append("\n".join(pending_headers))
    if not units:
        return []

    from sentence_transformers import SentenceTransformer
    import numpy as np

    if _SEMANTIC_MODEL is None:
        _SEMANTIC_MODEL = SentenceTransformer(
            "all-MiniLM-L6-v2",
            local_files_only=True,
        )

    embeddings = _SEMANTIC_MODEL.encode(units, convert_to_numpy=True)

    groups = [[units[0]]]
    for index in range(1, len(units)):
        previous = embeddings[index - 1]
        current = embeddings[index]
        denominator = np.linalg.norm(previous) * np.linalg.norm(current)
        similarity = float(np.dot(previous, current) / (denominator + 1e-9))

        if similarity < threshold:
            groups.append([units[index]])
        else:
            groups[-1].append(units[index])

    return [
        Chunk(
            text=" ".join(group).strip(),
            metadata={
                **metadata,
                "strategy": "semantic",
                "chunk_index": index,
            },
        )
        for index, group in enumerate(groups)
    ]


# ─── Strategy 2: Hierarchical Chunking ──────────────────


def chunk_hierarchical(text: str, parent_size: int = HIERARCHICAL_PARENT_SIZE,
                       child_size: int = HIERARCHICAL_CHILD_SIZE,
                       metadata: dict | None = None) -> tuple[list[Chunk], list[Chunk]]:
    """
    Parent-child hierarchy: retrieve child (precision) → return parent (context).
    Đây là default recommendation cho production RAG.

    Returns:
        (parents, children) — mỗi child có parent_id link đến parent.
    """
    metadata = metadata or {}
    text = text.strip()
    if not text:
        return ([], [])
    if parent_size <= 0 or child_size <= 0:
        raise ValueError("parent_size and child_size must be greater than 0")

    def split_to_size(value: str, max_size: int) -> list[str]:
        """Chia text theo từ; từ dài bất thường sẽ được cắt theo ký tự."""
        parts = []
        current = ""

        for word in value.split():
            if len(word) > max_size:
                if current:
                    parts.append(current)
                    current = ""
                parts.extend(
                    word[start:start + max_size]
                    for start in range(0, len(word), max_size)
                )
                continue

            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_size:
                parts.append(current)
                current = word
            else:
                current = candidate

        if current:
            parts.append(current)
        return parts

    # Paragraph dài hơn parent_size được chia nhỏ trước khi gom parent.
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if paragraph:
            paragraphs.extend(split_to_size(paragraph, parent_size))

    parent_texts = []
    current_parent = ""
    for paragraph in paragraphs:
        candidate = f"{current_parent}\n\n{paragraph}".strip()
        if current_parent and len(candidate) > parent_size:
            parent_texts.append(current_parent)
            current_parent = paragraph
        else:
            current_parent = candidate
    if current_parent:
        parent_texts.append(current_parent)

    source = str(metadata.get("source", "document"))
    source_id = re.sub(r"[^A-Za-z0-9_-]+", "_", source).strip("_") or "document"
    parents = []
    children = []

    for parent_index, parent_text in enumerate(parent_texts):
        parent_id = f"{source_id}_parent_{parent_index}"
        parents.append(Chunk(
            text=parent_text,
            metadata={
                **metadata,
                "strategy": "hierarchical",
                "chunk_type": "parent",
                "parent_id": parent_id,
                "chunk_index": parent_index,
            },
        ))

        child_texts = split_to_size(parent_text, child_size)
        for child_index, child_text in enumerate(child_texts):
            children.append(Chunk(
                text=child_text,
                metadata={
                    **metadata,
                    "strategy": "hierarchical",
                    "chunk_type": "child",
                    "chunk_index": child_index,
                },
                parent_id=parent_id,
            ))

    return (parents, children)


# ─── Strategy 3: Structure-Aware Chunking ────────────────


def chunk_structure_aware(text: str, metadata: dict | None = None) -> list[Chunk]:
    """
    Parse markdown headers → chunk theo logical structure.
    Giữ nguyên tables, code blocks, lists — không cắt giữa chừng.
    """
    metadata = metadata or {}
    text = text.strip()
    if not text:
        return []

    header_pattern = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
    chunks = []
    current_header = ""
    current_section = "Preamble"
    current_level = 0
    current_lines = []
    in_code_block = False

    def flush_section() -> None:
        nonlocal current_lines
        content = "\n".join(current_lines).strip()
        if not content and not current_header:
            current_lines = []
            return

        chunk_text = "\n\n".join(
            part for part in [current_header, content] if part
        ).strip()
        chunks.append(Chunk(
            text=chunk_text,
            metadata={
                **metadata,
                "strategy": "structure",
                "section": current_section,
                "header_level": current_level,
                "chunk_index": len(chunks),
            },
        ))
        current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        header_match = None if in_code_block else header_pattern.match(line)
        if header_match:
            flush_section()
            current_header = line.strip()
            current_level = len(header_match.group(1))
            current_section = header_match.group(2).strip()
        else:
            current_lines.append(line)

    flush_section()
    return chunks


# ─── A/B Test: Compare All Strategies ────────────────────


def compare_strategies(documents: list[dict]) -> dict:
    """
    Run all strategies on documents and compare.
    (Đã implement sẵn — sẽ hoạt động khi bạn implement 3 strategies ở trên)
    """
    def _stats(chunk_list):
        lengths = [len(c.text) for c in chunk_list]
        if not lengths:
            return {"count": 0, "avg_len": 0, "min_len": 0, "max_len": 0}
        return {
            "count": len(lengths),
            "avg_len": round(sum(lengths) / len(lengths)),
            "min_len": min(lengths),
            "max_len": max(lengths),
        }

    all_text = "\n\n".join(d["text"] for d in documents)
    meta = {"source": "all"}

    basic = chunk_basic(all_text, metadata=meta)
    semantic = chunk_semantic(all_text, metadata=meta)
    parents, children = chunk_hierarchical(all_text, metadata=meta)
    structure = chunk_structure_aware(all_text, metadata=meta)

    results = {
        "basic": _stats(basic),
        "semantic": _stats(semantic),
        "hierarchical": {**_stats(children), "parents": len(parents)},
        "structure": _stats(structure),
    }

    print(f"{'Strategy':<15} {'Chunks':>7} {'Avg':>5} {'Min':>5} {'Max':>5}")
    for name, s in results.items():
        print(f"{name:<15} {s['count']:>7} {s['avg_len']:>5} {s['min_len']:>5} {s['max_len']:>5}")

    return results


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")
    results = compare_strategies(docs)
    for name, stats in results.items():
        print(f"  {name}: {stats}")
