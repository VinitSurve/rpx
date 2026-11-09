"""Mermaid diagram generator and exporter for dependency and workspace graphs."""

from __future__ import annotations

import re
from pathlib import Path

from rpx.exceptions import ExportError
from rpx.models import DependencyGraph, ScanResult


def _safe_id(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "m_" + cleaned
    return cleaned


def generate_mermaid_graph(graph: DependencyGraph, max_edges: int = 80) -> str:
    """Generate a Mermaid flowchart string from a DependencyGraph."""
    lines = ["flowchart LR"]

    # Group modules by architectural layer as subgraphs
    for layer, mod_names in sorted(graph.inferred_layers.items()):
        safe_layer = _safe_id(f"layer_{layer}")
        lines.append(f'    subgraph {safe_layer}["Layer: {layer}"]')
        for m in mod_names[:40]:
            nid = _safe_id(m)
            lines.append(f'        {nid}["{m}"]')
        lines.append("    end")

    # Add directed edges
    cycle_edges: set[tuple[str, str]] = set()
    for cyc in graph.cycles:
        for i in range(len(cyc) - 1):
            cycle_edges.add((cyc[i], cyc[i + 1]))

    for src, dst in graph.edges[:max_edges]:
        sid = _safe_id(src)
        did = _safe_id(dst)
        if (src, dst) in cycle_edges:
            lines.append(f'    {sid} -. "cycle" .-> {did}')
        else:
            lines.append(f"    {sid} --> {did}")

    if not graph.edges and not graph.modules:
        lines.append('    empty["No internal module dependencies detected"]')

    return "\n".join(lines) + "\n"


def export_mermaid_report(result: ScanResult, output_path: Path) -> Path:
    """Write a Mermaid diagram file (.mmd or .md) from ScanResult."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mmd = generate_mermaid_graph(result.graph)
        if output_path.suffix.lower() == ".md":
            content = (
                f"# {result.metadata.name} — Module Dependency Graph\n\n```mermaid\n{mmd}```\n"
            )
        else:
            content = mmd
        output_path.write_text(content, encoding="utf-8")
        return output_path.resolve()
    except OSError as e:
        raise ExportError(f"Failed to export Mermaid diagram to {output_path}: {e}") from e
