#!/usr/bin/env python3
"""Create one explicit model/platform/framework adaptation workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

from adapt_model import MODEL_NAME_RE, PLATFORMS
from framework_workspace import FRAMEWORK_ID_RE, load_yaml, resolved_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("model")
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("framework")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    if not MODEL_NAME_RE.fullmatch(args.model) or args.model.startswith("_"):
        raise ValueError("模型名只能包含字母、数字、点、下划线和连字符")
    if not FRAMEWORK_ID_RE.fullmatch(args.framework):
        raise ValueError("framework ID 只能使用小写字母、数字、点、下划线和连字符")
    model_dir = root / "models" / args.model
    platform_dir = model_dir / args.platform
    if not (model_dir / "model.yml").is_file():
        raise ValueError(f"模型目录不存在或缺少 model.yml: {model_dir}")
    if not (platform_dir / "platform.yml").is_file():
        raise ValueError(f"平台目录不存在或缺少 platform.yml: {platform_dir}")
    _, profile = resolved_profile(root, args.framework)
    if args.platform not in profile["platforms"]:
        raise ValueError(f"{args.framework} 不支持平台 {args.platform}")
    target = platform_dir / "frameworks" / args.framework
    if target.exists():
        raise ValueError(f"拒绝覆盖已有 framework 工作区: {target}")
    platform_config_path = platform_dir / "platform.yml"
    platform_config = load_yaml(platform_config_path)
    frameworks = platform_config.setdefault("frameworks", {})
    if not isinstance(frameworks, dict):
        raise ValueError(f"platform.yml 的 frameworks 必须是映射: {platform_config_path}")
    if args.framework in frameworks:
        raise ValueError(f"platform.yml 已登记 framework: {args.framework}")
    template = root / "templates" / "framework-workspace"
    if not template.is_dir():
        raise ValueError(f"缺少 framework 工作区模板: {template}")
    target.parent.mkdir(parents=True, exist_ok=True)
    index = target.parent / "README.md"
    if not index.exists():
        index.write_text(
            "# Framework adaptations\n\n"
            "每个子目录对应一个模型、平台和 framework profile 的独立适配记录。"
            "不要在不同 framework 之间共享状态、远端工作根或启动脚本。\n",
            encoding="utf-8",
        )
    shutil.copytree(template, target)
    config_path = target / "framework.yml"
    config = load_yaml(config_path)
    config.update({
        "model": args.model,
        "platform": args.platform,
        "framework": args.framework,
        "profile": f"framework-profiles/{args.framework}/profile.yml",
        "profile_version": profile["profile_version"],
    })
    config["workflow"]["acceptance"]["substeps"] = {
        name: "not_started" for name, spec in profile["acceptance"]["steps"].items()
        if not spec.get("optional", False)
    }
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    frameworks[args.framework] = {
        "workspace": f"frameworks/{args.framework}/framework.yml",
        "profile": f"framework-profiles/{args.framework}/profile.yml",
    }
    platform_config_path.write_text(
        yaml.safe_dump(platform_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Created framework workspace: {target}")
    print(f"Profile: framework-profiles/{args.framework}/profile.yml")
    print("Next: record exact hosts and the framework-specific remote root in environment/README.md.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Error: {exc}")
        raise SystemExit(2)
