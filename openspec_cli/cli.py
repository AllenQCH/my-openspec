from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    OpenSpecError,
    archive_initiative,
    archive_readiness,
    bind_service,
    collect_project_result,
    init_initiative,
    init_project,
    initiative_completeness,
    json_output,
    new_investigation,
    project_readiness,
    promote_investigation,
    search_history,
    set_initiative_status,
    validate_workspace,
)


def root_from(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else Path(__file__).resolve().parent.parent


def parse_checkouts(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise OpenSpecError(f"Invalid --checkout {value!r}; expected serviceKey=/absolute/path")
        service_key, raw_path = value.split("=", 1)
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise OpenSpecError(f"Checkout path must be absolute: {raw_path}")
        result[service_key] = path.resolve()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openspec", description="Project-scoped OpenSpec coordination and archive CLI")
    parser.add_argument("--root", help="OpenSpec workspace root; defaults to this repository")
    commands = parser.add_subparsers(dest="command", required=True)

    command = commands.add_parser("init-project")
    command.add_argument("project_key")
    command.add_argument("display_name")
    command.add_argument("environment")

    command = commands.add_parser("init-initiative")
    command.add_argument("initiative_key")
    command.add_argument("demand_id")
    command.add_argument("demand_title")
    command.add_argument("environment")
    command.add_argument("--project", action="append", required=True)

    command = commands.add_parser("bind-service")
    command.add_argument("initiative_key")
    command.add_argument("project_key")
    command.add_argument("service_key")
    command.add_argument("repo_url")
    command.add_argument("openspec_path")
    command.add_argument("branch")

    command = commands.add_parser("collect-project-result")
    command.add_argument("initiative_key")
    command.add_argument("project_key")
    command.add_argument("service_key")
    command.add_argument("commit_sha")
    command.add_argument("--status", choices=["validated", "completed"], default="completed")
    command.add_argument("--test-evidence", action="append", default=[])
    command.add_argument("--delivery-evidence", action="append", default=[])

    command = commands.add_parser("set-initiative-status")
    command.add_argument("initiative_key")
    command.add_argument("status")

    command = commands.add_parser("check-project-ready")
    command.add_argument("initiative_key")
    command.add_argument("project_key")

    command = commands.add_parser("check-initiative-complete")
    command.add_argument("initiative_key")

    command = commands.add_parser("check-archive-ready")
    command.add_argument("initiative_key")

    command = commands.add_parser("new-investigation")
    command.add_argument("title")
    command.add_argument("environment")
    command.add_argument("--project")

    command = commands.add_parser("promote-investigation")
    command.add_argument("investigation_id")
    command.add_argument("initiative_key")
    command.add_argument("demand_id")
    command.add_argument("demand_title")
    command.add_argument("environment")
    command.add_argument("--project", action="append", required=True)

    command = commands.add_parser("archive-initiative")
    command.add_argument("initiative_key")
    command.add_argument("--revision")
    command.add_argument("--checkout", action="append", default=[], help="serviceKey=/absolute/repository/path")

    command = commands.add_parser("search-history")
    command.add_argument("--project")
    command.add_argument("--service")

    commands.add_parser("validate-workspace")
    return parser


def dispatch(args: argparse.Namespace) -> object:
    root = root_from(args.root)
    command = args.command
    if command == "init-project":
        return init_project(root, args.project_key, args.display_name, args.environment)
    if command == "init-initiative":
        return init_initiative(root, args.initiative_key, args.demand_id, args.demand_title, args.environment, args.project)
    if command == "bind-service":
        return bind_service(
            root, args.initiative_key, args.project_key, args.service_key, args.repo_url, args.openspec_path, args.branch
        )
    if command == "collect-project-result":
        return collect_project_result(
            root,
            args.initiative_key,
            args.project_key,
            args.service_key,
            args.commit_sha,
            args.status,
            args.test_evidence,
            args.delivery_evidence,
        )
    if command == "set-initiative-status":
        return set_initiative_status(root, args.initiative_key, args.status)
    if command == "check-project-ready":
        return project_readiness(root, args.initiative_key, args.project_key)
    if command == "check-initiative-complete":
        return initiative_completeness(root, args.initiative_key)
    if command == "check-archive-ready":
        return archive_readiness(root, args.initiative_key)
    if command == "new-investigation":
        return new_investigation(root, args.title, args.environment, args.project)
    if command == "promote-investigation":
        return promote_investigation(
            root,
            args.investigation_id,
            args.initiative_key,
            args.demand_id,
            args.demand_title,
            args.environment,
            args.project,
        )
    if command == "archive-initiative":
        return archive_initiative(root, args.initiative_key, parse_checkouts(args.checkout), args.revision)
    if command == "search-history":
        return {"results": search_history(root, args.project, args.service)}
    if command == "validate-workspace":
        return validate_workspace(root)
    raise OpenSpecError(f"Unsupported command: {command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        print(json_output(dispatch(args)))
        return 0
    except OpenSpecError as exc:
        print(json_output({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
