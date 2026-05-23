from typing import Any

from pydantic import BaseModel, Field

from app.schemas.workflow import WorkflowNodeRun
from app.services.agent.state import AgentState


class WorkflowState(BaseModel):
    workflow_run_id: str
    workflow_id: str
    agent_state: AgentState
    variables: dict[str, Any] = Field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    node_runs: list[WorkflowNodeRun] = Field(default_factory=list)
