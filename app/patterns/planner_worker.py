"""Pattern 1 — Planner-Worker Hierarchy for LAPTOP-1204 RCA."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.models.factory import build_frontier_client, build_slm_client
from app.models.model_interface import LanguageModel, ModelRole
from app.models.schemas import PatternResult
from app.observability.cost_calculator import CostCalculator
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.common import (
    build_architect_decision,
    segment_from_generation,
    summarize_token_bars,
)
from app.services.baseline_estimator import BaselineEstimator
from app.services.telemetry import TelemetryService

PATTERN_NAME = "Planner-Worker Hierarchy"
PATTERN_ID = "planner_worker"
SCENARIO = "Complete multi-domain RCA for LAPTOP-1204."
DEVICE_ID = "LAPTOP-1204"


class PlannerWorkerPattern:
    def __init__(
        self,
        settings: Settings | None = None,
        slm: LanguageModel | None = None,
        frontier: LanguageModel | None = None,
        telemetry: TelemetryService | None = None,
        tracer: LangSmithTracer | None = None,
    ):
        self.settings = settings or get_settings()
        self.slm = slm or build_slm_client(self.settings)
        self.frontier = frontier or build_frontier_client(self.settings)
        self.telemetry = telemetry or TelemetryService()
        self.tracer = tracer or LangSmithTracer(self.settings)
        self.costs = CostCalculator(self.settings)
        self.baseline = BaselineEstimator(self.settings)

    def run(self) -> PatternResult:
        device_block = self.telemetry.device_prompt_block(DEVICE_ID)
        incidents = self.telemetry.incidents_for(DEVICE_ID)
        with self.tracer.trace(
            pattern=PATTERN_NAME,
            scenario=SCENARIO,
            device_id=DEVICE_ID,
            metadata={"pattern_id": PATTERN_ID},
        ) as ctx:
            segments = []

            plan = self.frontier.structured_generate(
                prompt=(
                    "Create an investigation plan for complete multi-domain RCA.\n"
                    f"DEVICE TELEMETRY:\n{device_block}"
                ),
                schema={
                    "objective": "string",
                    "workers": ["cpu", "teams", "network", "compliance", "history"],
                    "synthesis_required": True,
                },
                system="You are a Frontier planner for digital workplace RCA.",
                metadata={"task": "planning", "device_id": DEVICE_ID},
            )
            segments.append(
                segment_from_generation(
                    segment="Planning",
                    task="planning",
                    role=ModelRole.PLANNER,
                    why="Complex task decomposition and planning.",
                    result=plan,
                    costs=self.costs,
                    baseline=self.baseline,
                    decision="FRONTIER",
                    decision_why="Planning requires advanced decomposition.",
                )
            )
            self.tracer.record(
                ctx,
                segment="FRONTIER — Planner",
                model_name=plan.model_name,
                model_type=plan.model_type,
                model_role=ModelRole.PLANNER,
                provider=plan.provider,
                input_tokens=plan.usage.input_tokens,
                output_tokens=plan.usage.output_tokens,
                latency_ms=plan.usage.latency_ms,
                confidence=plan.confidence,
                is_actual_usage=plan.usage.is_actual_usage,
            )

            worker_specs = [
                ("CPU Analysis", "cpu_memory", "CPU and memory analysis.", "Routine telemetry analysis."),
                ("Teams Analysis", "teams", "Teams crash analysis.", "Known telemetry interpretation."),
                ("Network/VPN Analysis", "network", "Network/VPN analysis.", "Well-defined metrics and thresholds."),
                ("Compliance Analysis", "compliance", "Compliance analysis.", "Rule-based interpretation."),
                ("History Analysis", "history", "Historical incident summarization.", "Straightforward summarization."),
            ]
            worker_outputs: list[str] = []
            for segment_name, task, task_desc, why in worker_specs:
                prompt = (
                    f"Perform {task_desc}\nDEVICE:\n{device_block}\n"
                    f"INCIDENTS:\n{incidents[:5]}"
                )
                result = self.slm.generate(
                    prompt,
                    system="You are a local SLM worker for routine endpoint analysis.",
                    metadata={"task": task, "device_id": DEVICE_ID},
                )
                seg = segment_from_generation(
                    segment=segment_name,
                    task=task,
                    role=ModelRole.WORKER,
                    why=why,
                    result=result,
                    costs=self.costs,
                    baseline=self.baseline,
                    decision="SLM",
                    decision_why=why,
                )
                if task == "cpu_memory":
                    alt = seg.alternative
                    assert alt is not None
                    seg.decision_why = (
                        f"SLM: {seg.tokens} tokens, {seg.latency_ms} ms, "
                        f"{seg.confidence:.0%} quality/confidence. "
                        f"Frontier Alternative: {alt.expected_tokens} estimated tokens, "
                        f"{alt.expected_latency_ms/1000:.1f} sec, "
                        f"{alt.expected_confidence:.0%} expected quality. "
                        "Decision: Use SLM. The small quality improvement does not justify "
                        "higher latency and Frontier consumption for this routine task."
                    )
                segments.append(seg)
                worker_outputs.append(result.text)
                self.tracer.record(
                    ctx,
                    segment=f"SLM — {segment_name}",
                    model_name=result.model_name,
                    model_type=result.model_type,
                    model_role=ModelRole.WORKER,
                    provider=result.provider,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    latency_ms=result.usage.latency_ms,
                    confidence=result.confidence,
                    is_actual_usage=result.usage.is_actual_usage,
                )

            synthesis = self.frontier.generate(
                prompt=(
                    "Create cross-domain final RCA from worker findings.\n"
                    + "\n\n".join(worker_outputs)
                ),
                system="You are a Frontier synthesizer for enterprise RCA.",
                metadata={"task": "rca_synthesis", "device_id": DEVICE_ID},
            )
            segments.append(
                segment_from_generation(
                    segment="RCA Synthesis",
                    task="rca_synthesis",
                    role=ModelRole.SYNTHESIZER,
                    why="Requires correlation across findings and advanced reasoning.",
                    result=synthesis,
                    costs=self.costs,
                    baseline=self.baseline,
                    decision="FRONTIER",
                    decision_why="Final RCA needs advanced cross-domain reasoning.",
                )
            )
            self.tracer.record(
                ctx,
                segment="FRONTIER — RCA Synthesis",
                model_name=synthesis.model_name,
                model_type=synthesis.model_type,
                model_role=ModelRole.SYNTHESIZER,
                provider=synthesis.provider,
                input_tokens=synthesis.usage.input_tokens,
                output_tokens=synthesis.usage.output_tokens,
                latency_ms=synthesis.usage.latency_ms,
                confidence=synthesis.confidence,
                is_actual_usage=synthesis.usage.is_actual_usage,
            )

            decision = build_architect_decision(
                pattern=PATTERN_NAME,
                scenario=SCENARIO,
                segments=segments,
                baseline_tasks=[
                    "planning",
                    "cpu_memory",
                    "teams",
                    "network",
                    "compliance",
                    "history",
                    "rca_synthesis",
                ],
                why=(
                    "Most individual analysis tasks are predictable. Advanced reasoning "
                    "is only required for planning and final correlation."
                ),
                recommendation=(
                    "Use Frontier where advanced reasoning creates measurable value. "
                    "Use SLM for routine execution where the quality difference does not "
                    "justify Frontier latency and cost."
                ),
                baseline=self.baseline,
                costs=self.costs,
            )
            return PatternResult(
                pattern=PATTERN_NAME,
                pattern_id=PATTERN_ID,
                scenario=SCENARIO,
                device_id=DEVICE_ID,
                segments=segments,
                summary=synthesis.text,
                findings={
                    "plan": plan.structured,
                    "worker_count": 5,
                    "primary_benefit": "Selective reasoning + orchestration efficiency",
                },
                architect_decision=decision,
                trace_id=ctx.trace_id,
                langsmith_url=ctx.langsmith_url,
                comparisons=summarize_token_bars(decision),
                metadata={"callout": "WHY NOT FRONTIER FOR CPU ANALYSIS?"},
            )
