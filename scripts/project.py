"""Per-project configuration and on-disk layout."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_PROJECT = "ai_context"


@dataclass(frozen=True)
class ProjectConfig:
    """Paths and API identifiers for one Drupal contrib project."""

    machine_name: str
    drupal_org_nid: int
    period_source: str = "releases"
    milestone_close_grace_hours: float = 24.0
    milestone_include_pattern: str = r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\d*)?$"
    milestone_exclude_titles: tuple[str, ...] = ()
    root: Path = REPO_ROOT

    @property
    def project_dir(self) -> Path:
        return self.root / self.machine_name

    @property
    def cache_dir(self) -> Path:
        return self.project_dir / "cache"

    @property
    def periods_dir(self) -> Path:
        return self.cache_dir / "periods"

    @property
    def reports_dir(self) -> Path:
        return self.project_dir / "reports"

    @property
    def summaries_dir(self) -> Path:
        return self.project_dir / "summaries"

    @property
    def exclude_list_file(self) -> Path:
        return self.project_dir / "exclude_from_lists.txt"

    @property
    def ignore_uncredited_file(self) -> Path:
        return self.project_dir / "ignore_uncredited_people.txt"

    @property
    def issues_cache(self) -> Path:
        return self.cache_dir / "issues.json"

    @property
    def records_cache(self) -> Path:
        return self.cache_dir / "contribution_records.json"

    @property
    def state_cache(self) -> Path:
        return self.cache_dir / "state.json"

    @property
    def audit_records_cache(self) -> Path:
        return self.cache_dir / "credit_audit_records.json"

    @property
    def closed_issues_cache(self) -> Path:
        return self.cache_dir / "closed_issues.json"

    @property
    def approvals_cache(self) -> Path:
        return self.cache_dir / "credit_approvals.json"

    @property
    def issue_activity_cache(self) -> Path:
        return self.cache_dir / "issue_activity.json"

    @property
    def audit_output(self) -> Path:
        return self.reports_dir / "credit-audit.md"

    @property
    def gitlab_project(self) -> str:
        return f"project/{self.machine_name}"

    @property
    def gitlab_project_encoded(self) -> str:
        return quote(self.gitlab_project, safe="")

    @property
    def user_agent(self) -> str:
        return (
            "issue-credit-report/1.0 "
            f"(+https://www.drupal.org/project/{self.machine_name})"
        )

    @property
    def drupal_releases_url(self) -> str:
        return f"https://www.drupal.org/project/{self.machine_name}/releases"

    @property
    def issue_iid_pattern(self) -> re.Pattern[str]:
        escaped = re.escape(self.machine_name)
        return re.compile(
            rf"(?:git\.drupalcode\.org/project/{escaped}/-/work_items/(\d+)"
            rf"|www\.drupal\.org/(?:node|project/[^/]+/issues)/(\d+))"
        )

    def issue_url(self, iid: int) -> str:
        return (
            f"https://git.drupalcode.org/project/{self.machine_name}"
            f"/-/work_items/{iid}"
        )

    def merge_request_url(self, iid: int) -> str:
        return (
            f"https://git.drupalcode.org/project/{self.machine_name}"
            f"/-/merge_requests/{iid}"
        )

    def milestone_search_url(self, title: str) -> str:
        return (
            f"https://git.drupalcode.org/project/{self.machine_name}"
            f"/-/milestones?search={quote(title, safe='')}"
        )

    def issue_iid_from_link(self, uri: str) -> int | None:
        match = self.issue_iid_pattern.search(uri)
        if not match:
            return None
        return int(match.group(1) or match.group(2))

    def ensure_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.periods_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_output_dir()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def _migrate_output_dir(self) -> None:
        """Rename legacy output/ to reports/."""
        legacy = self.project_dir / "output"
        if not legacy.is_dir():
            return
        target = self.reports_dir
        if not target.exists():
            legacy.rename(target)
            return
        for path in legacy.iterdir():
            dest = target / path.name
            if dest.exists():
                continue
            path.rename(dest)
        if not any(legacy.iterdir()):
            legacy.rmdir()

    @classmethod
    def load(cls, machine_name: str, root: Path = REPO_ROOT) -> ProjectConfig:
        project_dir = root / machine_name
        config_path = project_dir / "config.json"
        if not project_dir.is_dir():
            available = ", ".join(cls.list_projects(root)) or "(none)"
            raise SystemExit(
                f"Unknown project {machine_name!r}: {project_dir} not found. "
                f"Available: {available}"
            )
        if not config_path.is_file():
            raise SystemExit(
                f"Missing {config_path}. Create it with at least "
                '{"drupal_org_nid": 1234567}.'
            )
        data = json.loads(config_path.read_text())
        nid = data.get("drupal_org_nid")
        if not nid:
            raise SystemExit(f"{config_path} must include drupal_org_nid.")
        configured_name = data.get("machine_name") or machine_name
        if configured_name != machine_name:
            raise SystemExit(
                f"machine_name in {config_path} ({configured_name!r}) "
                f"must match directory name ({machine_name!r})."
            )
        grace_hours = float(data.get("milestone_close_grace_hours", 24.0))
        period_source = data.get("period_source", "releases")
        if period_source not in ("releases", "milestones"):
            raise SystemExit(
                f"{config_path} period_source must be 'releases' or 'milestones'."
            )
        include_pattern = data.get(
            "milestone_include_pattern",
            r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\d*)?$",
        )
        exclude_raw = data.get("milestone_exclude_titles") or []
        if isinstance(exclude_raw, str):
            exclude_titles = tuple(exclude_raw.split(","))
        else:
            exclude_titles = tuple(str(title) for title in exclude_raw)
        return cls(
            machine_name=configured_name,
            drupal_org_nid=int(nid),
            period_source=period_source,
            milestone_close_grace_hours=grace_hours,
            milestone_include_pattern=include_pattern,
            milestone_exclude_titles=exclude_titles,
            root=root,
        )

    @classmethod
    def list_projects(cls, root: Path = REPO_ROOT) -> list[str]:
        projects: list[str] = []
        for path in sorted(root.iterdir()):
            if path.is_dir() and (path / "config.json").is_file():
                projects.append(path.name)
        return projects


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        metavar="NAME",
        help=(
            f"Drupal project machine name (default: {DEFAULT_PROJECT}). "
            "Reads {NAME}/config.json; cache and reports live under {NAME}/."
        ),
    )
