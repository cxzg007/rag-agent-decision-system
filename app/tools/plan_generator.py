from pydantic import BaseModel


class PlanGeneratorInput(BaseModel):
    question: str
    evidence: list[str]


class PlanGeneratorOutput(BaseModel):
    plan: list[str]


async def plan_generator(payload: PlanGeneratorInput) -> PlanGeneratorOutput:
    return PlanGeneratorOutput(
        plan=[
            "Clarify the task objective.",
            "Search the knowledge base for relevant evidence.",
            "Generate a grounded answer with citations.",
            "Reflect on missing evidence and risks.",
        ]
    )
