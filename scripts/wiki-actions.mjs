#!/usr/bin/env node
/* ==========================================================================
 * Drive the Obsidian clone over CDP: open files, open the graph view, report
 * what the renderer sees.
 *
 *   node scripts/wiki-actions.mjs --cdp http://127.0.0.1:9242 \
 *        open <vault-relative-path>   open a note in the workspace
 *        graph                        open Obsidian's own graph view
 *        status                       report vault/graph/plugin state
 *        links <path>                 list the outgoing links of a page
 * ========================================================================== */
import process from "node:process";

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};

const CDP = argOf("--cdp", "http://127.0.0.1:9242");
// the command is the first argument that is not a flag or a flag value
const flagValues = new Set();
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith("--")) {
    flagValues.add(args[i].slice(2));
    if (!args[i].includes("=")) flagValues.add(args[i + 1]);
  }
}
const positional = args.filter((a) => !a.startsWith("--") && !flagValues.has(a));
const command = positional[0];

const targets = await (await fetch(`${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page");
if (!page) {
  console.error(`no page target on ${CDP}`);
  process.exit(2);
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
let nextId = 0;
const pending = new Map();
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};
const send = (method, params) =>
  new Promise((resolve) => {
    const id = ++nextId;
    pending.set(id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });
const evaluate = async (expression) => {
  const reply = await send("Runtime.evaluate", {
    expression: `(async () => { ${expression} })()`,
    returnByValue: true,
    awaitPromise: true,
  });
  if (reply.result?.exceptionDetails) {
    return { __error: reply.result.exceptionDetails.text };
  }
  return reply.result?.result?.value;
};
await new Promise((resolve) => (ws.onopen = resolve));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

if (command === "open") {
  const path = positional[1];
  const out = await evaluate(`
    const path = ${JSON.stringify(path)};
    const file = app.vault.getAbstractFileByPath(path);
    if (!file) return 'missing: ' + path;
    const leaf = app.workspace.getLeaf('tab');
    await leaf.openFile(file);
    await new Promise(r => setTimeout(r, 800));
    return 'opened: ' + app.workspace.getActiveFile()?.path;
  `);
  console.log(out);
}

if (command === "graph") {
  const out = await evaluate(`
    const leaf = app.workspace.getLeaf('tab');
    await leaf.setViewState({ type: 'graph', active: true, state: { search: '' } });
    await app.workspace.setActiveLeaf(leaf, { focus: true });
    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 250));
      if (document.querySelectorAll('.graph-view .node').length > 0) break;
    }
    await new Promise(r => setTimeout(r, 1500));
    return {
      view: 'graph',
      nodes: document.querySelectorAll('.graph-view .node').length,
      labels: document.querySelectorAll('.graph-view .node-label').length,
      edges: document.querySelectorAll('.graph-view .line').length,
      title: document.title,
    };
  `);
  console.log(JSON.stringify(out));
}

if (command === "status") {
  const out = await evaluate(`
    const links = app.metadataCache.resolvedLinks;
    const inbound = {};
    for (const [src, targets] of links) {
      for (const t of targets) inbound[t] = (inbound[t] || 0) + 1;
    }
    return {
      vault: app.vault.getName(),
      files: app.vault.getMarkdownFiles().length,
      pages: app.metadataCache.getMarkdownFiles?.().length ?? app.vault.getMarkdownFiles().length,
      resolvedLinks: links.size ?? Object.keys(links).length,
      mostLinked: Object.entries(inbound).sort((a,b)=>b[1]-a[1]).slice(0,8)
    };
  `);
  console.log(JSON.stringify(out, null, 1));
}

if (command === "links") {
  const path = positional[1];
  const out = await evaluate(`
    const cache = app.metadataCache.getCache(${JSON.stringify(path)});
    if (!cache) return 'no cache';
    return { links: cache.links, headings: cache.headings, tags: cache.tags };
  `);
  console.log(JSON.stringify(out, null, 1));
}

ws.close();
