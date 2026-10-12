#!/usr/bin/env python3
"""Cooperative human/agent handoff. Never executes commands or changes services."""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

import yaml

from framework_workspace import (FRAMEWORK_ID_RE, WORKFLOW_PHASES, load_yaml,
                                 pin_profile, resolved_profile, workspace_profile)

ROOT = Path(__file__).resolve().parents[1]
CHANGES = {"none", "documentation", "service", "code", "environment", "model", "plan", "evidence"}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def snapshot(directory, cfg):
    model = directory.parents[2]
    paths = {model / "model.yml", model / "architecture-and-inference.md"}
    for item in cfg["workflow"].values():
        for record in [item.get("verification", {}), *item.get("records", {}).values()]:
            if record.get("evidence"):
                path = (directory / record["evidence"]).resolve()
                if not path.is_relative_to(model.resolve()):
                    raise ValueError("local evidence escapes the model workspace")
                paths.add(path)
    return {"identity": {k: copy.deepcopy(cfg.get(k)) for k in
            ("target", "workspace", "deployment", "acceptance_plan", "profile_sha256", "evidence_contract")},
            "workflow": copy.deepcopy(cfg["workflow"]),
            "files": {str(p): fingerprint(p) for p in sorted(paths)}}


def ordered_stages(cfg):
    return [*WORKFLOW_PHASES[:3], *cfg["workflow"]["acceptance"]["substeps"], "acceptance", "retrospective"]


def invalidate(cfg, first, event):
    stages = ordered_stages(cfg)
    affected = stages[stages.index(first):]
    retired = {}
    for stage in affected:
        if stage in WORKFLOW_PHASES:
            item = cfg["workflow"][stage]
            retired[stage] = {k: copy.deepcopy(v) for k, v in item.items() if k not in {"substeps", "records"}}
            item.update(status="not_started", verification={}, last_verified=None,
                        blocker="人工变更后待复核: " + event["id"])
        else:
            acceptance = cfg["workflow"]["acceptance"]
            retired[stage] = {"status": acceptance["substeps"][stage],
                              "verification": acceptance.get("records", {}).pop(stage, {})}
            acceptance["substeps"][stage] = "not_started"
    event.update(revalidate=affected, previous_status=cfg["status"], retired_records=retired)
    # Overall status must never continue to advertise an invalidated pass.
    cfg.update(status="blocked", blocker="人工变更后待复核: " + ", ".join(affected), validated_hosts=[])


def status(directory, cfg):
    control = cfg.get("control", {})
    return {"mode": control.get("mode", "agent"), "operator": control.get("operator"),
            "note": control.get("note"), "model": cfg["model"], "platform": cfg["platform"],
            "framework": cfg["framework"], "hosts": cfg.get("target", {}).get("hosts", []),
            "container": cfg.get("target", {}).get("container_name"),
            "deployment": cfg.get("deployment", {}),
            "workspace_roots": cfg.get("workspace", {}).get("roots", []),
            "framework_file": str(directory / "framework.yml"),
            "stages": {s: (cfg["workflow"][s]["status"] if s in WORKFLOW_PHASES else
                            cfg["workflow"]["acceptance"]["substeps"][s]) for s in ordered_stages(cfg)},
            "last_event": ({k: v for k, v in control["history"][-1].items()
                            if k not in {"retired_records", "previous_contract", "before_handoff_workflow"}}
                           if control.get("history") else None),
            "process_note": "交接不会停止评测或服务；继续前核实仍在运行的任务，不重放启动命令。"}


def transition(directory, cfg, operation, *, actor, note, changes=(), evidence=None, root=ROOT, mounts=None):
    if not actor or not actor.strip() or not note or not note.strip():
        raise ValueError("--actor 和 --note 必填；简述操作人、现场状态与交接意图")
    control = cfg.setdefault("control", {"mode": "agent", "history": []})
    event = {"id": uuid.uuid4().hex, "at": datetime.now(timezone.utc).isoformat(),
             "operation": operation, "actor": actor, "note": note}
    if operation == "handoff":
        if control.get("mode", "agent") != "agent":
            raise ValueError("已有人工接管；先 status 查看当前交接")
        control.update(mode="human", operator=actor, note=note, snapshot=snapshot(directory, cfg))
    elif operation == "upgrade":
        if control.get("mode") != "human":
            raise ValueError("升级契约前先 handoff；不会自动迁移已有通过记录")
        _, profile = resolved_profile(root, cfg["framework"])
        if cfg["platform"] not in profile["platforms"]:
            raise ValueError("新契约不支持当前平台")
        event["previous_contract"] = {k: copy.deepcopy(cfg.get(k)) for k in
                                      ("evidence_contract", "profile_version", "profile_snapshot", "profile_sha256")}
        old_version = cfg.get("evidence_contract", 1)
        pin_profile(cfg, profile)
        # Clear old contract assertions before switching the step vocabulary.
        invalidate(cfg, "architecture" if old_version == 1 else "environment", event)
        old_steps = cfg["workflow"]["acceptance"]["substeps"]
        cfg["workflow"]["acceptance"]["substeps"] = {
            name: "not_started" for name, spec in profile["acceptance"]["steps"].items()
            if not spec.get("optional") or name in old_steps}
        control["snapshot"] = snapshot(directory, cfg)
    elif operation == "resume":
        if control.get("mode") != "human":
            raise ValueError("当前没有人工接管")
        changes = set(changes)
        if not changes or not changes <= CHANGES or ("none" in changes and len(changes) > 1):
            raise ValueError("明确 --change none/documentation/service/code/environment/model/plan/evidence，可重复")
        if changes - {"none", "documentation"} and not evidence:
            raise ValueError("实际变更需 --evidence 指向检查结果或变更说明的绝对文件路径")
        if evidence:
            proof = Path(evidence)
            if not proof.is_absolute() or not proof.is_file():
                raise ValueError("--evidence 必须是现有绝对文件路径")
            event["evidence"] = {"path": str(proof.resolve()), "sha256": fingerprint(proof)}
        before = control.get("snapshot")
        if not isinstance(before, dict):
            raise ValueError("接管快照缺失；不能推断人工变更范围")
        after = snapshot(directory, cfg)
        observed = [k for k, value in after["identity"].items() if before["identity"].get(k) != value]
        changed_files = [p for p in set(before["files"]) | set(after["files"])
                         if before["files"].get(p) != after["files"].get(p)]
        from framework_evidence import record_for, state, DONE, dependencies, verify_record
        previous = {"workflow": before["workflow"]}
        changed_records = [s for s in ordered_stages(cfg)
                           if record_for(previous, s) != record_for(cfg, s) or state(previous, s) != state(cfg, s)]
        if changes == {"none"} and (observed or changed_files or changed_records):
            raise ValueError("检测到文件或配置变化，不能声明 none；填写实际 --change")
        candidates = []
        candidates.extend(changed_records)
        basic = "execution-mode" if "execution-mode" in cfg["workflow"]["acceptance"]["substeps"] else "model-eager"
        mapping = {"model": "architecture", "environment": "environment", "code": "environment",
                   "service": basic}
        candidates.extend(mapping[c] for c in changes if c in mapping)
        if "plan" in changes and "acceptance_plan" not in observed:
            candidates.append(basic)
        if set(observed) & {"target", "workspace", "deployment", "profile_sha256", "evidence_contract"}:
            candidates.append("environment")
        if "acceptance_plan" in observed:
            old_plan = before["identity"].get("acceptance_plan") or {}
            new_plan = after["identity"].get("acceptance_plan") or {}
            fields = {k for k in set(old_plan) | set(new_plan) if old_plan.get(k) != new_plan.get(k)}
            candidates.append("performance" if fields <= {"performance_request_sha256", "performance_targets"}
                              else "accuracy" if fields <= {"accuracy_config_sha256"} else basic)
        model = directory.parents[2]
        if any(str(model / name) in changed_files for name in ("model.yml", "architecture-and-inference.md")):
            candidates.append("architecture")
        for stage in ordered_stages(cfg):
            record = (cfg["workflow"][stage].get("verification", {}) if stage in WORKFLOW_PHASES else
                      cfg["workflow"]["acceptance"].get("records", {}).get(stage, {}))
            if record.get("evidence") and str((directory / record["evidence"]).resolve()) in changed_files:
                candidates.append(stage)
        stages = ordered_stages(cfg)
        candidates = [c if c in stages else basic for c in candidates]
        candidate = copy.deepcopy(cfg)
        if candidates:
            invalidate(cfg, min(candidates, key=stages.index), event)
        if "evidence" in changes:
            if cfg.get("evidence_contract") != 2 or not mounts:
                raise ValueError("接纳人工结果需要 v2 契约及 --artifact-root HOST=/已核实可读根")
            profile = workspace_profile(root, cfg)
            accepted, rejected = [], {}
            for stage in event.get("revalidate", []):
                rec = record_for(candidate, stage)
                old = record_for(previous, stage)
                if state(candidate, stage) not in DONE or not rec:
                    continue
                if rec.get("run_id") == old.get("run_id"):
                    rejected[stage] = "仍为接管前的 run；需要本轮真实验证"
                    continue
                trial = copy.deepcopy(cfg)
                if stage in WORKFLOW_PHASES:
                    for key, value in candidate["workflow"][stage].items():
                        if key not in {"records", "substeps"}:
                            trial["workflow"][stage][key] = copy.deepcopy(value)
                else:
                    trial["workflow"]["acceptance"]["substeps"][stage] = state(candidate, stage)
                    trial["workflow"]["acceptance"].setdefault("records", {})[stage] = copy.deepcopy(rec)
                try:
                    for dep in dependencies(trial, profile, stage):
                        if state(trial, dep) not in DONE:
                            raise ValueError("前置待复核: " + dep)
                        verify_record(root, directory, trial, profile, dep, mounts)
                    verify_record(root, directory, trial, profile, stage, mounts)
                    cfg["workflow"] = trial["workflow"]
                    accepted.append(stage)
                except (ValueError, KeyError, TypeError, OSError, AttributeError, IndexError) as exc:
                    rejected[stage] = str(exc)
            event.update(accepted_manual_results=accepted, unaccepted_manual_results=rejected,
                         revalidate=[s for s in event.get("revalidate", []) if s not in accepted])
            if not event["revalidate"]:
                cfg.update(status=candidate["status"], blocker=candidate.get("blocker", ""))
            event["before_handoff_workflow"] = before["workflow"]
        event.update(changes=sorted(changes), observed_fields=observed, changed_files=changed_files)
        workspace_profile(root, cfg)  # Refuse malformed/tampered pinned contracts.
        control.update(mode="agent", operator=actor, note=note)
        control.pop("snapshot", None)
    else:
        raise ValueError("unknown operation")
    control.setdefault("history", []).append(event)
    return cfg


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["status", "handoff", "resume", "upgrade"])
    p.add_argument("model")
    p.add_argument("--platform", required=True)
    p.add_argument("--framework", required=True)
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--actor")
    p.add_argument("--note")
    p.add_argument("--change", action="append", choices=sorted(CHANGES), default=[])
    p.add_argument("--evidence")
    p.add_argument("--artifact-root", action="append", default=[], metavar="HOST=/readable/root")
    args = p.parse_args()
    try:
        root = args.repo_root.resolve()
        for value in (args.model.lower(), args.platform, args.framework):
            if not FRAMEWORK_ID_RE.fullmatch(value):
                raise ValueError("invalid workspace identity")
        directory = root / "models" / args.model / args.platform / "frameworks" / args.framework
        if directory.resolve() != directory or not directory.is_dir():
            raise ValueError("workspace must be an existing canonical directory")
        # Lock the stable directory inode, not the replaceable YAML inode.
        fd = os.open(directory, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = directory / "framework.yml"
            if path.is_symlink():
                raise ValueError("framework.yml must not be a symlink")
            cfg = load_yaml(path)
            if any(cfg[k] != getattr(args, k) for k in ("model", "platform", "framework")):
                raise ValueError("workspace identity mismatch")
            if args.operation != "status":
                mounts = {}
                for item in args.artifact_root:
                    host, sep, location = item.partition('=')
                    if not sep or not Path(location).is_absolute() or host in mounts:
                        raise ValueError("--artifact-root 必须为唯一 HOST=/绝对路径")
                    mounts[host] = location
                transition(directory, cfg, args.operation, actor=args.actor, note=args.note,
                           changes=args.change, evidence=args.evidence, root=root, mounts=mounts)
                with tempfile.NamedTemporaryFile("w", dir=directory, delete=False, encoding="utf-8") as stream:
                    temp = Path(stream.name)
                    try:
                        yaml.safe_dump(cfg, stream, allow_unicode=True, sort_keys=False)
                        stream.flush(); os.fsync(stream.fileno())
                        os.chmod(temp, path.stat().st_mode & 0o777)
                        os.replace(temp, path)
                    finally:
                        temp.unlink(missing_ok=True)
            print(json.dumps(status(directory, cfg), ensure_ascii=False, indent=2))
        finally:
            os.close(fd)
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError) as exc:
        print(json.dumps({"status": "incomplete", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
