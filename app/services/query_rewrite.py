class QueryRewriteService:
    async def rewrite(self, question: str) -> str:
        return question.strip()


query_rewrite_service = QueryRewriteService()
