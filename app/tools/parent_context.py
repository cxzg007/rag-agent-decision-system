from pydantic import BaseModel, Field

from app.services.retriever import retriever


class ParentContextInput(BaseModel):
    parent_ids: list[str] = Field(default_factory=list)


class ParentContextOutput(BaseModel):
    contexts: dict[str, str]


async def parent_context(payload: ParentContextInput) -> ParentContextOutput:
    contexts: dict[str, str] = {}
    for parent_id in payload.parent_ids:
        source = await retriever.get_parent(parent_id)
        if source:
            contexts[parent_id] = source.get("text", "")
    return ParentContextOutput(contexts=contexts)
