#!/usr/bin/env python3
"""Render the wiki's connection graph to a PNG.

Reads the graph.json produced by build_wiki.py and draws it with a
force-directed layout. The palette is monochrome so the figure matches the
Obsidian clone's own theme.

Usage: render_graph.py <vault-dir> [--out graph.png] [--dpi 200]
"""

import argparse
import json
import math
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.lines import Line2D

BG = "#ffffff"
INK = "#111111"
GREY = "#8a8a8a"
LIGHT = "#dcdcdc"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault")
    parser.add_argument("--out", default="graph.png")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--title", default="LLM wiki — how the sources connect")
    args = parser.parse_args()

    with open(os.path.join(args.vault, "graph.json"), encoding="utf-8") as handle:
        data = json.load(handle)

    graph = nx.Graph()
    for node in data["graph"]["nodes"]:
        graph.add_node(node["id"], **node)
    for edge in data["graph"]["edges"]:
        graph.add_edge(edge["source"], edge["target"], kind=edge["kind"])

    concepts = {n for n in graph.nodes if graph.nodes[n]["kind"] == "concept"}
    sources = set(graph.nodes) - concepts

    # Barycentric "concept map" layout: concepts sit on a circle, each source
    # is placed at the weighted centre of the concepts it mentions. This reads
    # far better than a force layout for a source->concept graph.
    mention_of = defaultdict(list)
    for u, v in graph.edges:
        if graph[u][v]["kind"] == "mentions":
            if u in concepts:
                mention_of[v].append(u)
            else:
                mention_of[u].append(v)

    concept_order = sorted(
        concepts,
        key=lambda c: (-len(mention_of.get(c, [])), graph.nodes[c]["title"].lower()),
    )
    layout = {}
    radius = 1.08
    for index, concept in enumerate(concept_order):
        angle = 2 * math.pi * index / max(len(concept_order), 1)
        # tiny angular jitter keeps neighbouring long labels from colliding
        angle += ((index % 3) - 1) * 0.035
        layout[concept] = np.array([radius * math.cos(angle), radius * math.sin(angle)])

    rng = np.random.default_rng(7)
    for source in sorted(sources):
        linked = mention_of.get(source, [])
        if linked:
            weights = [graph.degree(c) for c in linked]
            total = sum(weights) or 1
            position = sum(layout[c] * w for c, w in zip(linked, weights)) / total
            # push outward slightly so sources do not pile onto their concepts
            direction = position / (np.linalg.norm(position) or 1)
            position = position * 0.80 + direction * 0.32
        else:
            position = rng.normal(0, 0.05, 2)
        layout[source] = position + rng.normal(0, 0.035, 2)

    figure, axes = plt.subplots(figsize=(19, 13), facecolor=BG)
    axes.set_facecolor(BG)

    mention_edges = [(u, v) for u, v in graph.edges if graph[u][v]["kind"] == "mentions"]
    related_edges = [(u, v) for u, v in graph.edges if graph[u][v]["kind"] == "related"]

    nx.draw_networkx_edges(graph, layout, edgelist=related_edges, ax=axes,
                           edge_color=LIGHT, width=0.9, alpha=0.9)
    nx.draw_networkx_edges(graph, layout, edgelist=mention_edges, ax=axes,
                           edge_color="#b9b9b9", width=1.4, alpha=0.95,
                           arrows=False)

    concept_sizes = []
    source_sizes = []
    for node in graph.nodes:
        degree = graph.degree(node)
        if node in concepts:
            concept_sizes.append(90 + degree * 105)
        else:
            source_sizes.append(26 + degree * 20)

    nx.draw_networkx_nodes(graph, layout, nodelist=sorted(concepts), ax=axes,
                           node_color=INK, node_size=concept_sizes, alpha=0.92,
                           node_shape="o", linewidths=0)
    nx.draw_networkx_nodes(graph, layout, nodelist=sorted(sources), ax=axes,
                           node_color=BG, edgecolors=INK, node_size=source_sizes,
                           node_shape="s", linewidths=1.2)

    labels = {node: graph.nodes[node]["title"] for node in graph.nodes}
    concept_labels = {node: labels[node] for node in concepts}
    source_labels = {node: labels[node] for node in sources
                     if graph.degree(node) >= 3}

    # concept labels are pushed radially outwards so they never sit on the
    # sources clustered in the middle
    for node, text in concept_labels.items():
        position = layout[node]
        norm = np.linalg.norm(position) or 1.0
        direction = position / norm
        axes.annotate(
            text, xy=position, xytext=position + direction * 0.135,
            fontsize=10.5, fontweight="bold", color=INK,
            ha="center", va="center", zorder=5,
            bbox=dict(facecolor=BG, edgecolor="none", alpha=0.88, pad=0.8),
        )
    nx.draw_networkx_labels(graph, layout, labels=source_labels, ax=axes,
                            font_size=6.6, font_color=GREY)

    axes.set_title(args.title, fontsize=17, fontweight="bold", color=INK, pad=22)
    axes.text(
        0.5, 1.012,
        f"{len(sources)} sources  ·  {len(concepts)} concepts  ·  "
        f"{len(mention_edges)} source↔concept links  ·  {len(related_edges)} related links",
        transform=axes.transAxes, ha="center", va="bottom", fontsize=10.5, color=GREY,
    )
    axes.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=INK,
                   markersize=11, label="concept page"),
            Line2D([0], [0], marker="s", color="none", markerfacecolor=BG,
                   markeredgecolor=INK, markersize=9, label="source page"),
            Line2D([0], [0], color="#b9b9b9", lw=1.6, label="source mentions concept"),
            Line2D([0], [0], color=LIGHT, lw=1.1, label="related"),
        ],
        loc="lower left", frameon=False, fontsize=10, ncol=2,
    )
    axes.axis("off")
    axes.margins(0.06)
    figure.tight_layout()

    out_path = os.path.abspath(args.out)
    figure.savefig(out_path, dpi=args.dpi, facecolor=BG)
    print(f"wrote {out_path}")
    print(f"  nodes: {len(graph.nodes)}  edges: {graph.number_of_edges()}")
    top = sorted(graph.degree, key=lambda kv: -kv[1])[:6]
    print("  hubs: " + ", ".join(f"{labels[n]} ({d})" for n, d in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
