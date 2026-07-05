#!/usr/bin/env python3
"""Audit Drupal project issue credits and track reviewed approvals."""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from gitlab_activity import (
    enrich_issues_with_gitlab_activity,
    format_user_activity_lines,
)
from html_report import (
    a,
    code,
    em,
    escape,
    format_issue_item,
    h2,
    h3,
    join_blocks,
    li,
    p,
    pre_block,
    strong,
    ul,
)
from project import ProjectConfig, add_project_argument
from release_notes import (
    ApiClient,
    clear_gitlab_token_from_keyring,
    fetch_contribution_records_for_issue,
    fetch_project_contribution_records,
    gitlab_token_configured,
    gitlab_token_setup_hint,
    load_json,
    normalize_username,
    prompt_and_store_gitlab_token,
    save_json,
    upsert_release_record_cache_for_issue,
)

CREDIT_EXEMPT_WHY_LABELS = {
    "why::duplicate": "duplicate",
    "why::wontFix": "won't fix",
    "why::worksAsDesigned": "works as designed",
}


@dataclass
class AuditIssue:
    iid: int
    title: str
    issue_url: str
    closed_at: str | None
    record_nid: int | None
    record_url: str | None
    credited: list[str] = field(default_factory=list)
    uncredited: list[str] = field(default_factory=list)
    problem: str = "ok"
    labels: list[str] = field(default_factory=list)
    exemption: str | None = None
    duplicate_nids: list[int] = field(default_factory=list)
    ignored_uncredited: list[str] = field(default_factory=list)
    user_activity: dict[str, Any] = field(default_factory=dict)

    @property
    def pending_uncredited(self) -> list[str]:
        return self.uncredited


def resolve_issue_labels(
    iid: int,
    closed_issue: dict[str, Any],
    issues_cache: dict[str, dict[str, Any]],
) -> list[str]:
    labels = closed_issue.get("labels") or []
    if labels:
        return list(labels)
    return list(issues_cache.get(str(iid), {}).get("labels") or [])


def credit_exemption_reason(labels: list[str]) -> str | None:
    for label in labels:
        if label in CREDIT_EXEMPT_WHY_LABELS:
            return CREDIT_EXEMPT_WHY_LABELS[label]
    return None


def load_ignored_uncredited_people(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ignored: set[str] = set()
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        ignored.add(normalize_username(stripped))
    return ignored


def split_uncredited_people(
    uncredited: list[str],
    approved_users: set[str],
    ignored_users: set[str],
) -> tuple[list[str], list[str]]:
    pending: list[str] = []
    ignored_only: list[str] = []
    for user in uncredited:
        normalized = normalize_username(user)
        if normalized in approved_users:
            continue
        if normalized in ignored_users:
            ignored_only.append(user)
            continue
        pending.append(user)
    return pending, ignored_only


def merge_records_by_iid(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine duplicate contribution records that point at the same issue."""
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[int(record["iid"])].append(record)

    merged: list[dict[str, Any]] = []
    for iid in sorted(grouped):
        group = grouped[iid]
        if len(group) == 1:
            merged.append(group[0])
            continue

        credited: set[str] = set()
        uncredited: set[str] = set()
        duplicate_nids: list[int] = []
        for record in group:
            credited.update(record.get("credited") or [])
            uncredited.update(record.get("uncredited") or [])
            nid = record.get("nid")
            if nid is not None:
                duplicate_nids.append(int(nid))
        uncredited -= credited

        def record_score(rec: dict[str, Any]) -> tuple[int, int, int]:
            return (
                len(rec.get("credited") or []),
                -len(rec.get("uncredited") or []),
                int(rec.get("nid") or 0),
            )

        best = max(group, key=record_score)
        merged.append(
            {
                **best,
                "credited": sorted(credited),
                "uncredited": sorted(uncredited),
                "duplicate_nids": sorted(set(duplicate_nids)),
            }
        )

    return merged


def index_records_by_iid(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(record["iid"]): record for record in merge_records_by_iid(records)}


def load_cached_audit_records(project: ProjectConfig) -> list[dict[str, Any]]:
    """Load merged audit records from cache without printing status."""
    if not project.audit_records_cache.exists():
        return []
    return merge_records_by_iid(load_json(project.audit_records_cache, []))


def load_cached_closed_issues(project: ProjectConfig) -> dict[int, dict[str, Any]]:
    """Load closed GitLab issues from cache without printing status."""
    if not project.closed_issues_cache.exists():
        return {}
    cached = load_json(project.closed_issues_cache, {})
    return {int(iid): issue for iid, issue in cached.items()}


@dataclass(frozen=True)
class MissingContributionRecord:
    iid: int
    title: str
    issue_url: str


def closed_issues_missing_records(
    records: list[dict[str, Any]],
    closed_issues: dict[int, dict[str, Any]],
    issues_cache: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[MissingContributionRecord], list[MissingContributionRecord]]:
    """Closed GitLab issues with no contribution record on new.drupal.org.

    Returns (needs_record, exempt). Exempt issues carry duplicate / won't fix
    labels where no Drupal.org record is expected.
    """
    known = {int(record["iid"]) for record in merge_records_by_iid(records)}
    label_cache = issues_cache or {}
    needs_record: list[MissingContributionRecord] = []
    exempt: list[MissingContributionRecord] = []
    for iid in sorted(closed_issues):
        if iid in known:
            continue
        issue = closed_issues[iid]
        entry = MissingContributionRecord(
            iid=iid,
            title=issue.get("title", f"Issue #{iid}"),
            issue_url=issue.get("web_url", ""),
        )
        labels = resolve_issue_labels(iid, issue, label_cache)
        if credit_exemption_reason(labels):
            exempt.append(entry)
        else:
            needs_record.append(entry)
    return needs_record, exempt


def duplicate_contribution_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Contribution records where multiple Drupal.org nodes point at one issue."""
    return [
        record for record in records if len(record.get("duplicate_nids") or []) > 1
    ]


def format_duplicate_record_line(record: dict[str, Any]) -> str:
    nids = record.get("duplicate_nids") or []
    nid_links = ", ".join(f"https://new.drupal.org/node/{nid}" for nid in nids)
    return f"  #{record['iid']}: {record['title']} — {nid_links}"


def fetch_audit_records(client: ApiClient, refresh: bool) -> list[dict[str, Any]]:
    project = client.project
    if project.audit_records_cache.exists() and not refresh:
        cached = merge_records_by_iid(load_json(project.audit_records_cache, []))
        if cached:
            raw_count = len(load_json(project.audit_records_cache, []))
            if raw_count != len(cached):
                save_json(project.audit_records_cache, cached)
                print(
                    f"Merged {raw_count} cached records into {len(cached)} issues "
                    "(duplicate contribution records per issue)."
                )
            else:
                print(f"Loaded {len(cached)} contribution records from audit cache.")
            return cached

    print("Fetching all contribution records for credit audit...")
    summaries = fetch_project_contribution_records(client, require_credits=False)
    parsed_records = [
        {
            "uuid": summary["uuid"],
            "nid": summary["nid"],
            "title": summary["title"],
            "closed_at": summary["closed_at"],
            "source_link": summary["source_link"],
            "iid": summary["iid"],
            "credited": summary["credited"],
            "uncredited": summary["uncredited"],
            "record_url": summary["record_url"],
        }
        for summary in summaries
    ]

    raw_count = len(parsed_records)
    parsed_records = merge_records_by_iid(parsed_records)
    if raw_count != len(parsed_records):
        print(
            f"  merged {raw_count} API records into {len(parsed_records)} issues "
            "(duplicate contribution records per issue)"
        )
    save_json(project.audit_records_cache, parsed_records)
    print(f"Cached {len(parsed_records)} contribution records for audit.")
    return parsed_records


def audit_record_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": summary["uuid"],
        "nid": summary["nid"],
        "title": summary["title"],
        "closed_at": summary["closed_at"],
        "source_link": summary["source_link"],
        "iid": summary["iid"],
        "credited": summary["credited"],
        "uncredited": summary["uncredited"],
        "record_url": summary["record_url"],
    }


def refresh_audit_issue(client: ApiClient, iid: int) -> dict[str, Any] | None:
    """Re-fetch Drupal.org record(s) for one issue and update caches."""
    project = client.project
    print(f"Refreshing contribution record(s) for issue #{iid}...")
    summaries = fetch_contribution_records_for_issue(client, iid)

    cached = load_json(project.audit_records_cache, [])
    cached = [record for record in cached if int(record["iid"]) != iid]
    cached.extend(audit_record_from_summary(summary) for summary in summaries)
    merged = merge_records_by_iid(cached)
    save_json(project.audit_records_cache, merged)
    upsert_release_record_cache_for_issue(client, iid, summaries)

    match = next((record for record in merged if int(record["iid"]) == iid), None)
    if match:
        credited = ", ".join(match.get("credited") or []) or "(none)"
        uncredited = ", ".join(match.get("uncredited") or []) or "(none)"
        print(f"  node/{match.get('nid')}: credited={credited}; uncredited={uncredited}")
    elif summaries:
        print("  updated (merged duplicate records)")
    else:
        print("  no contribution record found on new.drupal.org")
    return match


def refresh_closed_issue_in_cache(client: ApiClient, iid: int) -> None:
    project = client.project
    url = (
        f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
        f"/issues/{iid}"
    )
    try:
        issue = client.get_json(url)
    except requests.HTTPError as exc:
        print(f"  warning: could not refresh GitLab issue #{iid}: {exc}", file=sys.stderr)
        return

    cached = load_json(project.closed_issues_cache, {})
    cached[str(iid)] = {
        "iid": iid,
        "title": issue.get("title", f"Issue #{iid}"),
        "closed_at": issue.get("closed_at"),
        "web_url": issue.get("web_url", project.issue_url(iid)),
        "labels": issue.get("labels", []),
        "milestone": issue.get("milestone"),
    }
    save_json(project.closed_issues_cache, cached)
    print(f"  refreshed GitLab metadata for issue #{iid}")


def clear_issue_activity_cache(client: ApiClient, iid: int) -> None:
    project = client.project
    if not project.issue_activity_cache.exists():
        return
    cached = load_json(project.issue_activity_cache, {})
    if str(iid) in cached:
        del cached[str(iid)]
        save_json(project.issue_activity_cache, cached)


def fetch_closed_gitlab_issues(client: ApiClient, refresh: bool) -> dict[int, dict[str, Any]]:
    project = client.project
    if project.closed_issues_cache.exists() and not refresh:
        cached = load_json(project.closed_issues_cache, {})
        if cached:
            print(f"Loaded {len(cached)} closed GitLab issues from cache.")
            return {int(iid): issue for iid, issue in cached.items()}

    print("Fetching closed GitLab issues...")
    all_issues: dict[int, dict[str, Any]] = {}
    page = 1
    per_page = 100
    while True:
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}/issues"
            f"?state=closed&per_page={per_page}&page={page}"
        )
        batch = client.get_json(url)
        if not batch:
            break

        for issue in batch:
            iid = int(issue["iid"])
            all_issues[iid] = {
                "iid": iid,
                "title": issue.get("title", f"Issue #{iid}"),
                "closed_at": issue.get("closed_at"),
                "web_url": issue.get("web_url", project.issue_url(iid)),
                "labels": issue.get("labels", []),
                "milestone": issue.get("milestone"),
            }

        print(f"  page {page}: {len(batch)} issues ({len(all_issues)} total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(1.0)

    save_json(project.closed_issues_cache, {str(iid): issue for iid, issue in all_issues.items()})
    print(f"Cached {len(all_issues)} closed GitLab issues.")
    return all_issues


def default_approvals() -> dict[str, Any]:
    return {"issues": {}, "uncredited": {}}


def load_approvals(project: ProjectConfig) -> dict[str, Any]:
    data = load_json(project.approvals_cache, default_approvals())
    data.setdefault("issues", {})
    data.setdefault("uncredited", {})
    return data


def save_approvals(project: ProjectConfig, data: dict[str, Any]) -> None:
    save_json(project.approvals_cache, data)


def is_issue_approved(approvals: dict[str, Any], iid: int) -> bool:
    return str(iid) in approvals["issues"]


def approved_uncredited_users(approvals: dict[str, Any], iid: int) -> set[str]:
    users = approvals["uncredited"].get(str(iid), [])
    return {normalize_username(user) for user in users}


def approve_issue(approvals: dict[str, Any], iid: int, note: str = "") -> None:
    approvals["issues"][str(iid)] = {
        "approved_at": datetime.now(tz=timezone.utc).isoformat(),
        "note": note,
    }


def approve_uncredited(
    approvals: dict[str, Any],
    iid: int,
    username: str,
    note: str = "",
) -> None:
    key = str(iid)
    users = approvals["uncredited"].setdefault(key, [])
    normalized = normalize_username(username)
    if normalized not in {normalize_username(user) for user in users}:
        users.append(normalized)
        users.sort()
    approvals["uncredited"][key] = users
    if note:
        approvals.setdefault("notes", {})[f"{iid}:{normalized}"] = note


def unapprove_issue(approvals: dict[str, Any], iid: int) -> None:
    approvals["issues"].pop(str(iid), None)
    approvals["uncredited"].pop(str(iid), None)


def unapprove_uncredited(approvals: dict[str, Any], iid: int, username: str) -> None:
    key = str(iid)
    users = approvals["uncredited"].get(key, [])
    normalized = normalize_username(username)
    approvals["uncredited"][key] = [
        user for user in users if normalize_username(user) != normalized
    ]
    if not approvals["uncredited"][key]:
        approvals["uncredited"].pop(key, None)


def build_audit_findings(
    records: list[dict[str, Any]],
    closed_issues: dict[int, dict[str, Any]],
    approvals: dict[str, Any],
    issues_cache: dict[str, dict[str, Any]] | None = None,
    ignored_users: set[str] | None = None,
) -> tuple[list[AuditIssue], list[AuditIssue], list[AuditIssue]]:
    records_by_iid = index_records_by_iid(records)
    label_cache = issues_cache or {}
    ignored = ignored_users or set()
    pending: list[AuditIssue] = []
    approved_items: list[AuditIssue] = []
    exempt_items: list[AuditIssue] = []

    for iid, issue in sorted(closed_issues.items()):
        labels = resolve_issue_labels(iid, issue, label_cache)
        record = records_by_iid.get(iid)
        if record:
            credited = list(record.get("credited") or [])
            uncredited = list(record.get("uncredited") or [])
            title = record.get("title") or issue["title"]
            closed_at = record.get("closed_at") or issue.get("closed_at")
            record_nid = record.get("nid")
            record_url = record.get("record_url")
            duplicate_nids = list(record.get("duplicate_nids") or [])
        else:
            credited = []
            uncredited = []
            title = issue["title"]
            closed_at = issue.get("closed_at")
            record_nid = None
            record_url = None
            duplicate_nids = []

        if is_issue_approved(approvals, iid):
            approved_items.append(
                AuditIssue(
                    iid=iid,
                    title=title,
                    issue_url=issue["web_url"],
                    closed_at=closed_at,
                    record_nid=record_nid,
                    record_url=record_url,
                    credited=credited,
                    uncredited=uncredited,
                    problem="approved",
                    duplicate_nids=duplicate_nids,
                )
            )
            continue

        approved_users = approved_uncredited_users(approvals, iid)
        pending_uncredited, ignored_uncredited = split_uncredited_people(
            uncredited,
            approved_users,
            ignored,
        )

        if not record:
            problem = "no_record"
        elif not credited and pending_uncredited:
            problem = "no_credits"
        elif credited and pending_uncredited:
            problem = "uncredited_people"
        elif ignored_uncredited:
            exempt_items.append(
                AuditIssue(
                    iid=iid,
                    title=title,
                    issue_url=issue["web_url"],
                    closed_at=closed_at,
                    record_nid=record_nid,
                    record_url=record_url,
                    credited=credited,
                    uncredited=[],
                    problem="ignored_uncredited_only",
                    labels=labels,
                    exemption="project manager (labels only)",
                    duplicate_nids=duplicate_nids,
                    ignored_uncredited=ignored_uncredited,
                )
            )
            continue
        elif not credited:
            problem = "no_credits"
        else:
            continue

        exemption = credit_exemption_reason(labels)
        if exemption and problem in {"no_record", "no_credits"}:
            exempt_items.append(
                AuditIssue(
                    iid=iid,
                    title=title,
                    issue_url=issue["web_url"],
                    closed_at=closed_at,
                    record_nid=record_nid,
                    record_url=record_url,
                    credited=credited,
                    uncredited=pending_uncredited,
                    problem=f"{problem}_exempt",
                    labels=labels,
                    exemption=exemption,
                    duplicate_nids=duplicate_nids,
                )
            )
            continue

        pending.append(
            AuditIssue(
                iid=iid,
                title=title,
                issue_url=issue["web_url"],
                closed_at=closed_at,
                record_nid=record_nid,
                record_url=record_url,
                credited=credited,
                uncredited=pending_uncredited,
                problem=problem,
                labels=labels,
                duplicate_nids=duplicate_nids,
            )
        )

    return pending, approved_items, exempt_items


PROBLEM_LABELS = {
    "no_record": "No contribution record",
    "no_credits": "No credits granted",
    "uncredited_people": "People listed but not credited",
}


def sort_pending_issues(pending: list[AuditIssue]) -> list[AuditIssue]:
    priority = {"no_record": 0, "no_credits": 1, "uncredited_people": 2}
    return sorted(pending, key=lambda issue: (priority.get(issue.problem, 9), issue.iid))


def append_uncredited_activity(
    nested: list[str],
    issue: AuditIssue,
) -> None:
    if not issue.uncredited:
        return
    for user in issue.uncredited:
        activity_items: list[str] = [f"{code(user)} activity:"]
        if issue.user_activity:
            for activity_line in format_user_activity_lines(user, issue.user_activity):
                activity_items.append(escape(activity_line.strip()))
        elif not gitlab_token_configured():
            activity_items.append(em(gitlab_token_setup_hint()))
        nested.append(ul(activity_items))


def format_issue_review(issue: AuditIssue, index: int, total: int) -> str:
    lines = [
        "",
        f"--- Issue {index} of {total} ---",
        f"#{issue.iid}: {issue.title}",
        f"Problem: {PROBLEM_LABELS.get(issue.problem, issue.problem)}",
        f"GitLab: {issue.issue_url}",
    ]
    if issue.record_url:
        lines.append(f"Contribution record: {issue.record_url}")
    if issue.credited:
        lines.append(f"Credited: {', '.join(issue.credited)}")
    else:
        lines.append("Credited: (none)")
    if issue.uncredited:
        lines.append(f"Missing (not credited): {', '.join(issue.uncredited)}")
        if issue.user_activity:
            for user in issue.uncredited:
                for activity_line in format_user_activity_lines(user, issue.user_activity):
                    lines.append(activity_line)
        elif not gitlab_token_configured():
            lines.append(f"  ({gitlab_token_setup_hint()})")
    elif issue.problem in {"no_record", "no_credits"}:
        lines.append("Missing: credits still need to be added on Drupal.org")
    return "\n".join(lines)


def prompt_review_choice(issue: AuditIssue) -> str:
    if issue.problem == "uncredited_people" and len(issue.uncredited) > 1:
        print(
            "\n[y] Approve (OK as-is)  [p] Approve some uncredited  "
            "[n] Deny / skip  [q] Quit"
        )
    else:
        print("\n[y] Approve (OK as-is)  [n] Deny / skip  [q] Quit")
    while True:
        try:
            choice = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if choice in {"y", "n", "q", "p"}:
            return choice
        print("Enter y, n, q" + (", or p" if issue.problem == "uncredited_people" else ""))


def prompt_partial_uncredited(issue: AuditIssue) -> list[str]:
    print("Which uncredited people are OK? (numbers, all, or none)")
    for number, user in enumerate(issue.uncredited, start=1):
        print(f"  {number}. {user}")
    while True:
        try:
            raw = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return []
        if raw in {"none", ""}:
            return []
        if raw == "all":
            return list(issue.uncredited)
        try:
            picks = [int(part) for part in raw.replace(",", " ").split()]
        except ValueError:
            print("Enter numbers like 1 3, 'all', or 'none'.")
            continue
        selected: list[str] = []
        valid = True
        for pick in picks:
            if pick < 1 or pick > len(issue.uncredited):
                print(f"Invalid choice: {pick}")
                valid = False
                break
            selected.append(issue.uncredited[pick - 1])
        if valid:
            return selected


def run_interactive_review(
    pending: list[AuditIssue],
    approvals: dict[str, Any],
    project: ProjectConfig,
) -> tuple[int, int, bool]:
    """Walk through pending issues. Returns approved count, skipped count, quit early."""
    queue = sort_pending_issues(pending)
    total = len(queue)
    if not total:
        print("Nothing to review — all pending issues are already handled.")
        return 0, 0, False

    print(f"Reviewing {total} issues. Approvals save after each answer.")
    approved_count = 0
    skipped_count = 0

    for index, issue in enumerate(queue, start=1):
        print(format_issue_review(issue, index, total))
        choice = prompt_review_choice(issue)

        if choice == "q":
            print("Review stopped.")
            return approved_count, skipped_count, True

        if choice == "n":
            print("Denied — will appear again next run.")
            skipped_count += 1
            continue

        if choice == "p":
            selected = prompt_partial_uncredited(issue)
            if not selected:
                print("No approvals saved.")
                skipped_count += 1
                continue
            for user in selected:
                approve_uncredited(approvals, issue.iid, user)
            save_approvals(project, approvals)
            remaining = [
                user
                for user in issue.uncredited
                if normalize_username(user)
                not in approved_uncredited_users(approvals, issue.iid)
            ]
            if not remaining and issue.credited:
                print(f"Approved {', '.join(selected)}. Issue complete.")
            else:
                print(f"Approved {', '.join(selected)}.")
                if remaining:
                    print(f"Still pending: {', '.join(remaining)}")
            approved_count += 1
            continue

        if choice == "y":
            approve_issue(approvals, issue.iid)
            save_approvals(project, approvals)
            print("Approved — won't appear again.")
            approved_count += 1

    print(f"Review complete. Approved {approved_count}, skipped {skipped_count}.")
    return approved_count, skipped_count, False


def render_audit_html(
    project: ProjectConfig,
    pending: list[AuditIssue],
    approved_items: list[AuditIssue],
    exempt_items: list[AuditIssue],
    generated_at: str,
    duplicate_records: list[dict[str, Any]] | None = None,
) -> str:
    by_problem: dict[str, list[AuditIssue]] = {
        "no_record": [],
        "no_credits": [],
        "uncredited_people": [],
    }
    for issue in pending:
        by_problem[issue.problem].append(issue)

    label_exempt = [
        issue for issue in exempt_items if issue.problem.endswith("_exempt")
    ]
    pm_exempt = [
        issue for issue in exempt_items if issue.problem == "ignored_uncredited_only"
    ]

    approve_cmds = "\n".join(
        [
            "# Interactive review (step through each issue)",
            f"python3 scripts/credit_audit.py --project {project.machine_name} --review",
            "",
            "# Whole issue reviewed (no record, no credits, or all uncredited people OK)",
            f"python3 scripts/credit_audit.py --project {project.machine_name} --approve 3586230",
            "",
            "# Only one listed-but-uncredited person is OK",
            f"python3 scripts/credit_audit.py --project {project.machine_name} --approve 3586230:danrod",
            "",
            "# Undo",
            f"python3 scripts/credit_audit.py --project {project.machine_name} --unapprove 3586230",
            f"python3 scripts/credit_audit.py --project {project.machine_name} --unapprove 3586230:danrod",
        ]
    )

    blocks: list[str] = [
        h2("Credit audit"),
        p(
            f"Closed {escape(project.machine_name)} issues that may need credit review on "
            f"{a('https://new.drupal.org', 'new.drupal.org')}."
        ),
        p(
            f"{strong(f'{len(pending)} issues need review')} · "
            f"{strong(f'{len(label_exempt)} exempt (duplicate / won\'t fix)')} · "
            f"{strong(f'{len(pm_exempt)} ignored (PM labels only)')} · "
            f"{strong(f'{len(approved_items)} issues approved')}"
        ),
        p(em(f"Generated {generated_at}")),
        h3("How to approve"),
        p("After reviewing an issue on Drupal.org, mark it so it won't appear again:"),
        pre_block(approve_cmds),
        p(f"Approvals are stored in {code(f'{project.machine_name}/cache/credit_approvals.json')}."),
    ]

    if duplicate_records:
        blocks.append(h3(f"Duplicate contribution records ({len(duplicate_records)})"))
        blocks.append(
            p(
                "Multiple published records point at the same GitLab issue. "
                "The audit merges credits across them, preferring records that "
                "have credits granted. Consider deleting stale duplicates on "
                "Drupal.org."
            )
        )
        dup_items = []
        for record in duplicate_records:
            nids = record.get("duplicate_nids") or []
            links = ", ".join(
                a(f"https://new.drupal.org/node/{nid}", f"node/{nid}") for nid in nids
            )
            dup_items.append(
                format_issue_item(
                    record["iid"],
                    record["title"],
                    record["source_link"],
                    extra=f"— {links}",
                )
            )
        blocks.append(ul(dup_items))

    section_titles = {
        "no_record": "No contribution record",
        "no_credits": "Contribution record with no credits granted",
        "uncredited_people": "People listed but not credited",
    }

    for problem, title in section_titles.items():
        issues = by_problem[problem]
        blocks.append(h3(f"{title} ({len(issues)})"))
        if not issues:
            blocks.append(p(em("None.")))
            continue

        issue_items = []
        for issue in issues:
            nested: list[str] = []
            if issue.record_url:
                nested.append(
                    li(
                        "Contribution record: "
                        f"{a(issue.record_url, f'node/{issue.record_nid}')}"
                    )
                )
            if issue.credited:
                nested.append(li(f"Credited: {escape(', '.join(issue.credited))}"))
            if issue.uncredited:
                nested.append(li(f"Uncredited: {escape(', '.join(issue.uncredited))}"))
                append_uncredited_activity(nested, issue)
            if problem == "no_record":
                nested.append(
                    li("Create a contribution record on Drupal.org and credit contributors.")
                )
            elif problem == "no_credits":
                nested.append(
                    li("Grant credit to at least one contributor, or approve if intentional.")
                )
            else:
                for user in issue.uncredited:
                    nested.append(
                        li(
                            f"Approve {code(user)}: "
                            f"{code(f'python3 scripts/credit_audit.py --project {project.machine_name} --approve {issue.iid}:{user}')}"
                        )
                    )
            nested.append(
                li(
                    f"Approve issue: "
                    f"{code(f'python3 scripts/credit_audit.py --project {project.machine_name} --approve {issue.iid}')}"
                )
            )
            issue_items.append(
                format_issue_item(
                    issue.iid,
                    issue.title,
                    issue.issue_url,
                    nested=nested,
                )
            )
        blocks.append(ul(issue_items))

    if label_exempt:
        blocks.append(h3(f"No credits expected — duplicate / won't fix ({len(label_exempt)})"))
        blocks.append(
            p(
                "GitLab labels "
                f"{code('why::duplicate')} or {code('why::wontFix')}. These issues do not "
                "need a contribution record or granted credits."
            )
        )
        exempt_items_html = []
        for issue in label_exempt:
            label = next(
                (label for label in issue.labels if label in CREDIT_EXEMPT_WHY_LABELS),
                issue.exemption or "",
            )
            nested = [li(f"GitLab label: {code(label)} ({escape(issue.exemption or '')})")]
            if issue.record_url:
                nested.append(
                    li(
                        "Contribution record: "
                        f"{a(issue.record_url, f'node/{issue.record_nid}')}"
                    )
                )
            exempt_items_html.append(
                format_issue_item(
                    issue.iid,
                    issue.title,
                    issue.issue_url,
                    nested=nested,
                )
            )
        blocks.append(ul(exempt_items_html))

    if pm_exempt:
        blocks.append(h3(f"Ignored uncredited — project managers ({len(pm_exempt)})"))
        blocks.append(
            p(
                "The only listed-but-uncredited people are in "
                f"{code('ignore_uncredited_people.txt')} (PMs who add labels, not code)."
            )
        )
        pm_items = []
        for issue in pm_exempt:
            nested = []
            if issue.credited:
                nested.append(li(f"Credited: {escape(', '.join(issue.credited))}"))
            nested.append(
                li(
                    "Ignored (not expected to credit): "
                    f"{escape(', '.join(issue.ignored_uncredited))}"
                )
            )
            if issue.record_url:
                nested.append(
                    li(
                        "Contribution record: "
                        f"{a(issue.record_url, f'node/{issue.record_nid}')}"
                    )
                )
            pm_items.append(
                format_issue_item(
                    issue.iid,
                    issue.title,
                    issue.issue_url,
                    nested=nested,
                )
            )
        blocks.append(ul(pm_items))

    if approved_items:
        blocks.append(h3(f"Approved ({len(approved_items)})"))
        blocks.append(
            p(
                em(
                    "These closed issues were marked reviewed. "
                    "Use --unapprove to restore them to the audit."
                )
            )
        )
        approved_html = [
            format_issue_item(issue.iid, issue.title, issue.issue_url)
            for issue in approved_items[:20]
        ]
        if len(approved_items) > 20:
            approved_html.append(li(f"… and {len(approved_items) - 20} more"))
        blocks.append(ul(approved_html))

    return join_blocks(blocks) + "\n"


def parse_approval_target(value: str) -> tuple[int, str | None]:
    if ":" in value:
        iid_raw, username = value.split(":", 1)
        return int(iid_raw), username.strip()
    return int(value), None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Drupal project issue credits and track reviewed approvals.",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Step through pending issues interactively and approve or skip each one.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch all contribution records and closed GitLab issues.",
    )
    parser.add_argument(
        "--refresh-issue",
        type=int,
        metavar="IID",
        help="Re-fetch contribution record(s) for one GitLab issue only (implies fresh GitLab comments for that issue).",
    )
    parser.add_argument(
        "--approve",
        metavar="TARGET",
        help="Approve an issue (IID) or uncredited person (IID:username).",
    )
    parser.add_argument(
        "--unapprove",
        metavar="TARGET",
        help="Remove an issue or uncredited-person approval.",
    )
    parser.add_argument(
        "--store-gitlab-token",
        action="store_true",
        help="Securely save a GitLab token to your OS keychain (input hidden).",
    )
    parser.add_argument(
        "--clear-gitlab-token",
        action="store_true",
        help="Remove the GitLab token from your OS keychain.",
    )
    parser.add_argument(
        "--refresh-comments",
        action="store_true",
        help="Re-fetch GitLab issue and MR comments (requires keychain token).",
    )
    parser.add_argument(
        "--ignore-list",
        type=Path,
        default=None,
        help=(
            "Path to usernames not expected to receive credit "
            "(default: {project}/ignore_uncredited_people.txt)."
        ),
    )
    parser.add_argument(
        "--list-approvals",
        action="store_true",
        help="Print current approvals and exit.",
    )
    add_project_argument(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.store_gitlab_token:
        prompt_and_store_gitlab_token()
        return 0

    if args.clear_gitlab_token:
        if clear_gitlab_token_from_keyring():
            print("Removed GitLab token from your OS keychain.")
        else:
            print("No GitLab token found in keychain.")
        return 0

    project = ProjectConfig.load(args.project)
    project.ensure_dirs()
    ignore_list = args.ignore_list or project.ignore_uncredited_file

    approvals = load_approvals(project)

    if args.approve:
        iid, username = parse_approval_target(args.approve)
        if username:
            approve_uncredited(approvals, iid, username)
            save_approvals(project, approvals)
            print(f"Approved uncredited person {username!r} on issue #{iid}.")
        else:
            approve_issue(approvals, iid)
            save_approvals(project, approvals)
            print(f"Approved issue #{iid}.")
        return 0

    if args.unapprove:
        iid, username = parse_approval_target(args.unapprove)
        if username:
            unapprove_uncredited(approvals, iid, username)
            save_approvals(project, approvals)
            print(f"Removed uncredited approval for {username!r} on issue #{iid}.")
        else:
            unapprove_issue(approvals, iid)
            save_approvals(project, approvals)
            print(f"Removed approval for issue #{iid}.")
        return 0

    if args.list_approvals:
        issue_count = len(approvals["issues"])
        uncredited_count = sum(len(users) for users in approvals["uncredited"].values())
        print(f"Issue approvals: {issue_count}")
        for iid, meta in sorted(approvals["issues"].items(), key=lambda item: int(item[0])):
            print(f"  #{iid} ({meta.get('approved_at', '')})")
        print(f"Uncredited-person approvals: {uncredited_count}")
        for iid, users in sorted(approvals["uncredited"].items(), key=lambda item: int(item[0])):
            for user in users:
                print(f"  #{iid}: {user}")
        return 0

    client = ApiClient(project)

    if args.refresh_issue:
        refresh_audit_issue(client, args.refresh_issue)
        refresh_closed_issue_in_cache(client, args.refresh_issue)
        clear_issue_activity_cache(client, args.refresh_issue)

    records = fetch_audit_records(
        client,
        refresh=args.refresh and not args.refresh_issue,
    )
    closed_issues = fetch_closed_gitlab_issues(
        client,
        refresh=args.refresh and not args.refresh_issue,
    )
    issues_cache = load_json(project.issues_cache, {})
    ignored_users = load_ignored_uncredited_people(ignore_list)
    if ignored_users:
        print(
            f"Loaded {len(ignored_users)} ignored uncredited usernames "
            f"from {ignore_list}."
        )
    pending, approved_items, exempt_items = build_audit_findings(
        records,
        closed_issues,
        approvals,
        issues_cache=issues_cache,
        ignored_users=ignored_users,
    )

    if pending and any(issue.uncredited for issue in pending):
        if not gitlab_token_configured():
            print(f"Note: {gitlab_token_setup_hint()}")
        else:
            activity_targets = pending
            refresh_activity = args.refresh_comments or args.refresh
            if args.refresh_issue:
                refresh_activity = True
                activity_targets = [
                    issue for issue in pending if issue.iid == args.refresh_issue
                ]
            if activity_targets:
                enrich_issues_with_gitlab_activity(
                    client,
                    activity_targets,
                    refresh=refresh_activity,
                )

    if args.review:
        run_interactive_review(pending, approvals, project)
        pending, approved_items, exempt_items = build_audit_findings(
            records,
            closed_issues,
            approvals,
            issues_cache=issues_cache,
            ignored_users=ignored_users,
        )
        if pending and any(issue.uncredited for issue in pending) and gitlab_token_configured():
            enrich_issues_with_gitlab_activity(
                client,
                pending,
                refresh=False,
            )

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    duplicate_records = duplicate_contribution_records(records)
    html = render_audit_html(
        project,
        pending,
        approved_items,
        exempt_items,
        generated_at,
        duplicate_records=duplicate_records,
    )
    project.audit_output.write_text(html)
    print(f"Wrote {project.audit_output}")

    counts = {
        "no_record": sum(1 for issue in pending if issue.problem == "no_record"),
        "no_credits": sum(1 for issue in pending if issue.problem == "no_credits"),
        "uncredited_people": sum(1 for issue in pending if issue.problem == "uncredited_people"),
    }
    print(
        "Needs review: "
        f"{len(pending)} total "
        f"({counts['no_record']} no record, "
        f"{counts['no_credits']} no credits, "
        f"{counts['uncredited_people']} with uncredited people)"
    )
    label_exempt_count = sum(1 for issue in exempt_items if issue.problem.endswith("_exempt"))
    pm_exempt_count = sum(
        1 for issue in exempt_items if issue.problem == "ignored_uncredited_only"
    )
    print(f"Exempt (duplicate / won't fix): {label_exempt_count} issues")
    print(f"Ignored (PM labels only): {pm_exempt_count} issues")
    print(f"Approved: {len(approved_items)} issues")

    missing_all, exempt_missing = closed_issues_missing_records(
        records,
        closed_issues,
        issues_cache=issues_cache,
    )
    if missing_all:
        print(f"Closed without contribution record: {len(missing_all)}")
        for issue in missing_all[:15]:
            print(f"  #{issue.iid}: {issue.title}")
        if len(missing_all) > 15:
            print(f"  … and {len(missing_all) - 15} more")
    if exempt_missing:
        print(
            f"No record expected (duplicate / won't fix): {len(exempt_missing)} "
            "(not listed above)"
        )
    if duplicate_records:
        print(f"Duplicate d.o records: {len(duplicate_records)}")
        for record in duplicate_records:
            print(format_duplicate_record_line(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
