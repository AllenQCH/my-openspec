from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from openspec_cli.core import (
    OpenSpecError,
    archive_initiative,
    archive_readiness,
    bind_service,
    collect_project_result,
    init_initiative,
    init_project,
    initiative_completeness,
    new_investigation,
    project_readiness,
    promote_investigation,
    search_history,
    set_initiative_status,
    validate_workspace,
)


class OpenSpecWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative in [
            "projects",
            "initiatives/_shared",
            "investigations/_unassigned",
            "archive/initiatives/_shared",
            "schemas",
            "templates",
        ]:
            (self.root / relative).mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_repo(self, name: str, openspec_path: str) -> tuple[Path, str]:
        repo = self.root / "repos" / name
        target = repo / openspec_path
        target.mkdir(parents=True)
        (target / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
        (target / "design.md").write_text("# Design\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "OpenSpec Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
        commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        return repo, commit

    def test_cross_project_archive_and_history(self) -> None:
        init_project(self.root, "project-a", "示例项目 A", "shared")
        init_project(self.root, "project-b", "示例项目 B", "shared")
        key = "DEMO-100-example-shared"
        init_initiative(self.root, key, "DEMO-100", "示例需求", "shared", ["project-a", "project-b"])

        service_a_path = "openspec/changes/DEMO-100"
        service_b_path = "openspec/changes/DEMO-100"
        bind_service(self.root, key, "project-a", "shared:service-a", "git@example.com:team/service-a.git", service_a_path, "feature/DEMO-100")
        bind_service(self.root, key, "project-b", "shared:service-b", "git@example.com:team/service-b.git", service_b_path, "feature/DEMO-100")
        service_a_repo, service_a_commit = self.make_repo("service-a", service_a_path)
        service_b_repo, service_b_commit = self.make_repo("service-b", service_b_path)

        for project, service, commit in [
            ("project-a", "shared:service-a", service_a_commit),
            ("project-b", "shared:service-b", service_b_commit),
        ]:
            collect_project_result(
                self.root,
                key,
                project,
                service,
                commit,
                "completed",
                ["testing.md"],
                ["rollout.md"],
            )

        self.assertTrue(project_readiness(self.root, key, "project-a")["ready"])
        self.assertTrue(initiative_completeness(self.root, key)["complete"])
        self.assertFalse(archive_readiness(self.root, key)["ready"])
        set_initiative_status(self.root, key, "completed")
        self.assertTrue(archive_readiness(self.root, key)["ready"])

        archived = archive_initiative(
            self.root,
            key,
            {"shared:service-a": service_a_repo, "shared:service-b": service_b_repo},
        )
        self.assertEqual("r001", archived["revision"])
        self.assertEqual(2, len(archived["snapshots"]))
        self.assertEqual(1, len(search_history(self.root, project_key="project-a")))
        self.assertEqual(1, len(search_history(self.root, service_key="shared:service-b")))
        self.assertTrue(validate_workspace(self.root)["valid"])

    def test_investigation_can_promote_without_initial_project(self) -> None:
        init_project(self.root, "project-a", "示例项目 A", "shared")
        created = new_investigation(self.root, "未知 trace 异常", "shared")
        promoted = promote_investigation(
            self.root,
            created["investigationId"],
            "DEMO-200-fix-status-shared",
            "DEMO-200",
            "修复示例状态回写",
            "shared",
            ["project-a"],
        )
        self.assertEqual(created["investigationId"], promoted["sourceInvestigation"])

    def test_rejects_partial_commit_sha(self) -> None:
        init_project(self.root, "project-a", "示例项目 A", "shared")
        key = "DEMO-300-example-shared"
        init_initiative(self.root, key, "DEMO-300", "示例", "shared", ["project-a"])
        bind_service(self.root, key, "project-a", "shared:service-a", "git@example.com:team/service-a.git", "openspec/changes/DEMO-300", "feature/DEMO-300")
        with self.assertRaises(OpenSpecError):
            collect_project_result(self.root, key, "project-a", "shared:service-a", "abc123", "completed", [], [])


if __name__ == "__main__":
    unittest.main()
