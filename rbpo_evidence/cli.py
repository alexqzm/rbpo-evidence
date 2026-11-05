# -*- coding: utf-8 -*-
"""Командная строка rbpo-evidence.

  rbpo-evidence stats                       сводка по модели
  rbpo-evidence validate                    проверка целостности модели и сопоставлений
  rbpo-evidence check MANIFEST [--json]     полнота свидетельств проекта
  rbpo-evidence graph [--mermaid] [--manifest M]   граф процессов (DOT или Mermaid)
  rbpo-evidence crosswalk FILE              покрытие сопоставления

Коды возврата check: 0 — полнота подтверждена, 10 — не хватает свидетельств,
30 — есть опровергнутые свидетельства, 2 — ошибка входных данных.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .check import Manifest, ManifestError, evaluate, render_json, render_markdown
from .crosswalk import Crosswalk, CrosswalkError
from .graph import to_dot, to_mermaid
from .model import Model, ModelError, default_model_path

EXIT = {"confirmed": 0, "missing": 10, "refuted": 30}


def _model(args) -> Model:
    return Model.load(args.model)


def cmd_stats(args) -> int:
    m = _model(args)
    s = m.stats()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    print(f"{m.standard.get('id')} (модель {m.version})")
    print(f"процессов: {s['processes']} (+ справочное приложение: {s['annex_processes']})")
    ob = s["requirements_by_obligation"]
    print(f"требований: {s['requirements']} — обязательных {ob.get('mandatory', 0)}, "
          f"рекомендуемых {ob.get('recommended', 0)}, по усмотрению {ob.get('discretionary', 0)}; "
          f"«если применимо»: {', '.join(s['requirements_if_applicable']) or 'нет'}")
    ct = s["artifacts_by_content"]
    print(f"артефактов: {s['artifacts']} — обязательных {ct.get('required', 0)}, необязательных {ct.get('optional', 0)}")
    print(f"ссылок «учитываемые при выполнении»: {s['considers_edges']}, из них между процессами "
          f"{s['cross_process_edges']} ({s['process_links']} связей процессов)")
    print("чаще всего учитываются другими процессами:")
    for aid, n in s["most_considered_artifacts"]:
        print(f"  {aid} {m.artifact[aid].label} — {n}")
    return 0


def cmd_validate(args) -> int:
    m = _model(args)
    n_req = sum(len(p.requirements) for p in m.processes)
    n_art = sum(len(p.artifacts) for p in m.processes)
    print(f"модель: ok ({len(m.processes)} процессов, {n_req} требований, {n_art} артефактов)")
    model_path = Path(args.model) if args.model else default_model_path()
    files = args.crosswalks or sorted(str(p) for p in (model_path.resolve().parent.parent / "crosswalk").glob("*.yaml"))
    for f in files:
        cw = Crosswalk.load(f, m)
        print(f"сопоставление {os.path.basename(f)}: ok ({len(cw.mappings)} элементов)")
    return 0


def cmd_check(args) -> int:
    m = _model(args)
    rep = evaluate(m, Manifest.load(args.manifest, m))
    print(render_json(rep) if args.json else render_markdown(m, rep))
    return EXIT[rep.overall]


def cmd_graph(args) -> int:
    m = _model(args)
    status = None
    if args.manifest:
        rep = evaluate(m, Manifest.load(args.manifest, m))
        status = {p.id: p.status for p in rep.processes}
    print(to_mermaid(m, status) if args.mermaid else to_dot(m, status))
    return 0


def cmd_crosswalk(args) -> int:
    m = _model(args)
    cw = Crosswalk.load(args.file, m)
    cov = cw.coverage()
    if args.json:
        print(json.dumps(cov, ensure_ascii=False, indent=2))
        return 0
    print(f"{cw.target.get('id', args.file)}: элементов {cov['targets']}")
    print(f"процессы ГОСТ, затронутые сопоставлением: {len(cov['processes_covered'])} из {len(m.processes)}")
    if cov["processes_not_covered"]:
        print("  без соответствия:", ", ".join(cov["processes_not_covered"]))
    if cov["artifacts_covered"]:
        n_art = sum(len(p.artifacts) for p in m.processes)
        print(f"артефакты ГОСТ, затронутые сопоставлением: {len(cov['artifacts_covered'])} из {n_art}")
    if cov["targets_unmapped"]:
        print("элементы без соответствия в ГОСТ:", ", ".join(cov["targets_unmapped"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rbpo-evidence", description="ГОСТ Р 56939-2024 как граф доказательств")
    ap.add_argument("--version", action="version", version=f"rbpo-evidence {__version__}")
    ap.add_argument("--model", help="путь к модели (по умолчанию model/gost-r-56939-2024.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats", help="сводка по модели")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_stats)
    v = sub.add_parser("validate", help="проверка модели и сопоставлений")
    v.add_argument("crosswalks", nargs="*")
    v.set_defaults(func=cmd_validate)
    c = sub.add_parser("check", help="полнота свидетельств проекта")
    c.add_argument("manifest")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)
    g = sub.add_parser("graph", help="граф процессов")
    g.add_argument("--mermaid", action="store_true", help="Mermaid вместо DOT")
    g.add_argument("--manifest", help="раскрасить процессы по статусу манифеста")
    g.set_defaults(func=cmd_graph)
    x = sub.add_parser("crosswalk", help="покрытие сопоставления")
    x.add_argument("file")
    x.add_argument("--json", action="store_true")
    x.set_defaults(func=cmd_crosswalk)
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ModelError, ManifestError, CrosswalkError, FileNotFoundError) as e:
        print(f"ошибка: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
