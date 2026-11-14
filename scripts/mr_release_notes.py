#!/usr/bin/env python3
"""Collect the release notes sections from merged MRs of a GitLab milestone.

For each closed issue in the milestone, this script reads the merged merge
requests whose title names the issue ("Issue #1234: ..."). It copies the
"Release note" or "Release notes" section of each MR description. When no MR
has the section, it uses the "Release notes snippet" section of the issue.

The result is saved to {project}/cache/mr_release_notes/{milestone}.json.
release_notes.py adds these notes at the end of the release notes report.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from project import ProjectConfig, add_project_argument
from release_notes import ApiClient, mr_release_notes_cache_path, save_json

GITLAB_API = "https://git.drupalcode.org/api/v4"

# A heading or bold label such as "### Release note", "## Release notes",
# "### Release notes snippet" or "**Release notes**".
SECTION_HEADING = re.compile(
    r"^(?P<hashes>#{1,6})\s*release[ -]?notes?(?:\s+snippet)?\s*:?\s*$"
    r"|^\*\*release[ -]?notes?(?:\s+snippet)?:?\*\*\s*:?\s*$",
    re.IGNORECASE,
)
# An inline label such as "Release note: Corrected the ...".
INLINE_LABEL = re.compile(
    r"^release[ -]?notes?(?:\s+snippet)?\s*:\s*(?P<text>\S.*)$",
    re.IGNORECASE,
)
ANY_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+\S")


def extract_release_notes(text: str | None) -> str:
    """Return the release notes section of a description, or ''.

    The section ends at the next heading of the same or a higher level. A
    section without a heading level (bold or inline label) ends at the next
    heading of any level.
    """
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").split("\n")
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = SECTION_HEADING.match(stripped)
        inline = INLINE_LABEL.match(stripped) if not heading else None
        if not heading and not inline:
            continue

        level = len(heading.group("hashes")) if heading and heading.group("hashes") else 7
        body: list[str] = [inline.group("text")] if inline else []
        fence = False
        for following in lines[index + 1:]:
            check = following.strip()
            if check.startswith("```"):
                fence = not fence
            if not fence:
                next_heading = ANY_HEADING.match(check)
                if next_heading and len(next_heading.group("hashes")) <= min(level, 6):
                    break
                if check.startswith("> [!note]"):
                    break
            body.append(following)
        return "\n".join(body).strip()
    return ""


def fetch_all(client: ApiClient, url: str) -> list[dict[str, Any]]:
    """Fetch every page of a GitLab list endpoint."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in url else "?"
        batch = client.get_json(f"{url}{separator}per_page=100&page={page}")
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def collect_milestone_notes(
    client: ApiClient,
    project: ProjectConfig,
    milestone: str,
) -> list[dict[str, Any]]:
    """Collect one entry per closed milestone issue with a merged MR."""
    base = f"{GITLAB_API}/projects/{project.gitlab_project_encoded}"
    issues = fetch_all(
        client,
        f"{base}/issues?state=closed&milestone={quote(milestone, safe='')}",
    )
    entries: list[dict[str, Any]] = []
    for issue in sorted(issues, key=lambda item: item["iid"]):
        iid = int(issue["iid"])
        related = client.get_json(f"{base}/issues/{iid}/related_merge_requests")
        own = [
            mr
            for mr in related
            if mr.get("state") == "merged"
            and mr.get("project_id") == issue.get("project_id")
            and re.search(rf"#{iid}\b", mr.get("title") or "")
        ]
        if not own:
            continue

        notes: list[dict[str, Any]] = []
        for mr in sorted(own, key=lambda item: item["iid"]):
            detail = client.get_json(f"{base}/merge_requests/{mr['iid']}")
            text = extract_release_notes(detail.get("description"))
            if text:
                notes.append({"mr_iid": int(mr["iid"]), "text": text})

        source = "merge_request"
        if not notes:
            text = extract_release_notes(issue.get("description"))
            if text:
                notes.append({"mr_iid": None, "text": text})
                source = "issue"
            else:
                source = "none"

        entries.append(
            {
                "iid": iid,
                "title": issue["title"],
                "merge_requests": [int(mr["iid"]) for mr in own],
                "source": source,
                "notes": notes,
            }
        )
        print(f"  #{iid}: {len(own)} merged MR(s), release notes from {source}")
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--milestone",
        required=True,
        help='GitLab milestone title, for example "1.0.0-rc2".',
    )
    add_project_argument(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = ProjectConfig.load(args.project)
    project.ensure_dirs()
    client = ApiClient(project)

    print(f"Collecting MR release notes for {args.milestone}...")
    entries = collect_milestone_notes(client, project, args.milestone)
    path = mr_release_notes_cache_path(project, args.milestone)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(
        path,
        {
            "milestone": args.milestone,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "entries": entries,
        },
    )
    missing = [entry["iid"] for entry in entries if entry["source"] == "none"]
    print(f"Wrote {path} ({len(entries)} issues with merged MRs)")
    if missing:
        print(
            "No release notes section: "
            + ", ".join(f"#{iid}" for iid in missing),
            file=sys.stderr,
        )
    print(
        "Run release_notes.py for this period to add the notes to the report:\n"
        f'  python3 scripts/release_notes.py --period "{args.milestone}"'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
