import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.document import DocumentChunk
from app.services.retriever import retriever


def load_chunks(path: Path, limit: int | None) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        chunks.append(DocumentChunk.model_validate(json.loads(line)))
        if limit is not None and len(chunks) >= limit:
            break
    return chunks


async def index_chunks(path: Path, batch_size: int, limit: int | None, recreate: bool) -> None:
    chunks = load_chunks(path, limit=limit)
    if recreate:
        exists = await retriever.client.indices.exists(index=retriever.index)
        if exists:
            await retriever.client.indices.delete(index=retriever.index)

    total = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        indexed = await retriever.index_chunks(batch)
        total += indexed
        print(f"indexed {total}/{len(chunks)} chunks")

    await retriever.close()
    print(f"done: indexed {total} chunks into index '{retriever.index}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index chunk JSONL into Elasticsearch.")
    parser.add_argument("--input", type=Path, default=Path("data/parsed/rfc_chunks.jsonl"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    asyncio.run(index_chunks(args.input, args.batch_size, args.limit, args.recreate))


if __name__ == "__main__":
    main()
