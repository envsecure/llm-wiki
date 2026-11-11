#!/usr/bin/env node
/* ==========================================================================
 * Prepare the Obsidian clone's graph view for capture:
 *   - close duplicate graph tabs
 *   - fit the graph to the view (or zoom into the dense core)
 *   - report the node/edge counts the renderer holds
 *
 *   node scripts/graph-fit.mjs --cdp <endpoint> [--mode fit|core] [--zoom 0.45]
 * ========================================================================== */
import process from "node:process";

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};
const CDP = argOf("--cdp", "http://127.0.0.1:9242");
const MODE = argOf("--mode", "fit");
const ZOOM = parseFloat(argOf("--zoom", "0.45"));

const targets = await (await fetch(`${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page");
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
  return reply.result?.result?.value ?? `ERR ${reply.result?.exceptionDetails?.text ?? ""}`;
};
await new Promise((resolve) => (ws.onopen = resolve));

const out = await evaluate(`
  const leaves = app.workspace.getLeavesOfType('graph');
  // close every graph leaf except the last (the visible one)
  for (let i = 0; i < leaves.length - 1; i++) {
    await app.workspace.getLeaf('tab').detach
      ? null : null;
    leaves[i].detach();
  }
  const active = app.workspace.getLeavesOfType('graph').slice(-1)[0];
  await app.workspace.setActiveLeaf(active, { focus: true });
  const view = active.view;
  const renderer = view.renderer;
  const w = renderer.width, h = renderer.height;

  const xs = renderer.nodes.map(n => n.x).sort((a,b)=>a-b);
  const ys = renderer.nodes.map(n => n.y).sort((a,b)=>a-b);
  const pct = (arr, p) => arr[Math.floor((arr.length - 1) * p)];

  let minX, maxX, minY, maxY, scale;
  if (${JSON.stringify(MODE)} === 'core') {
    // frame the dense core: ignore the scattered outliers
    minX = pct(xs, 0.18); maxX = pct(xs, 0.82);
    minY = pct(ys, 0.18); maxY = pct(ys, 0.82);
    scale = ${ZOOM};
  } else {
    minX = xs[0]; maxX = xs[xs.length-1];
    minY = ys[0]; maxY = ys[ys.length-1];
    scale = Math.min(w / Math.max(maxX-minX,1), h / Math.max(maxY-minY,1)) * 0.84;
  }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  renderer.scale = scale;
  renderer.targetScale = scale;
  renderer.setPan(w/2 - cx*scale, h/2 - cy*scale);
  renderer.changed();
  await new Promise(r => setTimeout(r, 1200));
  return {
    nodes: renderer.nodes.length,
    links: renderer.links.length,
    scale: Number(scale.toFixed(4)),
    canvas: { w, h },
  };
`);
console.log(JSON.stringify(out));
ws.close();
