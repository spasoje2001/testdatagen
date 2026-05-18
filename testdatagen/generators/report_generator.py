"""
HTML Coverage Report Generator for TestDataGen (#17)

Calculates test coverage per field/entity/schema and renders a clean
HTML report showing which boundary, partition, and edge-case values
were generated vs. required.

Coverage definition
-------------------
  required = union of all values the active strategy *must* produce
             (boundary values, partition representatives, edge cases)
  covered  = required ∩ actually_generated
  %        = len(covered) / len(required) * 100   (0 if required == 0)

When required == 0 (e.g. a plain random string field with no strategy
constraints), coverage is reported as 100% — there is nothing to verify.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from jinja2 import Environment, BaseLoader

from testdatagen.strategies.boundary import generate_boundary_values
from testdatagen.strategies.partition import (
    generate_partition_values,
    generate_enum_partition_values,
)
from testdatagen.strategies.edge_cases import (
    generate_edge_cases,
    generate_enum_coverage,
)

# Re-use field helpers from sql_generator
from testdatagen.generators.sql_generator import (
    _field_type_name,
    _get_constraint,
    _topological_sort,
    _collect_strategy_values,
    _combine_and_pad,
    _include_to_row,
    _generate_count,
    _combination_strategy,
    _include_cases,
    _is_array_ref,
    _is_simple_ref,
)
from testdatagen.generators.faker_integration import FakerTypeMapper

import os
from datetime import datetime
# ---------------------------------------------------------------------------
# HTML template (embedded — no file path dependency)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TestDataGen Coverage Report — {{ schema_name }}</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #64748b;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --accent: #6366f1;
    --font-mono: 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 2rem;
  }
  header {
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }
  header h1 {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }
  header h1 span { color: var(--accent); }
  .meta {
    display: flex;
    gap: 2rem;
    margin-top: 0.75rem;
    color: var(--muted);
    font-size: 0.82rem;
    font-family: var(--font-mono);
  }
  .meta b { color: var(--text); }

  /* Summary bar */
  .summary {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
  }
  .summary-pct {
    font-size: 2.5rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.04em;
  }
  .summary-detail { color: var(--muted); font-size: 0.85rem; }
  .summary-detail b { color: var(--text); }
  .progress-wrap { flex: 1; }
  .progress-bar {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 0.4rem;
  }
  .progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
  }

  /* Entity sections */
  .entity { margin-bottom: 2.5rem; }
  .entity-header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }
  .entity-header h2 {
    font-size: 1.05rem;
    font-weight: 600;
  }
  .entity-stats {
    font-size: 0.78rem;
    color: var(--muted);
    font-family: var(--font-mono);
  }
  .badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .badge-green  { background: rgba(34,197,94,.15);  color: var(--green); }
  .badge-yellow { background: rgba(234,179,8,.15);  color: var(--yellow);}
  .badge-red    { background: rgba(239,68,68,.15);  color: var(--red);   }

  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  th {
    background: var(--border);
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.6rem 1rem;
    text-align: left;
  }
  td {
    padding: 0.6rem 1rem;
    border-top: 1px solid var(--border);
    vertical-align: top;
  }
  tr:hover td { background: rgba(255,255,255,.02); }
  .field-name { font-family: var(--font-mono); color: var(--accent); }
  .field-type { color: var(--muted); font-size: 0.78rem; font-family: var(--font-mono); }
  .mini-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .mini-bar-track {
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
    min-width: 60px;
  }
  .mini-bar-fill { height: 100%; border-radius: 3px; }
  .pct-label {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    min-width: 3.5rem;
    text-align: right;
  }
  .missing {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--red);
    margin-top: 0.3rem;
  }
  .missing span {
    background: rgba(239,68,68,.1);
    border: 1px solid rgba(239,68,68,.25);
    border-radius: 4px;
    padding: 0.05rem 0.35rem;
    margin-right: 0.3rem;
    display: inline-block;
    margin-bottom: 0.2rem;
  }
  .strategy-tag {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.05rem 0.35rem;
    margin-right: 0.2rem;
  }
  .na { color: var(--muted); font-size: 0.78rem; }
  footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.78rem;
    font-family: var(--font-mono);
  }
</style>
</head>
<body>

<header>
  <h1>TestDataGen &mdash; <span>Coverage Report</span></h1>
  <div class="meta">
    <div>Schema: <b>{{ schema_name }}</b></div>
    <div>Strategy: <b>{{ strategy }}</b></div>
    <div>Seed: <b>{{ seed }}</b></div>
    <div>Generated: <b>{{ timestamp }}</b></div>
  </div>
</header>

{# Overall summary #}
<div class="summary">
  <div class="summary-pct" style="color: {{ overall.color }}">{{ overall.pct }}%</div>
  <div>
    <div class="summary-detail">
      <b>{{ overall.covered }}</b> / <b>{{ overall.required }}</b> required cases covered
      across <b>{{ entities|length }}</b> entities
    </div>
    <div class="progress-wrap">
      <div class="progress-bar">
        <div class="progress-fill" style="width:{{ overall.pct }}%; background:{{ overall.color }}"></div>
      </div>
    </div>
  </div>
</div>

{% for entity in entities %}
<div class="entity">
  <div class="entity-header">
    <h2>{{ entity.name }}</h2>
    <span class="badge badge-{{ entity.badge }}">{{ entity.pct }}%</span>
    <span class="entity-stats">{{ entity.records }} records &nbsp;|&nbsp; {{ entity.covered }}/{{ entity.required }} cases</span>
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:18%">Field</th>
        <th style="width:12%">Type</th>
        <th style="width:18%">Strategies</th>
        <th style="width:8%">Required</th>
        <th style="width:8%">Covered</th>
        <th>Coverage</th>
      </tr>
    </thead>
    <tbody>
    {% for field in entity.fields %}
      <tr>
        <td><span class="field-name">{{ field.name }}</span></td>
        <td><span class="field-type">{{ field.type }}</span></td>
        <td>
          {% for tag in field.strategy_tags %}
            <span class="strategy-tag">{{ tag }}</span>
          {% endfor %}
        </td>
        <td>{{ field.required }}</td>
        <td>{{ field.covered }}</td>
        <td>
          {% if field.required == 0 %}
            <span class="na">n/a</span>
          {% else %}
            <div class="mini-bar">
              <div class="mini-bar-track">
                <div class="mini-bar-fill" style="width:{{ field.pct }}%; background:{{ field.color }}"></div>
              </div>
              <span class="pct-label" style="color:{{ field.color }}">{{ field.pct }}%</span>
            </div>
            {% if field.missing %}
            <div class="missing">
              Missing:
              {% for m in field.missing %}
                <span>{{ m }}</span>
              {% endfor %}
            </div>
            {% endif %}
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endfor %}

<footer>Generated by TestDataGen &mdash; {{ timestamp }}</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Coverage colour helpers
# ---------------------------------------------------------------------------

def _coverage_color(pct: float) -> str:
    if pct >= 90:
        return "#22c55e"   # green
    if pct >= 60:
        return "#eab308"   # yellow
    return "#ef4444"       # red


def _coverage_badge(pct: float) -> str:
    if pct >= 90:
        return "green"
    if pct >= 60:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Per-field coverage calculation
# ---------------------------------------------------------------------------

def calculate_field_coverage(
    field,
    generated_values: List[Any],
    global_strategy: str,
) -> Dict:
    """
    Calculate coverage for a single field.

    Returns
    -------
    {
        "required":   int,
        "covered":    int,
        "percentage": float,   # 0-100
        "missing":    set,
        "strategy_tags": list[str],
    }
    """
    ft_name     = _field_type_name(field.type)
    constraints = list(getattr(field, "constraints", []) or [])

    sc = _get_constraint(constraints, "StrategyConstraint")
    field_strategy = sc.value if sc else global_strategy

    boundary_c   = _get_constraint(constraints, "BoundaryConstraint")
    partition_c  = _get_constraint(constraints, "PartitionConstraint")
    partitions_c = _get_constraint(constraints, "PartitionsConstraint")
    range_c      = _get_constraint(constraints, "RangeConstraint")
    include_c    = _get_constraint(constraints, "IncludeConstraint")
    special_c    = _get_constraint(constraints, "SpecialConstraint")
    precision_c  = _get_constraint(constraints, "PrecisionConstraint")
    precision    = precision_c.value if precision_c else 0

    required: Set[Any] = set()
    strategy_tags: List[str] = []

    # --- Boundary values ---
    use_boundary = field_strategy in ("smart", "boundary") or boundary_c is not None
    if use_boundary and ft_name in ("number", "date", "datetime") and range_c:
        bv = generate_boundary_values(ft_name, range_c.min, range_c.max, precision=precision)
        valid_bv = {r["value"] for r in bv if r["category"] == "valid"}
        required.update(valid_bv)
        strategy_tags.append("BVA")

    # --- Partition values ---
    use_partition = (
        field_strategy in ("smart", "partition")
        or partition_c is not None
        or partitions_c is not None
    )
    if use_partition and ft_name in ("number", "date", "datetime") and range_c:
        if partitions_c:
            required.update(partitions_c.values)
        elif partition_c:
            pv = generate_partition_values(
                ft_name, range_c.min, range_c.max,
                num_partitions=partition_c.value, precision=precision,
            )
            required.update(r["value"] for r in pv)
        else:
            pv = generate_partition_values(ft_name, range_c.min, range_c.max, precision=precision)
            required.update(r["value"] for r in pv)
        strategy_tags.append("EP")

    # --- Enum partition / coverage ---
    if ft_name == "enum":
        enum_vals = list(field.type.values)
        if field_strategy in ("smart", "partition"):
            pv = generate_enum_partition_values(enum_vals)
            required.update(r["value"] for r in pv)
            strategy_tags.append("EP")
        if field_strategy == "smart":
            cv = generate_enum_coverage(enum_vals)
            required.update(r["value"] for r in cv)
            if "EP" not in strategy_tags:
                strategy_tags.append("enum-coverage")

    # --- Edge cases from include constraint ---
    if include_c:
        edge = generate_edge_cases(ft_name, include_values=list(include_c.values))
        required.update(r["value"] for r in edge)
        strategy_tags.append("edge")

    # --- Special values ---
    if special_c:
        required.update(special_c.values)
        strategy_tags.append("special")

    # --- Boolean ---
    if ft_name == "boolean":
        required.update([True, False])
        strategy_tags.append("bool-coverage")

    if not required:
        return {
            "required":      0,
            "covered":       0,
            "percentage":    100.0,
            "missing":       set(),
            "strategy_tags": strategy_tags or ["random"],
        }

    gen_set = set(generated_values)
    covered = required & gen_set
    missing = required - gen_set
    pct     = len(covered) / len(required) * 100

    return {
        "required":      len(required),
        "covered":       len(covered),
        "percentage":    round(pct, 1),
        "missing":       missing,
        "strategy_tags": strategy_tags or ["random"],
    }


# ---------------------------------------------------------------------------
# Main report generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """
    Generates an HTML coverage report from a TestDataGen schema model.

    Parameters
    ----------
    model     : parsed textX model
    seed      : override seed
    timestamp : string to embed in the report header
    """

    def __init__(self, model, seed: Optional[int] = None, timestamp: str = ""):
        self.model     = model
        self.seed      = seed if seed is not None else getattr(model, "seed", None)
        self.timestamp = timestamp
        self._mapper   = FakerTypeMapper(seed=self.seed)
        self._generated_ids: Dict[str, List[Any]] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Return the complete HTML report as a string."""
        context = self._build_context()
        env  = Environment(loader=BaseLoader())
        tmpl = env.from_string(_HTML_TEMPLATE)
        return tmpl.render(**context)

    def calculate_coverage(self) -> Dict:
        """
        Return raw coverage data without rendering HTML.
        Useful for programmatic access and testing.

        Returns a dict with keys: schema_name, entities, overall.
        """
        return self._build_context()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_context(self) -> Dict:
        schema          = self.model
        entities        = _topological_sort(list(schema.entities))
        global_strategy = getattr(schema, "strategy", "random") or "random"
        global_combo    = getattr(schema, "combination_strategy", "pairwise") or "pairwise"

        entity_contexts = []
        total_required  = 0
        total_covered   = 0

        for entity in entities:
            config      = getattr(entity, "config", None)
            generate    = _generate_count(config)
            combo_strat = _combination_strategy(config, global_combo)
            includes    = _include_cases(config)

            normal_fields = [f for f in entity.fields if not _is_array_ref(f)]

            # Generate the rows (same pipeline as sql/json generators)
            field_values: Dict[str, List[Any]] = {
                field.name: _collect_strategy_values(field, global_strategy, self._mapper)
                for field in normal_fields
            }
            rows = _combine_and_pad(field_values, combo_strat, self.seed, generate)
            include_rows = [_include_to_row(tc, entity.fields) for tc in includes]
            rows = (include_rows + rows)[:generate]
            rows = self._resolve_refs(rows, normal_fields)
            self._store_ids(entity, rows)

            # Per-field coverage
            field_contexts = []
            entity_required = 0
            entity_covered  = 0

            for field in normal_fields:
                generated_values = [row.get(field.name) for row in rows]
                cov = calculate_field_coverage(field, generated_values, global_strategy)

                entity_required += cov["required"]
                entity_covered  += cov["covered"]

                missing_display = sorted(
                    str(m) for m in cov["missing"]
                )[:10]   # cap display at 10 items

                field_contexts.append({
                    "name":          field.name,
                    "type":          _field_type_name(field.type),
                    "required":      cov["required"],
                    "covered":       cov["covered"],
                    "pct":           cov["percentage"] if cov["required"] > 0 else 100,
                    "color":         _coverage_color(cov["percentage"]),
                    "missing":       missing_display,
                    "strategy_tags": cov["strategy_tags"],
                })

            entity_pct = (
                round(entity_covered / entity_required * 100, 1)
                if entity_required > 0 else 100.0
            )
            total_required += entity_required
            total_covered  += entity_covered

            entity_contexts.append({
                "name":     entity.name,
                "records":  len(rows),
                "required": entity_required,
                "covered":  entity_covered,
                "pct":      entity_pct,
                "badge":    _coverage_badge(entity_pct),
                "color":    _coverage_color(entity_pct),
                "fields":   field_contexts,
            })

        overall_pct = (
            round(total_covered / total_required * 100, 1)
            if total_required > 0 else 100.0
        )

        return {
            "schema_name": getattr(schema, "name", "Unknown"),
            "strategy":    getattr(schema, "strategy", "random") or "random",
            "seed":        self.seed if self.seed is not None else "none",
            "timestamp":   self.timestamp,
            "entities":    entity_contexts,
            "overall": {
                "pct":      overall_pct,
                "required": total_required,
                "covered":  total_covered,
                "color":    _coverage_color(overall_pct),
            },
        }

    def _store_ids(self, entity, rows):
        id_field = None
        for f in entity.fields:
            if f.name == "id":
                id_field = "id"
                break
        if id_field is None:
            for f in entity.fields:
                if _field_type_name(f.type) == "uuid":
                    id_field = f.name
                    break
        if id_field is None and entity.fields:
            id_field = entity.fields[0].name
        if id_field:
            self._generated_ids[entity.name] = [
                row.get(id_field) for row in rows if row.get(id_field) is not None
            ]

    def _resolve_refs(self, rows, fields):
        import random as _rm
        rng = _rm.Random(self.seed)
        ref_fields = {f.name: f for f in fields if _is_simple_ref(f)}
        if not ref_fields:
            return rows
        resolved = []
        for row in rows:
            new_row = dict(row)
            for fname, field in ref_fields.items():
                if new_row.get(fname) == "__ref__":
                    available = self._generated_ids.get(field.type.entity.name, [])
                    new_row[fname] = rng.choice(available) if available else None
            resolved.append(new_row)
        return resolved


def generate_report(model, output_dir, overwrite):
    """
    CLI interface for the ReportGenerator class.
    Handles file I/O and orchestration.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generator = ReportGenerator(model, timestamp=timestamp)
    
    report_content = generator.render()
    
    schema_name = getattr(model, "name", "generated_data")
    file_path = os.path.join(output_dir, f"{schema_name}.html")
    
    if os.path.exists(file_path) and not overwrite:
        raise FileExistsError(f"File {file_path} already exists. Use --overwrite to replace it.")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return file_path