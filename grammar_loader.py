from textx import metamodel_from_file, get_location
from textx.exceptions import TextXSemanticError
from pathlib import Path

GRAMMAR_PATH = Path(__file__).resolve().parent / "testdatagen" / "grammar" / "testdatagen.tx"

_METAMODEL = None
RANGE_TYPES = {"number", "date", "datetime"}
PRECISION_TYPES = {"number"}
PARTITION_TYPES = {"number", "date", "datetime"}
COVERAGE_MIN = 0
COVERAGE_MAX = 100


def _field_type_name(field_type):
    class_name = field_type.__class__.__name__
    if class_name == "RefType":
        return "ref"
    if class_name == "EnumType":
        return "enum"
    if hasattr(field_type, "name"):
        return field_type.name
    return class_name


def _constraint_name(constraint):
    return constraint.__class__.__name__


def _raise(message, obj):
    raise TextXSemanticError(message, **get_location(obj))


def _validate_range_constraint(field, constraint, field_type_name):
    if field_type_name not in RANGE_TYPES:
        _raise(
            f"Field '{field.name}': range constraint is allowed only for "
            f"number/date/datetime fields.",
            constraint,
        )

    min_value = constraint.min
    max_value = constraint.max

    if field_type_name == "number":
        if not isinstance(min_value, (int, float)) or not isinstance(max_value, (int, float)):
            _raise(
                f"Field '{field.name}': number range must use numeric values.",
                constraint,
            )
    else:
        if not isinstance(min_value, str) or not isinstance(max_value, str):
            _raise(
                f"Field '{field.name}': date/datetime range must use quoted values.",
                constraint,
            )

    if min_value > max_value:
        _raise(
            f"Field '{field.name}': range minimum cannot be greater than maximum.",
            constraint,
        )


def _validate_field(field):
    field_type_name = _field_type_name(field.type)

    if field.type.__class__.__name__ == "RefType":
        _validate_ref_type(field)

    constraints = getattr(field, "constraints", []) or []
    names = [_constraint_name(c) for c in constraints]

    if names.count("PartitionConstraint") > 1:
        _raise(f"Field '{field.name}': partition can be defined only once.", field)

    if names.count("PartitionsConstraint") > 1:
        _raise(f"Field '{field.name}': partitions can be defined only once.", field)

    if "PartitionConstraint" in names and "PartitionsConstraint" in names:
        _raise(
            f"Field '{field.name}': partition and partitions cannot be used together.",
            field,
        )

    for constraint in constraints:
        cname = _constraint_name(constraint)

        if cname == "RangeConstraint":
            _validate_range_constraint(field, constraint, field_type_name)

        elif cname == "PrecisionConstraint":
            if field_type_name not in PRECISION_TYPES:
                _raise(
                    f"Field '{field.name}': precision is allowed only for number fields.",
                    constraint,
                )
            if constraint.value < 0:
                _raise(
                    f"Field '{field.name}': precision must be >= 0.",
                    constraint,
                )

        elif cname in {"PartitionConstraint", "PartitionsConstraint", "BoundaryConstraint"}:
            if field_type_name not in PARTITION_TYPES:
                _raise(
                    f"Field '{field.name}': {cname} is allowed only for "
                    f"number/date/datetime fields.",
                    constraint,
                )

            if cname == "PartitionConstraint" and constraint.value <= 0:
                _raise(
                    f"Field '{field.name}': partition value must be > 0.",
                    constraint,
                )

            if cname == "PartitionsConstraint":
                if len(constraint.values) == 0:
                    _raise(
                        f"Field '{field.name}': partitions must contain at least one value.",
                        constraint,
                    )
                if any(v <= 0 for v in constraint.values):
                    _raise(
                        f"Field '{field.name}': partitions values must be > 0.",
                        constraint,
                    )

        elif cname == "CoverageConstraint":
            if not (COVERAGE_MIN <= constraint.value <= COVERAGE_MAX):
                _raise(
                    f"Field '{field.name}': coverage must be between 0 and 100.",
                    constraint,
                )

        elif cname == "SpecialConstraint":
            if len(constraint.values) == 0:
                _raise(
                    f"Field '{field.name}': special must contain at least one value.",
                    constraint,
                )

        elif cname == "IncludeConstraint":
            values = list(constraint.values)
            if len(set(values)) != len(values):
                _raise(
                    f"Field '{field.name}': include cannot contain duplicate values.",
                    constraint,
                )

        elif cname == "UniqueConstraint":
            pass

        elif cname == "StrategyConstraint":
            pass

def _validate_ref_type(field):
    field_type = field.type

    if field_type.__class__.__name__ != "RefType":
        return

    is_array = bool(getattr(field_type, "array", False))
    has_count = bool(getattr(field_type, "has_count", False))
    count_boundary = bool(getattr(field_type, "count_boundary", False))

    min_count = getattr(field_type, "min", None)
    max_count = getattr(field_type, "max", None)

    if has_count and not is_array:
        _raise(
            f"Field '{field.name}': count constraint is allowed only on array references.",
            field,
        )

    if count_boundary and not has_count:
        _raise(
            f"Field '{field.name}': boundary on count requires a count range.",
            field,
        )

    if has_count:
        if min_count < 0 or max_count < 0:
            _raise(
                f"Field '{field.name}': count values must be >= 0.",
                field,
            )
        if min_count > max_count:
            _raise(
                f"Field '{field.name}': count minimum cannot be greater than maximum.",
                field,
            )

def _detect_circular_references(schema):
    graph = {}

    for entity in schema.entities:
        refs = []
        for field in entity.fields:
            if field.type.__class__.__name__ == "RefType":
                refs.append(field.type.entity.name)
        graph[entity.name] = refs

    visited = set()
    stack = set()
    warned_cycles = set()

    def dfs(node, path):
        if node in stack:
            cycle_start = path.index(node)
            cycle = tuple(path[cycle_start:] + [node])
            if cycle not in warned_cycles:
                warned_cycles.add(cycle)
                print(
                    f"Warning: circular reference detected: {' -> '.join(cycle)}"
                )
            return

        if node in visited:
            return

        visited.add(node)
        stack.add(node)

        for neighbor in graph.get(node, []):
            dfs(neighbor, path + [neighbor])

        stack.remove(node)

    for entity_name in graph:
        dfs(entity_name, [entity_name])


def _validate_entity_config(entity):
    config = getattr(entity, "config", None)
    if config is None:
        return

    seen_option_types = set()

    for option in getattr(config, "options", []):
        option_type = option.__class__.__name__

        if option_type in seen_option_types:
            _raise(
                f"Entity '{entity.name}': config option '{option_type}' can appear only once.",
                option,
            )
        seen_option_types.add(option_type)

        if option_type == "GenerateOption":
            if option.generate < 0:
                _raise(
                    f"Entity '{entity.name}': generate must be >= 0.",
                    option,
                )

        elif option_type == "IncludeOption":
            field_names = {field.name for field in entity.fields}
            for test_case in option.include:
                assigned_names = set()
                for assignment in test_case.assignments:
                    if assignment.name not in field_names:
                        _raise(
                            f"Entity '{entity.name}': include references unknown field '{assignment.name}'.",
                            assignment,
                        )
                    if assignment.name in assigned_names:
                        _raise(
                            f"Entity '{entity.name}': duplicate assignment '{assignment.name}' in include test case.",
                            assignment,
                        )
                    assigned_names.add(assignment.name)


def _validate_model(model, _metamodel):
    schemas = [model] if hasattr(model, "entities") else getattr(model, "schemas", [])

    for schema in schemas:
        for entity in schema.entities:
            field_names = set()
            for field in entity.fields:
                if field.name in field_names:
                    _raise(
                        f"Entity '{entity.name}': duplicate field '{field.name}'.",
                        field,
                    )
                field_names.add(field.name)
                _validate_field(field)

            _validate_entity_config(entity)

        _detect_circular_references(schema)


def get_metamodel():
    global _METAMODEL
    if _METAMODEL is None:
        _METAMODEL = metamodel_from_file(str(GRAMMAR_PATH))
        _METAMODEL.register_model_processor(_validate_model)
    return _METAMODEL


def load_model(path):
    mm = get_metamodel()
    return mm.model_from_file(str(path))


def load_model_from_str(model_str):
    mm = get_metamodel()
    return mm.model_from_str(model_str)