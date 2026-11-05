# -*- coding: utf-8 -*-
"""Манифест свидетельств РБПО из результатов стенда scii-gate.

Берёт состояния свидетельств одного сценария из results.json стенда scii-gate (P, N, F) и через
crosswalk/scii-gate.yaml переносит их на артефакты ГОСТ Р 56939-2024. Правило для артефакта,
на который указывают несколько свидетельств: F, если хотя бы одно F; иначе P, если хотя бы одно P;
иначе N. Артефакты, на которые не указывает ни одно свидетельство, в манифест не попадают (N).

Запуск:
  python3 tools/manifest_from_scii_gate.py <scii-gate/results/results.json> <сценарий> > manifest.yaml
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    results_path, scenario = sys.argv[1], sys.argv[2]
    res = json.load(open(results_path, encoding="utf-8"))
    sc = res["scenarios"]
    entry = next((e for e in (sc.values() if isinstance(sc, dict) else sc) if e["id"] == scenario), None)
    if entry is None:
        print(f"сценарий {scenario} не найден", file=sys.stderr)
        return 2
    cw = yaml.safe_load(open(ROOT / "crosswalk" / "scii-gate.yaml", encoding="utf-8"))

    per_artifact = {}
    for m in cw["mappings"]:
        st = entry["states"].get(m["target"], "N")
        for aid in m.get("artifacts", []) or []:
            per_artifact.setdefault(aid, []).append((m["target"], st))

    def combine(states):
        s = [x for _, x in states]
        return "F" if "F" in s else ("P" if "P" in s else "N")

    def key(aid):
        return [int(x) for x in aid.split(".")]

    out = [
        "# Манифест свидетельств РБПО, полученный из результатов стенда scii-gate.",
        "# Сгенерирован tools/manifest_from_scii_gate.py; вручную не править.",
        "",
        "schema: rbpo-evidence/manifest/v1",
        f'project: "Стенд scii-gate, сценарий {scenario}: {entry.get("title", "")}"',
        'standard: "ГОСТ Р 56939-2024"',
        "source:",
        '  data: "scii-gate results/results.json"',
        f'  scenario: "{scenario}"',
        f'  gate_decision: "{entry.get("decision", "")}"',
        f'  run_finished: "{res.get("finished", "")}"',
        '  crosswalk: "crosswalk/scii-gate.yaml"',
        '  rule: "F, если хотя бы одно свидетельство F; иначе P, если хотя бы одно P; иначе N"',
        "artifacts:",
    ]
    for aid in sorted(per_artifact, key=key):
        st = combine(per_artifact[aid])
        ev = ", ".join(f"{t}={s}" for t, s in per_artifact[aid])
        out.append(f'  "{aid}": {{state: {st}, evidence: "{ev}"}}')
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
