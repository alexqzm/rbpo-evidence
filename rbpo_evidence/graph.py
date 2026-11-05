# -*- coding: utf-8 -*-
"""Экспорт графа процессов: ребро A -> B, если требование процесса B учитывает артефакт процесса A.

Вес ребра — число таких ссылок. Ссылки внутри процесса в граф процессов не входят.
При заданном отчёте узлы раскрашиваются по статусу процесса.
"""
from __future__ import annotations

import textwrap
from typing import Dict, Optional

from .model import Model

_FILL = {
    "confirmed": "#d8f0d0",
    "missing": "#fbe7c6",
    "refuted": "#f6c9c9",
    "excluded": "#e6e6e6",
    "optional": "#eef1f6",
}


def _short(title: str, width: int = 28) -> str:
    return "\\n".join(textwrap.wrap(title, width)[:3])


def to_dot(model: Model, status: Optional[Dict[str, str]] = None) -> str:
    out = ["digraph rbpo {", '  rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#ffffff", fontsize=10];']
    for p in model.processes:
        fill = _FILL.get((status or {}).get(p.id, ""), "#ffffff")
        out.append(f'  "{p.id}" [label="{p.id}\\n{_short(p.title)}", fillcolor="{fill}"];')
    for (src, dst), n in sorted(model.process_edges().items(), key=lambda kv: (float(kv[0][0][2:]), float(kv[0][1][2:]))):
        out.append(f'  "{src}" -> "{dst}" [label="{n}", penwidth={1 + min(n, 6) / 2:.1f}];')
    out.append("}")
    return "\n".join(out)


def to_mermaid(model: Model, status: Optional[Dict[str, str]] = None) -> str:
    def nid(pid: str) -> str:
        return "p" + pid.replace(".", "_")

    out = ["flowchart LR"]
    for p in model.processes:
        title = p.title if len(p.title) <= 40 else p.title[:38] + "…"
        out.append(f'  {nid(p.id)}["{p.id} {title}"]')
    for (src, dst), n in sorted(model.process_edges().items(), key=lambda kv: (float(kv[0][0][2:]), float(kv[0][1][2:]))):
        out.append(f"  {nid(src)} -->|{n}| {nid(dst)}")
    if status:
        for k, fill in _FILL.items():
            out.append(f"  classDef {k} fill:{fill},stroke:#888")
        for pid, st in status.items():
            out.append(f"  class {nid(pid)} {st}")
    return "\n".join(out)
