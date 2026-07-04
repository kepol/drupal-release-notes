#!/usr/bin/env python3
"""Print a release preparation status summary."""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from credit_audit import (
    CREDIT_EXEMPT_WHY_LABELS,
    build_audit_findings,
    closed_issues_missing_records,
    credit_exemption_reason,
    duplicate_contribution_records,
    load_approvals,
    load_cached_audit_records,
    load_cached_closed_issues,
    load_ignored_uncredited_people,
)
from period_context import (
    PERIOD_SOURCE_MILESTONES,
    PeriodContext,
    build_period_context,
    milestone_period_summary,
    milestone_scope_iids,
    milestone_window_for,
    milestone_titles,
    suggest_milestone_for_close,
    window_label_for,
)
from project import ProjectConfig, add_project_argument
from release_notes import (
    ApiClient,
    load_json,
    parse_dt,
    version_short_slug,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print release preparation status for a GitLab milestone.",
    )
    parser.add_argument(
        "--milestone",
        metavar="TITLE",
        help='GitLab milestone title (e.g. "1.0.0-beta3"). Required for status report.',
    )
    parser.add_argument(
        "--list-by-milestone",
        action="store_true",
        help=(
            "List all closed issues grouped by suggested milestone (from close date). "
            "Use --milestone to limit output to one release."
        ),
    )
    parser.add_argument(
        "--write-output",
        action="store_true",
        help=(
            "With --list-by-milestone, also write "
            "{project}/reports/milestone-assignments.md."
        ),
    )
    add_project_argument(parser)
    args = parser.parse_args()
    if not args.list_by_milestone and not args.milestone:
        parser.error("--milestone is required unless --list-by-milestone is used.")
    if args.write_output and not args.list_by_milestone:
        parser.error("--write-output requires --list-by-milestone.")
    return args


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


def fetch_all_closed_gitlab_issues(client: ApiClient) -> list[dict[str, Any]]:
    """Fetch every closed issue, including current milestone assignment."""
    return fetch_gitlab_issues(client, state="closed")


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


def release_notes_info(project: ProjectConfig, milestone: str) -> tuple[str, int | None]:
    relative = f"{project.machine_name}/reports/{milestone}.md"
    path = project.reports_dir / f"{milestone}.md"
    period_cache = project.periods_dir / f"{milestone}.json"
    if period_cache.exists():
        count = len(load_json(period_cache, {}).get("issues", []))
        return relative, count
    if path.exists():
        match = re.search(r"\*\*(\d+) credited issues\*\*", path.read_text())
        if match:
            return relative, int(match.group(1))
        return relative, None
    return relative, None


def load_period_issue_iids(project: ProjectConfig, milestone: str) -> set[int]:
    period_cache = project.periods_dir / f"{milestone}.json"
    if not period_cache.exists():
        return set()
    return {
        int(issue["iid"])
        for issue in load_json(period_cache, {}).get("issues", [])
    }


@dataclass(frozen=True)
class ReleaseNotesGap:
    iid: int
    title: str
    web_url: str
    reason: str


def explain_release_notes_gap(
    iid: int,
    records_by_iid: dict[int, dict[str, Any]],
    *,
    use_milestone_rules: bool,
) -> str:
    record = records_by_iid.get(iid)
    if not record:
        return "no contribution record on new.drupal.org"
    if not (record.get("credited") or []):
        return "contribution record exists but no credits granted"
    if use_milestone_rules:
        return "credited but not yet in release notes (re-run with --rebuild-frozen)"
    return "not included in release notes period"


def find_release_notes_gaps(
    milestone_issues: list[dict[str, Any]],
    period_iids: set[int],
    records: list[dict[str, Any]],
    *,
    ctx: PeriodContext,
) -> list[ReleaseNotesGap]:
    records_by_iid = {int(record["iid"]): record for record in records}
    use_milestone_rules = ctx.source == PERIOD_SOURCE_MILESTONES
    gaps: list[ReleaseNotesGap] = []
    for issue in milestone_issues:
        iid = int(issue["iid"])
        labels = issue.get("labels") or []
        exemption = credit_exemption_reason(labels)
        if exemption:
            continue
        record = records_by_iid.get(iid)
        if not record or not (record.get("credited") or []):
            gaps.append(
                ReleaseNotesGap(
                    iid=iid,
                    title=issue.get("title", ""),
                    web_url=issue.get("web_url", ""),
                    reason=explain_release_notes_gap(
                        iid,
                        records_by_iid,
                        use_milestone_rules=use_milestone_rules,
                    ),
                )
            )
            continue
        if use_milestone_rules:
            continue
        if iid in period_iids:
            continue
        gaps.append(
            ReleaseNotesGap(
                iid=iid,
                title=issue.get("title", ""),
                web_url=issue.get("web_url", ""),
                reason=explain_release_notes_gap(
                    iid,
                    records_by_iid,
                    use_milestone_rules=False,
                ),
            )
        )
    gaps.sort(key=lambda item: item.iid)
    return gaps


def explain_release_notes_exclusion(
    issue: dict[str, Any],
    records_by_iid: dict[int, dict[str, Any]],
    *,
    use_milestone_rules: bool,
) -> str:
    labels = issue.get("labels") or []
    exemption = credit_exemption_reason(labels)
    if exemption:
        for label in labels:
            if label in CREDIT_EXEMPT_WHY_LABELS:
                return f"{exemption} ({label})"
        return exemption
    iid = int(issue["iid"])
    return explain_release_notes_gap(
        iid,
        records_by_iid,
        use_milestone_rules=use_milestone_rules,
    )


def find_release_notes_exclusions(
    milestone_issues: list[dict[str, Any]],
    period_iids: set[int],
    records: list[dict[str, Any]],
    *,
    ctx: PeriodContext,
) -> list[ReleaseNotesGap]:
    """Closed milestone issues that are not in the release-notes period."""
    records_by_iid = {int(record["iid"]): record for record in records}
    use_milestone_rules = ctx.source == PERIOD_SOURCE_MILESTONES
    exclusions: list[ReleaseNotesGap] = []
    for issue in milestone_issues:
        iid = int(issue["iid"])
        if iid in period_iids:
            continue
        exclusions.append(
            ReleaseNotesGap(
                iid=iid,
                title=issue.get("title", ""),
                web_url=issue.get("web_url", ""),
                reason=explain_release_notes_exclusion(
                    issue,
                    records_by_iid,
                    use_milestone_rules=use_milestone_rules,
                ),
            )
        )
    exclusions.sort(key=lambda item: item.iid)
    return exclusions


def is_exempt_release_notes_reason(reason: str) -> bool:
    return "(why::" in reason


def release_notes_exclusion_intro(exclusions: list[ReleaseNotesGap]) -> str:
    count = len(exclusions)
    if all(is_exempt_release_notes_reason(item.reason) for item in exclusions):
        return (
            f"{count} closed in milestone not in release notes "
            f"(duplicate / won't fix / works as designed):"
        )
    return f"{count} closed in milestone not in release notes:"


def format_release_notes_gap_line(gap: ReleaseNotesGap) -> str:
    url = gap.web_url or f"#{gap.iid}"
    return indented(f"#{gap.iid}: {gap.title} — {gap.reason} — {url}")


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


@dataclass(frozen=True)
class MilestoneMismatch:
    iid: int
    title: str
    web_url: str
    assigned: str
    suggested: str
    closed_at: datetime


def find_milestone_mismatches(
    closed_issues: list[dict[str, Any]],
    ctx: PeriodContext,
    *,
    scope_iids: set[int],
) -> list[MilestoneMismatch]:
    """Closed in-scope issues where GitLab milestone != suggested release."""
    mismatches: list[MilestoneMismatch] = []
    for issue in closed_issues:
        iid = int(issue["iid"])
        if iid not in scope_iids:
            continue
        closed_raw = issue.get("closed_at")
        if not closed_raw:
            continue
        closed_at = parse_dt(closed_raw)
        milestone = issue.get("milestone") or {}
        assigned = milestone.get("title")
        suggested = suggest_milestone_for_close(
            closed_at,
            ctx,
            assigned_title=assigned,
        )
        if not assigned or assigned == suggested:
            continue
        mismatches.append(
            MilestoneMismatch(
                iid=iid,
                title=issue.get("title", ""),
                web_url=issue.get("web_url", ""),
                assigned=assigned,
                suggested=suggested,
                closed_at=closed_at,
            )
        )
    mismatches.sort(key=lambda item: item.closed_at)
    return mismatches


def format_milestone_mismatch_line(mismatch: MilestoneMismatch) -> str:
    closed = mismatch.closed_at.strftime("%Y-%m-%d")
    url = mismatch.web_url or f"#{mismatch.iid}"
    return indented(
        f"#{mismatch.iid}: {mismatch.title} — closed {closed}, "
        f"{mismatch.assigned!r} → {mismatch.suggested!r} ({url})"
    )


@dataclass(frozen=True)
class MilestoneAssignment:
    iid: int
    title: str
    web_url: str
    closed_at: datetime
    suggested: str
    current: str | None


def filter_by_iids(items: list[Any], scope_iids: set[int], *, attr: str = "iid") -> list[Any]:
    filtered: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            iid = item.get(attr)
        else:
            iid = getattr(item, attr)
        if iid in scope_iids:
            filtered.append(item)
    return filtered


def group_issues_by_suggested_milestone(
    closed_issues: list[dict[str, Any]],
    ctx: PeriodContext,
) -> dict[str, list[MilestoneAssignment]]:
    grouped: dict[str, list[MilestoneAssignment]] = {
        title: [] for title in milestone_titles(ctx)
    }
    for issue in closed_issues:
        closed_raw = issue.get("closed_at")
        if not closed_raw:
            continue
        closed_at = parse_dt(closed_raw)
        milestone = issue.get("milestone") or {}
        current = milestone.get("title")
        suggested = suggest_milestone_for_close(
            closed_at,
            ctx,
            assigned_title=current,
        )
        iid = int(issue["iid"])
        assignment = MilestoneAssignment(
            iid=iid,
            title=issue.get("title", ""),
            web_url=issue.get("web_url", ""),
            closed_at=closed_at,
            suggested=suggested,
            current=current,
        )
        grouped.setdefault(suggested, []).append(assignment)

    for assignments in grouped.values():
        assignments.sort(key=lambda item: item.closed_at)
    return grouped


def format_assignment_line(assignment: MilestoneAssignment) -> str:
    closed = assignment.closed_at.strftime("%Y-%m-%d")
    current = assignment.current or "(none)"
    url = assignment.web_url or f"#{assignment.iid}"
    return (
        f"- #{assignment.iid} — {assignment.title} — "
        f"closed {closed}, current milestone: {current} — {url}"
    )


def format_milestone_assignment_section(
    milestone: str,
    assignments: list[MilestoneAssignment],
    ctx: PeriodContext,
) -> list[str]:
    window = window_label_for(milestone, ctx)
    heading = f"## {milestone} ({len(assignments)} issues)"
    lines = [heading, ""]
    if window:
        lines.append(f"{window}.")
        lines.append("")
    if assignments:
        lines.extend(format_assignment_line(item) for item in assignments)
    else:
        lines.append("(none)")
    return lines


def list_by_milestone(
    args: argparse.Namespace,
    project: ProjectConfig,
    client: ApiClient,
) -> int:
    ctx = build_period_context(project, client)
    print("Fetching closed GitLab issues...")
    closed_issues = fetch_all_closed_gitlab_issues(client)
    grouped = group_issues_by_suggested_milestone(closed_issues, ctx)

    milestones = milestone_titles(ctx)
    if args.milestone:
        if args.milestone not in grouped and args.milestone not in milestones:
            known = ", ".join(milestones)
            print(
                f"Unknown milestone {args.milestone!r}. Expected one of: {known}",
                file=sys.stderr,
            )
            return 1
        milestones = [args.milestone]

    source_note = (
        "GitLab milestone start/due dates"
        if ctx.source == "milestones"
        else "Drupal.org release tags"
    )
    lines = [
        f"# Milestone assignments: {project.machine_name}",
        "",
        (
            f"Suggested GitLab milestones from close dates and {source_note}. "
            "Create missing milestones on GitLab, then assign each issue."
        ),
        "",
    ]
    for milestone in milestones:
        assignments = grouped.get(milestone, [])
        lines.extend(format_milestone_assignment_section(milestone, assignments, ctx))
        lines.append("")

    output = "\n".join(lines).rstrip() + "\n"
    print(output, end="")

    if args.write_output:
        path = project.reports_dir / "milestone-assignments.md"
        project.reports_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(output)
        print(f"Wrote {path}", file=sys.stderr)

    return 0


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

    if args.list_by_milestone:
        return list_by_milestone(args, project, client)

    open_in_milestone = fetch_gitlab_issues(
        client,
        milestone=args.milestone,
        state="opened",
    )

    ctx = build_period_context(project, client)
    from period_context import migrate_legacy_period_files

    migrate_legacy_period_files(project, ctx)
    releases = ctx.releases

    records = load_cached_audit_records(project)
    closed_issues = load_cached_closed_issues(project)
    issues_cache = load_json(project.issues_cache, {})
    approvals = load_approvals(project)
    ignored_users = load_ignored_uncredited_people(project.ignore_uncredited_file)

    milestone_closed = fetch_gitlab_issues(
        client,
        milestone=args.milestone,
        state="closed",
    )
    assigned_iids = {
        int(issue["iid"]) for issue in (*open_in_milestone, *milestone_closed)
    }
    scope_iids = milestone_scope_iids(
        args.milestone,
        ctx,
        closed_issues,
        assigned_iids=assigned_iids,
    )

    missing_records, exempt_missing = closed_issues_missing_records(
        records,
        closed_issues,
        issues_cache=issues_cache,
    )
    missing_records = filter_by_iids(missing_records, scope_iids)
    exempt_missing = filter_by_iids(exempt_missing, scope_iids)

    missing_in_milestone = filter_by_iids(missing_records, assigned_iids)

    pending, _approved, _exempt = build_audit_findings(
        records,
        closed_issues,
        approvals,
        issues_cache=issues_cache,
        ignored_users=ignored_users,
    )
    pending = filter_by_iids(pending, scope_iids)

    if milestone_window_for(args.milestone, ctx):
        notes_path, notes_count = release_notes_info(project, args.milestone)
        period_iids = load_period_issue_iids(project, args.milestone)
    else:
        notes_path = f"{project.machine_name}/reports/(no matching milestone)"
        notes_count = None
        period_iids = set()

    milestone_all_issues = [*open_in_milestone, *milestone_closed]
    release_notes_gaps = find_release_notes_gaps(
        milestone_all_issues,
        period_iids,
        records,
        ctx=ctx,
    )
    release_notes_exclusions = find_release_notes_exclusions(
        milestone_closed,
        period_iids,
        records,
        ctx=ctx,
    )

    qa_issue = find_qa_issue(
        client,
        issues_cache,
        milestone_release_short(args.milestone),
    )
    duplicate_records = [
        record
        for record in duplicate_contribution_records(records)
        if int(record["iid"]) in scope_iids
    ]

    scoped_closed_for_mismatch = [
        {**closed_issues[iid], "iid": iid}
        for iid in sorted(scope_iids)
        if iid in closed_issues
    ]
    milestone_mismatches = find_milestone_mismatches(
        scoped_closed_for_mismatch,
        ctx,
        scope_iids=scope_iids,
    )
    milestone_url = fetch_milestone_url(client, args.milestone)
    open_count, milestone_total = milestone_issue_counts(
        client,
        args.milestone,
        open_issues=open_in_milestone,
        closed_issues=milestone_closed,
    )

    status_heading = (
        f"Release status: {project.machine_name} ({args.milestone}) "
        f"[{ctx.source}]"
    )
    period_summary = milestone_period_summary(args.milestone, ctx)
    lines: list[str] = [
        SECTION_RULE,
        status_heading,
        SECTION_RULE,
    ]
    if period_summary:
        lines.append(period_summary)

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
        notes_line = f"Release notes: {notes_path} ({notes_count} credited)"
    elif milestone_window_for(args.milestone, ctx):
        notes_line = f"Release notes: {notes_path} (not generated yet)"
    else:
        notes_line = f"Release notes: no GitLab milestone {args.milestone!r}"

    notes_details: list[str] = []
    if release_notes_gaps:
        notes_line += (
            f" — milestone has {milestone_total}; "
            f"{len(release_notes_gaps)} not in release notes"
        )
        notes_details.extend(
            format_release_notes_gap_line(gap) for gap in release_notes_gaps
        )
    elif (
        notes_count is not None
        and milestone_total != notes_count
        and release_notes_exclusions
    ):
        notes_line += f" — milestone has {milestone_total}"
        notes_details.append(indented(release_notes_exclusion_intro(release_notes_exclusions)))
        notes_details.extend(
            format_release_notes_gap_line(exclusion)
            for exclusion in release_notes_exclusions
        )
    elif notes_count is not None and milestone_total != notes_count:
        notes_line += f" — milestone has {milestone_total}"
        if open_count > 0:
            notes_details.append(
                indented(
                    f"{open_count} still open in milestone "
                    f"(not expected in release notes)"
                )
            )

    append_section(lines, notes_line, notes_details)

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
            f"(in {args.milestone!r} scope, nothing on new.drupal.org)"
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
            f"(in {args.milestone!r} scope, closed without a Drupal.org record by design)"
        ),
        exempt_details,
    )

    mismatch_details = (
        [format_milestone_mismatch_line(mismatch) for mismatch in milestone_mismatches]
        if milestone_mismatches
        else [format_report_none()]
    )
    append_section(
        lines,
        (
            f"Wrong milestone: {len(milestone_mismatches)} "
            f"(assigned milestone != close date within {args.milestone!r} scope)"
        ),
        mismatch_details,
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
            f"(in {args.milestone!r} scope without a contribution record)"
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
