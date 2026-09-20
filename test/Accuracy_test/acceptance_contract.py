"""Shared, offline contract for formal accuracy acceptance (stdlib only)."""

import math


def expected_samples_by_task(cfg, tasks=None):
    """Return the frozen full-run sample count for every task.

    A scalar remains supported for one-task historical configurations. Formal
    multi-task runs must name each task explicitly so one dataset's count cannot
    be silently reused for another dataset.
    """
    tasks = cfg.get("tasks") if tasks is None else tasks
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty list")
    expected = cfg.get("expected_samples")
    if type(expected) is int:
        if expected < 1:
            raise ValueError("expected_samples must be positive")
        if len(tasks) != 1:
            raise ValueError("multi-task formal acceptance requires expected_samples keyed by task")
        return {tasks[0]: expected}
    if not isinstance(expected, dict) or set(expected) != set(tasks):
        raise ValueError("expected_samples must specify exactly one positive count per task")
    if any(type(value) is not int or value < 1 for value in expected.values()):
        raise ValueError("expected_samples counts must be positive integers")
    return dict(expected)


def validate_formal_config(cfg, *, require_formal=False):
    if not isinstance(cfg, dict):
        return ["accuracy config must be a JSON object"]
    if "formal_acceptance" in cfg and type(cfg["formal_acceptance"]) is not bool:
        return ["formal_acceptance must be a JSON boolean"]
    if cfg.get("formal_acceptance") is not True:
        return ["formal_acceptance must be true for formal acceptance"] if require_formal else []
    errors = []
    if cfg.get("service_mode") != "graph":
        errors.append("formal acceptance requires service_mode=graph")
    if type(cfg.get("num_concurrent")) is not int or cfg["num_concurrent"] < 32:
        errors.append("formal acceptance requires num_concurrent >= 32")
    if type(cfg.get("limit")) is not int or cfg["limit"] != 0:
        errors.append("formal acceptance requires limit=0 (full dataset)")
    if cfg.get("allow_timeouts") is not True:
        errors.append("formal acceptance requires allow_timeouts=true so timeout samples count as incorrect")
    tasks = cfg.get("tasks")
    criteria = cfg.get("acceptance_criteria")
    if not isinstance(tasks, list) or not tasks or not all(isinstance(t, str) and t for t in tasks):
        errors.append("formal acceptance requires an explicit tasks list")
        return errors
    if len(set(tasks)) != len(tasks):
        errors.append("tasks must not contain duplicates")
    try:
        expected_samples_by_task(cfg, tasks)
    except ValueError as exc:
        errors.append(f"formal acceptance {exc}")
    if not isinstance(criteria, dict) or set(criteria) != set(tasks):
        errors.append("acceptance_criteria must specify exactly one criterion per task")
        return errors
    datasets = cfg.get("datasets")
    legacy_dataset = cfg.get("dataset_path")
    if datasets is not None and legacy_dataset:
        errors.append("use either datasets or legacy dataset_path fields, not both")
    if datasets is not None and not isinstance(datasets, dict):
        errors.append("datasets must be an object when provided")
    elif datasets:
        if set(datasets) != set(tasks):
            errors.append("datasets must specify exactly one dataset descriptor per task")
        else:
            for task, descriptor in datasets.items():
                if not isinstance(descriptor, dict):
                    errors.append(f"{task}: dataset descriptor must be an object")
                    continue
                if not isinstance(descriptor.get("path"), str) or not descriptor["path"].strip():
                    errors.append(f"{task}: dataset path must be a non-empty string")
                if descriptor.get("name") is not None and not isinstance(descriptor.get("name"), str):
                    errors.append(f"{task}: dataset name must be a string or null")
                if not isinstance(descriptor.get("split", "train"), str) or not descriptor.get("split", "train").strip():
                    errors.append(f"{task}: dataset split must be a non-empty string")
    elif legacy_dataset and len(tasks) != 1:
        errors.append("legacy dataset_path fields support only one task; use datasets for multi-task runs")
    for task in tasks:
        item = criteria[task]
        if not isinstance(item, dict) or not isinstance(item.get("metric"), str) or not item["metric"]:
            errors.append(f"{task}: specify the exact result metric key")
            continue
        value = item.get("minimum")
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            errors.append(f"{task}: minimum must be a finite accuracy fraction in [0, 1]")
    return errors


def metric_errors(cfg, task, metrics):
    if cfg.get("formal_acceptance") is not True:
        return []
    errors = validate_formal_config(cfg, require_formal=True)
    if errors:
        return errors
    criterion = cfg["acceptance_criteria"][task]
    value = metrics.get(criterion["metric"])
    if type(value) not in (int, float) or not math.isfinite(value):
        return [f"{task}: missing or non-finite metric {criterion['metric']}"]
    if not 0 <= value <= 1 or value < criterion["minimum"]:
        return [f"{task}: accuracy {value} does not meet minimum {criterion['minimum']}"]
    return []
