"""MkDocs hook: links to code files and folders open on GitHub.

In the README files, links like [ping.py](ping.py) or [pyping/](pyping/) work on
GitHub but not on a static site. This hook rewrites them to repo_url/blob/main/...
(or tree/ for folders). Links to .md files and external links stay unchanged.
"""

import posixpath
import re

LINK = re.compile(r"(\]\()([^)\s#]+)(#[^)\s]*)?(\))")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


def on_page_markdown(markdown, page, config, files):
    repo = (config.repo_url or "").rstrip("/")
    if not repo:
        return markdown
    base = posixpath.dirname(page.file.src_uri)

    def rewrite(m):
        target = m.group(2)
        if "://" in target or target.startswith(("mailto:", "/")) or target.endswith(".md"):
            return m.group(0)
        path = posixpath.normpath(posixpath.join(base, target))
        kind = "tree" if target.endswith("/") else "blob"
        return f"{m.group(1)}{repo}/{kind}/main/{path}{m.group(3) or ''}{m.group(4)}"

    # Inside a code block, a closing fence uses the same character, is at least as
    # long, and has nothing after it. So a traceback line like "~~~~^^^^" does not close it.
    out, fence = [], None
    for line in markdown.splitlines(keepends=True):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
            out.append(line if m else LINK.sub(rewrite, line))
            continue
        if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
            fence = None
        out.append(line)
    return "".join(out)
