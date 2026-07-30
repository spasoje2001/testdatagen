"""
YAML Generator for TestDataGen (#XX)

Produces structured YAML output from a parsed TestDataGen schema.
Reuses the value-collection, combination, and FK-resolution pipeline
from sql_generator.py — only the output serialisation differs.

Output structure
----------------
metadata:
  schema: Ecommerce
  seed: 12345
  generated_at: 2024-01-15T10:30:00

entities:
  User:
    - id: uuid-1
      email: john@example.com
      age: 18
    - ...

  Order:
    - ...

Array-ref fields (ref Entity[]) are stored as YAML sequences of IDs
rather than full nested objects, keeping the output compact and easy
to consume.
"""

from __future__ import annotations

import os
import random as _random_module
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import yaml

from testdatagen.generators.faker_integration import FakerTypeMapper

# Re-use all the shared pipeline helpers from sql_generator
from testdatagen.generators.sql_generator import (
    _topological_sort,
    _collect_strategy_values,
    _combine_and_pad,
    _include_to_row,
    _get_option,
    _generate_count,
    _combination_strategy,
    _include_cases,
    _field_type_name,
    _is_array_ref,
    _is_simple_ref,
    _is_unique,
    _requires_unique_generation,
    _deduplicate,
    _schema_entities
)


# ---------------------------------------------------------------------------
# YAML value formatting
# ---------------------------------------------------------------------------

def format_value_yaml(value: Any) -> Any:
    """
    Convert a Python value to a YAML-serialisable type.

    Rules
    -----
    None            → None        (serialises as YAML null)
    bool            → bool
    int / float     → number
    date            → "YYYY-MM-DD"
    datetime        → "YYYY-MM-DDTHH:MM:SS"
    str             → str
    list            → list
    anything else   → str(value)
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [format_value_yaml(v) for v in value]
    if isinstance(value, str):
        return value
    return str(value)

# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class YAMLGenerator:
    """
    Generates structured YAML from a TestDataGen schema model.

    Parameters
    ----------
    model       : parsed textX model (from grammar_loader.load_model)
    seed        : override seed (None → use schema seed or random)
    timestamp   : ISO string to embed in metadata (defaults to empty string)
    pretty      : if True, output is formatted (default True)
    indent      : indentation spaces (default 2)
    """

    def __init__(
        self,
        model,
        seed: Optional[int] = None,
        timestamp: str = "",
        pretty: bool = True,
        indent: int = 2,
    ):
        self.model = model
        self.seed = seed if seed is not None else getattr(model, "seed", None)
        self.timestamp = timestamp
        self.pretty = pretty
        self.indent = indent
        self._mapper = FakerTypeMapper(seed=self.seed)
        self._generated_ids: Dict[str, List[Any]] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Return the complete YAML document as a string."""
        data = self.build()

        return yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            indent=self.indent,
            default_flow_style=False,
        )

    def build(self) -> dict:
        """
        Build and return the output as a plain Python dict.
        Useful for programmatic access without parsing YAML.
        """
        schema = self.model
        entities = _topological_sort(list(_schema_entities(schema)))
        global_strategy = getattr(schema, "strategy", "random") or "random"
        global_combo = (
            getattr(schema, "combination_strategy", "pairwise")
            or "pairwise"
        )

        entities_out: Dict[str, List[dict]] = {}

        for entity in entities:
            config = getattr(entity, "config", None)
            generate = _generate_count(config)
            combo_strat = _combination_strategy(config, global_combo)
            includes = _include_cases(config)

            normal_fields = [
                f for f in entity.fields
                if not _is_array_ref(f)
            ]
            array_fields = [
                f for f in entity.fields
                if _is_array_ref(f)
            ]

            combo_fields = [
                f for f in normal_fields
                if not _requires_unique_generation(f)
            ]
            unique_fields = [
                f for f in normal_fields
                if _requires_unique_generation(f)
            ]

            # 1. Collect strategy values
            field_values: Dict[str, List[Any]] = {
                field.name: _collect_strategy_values(
                    field,
                    global_strategy,
                    self._mapper,
                    generate,
                )
                for field in combo_fields
            }

            # 2. Combine values
            rows = _combine_and_pad(
                field_values,
                combo_strat,
                self.seed,
                generate,
            )

            # 3. Include explicit test cases
            include_rows = [
                _include_to_row(tc, entity.fields)
                for tc in includes
            ]
            rows = (include_rows + rows)[:generate]

            # 4. Generate unique values
            for row in rows:
                for field in unique_fields:
                    if row.get(field.name) is None:
                        row[field.name] = (
                            self._mapper.generate_for_type_name(
                                _field_type_name(field.type),
                                field.constraints,
                            )
                        )

            # 5. Resolve FK references
            rows = self._resolve_refs(rows, normal_fields)

            # 6. Store IDs
            self._store_ids(entity, rows)

            # 7. Attach array refs
            if array_fields:
                rows = self._attach_array_refs(
                    entity,
                    array_fields,
                    rows,
                )

            # 8. Convert values to YAML-safe types
            yaml_rows = [
                {
                    col: format_value_yaml(row.get(col))
                    for col in row
                }
                for row in rows
            ]
            entities_out[entity.name] = yaml_rows

        return {
            "metadata": {
                "schema": getattr(schema, "name", "Unknown"),
                "seed": self.seed,
                "generated_at": self.timestamp,
            },
            "entities": entities_out,
        }
    # ------------------------------------------------------------------
    # Internal helpers (mirror sql_generator internals)
    # ------------------------------------------------------------------

    def _store_ids(self, entity, rows: List[Dict[str, Any]]):
        """Remember generated ID values so later entities can use them as FKs."""
        id_field = None

        for field in entity.fields:
            if field.name == "id":
                id_field = "id"
                break

        if id_field is None:
            for field in entity.fields:
                if _field_type_name(field.type) == "uuid":
                    id_field = field.name
                    break

        if id_field is None and entity.fields:
            id_field = entity.fields[0].name

        if id_field:
            self._generated_ids[entity.name] = [
                row.get(id_field)
                for row in rows
                if row.get(id_field) is not None
            ]

    def _resolve_refs(
        self,
        rows: List[Dict[str, Any]],
        fields,
    ) -> List[Dict[str, Any]]:
        """Replace __ref__ sentinels with actual FK values."""

        rng = _random_module.Random(self.seed)
        ref_fields = {
            field.name: field
            for field in fields
            if _is_simple_ref(field)
        }

        if not ref_fields:
            return rows

        resolved = []

        for row in rows:
            new_row = dict(row)

            for field_name, field in ref_fields.items():
                if new_row.get(field_name) == "__ref__":
                    ref_entity = field.type.entity.name
                    available = self._generated_ids.get(ref_entity, [])

                    new_row[field_name] = (
                        rng.choice(available)
                        if available
                        else None
                    )

            resolved.append(new_row)

        return resolved

    def _attach_array_refs(
        self,
        entity,
        array_fields,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Attach array-reference fields as lists of referenced IDs.

        Example:
            items:
              - uuid-1
              - uuid-2
        """
        rng = _random_module.Random(self.seed)
        for field in array_fields:
            ref_entity = field.type.entity.name
            available_ids = self._generated_ids.get(ref_entity, [])

            if not available_ids:
                for row in rows:
                    row[field.name] = []
                continue

            field_type = field.type

            has_count = bool(getattr(field_type, "has_count", False))
            min_count = getattr(field_type, "min", 1) if has_count else 1
            max_count = getattr(field_type, "max", 3) if has_count else 3

            for row in rows:
                count = rng.randint(min_count, max_count)
                row[field.name] = rng.choices(
                    available_ids,
                    k=count,
                )

        return rows


def generate_yaml(model, output_dir, overwrite):
    """
    CLI interface for the YAMLGenerator class.
    Handles file I/O and orchestration.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generator = YAMLGenerator(
        model,
        timestamp=timestamp,
    )
    yaml_content = generator.render()
    schema_name = getattr(model, "name", "generated_data")
    file_path = os.path.join(
        output_dir,
        f"{schema_name}.yaml",
    )
    if os.path.exists(file_path) and not overwrite:
        raise FileExistsError(
            f"File {file_path} already exists. "
            "Use --overwrite to replace it."
        )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    return file_path
