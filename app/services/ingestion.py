from pathlib import Path

from app.schemas.document import DocumentIngestResponse
from app.services.chunker import chunker
from app.services.parser import document_parser
from app.services.retriever import retriever


class IngestionService:
    async def ingest_file(self, doc_id: str, filename: str, path: Path) -> DocumentIngestResponse:
        text = await document_parser.parse(path)
        chunks = chunker.split(doc_id=doc_id, text=text)
        indexed = await retriever.index_chunks(chunks)
        return DocumentIngestResponse(
            doc_id=doc_id,
            filename=filename,
            chunk_count=len(chunks),
            indexed_count=indexed,
        )


ingestion_service = IngestionService()
