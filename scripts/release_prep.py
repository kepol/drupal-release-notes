#!/usr/bin/env python3
"""Print a release preparation status summary."""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Any

from credit_audit import (
    build_audit_findings,
    closed_issues_missing_records,
    duplicate_contribution_records,
    load_approvals,
    load_cached_audit_records,
    load_cached_closed_issues,
    load_ignored_uncredited_people,
)
from project import ProjectConfig, add_project_argument
from release_notes import (
    ApiClient,
    build_periods,
    fetch_release_boundaries,
    load_json,
    version_short_slug,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print release preparation status for a GitLab milestone.",
    )
    parser.add_argument(
        "--milestone",
        required=True,
        metavar="TITLE",
        help='GitLab milestone title (e.g. "1.0.0-beta3").',
    )
    add_project_argument(parser)
    return parser.parse_args()


def fetch_gitlab_issues(
    client: ApiClient,
    *,
    milestone: str | None = None,
    state: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    project = client.project
    params: list[str] = ["per_page=100"]
    if milestone:
        params.append(f"milestone={quote_milestone(milestone)}")
    if state:
        params.append(f"state={state}")
    if search:
        params.append(f"search={quote_milestone(search)}")

    items: list[dict[str, Any]] = []
    page = 1
    while True:
        query = "&".join([*params, f"page={page}"])
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
            f"/issues?{query}"
        )
        batch = client.get_json(url)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.05)
    return items


def quote_milestone(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def milestone_release_short(milestone: str) -> str:
    """Turn a milestone like 1.0.0-beta3 into beta3 for QA title matching."""
    if re.search(r"-(alpha|beta|rc)\d+$", milestone, re.IGNORECASE):
        return version_short_slug(milestone)
    match = re.search(r"(alpha|beta|rc)(\d+)", milestone, re.IGNORECASE)
    if match:
        return f"{match.group(1).lower()}{match.group(2)}"
    return milestone


def find_qa_issue(
    client: ApiClient,
    issues_cache: dict[str, dict[str, Any]],
    release_short: str,
) -> dict[str, Any] | None:
    title_pattern = re.compile(rf"^CCC {re.escape(release_short)} QA$", re.IGNORECASE)
    for entry in issues_cache.values():
        if title_pattern.match(entry.get("title", "")):
            iid = int(entry["iid"])
            return resolve_issue_state(client, iid, entry.get("title", ""), entry.get("web_url"))

    for issue in fetch_gitlab_issues(client, search=f"CCC {release_short} QA"):
        title = issue.get("title", "")
        if title_pattern.match(title):
            iid = int(issue["iid"])
            return {
                "iid": iid,
                "title": title,
                "state": issue.get("state"),
                "web_url": issue.get("web_url", client.project.issue_url(iid)),
            }
    return None


def resolve_issue_state(
    client: ApiClient,
    iid: int,
    title: str,
    web_url: str | None,
) -> dict[str, Any]:
    project = client.project
    url = (
        f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
        f"/issues/{iid}"
    )
    try:
        issue = client.get_json(url)
        state = issue.get("state")
        title = issue.get("title", title)
        web_url = issue.get("web_url", web_url or project.issue_url(iid))
    except Exception:
        state = None
    return {
        "iid": iid,
        "title": title,
        "state": state,
        "web_url": web_url,
    }


def release_notes_info(project: ProjectConfig, period_slug: str) -> tuple[str, int | None]:
    relative = f"{project.machine_name}/output/{period_slug}.md"
    path = project.output_dir / f"{period_slug}.md"
    period_cache = project.periods_dir / f"{period_slug}.json"
    if period_cache.exists():
        count = len(load_json(period_cache, {}).get("issues", []))
        return relative, count
    if path.exists():
        match = re.search(r"\*\*(\d+) credited issues\*\*", path.read_text())
        if match:
            return relative, int(match.group(1))
        return relative, None
    return relative, None


def fetch_milestone(client: ApiClient, milestone_title: str) -> dict[str, Any] | None:
    """Return GitLab milestone metadata including issue_stats and web_url."""
    project = client.project
    for state in ("active", "all"):
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
            f"/milestones?search={quote_milestone(milestone_title)}&state={state}&per_page=20"
        )
        for milestone in client.get_json(url):
            if milestone.get("title") == milestone_title:
                return milestone
    return None


def fetch_milestone_url(client: ApiClient, milestone_title: str) -> str:
    """Return the GitLab web URL for a milestone title."""
    milestone = fetch_milestone(client, milestone_title)
    if milestone and milestone.get("web_url"):
        return milestone["web_url"]
    return client.project.milestone_search_url(milestone_title)


def milestone_issue_counts(
    client: ApiClient,
    milestone_title: str,
    *,
    open_issues: list[dict[str, Any]],
    closed_issues: list[dict[str, Any]],
) -> tuple[int, int]:
    """Return (open, total) issue counts for a milestone."""
    milestone = fetch_milestone(client, milestone_title)
    stats = (milestone or {}).get("issue_stats") or {}
    open_count = stats.get("open")
    total_count = stats.get("total")
    if open_count is not None and total_count is not None:
        return int(open_count), int(total_count)
    open_count = len(open_issues)
    total_count = open_count + len(closed_issues)
    return open_count, total_count


SECTION_RULE = "-" * 40
ITEM_INDENT = "    "


def bullet_section(text: str) -> str:
    return f"* {text}"


def indented(text: str) -> str:
    return f"{ITEM_INDENT}{text}"


def format_qa_line_text(qa_issue: dict[str, Any] | None) -> str:
    if qa_issue is None:
        return "QA issue: not found"
    state = (qa_issue.get("state") or "unknown").lower()
    url = qa_issue.get("web_url") or ""
    return f"QA issue: {state} ({url})"


def format_report_duplicate_line(record: dict[str, Any]) -> str:
    nids = record.get("duplicate_nids") or []
    nid_links = ", ".join(f"https://new.drupal.org/node/{nid}" for nid in nids)
    return indented(f"#{record['iid']}: {record['title']} — {nid_links}")


def format_report_issue_lines(
    issues: list[Any],
    *,
    limit: int = 20,
    bullet: bool = False,
) -> list[str]:
    prefix = "- " if bullet else ""
    lines: list[str] = []
    for issue in issues[:limit]:
        lines.append(indented(f"{prefix}#{issue.iid}: {issue.title}"))
    if len(issues) > limit:
        lines.append(indented(f"… and {len(issues) - limit} more"))
    return lines


def format_report_none() -> str:
    return indented("(none)")


def append_section(
    lines: list[str],
    heading: str,
    detail_lines: list[str],
) -> None:
    if lines:
        lines.append("")
    lines.append(bullet_section(heading))
    lines.extend(detail_lines)


def main() -> int:
    args = parse_args()
    project = ProjectConfig.load(args.project)
    client = ApiClient(project)

    open_in_milestone = fetch_gitlab_issues(
        client,
        milestone=args.milestone,
        state="opened",
    )

    records = load_cached_audit_records(project)
    closed_issues = load_cached_closed_issues(project)
    issues_cache = load_json(project.issues_cache, {})
    approvals = load_approvals(project)
    ignored_users = load_ignored_uncredited_people(project.ignore_uncredited_file)

    missing_records, exempt_missing = closed_issues_missing_records(
        records,
        closed_issues,
        issues_cache=issues_cache,
    )

    milestone_closed = fetch_gitlab_issues(
        client,
        milestone=args.milestone,
        state="closed",
    )
    milestone_closed_iids = {int(issue["iid"]) for issue in milestone_closed}
    missing_in_milestone = [
        issue for issue in missing_records if issue.iid in milestone_closed_iids
    ]

    pending, _approved, _exempt = build_audit_findings(
        records,
        closed_issues,
        approvals,
        issues_cache=issues_cache,
        ignored_users=ignored_users,
    )

    releases = fetch_release_boundaries(client)
    current_period = build_periods(releases, project)[-1]
    notes_path, notes_count = release_notes_info(project, current_period.slug)

    qa_issue = find_qa_issue(
        client,
        issues_cache,
        milestone_release_short(args.milestone),
    )
    duplicate_records = duplicate_contribution_records(records)
    milestone_url = fetch_milestone_url(client, args.milestone)
    open_count, milestone_total = milestone_issue_counts(
        client,
        args.milestone,
        open_issues=open_in_milestone,
        closed_issues=milestone_closed,
    )

    status_heading = f"Release status: {project.machine_name} ({args.milestone})"
    lines: list[str] = [
        SECTION_RULE,
        status_heading,
        SECTION_RULE,
    ]

    append_section(
        lines,
        f"Open in milestone: {open_count} of {milestone_total} — {milestone_url}",
        [],
    )

    if pending:
        credit_line = (
            f"Credit audit pending: {len(pending)} — "
            f"python3 scripts/credit_audit.py --project {project.machine_name} --review"
        )
    else:
        credit_line = f"Credit audit pending: {len(pending)}"
    append_section(lines, credit_line, [])

    append_section(lines, format_qa_line_text(qa_issue), [])

    if notes_count is not None:
        notes_line = f"Release notes: {notes_path} ({notes_count} issues)"
    else:
        notes_line = f"Release notes: {notes_path} (not generated yet)"
    append_section(lines, notes_line, [])

    duplicate_details = (
        [format_report_duplicate_line(record) for record in duplicate_records]
        if duplicate_records
        else [format_report_none()]
    )
    append_section(
        lines,
        f"Duplicate d.o records: {len(duplicate_records)}",
        duplicate_details,
    )

    missing_details = (
        format_report_issue_lines(missing_records)
        if missing_records
        else [format_report_none()]
    )
    append_section(
        lines,
        (
            f"Missing contribution records: {len(missing_records)} "
            f"(closed on GitLab, nothing on new.drupal.org)"
        ),
        missing_details,
    )

    exempt_details = (
        format_report_issue_lines(exempt_missing, bullet=True)
        if exempt_missing
        else [format_report_none()]
    )
    append_section(
        lines,
        (
            f"No record expected (duplicate / won't fix): {len(exempt_missing)} "
            f"(closed without a Drupal.org record by design)"
        ),
        exempt_details,
    )

    milestone_missing_details = (
        format_report_issue_lines(missing_in_milestone, bullet=True)
        if missing_in_milestone
        else [format_report_none()]
    )
    append_section(
        lines,
        (
            f"Missing in milestone: {len(missing_in_milestone)} "
            f"(closed in {args.milestone!r} without a record)"
        ),
        milestone_missing_details,
    )

    print("\n".join(lines))

    if not records and not closed_issues:
        print(
            "\nNo cached audit data. Run:\n"
            "  python3 scripts/credit_audit.py --refresh",
            file=sys.stderr,
        )
    elif not records or not closed_issues:
        print(
            "\nCache incomplete. Run:\n"
            "  python3 scripts/credit_audit.py --refresh",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
