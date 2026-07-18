#!/usr/bin/env python3
"""Generate Drupal project release credit reports from Drupal.org APIs."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import requests

from html_report import (
    a,
    drupal_org_profile_url,
    drupal_user_profile_url,
    em,
    escape,
    format_changes_since_line,
    format_issue_item,
    h2,
    h3,
    join_blocks,
    li,
    p,
    strong,
    table,
    ul,
)
from project import REPO_ROOT, ProjectConfig, add_project_argument

DEFAULT_MILESTONE_CLOSE_GRACE_HOURS = 24.0

CONTRIBUTOR_INCLUDE = (
    "field_contributors,field_contributors.field_contributor_user,"
    "field_contributors.field_contributor_organisation,"
    "field_contributors.field_contributor_customer"
)

GITLAB_TOKEN_FILE = REPO_ROOT / ".gitlab-token"
AI_INITIATIVE_PARTNERS_FILE = REPO_ROOT / "scripts" / "ai-initiative-partners.md"
GITLAB_KEYCHAIN_SERVICE = "issue-credit-report"
GITLAB_KEYCHAIN_ACCOUNT = "git.drupalcode.org"

CATEGORY_LABEL = re.compile(r"^category::(\w+)$")
PRIORITY_LABEL = re.compile(r"^priority::(\w+)$")
WHAT_CODE_LABEL = "what::code"

FEATURE_CATEGORIES = {"feature"}
BUG_CATEGORIES = {"bug"}
OTHER_CATEGORIES = {"plan", "task", "support"}
ADDITIONAL_CATEGORY_ORDER = ("plan", "task", "support")
HIGH_PRIORITIES = {"critical", "major"}
IGNORED_CONTRIBUTOR_USERNAMES = {"system message", "system_message"}
SPRINT_PLANNING_TITLE = re.compile(
    r"roadmap updates, sprint planning, and issue triage",
    re.IGNORECASE,
)
SESSION_OR_MEETING_TITLE = re.compile(
    r"\b(?:slides|sync|meeting|presentation)\b",
    re.IGNORECASE,
)
CREATE_CCC_RELEASE_TITLE = re.compile(
    r"^Create CCC .+ release$",
    re.IGNORECASE,
)
CCC_QA_TITLE = re.compile(
    r"^CCC .+ QA$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReleaseBoundary:
    version: str
    created: datetime


@dataclass(frozen=True)
class ReportPeriod:
    slug: str
    title: str
    start: datetime | None
    end: datetime | None
    frozen: bool


@dataclass
class CreditedIssue:
    uuid: str
    title: str
    iid: int
    closed_at: datetime
    category: str | None
    priority: str | None
    issue_url: str
    contributors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def users(self) -> list[str]:
        return [entry["user"] for entry in self.contributors if entry.get("user")]

    @property
    def orgs(self) -> list[str]:
        orgs: list[str] = []
        for entry in self.contributors:
            orgs.extend(org_keys(entry.get("orgs", [])))
        return orgs

    @property
    def user_org_map(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = defaultdict(set)
        for entry in self.contributors:
            user = entry.get("user")
            if user:
                mapping[user].update(org_keys(entry.get("orgs", [])))
        return mapping


@dataclass
class PeriodReport:
    period: ReportPeriod
    issues: list[CreditedIssue]
    generated_at: str

    @property
    def user_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for issue in self.issues:
            for user in issue.users:
                counts[user] += 1
        return counts

    @property
    def user_display_names(self) -> dict[str, str]:
        """Map normalized git username keys to Drupal.org display names."""
        names: dict[str, str] = {}
        for issue in self.issues:
            for entry in issue.contributors:
                user = entry.get("user")
                display = entry.get("display_name")
                if user and display:
                    names[user] = display
        return names

    @property
    def user_profile_urls(self) -> dict[str, str]:
        """Map normalized git username keys to Drupal.org profile URLs."""
        urls: dict[str, str] = {}
        for issue in self.issues:
            for entry in issue.contributors:
                user = entry.get("user")
                uid = entry.get("drupal_uid")
                if user and uid:
                    urls[user] = drupal_user_profile_url(int(uid))
        return urls

    @property
    def org_profile_urls(self) -> dict[str, str]:
        """Map normalized organization keys to Drupal.org profile URLs."""
        urls: dict[str, str] = {}
        for issue in self.issues:
            for entry in issue.contributors:
                for org in entry.get("orgs", []):
                    if not isinstance(org, dict):
                        continue
                    name = org_key(org)
                    nid = org.get("nid")
                    if name and nid:
                        urls[name] = drupal_org_profile_url(int(nid))
        return urls

    @property
    def org_display_titles(self) -> dict[str, str]:
        """Map normalized organization keys to Drupal.org organization titles."""
        titles: dict[str, str] = {}
        for issue in self.issues:
            for entry in issue.contributors:
                for org in entry.get("orgs", []):
                    if isinstance(org, dict):
                        name = org_key(org)
                        title = org.get("title")
                        if name and title:
                            titles[name] = title
        return titles

    @property
    def org_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for issue in self.issues:
            for org in set(issue.orgs):
                counts[org] += 1
        return counts

    @property
    def user_org_map(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = defaultdict(set)
        for issue in self.issues:
            for user, orgs in issue.user_org_map.items():
                mapping[user].update(orgs)
        return mapping


def gitlab_token_file_candidates() -> list[Path]:
    return [
        GITLAB_TOKEN_FILE,
        REPO_ROOT / ".gitlab-token.local",
        Path.home() / ".config" / "issue-credit-report" / "gitlab-token",
    ]


def load_gitlab_token_from_keyring() -> str | None:
    """Load token from OS keychain (macOS Keychain, Linux Secret Service, etc.)."""
    try:
        import keyring
    except ImportError:
        return _load_gitlab_token_from_macos_keychain()

    try:
        token = keyring.get_password(GITLAB_KEYCHAIN_SERVICE, GITLAB_KEYCHAIN_ACCOUNT)
    except Exception:
        return None
    return token.strip() if token else None


def _load_gitlab_token_from_macos_keychain() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                GITLAB_KEYCHAIN_SERVICE,
                "-a",
                GITLAB_KEYCHAIN_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    token = result.stdout.strip()
    return token or None


def store_gitlab_token_in_keyring(token: str) -> None:
    token = token.strip()
    if not token:
        raise ValueError("GitLab token is empty.")

    try:
        import keyring

        keyring.set_password(GITLAB_KEYCHAIN_SERVICE, GITLAB_KEYCHAIN_ACCOUNT, token)
        return
    except ImportError:
        if sys.platform == "darwin":
            _store_gitlab_token_in_macos_keychain(token)
            return
        raise RuntimeError(
            "Install keyring to store tokens in your OS secret store: "
            "python3 -m pip install keyring"
        ) from None
    except Exception as exc:
        raise RuntimeError(f"Could not save GitLab token to keychain: {exc}") from exc


def _store_gitlab_token_in_macos_keychain(token: str) -> None:
    try:
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-s",
                GITLAB_KEYCHAIN_SERVICE,
                "-a",
                GITLAB_KEYCHAIN_ACCOUNT,
                "-w",
                token,
                "-U",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(stderr or "security add-generic-password failed") from exc


def clear_gitlab_token_from_keyring() -> bool:
    """Remove token from keychain. Returns True if something was removed."""
    removed = False
    try:
        import keyring

        try:
            keyring.delete_password(GITLAB_KEYCHAIN_SERVICE, GITLAB_KEYCHAIN_ACCOUNT)
            removed = True
        except keyring.errors.PasswordDeleteError:
            pass
    except ImportError:
        if sys.platform == "darwin":
            removed = _clear_gitlab_token_from_macos_keychain() or removed

    return removed


def _clear_gitlab_token_from_macos_keychain() -> bool:
    try:
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s",
                GITLAB_KEYCHAIN_SERVICE,
                "-a",
                GITLAB_KEYCHAIN_ACCOUNT,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def prompt_and_store_gitlab_token() -> None:
    print(
        "Paste a git.drupalcode.org personal access token with read_api scope.\n"
        "Input is hidden. The token is stored in your OS keychain (encrypted), "
        "not in a plaintext project file."
    )
    token = getpass.getpass("GitLab token: ").strip()
    if not token:
        raise SystemExit("No token entered.")
    store_gitlab_token_in_keyring(token)
    print("Saved GitLab token to your OS keychain.")


def load_gitlab_token() -> str | None:
    """Load a GitLab token from the OS keychain or environment."""
    token = load_gitlab_token_from_keyring()
    if token:
        return token

    for path in gitlab_token_file_candidates():
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped

    for key in ("GITLAB_TOKEN", "GITLAB_PRIVATE_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def gitlab_token_configured() -> bool:
    return load_gitlab_token() is not None


def gitlab_token_setup_hint() -> str:
    return (
        "Run: python3 scripts/credit_audit.py --store-gitlab-token "
        "(saves to your OS keychain; not stored in plaintext)"
    )


class ApiClient:
    def __init__(self, project: ProjectConfig) -> None:
        self.project = project
        self.session = requests.Session()
        headers = {"User-Agent": project.user_agent}
        gitlab_token = load_gitlab_token()
        if gitlab_token:
            headers["PRIVATE-TOKEN"] = gitlab_token
        self.session.headers.update(headers)

    def get_json(
        self,
        url: str,
        *,
        accept: str = "application/json",
        max_retries: int = 6,
    ) -> Any:
        delay = 2.0
        for attempt in range(max_retries):
            response = self.session.get(url, headers={"Accept": accept}, timeout=120)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                print(
                    f"  rate limited, waiting {wait:.0f}s ({attempt + 1}/{max_retries})...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                delay = min(delay * 2, 60)
                continue
            if response.status_code >= 500 and attempt < max_retries - 1:
                print(
                    f"  server error {response.status_code}, retrying in {delay:.0f}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return response.json()

    def get_jsonapi(self, url: str) -> dict[str, Any]:
        return self.get_json(url, accept="application/vnd.api+json")


class DrupalProfileAliasResolver:
    """Resolve Drupal.org user/node IDs to public profile URLs via api-d7."""

    def __init__(self, client: ApiClient, cache_path: Path, *, refresh: bool = False) -> None:
        self.client = client
        self.cache_path = cache_path
        if refresh and cache_path.exists():
            cache_path.unlink()
        self._cache: dict[str, dict[str, str]] = load_json(
            cache_path,
            {"users": {}, "nodes": {}},
        )
        self._dirty = False

    def save(self) -> None:
        if self._dirty:
            save_json(self.cache_path, self._cache)

    def user_url(self, uid: int) -> str:
        key = str(uid)
        cached = self._cache.setdefault("users", {}).get(key)
        if cached:
            return cached
        url = self._fetch_user_url(uid)
        self._cache["users"][key] = url
        self._dirty = True
        return url

    def org_url(self, nid: int) -> str:
        key = str(nid)
        cached = self._cache.setdefault("nodes", {}).get(key)
        if cached:
            return cached
        url = self._fetch_org_url(nid)
        self._cache["nodes"][key] = url
        self._dirty = True
        return url

    def _fetch_user_url(self, uid: int) -> str:
        try:
            payload = self.client.get_json(
                f"https://www.drupal.org/api-d7/user/{uid}.json"
            )
            url = payload.get("url")
            if url:
                return url
        except requests.RequestException:
            pass
        return drupal_user_profile_url(uid)

    def _fetch_org_url(self, nid: int) -> str:
        try:
            payload = self.client.get_json(
                f"https://www.drupal.org/api-d7/node/{nid}.json"
            )
            url = payload.get("url")
            if url:
                return url
        except requests.RequestException:
            pass
        return drupal_org_profile_url(nid)


def build_user_profile_urls(
    report: PeriodReport,
    resolver: DrupalProfileAliasResolver,
) -> dict[str, str]:
    urls: dict[str, str] = {}
    for issue in report.issues:
        for entry in issue.contributors:
            user = entry.get("user")
            uid = entry.get("drupal_uid")
            if user and uid and user not in urls:
                urls[user] = resolver.user_url(int(uid))
    return urls


def build_org_profile_urls(
    report: PeriodReport,
    resolver: DrupalProfileAliasResolver,
) -> dict[str, str]:
    urls: dict[str, str] = {}
    for issue in report.issues:
        for entry in issue.contributors:
            for org in entry.get("orgs", []):
                if not isinstance(org, dict):
                    continue
                name = org_key(org)
                nid = org.get("nid")
                if name and nid and name not in urls:
                    urls[name] = resolver.org_url(int(nid))
    return urls


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize_username(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


def normalize_org(title: str) -> str:
    return title.strip().lower()


def partner_lookup_keys(name: str) -> set[str]:
    """Normalized keys for matching Drupal.org org names to partner list entries."""
    normalized = normalize_org(name)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    keys = {normalized}
    if compact:
        keys.add(compact)
    return keys


def load_ai_initiative_partner_keys(
    path: Path = AI_INITIATIVE_PARTNERS_FILE,
) -> frozenset[str]:
    """Load current and former AI Initiative partner names from markdown."""
    if not path.exists():
        return frozenset()

    keys: set[str] = set()
    in_partner_section = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if re.match(r"^#\s*Current partners\s*$", stripped, re.IGNORECASE):
            in_partner_section = True
            continue
        if re.match(r"^#\s*Previous partners\s*$", stripped, re.IGNORECASE):
            in_partner_section = True
            continue
        if re.match(r"^#\s*Updating", stripped, re.IGNORECASE):
            break
        if in_partner_section and stripped.startswith("- "):
            keys.update(partner_lookup_keys(stripped[2:].strip()))
    return frozenset(keys)


def org_matches_ai_initiative_partner(
    org_key_name: str,
    display_title: str,
    partner_keys: frozenset[str],
) -> bool:
    if not partner_keys:
        return False
    for candidate in (display_title, org_key_name):
        if partner_lookup_keys(candidate) & partner_keys:
            return True
    return False


def ai_initiative_partner_orgs_in_report(
    report: PeriodReport,
    partner_keys: frozenset[str],
) -> set[str]:
    """Return org keys in the report that match the AI Initiative partner list."""
    matched: set[str] = set()
    display_titles = report.org_display_titles
    for name in report.org_counts:
        display = display_titles.get(name, name)
        if org_matches_ai_initiative_partner(name, display, partner_keys):
            matched.add(name)
    return matched


def ai_initiative_partner_people_in_report(
    report: PeriodReport,
    partner_orgs: set[str],
) -> set[str]:
    """Return users credited with at least one AI Initiative partner organization."""
    if not partner_orgs:
        return set()
    matched: set[str] = set()
    user_orgs = report.user_org_map
    for user in report.user_counts:
        if user_orgs.get(user, set()) & partner_orgs:
            matched.add(user)
    return matched


def org_key(entry: str | dict[str, Any]) -> str:
    if isinstance(entry, dict):
        return entry.get("name") or normalize_org(entry.get("title", ""))
    return entry


def org_keys(orgs: list[str | dict[str, Any]]) -> list[str]:
    return [org_key(org) for org in orgs if org_key(org)]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def fetch_release_boundaries(client: ApiClient) -> list[ReleaseBoundary]:
    """Load tagged releases from Drupal.org."""
    project = client.project
    url = (
        "https://www.drupal.org/api-d7/node.json"
        f"?type=project_release&field_release_project={project.drupal_org_nid}"
        "&limit=50&sort=nid&direction=asc"
    )
    payload = client.get_json(url)
    releases: list[ReleaseBoundary] = []
    for node in payload.get("list", []):
        if node.get("field_release_build_type") == "dynamic":
            continue
        version = node.get("field_release_version")
        created = node.get("created")
        if not version or not created:
            continue
        releases.append(
            ReleaseBoundary(
                version=version,
                created=datetime.fromtimestamp(int(created), tz=timezone.utc),
            )
        )
    releases.sort(key=lambda release: release.created)
    return releases


def version_short_slug(version: str) -> str:
    """Short slug segment for a release version (e.g. 1.0.0-beta2 -> beta2)."""
    match = re.search(r"-(alpha|beta|rc)(\d+)$", version, re.IGNORECASE)
    if match:
        return f"{match.group(1).lower()}{match.group(2)}"
    return version.replace(".", "-")


def period_slug(start_version: str | None, end_version: str | None) -> str:
    if start_version is None:
        return f"pre-{version_short_slug(end_version or '')}"
    if end_version is None:
        return f"{version_short_slug(start_version)}-to-now"
    return f"{version_short_slug(start_version)}-to-{version_short_slug(end_version)}"


def period_title(start_version: str | None, end_version: str | None) -> str:
    if start_version is None:
        return f"Inception to {end_version}"
    if end_version is None:
        return f"{start_version} to now"
    return f"{start_version} to {end_version}"


def build_periods(releases: list[ReleaseBoundary], project: ProjectConfig) -> list[ReportPeriod]:
    if not releases:
        raise RuntimeError(
            f"No tagged releases found on Drupal.org for {project.machine_name}. "
            f"See {project.drupal_releases_url}"
        )

    periods: list[ReportPeriod] = [
        ReportPeriod(
            slug=period_slug(None, releases[0].version),
            title=period_title(None, releases[0].version),
            start=None,
            end=releases[0].created,
            frozen=True,
        )
    ]

    for index in range(len(releases) - 1):
        previous = releases[index]
        current = releases[index + 1]
        periods.append(
            ReportPeriod(
                slug=period_slug(previous.version, current.version),
                title=period_title(previous.version, current.version),
                start=previous.created,
                end=current.created,
                frozen=True,
            )
        )

    last = releases[-1]
    periods.append(
        ReportPeriod(
            slug=period_slug(last.version, None),
            title=period_title(last.version, None),
            start=last.created,
            end=None,
            frozen=False,
        )
    )
    return periods


def release_compare_versions(
    period: ReportPeriod,
    releases: list[ReleaseBoundary],
) -> tuple[str, str] | None:
    """Return (since_version, until_version) for a GitLab compare link."""
    if not releases:
        return None

    versions = [release.version for release in releases]
    title = period.title.strip()

    if title in versions:
        index = versions.index(title)
        if index == 0:
            return None
        return versions[index - 1], title

    if " to " not in title:
        return None

    since_part, until_part = title.split(" to ", 1)
    if since_part.strip().lower() == "inception":
        return None

    since_version = since_part.strip()
    until_label = until_part.strip()
    if until_label.lower() == "now":
        if since_version not in versions:
            return None
        return since_version, versions[-1]

    until_version = until_label
    if since_version in versions and until_version in versions:
        return since_version, until_version
    return None


def next_release_version(version: str) -> str:
    """Return the next pre-release version (increment alpha/beta/rc suffix)."""
    match = re.search(
        r"^(?P<prefix>.+-)(?P<phase>alpha|beta|rc)(?P<num>\d+)$",
        version,
        re.IGNORECASE,
    )
    if match:
        prefix = match.group("prefix")
        phase = match.group("phase").lower()
        num = int(match.group("num"))
        return f"{prefix}{phase}{num + 1}"
    raise ValueError(f"Cannot infer next release after {version!r}")


def milestone_for_closed_at(
    closed_at: datetime,
    releases: list[ReleaseBoundary],
    *,
    grace_hours: float = DEFAULT_MILESTONE_CLOSE_GRACE_HOURS,
) -> str:
    """Return the GitLab milestone title for when an issue was closed.

    Work closed between two tagged releases belongs to the later release's
    milestone. Each release boundary includes a grace period (default 24 hours
    after the tag) so release-day housekeeping issues still map to that release.
    """
    if not releases:
        raise ValueError("At least one release boundary is required.")

    grace = timedelta(hours=grace_hours)

    if closed_at < releases[0].created:
        return releases[0].version

    for index in range(len(releases) - 1):
        if releases[index].created <= closed_at < releases[index + 1].created + grace:
            return releases[index + 1].version

    if closed_at < releases[-1].created + grace:
        return releases[-1].version

    return next_release_version(releases[-1].version)


def index_included(included: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in included:
        indexed[item["type"]][item["id"]] = item
    return indexed


def parse_contributor_entries(
    record: dict[str, Any],
    included_index: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Parse all contributor paragraphs, including uncredited entries."""
    entries: list[dict[str, Any]] = []
    contributor_refs = record.get("relationships", {}).get("field_contributors", {}).get("data", [])

    for ref in contributor_refs:
        paragraph = included_index.get("paragraph--contributor", {}).get(ref["id"])
        if not paragraph:
            continue
        para_attrs = paragraph.get("attributes", {})

        user_name = None
        display_name = None
        drupal_uid = None
        user_ref = paragraph.get("relationships", {}).get("field_contributor_user", {}).get("data")
        if user_ref:
            user = included_index.get("user--user", {}).get(user_ref["id"])
            if user:
                user_attrs = user.get("attributes", {})
                drupal_uid = user_attrs.get("drupal_internal__uid")
                display_name = (
                    user_attrs.get("display_name") or user_attrs.get("name") or ""
                ).strip()
                git_username = user_attrs.get("field_git_username")
                if git_username:
                    user_name = normalize_username(git_username)
                elif display_name:
                    user_name = normalize_username(display_name)

        orgs: list[dict[str, Any]] = []
        org_refs = paragraph.get("relationships", {}).get("field_contributor_organisation", {}).get("data") or []
        customer_refs = paragraph.get("relationships", {}).get("field_contributor_customer", {}).get("data") or []
        for org_ref in org_refs + customer_refs:
            org = included_index.get("node--organization", {}).get(org_ref["id"])
            if org and org.get("attributes", {}).get("title"):
                attrs = org["attributes"]
                title = attrs["title"].strip()
                orgs.append(
                    {
                        "name": normalize_org(title),
                        "title": title,
                        "nid": attrs.get("drupal_internal__nid"),
                    }
                )

        if not user_name and not orgs:
            continue
        if user_name and user_name in IGNORED_CONTRIBUTOR_USERNAMES:
            continue

        entries.append(
            {
                "user": user_name,
                "display_name": display_name or None,
                "drupal_uid": drupal_uid,
                "orgs": orgs,
                "credited": bool(para_attrs.get("field_credit_this_contributor")),
            }
        )

    return entries


def parse_credited_contributors(
    record: dict[str, Any],
    included_index: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    contributors: list[dict[str, Any]] = []
    for entry in parse_contributor_entries(record, included_index):
        if not entry["credited"]:
            continue
        if entry["user"] or entry["orgs"]:
            contributors.append(
                {
                    "user": entry["user"],
                    "display_name": entry.get("display_name"),
                    "drupal_uid": entry.get("drupal_uid"),
                    "orgs": entry["orgs"],
                }
            )
    return contributors


def contribution_record_list_url(project: ProjectConfig) -> str:
    return (
        "https://new.drupal.org/jsonapi/node/contribution_record"
        f"?filter[field_project_name]={project.machine_name}"
        "&filter[field_draft]=0"
        "&fields[node--contribution_record]=drupal_internal__nid,title,"
        "field_last_status_change,field_source_link"
        "&page[limit]=50"
    )


def fetch_contribution_record_detail(
    client: ApiClient,
    uuid: str,
) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Any]]]]:
    """Fetch one record with contributors.

    Paginated list responses can return stale contributor paragraphs on
    new.drupal.org, so always load contributor data per record. Use the
    latest revision — the default revision can lag after edits on Drupal.org.
    """
    url = (
        "https://new.drupal.org/jsonapi/node/contribution_record/"
        f"{uuid}?include={CONTRIBUTOR_INCLUDE}&resourceVersion=rel:latest-version"
    )
    payload = client.get_jsonapi(url)
    return payload["data"], index_included(payload.get("included", []))


def summarize_contribution_record(
    record: dict[str, Any],
    included_index: dict[str, dict[str, dict[str, Any]]],
    project: ProjectConfig,
) -> dict[str, Any] | None:
    attrs = record.get("attributes", {})
    closed_raw = attrs.get("field_last_status_change")
    source = attrs.get("field_source_link", {}).get("uri")
    if not closed_raw or not source:
        return None

    iid = project.issue_iid_from_link(source)
    if not iid:
        return None

    entries = parse_contributor_entries(record, included_index)
    credited = sorted(
        {entry["user"] for entry in entries if entry["credited"] and entry.get("user")}
    )
    uncredited = sorted(
        {entry["user"] for entry in entries if not entry["credited"] and entry.get("user")}
    )
    contributors = parse_credited_contributors(record, included_index)
    nid = attrs.get("drupal_internal__nid")
    return {
        "uuid": record["id"],
        "nid": nid,
        "title": attrs.get("title", f"Issue #{iid}"),
        "closed_at": closed_raw,
        "source_link": source,
        "iid": iid,
        "contributors": contributors,
        "credited": credited,
        "uncredited": uncredited,
        "record_url": f"https://new.drupal.org/node/{nid}" if nid else None,
    }


def fetch_project_contribution_records(
    client: ApiClient,
    *,
    require_credits: bool = False,
) -> list[dict[str, Any]]:
    project = client.project
    print("Listing contribution records from new.drupal.org...")
    stubs: list[dict[str, Any]] = []
    url: str | None = contribution_record_list_url(project)
    page = 0
    while url:
        payload = client.get_jsonapi(url)
        stubs.extend(payload.get("data", []))
        page += 1
        print(f"  list page {page}: {len(stubs)} records")
        url = payload.get("links", {}).get("next", {}).get("href")
        time.sleep(0.1)

    print(f"Fetching contributor details for {len(stubs)} records...")
    parsed_records: list[dict[str, Any]] = []
    for index, stub in enumerate(stubs, start=1):
        record, included_index = fetch_contribution_record_detail(client, stub["id"])
        summary = summarize_contribution_record(record, included_index, project)
        if summary is None:
            continue
        if require_credits and not summary["contributors"]:
            continue
        parsed_records.append(summary)
        if index % 25 == 0 or index == len(stubs):
            print(f"  detail {index}/{len(stubs)}: kept {len(parsed_records)}")
        time.sleep(0.05)

    return parsed_records


def fetch_contribution_records_for_issue(
    client: ApiClient,
    iid: int,
) -> list[dict[str, Any]]:
    """Fetch fresh contributor lists for all records linked to one GitLab issue."""
    project = client.project
    issue_url = project.issue_url(iid)
    list_url = (
        "https://new.drupal.org/jsonapi/node/contribution_record"
        f"?filter[field_source_link.uri]={quote(issue_url, safe='')}"
        "&filter[field_draft]=0"
        "&fields[node--contribution_record]=drupal_internal__nid,title,"
        "field_last_status_change,field_source_link"
    )
    payload = client.get_jsonapi(list_url)
    stubs = payload.get("data") or []
    if isinstance(stubs, dict):
        stubs = [stubs]

    summaries: list[dict[str, Any]] = []
    for stub in stubs:
        record, included_index = fetch_contribution_record_detail(client, stub["id"])
        summary = summarize_contribution_record(record, included_index, project)
        if summary and int(summary["iid"]) == iid:
            summaries.append(summary)
    return summaries


def upsert_release_record_cache_for_issue(
    client: ApiClient,
    iid: int,
    summaries: list[dict[str, Any]],
) -> None:
    """Update release-notes cache for one issue when that cache already exists."""
    project = client.project
    if not project.records_cache.exists():
        return
    cached = load_json(project.records_cache, [])
    cached = [record for record in cached if int(record["iid"]) != iid]
    for summary in summaries:
        if summary.get("contributors"):
            cached.append(
                {
                    "uuid": summary["uuid"],
                    "nid": summary["nid"],
                    "title": summary["title"],
                    "closed_at": summary["closed_at"],
                    "source_link": summary["source_link"],
                    "iid": summary["iid"],
                    "contributors": summary["contributors"],
                }
            )
    save_json(project.records_cache, cached)


def fetch_contribution_records(client: ApiClient, refresh: bool) -> list[dict[str, Any]]:
    project = client.project
    if project.records_cache.exists() and not refresh:
        cached = load_json(project.records_cache, [])
        if cached and "contributors" not in cached[0]:
            print("Contribution record cache uses old format; refreshing...")
            refresh = True
        elif cached:
            print(f"Loaded {len(cached)} contribution records from cache.")
            return cached

    print("Fetching contribution records from new.drupal.org...")
    summaries = fetch_project_contribution_records(client, require_credits=True)
    parsed_records = [
        {
            "uuid": summary["uuid"],
            "nid": summary["nid"],
            "title": summary["title"],
            "closed_at": summary["closed_at"],
            "source_link": summary["source_link"],
            "iid": summary["iid"],
            "contributors": summary["contributors"],
        }
        for summary in summaries
    ]

    save_json(project.records_cache, parsed_records)
    save_json(
        project.state_cache,
        {
            "records_cached_at": datetime.now(tz=timezone.utc).isoformat(),
            "record_count": len(parsed_records),
        },
    )
    print(f"Cached {len(parsed_records)} credited contribution records.")
    return parsed_records


def load_issues_cache(project: ProjectConfig) -> dict[str, dict[str, Any]]:
    return load_json(project.issues_cache, {})


def save_issues_cache(project: ProjectConfig, cache: dict[str, dict[str, Any]]) -> None:
    save_json(project.issues_cache, cache)


def issue_has_merge_request(meta: dict[str, Any]) -> bool:
    """True when GitLab reports a related MR or the issue carries what::code."""
    if meta.get("has_merge_request"):
        return True
    return WHAT_CODE_LABEL in meta.get("labels", [])


def merge_request_metadata_incomplete(
    iids: set[int],
    issues_cache: dict[str, dict[str, Any]],
) -> bool:
    for iid in iids:
        entry = issues_cache.get(str(iid))
        if entry is None or "has_merge_request" not in entry:
            return True
    return False


def enrich_merge_request_metadata(
    client: ApiClient,
    issues_cache: dict[str, dict[str, Any]],
    iids: set[int],
    *,
    refresh: bool = False,
) -> None:
    """Populate has_merge_request on cached issue entries via GitLab API."""
    from gitlab_activity import find_merge_requests

    pending = sorted(
        iid
        for iid in iids
        if refresh or "has_merge_request" not in issues_cache.get(str(iid), {})
    )
    if not pending:
        return

    print(f"Checking merge requests for {len(pending)} credited issues...")
    for index, iid in enumerate(pending, start=1):
        key = str(iid)
        entry = issues_cache.setdefault(
            key,
            {
                "iid": iid,
                "title": f"Issue #{iid}",
                "labels": [],
                "category": None,
                "priority": None,
                "web_url": client.project.issue_url(iid),
            },
        )
        merge_requests = find_merge_requests(client, iid)
        entry["has_merge_request"] = bool(merge_requests)
        entry["merge_request_urls"] = [
            merge_request["web_url"] for merge_request in merge_requests
        ]
        if index % 25 == 0 or index == len(pending):
            print(f"  {index}/{len(pending)} issues checked")
        time.sleep(0.1)


def parse_issue_entry(issue: dict[str, Any], project: ProjectConfig) -> dict[str, Any]:
    iid = int(issue["iid"])
    category = None
    priority = None
    for label in issue.get("labels", []):
        category_match = CATEGORY_LABEL.match(label)
        if category_match:
            category = category_match.group(1).lower()
        priority_match = PRIORITY_LABEL.match(label)
        if priority_match:
            priority = priority_match.group(1).lower()
    return {
        "iid": iid,
        "title": issue.get("title", f"Issue #{iid}"),
        "labels": issue.get("labels", []),
        "category": category,
        "priority": priority,
        "web_url": issue.get("web_url", project.issue_url(iid)),
    }


def is_valid_issue_cache_entry(entry: dict[str, Any]) -> bool:
    """Detect placeholder entries written after failed per-issue API calls."""
    if "priority" not in entry:
        return False
    if entry.get("labels"):
        return True
    title = entry.get("title", "")
    return not title.startswith("Issue #")


def issues_cache_needs_refresh(
    iids: set[int],
    issues_cache: dict[str, dict[str, Any]],
) -> bool:
    if not issues_cache:
        return True
    for iid in iids:
        entry = issues_cache.get(str(iid))
        if entry is None or not is_valid_issue_cache_entry(entry):
            return True
    return False


def fetch_all_gitlab_issues(client: ApiClient) -> dict[int, dict[str, Any]]:
    """Fetch all project issues in paginated batches (~5 requests total)."""
    project = client.project
    all_issues: dict[int, dict[str, Any]] = {}
    page = 1
    per_page = 100

    print("Fetching GitLab issue metadata (paginated)...")
    while True:
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}/issues"
            f"?state=all&per_page={per_page}&page={page}"
        )
        batch = client.get_json(url)
        if not batch:
            break

        for issue in batch:
            entry = parse_issue_entry(issue, project)
            all_issues[entry["iid"]] = entry

        print(f"  page {page}: {len(batch)} issues ({len(all_issues)} total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(1.0)

    return all_issues


def fetch_missing_issues_by_iids(
    client: ApiClient,
    missing_iids: set[int],
    issues_cache: dict[str, dict[str, Any]],
) -> None:
    """Fallback for credited issues not returned by the list endpoint."""
    if not missing_iids:
        return

    project = client.project
    print(f"Fetching {len(missing_iids)} missing issues via bulk iids[] lookup...")
    batch_size = 50
    sorted_iids = sorted(missing_iids)
    for start in range(0, len(sorted_iids), batch_size):
        chunk = sorted_iids[start : start + batch_size]
        params = "&".join(f"iids[]={iid}" for iid in chunk)
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}/issues"
            f"?{params}&per_page={batch_size}"
        )
        try:
            batch = client.get_json(url)
        except requests.HTTPError as exc:
            print(f"  warning: bulk fetch failed: {exc}", file=sys.stderr)
            continue
        for issue in batch:
            entry = parse_issue_entry(issue, project)
            issues_cache[str(entry["iid"])] = entry
        time.sleep(1.0)


def fetch_issue_metadata(
    client: ApiClient,
    iids: set[int],
    issues_cache: dict[str, dict[str, Any]],
    refresh: bool,
) -> dict[int, dict[str, Any]]:
    project = client.project
    if refresh or issues_cache_needs_refresh(iids, issues_cache):
        if refresh:
            print("Refreshing GitLab issue cache...")
        else:
            print("Issue cache is missing or invalid; refreshing...")
        all_issues = fetch_all_gitlab_issues(client)
        issues_cache = {str(iid): entry for iid, entry in all_issues.items()}
        save_issues_cache(project, issues_cache)

    missing = {iid for iid in iids if str(iid) not in issues_cache}
    if missing:
        fetch_missing_issues_by_iids(client, missing, issues_cache)
        save_issues_cache(project, issues_cache)

    still_missing = [iid for iid in iids if str(iid) not in issues_cache]
    if still_missing:
        print(
            f"  warning: {len(still_missing)} credited issues not found on GitLab: "
            f"{still_missing[:5]}{'...' if len(still_missing) > 5 else ''}",
            file=sys.stderr,
        )

    needs_mr = refresh or merge_request_metadata_incomplete(iids, issues_cache)
    if needs_mr:
        enrich_merge_request_metadata(
            client,
            issues_cache,
            iids,
            refresh=refresh,
        )
        save_issues_cache(project, issues_cache)

    return {iid: issues_cache[str(iid)] for iid in iids if str(iid) in issues_cache}


def in_period(closed_at: datetime, period: ReportPeriod) -> bool:
    if period.start and closed_at < period.start:
        return False
    if period.end and closed_at >= period.end:
        return False
    return True


def issue_closed_at_for_period(
    record: dict[str, Any],
    closed_issues: dict[int, dict[str, Any]],
) -> datetime:
    """Prefer GitLab close date over Drupal.org credit-finalized date."""
    iid = int(record["iid"])
    gitlab = closed_issues.get(iid, {})
    closed_raw = gitlab.get("closed_at") or record.get("closed_at")
    return parse_dt(closed_raw)


def build_period_report(
    period: ReportPeriod,
    records: list[dict[str, Any]],
    issue_meta: dict[int, dict[str, Any]],
    project: ProjectConfig,
    closed_issues: dict[int, dict[str, Any]] | None = None,
    ctx: Any | None = None,
) -> PeriodReport:
    from period_context import (
        PERIOD_SOURCE_MILESTONES,
        issue_in_milestone_release_period,
    )

    closed_lookup = closed_issues or {}
    use_milestones = ctx is not None and ctx.source == PERIOD_SOURCE_MILESTONES
    issues: list[CreditedIssue] = []
    for record in records:
        closed_at = issue_closed_at_for_period(record, closed_lookup)
        if use_milestones:
            if not issue_in_milestone_release_period(
                int(record["iid"]),
                period.title,
                ctx,
                closed_lookup,
                closed_at,
            ):
                continue
        elif not in_period(closed_at, period):
            continue
        iid = int(record["iid"])
        meta = issue_meta.get(iid, {})
        issues.append(
            CreditedIssue(
                uuid=record["uuid"],
                title=meta.get("title") or record["title"],
                iid=iid,
                closed_at=closed_at,
                category=meta.get("category"),
                priority=meta.get("priority"),
                issue_url=meta.get("web_url", project.issue_url(iid)),
                contributors=record.get("contributors", []),
            )
        )
    issues.sort(key=lambda item: item.iid)
    return PeriodReport(
        period=period,
        issues=issues,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def serialize_report(report: PeriodReport) -> dict[str, Any]:
    return {
        "period": {
            "slug": report.period.slug,
            "title": report.period.title,
            "start": report.period.start.isoformat() if report.period.start else None,
            "end": report.period.end.isoformat() if report.period.end else None,
            "frozen": report.period.frozen,
        },
        "generated_at": report.generated_at,
        "issues": [
            {
                "uuid": issue.uuid,
                "iid": issue.iid,
                "title": issue.title,
                "category": issue.category,
                "priority": issue.priority,
                "closed_at": issue.closed_at.isoformat(),
                "issue_url": issue.issue_url,
                "contributors": issue.contributors,
            }
            for issue in report.issues
        ],
        "user_counts": dict(report.user_counts),
        "org_counts": dict(report.org_counts),
    }


def deserialize_report(data: dict[str, Any]) -> PeriodReport:
    period_data = data["period"]
    period = ReportPeriod(
        slug=period_data["slug"],
        title=period_data["title"],
        start=parse_dt(period_data["start"]) if period_data.get("start") else None,
        end=parse_dt(period_data["end"]) if period_data.get("end") else None,
        frozen=period_data.get("frozen", False),
    )
    issues = [
        CreditedIssue(
            uuid=item["uuid"],
            title=item["title"],
            iid=int(item["iid"]),
            closed_at=parse_dt(item["closed_at"]),
            category=item.get("category"),
            priority=item.get("priority"),
            issue_url=item["issue_url"],
            contributors=item.get("contributors") or [
                {"user": user, "orgs": item.get("orgs", [])}
                for user in item.get("users", [])
            ],
        )
        for item in data.get("issues", [])
    ]
    return PeriodReport(period=period, issues=issues, generated_at=data["generated_at"])


def load_cached_period_reports(project: ProjectConfig) -> list[PeriodReport]:
    """Load all frozen period reports from cache."""
    if not project.periods_dir.is_dir():
        return []
    reports: list[PeriodReport] = []
    for path in sorted(project.periods_dir.glob("*.json")):
        data = load_json(path, {})
        if not data.get("period"):
            continue
        reports.append(deserialize_report(data))
    return reports


def is_individual_release_period(
    report: PeriodReport,
    project: ProjectConfig,
) -> bool:
    """Return whether a cached period is one release milestone, not a merge."""
    title = report.period.title
    if project.period_source == "milestones":
        return bool(re.match(project.milestone_include_pattern, title))
    return " through " not in title and " to " not in title


def aggregate_period_issues(reports: list[PeriodReport]) -> list[CreditedIssue]:
    """Merge issues from multiple periods, counting each issue once."""
    merged: dict[int, CreditedIssue] = {}
    for report in reports:
        for issue in report.issues:
            merged[issue.iid] = issue
    return sorted(merged.values(), key=lambda item: item.iid)


def build_aggregate_contributor_report(
    reports: list[PeriodReport],
) -> PeriodReport:
    issues = aggregate_period_issues(reports)
    return PeriodReport(
        period=ReportPeriod(
            slug="all-releases",
            title="All releases",
            start=None,
            end=None,
            frozen=True,
        ),
        issues=issues,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class ContributorIssueTier:
    label: str
    minimum: int
    maximum: int | None = None


CONTRIBUTOR_ISSUE_TIERS = (
    ContributorIssueTier("50+ issues", 50),
    ContributorIssueTier("25 to 49 issues", 25, 49),
    ContributorIssueTier("10 to 24 issues", 10, 24),
    ContributorIssueTier("2 to 9 issues", 2, 9),
    ContributorIssueTier("1 issue", 1, 1),
)


def count_in_contributor_tier(
    counts: Counter[str],
    tier: ContributorIssueTier,
) -> int:
    bucket = 0
    for count in counts.values():
        if count < tier.minimum:
            continue
        if tier.maximum is not None and count > tier.maximum:
            continue
        bucket += 1
    return bucket


def integer_percentages(bucket_counts: list[int], total: int) -> list[int]:
    """Whole-number percentages that always sum to 100."""
    if not total:
        return [0 for _ in bucket_counts]

    exact = [count / total * 100 for count in bucket_counts]
    rounded = [int(value) for value in exact]
    shortfall = 100 - sum(rounded)
    if shortfall:
        remainders = sorted(
            ((exact[index] - rounded[index], index) for index in range(len(exact))),
            reverse=True,
        )
        for _, index in remainders[:shortfall]:
            rounded[index] += 1
    return rounded


def format_contributor_tier_stats(
    counts: Counter[str],
    *,
    contributor_label: str,
) -> list[str]:
    """Return list items for issue-count distribution by contributor."""
    total = len(counts)
    if not total:
        return []

    bucket_counts = [
        count_in_contributor_tier(counts, tier) for tier in CONTRIBUTOR_ISSUE_TIERS
    ]
    percentages = integer_percentages(bucket_counts, total)
    items: list[str] = []
    for tier, percentage in zip(CONTRIBUTOR_ISSUE_TIERS, percentages):
        items.append(
            li(
                f"{percentage}% {contributor_label} contributed to "
                f"{tier.label}"
            )
        )
    return items


def render_contributors_totals_html(
    project: ProjectConfig,
    milestone_reports: list[PeriodReport],
    aggregate: PeriodReport,
    *,
    alias_resolver: DrupalProfileAliasResolver,
) -> str:
    """Running totals of credited people and organizations across all milestones."""
    user_profile_urls = build_user_profile_urls(aggregate, alias_resolver)
    org_profile_urls = build_org_profile_urls(aggregate, alias_resolver)
    partner_keys = load_ai_initiative_partner_keys()
    partner_orgs = ai_initiative_partner_orgs_in_report(aggregate, partner_keys)
    partner_people = ai_initiative_partner_people_in_report(aggregate, partner_orgs)

    milestone_rows: list[list[str]] = []
    for report in sorted(milestone_reports, key=lambda item: item.period.title):
        period = report.period
        milestone_rows.append(
            [
                period.title,
                str(len(report.issues)),
                str(len(report.user_counts)),
                str(len(report.org_counts)),
            ]
        )

    people = (
        format_people_counter(
            aggregate,
            user_profile_urls,
            mark_partner_users=partner_people,
        )
        or "none"
    )
    orgs = (
        format_org_counter(
            aggregate,
            org_profile_urls,
            mark_partner_orgs=partner_orgs,
        )
        or "none"
    )
    issue_count = len(aggregate.issues)
    milestone_count = len(milestone_reports)

    blocks = [
        h2("All releases — contributor totals"),
        p(
            f"Running totals across {strong(str(issue_count))} credited issues "
            f"in {strong(str(milestone_count))} milestones "
            "(each issue counted once)."
        ),
        p(em(f"Generated {aggregate.generated_at}")),
        h3(f"People ({len(aggregate.user_counts)})"),
        p(people),
    ]
    if partner_people:
        blocks.append(
            p(
                f"(*) {len(partner_people)} people are associated with an "
                "organization that is or was part of the Drupal AI Initiative"
            )
        )
    people_tier_stats = format_contributor_tier_stats(
        aggregate.user_counts,
        contributor_label="people",
    )
    if people_tier_stats:
        blocks.append(ul(people_tier_stats))
    blocks.extend(
        [
            h3(f"Organizations ({len(aggregate.org_counts)})"),
            p(orgs),
        ]
    )
    if partner_orgs:
        blocks.append(
            p(
                f"(*) {len(partner_orgs)} organizations are or were part of the "
                "Drupal AI Initiative"
            )
        )
    org_tier_stats = format_contributor_tier_stats(
        aggregate.org_counts,
        contributor_label="organizations",
    )
    if org_tier_stats:
        blocks.append(ul(org_tier_stats))
    if milestone_rows:
        blocks.extend(
            [
                h3("By milestone"),
                table(
                    ["Milestone", "Issues", "People", "Organizations"],
                    milestone_rows,
                ),
            ]
        )
    return join_blocks(blocks) + "\n"


def write_contributors_totals_report(
    project: ProjectConfig,
    *,
    alias_resolver: DrupalProfileAliasResolver,
) -> Path | None:
    """Write aggregate contributor reference HTML from cached period reports."""
    cached = load_cached_period_reports(project)
    milestone_reports = [
        report
        for report in cached
        if is_individual_release_period(report, project) and report.issues
    ]
    if not milestone_reports:
        return None

    aggregate = build_aggregate_contributor_report(milestone_reports)
    html = render_contributors_totals_html(
        project,
        milestone_reports,
        aggregate,
        alias_resolver=alias_resolver,
    )
    output_path = project.contributors_totals_report
    output_path.write_text(html)
    return output_path


def format_counter(counter: Counter[str]) -> str:
    return ", ".join(f"{name} ({count})" for name, count in counter.most_common())


def format_org_counter(
    report: PeriodReport,
    profile_urls: dict[str, str] | None = None,
    *,
    mark_partner_orgs: set[str] | None = None,
) -> str:
    org_counts = report.org_counts
    display_titles = report.org_display_titles
    profile_urls = profile_urls or report.org_profile_urls
    partner_marks = mark_partner_orgs or set()
    parts: list[str] = []
    for name, count in org_counts.most_common():
        display = display_titles.get(name, name)
        url = profile_urls.get(name)
        if name in partner_marks:
            label_text = f"{display} (*)"
        else:
            label_text = display
        label = a(url, label_text) if url else escape(label_text)
        parts.append(f"{label} ({count})")
    return ", ".join(parts)


def top_org_count_for_user(user: str, user_orgs: set[str], org_counts: Counter[str]) -> int:
    if not user_orgs:
        return 0
    return max(org_counts.get(org, 0) for org in user_orgs)


def format_people_counter(
    report: PeriodReport,
    profile_urls: dict[str, str] | None = None,
    *,
    mark_partner_users: set[str] | None = None,
) -> str:
    user_counts = report.user_counts
    org_counts = report.org_counts
    user_orgs = report.user_org_map
    display_names = report.user_display_names
    profile_urls = profile_urls or report.user_profile_urls
    partner_marks = mark_partner_users or set()

    sorted_users = sorted(
        user_counts.keys(),
        key=lambda user: (
            -user_counts[user],
            -top_org_count_for_user(user, user_orgs[user], org_counts),
            display_names.get(user, user).casefold(),
        ),
    )
    parts: list[str] = []
    for user in sorted_users:
        display = display_names.get(user, user)
        url = profile_urls.get(user)
        if user in partner_marks:
            label_text = f"{display} (*)"
        else:
            label_text = display
        label = a(url, label_text) if url else escape(label_text)
        parts.append(f"{label} ({user_counts[user]})")
    return ", ".join(parts)


def load_manual_list_exclusions(path: Path) -> set[int]:
    """Load issue numbers to hide from list sections but keep in Additional totals."""
    if not path.exists():
        return set()

    iids: set[int] = set()
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.search(r"(\d+)", stripped)
        if match:
            iids.add(int(match.group(1)))
    return iids


def is_excluded_from_other_major(title: str) -> bool:
    return bool(
        SPRINT_PLANNING_TITLE.search(title)
        or SESSION_OR_MEETING_TITLE.search(title)
        or CREATE_CCC_RELEASE_TITLE.search(title)
        or CCC_QA_TITLE.search(title)
    )


def is_other_major_contribution(issue: CreditedIssue) -> bool:
    if issue.category in FEATURE_CATEGORIES | BUG_CATEGORIES:
        return False
    if issue.priority not in HIGH_PRIORITIES:
        return False
    if is_excluded_from_other_major(issue.title):
        return False
    return True


def major_contribution_iids(issues: list[CreditedIssue]) -> set[int]:
    """Major non-feature/bug issues, including those hidden from display lists."""
    return {issue.iid for issue in issues if is_other_major_contribution(issue)}


def primary_release_iids(issues: list[CreditedIssue]) -> set[int]:
    """Feature, bug, and other-major issues (used to bucket the remainder)."""
    primary: set[int] = set()
    for issue in issues:
        if issue.category in FEATURE_CATEGORIES | BUG_CATEGORIES:
            primary.add(issue.iid)
        elif is_other_major_contribution(issue):
            primary.add(issue.iid)
    return primary


@dataclass
class ClassifiedReleaseIssues:
    features: list[CreditedIssue]
    bugs: list[CreditedIssue]
    other_major_display: list[CreditedIssue]
    other_major_accounted: list[CreditedIssue]
    additional_code_display: list[CreditedIssue]
    additional_code_accounted: int
    non_code_counts: Counter[str]
    non_code_uncategorized: int


def classify_release_issues(
    accountable: list[CreditedIssue],
    listable: list[CreditedIssue],
    issue_meta: dict[int, dict[str, Any]],
) -> ClassifiedReleaseIssues:
    features = [issue for issue in listable if issue.category in FEATURE_CATEGORIES]
    bugs = [issue for issue in listable if issue.category in BUG_CATEGORIES]
    other_major_display = [
        issue for issue in listable if is_other_major_contribution(issue)
    ]
    other_major_accounted = [
        issue for issue in accountable if is_other_major_contribution(issue)
    ]
    primary_iids = primary_release_iids(accountable)

    additional_code_display = [
        issue
        for issue in listable
        if issue.iid not in primary_iids
        and issue_has_merge_request(issue_meta.get(issue.iid, {}))
    ]
    additional_code_accounted = sum(
        1
        for issue in accountable
        if issue.iid not in primary_iids
        and issue_has_merge_request(issue_meta.get(issue.iid, {}))
    )

    non_code_counts: Counter[str] = Counter()
    non_code_uncategorized = 0
    for issue in accountable:
        if issue.iid in primary_iids:
            continue
        if issue_has_merge_request(issue_meta.get(issue.iid, {})):
            continue
        if issue.category in OTHER_CATEGORIES:
            non_code_counts[issue.category] += 1
        else:
            non_code_uncategorized += 1

    return ClassifiedReleaseIssues(
        features=features,
        bugs=bugs,
        other_major_display=other_major_display,
        other_major_accounted=other_major_accounted,
        additional_code_display=additional_code_display,
        additional_code_accounted=additional_code_accounted,
        non_code_counts=non_code_counts,
        non_code_uncategorized=non_code_uncategorized,
    )


def load_summary_paragraph(project: ProjectConfig, period_slug: str) -> str | None:
    """Load optional AI-written summary from summaries/{slug}.txt."""
    for suffix in (".txt", ".md"):
        path = project.summaries_dir / f"{period_slug}{suffix}"
        if path.exists():
            text = path.read_text().strip()
            if text:
                return text
    return None


def generate_factual_summary(
    period: ReportPeriod,
    *,
    total_issues: int,
    feature_count: int,
    bug_count: int,
    major_count: int,
    additional_code_count: int,
    non_code_counts: Counter[str],
    non_code_uncategorized: int,
) -> str:
    """Fallback summary from section counts when no summaries/{slug}.txt exists."""
    parts: list[str] = [
        f"This release ({period.title}) includes {total_issues} credited issues."
    ]
    breakdown: list[str] = []
    if feature_count:
        breakdown.append(f"{feature_count} new feature{'s' if feature_count != 1 else ''}")
    if bug_count:
        breakdown.append(f"{bug_count} bug fix{'es' if bug_count != 1 else ''}")
    if major_count:
        breakdown.append(
            f"{major_count} other major issue{'s' if major_count != 1 else ''}"
        )
    if additional_code_count:
        breakdown.append(
            f"{additional_code_count} additional code issue"
            f"{'s' if additional_code_count != 1 else ''}"
        )
    non_code_total = sum(non_code_counts.values()) + non_code_uncategorized
    if non_code_total:
        breakdown.append(
            f"{non_code_total} additional non-code contribution"
            f"{'s' if non_code_total != 1 else ''}"
        )
    if breakdown:
        parts.append("It includes " + ", ".join(breakdown) + ".")
    return " ".join(parts)


def write_summary_prompt(
    project: ProjectConfig,
    period: ReportPeriod,
    accountable: list[CreditedIssue],
    listable: list[CreditedIssue],
    issue_meta: dict[int, dict[str, Any]],
) -> Path:
    """Write a prompt file to feed to an AI for a prose release summary."""
    project.summaries_dir.mkdir(parents=True, exist_ok=True)
    path = project.summaries_dir / f"{period.slug}.prompt.md"
    classified = classify_release_issues(accountable, listable, issue_meta)
    primary_iids = primary_release_iids(accountable)
    non_code_issues = [
        issue
        for issue in accountable
        if issue.iid not in primary_iids
        and not issue_has_merge_request(issue_meta.get(issue.iid, {}))
    ]

    def group_lines(issues: list[CreditedIssue]) -> list[str]:
        return [
            f"- #{issue.iid}: {issue.title}"
            for issue in sorted(issues, key=lambda item: item.iid)
        ]

    def append_section(lines: list[str], heading: str, issues: list[CreditedIssue]) -> None:
        if not issues:
            return
        lines.extend([heading, *group_lines(issues), ""])

    lines = [
        f"# Summary prompt: {period.title}",
        "",
        "Write 1–2 paragraphs summarizing this release for Drupal.org release notes.",
        "Focus on user-facing value, major themes, and stability improvements.",
        "Do not list every issue; synthesize the work below.",
        "",
        f"Period: {period.title}",
        f"Credited issues in this report: {len(accountable)}",
        "",
    ]
    append_section(lines, "## New Features", classified.features)
    append_section(lines, "## Bug Fixes", classified.bugs)
    append_section(
        lines,
        "## Other Major Issues",
        classified.other_major_accounted,
    )
    append_section(
        lines,
        "## Additional Code Issues",
        classified.additional_code_display,
    )
    append_section(
        lines,
        "## Additional Non-Code Contributions (titles only)",
        non_code_issues,
    )
    lines.extend(
        [
            "---",
            "",
            f"Save the finished summary to: {project.machine_name}/summaries/{period.slug}.txt",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n")
    return path


def render_html(
    report: PeriodReport,
    project: ProjectConfig,
    exclude_from_lists: set[int] | None = None,
    *,
    issue_meta: dict[int, dict[str, Any]] | None = None,
    alias_resolver: DrupalProfileAliasResolver | None = None,
    releases: list[ReleaseBoundary] | None = None,
) -> str:
    manual_excludes = exclude_from_lists or set()
    accountable = report.issues
    listable = [issue for issue in accountable if issue.iid not in manual_excludes]
    meta = issue_meta or {}
    classified = classify_release_issues(accountable, listable, meta)

    feature_count = len([i for i in accountable if i.category in FEATURE_CATEGORIES])
    bug_count = len([i for i in accountable if i.category in BUG_CATEGORIES])
    major_count = len(classified.other_major_accounted)
    total_issues = len(accountable)

    summary = load_summary_paragraph(project, report.period.slug)
    if summary is None:
        summary = generate_factual_summary(
            report.period,
            total_issues=total_issues,
            feature_count=feature_count,
            bug_count=bug_count,
            major_count=major_count,
            additional_code_count=classified.additional_code_accounted,
            non_code_counts=classified.non_code_counts,
            non_code_uncategorized=classified.non_code_uncategorized,
        )

    blocks: list[str] = []
    if releases:
        compare = release_compare_versions(report.period, releases)
        if compare:
            since_version, until_version = compare
            blocks.append(
                p(
                    format_changes_since_line(
                        since_version,
                        since_url=project.drupal_release_url(since_version),
                        compare_url=project.gitlab_compare_url(
                            since_version,
                            until_version,
                        ),
                    )
                )
            )

    blocks.extend(
        [
            h2(report.period.title),
            p(strong(f"{total_issues} credited issues")),
            p(summary),
            p(em(f"Generated {report.generated_at}")),
        ]
    )

    if alias_resolver is None:
        client = ApiClient(project)
        alias_resolver = DrupalProfileAliasResolver(
            client,
            project.profile_aliases_cache,
        )
    user_profile_urls = build_user_profile_urls(report, alias_resolver)
    org_profile_urls = build_org_profile_urls(report, alias_resolver)
    alias_resolver.save()

    people = format_people_counter(report, user_profile_urls) or "none"
    orgs = format_org_counter(report, org_profile_urls) or "none"
    blocks.extend(
        [
            h3("Contributors"),
            p(f"{strong('People:')} {people}"),
            p(f"{strong('Organizations:')} {orgs}"),
        ]
    )

    if classified.features:
        blocks.append(h3(f"New Features ({len(classified.features)})"))
        blocks.append(
            ul(
                format_issue_item(issue.iid, issue.title, issue.issue_url)
                for issue in sorted(classified.features, key=lambda item: item.iid)
            )
        )

    if classified.bugs:
        blocks.append(h3(f"Bug Fixes ({len(classified.bugs)})"))
        blocks.append(
            ul(
                format_issue_item(issue.iid, issue.title, issue.issue_url)
                for issue in sorted(classified.bugs, key=lambda item: item.iid)
            )
        )

    if classified.other_major_display or classified.other_major_accounted:
        blocks.append(
            h3(f"Other Major Issues ({len(classified.other_major_accounted)})")
        )
        blocks.append(
            ul(
                format_issue_item(issue.iid, issue.title, issue.issue_url)
                for issue in sorted(
                    classified.other_major_display,
                    key=lambda item: item.iid,
                )
            )
        )

    if classified.additional_code_display or classified.additional_code_accounted:
        blocks.append(
            h3(
                f"Additional Code Issues ({classified.additional_code_accounted})"
            )
        )
        if classified.additional_code_display:
            blocks.append(
                ul(
                    format_issue_item(issue.iid, issue.title, issue.issue_url)
                    for issue in sorted(
                        classified.additional_code_display,
                        key=lambda item: item.iid,
                    )
                )
            )

    non_code_total = (
        sum(classified.non_code_counts.values())
        + classified.non_code_uncategorized
    )
    if non_code_total:
        blocks.append(
            h3(f"Additional Non-Code Contributions ({non_code_total})")
        )
        non_code_items = [
            li(f"{category.capitalize()}: {classified.non_code_counts[category]}")
            for category in ADDITIONAL_CATEGORY_ORDER
            if classified.non_code_counts.get(category, 0)
        ]
        if classified.non_code_uncategorized:
            non_code_items.append(
                li(
                    "Uncategorized credited issues: "
                    f"{classified.non_code_uncategorized}"
                )
            )
        blocks.append(ul(non_code_items))

    return join_blocks(blocks) + "\n"


def frozen_period_cache_stale(
    report: PeriodReport,
    records: list[dict[str, Any]],
    closed_issues: dict[int, dict[str, Any]] | None,
    ctx: Any | None,
) -> bool:
    """True when GitLab milestone assignments no longer match a frozen period cache."""
    from period_context import (
        PERIOD_SOURCE_MILESTONES,
        issue_in_milestone_release_period,
        issue_milestone_title,
    )

    if ctx is None or ctx.source != PERIOD_SOURCE_MILESTONES:
        return False

    closed_lookup = closed_issues or {}
    cached_iids = {issue.iid for issue in report.issues}

    for issue in report.issues:
        assigned = issue_milestone_title(closed_lookup.get(issue.iid, {}))
        if assigned and assigned != report.period.title:
            return True

    for record in records:
        iid = int(record["iid"])
        if iid in cached_iids:
            continue
        closed_at = issue_closed_at_for_period(record, closed_lookup)
        if issue_in_milestone_release_period(
            iid,
            report.period.title,
            ctx,
            closed_lookup,
            closed_at,
        ):
            return True

    return False


def load_or_build_period_report(
    client: ApiClient,
    period: ReportPeriod,
    records: list[dict[str, Any]],
    issue_meta: dict[int, dict[str, Any]],
    rebuild_frozen: bool,
    closed_issues: dict[int, dict[str, Any]] | None = None,
    ctx: Any | None = None,
) -> PeriodReport:
    project = client.project
    cache_path = project.periods_dir / f"{period.slug}.json"
    if period.frozen and cache_path.exists() and not rebuild_frozen:
        cached = deserialize_report(load_json(cache_path, {}))
        if frozen_period_cache_stale(cached, records, closed_issues, ctx):
            print(
                f"Rebuilding {period.slug}: milestone assignments changed "
                "since this period was frozen."
            )
        else:
            print(f"Using frozen cache for {period.slug}")
            return cached

    report = build_period_report(
        period,
        records,
        issue_meta,
        project,
        closed_issues=closed_issues,
        ctx=ctx,
    )
    save_json(cache_path, serialize_report(report))
    print(
        f"Built {period.slug}: {len(report.issues)} credited issues, "
        f"{len(report.user_counts)} people, {len(report.org_counts)} organizations"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help=(
            "Full refresh: re-fetch contribution records, GitLab issues, profile "
            "aliases, rebuild all period caches and reports, refresh the credit "
            "audit cache and report, and run release prep for the current milestone."
        ),
    )
    parser.add_argument(
        "--refresh-records",
        action="store_true",
        help="Re-fetch all contribution records from new.drupal.org.",
    )
    parser.add_argument(
        "--refresh-issues",
        action="store_true",
        help="Re-fetch GitLab issue metadata even if cached.",
    )
    parser.add_argument(
        "--refresh-aliases",
        action="store_true",
        help="Re-fetch Drupal.org profile URL aliases (api-d7) even if cached.",
    )
    parser.add_argument(
        "--rebuild-frozen",
        action="store_true",
        help="Recompute all completed (non-current) release periods.",
    )
    parser.add_argument(
        "--period",
        default="all",
        help=(
            "Report period to generate, or 'all'. "
            "With period_source milestones: GitLab milestone title "
            '(e.g. "1.0.0-beta3"). With releases: slug from Drupal.org tags '
            "(e.g. beta2-to-now)."
        ),
    )
    parser.add_argument(
        "--exclude-list",
        type=Path,
        default=None,
        help="Path to issue exclusion list (default: {project}/exclude_from_lists.txt).",
    )
    parser.add_argument(
        "--write-summary-prompts",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    add_project_argument(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_all:
        args.refresh_records = True
        args.refresh_issues = True
        args.refresh_aliases = True
        args.rebuild_frozen = True

    project = ProjectConfig.load(args.project)
    project.ensure_dirs()
    exclude_list = args.exclude_list or project.exclude_list_file

    from period_context import (
        PERIOD_SOURCE_MILESTONES,
        build_period_context,
        build_report_periods,
        migrate_legacy_period_files,
        select_report_periods,
    )

    client = ApiClient(project)
    ctx = build_period_context(project, client)
    migrate_legacy_period_files(project, ctx)
    releases = ctx.releases
    periods = build_report_periods(ctx, project)
    if ctx.source == PERIOD_SOURCE_MILESTONES:
        print(
            "Release notes use GitLab milestone titles "
            f"({ctx.source}); close date is used only when unassigned."
        )
    release_summary = ", ".join(release.version for release in releases)
    print(f"Release boundaries from Drupal.org: {release_summary}")
    if args.period != "all":
        matching = select_report_periods(args.period, periods)
        if not matching:
            available = ", ".join(period.slug for period in periods)
            print(
                f"Unknown period {args.period!r}. Available: {available}",
                file=sys.stderr,
            )
            return 1
        periods = matching

    records = fetch_contribution_records(client, refresh=args.refresh_records)
    iids = {int(record["iid"]) for record in records}
    issues_cache = load_issues_cache(project)
    needs_issue_refresh = args.refresh_issues or issues_cache_needs_refresh(iids, issues_cache)
    issue_meta = fetch_issue_metadata(client, iids, issues_cache, refresh=needs_issue_refresh)
    rebuild_frozen = args.rebuild_frozen or needs_issue_refresh

    closed_issues: dict[int, dict[str, Any]] = {}
    if project.period_source == PERIOD_SOURCE_MILESTONES:
        from credit_audit import load_cached_closed_issues
        from period_context import enrich_closed_issues_milestones

        closed_issues = load_cached_closed_issues(project)
        if not closed_issues:
            print(
                "Warning: no closed GitLab issues cache; run "
                "python3 scripts/credit_audit.py --refresh",
                file=sys.stderr,
            )
        elif ctx.source == PERIOD_SOURCE_MILESTONES:
            closed_issues = enrich_closed_issues_milestones(
                client,
                closed_issues,
                iids,
                refresh_credited=args.refresh_issues or args.refresh_all,
            )
            save_json(
                project.closed_issues_cache,
                {str(iid): issue for iid, issue in closed_issues.items()},
            )

    exclude_from_lists = load_manual_list_exclusions(exclude_list)
    if exclude_from_lists:
        print(f"Loaded {len(exclude_from_lists)} manual list exclusions from {exclude_list}.")

    alias_resolver = DrupalProfileAliasResolver(
        client,
        project.profile_aliases_cache,
        refresh=args.refresh_aliases,
    )

    for period in periods:
        report = load_or_build_period_report(
            client,
            period,
            records,
            issue_meta,
            rebuild_frozen=rebuild_frozen,
            closed_issues=closed_issues,
            ctx=ctx,
        )
        html = render_html(
            report,
            project,
            exclude_from_lists=exclude_from_lists,
            issue_meta=issue_meta,
            alias_resolver=alias_resolver,
            releases=releases,
        )
        output_path = project.release_notes_report(period.slug)
        output_path.write_text(html)
        print(f"Wrote {output_path}")

        accountable = report.issues
        listable = [issue for issue in accountable if issue.iid not in exclude_from_lists]
        prompt_path = write_summary_prompt(
            project,
            report.period,
            accountable,
            listable,
            issue_meta,
        )
        print(f"Wrote {prompt_path}")

    totals_path = write_contributors_totals_report(
        project,
        alias_resolver=alias_resolver,
    )
    if totals_path:
        print(f"Wrote {totals_path}")

    if args.refresh_all:
        print("\n--- Refreshing credit audit ---")
        audit_script = REPO_ROOT / "scripts" / "credit_audit.py"
        result = subprocess.run(
            [
                sys.executable,
                str(audit_script),
                "--project",
                project.machine_name,
                "--refresh",
                "--refresh-comments",
            ],
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            return result.returncode

        if ctx.source == PERIOD_SOURCE_MILESTONES:
            from period_context import current_milestone_title

            current_milestone = current_milestone_title(ctx)
            if current_milestone:
                print(
                    f"\n--- Refreshing release prep ({current_milestone}) ---"
                )
                prep_script = REPO_ROOT / "scripts" / "release_prep.py"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(prep_script),
                        "--project",
                        project.machine_name,
                        "--milestone",
                        current_milestone,
                    ],
                    cwd=REPO_ROOT,
                )
                if result.returncode != 0:
                    return result.returncode

            from credit_audit import load_cached_closed_issues

            closed_issues = load_cached_closed_issues(project)

    if ctx.source == PERIOD_SOURCE_MILESTONES and closed_issues:
        from release_prep import write_milestone_support_reports

        for path in write_milestone_support_reports(project, ctx, closed_issues):
            print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
