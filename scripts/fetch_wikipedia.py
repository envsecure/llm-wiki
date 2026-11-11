#!/usr/bin/env python3
"""Fetch AI-related Wikipedia articles as plain-text sources for the wiki.

Uses the MediaWiki action API with `explaintext`, so the raw sources are
clean, immutable text (the wiki layer will summarise and cross-link them).

Usage: fetch_wikipedia.py <output-dir>
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"

ARTICLES = [
    ("artificial-intelligence", "Artificial intelligence"),
    ("machine-learning", "Machine learning"),
    ("deep-learning", "Deep learning"),
    ("neural-network", "Neural network"),
    ("large-language-model", "Large language model"),
    ("foundation-model", "Foundation model"),
    ("transformer-architecture", "Transformer (deep learning architecture)"),
    ("attention-mechanism", "Attention mechanism"),
    ("tokenization", "Tokenization (lexical analysis)"),
    ("embedding", "Embedding (machine learning)"),
    ("vector-database", "Vector database"),
    ("retrieval-augmented-generation", "Retrieval-augmented generation"),
    ("prompt-engineering", "Prompt engineering"),
    ("fine-tuning", "Fine-tuning (machine learning)"),
    ("self-supervised-learning", "Self-supervised learning"),
    ("supervised-learning", "Supervised learning"),
    ("unsupervised-learning", "Unsupervised learning"),
    ("reinforcement-learning", "Reinforcement learning"),
    ("ai-agent", "AI agent"),
    ("chatbot", "Chatbot"),
    ("ai-hallucination", "Hallucination (artificial intelligence)"),
    ("knowledge-graph", "Knowledge graph"),
    ("model-context-protocol", "Model Context Protocol"),
    ("software-as-a-service", "Software as a service"),
    ("wiki", "Wiki"),
    ("hypertext", "Hypertext"),
    ("markdown", "Markdown"),
]

UA = {"User-Agent": "obsidian-clone-wiki/1.0 (local research build)"}


def fetch_titles(titles):
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "exsectionformat": "plain",
        "exlimit": "max",
        "format": "json",
        "redirects": "1",
        "titles": "|".join(titles),
    }
    url = API + "?" + urllib.parse.urlencode(params)
    delay = 2.5
    for attempt in range(6):
        request = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("exhausted retries")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    outdir = sys.argv[1]
    force = "--force" in sys.argv
    os.makedirs(outdir, exist_ok=True)

    manifest = []
    # The extracts API only returns one full-text extract per request
    # (exlimit > 1 requires exintro), so each article is requested separately.
    batches = [[article] for article in ARTICLES]

    for chunk in batches:
        titles = [t for _, t in chunk]
        try:
            data = fetch_titles(titles)
        except Exception as exc:  # noqa: BLE001
            print(f"  batch failed: {exc}", file=sys.stderr)
            time.sleep(2)
            continue
        pages = data.get("query", {}).get("pages", {})
        by_title = {p.get("title"): p for p in pages.values()}
        # Redirects and normalisations change the returned title, so resolve
        # the requested title through them before looking the page up.
        aliases = {}
        for key in ("normalized", "redirects"):
            for entry in data.get("query", {}).get(key, []) or []:
                if entry.get("from") and entry.get("to"):
                    aliases[entry["from"]] = entry["to"]
        for slug, title in chunk:
            resolved = aliases.get(title, title)
            page = by_title.get(resolved) or by_title.get(title)
            filename = f"wikipedia-{slug}.md"
            target = os.path.join(outdir, filename)
            if os.path.exists(target) and not force:
                print(f"  --  {title:46} already fetched")
                manifest.append({
                    "name": slug, "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "file": filename,
                    "bytes": os.path.getsize(target),
                })
                continue
            if not page or "extract" not in page:
                print(f"  missing: {title}", file=sys.stderr)
                continue
            extract = page["extract"]
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(
                    f"# {title}\n\n"
                    f"_source: https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}_\n"
                    f"_bytes: {len(extract)}\n\n{extract}\n"
                )
            manifest.append({
                "name": slug,
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                "file": filename,
                "bytes": len(extract),
            })
            print(f"  ok  {title:46} {len(extract):>8} chars")
        time.sleep(2.5)

    manifest_path = os.path.join(outdir, "manifest-wikipedia.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    print(f"\nfetched {len(manifest)} Wikipedia articles into {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
