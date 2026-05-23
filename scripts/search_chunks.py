import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.retriever import retriever
from app.tools.knowledge_search import KnowledgeSearchInput, knowledge_search


async def search(query: str, top_k: int, no_rerank: bool) -> None:
    if no_rerank:
        results = (await retriever.search(query, top_k=top_k))[:top_k]
    else:
        results = (await knowledge_search(KnowledgeSearchInput(query=query, top_k=top_k))).chunks
    for rank, item in enumerate(results, 1):
        source = item.metadata.get("source_file", item.doc_id)
        parent_id = item.metadata.get("parent_id")
        section = item.metadata.get("section")
        retrieval_score = item.metadata.get("retrieval_score")
        preview = " ".join(item.text.split())[:260]
        print(f"{rank}. {item.chunk_id} score={item.score:.6f} source={source}")
        if retrieval_score is not None:
            print(f"   retrieval_score={retrieval_score:.6f} rerank_model={item.metadata.get('rerank_model')}")
        print(f"   parent={parent_id} section={section}")
        print(f"   {preview}")
    await retriever.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Search indexed chunks.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()
    asyncio.run(search(args.query, args.top_k, args.no_rerank))


if __name__ == "__main__":
    main()
