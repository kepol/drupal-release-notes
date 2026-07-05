"""Map issue close dates to release milestones (GitLab dates or Drupal.org tags)."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from project import REPORT_EXTENSION, ProjectConfig
from release_notes import (
    ApiClient,
    ReleaseBoundary,
    fetch_release_boundaries,
    milestone_for_closed_at,
    next_release_version,
    parse_dt,
)

DEFAULT_MILESTONE_VERSION_PATTERN = (
    r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\d*)?$"
)
PERIOD_SOURCE_RELEASES = "releases"
PERIOD_SOURCE_MILESTONES = "milestones"


@dataclass(frozen=True)
class MilestoneWindow:
    """Close-date range for one GitLab milestone."""

    title: str
    start: datetime | None
    end: datetime | None

    def contains(self, closed_at: datetime, *, grace: timedelta) -> bool:
        start = self.start or datetime.min.replace(tzinfo=timezone.utc)
        if self.end is None:
            return closed_at >= start
        end = self.end + grace
        return start <= closed_at <= end


@dataclass(frozen=True)
class PeriodContext:
    """Resolved period boundaries for one project run."""

    source: str
    releases: list[ReleaseBoundary]
    windows: list[MilestoneWindow]
    grace_hours: float

    @property
    def grace(self) -> timedelta:
        return timedelta(hours=self.grace_hours)


def parse_gitlab_date(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        return parsed.replace(hour=23, minute=59, second=59)
    return parsed


def milestone_title_matches(title: str, project: ProjectConfig) -> bool:
    if title in project.milestone_exclude_titles:
        return False
    return re.match(project.milestone_include_pattern, title) is not None


def fetch_all_gitlab_milestones(client: ApiClient) -> list[dict[str, Any]]:
    project = client.project
    items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for state in ("active", "closed"):
        page = 1
        while True:
            url = (
                f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
                f"/milestones?state={state}&per_page=100&page={page}"
            )
            batch = client.get_json(url)
            if not batch:
                break
            for milestone in batch:
                milestone_id = int(milestone["id"])
                if milestone_id in seen_ids:
                    continue
                seen_ids.add(milestone_id)
                items.append(milestone)
            if len(batch) < 100:
                break
            page += 1
            time.sleep(0.05)
    return items


def build_milestone_windows(
    milestones: list[dict[str, Any]],
    project: ProjectConfig,
) -> list[MilestoneWindow]:
    windows: list[MilestoneWindow] = []
    for milestone in milestones:
        title = milestone.get("title") or ""
        if not milestone_title_matches(title, project):
            continue
        windows.append(
            MilestoneWindow(
                title=title,
                start=parse_gitlab_date(milestone.get("start_date")),
                end=parse_gitlab_date(milestone.get("due_date"), end_of_day=True),
            )
        )

    def sort_key(window: MilestoneWindow) -> tuple[datetime, str]:
        start = window.start or datetime.min.replace(tzinfo=timezone.utc)
        return (start, window.title)

    windows.sort(key=sort_key)
    return windows


def build_period_context(project: ProjectConfig, client: ApiClient) -> PeriodContext:
    releases = fetch_release_boundaries(client)
    source = project.period_source
    windows: list[MilestoneWindow] = []

    if source == PERIOD_SOURCE_MILESTONES:
        raw = fetch_all_gitlab_milestones(client)
        windows = build_milestone_windows(raw, project)
        if not windows:
            print(
                "Warning: period_source is 'milestones' but no matching GitLab "
                "milestones were found; falling back to Drupal.org release tags.",
                file=sys.stderr,
            )
            source = PERIOD_SOURCE_RELEASES

    return PeriodContext(
        source=source,
        releases=releases,
        windows=windows,
        grace_hours=project.milestone_close_grace_hours,
    )


def suggest_milestone_for_close(
    closed_at: datetime,
    ctx: PeriodContext,
    *,
    assigned_title: str | None = None,
) -> str:
    """Return the milestone title an issue close date belongs to."""
    if ctx.source == PERIOD_SOURCE_MILESTONES and ctx.windows:
        if assigned_title:
            for window in ctx.windows:
                if window.title == assigned_title and window.contains(
                    closed_at,
                    grace=ctx.grace,
                ):
                    return assigned_title

        matched: str | None = None
        for window in ctx.windows:
            if window.contains(closed_at, grace=ctx.grace):
                matched = window.title
        if matched:
            return matched

        if ctx.windows:
            last = ctx.windows[-1]
            last_end = last.end
            if last_end and closed_at > last_end + ctx.grace:
                try:
                    return next_release_version(last.title)
                except ValueError:
                    pass
            return last.title

    return milestone_for_closed_at(
        closed_at,
        ctx.releases,
        grace_hours=ctx.grace_hours,
    )


def milestone_titles(ctx: PeriodContext) -> list[str]:
    if ctx.source == PERIOD_SOURCE_MILESTONES and ctx.windows:
        titles = [window.title for window in ctx.windows]
        try:
            titles.append(next_release_version(ctx.windows[-1].title))
        except ValueError:
            pass
        return titles

    if not ctx.releases:
        return []
    titles = [release.version for release in ctx.releases]
    titles.append(next_release_version(ctx.releases[-1].version))
    return titles


def window_label_for(milestone: str, ctx: PeriodContext) -> str:
    if ctx.source == PERIOD_SOURCE_MILESTONES:
        for window in ctx.windows:
            if window.title != milestone:
                continue
            start = (
                window.start.strftime("%Y-%m-%d")
                if window.start
                else "project start"
            )
            if window.end:
                cutoff = window.end + ctx.grace
                end = cutoff.strftime("%Y-%m-%d %H:%M UTC")
                grace_note = (
                    f" ({ctx.grace_hours:g}h grace after due date)"
                    if ctx.grace_hours
                    else ""
                )
                return f"closed {start} through {end} (GitLab milestone dates{grace_note})"
            return f"closed on or after {start} (GitLab milestone, open-ended)"

        if ctx.windows and milestone == next_release_version(ctx.windows[-1].title):
            last = ctx.windows[-1]
            if last.end:
                start = (last.end + ctx.grace).strftime("%Y-%m-%d %H:%M UTC")
                return f"closed after {start} (after last milestone window)"
        return ""

    if not ctx.releases:
        return ""

    grace = ctx.grace
    if milestone == ctx.releases[0].version:
        end = ctx.releases[0].created.strftime("%Y-%m-%d")
        return f"closed before {end} (Drupal.org release tag)"

    for index in range(len(ctx.releases) - 1):
        if milestone == ctx.releases[index + 1].version:
            start = ctx.releases[index].created.strftime("%Y-%m-%d")
            cutoff = ctx.releases[index + 1].created + grace
            end = cutoff.strftime("%Y-%m-%d %H:%M UTC")
            return (
                f"closed {start} through {end} "
                f"({ctx.grace_hours:g}h grace after {milestone} tag)"
            )

    if milestone == next_release_version(ctx.releases[-1].version):
        cutoff = ctx.releases[-1].created + grace
        start = cutoff.strftime("%Y-%m-%d %H:%M UTC")
        return f"closed on or after {start} (current development)"

    return ""


def milestone_period_summary(milestone: str, ctx: PeriodContext) -> str:
    """One-line start/end range for the release status header."""
    grace_suffix = (
        f" (+{ctx.grace_hours:g}h grace)"
        if ctx.grace_hours
        else ""
    )

    if ctx.source == PERIOD_SOURCE_MILESTONES:
        for window in ctx.windows:
            if window.title != milestone:
                continue
            start = (
                window.start.strftime("%Y-%m-%d")
                if window.start
                else "project start"
            )
            if window.end:
                end = (window.end + ctx.grace).strftime("%Y-%m-%d %H:%M UTC")
                return f"Release window: {start} → {end}{grace_suffix}"
            return f"Release window: {start} → (open-ended)"

        if ctx.windows and milestone == next_release_version(ctx.windows[-1].title):
            last = ctx.windows[-1]
            if last.end:
                start = (last.end + ctx.grace).strftime("%Y-%m-%d %H:%M UTC")
                return f"Release window: {start} → (current development)"
        return ""

    if not ctx.releases:
        return ""

    if milestone == ctx.releases[0].version:
        end = (ctx.releases[0].created + ctx.grace).strftime("%Y-%m-%d %H:%M UTC")
        return f"Release window: project start → {end}{grace_suffix}"

    for index in range(len(ctx.releases) - 1):
        if milestone == ctx.releases[index + 1].version:
            start = ctx.releases[index].created.strftime("%Y-%m-%d %H:%M UTC")
            end = (ctx.releases[index + 1].created + ctx.grace).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            return f"Release window: {start} → {end}{grace_suffix}"

    if milestone == next_release_version(ctx.releases[-1].version):
        start = (ctx.releases[-1].created + ctx.grace).strftime("%Y-%m-%d %H:%M UTC")
        return f"Release window: {start} → (current development)"

    return ""


def issue_in_milestone_scope(
    iid: int,
    issue: dict[str, Any],
    milestone_title: str,
    ctx: PeriodContext,
    assigned_to_milestone: set[int],
) -> bool:
    if iid in assigned_to_milestone:
        return True
    closed_raw = issue.get("closed_at")
    if not closed_raw:
        return False
    closed_at = parse_dt(closed_raw)
    milestone = issue.get("milestone") or {}
    assigned = milestone.get("title")
    return suggest_milestone_for_close(
        closed_at,
        ctx,
        assigned_title=assigned,
    ) == milestone_title


def milestone_scope_iids(
    milestone_title: str,
    ctx: PeriodContext,
    closed_issues: dict[int, dict[str, Any]],
    *,
    assigned_iids: set[int] | None = None,
) -> set[int]:
    assigned = set(assigned_iids or [])
    scoped = set(assigned)
    for iid, issue in closed_issues.items():
        if iid in assigned:
            continue
        if issue_in_milestone_scope(
            iid,
            issue,
            milestone_title,
            ctx,
            assigned,
        ):
            scoped.add(iid)
    return scoped


def build_report_periods(ctx: PeriodContext, project: ProjectConfig) -> list[Any]:
    """Build release-note periods from milestone windows or Drupal.org tags."""
    from release_notes import ReportPeriod, build_periods

    if ctx.source != PERIOD_SOURCE_MILESTONES or not ctx.windows:
        return build_periods(ctx.releases, project)

    periods: list[ReportPeriod] = []
    seen_titles: set[str] = set()
    for index, window in enumerate(ctx.windows):
        if window.title in seen_titles:
            continue
        seen_titles.add(window.title)
        start = window.start
        end = window.end + ctx.grace if window.end else None
        is_current = index == len(ctx.windows) - 1 and end is None
        periods.append(
            ReportPeriod(
                slug=window.title,
                title=window.title,
                start=start,
                end=end,
                frozen=not is_current,
            )
        )
    return periods


def milestone_window_for(milestone: str, ctx: PeriodContext) -> MilestoneWindow | None:
    return next((window for window in ctx.windows if window.title == milestone), None)


def issue_milestone_title(issue: dict[str, Any]) -> str | None:
    milestone = issue.get("milestone")
    if not milestone:
        return None
    if isinstance(milestone, dict):
        return milestone.get("title")
    return str(milestone)


def issue_in_milestone_release_period(
    iid: int,
    milestone_title: str,
    ctx: PeriodContext,
    closed_issues: dict[int, dict[str, Any]],
    closed_at: datetime,
) -> bool:
    """Return whether a credited issue belongs in one milestone-mode release period."""
    assigned = issue_milestone_title(closed_issues.get(iid, {}))
    if assigned:
        return assigned == milestone_title

    window = milestone_window_for(milestone_title, ctx)
    if not window or not window.contains(closed_at, grace=ctx.grace):
        return False
    return (
        suggest_milestone_for_close(
            closed_at,
            ctx,
            assigned_title=assigned,
        )
        == milestone_title
    )


def enrich_closed_issues_milestones(
    client: ApiClient,
    closed_issues: dict[int, dict[str, Any]],
    iids: set[int],
) -> dict[int, dict[str, Any]]:
    """Fill missing GitLab milestone assignments for credited issues."""
    needed = {
        iid
        for iid in iids
        if not issue_milestone_title(closed_issues.get(iid, {}))
    }
    if not needed:
        return closed_issues

    project = client.project
    enriched = dict(closed_issues)
    print(f"Fetching GitLab milestone assignment for {len(needed)} issues...")
    page = 1
    per_page = 100
    while needed:
        url = (
            f"https://git.drupalcode.org/api/v4/projects/{project.gitlab_project_encoded}"
            f"/issues?state=closed&per_page={per_page}&page={page}"
        )
        batch = client.get_json(url)
        if not batch:
            break
        for issue in batch:
            iid = int(issue["iid"])
            if iid not in needed:
                continue
            existing = enriched.get(iid, {"iid": iid})
            enriched[iid] = {
                **existing,
                "iid": iid,
                "title": issue.get("title", existing.get("title", f"Issue #{iid}")),
                "closed_at": issue.get("closed_at") or existing.get("closed_at"),
                "web_url": issue.get(
                    "web_url",
                    existing.get("web_url", project.issue_url(iid)),
                ),
                "labels": issue.get("labels", existing.get("labels", [])),
                "milestone": issue.get("milestone"),
            }
            needed.discard(iid)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.05)

    if needed:
        print(
            f"Warning: milestone still missing for {len(needed)} credited issues.",
            file=sys.stderr,
        )
    return enriched


def migrate_legacy_period_files(project: ProjectConfig, ctx: PeriodContext) -> None:
    """Rename release-slug cache/output files to GitLab milestone titles."""
    from release_notes import load_json, save_json

    if ctx.source != PERIOD_SOURCE_MILESTONES:
        return

    renames: dict[str, str] = {}
    for path in sorted(project.periods_dir.glob("*.json")):
        data = load_json(path, {})
        period_data = data.get("period") or {}
        title = period_data.get("title")
        old_slug = path.stem
        if not title or old_slug == title:
            continue
        renames[old_slug] = title
        period_data["slug"] = title
        data["period"] = period_data
        new_path = project.periods_dir / f"{title}.json"
        save_json(new_path, data)
        path.unlink()
        print(f"Migrated period cache {old_slug}.json → {title}.json")

    for old_slug, title in renames.items():
        for directory, extensions in [
            (project.reports_dir, [REPORT_EXTENSION]),
            (project.summaries_dir, [".prompt.md", ".txt"]),
        ]:
            directory.mkdir(parents=True, exist_ok=True)
            for ext in extensions:
                old_path = directory / f"{old_slug}{ext}"
                if directory == project.reports_dir and ext == REPORT_EXTENSION:
                    new_path = directory / project.release_notes_filename(title)
                else:
                    new_path = directory / f"{title}{ext}"
                if not old_path.exists():
                    continue
                if new_path.exists():
                    old_path.unlink()
                else:
                    old_path.rename(new_path)
                    print(f"Migrated {old_path.relative_to(project.project_dir)} → {new_path.name}")
                if ext == ".prompt.md" and new_path.exists():
                    text = new_path.read_text()
                    updated = text.replace(
                        f"summaries/{old_slug}.txt",
                        f"summaries/{title}.txt",
                    )
                    if updated != text:
                        new_path.write_text(updated)


def select_report_periods(
    requested: str,
    periods: list[Any],
) -> list[Any]:
    """Match a --period value to built report periods."""
    if requested == "all":
        return periods
    matching = [
        period
        for period in periods
        if period.slug == requested or period.title == requested
    ]
    return matching
