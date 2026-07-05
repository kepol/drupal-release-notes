"""HTML helpers for Drupal.org-compatible report output."""

from __future__ import annotations

import html as html_module
from typing import Sequence


def escape(text: str) -> str:
    return html_module.escape(str(text), quote=True)


def tag(name: str, content: str = "", **attrs: str) -> str:
    attr_str = "".join(
        f' {key}="{escape(value)}"' for key, value in attrs.items() if value is not None
    )
    if content:
        return f"<{name}{attr_str}>{content}</{name}>"
    return f"<{name}{attr_str}></{name}>"


def h2(text: str) -> str:
    return tag("h2", escape(text))


def h3(text: str) -> str:
    return tag("h3", escape(text))


def h4(text: str) -> str:
    return tag("h4", escape(text))


def p(content: str) -> str:
    return tag("p", content)


def strong(text: str) -> str:
    return tag("strong", escape(text))


def em(text: str) -> str:
    return tag("em", escape(text))


def code(text: str) -> str:
    return tag("code", escape(text))


def a(href: str, text: str) -> str:
    return tag("a", escape(text), href=href)


def ul(items: Sequence[str]) -> str:
    if not items:
        return ""
    rendered: list[str] = []
    for item in items:
        if item.startswith("<li"):
            rendered.append(item)
        else:
            rendered.append(li(item))
    return tag("ul", "\n".join(rendered))


def li(content: str) -> str:
    return tag("li", content)


def pre_block(content: str) -> str:
    return tag("pre", tag("code", escape(content)))


def join_blocks(blocks: Sequence[str]) -> str:
    return "\n".join(block for block in blocks if block)


def format_issue_link(iid: int, url: str) -> str:
    return a(url, f"#{iid}")


def format_issue_text(
    iid: int,
    title: str,
    url: str,
    *,
    extra: str = "",
) -> str:
    """Issue <a href=\"...\">#3574905</a>: Title."""
    clean_title = escape(title.strip().rstrip("."))
    text = f"Issue {format_issue_link(iid, url)}: {clean_title}."
    if extra:
        text = f"{text} {extra.lstrip()}"
    return text


def format_issue_item(
    iid: int,
    title: str,
    url: str,
    *,
    extra: str = "",
    nested: Sequence[str] | None = None,
) -> str:
    content = format_issue_text(iid, title, url, extra=extra)
    if nested:
        content = f"{content}\n{ul(nested)}"
    return li(content)


def format_issue_list(
    issues: Sequence[tuple[int, str, str]],
    *,
    extra_for: dict[int, str] | None = None,
) -> str:
    items: list[str] = []
    extras = extra_for or {}
    for iid, title, url in issues:
        items.append(format_issue_item(iid, title, url, extra=extras.get(iid, "")))
    return ul(items)


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = tag("thead", tag("tr", "".join(tag("th", escape(cell)) for cell in headers)))
    body_rows = []
    for row in rows:
        body_rows.append(
            tag("tr", "".join(tag("td", escape(cell)) for cell in row))
        )
    body = tag("tbody", "\n".join(body_rows))
    return tag("table", f"{head}\n{body}")
