# -*- coding: utf-8 -*-
"""Проверка полноты свидетельств проекта по модели ГОСТ Р 56939-2024.

Манифест проекта задаёт состояние каждого артефакта в трёхзначной семантике, как в методе SCII:
  P — предъявлен и подтверждает выполнение;
  F — предъявлен и опровергает (например, отчёт показывает неустранённые критичные ошибки);
  N — не предъявлен (отсутствие ключа в манифесте означает N).

Статус процесса:
  refuted   — есть опровергнутый артефакт (аналог вето);
  missing   — не предъявлен хотя бы один обязательный артефакт (аналог «запроса свидетельств»);
  confirmed — все обязательные артефакты подтверждены, опровержений нет;
  excluded  — процесс исключён из области применения в манифесте (п. 4.14–4.15 стандарта);
  optional  — процесс применяется по усмотрению (5.15) и свидетельств по нему нет.

Это проверка полноты свидетельств, а не оценка соответствия: методику оценки соответствия
стандарт относит к отдельному национальному стандарту (п. 4.4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .model import Model, process_of

STATES = ("P", "N", "F")
STATUS_RU = {
    "refuted": "опровергнуто",
    "missing": "не хватает свидетельств",
    "confirmed": "подтверждено",
    "excluded": "вне области",
    "optional": "по усмотрению, не предъявлено",
}
OVERALL_RU = {
    "refuted": "есть опровергнутые свидетельства",
    "missing": "свидетельств не хватает",
    "confirmed": "полнота свидетельств подтверждена",
}


class ManifestError(ValueError):
    """Ошибка в манифесте проекта."""


@dataclass
class Manifest:
    project: str
    states: Dict[str, str]
    refs: Dict[str, dict]
    excluded: Dict[str, str]
    source: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str, model: Model) -> "Manifest":
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        return cls.from_dict(d, model)

    @classmethod
    def from_dict(cls, d: dict, model: Model) -> "Manifest":
        errors = []
        states, refs = {}, {}
        for aid, v in (d.get("artifacts") or {}).items():
            aid = str(aid)
            if aid not in model.artifact:
                errors.append(f"неизвестный артефакт {aid}")
                continue
            v = v if isinstance(v, dict) else {"state": v}
            st = str(v.get("state", "N"))
            if st not in STATES:
                errors.append(f"{aid}: состояние {st} (допустимо P, N, F)")
            states[aid] = st
            refs[aid] = {k: v[k] for k in v if k != "state"}
        excluded = {}
        for x in (d.get("scope") or {}).get("exclude", []) or []:
            pid = str(x["process"])
            if pid not in model.process:
                errors.append(f"исключён неизвестный процесс {pid}")
            if not str(x.get("reason", "")).strip():
                errors.append(f"исключение {pid} без обоснования")
            excluded[pid] = str(x.get("reason", ""))
        if errors:
            raise ManifestError("; ".join(errors))
        return cls(project=str(d.get("project", "")), states=states, refs=refs, excluded=excluded,
                   source=d.get("source") or {})

    def state(self, aid: str) -> str:
        return self.states.get(aid, "N")


@dataclass
class ProcessResult:
    id: str
    title: str
    status: str
    confirmed: List[str]
    missing: List[str]
    refuted: List[str]
    optional_missing: List[str]


@dataclass
class Impact:
    requirement: str
    process: str
    artifact: str
    state: str


@dataclass
class Report:
    project: str
    overall: str
    processes: List[ProcessResult]
    impacts: List[Impact]
    counts: Dict[str, int]
    artifacts_presented: int
    artifacts_total: int
    source: dict

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "overall": self.overall,
            "counts": self.counts,
            "artifacts_presented": self.artifacts_presented,
            "artifacts_total": self.artifacts_total,
            "processes": [p.__dict__ for p in self.processes],
            "cross_process_impacts": [i.__dict__ for i in self.impacts],
            "source": self.source,
        }


def evaluate(model: Model, manifest: Manifest) -> Report:
    results: List[ProcessResult] = []
    for p in model.processes:
        conf = [a.id for a in p.artifacts if manifest.state(a.id) == "P"]
        refuted = [a.id for a in p.artifacts if manifest.state(a.id) == "F"]
        required = [a for a in p.artifacts if a.content == "required" and not p.discretionary]
        missing = [a.id for a in required if manifest.state(a.id) == "N"]
        opt_missing = [a.id for a in p.artifacts if a not in required and manifest.state(a.id) == "N"]
        if p.id in manifest.excluded:
            status = "excluded"
        elif refuted:
            status = "refuted"
        elif missing:
            status = "missing"
        elif p.discretionary and not conf:
            status = "optional"
        else:
            status = "confirmed"
        results.append(ProcessResult(p.id, p.title, status, conf, missing, refuted, opt_missing))

    # Межпроцессные последствия: требование учитывает артефакт другого процесса, который не подтверждён.
    in_scope = {r.id for r in results if r.status != "excluded"}
    impacts: List[Impact] = []
    for rid, aid in model.edges():
        rp, ap = process_of(rid), process_of(aid)
        if rp == ap or rp not in in_scope or ap in manifest.excluded:
            continue
        st = manifest.state(aid)
        if st != "P":
            impacts.append(Impact(requirement=rid, process=rp, artifact=aid, state=st))

    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    if counts.get("refuted"):
        overall = "refuted"
    elif counts.get("missing"):
        overall = "missing"
    else:
        overall = "confirmed"
    total = sum(len(p.artifacts) for p in model.processes)
    presented = sum(1 for a in model.artifact.values() if not a.id.startswith("A.") and manifest.state(a.id) != "N")
    return Report(manifest.project, overall, results, impacts, counts, presented, total, manifest.source)


def render_markdown(model: Model, report: Report) -> str:
    L: List[str] = []
    w = L.append
    w(f"# Полнота свидетельств РБПО: {report.project}")
    w("")
    w(f"Модель: {model.standard.get('id', '')}, версия модели {model.version}. "
      "Это проверка полноты свидетельств, а не оценка соответствия стандарту (п. 4.4).")
    w("")
    w(f"**Итог:** {OVERALL_RU[report.overall]}. Предъявлено артефактов: {report.artifacts_presented} "
      f"из {report.artifacts_total}.")
    w("")
    order = ["confirmed", "missing", "refuted", "optional", "excluded"]
    w("| Статус процесса | Процессов |")
    w("|---|---:|")
    for k in order:
        if report.counts.get(k):
            w(f"| {STATUS_RU[k]} | {report.counts[k]} |")
    w("")
    w("## Процессы")
    w("")
    w("| Процесс | Статус | Подтверждено | Нет обязательных | Опровергнуто |")
    w("|---|---|---|---|---|")
    for r in report.processes:
        title = r.title if len(r.title) <= 60 else r.title[:57] + "…"
        w(f"| {r.id} {title} | {STATUS_RU[r.status]} | {', '.join(r.confirmed) or '—'} | "
          f"{', '.join(r.missing) or '—'} | {', '.join(r.refuted) or '—'} |")
    w("")
    if report.impacts:
        w("## Межпроцессные последствия")
        w("")
        w("Требование учитывает артефакт другого процесса, который не подтверждён (N — не предъявлен, "
          "F — опровергнут).")
        w("")
        w("| Требование | Учитывает | Состояние |")
        w("|---|---|---|")
        for i in report.impacts:
            req = model.requirement[i.requirement]
            art = model.artifact[i.artifact]
            w(f"| {i.requirement} {req.label} | {i.artifact} {art.label} | {i.state} |")
        w("")
    if report.source:
        w("## Происхождение манифеста")
        w("")
        for k, v in report.source.items():
            w(f"- {k}: {v}")
        w("")
    return "\n".join(L)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def check_file(model: Model, manifest_path: str, fmt: str = "md") -> str:
    rep = evaluate(model, Manifest.load(manifest_path, model))
    return render_json(rep) if fmt == "json" else render_markdown(model, rep)
