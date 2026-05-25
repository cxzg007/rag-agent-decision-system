from app.eval.metrics import (
    _constraint_pass_rate,
    _plan_completeness,
    _trace_coverage,
    _workflow_completion,
)
from app.schemas.chat import ToolCallRecord
from app.schemas.workflow import WorkflowNodeRun, WorkflowResponse


def test_agent_eval_metrics_for_complete_mission_plan():
    response = WorkflowResponse(
        workflow_run_id="run-1",
        workflow_id="supervisor_workflow_v1",
        trace_id="trace-1",
        session_id="s1",
        answer="review_only_json parallel_area_split",
        node_runs=[
            WorkflowNodeRun(
                node_id="supervisor_router",
                node_type="router",
                status="success",
                latency_ms=1.0,
            ),
            WorkflowNodeRun(
                node_id="mission_export",
                node_type="tool",
                status="success",
                latency_ms=2.0,
                output={
                    "mission_plan": {
                        "approval_required": True,
                        "export_format": "review_only_json",
                        "risk_level": "low",
                        "routes": [{"drone_id": "UAV-01"}],
                        "mitigations": ["standard preflight check"],
                    }
                },
            ),
        ],
        tool_calls=[
            ToolCallRecord(
                name="drone_mission_export",
                arguments={},
                output_summary="exported review-only mission plan with 1 route(s)",
                success=True,
                latency_ms=3.0,
            )
        ],
    )
    expected_nodes = ["supervisor_router", "mission_export"]
    expected_tools = ["drone_mission_export"]
    constraints = [
        "approval_required",
        "review_only_export",
        "risk_level_present",
        "route_present",
        "mitigation_present",
        "no_dispatch_tool",
    ]

    assert _workflow_completion(response, expected_nodes) == 1.0
    assert _constraint_pass_rate(response, constraints) == 1.0
    assert _trace_coverage(response, expected_tools) == 1.0
    assert (
        _plan_completeness(
            successful_nodes={"supervisor_router", "mission_export"},
            successful_tools=["drone_mission_export"],
            expected_nodes=expected_nodes,
            expected_tools=expected_tools,
            output_completeness=1.0,
        )
        == 1.0
    )
