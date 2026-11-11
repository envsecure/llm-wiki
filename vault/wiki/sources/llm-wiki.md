---
title: "LLM Wiki (Karpathy)"
aliases: ["LLM Wiki (Karpathy)"]
source: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw
category: wiki-tooling
ingested: 2026-11-11
type: source
---

# LLM Wiki (Karpathy)

> Raw source: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw
> Immutable source document — the wiki summarises it, it never edits it.

## Summary

This is an idea file, it is designed to be copy pasted to your own LLM Agent (e.g. OpenAI Codex, Claude Code, OpenCode / Pi, or etc.). Its goal is to communicate the high level idea, but your agent will build out the specifics in collaboration with you.

Most people's experience with LLMs and documents looks like RAG: you upload a collection of files, the LLM retrieves relevant chunks at query time, and generates an answer. This works, but the LLM is rediscovering knowledge from scratch on every question. There's no accumulation. Ask a subtle question that requires synthesizing five documents, and the LLM has to find and piece together the relevant fragments every time. Nothing is built up. NotebookLM, ChatGPT file uploads, and most RAG systems work this way.

The idea here is different. Instead of just retrieving from raw documents at query time, the LLM **incrementally builds and maint

## Key terms

`pages`, `sources`, `files`, `source`, `knowledge`, `documents`, `markdown`, `search`

## Concepts

- [[large-language-model|Large language model]]
- [[wiki|Wiki]]
- [[markdown|Markdown]]
- [[llm-agent-workflow|LLM agent workflow]]
- [[obsidian|Obsidian]]
- [[knowledge-compounding|Knowledge compounding]]

## Related sources

- [[qmd|qmd (GitHub)]]
- [[wikipedia-knowledge-graph|Knowledge graph (Wikipedia)]]
- [[wikipedia-ai-agent|AI agent (Wikipedia)]]
