import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.metrics import EvalDependencyError, run_eval
from app.schemas.eval import EvalResponse, EvalRunResult
from app.services.retriever import retriever


def metric_value(run: EvalRunResult, name: str) -> float:
    for metric in run.metrics:
        if metric.name == name:
            return metric.value
    return 0.0


def named_metric(metrics, name: str) -> float:
    for metric in metrics:
        if metric.name == name:
            return metric.value
    return 0.0


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def delta_pct(value: float, baseline: float) -> str:
    points = (value - baseline) * 100
    if baseline == 0:
        relative = "n/a"
    else:
        relative = f"{((value - baseline) / baseline) * 100:+.2f}%"
    return f"{points:+.2f} pp / {relative}"


def render_report(response: EvalResponse, elapsed_ms: float) -> str:
    lines = [
        "# RAG Evaluation Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Dataset size: {response.dataset_size}",
        f"Elapsed: {elapsed_ms:.2f} ms",
        "",
        "## Ablation Summary",
        "",
        "| Config | Retrieval | Rerank | Metadata Adj. | Recall@5 | MRR@10 | Citation Acc. | Tool Success |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for run in response.runs:
        config = run.config
        lines.append(
            "| "
            + " | ".join(
                [
                    config.name,
                    config.retrieval_mode,
                    str(config.use_rerank),
                    str(config.use_metadata_adjustment),
                    pct(metric_value(run, "Recall@5")),
                    pct(metric_value(run, "MRR@10")),
                    pct(metric_value(run, "CitationAccuracy")),
                    pct(metric_value(run, "ToolSuccessRate")),
                ]
            )
            + " |"
        )

    if response.runs:
        baseline = response.runs[0]
        lines.extend(
            [
                "",
                f"## Improvement vs Baseline: {baseline.config.name}",
                "",
                "| Config | Recall@5 Delta | MRR@10 Delta | Citation Acc. Delta | Tool Success Delta |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        baseline_metrics = {
            "Recall@5": metric_value(baseline, "Recall@5"),
            "MRR@10": metric_value(baseline, "MRR@10"),
            "CitationAccuracy": metric_value(baseline, "CitationAccuracy"),
            "ToolSuccessRate": metric_value(baseline, "ToolSuccessRate"),
        }
        for run in response.runs[1:]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        run.config.name,
                        delta_pct(metric_value(run, "Recall@5"), baseline_metrics["Recall@5"]),
                        delta_pct(metric_value(run, "MRR@10"), baseline_metrics["MRR@10"]),
                        delta_pct(metric_value(run, "CitationAccuracy"), baseline_metrics["CitationAccuracy"]),
                        delta_pct(metric_value(run, "ToolSuccessRate"), baseline_metrics["ToolSuccessRate"]),
                    ]
                )
                + " |"
            )

    for run in response.runs:
        lines.extend(
            [
                "",
                f"## Case Details: {run.config.name}",
                "",
                "| Hit@5 | RR | Question | Gold Chunks | Retrieved Top 5 |",
                "|---:|---:|---|---|---|",
            ]
        )
        for case in run.cases:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(case.hit_at_5),
                        f"{case.reciprocal_rank:.3f}",
                        case.question.replace("|", "\\|"),
                        ", ".join(case.gold_chunk_ids),
                        ", ".join(case.retrieved_chunk_ids[:5]),
                    ]
                )
                + " |"
            )

        misses = [case for case in run.cases if not case.hit_at_5]
        if misses:
            lines.extend(["", "### Missed Cases", ""])
            for case in misses:
                lines.append(f"- {case.question}")

    for agent_run in response.agent_runs:
        lines.extend(
            [
                "",
                f"## Agent Evaluation: {agent_run.name}",
                "",
                "| Metric | Value |",
                "|---|---:|",
                f"| AgentRunSuccessRate | {pct(named_metric(agent_run.metrics, 'AgentRunSuccessRate'))} |",
                f"| AgentCitationHit@5 | {pct(named_metric(agent_run.metrics, 'AgentCitationHit@5'))} |",
                f"| AnswerKeywordCoverage | {pct(named_metric(agent_run.metrics, 'AnswerKeywordCoverage'))} |",
                f"| AgentNodeSuccessRate | {pct(named_metric(agent_run.metrics, 'AgentNodeSuccessRate'))} |",
                f"| AgentToolSuccessRate | {pct(named_metric(agent_run.metrics, 'AgentToolSuccessRate'))} |",
                f"| AgentAvgLatencyMs | {named_metric(agent_run.metrics, 'AgentAvgLatencyMs'):.2f} ms |",
                "",
                "### Agent Case Details",
                "",
                "| Citation Hit | Keyword Coverage | Node Success | Tool Success | Latency | Question | Citations | Matched Keywords |",
                "|---:|---:|---:|---:|---:|---|---|---|",
            ]
        )
        for case in agent_run.cases:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(case.citation_hit),
                        pct(case.answer_keyword_coverage),
                        pct(case.node_success_rate),
                        pct(case.tool_success_rate),
                        f"{case.latency_ms:.2f} ms",
                        case.question.replace("|", "\\|"),
                        ", ".join(case.citation_chunk_ids[:5]),
                        ", ".join(case.matched_keywords),
                    ]
                )
                + " |"
            )
        failures = [case for case in agent_run.cases if case.error_message]
        if failures:
            lines.extend(["", "### Agent Failed Cases", ""])
            for case in failures:
                lines.append(f"- {case.question}: {case.error_message}")

    return "\n".join(lines) + "\n"


def render_failure_report(error: Exception, elapsed_ms: float) -> str:
    error_text = str(error)
    if "localhost:9200" in error_text:
        error_text = "Elasticsearch is unavailable at localhost:9200."
    elif "localhost:6379" in error_text:
        error_text = "Redis is unavailable at localhost:6379."
    elif "15432" in error_text:
        error_text = "PostgreSQL is unavailable at 127.0.0.1:15432."
    return "\n".join(
        [
            "# RAG Evaluation Report",
            "",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
            f"Elapsed: {elapsed_ms:.2f} ms",
            "",
            "## Status",
            "",
            "Evaluation did not run because a required dependency was unavailable.",
            "",
            "## Error",
            "",
            "```text",
            error_text,
            "```",
            "",
            "## Suggested Fix",
            "",
            "Start the local infrastructure and rerun the report:",
            "",
            "```powershell",
            "docker compose up -d",
            "python scripts/upgrade_db.py",
            "python scripts/run_eval_report.py",
            "```",
            "",
        ]
    )


async def run_report(output_path: Path, dataset_path: Path, include_agent_eval: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        response = await run_eval(dataset_path=dataset_path, include_agent_eval=include_agent_eval)
        elapsed_ms = (time.perf_counter() - started) * 1000
        report = render_report(response, elapsed_ms)
    except EvalDependencyError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        report = render_failure_report(exc, elapsed_ms)
    finally:
        await retriever.close()

    output_path.write_text(report, encoding="utf-8")
    print(f"wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run eval ablations and write a Markdown report.")
    parser.add_argument("--output", type=Path, default=Path("reports/eval_report.md"))
    parser.add_argument("--dataset", type=Path, default=Path("app/eval/dataset.jsonl"))
    parser.add_argument("--no-agent-eval", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_report(args.output, args.dataset, include_agent_eval=not args.no_agent_eval))


if __name__ == "__main__":
    main()
