#!/usr/bin/env python3
"""Generate ai_context release credit reports from Drupal.org APIs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import requests

USER_AGENT = "issue-credit-report/1.0 (+https://www.drupal.org/project/ai_context)"
PROJECT_MACHINE_NAME = "ai_context"
PROJECT_NID = 3546505
GITLAB_PROJECT = "project/ai_context"
GITLAB_PROJECT_ENCODED = quote(GITLAB_PROJECT, safe="")
ISSUE_URL = "https://git.drupalcode.org/project/ai_context/-/work_items/{iid}"

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
SUMMARIES_DIR = ROOT / "summaries"
EXCLUDE_LIST_FILE = ROOT / "exclude_from_lists.txt"
ISSUES_CACHE = CACHE_DIR / "issues.json"
RECORDS_CACHE = CACHE_DIR / "contribution_records.json"
STATE_FILE = CACHE_DIR / "state.json"
PERIODS_DIR = CACHE_DIR / "periods"

CATEGORY_LABEL = re.compile(r"^category::(\w+)$")
PRIORITY_LABEL = re.compile(r"^priority::(\w+)$")
ISSUE_IID = re.compile(
    r"(?:git\.drupalcode\.org/project/ai_context/-/work_items/(\d+)"
    r"|www\.drupal\.org/(?:node|project/[^/]+/issues)/(\d+))"
)

FEATURE_CATEGORIES = {"feature"}
BUG_CATEGORIES = {"bug"}
OTHER_CATEGORIES = {"plan", "task", "support", "discuss"}
HIGH_PRIORITIES = {"critical", "major"}
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
            orgs.extend(entry.get("orgs", []))
        return orgs

    @property
    def user_org_map(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = defaultdict(set)
        for entry in self.contributors:
            user = entry.get("user")
            if user:
                mapping[user].update(entry.get("orgs", []))
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


class ApiClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        headers = {"User-Agent": USER_AGENT}
        gitlab_token = os.environ.get("GITLAB_TOKEN") or os.environ.get("GITLAB_PRIVATE_TOKEN")
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


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize_username(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


def normalize_org(title: str) -> str:
    return title.strip().lower()


def issue_iid_from_link(uri: str) -> int | None:
    match = ISSUE_IID.search(uri)
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def fetch_release_boundaries(client: ApiClient) -> list[ReleaseBoundary]:
    """Load tagged releases from Drupal.org (same data as /project/ai_context/releases)."""
    url = (
        "https://www.drupal.org/api-d7/node.json"
        f"?type=project_release&field_release_project={PROJECT_NID}"
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


def build_periods(releases: list[ReleaseBoundary]) -> list[ReportPeriod]:
    if not releases:
        raise RuntimeError(
            "No tagged releases found on Drupal.org for ai_context. "
            "See https://www.drupal.org/project/ai_context/releases"
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


def index_included(included: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in included:
        indexed[item["type"]][item["id"]] = item
    return indexed


def parse_credited_contributors(
    record: dict[str, Any],
    included_index: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    contributors: list[dict[str, Any]] = []
    contributor_refs = record.get("relationships", {}).get("field_contributors", {}).get("data", [])

    for ref in contributor_refs:
        paragraph = included_index.get("paragraph--contributor", {}).get(ref["id"])
        if not paragraph:
            continue
        attrs = paragraph.get("attributes", {})
        if not attrs.get("field_credit_this_contributor"):
            continue

        user_name = None
        user_ref = paragraph.get("relationships", {}).get("field_contributor_user", {}).get("data")
        if user_ref:
            user = included_index.get("user--user", {}).get(user_ref["id"])
            if user:
                git_username = user["attributes"].get("field_git_username")
                display = user["attributes"].get("display_name") or user["attributes"].get("name")
                if git_username:
                    user_name = normalize_username(git_username)
                elif display:
                    user_name = normalize_username(display)

        orgs: list[str] = []
        org_refs = paragraph.get("relationships", {}).get("field_contributor_organisation", {}).get("data") or []
        customer_refs = paragraph.get("relationships", {}).get("field_contributor_customer", {}).get("data") or []
        for org_ref in org_refs + customer_refs:
            org = included_index.get("node--organization", {}).get(org_ref["id"])
            if org and org.get("attributes", {}).get("title"):
                orgs.append(normalize_org(org["attributes"]["title"]))

        if user_name or orgs:
            contributors.append({"user": user_name, "orgs": orgs})

    return contributors


def fetch_contribution_records(client: ApiClient, refresh: bool) -> list[dict[str, Any]]:
    if RECORDS_CACHE.exists() and not refresh:
        cached = load_json(RECORDS_CACHE, [])
        if cached and "contributors" not in cached[0]:
            print("Contribution record cache uses old format; refreshing...")
            refresh = True
        elif cached:
            print(f"Loaded {len(cached)} contribution records from cache.")
            return cached

    print("Fetching contribution records from new.drupal.org...")
    start_url = (
        "https://new.drupal.org/jsonapi/node/contribution_record"
        f"?filter[field_project_name]={PROJECT_MACHINE_NAME}"
        "&filter[field_draft]=0"
        "&include=field_contributors,field_contributors.field_contributor_user,"
        "field_contributors.field_contributor_organisation,field_contributors.field_contributor_customer"
        "&page[limit]=50"
    )

    parsed_records: list[dict[str, Any]] = []
    url: str | None = start_url
    page = 0
    while url:
        payload = client.get_jsonapi(url)
        included_index = index_included(payload.get("included", []))
        for record in payload.get("data", []):
            attrs = record.get("attributes", {})
            closed_raw = attrs.get("field_last_status_change")
            source = attrs.get("field_source_link", {}).get("uri")
            if not closed_raw or not source:
                continue

            contributors = parse_credited_contributors(record, included_index)
            if not contributors:
                continue

            iid = issue_iid_from_link(source)
            if not iid:
                continue

            parsed_records.append(
                {
                    "uuid": record["id"],
                    "nid": attrs.get("drupal_internal__nid"),
                    "title": attrs.get("title", f"Issue #{iid}"),
                    "closed_at": closed_raw,
                    "source_link": source,
                    "iid": iid,
                    "contributors": contributors,
                }
            )

        page += 1
        print(f"  page {page}: {len(parsed_records)} credited records so far")
        url = payload.get("links", {}).get("next", {}).get("href")
        time.sleep(0.1)

    save_json(RECORDS_CACHE, parsed_records)
    save_json(
        STATE_FILE,
        {
            "records_cached_at": datetime.now(tz=timezone.utc).isoformat(),
            "record_count": len(parsed_records),
        },
    )
    print(f"Cached {len(parsed_records)} credited contribution records.")
    return parsed_records


def load_issues_cache() -> dict[str, dict[str, Any]]:
    return load_json(ISSUES_CACHE, {})


def save_issues_cache(cache: dict[str, dict[str, Any]]) -> None:
    save_json(ISSUES_CACHE, cache)


def parse_issue_entry(issue: dict[str, Any]) -> dict[str, Any]:
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
        "web_url": issue.get("web_url", ISSUE_URL.format(iid=iid)),
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
    all_issues: dict[int, dict[str, Any]] = {}
    page = 1
    per_page = 100

    print("Fetching GitLab issue metadata (paginated)...")
    while True:
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/issues"
            f"?state=all&per_page={per_page}&page={page}"
        )
        batch = client.get_json(url)
        if not batch:
            break

        for issue in batch:
            entry = parse_issue_entry(issue)
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

    print(f"Fetching {len(missing_iids)} missing issues via bulk iids[] lookup...")
    batch_size = 50
    sorted_iids = sorted(missing_iids)
    for start in range(0, len(sorted_iids), batch_size):
        chunk = sorted_iids[start : start + batch_size]
        params = "&".join(f"iids[]={iid}" for iid in chunk)
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/issues"
            f"?{params}&per_page={batch_size}"
        )
        try:
            batch = client.get_json(url)
        except requests.HTTPError as exc:
            print(f"  warning: bulk fetch failed: {exc}", file=sys.stderr)
            continue
        for issue in batch:
            entry = parse_issue_entry(issue)
            issues_cache[str(entry["iid"])] = entry
        time.sleep(1.0)


def fetch_issue_metadata(
    client: ApiClient,
    iids: set[int],
    issues_cache: dict[str, dict[str, Any]],
    refresh: bool,
) -> dict[int, dict[str, Any]]:
    if refresh or issues_cache_needs_refresh(iids, issues_cache):
        if refresh:
            print("Refreshing GitLab issue cache...")
        else:
            print("Issue cache is missing or invalid; refreshing...")
        all_issues = fetch_all_gitlab_issues(client)
        issues_cache = {str(iid): entry for iid, entry in all_issues.items()}
        save_issues_cache(issues_cache)

    missing = {iid for iid in iids if str(iid) not in issues_cache}
    if missing:
        fetch_missing_issues_by_iids(client, missing, issues_cache)
        save_issues_cache(issues_cache)

    still_missing = [iid for iid in iids if str(iid) not in issues_cache]
    if still_missing:
        print(
            f"  warning: {len(still_missing)} credited issues not found on GitLab: "
            f"{still_missing[:5]}{'...' if len(still_missing) > 5 else ''}",
            file=sys.stderr,
        )

    return {iid: issues_cache[str(iid)] for iid in iids if str(iid) in issues_cache}


def in_period(closed_at: datetime, period: ReportPeriod) -> bool:
    if period.start and closed_at < period.start:
        return False
    if period.end and closed_at >= period.end:
        return False
    return True


def build_period_report(
    period: ReportPeriod,
    records: list[dict[str, Any]],
    issue_meta: dict[int, dict[str, Any]],
) -> PeriodReport:
    issues: list[CreditedIssue] = []
    for record in records:
        closed_at = parse_dt(record["closed_at"])
        if not in_period(closed_at, period):
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
                issue_url=meta.get("web_url", ISSUE_URL.format(iid=iid)),
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


def format_counter(counter: Counter[str]) -> str:
    return ", ".join(f"{name} ({count})" for name, count in counter.most_common())


def top_org_count_for_user(user: str, user_orgs: set[str], org_counts: Counter[str]) -> int:
    if not user_orgs:
        return 0
    return max(org_counts.get(org, 0) for org in user_orgs)


def format_people_counter(report: PeriodReport) -> str:
    user_counts = report.user_counts
    org_counts = report.org_counts
    user_orgs = report.user_org_map

    sorted_users = sorted(
        user_counts.keys(),
        key=lambda user: (
            -user_counts[user],
            -top_org_count_for_user(user, user_orgs[user], org_counts),
            user,
        ),
    )
    return ", ".join(f"{user} ({user_counts[user]})" for user in sorted_users)


def load_manual_list_exclusions(path: Path = EXCLUDE_LIST_FILE) -> set[int]:
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


def load_summary_paragraph(period_slug: str) -> str | None:
    """Load optional AI-written summary from summaries/{slug}.txt."""
    for suffix in (".txt", ".md"):
        path = SUMMARIES_DIR / f"{period_slug}{suffix}"
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
    other_counts: Counter[str],
    uncategorized_count: int,
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
            f"{major_count} other major contribution{'s' if major_count != 1 else ''}"
        )
    additional = sum(other_counts.values()) + uncategorized_count
    if additional:
        breakdown.append(f"{additional} additional contribution{'s' if additional != 1 else ''}")
    if breakdown:
        parts.append("It includes " + ", ".join(breakdown) + ".")
    return " ".join(parts)


def write_summary_prompt(
    period: ReportPeriod,
    accountable: list[CreditedIssue],
    major_iids: set[int],
    listable: list[CreditedIssue],
) -> Path:
    """Write a prompt file to feed to an AI for a prose release summary."""
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    path = SUMMARIES_DIR / f"{period.slug}.prompt.md"

    def group_lines(issues: list[CreditedIssue]) -> list[str]:
        return [
            f"- #{issue.iid}: {issue.title}"
            for issue in sorted(issues, key=lambda item: item.iid)
        ]

    features = [i for i in listable if i.category in FEATURE_CATEGORIES]
    bugs = [i for i in listable if i.category in BUG_CATEGORIES]
    major = [i for i in accountable if i.iid in major_iids]
    other: list[CreditedIssue] = []
    for issue in accountable:
        if issue.iid in major_iids:
            continue
        if issue.category in OTHER_CATEGORIES:
            other.append(issue)

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
    append_section(lines, "## New Features", features)
    append_section(lines, "## Bug Fixes", bugs)
    append_section(lines, "## Other Major Contributions", major)
    append_section(lines, "## Additional Contributions (titles only)", other)
    lines.extend(
        [
            "---",
            "",
            f"Save the finished summary to: summaries/{period.slug}.txt",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n")
    return path


def render_markdown(
    report: PeriodReport,
    exclude_from_lists: set[int] | None = None,
) -> str:
    manual_excludes = exclude_from_lists or set()
    accountable = report.issues
    major_iids = major_contribution_iids(report.issues)
    listable = [issue for issue in accountable if issue.iid not in manual_excludes]

    features = [issue for issue in listable if issue.category in FEATURE_CATEGORIES]
    bugs = [issue for issue in listable if issue.category in BUG_CATEGORIES]
    other_major_display = [issue for issue in listable if is_other_major_contribution(issue)]
    other_major_accounted = [issue for issue in accountable if is_other_major_contribution(issue)]
    other_counts = Counter(
        issue.category
        for issue in accountable
        if issue.category in OTHER_CATEGORIES and issue.iid not in major_iids
    )
    uncategorized = [
        issue
        for issue in accountable
        if issue.category not in FEATURE_CATEGORIES | BUG_CATEGORIES | OTHER_CATEGORIES
        and issue.iid not in major_iids
    ]

    feature_count = len([i for i in accountable if i.category in FEATURE_CATEGORIES])
    bug_count = len([i for i in accountable if i.category in BUG_CATEGORIES])
    major_count = len(other_major_accounted)
    total_issues = len(accountable)

    summary = load_summary_paragraph(report.period.slug)
    if summary is None:
        summary = generate_factual_summary(
            report.period,
            total_issues=total_issues,
            feature_count=feature_count,
            bug_count=bug_count,
            major_count=major_count,
            other_counts=other_counts,
            uncategorized_count=len(uncategorized),
        )

    lines: list[str] = [
        f"# {report.period.title}",
        "",
        f"**{total_issues} credited issues**",
        "",
        summary,
        "",
        f"_Generated {report.generated_at}_",
        "",
    ]

    if features:
        lines.extend([f"## New Features ({len(features)})", ""])
        for issue in sorted(features, key=lambda item: item.iid):
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
        lines.append("")

    if bugs:
        lines.extend([f"## Bug Fixes ({len(bugs)})", ""])
        for issue in sorted(bugs, key=lambda item: item.iid):
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
        lines.append("")

    if other_major_display or other_major_accounted:
        lines.extend(
            [f"## Other Major Contributions ({len(other_major_accounted)})", ""]
        )
        for issue in sorted(other_major_display, key=lambda item: item.iid):
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
        lines.append("")

    lines.extend(["## Additional Contributions", ""])
    for category in ("plan", "task", "support", "discuss"):
        count = other_counts.get(category, 0)
        label = category.capitalize()
        lines.append(f"* {label}: {count}")
    if uncategorized:
        lines.append(f"* Uncategorized credited issues: {len(uncategorized)}")
    lines.append("")

    lines.extend(
        [
            "## Contributors",
            "",
            f"**People:** {format_people_counter(report) or 'none'}",
            "",
            f"**Organizations:** {format_counter(report.org_counts) or 'none'}",
            "",
        ]
    )
    return "\n".join(lines)


def load_or_build_period_report(
    period: ReportPeriod,
    records: list[dict[str, Any]],
    issue_meta: dict[int, dict[str, Any]],
    rebuild_frozen: bool,
) -> PeriodReport:
    cache_path = PERIODS_DIR / f"{period.slug}.json"
    if period.frozen and cache_path.exists() and not rebuild_frozen:
        print(f"Using frozen cache for {period.slug}")
        return deserialize_report(load_json(cache_path, {}))

    report = build_period_report(period, records, issue_meta)
    save_json(cache_path, serialize_report(report))
    print(
        f"Built {period.slug}: {len(report.issues)} credited issues, "
        f"{len(report.user_counts)} people, {len(report.org_counts)} organizations"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
        "--rebuild-frozen",
        action="store_true",
        help="Recompute all completed (non-current) release periods.",
    )
    parser.add_argument(
        "--period",
        default="all",
        help=(
            "Report period slug to generate, or 'all'. "
            "Slugs are derived from Drupal.org releases (e.g. beta2-to-now)."
        ),
    )
    parser.add_argument(
        "--exclude-list",
        type=Path,
        default=EXCLUDE_LIST_FILE,
        help="Path to issue exclusion list (default: exclude_from_lists.txt).",
    )
    parser.add_argument(
        "--write-summary-prompts",
        action="store_true",
        help=(
            "Write summaries/{period}.prompt.md files for AI-assisted prose summaries."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = ApiClient()
    releases = fetch_release_boundaries(client)
    periods = build_periods(releases)
    release_summary = ", ".join(release.version for release in releases)
    print(f"Release boundaries from Drupal.org: {release_summary}")
    if args.period != "all":
        matching = [period for period in periods if period.slug == args.period]
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
    issues_cache = load_issues_cache()
    needs_issue_refresh = args.refresh_issues or issues_cache_needs_refresh(iids, issues_cache)
    issue_meta = fetch_issue_metadata(client, iids, issues_cache, refresh=needs_issue_refresh)
    rebuild_frozen = args.rebuild_frozen or needs_issue_refresh
    exclude_from_lists = load_manual_list_exclusions(args.exclude_list)
    if exclude_from_lists:
        print(f"Loaded {len(exclude_from_lists)} manual list exclusions from {args.exclude_list}.")

    for period in periods:
        report = load_or_build_period_report(
            period,
            records,
            issue_meta,
            rebuild_frozen=rebuild_frozen,
        )
        markdown = render_markdown(report, exclude_from_lists=exclude_from_lists)
        output_path = OUTPUT_DIR / f"{period.slug}.md"
        output_path.write_text(markdown)
        print(f"Wrote {output_path}")

        if args.write_summary_prompts:
            accountable = report.issues
            major_iids = major_contribution_iids(report.issues)
            listable = [issue for issue in accountable if issue.iid not in exclude_from_lists]
            prompt_path = write_summary_prompt(
                report.period,
                accountable,
                major_iids,
                listable,
            )
            print(f"Wrote {prompt_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
