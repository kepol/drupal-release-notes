"""Fetch GitLab issue and merge request comments for credit audit context."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from report import (
    CACHE_DIR,
    GITLAB_PROJECT_ENCODED,
    ApiClient,
    gitlab_token_configured,
    load_json,
    normalize_username,
    save_json,
)

ISSUE_ACTIVITY_CACHE = CACHE_DIR / "issue_activity.json"
GITLAB_MR_URL = "https://git.drupalcode.org/project/ai_context/-/merge_requests/{iid}"
NOTE_BODY_LIMIT = 200
BOT_USERNAMES = {"drupalbot", "system", "system_message", "ghost"}


def normalize_note_body(body: str, limit: int = NOTE_BODY_LIMIT) -> str:
    text = re.sub(r"<[^>]+>", " ", body or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def fetch_paginated(client: ApiClient, base_url: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in base_url else "?"
        url = f"{base_url}{separator}page={page}"
        batch = client.get_json(url)
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.05)
    return items


def find_merge_requests(client: ApiClient, issue_iid: int) -> list[dict[str, Any]]:
    seen: set[int] = set()
    merge_requests: list[dict[str, Any]] = []

    def add_batch(batch: list[dict[str, Any]]) -> None:
        for merge_request in batch:
            mr_iid = int(merge_request["iid"])
            if mr_iid in seen:
                continue
            branch = merge_request.get("source_branch") or ""
            title = merge_request.get("title") or ""
            description = merge_request.get("description") or ""
            if (
                str(issue_iid) in branch
                or str(issue_iid) in title
                or f"#{issue_iid}" in title
                or f"#{issue_iid}" in description
                or f"Closes #{issue_iid}" in description
                or f"closes #{issue_iid}" in description
            ):
                seen.add(mr_iid)
                merge_requests.append(
                    {
                        "iid": mr_iid,
                        "title": title,
                        "web_url": merge_request.get(
                            "web_url",
                            GITLAB_MR_URL.format(iid=mr_iid),
                        ),
                    }
                )

    related_url = (
        f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/issues/"
        f"{issue_iid}/related_merge_requests"
    )
    try:
        add_batch(client.get_json(related_url))
    except requests.HTTPError:
        pass

    search_url = (
        f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/"
        f"merge_requests?search={issue_iid}&state=all&per_page=100"
    )
    try:
        add_batch(client.get_json(search_url))
    except requests.HTTPError:
        pass

    merge_requests.sort(key=lambda item: item["iid"])
    return merge_requests


def fetch_issue_notes(client: ApiClient, issue_iid: int) -> list[dict[str, Any]]:
    base_url = (
        f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/issues/"
        f"{issue_iid}/notes?per_page=100&sort=asc&order_by=created_at"
    )
    return fetch_paginated(client, base_url)


def fetch_merge_request_notes(client: ApiClient, mr_iid: int) -> list[dict[str, Any]]:
    base_url = (
        f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ENCODED}/"
        f"merge_requests/{mr_iid}/notes?per_page=100&sort=asc&order_by=created_at"
    )
    return fetch_paginated(client, base_url)


def parse_note(note: dict[str, Any]) -> dict[str, str] | None:
    if note.get("system"):
        return None
    author = note.get("author") or {}
    username = author.get("username")
    if not username or normalize_username(username) in BOT_USERNAMES:
        return None
    body = normalize_note_body(note.get("body", ""))
    if not body:
        return None
    created = note.get("created_at") or ""
    if created:
        created = created.replace("T", " ").replace("Z", " UTC")[:19]
    return {
        "author": normalize_username(username),
        "created_at": created,
        "body": body,
    }


def comments_for_users(
    notes: list[dict[str, Any]],
    usernames: set[str],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {user: [] for user in usernames}
    for note in notes:
        parsed = parse_note(note)
        if parsed is None or parsed["author"] not in usernames:
            continue
        grouped[parsed["author"]].append(
            {"created_at": parsed["created_at"], "body": parsed["body"]}
        )
    return {user: comments for user, comments in grouped.items() if comments}


def fetch_issue_user_activity(
    client: ApiClient,
    issue_iid: int,
    usernames: list[str],
) -> dict[str, Any]:
    normalized = sorted({normalize_username(user) for user in usernames})
    activity: dict[str, Any] = {
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "users": {user: {"issue": [], "merge_requests": []} for user in normalized},
        "merge_request_refs": [],
    }

    issue_notes = fetch_issue_notes(client, issue_iid)
    issue_comments = comments_for_users(issue_notes, set(normalized))
    for user, comments in issue_comments.items():
        activity["users"][user]["issue"] = comments

    merge_requests = find_merge_requests(client, issue_iid)
    activity["merge_request_refs"] = merge_requests
    for merge_request in merge_requests:
        mr_notes = fetch_merge_request_notes(client, int(merge_request["iid"]))
        mr_comments = comments_for_users(mr_notes, set(normalized))
        for user, comments in mr_comments.items():
            activity["users"][user]["merge_requests"].append(
                {
                    "mr_iid": merge_request["iid"],
                    "mr_title": merge_request.get("title", ""),
                    "mr_url": merge_request.get("web_url"),
                    "comments": comments,
                }
            )

    return activity


def load_activity_cache() -> dict[str, Any]:
    return load_json(ISSUE_ACTIVITY_CACHE, {})


def save_activity_cache(cache: dict[str, Any]) -> None:
    save_json(ISSUE_ACTIVITY_CACHE, cache)


def get_cached_activity(
    cache: dict[str, Any],
    issue_iid: int,
    usernames: list[str],
) -> dict[str, Any] | None:
    entry = cache.get(str(issue_iid))
    if not entry:
        return None
    cached_users = sorted(entry.get("users", {}).keys())
    if cached_users != sorted({normalize_username(user) for user in usernames}):
        return None
    return entry


def enrich_issues_with_gitlab_activity(
    client: ApiClient,
    issues: list[Any],
    *,
    refresh: bool = False,
) -> None:
    """Attach GitLab comment context to audit issues (mutates user_activity field)."""
    if not gitlab_token_configured():
        return

    pending = [issue for issue in issues if issue.uncredited]
    if not pending:
        return

    cache = load_activity_cache()
    print(f"Loading GitLab comments for {len(pending)} issues...")
    for index, issue in enumerate(pending, start=1):
        cached = None if refresh else get_cached_activity(cache, issue.iid, issue.uncredited)
        if cached is None:
            try:
                cached = fetch_issue_user_activity(client, issue.iid, issue.uncredited)
            except requests.HTTPError as exc:
                print(f"  warning: GitLab activity failed for #{issue.iid}: {exc}")
                cached = {
                    "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
                    "users": {
                        normalize_username(user): {"issue": [], "merge_requests": []}
                        for user in issue.uncredited
                    },
                    "merge_request_refs": [],
                    "error": str(exc),
                }
            cache[str(issue.iid)] = cached
            save_activity_cache(cache)
            time.sleep(0.2)
        issue.user_activity = cached.get("users", {})
        if index % 10 == 0 or index == len(pending):
            print(f"  activity {index}/{len(pending)}")


def format_user_activity_lines(user: str, activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    user_data = activity.get(normalize_username(user), {})
    issue_comments = user_data.get("issue") or []
    mr_entries = user_data.get("merge_requests") or []

    if issue_comments:
        lines.append(f"    Issue comments by `{user}`:")
        for comment in issue_comments:
            when = comment.get("created_at") or "unknown date"
            lines.append(f"      - [{when}] {comment.get('body', '')}")
    else:
        lines.append(f"    Issue comments by `{user}`: none")

    mr_comment_count = sum(len(entry.get("comments") or []) for entry in mr_entries)
    if mr_entries:
        if mr_comment_count:
            lines.append(f"    Merge request comments by `{user}`:")
        else:
            lines.append(
                f"    Merge request comments by `{user}`: none "
                f"({len(mr_entries)} linked MR(s))"
            )
        for entry in mr_entries:
            comments = entry.get("comments") or []
            if not comments:
                continue
            mr_label = entry.get("mr_title") or f"!{entry.get('mr_iid')}"
            lines.append(f"      MR !{entry.get('mr_iid')} ({mr_label}):")
            for comment in comments:
                when = comment.get("created_at") or "unknown date"
                lines.append(f"        - [{when}] {comment.get('body', '')}")
    else:
        lines.append(f"    Merge request comments by `{user}`: no linked MR found")

    return lines
