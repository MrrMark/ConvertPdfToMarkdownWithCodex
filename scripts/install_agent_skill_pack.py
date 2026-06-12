#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Sequence


SKILL_NAME = "pdf2md-rag-ingest"
SKILL_SOURCE = Path("agent-pack") / "skills" / SKILL_NAME
CURSOR_RULE_SOURCE = Path("agent-adapters") / "cursor" / f"{SKILL_NAME}.mdc"
CONTINUE_RULE_SOURCE = Path("agent-adapters") / "continue" / f"{SKILL_NAME}.md"
SKILL_CLIENTS = {"agents", "claude", "cline", "roo"}
RULE_CLIENTS = {"cursor", "continue"}
ALL_CLIENTS = tuple(sorted(SKILL_CLIENTS | RULE_CLIENTS))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.resolve()
    clients = expand_clients(args.clients)
    installed: list[tuple[str, Path]] = []
    for client in clients:
        target = target_for_client(client, root, args.scope)
        source = source_for_client(client, root)
        install_path(source, target, mode=args.mode, overwrite=args.overwrite, dry_run=args.dry_run)
        installed.append((client, target))
    for client, target in installed:
        prefix = "would install" if args.dry_run else "installed"
        print(f"{prefix} {client}: {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the portable pdf2md agent skill/rule pack for local agents.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--clients",
        default="agents",
        help=f"Comma-separated clients: {', '.join(ALL_CLIENTS)}, or all.",
    )
    parser.add_argument("--scope", choices=("project", "global"), default="project")
    parser.add_argument("--mode", choices=("copy", "symlink"), default="copy")
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    return parser


def expand_clients(raw: str) -> list[str]:
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    if not requested:
        raise SystemExit("--clients must not be empty")
    if "all" in requested:
        return list(ALL_CLIENTS)
    unknown = sorted(set(requested) - set(ALL_CLIENTS))
    if unknown:
        raise SystemExit(f"Unknown clients: {', '.join(unknown)}")
    return requested


def source_for_client(client: str, root: Path) -> Path:
    if client in SKILL_CLIENTS:
        return root / SKILL_SOURCE
    if client == "cursor":
        return root / CURSOR_RULE_SOURCE
    if client == "continue":
        return root / CONTINUE_RULE_SOURCE
    raise ValueError(f"Unknown client: {client}")


def target_for_client(client: str, root: Path, scope: str) -> Path:
    base = Path.home() if scope == "global" else root
    if client == "agents":
        return base / ".agents" / "skills" / SKILL_NAME
    if client == "claude":
        return base / ".claude" / "skills" / SKILL_NAME
    if client == "cline":
        return base / ".cline" / "skills" / SKILL_NAME
    if client == "roo":
        return base / ".roo" / "skills" / SKILL_NAME
    if client == "cursor":
        if scope == "global":
            raise SystemExit("Cursor adapter currently supports project scope only.")
        return root / ".cursor" / "rules" / f"{SKILL_NAME}.mdc"
    if client == "continue":
        if scope == "global":
            raise SystemExit("Continue adapter currently supports project scope only.")
        return root / ".continue" / "rules" / f"{SKILL_NAME}.md"
    raise ValueError(f"Unknown client: {client}")


def install_path(source: Path, target: Path, *, mode: str, overwrite: bool, dry_run: bool) -> None:
    if not source.exists():
        raise SystemExit(f"Source does not exist: {source}")
    if target.exists() or target.is_symlink():
        if not overwrite:
            raise SystemExit(f"Target already exists: {target}. Use --overwrite to replace it.")
        if dry_run:
            return
        remove_target(target)
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        target.symlink_to(source.resolve(), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def remove_target(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


if __name__ == "__main__":
    raise SystemExit(main())
