import re

from app.schemas.document import DocumentChunk


SECTION_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*\.)\s+(?P<title>[A-Z0-9][^\n]{2,160})$")
RFC_TITLE_RE = re.compile(r"^(?P<title>.+(?:Protocol|Semantics|HTTP|TLS|QUIC).*)$")


class StructureAwareChunker:
    def split(
        self,
        doc_id: str,
        text: str,
        chunk_size: int = 900,
        overlap: int = 120,
        parent_size: int = 3600,
    ) -> list[DocumentChunk]:
        clean = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        doc_title = self._extract_title(clean)
        sections = self._split_sections(clean)
        if not sections:
            sections = self._split_by_size(clean, parent_size)

        chunks: list[DocumentChunk] = []
        child_global_index = 0

        for parent_index, section in enumerate(sections):
            parent_id = f"{doc_id}_p{parent_index:04d}"
            parent_text = section["text"]
            parent_metadata = {
                "start": section["start"],
                "end": section["end"],
                "char_count": len(parent_text),
                "chunk_role": "context",
            }
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    chunk_id=parent_id,
                    chunk_level="parent",
                    text=parent_text,
                    title=doc_title,
                    section=section.get("section"),
                    metadata=parent_metadata,
                )
            )

            child_start = 0
            child_index = 0
            while child_start < len(parent_text):
                child_end = min(child_start + chunk_size, len(parent_text))
                child_text = parent_text[child_start:child_end]
                absolute_start = section["start"] + child_start
                absolute_end = section["start"] + child_end
                chunks.append(
                    DocumentChunk(
                        doc_id=doc_id,
                        chunk_id=f"{doc_id}_c{child_global_index:04d}",
                        chunk_level="child",
                        parent_id=parent_id,
                        child_index=child_index,
                        text=child_text,
                        title=doc_title,
                        section=section.get("section"),
                        metadata={
                            "start": absolute_start,
                            "end": absolute_end,
                            "parent_start": section["start"],
                            "parent_end": section["end"],
                            "char_count": len(child_text),
                            "chunk_role": "retrieval",
                        },
                    )
                )
                if child_end == len(parent_text):
                    break
                child_start = max(child_end - overlap, child_start + 1)
                child_index += 1
                child_global_index += 1
            child_global_index += 1

        return chunks

    def _extract_title(self, text: str) -> str | None:
        for line in text.splitlines()[:80]:
            stripped = line.strip()
            if not stripped or stripped.startswith(("RFC ", "Request for Comments", "Internet Engineering")):
                continue
            if RFC_TITLE_RE.match(stripped) and len(stripped) < 180:
                return stripped
        return None

    def _split_sections(self, text: str) -> list[dict]:
        matches = []
        cursor = 0
        for line in text.splitlines():
            start = text.find(line, cursor)
            cursor = start + len(line)
            stripped = line.strip()
            if stripped.endswith(".") or "..." in stripped:
                continue
            match = SECTION_RE.match(stripped)
            if match:
                section_title = f"{match.group('number')} {match.group('title').strip()}"
                matches.append({"start": start, "section": section_title})

        if not matches:
            return []

        sections = []
        if matches[0]["start"] > 0:
            sections.append(
                {
                    "section": "front_matter",
                    "start": 0,
                    "end": matches[0]["start"],
                    "text": text[: matches[0]["start"]].strip(),
                }
            )
        for index, item in enumerate(matches):
            end = matches[index + 1]["start"] if index + 1 < len(matches) else len(text)
            section_text = text[item["start"] : end].strip()
            if section_text:
                sections.append(
                    {
                        "section": item["section"],
                        "start": item["start"],
                        "end": end,
                        "text": section_text,
                    }
                )
        return [section for section in sections if section["text"]]

    def _split_by_size(self, text: str, parent_size: int) -> list[dict]:
        sections = []
        start = 0
        index = 0
        while start < len(text):
            end = min(start + parent_size, len(text))
            sections.append(
                {
                    "section": f"part_{index:04d}",
                    "start": start,
                    "end": end,
                    "text": text[start:end],
                }
            )
            if end == len(text):
                break
            start = end
            index += 1
        return sections


chunker = StructureAwareChunker()
