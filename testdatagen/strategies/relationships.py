import random as _random_module

def _one_to_one(
    relationship,
    from_rows,
    to_rows,
    prop_rows=None,
    generate=None,
    min_degree=None,
    max_degree=None,
    seed=None,
):
    limit = min(len(from_rows), len(to_rows))
    if generate is not None:
        limit = min(limit, generate)
    
    from_obj = getattr(relationship, "from_", getattr(relationship, "from", None))
    from_name = from_obj.name if from_obj else None
    prop_rows = prop_rows or []

    for i in range(limit):
        properties = prop_rows[i] if i < len(prop_rows) else {}
        yield {
            "from_label": from_name,
            "from_id": from_rows[i]["id"],
            "to_label": relationship.to.name,
            "to_id": to_rows[i]["id"],
            "type": relationship.name.upper(),
            "properties": properties,
        }


def _one_to_many(
    relationship,
    from_rows,
    to_rows,
    prop_rows=None,
    generate=None,
    min_degree=None,
    max_degree=None,
    seed=None,
):
    rng = _random_module.Random(seed)
    generated = 0
    prop_index = 0
    prop_rows = prop_rows or []

    min_degree = min_degree or 1
    max_degree = max_degree or len(to_rows)
    max_degree = min(max_degree, len(to_rows))

    for source in from_rows:
        degree = rng.randint(min_degree, max_degree)
        targets = rng.sample(to_rows, degree)

        for target in targets:
            if generate is not None and generated >= generate:
                return

            properties = prop_rows[prop_index] if prop_index < len(prop_rows) else {}
            prop_index += 1
            generated += 1

            from_obj = getattr(relationship, "from_", getattr(relationship, "from", None))
            from_name = from_obj.name if from_obj else None

            yield {
                "from_label": from_name,
                "from_id": source["id"],
                "to_label": relationship.to.name,
                "to_id": target["id"],
                "type": relationship.name.upper(),
                "properties": properties,
            }


def _many_to_one(
    relationship,
    from_rows,
    to_rows,
    prop_rows=None,
    generate=None,
    min_degree=None,
    max_degree=None,
    seed=None,
):
    rng = _random_module.Random(seed)
    limit = len(from_rows)
    if generate is not None:
        limit = min(limit, generate)
    
    prop_rows = prop_rows or []
    from_obj = getattr(relationship, "from_", getattr(relationship, "from", None))
    from_name = from_obj.name if from_obj else None

    for i, source in enumerate(from_rows[:limit]):
        properties = prop_rows[i] if i < len(prop_rows) else {}
        yield {
            "from_label": from_name,
            "from_id": source["id"],
            "to_label": relationship.to.name,
            "to_id": rng.choice(to_rows)["id"],
            "type": relationship.name.upper(),
            "properties": properties,
        }


def _many_to_many(
    relationship,
    from_rows,
    to_rows,
    prop_rows=None,
    generate=None,
    min_degree=None,
    max_degree=None,
    seed=None,
):
    rng = _random_module.Random(seed)
    generated = 0
    prop_index = 0
    prop_rows = prop_rows or []

    min_degree = min_degree or 1
    max_degree = max_degree or len(to_rows)
    max_degree = min(max_degree, len(to_rows))

    for source in from_rows:
        degree = rng.randint(min_degree, max_degree)
        targets = rng.sample(to_rows, degree)

        for target in targets:
            if generate is not None and generated >= generate:
                return

            properties = prop_rows[prop_index] if prop_index < len(prop_rows) else {}
            prop_index += 1
            generated += 1

            from_obj = getattr(relationship, "from_", getattr(relationship, "from", None))
            from_name = from_obj.name if from_obj else None

            yield {
                "from_label": from_name,
                "from_id": source["id"],
                "to_label": relationship.to.name,
                "to_id": target["id"],
                "type": relationship.name.upper(),
                "properties": properties,
            }
