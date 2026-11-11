---
title: "Dataview (GitHub)"
aliases: ["Dataview (GitHub)"]
source: https://raw.githubusercontent.com/blacksmithgu/obsidian-dataview/master/README.md
category: wiki-tooling
ingested: 2026-11-11
type: source
---

# Dataview (GitHub)

> Raw source: https://raw.githubusercontent.com/blacksmithgu/obsidian-dataview/master/README.md
> Immutable source document — the wiki summarises it, it never edits it.

## Summary

Treat your [Obsidian Vault](https://obsidian.md/) as a database which you can query from. Provides a JavaScript API and
pipeline-based query language for filtering, sorting, and extracting data from Markdown pages. See the Examples section
below for some quick examples, or the full [reference](https://blacksmithgu.github.io/obsidian-dataview/) for all the details.

~~~markdown
```dataview
table time-played, length, rating
from "games"
sort rating desc
```
~~~

List all markdown [tasks](https://blacksmithgu.github.io/obsidian-dataview/data-annotation/#tasks) in un-completed projects:

Show all files in the `books` folder that you read in 2021, grouped by genre and sorted by rating:

~~~markdown
```dataviewjs
for (let group of dv.pages("#book").where(p => p["time-read"].year == 2021).groupBy(p => p.genre)) {
	dv.header(3, group.key);
	dv.table(["Name", "Time Read", "Rating"],
		group.rows


## Key terms

`dataview`, `obsidian-dataview`, `markdown`, `https`, `blacksmithgu`, `rating`, `github`, `inline`

## Concepts

- [[dataview|Dataview]]
- [[obsidian|Obsidian]]
- [[markdown|Markdown]]

## Related sources

- [[llm-wiki|LLM Wiki (Karpathy)]]
- [[obsidian-web-clipper|Obsidian Web Clipper (GitHub)]]
