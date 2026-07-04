#!/usr/bin/env python3
"""Audit ai_context issue credits and track reviewed approvals."""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report import (
    ApiClient,
    CACHE_DIR,
    ISSUE_URL,
    ISSUES_CACHE,
    OUTPUT_DIR,
    ROOT,
    PROJECT_MACHINE_NAME,
    GITLAB_PROJECT_ENCODED,
    fetch_project_contribution_records,
    load_json,
    normalize_username,
    save_json,
)

AUDIT_CACHE = CACHE_DIR / "credit_audit_records.json"
CLOSED_ISSUES_CACHE = CACHE_DIR / "closed_issues.json"
APPROVALS_FILE = CACHE_DIR / "credit_approvals.json"
AUDIT_OUTPUT = OUTPUT_DIR / "credit-audit.md"
IGNORE_UNCREDITED_FILE = ROOT / "ignore_uncredited_people.txt"

CREDIT_EXEMPT_WHY_LABELS = {
    "why::duplicate": "duplicate",
    "why::wontFix": "won't fix",
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


def load_ignored_uncredited_people(path: Path = IGNORE_UNCREDITED_FILE) -> set[str]:
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


def fetch_audit_records(client: ApiClient, refresh: bool) -> list[dict[str, Any]]:
    if AUDIT_CACHE.exists() and not refresh:
        cached = merge_records_by_iid(load_json(AUDIT_CACHE, []))
        if cached:
            raw_count = len(load_json(AUDIT_CACHE, []))
            if raw_count != len(cached):
                save_json(AUDIT_CACHE, cached)
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
    save_json(AUDIT_CACHE, parsed_records)
    print(f"Cached {len(parsed_records)} contribution records for audit.")
    return parsed_records


def fetch_closed_gitlab_issues(client: ApiClient, refresh: bool) -> dict[int, dict[str, Any]]:
    if CLOSED_ISSUES_CACHE.exists() and not refresh:
        cached = load_json(CLOSED_ISSUES_CACHE, {})
        if cached:
            print(f"Loaded {len(cached)} closed GitLab issues from cache.")
            return {int(iid): issue for iid, issue in cached.items()}

    print("Fetching closed GitLab issues...")
    all_issues: dict[int, dict[str, Any]] = {}
    page = 1
    per_page = 100
    while True:
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/issues"
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
                "web_url": issue.get("web_url", ISSUE_URL.format(iid=iid)),
                "labels": issue.get("labels", []),
            }

        print(f"  page {page}: {len(batch)} issues ({len(all_issues)} total)")
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(1.0)

    save_json(CLOSED_ISSUES_CACHE, {str(iid): issue for iid, issue in all_issues.items()})
    print(f"Cached {len(all_issues)} closed GitLab issues.")
    return all_issues


def default_approvals() -> dict[str, Any]:
    return {"issues": {}, "uncredited": {}}


def load_approvals() -> dict[str, Any]:
    data = load_json(APPROVALS_FILE, default_approvals())
    data.setdefault("issues", {})
    data.setdefault("uncredited", {})
    return data


def save_approvals(data: dict[str, Any]) -> None:
    save_json(APPROVALS_FILE, data)


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
            save_approvals(approvals)
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
            save_approvals(approvals)
            print("Approved — won't appear again.")
            approved_count += 1

    print(f"Review complete. Approved {approved_count}, skipped {skipped_count}.")
    return approved_count, skipped_count, False


def render_audit_markdown(
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

    lines = [
        "# Credit audit",
        "",
        "Closed ai_context issues that may need credit review on "
        "[new.drupal.org](https://new.drupal.org).",
        "",
        f"**{len(pending)} issues need review** · "
        f"**{len(label_exempt)} exempt (duplicate / won't fix)** · "
        f"**{len(pm_exempt)} ignored (PM labels only)** · "
        f"**{len(approved_items)} issues approved**",
        "",
        f"_Generated {generated_at}_",
        "",
        "## How to approve",
        "",
        "After reviewing an issue on Drupal.org, mark it so it won't appear again:",
        "",
        "```bash",
        "# Interactive review (step through each issue)",
        "python3 credit_audit.py --review",
        "",
        "# Whole issue reviewed (no record, no credits, or all uncredited people OK)",
        "python3 credit_audit.py --approve 3586230",
        "",
        "# Only one listed-but-uncredited person is OK",
        "python3 credit_audit.py --approve 3586230:danrod",
        "",
        "# Undo",
        "python3 credit_audit.py --unapprove 3586230",
        "python3 credit_audit.py --unapprove 3586230:danrod",
        "```",
        "",
        "Approvals are stored in `cache/credit_approvals.json`.",
        "",
    ]

    if duplicate_records:
        lines.extend(
            [
                f"## Duplicate contribution records ({len(duplicate_records)})",
                "",
                "Multiple published records point at the same GitLab issue. "
                "The audit merges credits across them, preferring records that "
                "have credits granted. Consider deleting stale duplicates on "
                "Drupal.org.",
                "",
            ]
        )
        for record in duplicate_records:
            nids = record.get("duplicate_nids") or []
            links = ", ".join(f"[node/{nid}](https://new.drupal.org/node/{nid})" for nid in nids)
            lines.append(
                f"* [#{record['iid']}]({record['source_link']}): {record['title']} — {links}"
            )
        lines.append("")

    section_titles = {
        "no_record": "No contribution record",
        "no_credits": "Contribution record with no credits granted",
        "uncredited_people": "People listed but not credited",
    }

    for problem, title in section_titles.items():
        issues = by_problem[problem]
        lines.extend([f"## {title} ({len(issues)})", ""])
        if not issues:
            lines.append("_None._")
            lines.append("")
            continue

        for issue in issues:
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
            if issue.record_url:
                lines.append(f"  * Contribution record: [node/{issue.record_nid}]({issue.record_url})")
            if issue.credited:
                lines.append(f"  * Credited: {', '.join(issue.credited)}")
            if issue.uncredited:
                lines.append(f"  * Uncredited: {', '.join(issue.uncredited)}")
            if problem == "no_record":
                lines.append(
                    "  * Create a contribution record on Drupal.org and credit contributors."
                )
            elif problem == "no_credits":
                lines.append(
                    "  * Grant credit to at least one contributor, or approve if intentional."
                )
            else:
                for user in issue.uncredited:
                    lines.append(
                        f"  * Approve `{user}`: "
                        f"`python3 credit_audit.py --approve {issue.iid}:{user}`"
                    )
            lines.append(
                f"  * Approve issue: `python3 credit_audit.py --approve {issue.iid}`"
            )
            lines.append("")

    if label_exempt:
        lines.extend(
            [
                f"## No credits expected — duplicate / won't fix ({len(label_exempt)})",
                "",
                "GitLab labels `why::duplicate` or `why::wontFix`. These issues do not "
                "need a contribution record or granted credits.",
                "",
            ]
        )
        for issue in label_exempt:
            label = next(
                (label for label in issue.labels if label in CREDIT_EXEMPT_WHY_LABELS),
                issue.exemption or "",
            )
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
            lines.append(f"  * GitLab label: `{label}` ({issue.exemption})")
            if issue.record_url:
                lines.append(
                    f"  * Contribution record: [node/{issue.record_nid}]({issue.record_url})"
                )
            lines.append("")

    if pm_exempt:
        lines.extend(
            [
                f"## Ignored uncredited — project managers ({len(pm_exempt)})",
                "",
                "The only listed-but-uncredited people are in "
                "`ignore_uncredited_people.txt` (PMs who add labels, not code).",
                "",
            ]
        )
        for issue in pm_exempt:
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
            if issue.credited:
                lines.append(f"  * Credited: {', '.join(issue.credited)}")
            lines.append(
                f"  * Ignored (not expected to credit): "
                f"{', '.join(issue.ignored_uncredited)}"
            )
            if issue.record_url:
                lines.append(
                    f"  * Contribution record: [node/{issue.record_nid}]({issue.record_url})"
                )
            lines.append("")

    if approved_items:
        lines.extend([f"## Approved ({len(approved_items)})", ""])
        lines.append(
            "_These closed issues were marked reviewed. "
            "Use `--unapprove` to restore them to the audit._"
        )
        lines.append("")
        for issue in approved_items[:20]:
            lines.append(f"* [#{issue.iid}]({issue.issue_url}): {issue.title}")
        if len(approved_items) > 20:
            lines.append(f"* … and {len(approved_items) - 20} more")
        lines.append("")

    return "\n".join(lines)


def parse_approval_target(value: str) -> tuple[int, str | None]:
    if ":" in value:
        iid_raw, username = value.split(":", 1)
        return int(iid_raw), username.strip()
    return int(value), None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit ai_context issue credits and track reviewed approvals.",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Step through pending issues interactively and approve or skip each one.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch contribution records and closed GitLab issues.",
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
        "--ignore-list",
        type=Path,
        default=IGNORE_UNCREDITED_FILE,
        help=(
            "Path to usernames not expected to receive credit "
            "(default: ignore_uncredited_people.txt)."
        ),
    )
    parser.add_argument(
        "--list-approvals",
        action="store_true",
        help="Print current approvals and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    approvals = load_approvals()

    if args.approve:
        iid, username = parse_approval_target(args.approve)
        if username:
            approve_uncredited(approvals, iid, username)
            save_approvals(approvals)
            print(f"Approved uncredited person {username!r} on issue #{iid}.")
        else:
            approve_issue(approvals, iid)
            save_approvals(approvals)
            print(f"Approved issue #{iid}.")
        return 0

    if args.unapprove:
        iid, username = parse_approval_target(args.unapprove)
        if username:
            unapprove_uncredited(approvals, iid, username)
            save_approvals(approvals)
            print(f"Removed uncredited approval for {username!r} on issue #{iid}.")
        else:
            unapprove_issue(approvals, iid)
            save_approvals(approvals)
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

    client = ApiClient()
    records = fetch_audit_records(client, refresh=args.refresh)
    closed_issues = fetch_closed_gitlab_issues(client, refresh=args.refresh)
    issues_cache = load_json(ISSUES_CACHE, {})
    ignored_users = load_ignored_uncredited_people(args.ignore_list)
    if ignored_users:
        print(
            f"Loaded {len(ignored_users)} ignored uncredited usernames "
            f"from {args.ignore_list}."
        )
    pending, approved_items, exempt_items = build_audit_findings(
        records,
        closed_issues,
        approvals,
        issues_cache=issues_cache,
        ignored_users=ignored_users,
    )

    if args.review:
        run_interactive_review(pending, approvals)
        pending, approved_items, exempt_items = build_audit_findings(
            records,
            closed_issues,
            approvals,
            issues_cache=issues_cache,
            ignored_users=ignored_users,
        )

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    duplicate_records = [
        record for record in records if len(record.get("duplicate_nids") or []) > 1
    ]
    markdown = render_audit_markdown(
        pending,
        approved_items,
        exempt_items,
        generated_at,
        duplicate_records=duplicate_records,
    )
    AUDIT_OUTPUT.write_text(markdown)
    print(f"Wrote {AUDIT_OUTPUT}")

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
