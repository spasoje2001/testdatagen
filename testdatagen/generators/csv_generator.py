"""
CSV Generator for TestDataGen (#XX)

Produces CSV output from a parsed TestDataGen schema.
Reuses the value-collection, combination, and FK-resolution pipeline
from sql_generator.py — only the output serialisation differs.

Output structure
----------------
A directory named after the schema is created, containing one CSV file
per entity and a generation metadata file.

Example:

Ecommerce/
├── User.csv
├── Product.csv
├── Order.csv
└── generated_details.txt

Each CSV file contains a header row followed by generated records:

id,email,age
uuid-1,john@example.com,18
uuid-2,jane@example.com,20

Array-ref fields (ref Entity[]) are stored as semicolon-separated
ID lists within a single CSV cell.

The generated_details.txt file contains generation metadata such as the
schema name, seed, generation timestamp, output format, and the number
of generated records per entity.
"""
from __future__ import annotations

import csv
import os
import random as _random_module
import shutil
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from testdatagen.generators.faker_integration import FakerTypeMapper

# Re-use all the shared pipeline helpers from sql_generator
from testdatagen.generators.sql_generator import (
    _topological_sort,
    _collect_strategy_values,
    _combine_and_pad,
    _include_to_row,
    _generate_count,
    _combination_strategy,
    _include_cases,
    _field_type_name,
    _is_array_ref,
    _is_simple_ref,
    _requires_unique_generation,
    _schema_entities
)


# ---------------------------------------------------------------------------
# CSV value formatting
# ---------------------------------------------------------------------------

def format_value_csv(value: Any) -> Any:
    """
    Convert a Python value to a CSV-compatible string.

    Rules
    -----
    None            → ""
    bool            → "true" / "false"
    int / float     → number      (as-is)
    date            → "YYYY-MM-DD"
    datetime        → "YYYY-MM-DDTHH:MM:SS"
    str             → str         (as-is)
    list            → semicolon-separated values
    anything else   → str(value)
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return ";".join("" if v is None else str(format_value_csv(v)) for v in value)
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class CSVGenerator:
    """
    Generates CSV files from a TestDataGen schema model.

    One CSV file is created for each entity together with a
    generation_details.txt metadata file.

    Parameters
    ----------
    model       : parsed textX model (from grammar_loader.load_model)
    seed        : override seed (None → use schema seed or random)
    timestamp   : ISO string to embed in metadata (defaults to empty string)
    """

    def __init__(
        self,
        model,
        seed: Optional[int] = None,
        timestamp: str = "",
    ):
        self.model     = model
        self.seed      = seed if seed is not None else getattr(model, "seed", None)
        self.timestamp = timestamp
        self._mapper   = FakerTypeMapper(seed=self.seed)
        self._generated_ids: Dict[str, List[Any]] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def build(self) -> dict:
        """
        Build and return the output as a plain Python dict.
        Useful for programmatic access before writing CSV files.
        """
        schema          = self.model
        entities        = _topological_sort(list(_schema_entities(schema)))
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

            combo_fields = [f for f in normal_fields if not _requires_unique_generation(f)]
            unique_fields = [f for f in normal_fields if _requires_unique_generation(f)]

            # 1. Collect strategy values for normal fields
            field_values: Dict[str, List[Any]] = {
                field.name: _collect_strategy_values(field, global_strategy, self._mapper, generate)
                for field in combo_fields
            }

            # 2. Combine + pad to generate count
            rows = _combine_and_pad(field_values, combo_strat, self.seed, generate)

            # 3. Prepend explicit include test cases, then trim
            include_rows = [_include_to_row(tc, entity.fields) for tc in includes]
            rows = (include_rows + rows)[:generate]

            # 4. Adding unique fields
            for row in rows:
                for f in unique_fields:
                    if row.get(f.name) is None:
                        row[f.name] = self._mapper.generate_for_type_name(_field_type_name(f.type), f.constraints)

            # 5. Resolve FK refs
            rows = self._resolve_refs(rows, normal_fields)

            # 6. Track IDs for downstream FK resolution
            self._store_ids(entity, rows)

            # 7. Attach array-ref fields as lists of IDs on each row
            if array_fields:
                rows = self._attach_array_refs(entity, array_fields, rows)

            # 8. Convert values to CSV-compatible representation
            csv_rows = [
                {col: format_value_csv(row.get(col)) for col in row}
                for row in rows
            ]

            entities_out[entity.name] = csv_rows

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

    def generate(self, output_dir: str) -> None:
        """
        Generate one CSV file per entity together with
        a generation_details.txt metadata file.
        """
        data = self.build()

        # Write metadata file
        self._write_generation_details(
            output_dir,
            data["metadata"],
            data["entities"],
        )

        # Write one CSV per entity
        for entity_name, rows in data["entities"].items():
            self._write_entity_csv(
                output_dir,
                entity_name,
                rows,
            )

    def _write_entity_csv(
        self,
        output_dir: str,
        entity_name: str,
        rows: List[Dict[str, Any]],
    ) -> None:
        path = os.path.join(output_dir, f"{entity_name}.csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            if not rows:
                return

            writer = csv.DictWriter(
                f,
                fieldnames=list(rows[0].keys()),
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(row)
    
    def _write_generation_details(
        self,
        output_dir: str,
        metadata: Dict[str, Any],
        entities: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        path = os.path.join(output_dir, "generation_details.txt")

        with open(path, "w", encoding="utf-8") as f:
            f.write("TestDataGen CSV Generation\n")
            f.write("==========================\n\n")

            f.write(f"Schema: {metadata['schema']}\n")
            f.write(f"Seed: {metadata['seed']}\n")
            f.write(f"Generated at: {metadata['generated_at']}\n\n")

            total = sum(len(rows) for rows in entities.values())

            f.write(f"Format: CSV\n")
            f.write(f"Output directory: {metadata['schema']}\n")
            f.write(f"Entities: {len(entities)}\n")
            f.write(f"Total records: {total}\n\n")

            f.write("Entities\n")
            f.write("-----------------\n")
            for entity_name, rows in entities.items():
                f.write(f"{entity_name}: {len(rows)} records\n")


def generate_csv(model, output_dir, overwrite):
    """
    Generate CSV files for the given schema.

    Returns
    -------
    str
        Path to the generated directory.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    generator = CSVGenerator(model, timestamp=timestamp)

    schema_name = getattr(model, "name", "generated_data")
    csv_dir = os.path.join(output_dir, schema_name)

    if os.path.exists(csv_dir):
        if not overwrite:
            raise FileExistsError(
                f"Directory {csv_dir} already exists. Use --overwrite to replace it."
            )
        shutil.rmtree(csv_dir)

    os.makedirs(csv_dir, exist_ok=True)

    generator.generate(csv_dir)

    return csv_dir
