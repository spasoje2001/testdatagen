"""
JSON Generator for TestDataGen (#16)

Produces structured JSON output from a parsed TestDataGen schema.
Reuses the value-collection, combination, and FK-resolution pipeline
from sql_generator.py — only the output serialisation differs.

Output structure
----------------
{
  "metadata": {
    "schema": "Ecommerce",
    "seed": 12345,
    "generated_at": "2024-01-15T10:30:00"
  },
  "entities": {
    "User": [
      {"id": "uuid-1", "email": "john@example.com", "age": 18, ...},
      ...
    ],
    "Order": [...]
  }
}

Array-ref fields (ref Entity[]) are stored as a list of IDs on each row
rather than full nested objects, keeping the output flat and easy to mock.
"""

from __future__ import annotations

import json
import os
import random as _random_module
from datetime import date, datetime
from typing import Any, Dict, List, Optional

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
    _deduplicate,
)


# ---------------------------------------------------------------------------
# JSON value formatting
# ---------------------------------------------------------------------------

def format_value_json(value: Any) -> Any:
    """
    Convert a Python value to a JSON-serialisable type.

    Rules
    -----
    None            → None        (serialises as JSON null)
    bool            → bool        (True/False — must come before int check)
    int / float     → number      (as-is)
    date            → "YYYY-MM-DD"
    datetime        → "YYYY-MM-DDTHH:MM:SS"
    str             → str         (as-is)
    list            → list        (array-ref ID lists)
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
        return [format_value_json(v) for v in value]
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class JSONGenerator:
    """
    Generates structured JSON from a TestDataGen schema model.

    Parameters
    ----------
    model       : parsed textX model (from grammar_loader.load_model)
    seed        : override seed (None → use schema seed or random)
    timestamp   : ISO string to embed in metadata (defaults to empty string)
    pretty      : if True, output is indented (default True)
    indent      : indentation spaces when pretty=True (default 2)
    """

    def __init__(
        self,
        model,
        seed: Optional[int] = None,
        timestamp: str = "",
        pretty: bool = True,
        indent: int = 2,
    ):
        self.model     = model
        self.seed      = seed if seed is not None else getattr(model, "seed", None)
        self.timestamp = timestamp
        self.pretty    = pretty
        self.indent    = indent
        self._mapper   = FakerTypeMapper(seed=self.seed)
        self._generated_ids: Dict[str, List[Any]] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Return the complete JSON document as a string."""
        data = self.build()
        return json.dumps(data, indent=self.indent if self.pretty else None, ensure_ascii=False)

    def build(self) -> dict:
        """
        Build and return the output as a plain Python dict.
        Useful for programmatic access without parsing JSON.
        """
        schema          = self.model
        entities        = _topological_sort(list(schema.entities))
        global_strategy = getattr(schema, "strategy", "random") or "random"
        global_combo    = getattr(schema, "combination_strategy", "pairwise") or "pairwise"

        entities_out: Dict[str, List[dict]] = {}

        for entity in entities:
            config      = getattr(entity, "config", None)
            generate    = _generate_count(config)
            combo_strat = _combination_strategy(config, global_combo)
            includes    = _include_cases(config)

            normal_fields = [f for f in entity.fields if not _is_array_ref(f)]
            array_fields  = [f for f in entity.fields if _is_array_ref(f)]

            # 1. Collect strategy values for normal fields
            field_values: Dict[str, List[Any]] = {
                field.name: _collect_strategy_values(field, global_strategy, self._mapper)
                for field in normal_fields
            }

            # 2. Combine + pad to generate count
            rows = _combine_and_pad(field_values, combo_strat, self.seed, generate)

            # 3. Prepend explicit include test cases, then trim
            include_rows = [_include_to_row(tc, entity.fields) for tc in includes]
            rows = (include_rows + rows)[:generate]

            # 4. Resolve simple FK refs
            rows = self._resolve_refs(rows, normal_fields)

            # 5. Track IDs for downstream FK resolution
            self._store_ids(entity, rows)

            # 6. Attach array-ref fields as lists of IDs on each row
            if array_fields:
                rows = self._attach_array_refs(entity, array_fields, rows)

            # 7. Convert all values to JSON-safe types
            json_rows = [
                {col: format_value_json(row.get(col)) for col in row}
                for row in rows
            ]

            entities_out[entity.name] = json_rows

        return {
            "metadata": {
                "schema":       getattr(schema, "name", "Unknown"),
                "seed":         self.seed,
                "generated_at": self.timestamp,
            },
            "entities": entities_out,
        }

    # ------------------------------------------------------------------
    # Internal helpers  (mirror sql_generator internals)
    # ------------------------------------------------------------------

    def _store_ids(self, entity, rows: List[Dict[str, Any]]):
        """Remember generated id values so later entities can use them as FKs."""
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

    def _resolve_refs(self, rows: List[Dict[str, Any]], fields) -> List[Dict[str, Any]]:
        """Replace __ref__ sentinels with actual FK values."""
        rng = _random_module.Random(self.seed)
        ref_fields = {f.name: f for f in fields if _is_simple_ref(f)}
        if not ref_fields:
            return rows

        resolved = []
        for row in rows:
            new_row = dict(row)
            for fname, field in ref_fields.items():
                if new_row.get(fname) == "__ref__":
                    ref_entity_name = field.type.entity.name
                    available = self._generated_ids.get(ref_entity_name, [])
                    new_row[fname] = rng.choice(available) if available else None
            resolved.append(new_row)
        return resolved

    def _attach_array_refs(
        self,
        entity,
        array_fields,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        For each array-ref field, attach a list of FK IDs directly on the row
        under the field name.  e.g. row["items"] = ["uuid-1", "uuid-2"].
        """
        rng = _random_module.Random(self.seed)

        for arr_field in array_fields:
            ref_entity_name = arr_field.type.entity.name
            available_ids   = self._generated_ids.get(ref_entity_name, [])
            if not available_ids:
                for row in rows:
                    row[arr_field.name] = []
                continue

            ft        = arr_field.type
            has_count = bool(getattr(ft, "has_count", False))
            min_count = getattr(ft, "min", 1) if has_count else 1
            max_count = getattr(ft, "max", 3) if has_count else 3

            for row in rows:
                count = rng.randint(min_count, max_count)
                row[arr_field.name] = rng.choices(available_ids, k=count)

        return rows



def generate_json(model, output_dir, overwrite):
    """
    CLI interface for the JSONGenerator class.
    Handles file I/O and orchestration.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generator = JSONGenerator(model, timestamp=timestamp)
    
    json_content = generator.render()
    
    schema_name = getattr(model, "name", "generated_data")
    file_path = os.path.join(output_dir, f"{schema_name}.json")
    
    if os.path.exists(file_path) and not overwrite:
        raise FileExistsError(f"File {file_path} already exists. Use --overwrite to replace it.")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(json_content)
    
    return file_path