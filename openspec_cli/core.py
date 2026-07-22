from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


SCHEMA_VERSION = 1
PROJECT_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SERVICE_KEY_RE = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9._-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
ENVIRONMENTS = {"cn", "intl", "shared"}
INITIATIVE_STATUSES = {
    "draft",
    "active",
    "implementing",
    "delivered",
    "validating",
    "completed",
    "archived",
    "blocked",
    "cancelled",
}
BINDING_STATUSES = {"planned", "implementing", "testing", "delivered", "validated", "completed", "blocked"}
INVESTIGATION_STATUSES = {"new", "analyzing", "resolved", "promoted", "blocked", "archived"}


class OpenSpecError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def require_component(value: str, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise OpenSpecError(f"Invalid {label}: {value!r}")
    if pattern and not pattern.fullmatch(value):
        raise OpenSpecError(f"Invalid {label}: {value!r}")
    return value


def require_environment(value: str) -> str:
    if value not in ENVIRONMENTS:
        raise OpenSpecError(f"Invalid environment {value!r}; expected one of {sorted(ENVIRONMENTS)}")
    return value


def require_relative_path(value: str, label: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise OpenSpecError(f"Invalid {label}: {value!r}; expected a repository-relative path")
    return path.as_posix()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OpenSpecError(f"Required file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OpenSpecError(f"Expected a YAML mapping: {path}")
    return data


def project_dir(root: Path, project_key: str) -> Path:
    return root / "projects" / require_component(project_key, "projectKey", PROJECT_KEY_RE)


def initiative_dir(root: Path, initiative_key: str) -> Path:
    return root / "initiatives" / "_shared" / require_component(initiative_key, "initiativeKey")


def binding_dir(root: Path, project_key: str, initiative_key: str) -> Path:
    return root / "initiatives" / require_component(project_key, "projectKey", PROJECT_KEY_RE) / require_component(
        initiative_key, "initiativeKey"
    )


def init_project(root: Path, project_key: str, display_name: str, environment: str) -> dict[str, Any]:
    require_component(project_key, "projectKey", PROJECT_KEY_RE)
    require_environment(environment)
    target = project_dir(root, project_key)
    if target.exists():
        raise OpenSpecError(f"Project already exists: {target}")
    standards = target / "standards"
    standards.mkdir(parents=True)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "objectType": "project",
        "projectKey": project_key,
        "displayName": display_name,
        "environment": environment,
        "status": "active",
        "standards": {"path": f"projects/{project_key}/standards", "version": 1},
        "repositories": [],
        "createdAt": now_iso(),
    }
    write_yaml(target / "project.yaml", payload)
    atomic_write_text(target / "README.md", f"# {display_name}\n\n项目标识：`{project_key}`。\n")
    templates = {
        "requirement.md": "# 需求规范\n\n记录本项目通用的需求边界、术语和验收口径。\n",
        "backend-design.md": "# 后端设计规范\n\n记录本项目通用的架构、接口、数据和兼容性规则。\n",
        "testing.md": "# 测试规范\n\n记录单元测试、本地闭环和测试环境验证要求。\n",
        "code-review.md": "# Code Review 规范\n\n记录项目适用的 CR 检查项。\n",
        "delivery.md": "# 交付规范\n\n记录权限 SQL、依赖包、提测材料和流水线要求。\n",
    }
    for name, content in templates.items():
        atomic_write_text(standards / name, content)
    return {"projectKey": project_key, "path": str(target.relative_to(root))}


def init_initiative(
    root: Path,
    initiative_key: str,
    demand_id: str,
    demand_title: str,
    environment: str,
    projects: Iterable[str],
) -> dict[str, Any]:
    require_component(initiative_key, "initiativeKey")
    require_component(demand_id, "demandId")
    require_environment(environment)
    project_keys = list(dict.fromkeys(projects))
    if not project_keys:
        raise OpenSpecError("At least one participating project is required")
    for key in project_keys:
        if not (project_dir(root, key) / "project.yaml").is_file():
            raise OpenSpecError(f"Unknown projectKey: {key}")
    target = initiative_dir(root, initiative_key)
    if target.exists():
        raise OpenSpecError(f"Initiative already exists: {target}")
    target.mkdir(parents=True)
    created_at = now_iso()
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "objectType": "initiative",
        "initiativeKey": initiative_key,
        "demandId": demand_id,
        "demandTitle": demand_title,
        "environment": environment,
        "status": "draft",
        "participatingProjects": project_keys,
        "projectDependencies": [],
        "sourceInvestigations": [],
        "createdAt": created_at,
        "updatedAt": created_at,
        "lastArchivedRevision": None,
    }
    write_yaml(target / "initiative.yaml", payload)
    write_yaml(
        target / "project-map.yaml",
        {"schemaVersion": SCHEMA_VERSION, "initiativeKey": initiative_key, "projects": project_keys, "dependencies": []},
    )
    atomic_write_text(target / "overview.md", f"# {demand_title}\n\n需求号：`{demand_id}`。\n")
    atomic_write_text(target / "closeout.md", "# Closeout\n\n当前状态：未完成。\n")
    for key in project_keys:
        bind_target = binding_dir(root, key, initiative_key)
        bind_target.mkdir(parents=True)
        write_yaml(
            bind_target / "binding.yaml",
            {
                "schemaVersion": SCHEMA_VERSION,
                "objectType": "initiative_project_binding",
                "initiativeRef": f"initiatives/_shared/{initiative_key}",
                "initiativeKey": initiative_key,
                "projectKey": key,
                "status": "planned",
                "standardsRef": f"projects/{key}/standards",
                "serviceBindings": [],
                "testEvidence": [],
                "deliveryEvidence": [],
                "updatedAt": created_at,
            },
        )
    return {"initiativeKey": initiative_key, "path": str(target.relative_to(root)), "projects": project_keys}


def bind_service(
    root: Path,
    initiative_key: str,
    project_key: str,
    service_key: str,
    repo_url: str,
    openspec_path: str,
    branch: str,
) -> dict[str, Any]:
    require_component(service_key, "serviceKey", SERVICE_KEY_RE)
    openspec_path = require_relative_path(openspec_path, "openSpecPath")
    path = binding_dir(root, project_key, initiative_key) / "binding.yaml"
    binding = load_yaml(path)
    services = binding.setdefault("serviceBindings", [])
    if any(item.get("serviceKey") == service_key for item in services):
        raise OpenSpecError(f"Service binding already exists: {service_key}")
    services.append(
        {
            "serviceKey": service_key,
            "repoUrl": repo_url,
            "openSpecPath": openspec_path,
            "branch": branch,
            "commitSha": None,
            "status": "planned",
            "snapshotSha256": None,
        }
    )
    binding["updatedAt"] = now_iso()
    write_yaml(path, binding)
    return {"initiativeKey": initiative_key, "projectKey": project_key, "serviceKey": service_key}


def collect_project_result(
    root: Path,
    initiative_key: str,
    project_key: str,
    service_key: str,
    commit_sha: str,
    status: str,
    test_evidence: Iterable[str],
    delivery_evidence: Iterable[str],
) -> dict[str, Any]:
    require_component(service_key, "serviceKey", SERVICE_KEY_RE)
    if not COMMIT_RE.fullmatch(commit_sha):
        raise OpenSpecError("commitSha must be a full 40- or 64-character lowercase hexadecimal object id")
    if status not in BINDING_STATUSES:
        raise OpenSpecError(f"Invalid binding status: {status}")
    path = binding_dir(root, project_key, initiative_key) / "binding.yaml"
    binding = load_yaml(path)
    service = next((item for item in binding.get("serviceBindings", []) if item.get("serviceKey") == service_key), None)
    if service is None:
        raise OpenSpecError(f"Service binding not found: {service_key}")
    service["commitSha"] = commit_sha
    service["status"] = status
    binding["status"] = status
    binding["testEvidence"] = list(dict.fromkeys([*binding.get("testEvidence", []), *test_evidence]))
    binding["deliveryEvidence"] = list(dict.fromkeys([*binding.get("deliveryEvidence", []), *delivery_evidence]))
    binding["updatedAt"] = now_iso()
    write_yaml(path, binding)
    return {"initiativeKey": initiative_key, "projectKey": project_key, "serviceKey": service_key, "status": status}


def set_initiative_status(root: Path, initiative_key: str, status: str) -> dict[str, Any]:
    if status not in INITIATIVE_STATUSES:
        raise OpenSpecError(f"Invalid initiative status: {status}")
    path = initiative_dir(root, initiative_key) / "initiative.yaml"
    payload = load_yaml(path)
    payload["status"] = status
    payload["updatedAt"] = now_iso()
    write_yaml(path, payload)
    return {"initiativeKey": initiative_key, "status": status}


def project_readiness(root: Path, initiative_key: str, project_key: str) -> dict[str, Any]:
    path = binding_dir(root, project_key, initiative_key) / "binding.yaml"
    binding = load_yaml(path)
    blockers: list[str] = []
    services = binding.get("serviceBindings") or []
    if not services:
        blockers.append("serviceBindings is empty")
    for service in services:
        key = service.get("serviceKey", "<unknown>")
        if service.get("status") not in {"validated", "completed"}:
            blockers.append(f"{key}: status must be validated or completed")
        if not COMMIT_RE.fullmatch(str(service.get("commitSha") or "")):
            blockers.append(f"{key}: final commitSha is missing or invalid")
    if not binding.get("testEvidence"):
        blockers.append("testEvidence is empty")
    if not binding.get("deliveryEvidence"):
        blockers.append("deliveryEvidence is empty")
    return {
        "ready": not blockers,
        "initiativeKey": initiative_key,
        "projectKey": project_key,
        "status": binding.get("status"),
        "blockers": blockers,
    }


def initiative_completeness(root: Path, initiative_key: str) -> dict[str, Any]:
    initiative = load_yaml(initiative_dir(root, initiative_key) / "initiative.yaml")
    projects = initiative.get("participatingProjects") or []
    results = [project_readiness(root, initiative_key, key) for key in projects]
    blockers = [f"{item['projectKey']}: {blocker}" for item in results for blocker in item["blockers"]]
    return {
        "complete": bool(projects) and not blockers,
        "initiativeKey": initiative_key,
        "status": initiative.get("status"),
        "projects": results,
        "blockers": blockers,
    }


def archive_readiness(root: Path, initiative_key: str) -> dict[str, Any]:
    result = initiative_completeness(root, initiative_key)
    blockers = list(result["blockers"])
    if result["status"] != "completed":
        blockers.append("initiative status must be completed")
    return {**result, "ready": not blockers, "blockers": blockers}


def new_investigation(root: Path, title: str, environment: str, project_key: str | None = None) -> dict[str, Any]:
    require_environment(environment)
    if project_key:
        require_component(project_key, "projectKey", PROJECT_KEY_RE)
        if not (project_dir(root, project_key) / "project.yaml").is_file():
            raise OpenSpecError(f"Unknown projectKey: {project_key}")
    short_id = secrets.token_hex(3)
    date = datetime.now().strftime("%Y%m%d")
    slug = re.sub(r"[\\/:*?\"<>|\s]+", "-", title).strip("-") or "unknown"
    directory_name = f"inv-{date}-{short_id}-{slug}-{environment}"
    parent_key = project_key or "_unassigned"
    target = root / "investigations" / parent_key / directory_name
    target.mkdir(parents=True)
    investigation_id = f"inv-{date}-{short_id}"
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "objectType": "investigation",
        "investigationId": investigation_id,
        "title": title,
        "projectKey": project_key,
        "environment": environment,
        "status": "new",
        "createdAt": now_iso(),
        "inputs": {"problemDescription": title, "traceIds": []},
        "candidateServices": [],
        "result": {"conclusion": "pending", "rootCause": None, "promotedInitiative": None},
    }
    write_yaml(target / "links.yaml", payload)
    atomic_write_text(target / "README.md", f"# {title}\n\n排查编号：`{investigation_id}`。\n")
    atomic_write_text(target / "overview.md", f"# 现象\n\n{title}\n")
    atomic_write_text(target / "findings.md", "# Findings\n\n当前结论：待分析。\n")
    atomic_write_text(target / "handoff.md", "# Handoff\n\n当前出口：待确定。\n")
    for name in ["logs", "traces", "sql", "source-flow"]:
        (target / "evidence" / name).mkdir(parents=True)
    return {"investigationId": investigation_id, "path": str(target.relative_to(root))}


def _find_investigation(root: Path, investigation_id: str) -> Path:
    matches = [path.parent for path in (root / "investigations").glob(f"*/*/links.yaml") if load_yaml(path).get("investigationId") == investigation_id]
    if len(matches) != 1:
        raise OpenSpecError(f"Expected one investigation for {investigation_id}, found {len(matches)}")
    return matches[0]


def promote_investigation(
    root: Path,
    investigation_id: str,
    initiative_key: str,
    demand_id: str,
    demand_title: str,
    environment: str,
    projects: Iterable[str],
) -> dict[str, Any]:
    investigation_path = _find_investigation(root, investigation_id)
    result = init_initiative(root, initiative_key, demand_id, demand_title, environment, projects)
    links_path = investigation_path / "links.yaml"
    investigation = load_yaml(links_path)
    investigation["status"] = "promoted"
    investigation["result"]["conclusion"] = "implementation_required"
    investigation["result"]["promotedInitiative"] = initiative_key
    write_yaml(links_path, investigation)
    initiative_path = initiative_dir(root, initiative_key) / "initiative.yaml"
    initiative = load_yaml(initiative_path)
    initiative["sourceInvestigations"] = [str(investigation_path.relative_to(root))]
    write_yaml(initiative_path, initiative)
    return {**result, "sourceInvestigation": investigation_id}


def _run_git(checkout: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(checkout), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).stdout
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise OpenSpecError(f"git {' '.join(args)} failed for {checkout}: {detail}") from exc


def _extract_git_tree(checkout: Path, commit_sha: str, source_path: str, destination: Path) -> None:
    _run_git(checkout, "cat-file", "-e", f"{commit_sha}^{{commit}}")
    _run_git(checkout, "cat-file", "-e", f"{commit_sha}:{source_path}")
    archive = _run_git(checkout, "archive", "--format=tar", commit_sha, source_path)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as handle:
        base = destination.resolve()
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if base != target and base not in target.parents:
                raise OpenSpecError(f"Unsafe archive member: {member.name}")
            if member.issym() or member.islnk():
                raise OpenSpecError(f"Symlinks are not allowed in OpenSpec snapshots: {member.name}")
        handle.extractall(destination)


def tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _next_revision(revisions: Path) -> str:
    existing = [int(path.name[1:]) for path in revisions.glob("r[0-9][0-9][0-9]") if path.name[1:].isdigit()]
    return f"r{(max(existing, default=0) + 1):03d}"


def archive_initiative(
    root: Path, initiative_key: str, checkouts: dict[str, Path], revision: str | None = None
) -> dict[str, Any]:
    readiness = archive_readiness(root, initiative_key)
    if not readiness["ready"]:
        raise OpenSpecError("Archive is not ready: " + "; ".join(readiness["blockers"]))
    archive_root = root / "archive" / "initiatives" / "_shared" / initiative_key
    revisions = archive_root / "revisions"
    revisions.mkdir(parents=True, exist_ok=True)
    revision = revision or _next_revision(revisions)
    if not re.fullmatch(r"r[0-9]{3}", revision):
        raise OpenSpecError("Revision must match rNNN")
    target = revisions / revision
    if target.exists():
        raise OpenSpecError(f"Archive revision already exists: {target}")
    temp = revisions / f".{revision}.{secrets.token_hex(4)}.tmp"
    temp.mkdir()
    snapshot_records: list[dict[str, Any]] = []
    try:
        shutil.copytree(initiative_dir(root, initiative_key), temp / "initiative")
        (temp / "project-bindings").mkdir()
        for project_result in readiness["projects"]:
            project_key = project_result["projectKey"]
            binding_path = binding_dir(root, project_key, initiative_key) / "binding.yaml"
            binding = load_yaml(binding_path)
            shutil.copy2(binding_path, temp / "project-bindings" / f"{project_key}.yaml")
            for service in binding.get("serviceBindings", []):
                service_key = service["serviceKey"]
                checkout = checkouts.get(service_key)
                if checkout is None:
                    raise OpenSpecError(f"Missing --checkout for {service_key}")
                if not checkout.is_dir():
                    raise OpenSpecError(f"Checkout not found for {service_key}: {checkout}")
                service_dir = require_component(service_key.split(":", 1)[1], "service directory")
                destination = temp / "project-openspec-snapshots" / project_key / service_dir
                _extract_git_tree(checkout, service["commitSha"], service["openSpecPath"], destination)
                snapshot_hash = tree_sha256(destination)
                service["snapshotSha256"] = snapshot_hash
                snapshot_records.append(
                    {
                        "projectKey": project_key,
                        "serviceKey": service_key,
                        "repoUrl": service["repoUrl"],
                        "commitSha": service["commitSha"],
                        "openSpecPath": service["openSpecPath"],
                        "snapshotSha256": snapshot_hash,
                    }
                )
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "objectType": "initiative_archive_revision",
            "initiativeKey": initiative_key,
            "revision": revision,
            "archivedAt": now_iso(),
            "snapshots": snapshot_records,
        }
        write_yaml(temp / "manifest.yaml", manifest)
        os.replace(temp, target)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    initiative_path = initiative_dir(root, initiative_key) / "initiative.yaml"
    initiative = load_yaml(initiative_path)
    initiative["status"] = "archived"
    initiative["lastArchivedRevision"] = revision
    initiative["updatedAt"] = now_iso()
    write_yaml(initiative_path, initiative)
    write_yaml(archive_root / "latest.yaml", {"initiativeKey": initiative_key, "revision": revision, "path": str(target.relative_to(root))})
    return {"initiativeKey": initiative_key, "revision": revision, "path": str(target.relative_to(root)), "snapshots": snapshot_records}


def search_history(root: Path, project_key: str | None = None, service_key: str | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for manifest_path in sorted((root / "archive" / "initiatives" / "_shared").glob("*/revisions/r[0-9][0-9][0-9]/manifest.yaml")):
        manifest = load_yaml(manifest_path)
        snapshots = manifest.get("snapshots", [])
        if project_key and not any(item.get("projectKey") == project_key for item in snapshots):
            continue
        if service_key and not any(item.get("serviceKey") == service_key for item in snapshots):
            continue
        results.append({**manifest, "path": str(manifest_path.parent.relative_to(root))})
    return results


def validate_workspace(root: Path) -> dict[str, Any]:
    required = [
        "projects",
        "initiatives/_shared",
        "investigations/_unassigned",
        "archive/initiatives/_shared",
        "schemas",
        "templates",
    ]
    errors = [f"Missing required path: {path}" for path in required if not (root / path).exists()]
    for path in root.glob("projects/*/project.yaml"):
        try:
            project = load_yaml(path)
            if project.get("objectType") != "project" or project.get("projectKey") != path.parent.name:
                errors.append(f"Invalid project identity: {path.relative_to(root)}")
        except OpenSpecError as exc:
            errors.append(str(exc))
    for path in root.glob("initiatives/_shared/*/initiative.yaml"):
        try:
            initiative = load_yaml(path)
            key = initiative.get("initiativeKey")
            if key != path.parent.name:
                errors.append(f"Invalid initiative identity: {path.relative_to(root)}")
            for project_key in initiative.get("participatingProjects", []):
                if not (binding_dir(root, project_key, key) / "binding.yaml").is_file():
                    errors.append(f"Missing binding for {key}/{project_key}")
        except OpenSpecError as exc:
            errors.append(str(exc))
    return {"valid": not errors, "errors": errors}


def json_output(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
