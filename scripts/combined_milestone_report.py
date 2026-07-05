#!/usr/bin/env python3
"""Merge multiple GitLab milestone reports and compare to Drupal.org release notes."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from html_report import (
    a,
    em,
    escape,
    format_issue_item,
    h2,
    h3,
    h4,
    join_blocks,
    li,
    p,
    strong,
    table,
    ul,
)
from project import ProjectConfig, REPORT_EXTENSION, add_project_argument
from release_notes import (
    BUG_CATEGORIES,
    FEATURE_CATEGORIES,
    PeriodReport,
    ReportPeriod,
    deserialize_report,
    format_counter,
    format_people_counter,
    is_other_major_contribution,
    load_json,
    render_html,
)

# Drupal.org 1.0.0-beta1 page (includes pre-alpha work bundled into beta1 release).
DRUPAL_ORG_BETA1 = {
    "feature": [
        3575590, 3556909, 3568673, 3575595, 3571909, 3564706, 3569311, 3572160,
        3570933, 3568674, 3568677, 3570940, 3568676, 3571788, 3567791, 3547034,
        3547035, 3547033, 3559384, 3569313, 3550034, 3563089, 3547050, 3570934,
        3566852, 3564714, 3563362, 3563365, 3564653, 3563371, 3563361, 3563360,
        3563049, 3563052, 3563357, 3555225, 3549082,
    ],
    "task": [
        3574359, 3547037, 3579344, 3577087, 3579857, 3574908, 3579234, 3574904,
        3574906, 3549849, 3577427, 3569776, 3577656, 3577426, 3577398, 3574420,
        3576089, 3573713, 3574936, 3571794, 3573717, 3573708, 3563366, 3567571,
        3563107, 3574923, 3573709, 3572891, 3556908, 3571299, 3558814, 3571393,
        3563372, 3563127, 3557719, 3569514, 3569312, 3567568, 3568384, 3566842,
        3545824, 3568086, 3566866, 3566863, 3566861, 3566865, 3566811, 3566858,
        3563043, 3564667, 3547042, 3564691, 3564709, 3563000, 3563036, 3563038,
        3563100, 3563108, 3559504, 3559380, 3563008, 3559388, 3556878, 3557700,
        3558583, 3550892, 3549081,
    ],
    "bug": [
        3579841, 3578114, 3579394, 3579396, 3578657, 3577512, 3577745, 3578386,
        3554221, 3571188, 3571392, 3571006, 3571195, 3568115, 3568177, 3563975,
        3554616, 3552972, 3554277, 3549752, 3550895, 3549748, 3547892,
    ],
    "plan": [
        3567570, 3577379, 3564629, 3569967, 3573719, 3572067, 3559379, 3550896,
    ],
}

DRUPAL_PEOPLE = {
    "kristen pol": 121,
    "afoster": 21,
    "scott falconer": 18,
    "marcus_johansson": 16,
    "bbruno": 12,
    "emma horrell": 12,
    "dstorozhuk": 10,
    "danrod": 8,
    "ahmedjabar": 8,
    "robloach": 6,
    "svendecabooter": 6,
    "erichomanchuk": 5,
    "tedbow": 5,
    "annmarysruthy": 4,
    "yautja_cetanu": 4,
    "b_sharpe": 3,
    "kostiantyn": 3,
    "axioteo": 2,
    "unqunq": 2,
    "a.dmitriiev": 2,
    "hrishikesh-dalal": 2,
    "divyamdotfoo": 2,
    "kurtfoster": 2,
    "nickolaj": 2,
    "guptahemant": 1,
    "naveenapj": 1,
    "velmir_taky": 1,
    "nexusnovaz": 1,
    "rakhimandhania": 1,
    "fjgarlin": 1,
    "twiesing": 1,
    "joachim namyslo": 1,
    "medha kumari": 1,
    "breidert": 1,
    "tonypaulbarker": 1,
    "nikro": 1,
    "abhisekmazumdar": 1,
    "webbywe": 1,
    "ajv009": 1,
    "ahmad khader": 1,
    "thamas": 1,
    "harivansh": 1,
    "gantal": 1,
    "sujal kshatri": 1,
    "shamir.vs": 1,
    "jurgenhaas": 1,
    "roromedia": 1,
    "mandclu": 1,
    "akhil babu": 1,
}

DRUPAL_ORGS = {
    "salsa digital": 123,
    "itty bitty byte": 117,
    "foster interactive inc.": 25,
    "acquia": 23,
    "freelygive": 17,
    "1xinternet": 16,
    "itech4web": 12,
    "drupal ukraine community": 12,
    "the university of edinburgh": 12,
    "optasy": 8,
    "kalamuna": 6,
    "sven decabooter": 6,
    "dynamate": 6,
    "qed42": 6,
    "imagex": 3,
    "e-sepia web innovation": 2,
    "digitaltrotter": 2,
    "entityone": 2,
    "zoocha": 1,
    "drupal association": 1,
    "annertech": 1,
    "localgov drupal": 1,
    "dropsolid": 1,
    "civicactions": 1,
    "vardot": 1,
    "opensense labs": 1,
    "drupalfit": 1,
    "elevated third": 1,
    "zyxware technologies": 1,
    "lakedrops": 1,
}

USERNAME_TO_DISPLAY = {
    "kepol": "kristen pol",
    "aidanfoster": "afoster",
    "emma-horrell": "emma horrell",
    "yautja_cetanu": "yautja_cetanu",
    "ahmedj": "ahmedjabar",
    "kumarimedha09": "medha kumari",
    "sujal_31": "sujal kshatri",
    "naveen.prakash.work": "naveenapj",
    "akhilbabu": "akhil babu",
    "ahmad-khader": "ahmad khader",
    "scottfalconer": "scott falconer",
    "svendecabooter": "svendecabooter",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--milestones",
        nargs="+",
        default=["1.0.0-alpha", "1.0.0-beta1"],
        help="GitLab milestone titles to merge (in order).",
    )
    parser.add_argument(
        "--slug",
        default="alpha-through-beta1",
        help="Filename slug for combined outputs (default: alpha-through-beta1).",
    )
    parser.add_argument(
        "--title",
        default="1.0.0-alpha through 1.0.0-beta1",
        help="Report heading title.",
    )
    parser.add_argument(
        "--drupal-release",
        default="1.0.0-beta1",
        help="Drupal.org release page label for comparison section.",
    )
    add_project_argument(parser)
    return parser.parse_args()


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def merge_milestone_reports(
    project: ProjectConfig,
    milestones: list[str],
    *,
    title: str,
    slug: str,
) -> PeriodReport:
    merged: dict[int, Any] = {}
    for milestone in milestones:
        cache_path = project.periods_dir / f"{milestone}.json"
        if not cache_path.exists():
            raise SystemExit(
                f"Missing period cache {cache_path}. Run:\n"
                f'  python3 scripts/release_notes.py --period "{milestone}" --rebuild-frozen'
            )
        report = deserialize_report(load_json(cache_path, {}))
        for issue in report.issues:
            merged[issue.iid] = issue

    period = ReportPeriod(
        slug=slug,
        title=title,
        start=None,
        end=None,
        frozen=True,
    )
    issues = sorted(merged.values(), key=lambda item: item.iid)
    return PeriodReport(
        period=period,
        issues=issues,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def repo_section_for(issue) -> str:
    if issue.category in FEATURE_CATEGORIES:
        return "feature"
    if issue.category in BUG_CATEGORIES:
        return "bug"
    if issue.category == "plan":
        return "plan"
    if issue.category == "task":
        return "task"
    return issue.category or "other"


def drupal_all_issues() -> set[int]:
    all_iids: set[int] = set()
    for iids in DRUPAL_ORG_BETA1.values():
        all_iids.update(iids)
    return all_iids


def drupal_category(iid: int) -> list[str]:
    return [cat for cat, iids in DRUPAL_ORG_BETA1.items() if iid in iids]


def merged_people_counts(report: PeriodReport) -> Counter[str]:
    counts: Counter[str] = Counter()
    for user, count in report.user_counts.items():
        display = USERNAME_TO_DISPLAY.get(user, user)
        counts[norm_key(display)] += count
    return counts


def render_comparison(
    report: PeriodReport,
    *,
    project: ProjectConfig,
    milestones: list[str],
    drupal_release: str,
    closed_issues: dict[str, Any],
) -> str:
    repo_iids = {issue.iid for issue in report.issues}
    do_iids = drupal_all_issues()
    by_iid = {issue.iid: issue for issue in report.issues}

    release_url = (
        f"https://www.drupal.org/project/ai_context/releases/{drupal_release}"
    )
    blocks: list[str] = [
        h2(f"Drupal.org vs repo: {report.period.title}"),
        p(
            "Compares "
            f"{a(release_url, f'Drupal.org {drupal_release} release notes')} "
            f"to merged repo milestones: {escape(', '.join(milestones))}."
        ),
        p(strong(f"Repo credited (combined): {len(repo_iids)}")),
        p(strong(f"Drupal.org issues listed: {len(do_iids)}")),
        p(strong(f"On both: {len(repo_iids & do_iids)}")),
    ]

    def append_issue_block(heading: str, iids: list[int]) -> None:
        if not iids:
            return
        blocks.append(h3(f"{heading} ({len(iids)})"))
        items = []
        for iid in iids:
            issue = by_iid.get(iid)
            title = issue.title if issue else closed_issues.get(str(iid), {}).get(
                "title", f"Issue #{iid}"
            )
            do_cats = drupal_category(iid)
            repo_cat = repo_section_for(issue) if issue else "—"
            url = issue.issue_url if issue else project.issue_url(iid)
            items.append(
                format_issue_item(
                    iid,
                    title,
                    url,
                    extra=(
                        f"— repo: {escape(repo_cat)}; "
                        f"drupal.org: {escape(', '.join(do_cats) or '—')}"
                    ),
                )
            )
        blocks.append(ul(items))

    missing_on_do = sorted(repo_iids - do_iids)
    extra_on_do = sorted(do_iids - repo_iids)

    append_issue_block("Missing on Drupal.org (credited in repo)", missing_on_do)

    blocks.append(h3(f"On Drupal.org but not in repo ({len(extra_on_do)})"))
    if extra_on_do:
        extra_items = []
        for iid in extra_on_do:
            meta = closed_issues.get(str(iid), {})
            labels = meta.get("labels") or []
            exempt = [label for label in labels if label.startswith("why::")]
            title = meta.get("title", f"Issue #{iid}")
            reason = ", ".join(exempt) if exempt else "not credited / wrong milestone"
            extra_items.append(
                format_issue_item(
                    iid,
                    title,
                    project.issue_url(iid),
                    extra=(
                        f"— drupal.org: {escape(', '.join(drupal_category(iid)))}; "
                        f"{escape(reason)}"
                    ),
                )
            )
        blocks.append(ul(extra_items))
    else:
        blocks.append(p(em("None.")))

    for category in ("feature", "task", "bug", "plan"):
        do_set = set(DRUPAL_ORG_BETA1[category])
        repo_in_cat = {
            iid
            for iid in repo_iids
            if repo_section_for(by_iid[iid]) == category
        }
        wrong_on_do = sorted(
            iid
            for iid in do_set - repo_iids
            if any(label.startswith("why::") for label in (closed_issues.get(str(iid), {}).get("labels") or []))
        )
        wrong_section = sorted(
            iid for iid in do_set & repo_iids if repo_section_for(by_iid[iid]) != category
        )
        missing_cat = sorted(repo_in_cat - do_set)
        if wrong_on_do:
            append_issue_block(
                f"{category.capitalize()}s on Drupal.org that should be removed (exempt)",
                wrong_on_do,
            )
        if wrong_section:
            append_issue_block(
                f"{category.capitalize()}s on Drupal.org with wrong section vs repo category",
                wrong_section,
            )
        if missing_cat:
            append_issue_block(
                f"{category.capitalize()}s missing on Drupal.org",
                missing_cat,
            )

    blocks.append(h3("Contributor differences"))
    repo_people = merged_people_counts(report)
    blocks.append(h4("People"))
    all_people = set(repo_people) | {norm_key(name) for name in DRUPAL_PEOPLE}
    diffs = []
    for key in all_people:
        display = next(
            (name for name in DRUPAL_PEOPLE if norm_key(name) == key),
            next(
                (USERNAME_TO_DISPLAY.get(u, u) for u in report.user_counts if norm_key(USERNAME_TO_DISPLAY.get(u, u)) == key),
                key,
            ),
        )
        dc = DRUPAL_PEOPLE.get(display, 0)
        if not dc:
            for name, count in DRUPAL_PEOPLE.items():
                if norm_key(name) == key:
                    dc = count
                    display = name
                    break
        rc = repo_people.get(key, 0)
        if dc != rc:
            diffs.append((display, str(dc), str(rc), f"{rc - dc:+d}"))
    if diffs:
        blocks.append(
            table(
                ["Person", "Drupal.org", "Repo", "Δ"],
                sorted(diffs, key=lambda item: -abs(int(item[3]))),
            )
        )
    else:
        blocks.append(p(em("No differences.")))

    blocks.append(h4("Organizations"))
    repo_orgs: Counter[str] = Counter()
    for name, count in report.org_counts.items():
        repo_orgs[norm_key(name)] += count
    do_orgs = {norm_key(name): (name, count) for name, count in DRUPAL_ORGS.items()}
    org_diffs = []
    for key in sorted(set(repo_orgs) | set(do_orgs)):
        display, dc = do_orgs.get(key, (key, 0))
        rc = repo_orgs.get(key, 0)
        if dc != rc:
            org_diffs.append((display, str(dc), str(rc), f"{rc - dc:+d}"))
    if org_diffs:
        blocks.append(
            table(
                ["Organization", "Drupal.org", "Repo", "Δ"],
                sorted(org_diffs, key=lambda item: -abs(int(item[3]))),
            )
        )
    else:
        blocks.append(p(em("No differences.")))

    return join_blocks(blocks) + "\n"


def main() -> int:
    args = parse_args()
    project = ProjectConfig.load(args.project)
    project.ensure_dirs()

    report = merge_milestone_reports(
        project,
        args.milestones,
        title=args.title,
        slug=args.slug,
    )

    notes_name = project.release_notes_filename(f"{args.slug}")
    notes_path = project.reports_dir / notes_name
    notes_path.write_text(render_html(report, project))
    print(f"Wrote {notes_path} ({len(report.issues)} credited issues)")

    closed_raw = load_json(project.closed_issues_cache, {})
    comparison_path = project.reports_dir / f"compare-drupalorg-{args.slug}{REPORT_EXTENSION}"
    comparison_path.write_text(
        render_comparison(
            report,
            project=project,
            milestones=args.milestones,
            drupal_release=args.drupal_release,
            closed_issues=closed_raw,
        )
    )
    print(f"Wrote {comparison_path}")

    cache_path = project.periods_dir / f"{args.slug}.json"
    from release_notes import serialize_report, save_json

    save_json(cache_path, serialize_report(report))
    print(f"Wrote {cache_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
