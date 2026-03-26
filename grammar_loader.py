from pathlib import Path
import warnings

from textx import metamodel_from_file
from validation import (
    ValidationError,
    MissingRequiredValueError,
    InvalidRangeError,
    InvalidEnumError,
    InvalidGenerateCountError,
    InvalidPrecisionError,
    InvalidIncludeFieldError,
    InvalidIncludeValueError,
    InvalidPartitionsError,
)

GRAMMAR_PATH = Path("testdatagen/grammar/testdatagen.tx")

_METAMODEL = None

RANGE_TYPES = {"number", "date", "datetime"}
PRECISION_TYPES = {"number"}
PARTITION_TYPES = {"number", "date", "datetime"}
STRING_LIKE_TYPES = {
    "uuid",
    "email",
    "fullName",
    "firstName",
    "lastName",
    "date",
    "datetime",
    "string",
    "productName",
    "companyName",
    "address",
    "city",
    "country",
    "phone",
    "url",
}
COVERAGE_MIN = 0
COVERAGE_MAX = 100
MIN_PARTITIONS_COUNT = 1
MAX_PARTITIONS_COUNT = 10


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


def _validate_required_schema(schema):
    if not getattr(schema, "name", None):
        raise MissingRequiredValueError("Schema must have a name.", schema)

    entities = getattr(schema, "entities", [])
    if not entities:
        raise MissingRequiredValueError(
            f"Schema '{schema.name}' must define at least one entity.",
            schema,
        )


def _validate_required_entity(entity):
    if not getattr(entity, "name", None):
        raise MissingRequiredValueError("Entity must have a name.", entity)

    fields = getattr(entity, "fields", [])
    if not fields:
        raise MissingRequiredValueError(
            f"Entity '{entity.name}' must define at least one field.",
            entity,
        )


def _validate_required_field(field):
    if not getattr(field, "name", None):
        raise MissingRequiredValueError("Field must have a name.", field)

    if not getattr(field, "type", None):
        raise MissingRequiredValueError(
            f"Field '{field.name}' must define a type.",
            field,
        )


def _validate_enum_type(enum_type):
    values = getattr(enum_type, "values", [])
    if not values:
        raise InvalidEnumError(
            "Enum type must define at least one value.",
            enum_type,
        )


def _validate_range_constraint(field, constraint, field_type_name):
    if field_type_name not in RANGE_TYPES:
        raise InvalidRangeError(
            f"Field '{field.name}': range is allowed only for number, date, or datetime fields.",
            constraint,
        )

    min_value = constraint.min
    max_value = constraint.max

    if field_type_name == "number":
        if not isinstance(min_value, (int, float)) or not isinstance(max_value, (int, float)):
            raise InvalidRangeError(
                f"Field '{field.name}': number range must use numeric values.",
                constraint,
            )
    else:
        if not isinstance(min_value, str) or not isinstance(max_value, str):
            raise InvalidRangeError(
                f"Field '{field.name}': date/datetime range must use quoted string values.",
                constraint,
            )

    if min_value >= max_value:
        raise InvalidRangeError(
            f"Field '{field.name}': invalid range ({min_value}..{max_value}); min must be less than max.",
            constraint,
        )


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
        raise ValidationError(
            f"Field '{field.name}': count is allowed only on array references (ref Entity[]).",
            field,
        )

    if count_boundary and not has_count:
        raise ValidationError(
            f"Field '{field.name}': boundary on count requires a count range.",
            field,
        )

    if has_count:
        if min_count < 0 or max_count < 0:
            raise ValidationError(
                f"Field '{field.name}': count values must be >= 0.",
                field,
            )
        if min_count >= max_count:
            raise ValidationError(
                f"Field '{field.name}': invalid count range ({min_count}..{max_count}); min must be less than max.",
                field,
            )


def _validate_field(field):
    _validate_required_field(field)

    field_type_name = _field_type_name(field.type)

    if field.type.__class__.__name__ == "RefType":
        _validate_ref_type(field)

    if field.type.__class__.__name__ == "EnumType":
        _validate_enum_type(field.type)

    constraints = getattr(field, "constraints", []) or []
    names = [_constraint_name(c) for c in constraints]

    if names.count("PartitionConstraint") > 1:
        raise InvalidPartitionsError(
            f"Field '{field.name}': partition can be defined only once.",
            field,
        )

    if names.count("PartitionsConstraint") > 1:
        raise InvalidPartitionsError(
            f"Field '{field.name}': partitions can be defined only once.",
            field,
        )

    if "PartitionConstraint" in names and "PartitionsConstraint" in names:
        raise InvalidPartitionsError(
            f"Field '{field.name}': partition and partitions cannot be used together.",
            field,
        )

    for constraint in constraints:
        cname = _constraint_name(constraint)

        if cname == "RangeConstraint":
            _validate_range_constraint(field, constraint, field_type_name)

        elif cname == "PrecisionConstraint":
            if field_type_name not in PRECISION_TYPES:
                raise InvalidPrecisionError(
                    f"Field '{field.name}': precision is valid only for number fields.",
                    constraint,
                )
            if constraint.value < 0:
                raise InvalidPrecisionError(
                    f"Field '{field.name}': precision must be >= 0.",
                    constraint,
                )

        elif cname in {"PartitionConstraint", "PartitionsConstraint", "BoundaryConstraint"}:
            if field_type_name not in PARTITION_TYPES:
                raise InvalidPartitionsError(
                    f"Field '{field.name}': {cname} is allowed only for number/date/datetime fields.",
                    constraint,
                )

            if cname == "PartitionConstraint":
                if constraint.value <= 0:
                    raise InvalidPartitionsError(
                        f"Field '{field.name}': partition value must be > 0.",
                        constraint,
                    )
                if constraint.value > MAX_PARTITIONS_COUNT:
                    raise InvalidPartitionsError(
                        f"Field '{field.name}': partition count must be between 1 and 10.",
                        constraint,
                    )

            if cname == "PartitionsConstraint":
                values = getattr(constraint, "values", [])
                if not values:
                    raise InvalidPartitionsError(
                        f"Field '{field.name}': partitions must contain at least one value.",
                        constraint,
                    )

                if not (MIN_PARTITIONS_COUNT <= len(values) <= MAX_PARTITIONS_COUNT):
                    raise InvalidPartitionsError(
                        f"Field '{field.name}': partitions count must be between 1 and 10, got {len(values)}.",
                        constraint,
                    )

                if any(v <= 0 for v in values):
                    raise InvalidPartitionsError(
                        f"Field '{field.name}': all partition values must be > 0.",
                        constraint,
                    )

        elif cname == "CoverageConstraint":
            if not (COVERAGE_MIN <= constraint.value <= COVERAGE_MAX):
                raise ValidationError(
                    f"Field '{field.name}': coverage must be between 0 and 100.",
                    constraint,
                )

        elif cname == "SpecialConstraint":
            if not constraint.values:
                raise ValidationError(
                    f"Field '{field.name}': special must contain at least one value.",
                    constraint,
                )

        elif cname == "IncludeConstraint":
            values = list(constraint.values)
            if len(set(values)) != len(values):
                raise ValidationError(
                    f"Field '{field.name}': include cannot contain duplicate values.",
                    constraint,
                )


def _is_null_value(value):
    return value == "null"


def _validate_assignment_value_against_field(field, assignment):
    field_type = field.type
    field_type_name = _field_type_name(field_type)
    value = assignment.value

    if _is_null_value(value):
        return

    if field_type_name == "number":
        if not isinstance(value, (int, float)):
            raise InvalidIncludeValueError(
                f"Include value for field '{field.name}' must be a number, got {value!r}.",
                assignment,
            )

    elif field_type_name == "boolean":
        if not isinstance(value, bool):
            raise InvalidIncludeValueError(
                f"Include value for field '{field.name}' must be boolean, got {value!r}.",
                assignment,
            )

    elif field_type_name in STRING_LIKE_TYPES:
        if not isinstance(value, str):
            raise InvalidIncludeValueError(
                f"Include value for field '{field.name}' must be a string, got {value!r}.",
                assignment,
            )

    elif field_type_name == "enum":
        if not isinstance(value, str):
            raise InvalidIncludeValueError(
                f"Include value for enum field '{field.name}' must be a string, got {value!r}.",
                assignment,
            )

        allowed = set(field_type.values)
        if value not in allowed:
            raise InvalidIncludeValueError(
                f"Include value for enum field '{field.name}' must be one of {sorted(allowed)}, got {value!r}.",
                assignment,
            )

    elif field_type_name == "ref":
        if not isinstance(value, str):
            raise InvalidIncludeValueError(
                f"Include value for ref field '{field.name}' must be a string identifier or null, got {value!r}.",
                assignment,
            )


def _validate_entity_config(entity):
    config = getattr(entity, "config", None)
    if config is None:
        return

    field_names = {field.name for field in entity.fields}
    field_by_name = {field.name: field for field in entity.fields}
    seen_option_types = set()

    for option in getattr(config, "options", []):
        option_type = option.__class__.__name__

        if option_type in seen_option_types:
            raise ValidationError(
                f"Entity '{entity.name}': config option '{option_type}' can appear only once.",
                option,
            )
        seen_option_types.add(option_type)

        if option_type == "GenerateOption":
            if option.generate <= 0:
                raise InvalidGenerateCountError(
                    f"Entity '{entity.name}': generate must be a positive integer.",
                    option,
                )

        elif option_type == "IncludeOption":
            for test_case in option.include:
                assigned_names = set()
                for assignment in test_case.assignments:
                    if assignment.name not in field_names:
                        raise InvalidIncludeFieldError(
                            f"Entity '{entity.name}': include references unknown field '{assignment.name}'.",
                            assignment,
                        )

                    if assignment.name in assigned_names:
                        raise InvalidIncludeFieldError(
                            f"Entity '{entity.name}': duplicate assignment '{assignment.name}' in include test case.",
                            assignment,
                        )

                    assigned_names.add(assignment.name)

                    field = field_by_name[assignment.name]
                    _validate_assignment_value_against_field(field, assignment)


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
                warnings.warn(
                    f"Circular reference detected: {' -> '.join(cycle)}",
                    UserWarning,
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


def _validate_model(model, _metamodel):
    schemas = [model] if hasattr(model, "entities") else getattr(model, "schemas", [])

    for schema in schemas:
        _validate_required_schema(schema)

        for entity in schema.entities:
            _validate_required_entity(entity)

            field_names = set()
            for field in entity.fields:
                if field.name in field_names:
                    raise ValidationError(
                        f"Entity '{entity.name}': duplicate field '{field.name}'.",
                        field,
                    )
                field_names.add(field.name)
                _validate_field(field)

            _validate_entity_config(entity)

        _detect_circular_references(schema)


def _noop_processor(_obj):
    return


def get_metamodel():
    global _METAMODEL

    if _METAMODEL is None:
        mm = metamodel_from_file(str(GRAMMAR_PATH))
        mm.register_model_processor(_validate_model)
        mm.register_obj_processors({
            "Schema": _noop_processor,
            "Entity": _noop_processor,
            "Field": _noop_processor,
            "EnumType": _noop_processor,
            "GenerateOption": _noop_processor,
            "IncludeOption": _noop_processor,
        })

        _METAMODEL = mm

    return _METAMODEL


def load_model(path):
    return get_metamodel().model_from_file(str(path))


def load_model_from_str(model_str):
    return get_metamodel().model_from_str(model_str)
