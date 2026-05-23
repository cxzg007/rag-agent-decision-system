from pathlib import Path


class DocumentParser:
    async def parse(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            return await self._parse_pdf(path)
        return path.read_text(encoding="utf-8", errors="ignore")

    async def _parse_pdf(self, path: Path) -> str:
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("Install pdfplumber to parse PDF files.") from exc

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page_no, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                pages.append(f"[page={page_no}]\n{text}")
        return "\n\n".join(pages)


document_parser = DocumentParser()
