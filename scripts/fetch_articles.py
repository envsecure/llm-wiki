#!/usr/bin/env python3
"""Fetch the sources referenced by Karpathy's "LLM Wiki" idea file (plus one hop
of links) so they can be ingested into a wiki and their connections mapped.

Usage: fetch_articles.py <output-dir> [--hops 1] [--max-per-page 12]
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) obsidian-clone-wiki/1.0"}

# Seeds: the resources the LLM Wiki document actually names, plus the primary
# source it credits (Vannevar Bush's 1945 Memex paper).
SEEDS = [
    ("llm-wiki", "https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw"),
    ("qmd", "https://raw.githubusercontent.com/tobi/qmd/main/README.md"),
    ("marp", "https://raw.githubusercontent.com/marp-team/marp/main/README.md"),
    ("dataview", "https://raw.githubusercontent.com/blacksmithgu/obsidian-dataview/master/README.md"),
    ("obsidian-web-clipper", "https://raw.githubusercontent.com/obsidianmd/obsidian-clipper/main/README.md"),
    ("as-we-may-think", "https://www.cs.umd.edu/~ben/papers/1945aswemaythink.pdf"),
    ("tolkien-gateway", "https://tolkiengateway.net/wiki/Main_Page"),
    ("obsidian-help", "https://help.obsidian.md/Getting+started/How+Obsidian+stores+data"),
    ("obsidian-graph", "https://help.obsidian.md/Plugins/Graph+view"),
    ("obsidian-clipper-help", "https://help.obsidian.md/Plugins/Obsidian+Web+Clipper"),
]

# Only follow links that look like articles/docs (no social media, no binaries).
SKIP_HOSTS = {
    "twitter.com", "x.com", "youtube.com", "youtu.be", "facebook.com",
    "instagram.com", "linkedin.com", "reddit.com", "discord.com", "slack.com",
    "patreon.com", "paypal.com", "amazon.com", "buy.me", "ko-fi.com",
    "opensource.org", "creativecommons.org", "wikipedia.org",
}
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip", ".mp4",
            ".webm", ".ico", ".woff", ".woff2", ".ttf", ".exe", ".dmg", ".apk")
ARTICLE_HOSTS = {
    "raw.githubusercontent.com", "gist.githubusercontent.com", "github.com",
    "help.obsidian.md", "tolkiengateway.net", "marp.app", "qmd.tobi.li",
    "www.cs.umd.edu", "huggingface.co", "arxiv.org",
}

LINK_RE = re.compile(r'<a[^>]+href=["\']([^"\'#]+)["\']', re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def fetch(url: str, timeout: int = 45) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            return response.status, content_type, raw
    except urllib.error.HTTPError as exc:
        return exc.code, "", b""
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc), b""


def to_text(raw: bytes, content_type: str) -> str:
    if "pdf" in content_type.lower() or raw[:4] == b"%PDF":
        return "[binary pdf document] " + str(len(raw)) + " bytes"
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def html_to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|nav|footer|svg)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<!--.*?-->", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>", "\n", page)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t\r\f\v]+", " ", page)
    page = re.sub(r"\n\s*\n\s*\n+", "\n\n", page)
    return page.strip()


def slug(name: str) -> str:
    keep = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-").lower()
    return keep[:80] or "page"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--hops", type=int, default=1)
    parser.add_argument("--max-per-page", type=int, default=12)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    manifest = []
    seen = set()
    frontier = list(SEEDS)
    hop = 0

    while frontier and hop <= args.hops:
        next_frontier = []
        for name, url in frontier:
            key = url.split("#")[0]
            if key in seen:
                continue
            seen.add(key)
            status, content_type, raw = fetch(url)
            if status != 200:
                print(f"  [{status}] {url}", file=sys.stderr)
                continue
            text = to_text(raw, content_type)
            if "html" in content_type.lower():
                title_match = TITLE_RE.search(text)
                title = html.unescape(title_match.group(1)).strip() if title_match else name
                body = html_to_text(text)
                links = [urllib.parse.urljoin(url, href) for href in LINK_RE.findall(text)]
            else:
                title = name
                body = text
                links = re.findall(r"\[[^\]]*\]\((https?://[^)\s]+)\)", text)
                links += re.findall(r"https?://[^\s)\"']+", text)

            filename = f"{slug(name)}.md"
            with open(os.path.join(args.outdir, filename), "w", encoding="utf-8") as handle:
                handle.write(f"# {title}\n\n_source: {url}\n_bytes: {len(raw)}\n\n{body}\n")

            kept = []
            for link in links:
                parsed = urllib.parse.urlparse(link)
                host = parsed.netloc.lower().replace("www.", "")
                if host in SKIP_HOSTS or parsed.scheme not in ("http", "https"):
                    continue
                if parsed.path.lower().endswith(SKIP_EXT):
                    continue
                if host not in ARTICLE_HOSTS:
                    continue
                kept.append(link.split("#")[0])
            kept = list(dict.fromkeys(kept))[: args.max_per_page]

            manifest.append({
                "name": name,
                "title": title,
                "url": url,
                "file": filename,
                "bytes": len(raw),
                "out_links": kept,
            })
            print(f"  ok {status} {name:22} {len(raw):>8} B  -> {filename} ({len(kept)} links)")
            next_frontier.extend((f"{name}-{i}", link) for i, link in enumerate(kept))

            time.sleep(0.3)

        frontier = next_frontier
        hop += 1

    with open(os.path.join(args.outdir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    print(f"\nfetched {len(manifest)} pages into {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
