"""Export saved pattern results to a shareable static HTML report."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.observability.trace_store import get_trace_store
from app.services.result_store import get_result_store
from app.services.scenario_service import PATTERN_CATALOG, get_scenario_service

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "right-model-lab-report.html"


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _segment_rows(result) -> str:
    rows = []
    for s in result.segments:
        if result.pattern_id == "router" and s.segment.startswith("REQ-"):
            continue
        rows.append(
            "<tr>"
            f"<td>{_esc(s.segment)}</td>"
            f"<td><span class='badge {s.model_type.value.lower()}'>{_esc(s.model_type.value)}</span></td>"
            f"<td>{_esc(s.tokens)}</td>"
            f"<td>{_esc(round(s.latency_ms, 1))} ms</td>"
            f"<td>{_esc(round(s.confidence * 100, 1))}%</td>"
            f"<td>{_esc(s.provenance)}</td>"
            f"<td>{_esc(s.why)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_html() -> str:
    settings = get_settings()
    status = settings.public_status()
    service = get_scenario_service()
    cards = service.overview_cards()
    mlops = service.mlops_dashboard()
    kpis = mlops.get("kpis") or {}
    results = get_result_store().all()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pattern_cards = []
    pattern_sections = []
    for item in PATTERN_CATALOG:
        result = results.get(item["pattern_id"])
        last = result.created_at.isoformat() if result else "Not run"
        pattern_cards.append(
            f"""
<article class="tile">
  <h3>{_esc(item['pattern'])}</h3>
  <p>{_esc(item['scenario'])}</p>
  <div class="muted"><b>SLM:</b> {_esc(item['slm_role'])}</div>
  <div class="muted"><b>Frontier:</b> {_esc(item['frontier_role'])}</div>
  <div class="benefit">{_esc(item['primary_benefit'])}</div>
  <div class="muted">Last run: {_esc(last)}</div>
</article>
"""
        )
        if not result or not result.architect_decision:
            pattern_sections.append(
                f"<section id='{_esc(item['pattern_id'])}'><h2>{_esc(item['pattern'])}</h2>"
                f"<p class='muted'>No saved result yet.</p></section>"
            )
            continue
        d = result.architect_decision
        comps = result.comparisons or {}
        pattern_sections.append(
            f"""
<section id="{_esc(item['pattern_id'])}">
  <h2>{_esc(result.pattern)}</h2>
  <p class="lead">{_esc(result.scenario)}</p>
  <div class="grid4">
    <div class="kpi"><div class="label">SLM Calls</div><div class="value">{d.slm_calls}</div></div>
    <div class="kpi"><div class="label">Frontier Calls</div><div class="value">{d.frontier_calls}</div></div>
    <div class="kpi"><div class="label">Frontier Tokens Avoided</div><div class="value">{d.frontier_tokens_avoided} ({d.frontier_tokens_avoided_pct}%)</div></div>
    <div class="kpi"><div class="label">Hybrid Confidence</div><div class="value">{round(d.hybrid_confidence*100,1)}%</div></div>
  </div>
  <div class="panel">
    <h3>AI Architect Decision</h3>
    <p><b>Frontier used for:</b> {_esc(', '.join(d.frontier_used_for) or 'None')}</p>
    <p><b>SLM used for:</b> {_esc(', '.join(d.slm_used_for) or 'None')}</p>
    <p><b>Why:</b> {_esc(d.why_this_architecture)}</p>
    <p><b>Recommendation:</b> {_esc(d.recommendation)}</p>
    <p class="muted">Hybrid tokens: {d.total_tokens} · All-Frontier (ESTIMATED): {d.all_frontier_tokens} · Cost avoided*: {d.cost_avoided}</p>
  </div>
  <div class="panel">
    <h3>Segment Ledger</h3>
    <table>
      <thead><tr><th>Segment</th><th>Model Type</th><th>Tokens</th><th>Latency</th><th>Confidence</th><th>Provenance</th><th>Why</th></tr></thead>
      <tbody>{_segment_rows(result)}</tbody>
    </table>
  </div>
  <details class="panel">
    <summary>Comparison payload</summary>
    <pre>{_esc(json.dumps(comps, indent=2, default=str)[:12000])}</pre>
  </details>
  <p class="muted">Trace ID: {_esc(result.trace_id)}</p>
</section>
"""
        )

    efficiency_rows = "".join(
        "<tr>"
        f"<td>{_esc(e.get('pattern'))}</td>"
        f"<td>{_esc(e.get('slm_calls'))}</td>"
        f"<td>{_esc(e.get('frontier_calls'))}</td>"
        f"<td>{_esc(e.get('slm_tokens'))}</td>"
        f"<td>{_esc(e.get('frontier_tokens'))}</td>"
        f"<td>{_esc(e.get('frontier_tokens_avoided'))}</td>"
        f"<td>{_esc(e.get('confidence'))}</td>"
        f"<td>{_esc(e.get('primary_benefit'))}</td>"
        "</tr>"
        for e in (mlops.get("efficiency_table") or [])
    )

    recent_spans = get_trace_store().list_runs(limit=40)
    span_rows = "".join(
        "<tr>"
        f"<td>{_esc((r.get('trace_id') or '')[:10])}</td>"
        f"<td>{_esc(r.get('pattern'))}</td>"
        f"<td>{_esc(r.get('segment'))}</td>"
        f"<td>{_esc(r.get('model_type'))}</td>"
        f"<td>{_esc(r.get('total_tokens'))}</td>"
        f"<td>{_esc(r.get('latency_ms'))}</td>"
        f"<td>{_esc(r.get('provenance'))}</td>"
        "</tr>"
        for r in reversed(recent_spans)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Right Model Lab — Static Demo Report</title>
  <style>
    :root {{
      --bg:#0b1220; --panel:#111827; --text:#e5e7eb; --muted:#94a3b8;
      --cyan:#22d3ee; --green:#34d399; --blue:#60a5fa; --amber:#fbbf24; --line:rgba(148,163,184,.25);
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family: Inter, Segoe UI, sans-serif; color:var(--text);
      background: radial-gradient(900px 400px at 10% -10%, rgba(34,211,238,.12), transparent 50%),
                  linear-gradient(180deg,#0b1220,#0f172a 60%,#111827);
    }}
    .wrap {{ max-width:1200px; margin:0 auto; padding:1.25rem; }}
    .hero {{
      border:1px solid rgba(34,211,238,.35); border-radius:16px; padding:1.1rem 1.25rem;
      background:linear-gradient(120deg, rgba(34,211,238,.14), rgba(16,185,129,.10));
      margin-bottom:1rem;
    }}
    .eyebrow {{ color:var(--cyan); font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; font-weight:700; }}
    h1 {{ margin:.2rem 0; font-size:1.8rem; }}
    .subtitle,.muted,.lead {{ color:var(--muted); }}
    .grid5,.grid4,.tiles {{ display:grid; gap:.7rem; }}
    .grid5 {{ grid-template-columns:repeat(5,minmax(0,1fr)); margin: .8rem 0; }}
    .grid4 {{ grid-template-columns:repeat(4,minmax(0,1fr)); margin: .8rem 0; }}
    .tiles {{ grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }}
    .kpi,.tile,.panel {{
      background:rgba(15,23,42,.72); border:1px solid var(--line); border-radius:14px; padding:.85rem;
    }}
    .kpi .label,.tile .muted {{ color:var(--muted); font-size:.78rem; }}
    .kpi .value {{ font-size:1.2rem; font-weight:700; margin-top:.2rem; font-family: ui-monospace, monospace; }}
    .benefit {{ color:var(--green); font-weight:600; margin-top:.45rem; font-size:.85rem; }}
    table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
    th,td {{ border-bottom:1px solid var(--line); padding:.45rem .35rem; text-align:left; vertical-align:top; }}
    th {{ color:#cbd5e1; }}
    .badge {{ display:inline-block; border-radius:999px; padding:.1rem .45rem; font-size:.7rem; font-weight:700; }}
    .badge.slm {{ background:rgba(16,185,129,.18); color:#6ee7b7; }}
    .badge.frontier {{ background:rgba(59,130,246,.18); color:#93c5fd; }}
    .badge.non_llm {{ background:rgba(245,158,11,.16); color:#fcd34d; }}
    nav a {{ color:var(--cyan); margin-right:.8rem; text-decoration:none; font-size:.9rem; }}
    pre {{ white-space:pre-wrap; word-break:break-word; color:#cbd5e1; font-size:.78rem; }}
    @media (max-width:900px) {{
      .grid5,.grid4 {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Right Model Lab</h1>
      <p class="subtitle">Static shareable report — use the right model for the right task.</p>
      <p class="muted">Generated { _esc(generated) } · Mode: {"DEMO" if status.get("demo_mode") else "LIVE"} · LangSmith: {"active" if status.get("langsmith_active") else "local-only"}</p>
      <nav>
        <a href="#overview">Overview</a>
        <a href="#patterns">Patterns</a>
        <a href="#efficiency">Efficiency</a>
        <a href="#spans">Spans</a>
      </nav>
    </header>

    <section id="overview">
      <h2>Overview KPIs</h2>
      <div class="grid5">
        <div class="kpi"><div class="label">Endpoints</div><div class="value">{_esc(cards.get('endpoints'))}</div></div>
        <div class="kpi"><div class="label">Healthy / At Risk / Critical</div><div class="value">{_esc(cards.get('healthy'))} / {_esc(cards.get('at_risk'))} / {_esc(cards.get('critical'))}</div></div>
        <div class="kpi"><div class="label">SLM Calls</div><div class="value">{_esc(kpis.get('slm_calls', cards.get('slm_calls')))}</div></div>
        <div class="kpi"><div class="label">Frontier Calls</div><div class="value">{_esc(kpis.get('frontier_calls', cards.get('frontier_calls')))}</div></div>
        <div class="kpi"><div class="label">Frontier Tokens Avoided</div><div class="value">{_esc(kpis.get('frontier_tokens_avoided', 0))}</div></div>
      </div>
      <p class="muted">Illustrative pricing — configure using current provider pricing. Estimated cost avoided*: {_esc(kpis.get('estimated_cost_avoided', cards.get('estimated_cost_avoided')))}</p>
    </section>

    <section id="patterns">
      <h2>The Five Architecture Patterns</h2>
      <div class="tiles">{''.join(pattern_cards)}</div>
    </section>

    {''.join(pattern_sections)}

    <section id="efficiency">
      <h2>Pattern Efficiency Table</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Pattern</th><th>SLM Calls</th><th>Frontier Calls</th><th>SLM Tokens</th><th>Frontier Tokens</th><th>Frontier Tokens Avoided</th><th>Confidence</th><th>Primary Benefit</th></tr></thead>
          <tbody>{efficiency_rows or '<tr><td colspan="8">No efficiency rows yet. Run patterns first.</td></tr>'}</tbody>
        </table>
      </div>
    </section>

    <section id="spans">
      <h2>Recent Local Spans</h2>
      <div class="panel">
        <table>
          <thead><tr><th>Trace</th><th>Pattern</th><th>Segment</th><th>Model Type</th><th>Tokens</th><th>Latency</th><th>Provenance</th></tr></thead>
          <tbody>{span_rows or '<tr><td colspan="7">No spans recorded.</td></tr>'}</tbody>
        </table>
      </div>
      <p class="muted">Provenance labels: ACTUAL / SIMULATED / ESTIMATED. Secrets are never included in this report.</p>
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_html(), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
