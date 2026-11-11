---
title: "Schema"
type: schema
---

# Schema — how this wiki is maintained

This document is the agent contract for the wiki. An LLM agent reading a source
follows it to keep the wiki consistent.

## Layers

| Layer | Location | Who writes it |
| --- | --- | --- |
| Raw sources | `raw/` | nobody — immutable, the source of truth |
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

* 36 raw sources ingested
* 35 concept pages
* 235 source ↔ concept links
