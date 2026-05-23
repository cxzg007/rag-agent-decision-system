import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


STOPWORDS = {
    "about",
    "after",
    "also",
    "applications",
    "because",
    "before",
    "between",
    "being",
    "can",
    "client",
    "clients",
    "connection",
    "connections",
    "data",
    "defined",
    "document",
    "during",
    "endpoint",
    "endpoints",
    "field",
    "fields",
    "from",
    "frame",
    "frames",
    "header",
    "message",
    "messages",
    "method",
    "must",
    "packet",
    "packets",
    "request",
    "response",
    "section",
    "server",
    "servers",
    "shall",
    "should",
    "state",
    "that",
    "the",
    "this",
    "transport",
    "using",
    "value",
    "values",
    "with",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a larger deterministic RFC eval dataset.")
    parser.add_argument("--input", type=Path, default=Path("data/parsed/rfc_parent_child_chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("app/eval/dataset_large.jsonl"))
    parser.add_argument("--max-cases", type=int, default=60)
    parser.add_argument("--min-chars", type=int, default=450)
    args = parser.parse_args()

    rows = load_child_chunks(args.input, min_chars=args.min_chars)
    selected = balanced_sample(rows, max_cases=args.max_cases)
    eval_rows = [build_eval_row(row) for row in selected]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in eval_rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(eval_rows)} cases to {args.output}")


def load_child_chunks(path: Path, min_chars: int) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("chunk_level") != "child":
            continue
        text = " ".join(str(row.get("text", "")).split())
        section = str(row.get("section") or "")
        if len(text) < min_chars or not useful_section(section):
            continue
        keywords = extract_keywords(section, text)
        if len(keywords) < 3:
            continue
        row["text"] = text
        row["answer_keywords"] = keywords[:3]
        rows.append(row)
    return rows


def useful_section(section: str) -> bool:
    if not section or section == "front_matter":
        return False
    lower = section.lower()
    return not any(term in lower for term in ["references", "author", "contributors", "iana"])


def balanced_sample(rows: list[dict], max_cases: int) -> list[dict]:
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_doc[row["doc_id"]].append(row)

    for doc_rows in by_doc.values():
        doc_rows.sort(key=lambda item: (item.get("section") or "", item["chunk_id"]))

    selected: list[dict] = []
    docs = sorted(by_doc)
    cursor = 0
    while len(selected) < max_cases and any(by_doc.values()):
        doc_id = docs[cursor % len(docs)]
        cursor += 1
        if by_doc[doc_id]:
            selected.append(by_doc[doc_id].pop(0))
    return selected


def build_eval_row(row: dict) -> dict:
    section = str(row.get("section") or "the selected section")
    doc_label = doc_display_name(row["doc_id"])
    topic = clean_section(section)
    keyword_hint = " and ".join(row["answer_keywords"][:2])
    question = f"What does {doc_label} say about {topic} and {keyword_hint}?"
    gold_ids = [row["chunk_id"]]
    parent_id = row.get("parent_id")
    if parent_id:
        gold_ids.extend(sibling_gold_ids(row["chunk_id"], parent_id))
    return {
        "question": question,
        "gold_chunk_ids": gold_ids,
        "answer_keywords": row["answer_keywords"],
        "task_type": "document_qa",
        "source_doc_id": row["doc_id"],
        "source_section": section,
    }


def sibling_gold_ids(chunk_id: str, parent_id: str) -> list[str]:
    match = re.match(r"(.+)_c(\d+)$", chunk_id)
    if not match:
        return []
    prefix, number = match.groups()
    index = int(number)
    siblings = []
    for sibling_index in (index - 1, index + 1):
        if sibling_index >= 0:
            siblings.append(f"{prefix}_c{sibling_index:04d}")
    return siblings


def doc_display_name(doc_id: str) -> str:
    if "8446" in doc_id:
        return "TLS 1.3"
    if "9000" in doc_id:
        return "QUIC"
    if "9110" in doc_id:
        return "HTTP semantics"
    return doc_id


def clean_section(section: str) -> str:
    cleaned = re.sub(r"^\d+(\.\d+)*\.\s*", "", section).strip()
    return cleaned or section


def extract_keywords(section: str, text: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip("_-")
        lower = normalized.lower()
        if lower in STOPWORDS or len(lower) < 3 or lower in seen:
            continue
        if len(lower) <= 4 and not normalized.isupper():
            continue
        if normalized.isdigit():
            continue
        seen.add(lower)
        keywords.append(normalized)
    return keywords


if __name__ == "__main__":
    main()
