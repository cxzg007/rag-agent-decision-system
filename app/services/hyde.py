class HydeService:
    async def generate(self, question: str) -> str:
        return f"Possible answer context for: {question}"


hyde_service = HydeService()
