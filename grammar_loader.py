from textx import metamodel_from_file, get_location
from textx.exceptions import TextXSemanticError

DATE_LIKE_TYPES = {"date", "datetime"}
RANGE_TYPES = {"number", "date", "datetime"}
PRECISION_TYPES = {"number"}
PARTITION_TYPES = {"number", "date", "datetime"}
COVERAGE_MIN = 0
COVERAGE_MAX = 100


def _field_type_name(field_type):
    if hasattr(field_type, "name"):
        return field_type.name
    if field_type.__class__.__name__ == "EnumType":
        return "enum"
    return type(field_type).__name__


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


def get_metamodel():
    mm = metamodel_from_file("testdatagen\\grammar\\testdatagen.tx")
    mm.register_model_processor(_validate_model)
    return mm


def load_model(path):
    mm = get_metamodel()
    return mm.model_from_file(str(path))


def load_model_from_str(model_str):
    mm = get_metamodel()
    return mm.model_from_str(model_str)