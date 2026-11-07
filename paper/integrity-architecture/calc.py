#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расчёты статьи «Архитектура обеспечения целостности цепочки сборки и обновления программного
обеспечения при реализации требований ГОСТ Р 56939-2024» (А.Р. Кузьмин, рукопись, 2026).

Входные данные:
  * модель ГОСТ Р 56939-2024 и сопоставление со свидетельствами стенда scii-gate из этого
    репозитория (model/gost-r-56939-2024.yaml, crosswalk/scii-gate.yaml);
  * состояния свидетельств и решения модуля допуска по 16 сценариям стенда ArduPilot (прогон
    30.10.2026) и разметка сценариев: копия двух файлов scii-gate 0.1.5 в каталоге scii-gate-0.1.5/
    (тег v0.1.5, DOI 10.5281/zenodo.24005892).

Запуск из корня репозитория:
  python3 paper/integrity-architecture/calc.py                    пересчёт и печать
  python3 paper/integrity-architecture/calc.py --check            сверка с results.json
  python3 paper/integrity-architecture/calc.py --json out.json    сохранить результат
Ключ --gate задаёт клон scii-gate (тег v0.1.5) вместо копии, ключ --evidence другой клон rbpo-evidence.

Все числа статьи, относящиеся к структуре стандарта и к сравнению проверок, берутся из вывода этой
программы. Назначенных или подобранных величин здесь нет: только подсчёт по модели стандарта,
сопоставлению и данным прогона.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GATE_COPY = os.path.join(HERE, "scii-gate-0.1.5")
STORED = os.path.join(HERE, "results.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def proc_of(clause):
    return ".".join(clause.split(".")[:2])


def key(clause):
    return [int(x) for x in clause.split(".")]


# ---------------------------------------------------------------------------------------------------
# 1. Модель стандарта: граф «требование -> учитываемый артефакт» и граф процессов
# ---------------------------------------------------------------------------------------------------
def load_model(path):
    data = yaml.safe_load(open(path, encoding="utf-8"))
    procs = {}
    for p in data["processes"]:
        procs[str(p["id"])] = {
            "title": p["title"],
            "requirements": [
                {"id": str(r["id"]), "obligation": r["obligation"],
                 "considers": [str(x) for x in (r.get("considers") or [])],
                 "if_applicable": bool(r.get("if_applicable", False))}
                for r in (p.get("requirements") or [])],
            "artifacts": [{"id": str(a["id"]), "content": a["content"]} for a in (p.get("artifacts") or [])],
        }
    return data, procs


def structure(procs):
    reqs = [r for p in procs.values() for r in p["requirements"]]
    arts = [a for p in procs.values() for a in p["artifacts"]]
    edges = [(r["id"], t) for r in reqs for t in r["considers"]]
    cross = [(r, a) for r, a in edges if proc_of(r) != proc_of(a)]
    pedges = Counter((proc_of(a), proc_of(r)) for r, a in cross)     # процесс-источник артефакта -> процесс-потребитель
    out_refs = Counter(proc_of(a) for _, a in cross)                   # на артефакты процесса ссылаются другие
    in_refs = Counter(proc_of(r) for r, _ in cross)                    # требования процесса ссылаются на чужие
    art_indeg = Counter(a for _, a in cross)
    isolated = sorted([p for p in procs if out_refs[p] == 0 and in_refs[p] == 0], key=key)

    # предки процесса в графе процессов (есть ориентированный путь к нему)
    preds = defaultdict(set)
    for (s, d) in pedges:
        preds[d].add(s)

    def ancestors(target):
        seen, stack = set(), [target]
        while stack:
            x = stack.pop()
            for y in preds[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen

    # слабосвязные компоненты графа процессов
    adj = defaultdict(set)
    for (s, d) in pedges:
        adj[s].add(d)
        adj[d].add(s)
    comps, seen = [], set()
    for p in sorted(procs, key=key):
        if p in seen:
            continue
        comp, stack = set(), [p]
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack.extend(adj[x] - comp)
        seen |= comp
        comps.append(sorted(comp, key=key))

    rel = procs["5.20"]
    rel_considers = sorted({t for r in rel["requirements"] for t in r["considers"]}, key=key)
    rel_own = [a["id"] for a in rel["artifacts"]]
    R_rel = sorted(set(rel_considers) | set(rel_own), key=key)

    hub = {"5.6", "5.7"}
    to_hub = sum(n for (s, d), n in pedges.items() if s in hub)
    return {
        "processes": len(procs),
        "requirements": len(reqs),
        "requirements_by_obligation": dict(Counter(r["obligation"] for r in reqs)),
        "if_applicable": [r["id"] for r in reqs if r["if_applicable"]],
        "artifacts": len(arts),
        "artifacts_by_content": dict(Counter(a["content"] for a in arts)),
        "considers_refs": len(edges),
        "cross_process_refs": len(cross),
        "process_links": len(pedges),
        "refs_to_5_6_and_5_7": to_hub,
        "refs_to_5_7": sum(n for (s, d), n in pedges.items() if s == "5.7"),
        "refs_to_5_6": sum(n for (s, d), n in pedges.items() if s == "5.6"),
        "most_considered_artifacts": art_indeg.most_common(6),
        "relies_on_others_top": sorted(in_refs.items(), key=lambda kv: (-kv[1], key(kv[0])))[:5],
        "isolated_processes": isolated,
        "isolated_titles": {p: procs[p]["title"] for p in isolated},
        "components": comps,
        "ancestors_of_5_20": sorted(ancestors("5.20"), key=key),
        "not_ancestors_of_5_20": sorted(set(procs) - ancestors("5.20") - {"5.20"}, key=key),
        "direct_preds_of_5_20": sorted(preds["5.20"], key=key),
        "release_requirements": {r["id"]: r["considers"] for r in rel["requirements"]},
        "release_own_artifacts": rel_own,
        "R_rel": R_rel,
        "process_edges": {f"{s}->{d}": n for (s, d), n in sorted(pedges.items(), key=lambda kv: (key(kv[0][0]), key(kv[0][1])))},
        "titles": {p: procs[p]["title"] for p in sorted(procs, key=key)},
    }


# ---------------------------------------------------------------------------------------------------
# 2. Связь графа цепочки (свидетельства гейта) с графом стандарта и политики допуска
# ---------------------------------------------------------------------------------------------------
def combine(states):
    """Правило переноса: F, если хотя бы одно свидетельство F; иначе P, если хотя бы одно P; иначе N."""
    return "F" if "F" in states else ("P" if "P" in states else "N")


def artifact_states(scenario_states, mappings):
    per = defaultdict(list)
    for m in mappings:
        for aid in (m.get("artifacts") or []):
            per[aid].append(scenario_states.get(m["target"], "N"))
    return {aid: combine(v) for aid, v in per.items()}


def completeness_rule(art_st, considered, required):
    """Политики по артефактам стандарта: опровержение -> отказ; недостающий требуемый -> запрос; иначе допуск."""
    if any(art_st.get(a, "N") == "F" for a in considered):
        return "отказ"
    if any(art_st.get(a, "N") != "P" for a in required):
        return "запрос свидетельств"
    return "допуск"


DECISIONS = ["допуск", "ручное рассмотрение", "запрос свидетельств", "отказ"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Расчёты статьи об архитектуре обеспечения целостности")
    ap.add_argument("--evidence", default=REPO, help="клон rbpo-evidence (по умолчанию этот репозиторий)")
    ap.add_argument("--gate", default=GATE_COPY, help="клон scii-gate v0.1.5 (по умолчанию копия scii-gate-0.1.5/)")
    ap.add_argument("--json", help="куда сохранить результат")
    ap.add_argument("--check", action="store_true", help="сверить пересчёт с results.json")
    ap.add_argument("--quiet", action="store_true", help="не печатать сводку")
    a = ap.parse_args(argv)

    model_path = os.path.join(a.evidence, "model", "gost-r-56939-2024.yaml")
    cw_path = os.path.join(a.evidence, "crosswalk", "scii-gate.yaml")
    res_path = os.path.join(a.gate, "results", "results.json")
    prof_path = os.path.join(a.gate, "paper", "evidence-graph-method", "profile.json")

    data, procs = load_model(model_path)
    S = structure(procs)

    cw = yaml.safe_load(open(cw_path, encoding="utf-8"))
    maps = cw["mappings"]
    A_ch = sorted({x for m in maps for x in (m.get("artifacts") or [])}, key=key)
    no_art = [m["target"] for m in maps if not m.get("artifacts")]
    ev_to_proc = {m["target"]: sorted({proc_of(x) for x in (m.get("artifacts") or [])}, key=key) for m in maps}

    res = json.load(open(res_path, encoding="utf-8"))
    items = list(res["scenarios"].values()) if isinstance(res["scenarios"], dict) else res["scenarios"]
    scen = {e["id"]: e for e in items}
    order = [e["id"] for e in items]

    prof = json.load(open(prof_path, encoding="utf-8"))
    rc = prof["real_chain"]["scenarios"]
    dangerous = {k: bool(v["dangerous"]) for k, v in rc.items()}
    assert set(dangerous) == set(order), "разметка пакета статьи и прогон расходятся"

    # состояния артефактов по сценариям
    AS = {sid: artifact_states(scen[sid]["states"], maps) for sid in order}
    ref = AS["B1"]                                    # эталонная запись стенда
    req_all = [x for x in A_ch if ref[x] == "P"]       # что эталон подтверждает
    R_rel_ch = [x for x in S["R_rel"] if x in A_ch]
    req_rel = [x for x in R_rel_ch if ref[x] == "P"]
    integrity_only = ["5.20.3.4"]

    policies = {
        "P0": {"name": "проверка целостности получателем (5.20.3.4)",
               "fn": lambda st: completeness_rule(st, integrity_only, [x for x in integrity_only if ref[x] == "P"])},
        "P1": {"name": "артефакты, на которые опирается стадия выпуска 5.20",
               "fn": lambda st: completeness_rule(st, R_rel_ch, req_rel)},
        "P2": {"name": "все артефакты стандарта, связанные с графом цепочки",
               "fn": lambda st: completeness_rule(st, A_ch, req_all)},
    }

    rows = []
    for sid in order:
        e = scen[sid]
        st = AS[sid]
        row = {
            "id": sid, "title": e["title"], "dangerous": dangerous[sid],
            "gate": e["decision"], "R": e["R"], "R_min": e["R_min"], "R_max": e["R_max"], "G": e["G"], "B": e["B"],
            "artifact_states": {x: st[x] for x in A_ch},
            "refuted_artifacts": [x for x in A_ch if st[x] == "F"],
            "missing_vs_reference": [x for x in A_ch if ref[x] == "P" and st[x] == "N"],
            "refuted_evidence": sorted([s for s, v in e["states"].items() if v == "F"]),
            "missing_evidence_vs_reference": sorted([s for s, v in e["states"].items()
                                                      if v == "N" and scen["B1"]["states"].get(s) == "P"]),
        }
        row["refuted_outside_R_rel"] = [x for x in row["refuted_artifacts"] if x not in S["R_rel"]]
        row["refuted_inside_R_rel"] = [x for x in row["refuted_artifacts"] if x in S["R_rel"]]
        row["refuted_evidence_without_artifact"] = [s for s in row["refuted_evidence"] if s in no_art]
        for k, p in policies.items():
            row[k] = p["fn"](st)
        rows.append(row)

    def tally(field):
        out = {}
        for grp, flag in (("dangerous", True), ("benign", False)):
            c = Counter(r[field] for r in rows if r["dangerous"] == flag)
            out[grp] = {d: c.get(d, 0) for d in DECISIONS}
            out[grp]["total"] = sum(c.values())
        return out

    tallies = {k: tally(k) for k in ("P0", "P1", "P2", "gate")}

    # пары «до и после реагирования» (сценарии стенда, отличающиеся по замыслу одним действием)
    def diff(a, b):
        ea, eb = scen[a]["states"], scen[b]["states"]
        return sorted([f"{s}: {ea[s]}->{eb[s]}" for s in ea if ea[s] != eb.get(s)])

    loop = []
    for a_, b_, action in (("O1", "B1", "поставщик предъявляет недостающие свидетельства сборки, хранилища и пакета"),
                           ("B3", "B1", "добавлена независимая контрольная пересборка"),
                           ("B5a", "B5b", "получатель обновил якоря доверия после плановой смены ключа")):
        loop.append({"before": a_, "after": b_, "action": action,
                     "decision_before": scen[a_]["decision"], "decision_after": scen[b_]["decision"],
                     "R_before": [scen[a_]["R_min"], scen[a_]["R_max"]], "R_after": [scen[b_]["R_min"], scen[b_]["R_max"]],
                     "evidence_changes": diff(a_, b_),
                     "artifact_changes": sorted([f"{x}: {AS[a_][x]}->{AS[b_][x]}" for x in A_ch if AS[a_][x] != AS[b_][x]], key=lambda s: key(s.split(':')[0]))})

    # сколько опасных сценариев «видит» стадия выпуска: опровержение внутри R_rel
    dang = [r for r in rows if r["dangerous"]]
    seen_by_rel = [r["id"] for r in dang if r["refuted_inside_R_rel"]]
    unseen_by_rel = [r["id"] for r in dang if not r["refuted_inside_R_rel"]]
    unseen_with_outside_refutation = [r["id"] for r in dang if not r["refuted_inside_R_rel"] and r["refuted_outside_R_rel"]]

    out = {
        "inputs": {
            "model": {"path": "rbpo-evidence/model/gost-r-56939-2024.yaml", "sha256": sha256(model_path)},
            "crosswalk": {"path": "rbpo-evidence/crosswalk/scii-gate.yaml", "sha256": sha256(cw_path)},
            "results": {"path": "scii-gate/results/results.json", "sha256": sha256(res_path),
                        "run": [res["started"], res["finished"]], "theta": res["theta"]},
            "profile": {"path": "scii-gate/paper/evidence-graph-method/profile.json", "sha256": sha256(prof_path)},
        },
        "structure": S,
        "coupling": {
            "evidence_types": len(maps),
            "evidence_with_artifact": len(maps) - len(no_art),
            "evidence_without_artifact": no_art,
            "chain_artifacts": A_ch,
            "chain_artifacts_count": len(A_ch),
            "chain_processes": sorted({proc_of(x) for x in A_ch}, key=key),
            "evidence_to_processes": ev_to_proc,
            "reference_confirms": req_all,
            "R_rel_in_chain": R_rel_ch,
            "R_rel_required_by_reference": req_rel,
            "shared_artifacts": {x: [m["target"] for m in maps if x in (m.get("artifacts") or [])] for x in A_ch},
        },
        "scenarios": rows,
        "tallies": tallies,
        "release_view": {"dangerous_total": len(dang), "refutation_visible_in_R_rel": seen_by_rel,
                         "not_visible_in_R_rel": unseen_by_rel,
                         "not_visible_but_refuted_elsewhere": unseen_with_outside_refutation},
        "response_loop": loop,
        "run_checks": {"decision_match": sum(1 for e in items if e["decision_match"]), "scenarios": len(items),
                       "state_pairs": sum(len(e["states"]) for e in items),
                       "state_mismatches": sum(len(e["state_mismatches"]) for e in items)},
    }

    # ---------- печать ----------
    p = (lambda *args, **kw: None) if a.quiet else print
    p("== Структура стандарта ==")
    for k in ("processes", "requirements", "requirements_by_obligation", "if_applicable", "artifacts",
              "artifacts_by_content", "considers_refs", "cross_process_refs", "process_links",
              "refs_to_5_6_and_5_7", "refs_to_5_7", "refs_to_5_6", "most_considered_artifacts", "relies_on_others_top"):
        p(f"{k}: {S[k]}")
    p("изолированные процессы:", ", ".join(S["isolated_processes"]))
    p("компоненты графа процессов:", [c for c in S["components"] if len(c) > 1], "+ одиночные", sum(1 for c in S["components"] if len(c) == 1))
    p("предки 5.20:", ", ".join(S["ancestors_of_5_20"]))
    p("не предки 5.20:", ", ".join(S["not_ancestors_of_5_20"]))
    p("прямые предшественники 5.20:", ", ".join(S["direct_preds_of_5_20"]))
    p("требования 5.20:", S["release_requirements"])
    p("R_rel:", ", ".join(S["R_rel"]))
    p()
    p("== Связь с графом цепочки ==")
    c = out["coupling"]
    p(f"типов свидетельств {c['evidence_types']}, с артефактом {c['evidence_with_artifact']}, без артефакта {c['evidence_without_artifact']}")
    p(f"артефактов ГОСТ, связанных с цепочкой: {c['chain_artifacts_count']} в процессах {c['chain_processes']}")
    p("общие артефакты:", {k: v for k, v in c["shared_artifacts"].items() if len(v) > 1})
    p("эталон B1 подтверждает:", c["reference_confirms"], len(c["reference_confirms"]))
    p("R_rel ∩ цепочка:", c["R_rel_in_chain"], " требуемые по эталону:", c["R_rel_required_by_reference"])
    p()
    p("== Сценарии ==")
    p(f"{'id':4} {'опасн':5} {'гейт':20} {'P0':20} {'P1':20} {'P2':20} опровергнуто(вне R_rel | внутри)")
    for r in rows:
        p(f"{r['id']:4} {str(r['dangerous']):5} {r['gate']:20} {r['P0']:20} {r['P1']:20} {r['P2']:20} "
          f"{r['refuted_outside_R_rel']} | {r['refuted_inside_R_rel']}  нет к эталону: {r['missing_vs_reference']}")
    p()
    p("== Итоги по группам ==")
    for k, t in tallies.items():
        p(k, "опасные:", t["dangerous"], " штатные:", t["benign"])
    p()
    p("опровержение видно в R_rel:", seen_by_rel, " не видно:", unseen_by_rel, " из них с опровержением вне R_rel:", unseen_with_outside_refutation)
    p()
    p("== Контур реагирования ==")
    for x in loop:
        p(x["before"], "->", x["after"], ":", x["decision_before"], "->", x["decision_after"], x["R_before"], "->", x["R_after"])
        p("   свидетельства:", x["evidence_changes"])
        p("   артефакты:", x["artifact_changes"])
    p()
    p("проверки прогона:", out["run_checks"])
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.check:
        same = json.dumps(out, ensure_ascii=False, indent=1) == open(STORED, encoding="utf-8").read()
        print("сверка с results.json:", "совпадает" if same else "РАСХОДИТСЯ")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
