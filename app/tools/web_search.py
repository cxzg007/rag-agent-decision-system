from pydantic import BaseModel


class WebSearchInput(BaseModel):
    query: str


class WebSearchOutput(BaseModel):
    results: list[dict]


async def web_search(payload: WebSearchInput) -> WebSearchOutput:
    return WebSearchOutput(
        results=[
            {
                "title": "Web search is not wired yet",
                "url": "",
                "snippet": f"Add a real search provider for query: {payload.query}",
            }
        ]
    )
