import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.chunker import chunker
from app.services.parser import document_parser


RFC_FILE_RE = re.compile(r"^rfc(?P<number>\d+)-(?P<slug>.+)\.txt$")


def build_source_metadata(path: Path) -> dict:
    metadata = {
        "source_file": path.name,
        "source_path": str(path),
        "file_extension": path.suffix.lower(),
        "doc_type": "technical_standard" if path.name.lower().startswith("rfc") else "document",
    }
    match = RFC_FILE_RE.match(path.name.lower())
    if match:
        rfc_number = match.group("number")
        metadata.update(
            {
                "standard_body": "IETF",
                "standard_series": "RFC",
                "rfc_number": rfc_number,
                "source_url": f"https://www.rfc-editor.org/rfc/rfc{rfc_number}.txt",
                "topic_slug": match.group("slug").removesuffix(".txt"),
            }
        )
    return metadata


async def chunk_dataset(input_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    supported = {".txt", ".md", ".pdf"}
    files = sorted(path for path in input_dir.iterdir() if path.suffix.lower() in supported)

    total_chunks = 0
    with output_path.open("w", encoding="utf-8") as writer:
        for path in files:
            doc_id = path.stem
            text = await document_parser.parse(path)
            chunks = chunker.split(doc_id=doc_id, text=text)
            source_metadata = build_source_metadata(path)
            for chunk in chunks:
                payload = chunk.model_dump()
                payload["metadata"] = {
                    **payload.get("metadata", {}),
                    **source_metadata,
                }
                writer.write(json.dumps(payload, ensure_ascii=False) + "\n")
            parents = sum(1 for chunk in chunks if chunk.chunk_level == "parent")
            children = sum(1 for chunk in chunks if chunk.chunk_level == "child")
            print(f"{path.name}: {parents} parent chunks, {children} child chunks")
            total_chunks += len(chunks)

    print(f"wrote {total_chunks} chunks to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk local documents into JSONL.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/parsed/chunks.jsonl"))
    args = parser.parse_args()
    asyncio.run(chunk_dataset(args.input_dir, args.output))


if __name__ == "__main__":
    main()
