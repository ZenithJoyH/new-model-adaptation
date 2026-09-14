"""Shared, offline contract for formal accuracy acceptance (stdlib only)."""

import math


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
    if type(cfg.get("expected_samples")) is not int or cfg["expected_samples"] < 1:
        errors.append("formal acceptance requires positive expected_samples")
    if cfg.get("allow_timeouts") is not True:
        errors.append("formal acceptance requires allow_timeouts=true so timeout samples count as incorrect")
    tasks = cfg.get("tasks")
    criteria = cfg.get("acceptance_criteria")
    if not isinstance(tasks, list) or not tasks or not all(isinstance(t, str) and t for t in tasks):
        errors.append("formal acceptance requires an explicit tasks list")
        return errors
    if len(set(tasks)) != len(tasks):
        errors.append("tasks must not contain duplicates")
    if not isinstance(criteria, dict) or set(criteria) != set(tasks):
        errors.append("acceptance_criteria must specify exactly one criterion per task")
        return errors
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
