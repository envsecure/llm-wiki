#!/usr/bin/env python3
"""Build a Karpathy-style LLM wiki from the raw sources.

Layout (the three layers from the LLM Wiki idea file):

    raw/                 immutable sources (never edited)
    wiki/index.md        content-oriented catalog
    wiki/log.md          chronological log
    wiki/sources/*.md    one summary page per source
    wiki/concepts/*.md   concept pages that aggregate sources
    schema.md            the schema document (the agent contract)

Concept pages are linked to the sources that mention them and to each other
when they co-occur, so the vault has a real graph for Obsidian to draw.

Usage: build_wiki.py <vault-dir> [--raw raw] [--min-mentions 2]
"""

import argparse
import datetime
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

CONCEPTS = {
    "artificial intelligence": ["artificial intelligence", " ai ", "machine intelligence"],
    "machine learning": ["machine learning", "statistical learning"],
    "deep learning": ["deep learning", "deep neural"],
    "neural network": ["neural network", "neuron"],
    "large language model": ["large language model", "language model", "llm", "gpt"],
    "foundation model": ["foundation model", "pretrained model", "base model"],
    "transformer": ["transformer", "self-attention architecture"],
    "attention mechanism": ["attention mechanism", "attention layer", "attention weights"],
    "tokenization": ["tokenization", "tokenizer", "subword", "vocabulary"],
    "embedding": ["embedding", "vector representation", "word vector"],
    "vector database": ["vector database", "vector store", "vectordb", "ann index"],
    "retrieval-augmented generation": ["retrieval-augmented", "retrieval augmented", "rag"],
    "prompt engineering": ["prompt engineering", "prompt design", "system prompt"],
    "fine-tuning": ["fine-tuning", "fine tuning", "finetune", "fine-tune"],
    "self-supervised learning": ["self-supervised", "self supervised"],
    "supervised learning": ["supervised learning"],
    "unsupervised learning": ["unsupervised learning", "clustering"],
    "reinforcement learning": ["reinforcement learning", "rlhf", "reward model", "policy gradient"],
    "ai agent": ["ai agent", "agentic", "autonomous agent", "tool use"],
    "chatbot": ["chatbot", "chat bot", "conversational model"],
    "hallucination": ["hallucination", "hallucinate"],
    "knowledge graph": ["knowledge graph", "semantic network", "ontology"],
    "model context protocol": ["model context protocol", "mcp"],
    "wiki": ["wiki", "wikis", "wiki page", "knowledge base"],
    "hypertext": ["hypertext", "hyperlink", "hypertext links"],
    "markdown": ["markdown", "frontmatter", "wikilink", "wiki link"],
    "obsidian": ["obsidian"],
    "rag pipeline": ["indexing", "retrieval", "query time", "chunk"],
    "knowledge compounding": ["accumulation", "compounding", "incremental", "maintained"],
    "llm agent workflow": ["llm agent", "agentic workflow", "claude code", "codex", "opencode"],
    "dataview": ["dataview"],
    "marp": ["marp", "slide deck"],
    "web clipper": ["web clipper", "clipped", "clipping"],
    "local search": ["bm25", "hybrid search", "re-ranking", "search engine", "on-device"],
    "memex": ["memex", "vannevar", "associative trail"],
}

# Unique, human-facing names. Obsidian resolves [[links]] case-insensitively,
# so a concept named "artificial intelligence" and a source named
# "Artificial intelligence" would make BOTH links ambiguous. Every page
# therefore gets a distinct display name.
CONCEPT_DISPLAY = {
    "ai agent": "AI agent",
    "llm agent workflow": "LLM agent workflow",
    "rag pipeline": "RAG pipeline",
    "model context protocol": "Model Context Protocol",
    "web clipper": "Web clipper",
    "local search": "Local search",
    "knowledge compounding": "Knowledge compounding",
    "large language model": "Large language model",
    "retrieval-augmented generation": "Retrieval-augmented generation",
    "self-supervised learning": "Self-supervised learning",
    "supervised learning": "Supervised learning",
    "unsupervised learning": "Unsupervised learning",
    "reinforcement learning": "Reinforcement learning",
    "machine learning": "Machine learning",
    "deep learning": "Deep learning",
    "neural network": "Neural network",
    "artificial intelligence": "Artificial intelligence",
    "foundation model": "Foundation model",
    "attention mechanism": "Attention mechanism",
    "prompt engineering": "Prompt engineering",
    "fine-tuning": "Fine-tuning",
    "self-supervised": "Self-supervised",
    "tokenization": "Tokenization",
    "vector database": "Vector database",
    "knowledge graph": "Knowledge graph",
    "hallucination": "Hallucination",
    "chatbot": "Chatbot",
    "embedding": "Embedding",
    "transformer": "Transformer",
    "dataview": "Dataview",
    "marp": "Marp",
    "markdown": "Markdown",
    "hypertext": "Hypertext",
    "memex": "Memex",
    "obsidian": "Obsidian",
    "wiki": "Wiki",
}

SOURCE_DISPLAY = {
    "llm-wiki": "LLM Wiki (Karpathy)",
    "qmd": "qmd (GitHub)",
    "marp": "Marp (GitHub)",
    "dataview": "Dataview (GitHub)",
    "obsidian-web-clipper": "Obsidian Web Clipper (GitHub)",
    "tolkien-gateway": "Tolkien Gateway",
    "obsidian-help": "Obsidian Help",
    "obsidian-graph": "Obsidian Graph view",
    "obsidian-clipper-help": "Obsidian Clipper help",
    "as-we-may-think": "As We May Think (Bush 1945)",
}


def wikilink(target_slug: str, display: str) -> str:
    """Obsidian resolves [[links]] by file basename, so the link text carries the
    basename and the alias part carries the human-readable title."""
    return f"[[{target_slug}|{display}]]"


def concept_name(concept: str) -> str:
    return CONCEPT_DISPLAY.get(concept, concept[:1].upper() + concept[1:])


def source_name(source) -> str:
    slug_name = source["slug"]
    if slug_name in SOURCE_DISPLAY:
        return SOURCE_DISPLAY[slug_name]
    if slug_name.startswith("wikipedia-"):
        return f'{source["title"]} (Wikipedia)'
    return source["title"]


CATEGORY_RULES = [
    ("ai-core", ["wikipedia-artificial", "wikipedia-machine-learning", "wikipedia-deep-learning",
                 "wikipedia-neural", "wikipedia-supervised", "wikipedia-unsupervised",
                 "wikipedia-reinforcement", "wikipedia-self-supervised"]),
    ("llm-stack", ["wikipedia-large-language", "wikipedia-foundation", "wikipedia-transformer",
                   "wikipedia-attention", "wikipedia-tokenization", "wikipedia-embedding",
                   "wikipedia-vector-database", "wikipedia-retrieval-augmented",
                   "wikipedia-prompt-engineering", "wikipedia-fine-tuning",
                   "wikipedia-ai-agent", "wikipedia-chatbot", "wikipedia-hallucination",
                   "wikipedia-model-context-protocol"]),
    ("wiki-tooling", ["llm-wiki", "qmd", "dataview", "marp", "obsidian-web-clipper",
                      "obsidian-help", "obsidian-graph", "obsidian-clipper-help"]),
    ("foundations", ["wikipedia-knowledge-graph", "wikipedia-wiki", "wikipedia-hypertext",
                     "wikipedia-markdown", "wikipedia-software-as-a-service", "tolkien"]),
]

STOP = set("""the a an and or of to in for on with by is are was were be been being as at from that this
these those it its their his her they them we you i not no but if then than so such can could may
might will would shall should must do does did done have has had having which who whom whose what
when where why how all any both each few more most other some only own same too very s t just also
about into over under again further once here there when where why how""".split())


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "page"


def read_source(path: str):
    with open(path, encoding="utf-8", errors="replace") as handle:
        raw = handle.read()
    title = ""
    source_url = ""
    body = raw
    match = re.match(r"#\s+(.+)\n", raw)
    if match:
        title = match.group(1).strip()
    match = re.search(r"_source:\s*(\S+)", raw)
    if match:
        source_url = match.group(1)
    body = re.sub(r"^#\s+.+\n", "", raw)
    body = re.sub(r"^_(source|bytes):.*$", "", body, flags=re.M)
    return title or os.path.basename(path), source_url, body.strip()


def lead_paragraphs(text: str, limit: int = 900) -> str:
    text = re.sub(r"\n{2,}", "\n\n", text)
    blocks = [b.strip() for b in text.split("\n\n") if len(b.strip()) > 80]
    out = []
    for block in blocks:
        out.append(block)
        if sum(len(o) for o in out) > limit:
            break
    return "\n\n".join(out)[:limit]


def key_terms(text: str, count: int = 8):
    words = re.findall(r"[a-z][a-z\-]{4,}", text.lower())
    counter = Counter(w for w in words if w not in STOP)
    return [word for word, _ in counter.most_common(count)]


def classify(name: str) -> str:
    for category, prefixes in CATEGORY_RULES:
        for prefix in prefixes:
            if name.startswith(prefix):
                return category
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault")
    parser.add_argument("--raw", default="raw")
    parser.add_argument("--min-mentions", type=int, default=2)
    parser.add_argument("--only-seeded", action="store_true",
                        help="keep only the curated sources (seeds + Wikipedia articles)")
    args = parser.parse_args()

    vault = os.path.abspath(args.vault)
    raw_dir = os.path.join(vault, args.raw)
    wiki_dir = os.path.join(vault, "wiki")
    sources_dir = os.path.join(wiki_dir, "sources")
    concepts_dir = os.path.join(wiki_dir, "concepts")
    for path in (sources_dir, concepts_dir):
        os.makedirs(path, exist_ok=True)

    files = sorted(
        f for f in os.listdir(raw_dir)
        if f.endswith(".md") and not f.startswith("manifest")
    )

    # --only-seeded keeps the curated source set (the seeds plus the Wikipedia
    # articles) and drops the one-hop duplicates that the crawler picked up.
    only_seeded = args.only_seeded
    if only_seeded:
        # the curated set: every Wikipedia article plus the named seed pages.
        # One-hop crawler pages (marp-0, obsidian-web-clipper-3, ...) are
        # near-duplicates of the seeds and are left in raw/ but not ingested.
        seed_names = {
            "llm-wiki", "qmd", "marp", "dataview", "obsidian-web-clipper",
            "as-we-may-think", "tolkien-gateway", "obsidian-help",
            "obsidian-graph", "obsidian-clipper-help",
        }
        files = [
            f for f in files
            if f.startswith("wikipedia-") or f[:-3] in seed_names
        ]

    sources = []
    for filename in files:
        title, url, body = read_source(os.path.join(raw_dir, filename))
        slug_name = slug(filename[:-3])
        lower = (" " + body.lower() + " ")
        mentions = Counter()
        for concept, needles in CONCEPTS.items():
            hits = sum(lower.count(needle) for needle in needles)
            if hits:
                mentions[concept] = hits
        sources.append({
            "slug": slug_name,
            "title": title,
            "url": url,
            "body": body,
            "file": filename,
            "mentions": mentions,
            "category": classify(slug_name),
        })

    # concept -> sources, source -> concepts
    concept_sources = defaultdict(set)
    for source in sources:
        for concept, hits in source["mentions"].items():
            if hits >= args.min_mentions:
                concept_sources[concept].add(source["slug"])

    # concept co-occurrence -> related concepts
    concept_related = defaultdict(Counter)
    all_concepts = list(concept_sources.keys())
    for concept in all_concepts:
        members = concept_sources[concept]
        for other in members:
            if other == concept:
                continue
            other_members = concept_sources.get(other)
            if not other_members:
                continue
            for shared in all_concepts:
                if shared == concept:
                    continue
                if concept_sources.get(shared, set()) & other_members:
                    concept_related[concept][shared] += 1

    # related sources via shared concepts (kept sparse so the graph stays
    # readable: only pairs sharing two or more concepts, top 3 per source)
    source_related = defaultdict(Counter)
    for concept, members in concept_sources.items():
        members = sorted(members)
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                source_related[left][right] += 1
                source_related[right][left] += 1
    for name in list(source_related):
        source_related[name] = Counter(
            {other: hits for other, hits in source_related[name].most_common(3) if hits >= 2}
        )

    today = datetime.date.today().isoformat()
    log_lines = [f"# Log", "", "Chronological record of wiki activity.", ""]

    # ---- source pages ----
    for source in sources:
        name = source["slug"]
        concepts = sorted(
            (c for c in source["mentions"] if c in concept_sources and source["slug"] in concept_sources[c]),
            key=lambda c: -source["mentions"][c],
        )[:6]
        related = [s for s, _ in source_related[name].most_common(4)]
        title = source_name(source)
        lines = [
            "---",
            f'title: "{title.replace(chr(34), chr(39))}"',
            f'aliases: ["{title.replace(chr(34), chr(39))}"]',
            f"source: {source['url']}",
            f"category: {source['category']}",
            f"ingested: {today}",
            "type: source",
            "---",
            "",
            f"# {title}",
            "",
            f"> Raw source: {source['url']}",
            "> Immutable source document — the wiki summarises it, it never edits it.",
            "",
            "## Summary",
            "",
            lead_paragraphs(source["body"]),
            "",
            "## Key terms",
            "",
        ]
        terms = key_terms(source["body"])
        lines.append(", ".join(f"`{t}`" for t in terms) or "—")
        lines += ["", "## Concepts", ""]
        if concepts:
            for concept in concepts:
                lines.append(f"- {wikilink(slug(concept), concept_name(concept))}")
        else:
            lines.append("- (no concept pages reference this source yet)")
        lines += ["", "## Related sources", ""]
        for other in related:
            other_title = next((source_name(s) for s in sources if s["slug"] == other), other)
            lines.append(f"- {wikilink(other, other_title)}")
        lines.append("")
        with open(os.path.join(sources_dir, f"{name}.md"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        log_lines.append(f"## [{today}] ingest | {title}")
        log_lines.append(f"- created `wiki/sources/{name}.md` from {source['url']}")
        log_lines.append(f"- concepts: {', '.join(concepts) if concepts else 'none'}")
        log_lines.append("")

    # ---- concept pages ----
    for concept, members in sorted(concept_sources.items()):
        name = slug(concept)
        display = concept_name(concept)
        member_titles = []
        for member in sorted(members):
            member_titles.append(next((source_name(s) for s in sources if s["slug"] == member), member))
        related = [c for c, _ in concept_related[concept].most_common(6)]
        lines = [
            "---",
            f'title: "{display}"',
            f'aliases: ["{display}"]',
            f"category: concepts",
            f"updated: {today}",
            "type: concept",
            "---",
            "",
            f"# {display}",
            "",
            f"Concept page. **{len(members)}** sources mention it.",
            "",
            "## Sources",
            "",
        ]
        for member, title in zip(sorted(members), member_titles):
            lines.append(f"- {wikilink(member, title)}")
        lines += ["", "## Related concepts", ""]
        for other in related:
            lines.append(f"- {wikilink(slug(other), concept_name(other))}")
        lines += [
            "",
            "## Synthesis",
            "",
            f"*{concept}* appears across {len(members)} of the ingested sources. "
            f"It is the most connected idea in this part of the wiki"
            + (f", recurring together with {related[0]}." if related else ".")
            if related else
            f"*{concept}* appears across {len(members)} of the ingested sources.",
            "",
        ]
        with open(os.path.join(concepts_dir, f"{name}.md"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    # ---- index ----
    by_category = defaultdict(list)
    for source in sources:
        by_category[source["category"]].append(source)

    index = [
        "---",
        'title: "Index"',
        f"updated: {today}",
        "type: index",
        "---",
        "",
        "# Index",
        "",
        f"Catalog of the wiki: **{len(sources)}** sources and "
        f"**{len(concept_sources)}** concept pages.",
        "",
        "Start with a concept page, follow it to the sources, then read the raw document.",
        "",
    ]
    for category in sorted(by_category):
        index.append(f"## {category}")
        index.append("")
        for source in sorted(by_category[category], key=lambda s: s["title"].lower()):
            terms = key_terms(source["body"], 4)
            summary = f"covers {', '.join(terms)}" if terms else "reference document"
            index.append(f"- {wikilink(source['slug'], source_name(source))} — {summary}")
        index.append("")
    index.append("## Concepts")
    index.append("")
    for concept in sorted(concept_sources):
        index.append(f"- {wikilink(slug(concept), concept_name(concept))} — {len(concept_sources[concept])} sources")
    index.append("")
    with open(os.path.join(wiki_dir, "index.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(index))

    # ---- log ----
    log = [
        "---",
        'title: "Log"',
        "type: log",
        "---",
        "",
        "# Log",
        "",
        "Chronological record of wiki activity. Parseable with "
        '`grep "^## \\[" log.md | tail -5`.',
        "",
    ] + log_lines
    with open(os.path.join(wiki_dir, "log.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(log))

    # ---- schema ----
    schema = f"""---
title: "Schema"
type: schema
---

# Schema — how this wiki is maintained

This document is the agent contract for the wiki. An LLM agent reading a source
follows it to keep the wiki consistent.

## Layers

| Layer | Location | Who writes it |
| --- | --- | --- |
| Raw sources | `{args.raw}/` | nobody — immutable, the source of truth |
| Wiki | `wiki/` | the agent |
| Schema | `schema.md` | humans and the agent, together |

## Page conventions

* Every page starts with YAML frontmatter: `title`, `type`, and for source pages
  `source`, `category`, `ingested`.
* `wiki/index.md` is content-oriented: a catalog of every page with a one-line summary.
* `wiki/log.md` is chronological: one `## [YYYY-MM-DD] ingest | Title` entry per operation.
* Source pages live in `wiki/sources/`, concept pages in `wiki/concepts/`.
* Concept pages are the hubs: they link to the sources that mention them and to the
  concepts they co-occur with.

## Operations

* **Ingest** — read a raw source, create or update its source page, update every
  concept page it touches, refresh `wiki/index.md`, append to `wiki/log.md`.
* **Query** — read `wiki/index.md` first, drill into concept pages, cite sources.
* **Lint** — look for contradictions between pages, stale claims, orphan pages with
  no inbound links, and concepts mentioned in the sources but without their own page.

## Current state

* {len(sources)} raw sources ingested
* {len(concept_sources)} concept pages
* {sum(len(v) for v in concept_sources.values())} source ↔ concept links
"""
    with open(os.path.join(vault, "schema.md"), "w", encoding="utf-8") as handle:
        handle.write(schema)

    summary = {
        "sources": len(sources),
        "concepts": len(concept_sources),
        "source_concept_links": sum(len(v) for v in concept_sources.values()),
        "concept_related_links": sum(len(v) for v in concept_related.values()),
        "source_related_links": sum(len(v) for v in source_related.values()),
        "categories": {k: len(v) for k, v in by_category.items()},
        "graph": {
            "nodes": (
                [{"id": s["slug"], "kind": "source", "title": s["title"], "category": s["category"]} for s in sources]
                + [{"id": f"concept:{slug(c)}", "kind": "concept", "title": c} for c in concept_sources]
            ),
            "edges": sorted(
                [{"source": f"concept:{slug(c)}", "target": s, "kind": "mentions"} for c, members in concept_sources.items() for s in members]
                + [{"source": a, "target": b, "kind": "related"} for a, rel in source_related.items() for b in rel]
                + [{"source": f"concept:{slug(c)}", "target": f"concept:{slug(o)}", "kind": "related"} for c, rel in concept_related.items() for o in rel],
                key=lambda e: (e["source"], e["target"], e["kind"]),
            ),
        },
    }
    with open(os.path.join(vault, "graph.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)

    print(f"sources   : {summary['sources']}")
    print(f"concepts  : {summary['concepts']}")
    print(f"links     : {summary['source_concept_links']} source↔concept, "
          f"{summary['concept_related_links']} concept↔concept, "
          f"{summary['source_related_links']} source↔source")
    print(f"graph     : {len(summary['graph']['nodes'])} nodes, {len(summary['graph']['edges'])} edges")
    print(f"vault     : {vault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
