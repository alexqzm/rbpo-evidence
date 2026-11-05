# -*- coding: utf-8 -*-
"""Модель ГОСТ Р 56939-2024: процессы, требования, артефакты и ссылки «учитываемые при выполнении».

Модель хранится в YAML (model/gost-r-56939-2024.yaml). Этот модуль загружает её, проверяет
целостность и даёт индексы и производные величины: рёбра графа, межпроцессные ссылки, сводку.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

MODEL_FILE = "gost-r-56939-2024.yaml"
OBLIGATIONS = ("mandatory", "recommended", "discretionary")
CONTENTS = ("required", "optional")
_PROC_ID = re.compile(r"^(?:5|A)\.\d+$")
_REQ_ID = re.compile(r"^(?:5|A)\.\d+\.2\.\d+$")
_ART_ID = re.compile(r"^(?:5|A)\.\d+\.3\.\d+$")


class ModelError(ValueError):
    """Нарушение целостности модели."""


@dataclass(frozen=True)
class Requirement:
    id: str
    label: str
    obligation: str
    process: str
    considers: Tuple[str, ...] = ()
    if_applicable: bool = False


@dataclass(frozen=True)
class Artifact:
    id: str
    label: str
    content: str
    process: str


@dataclass
class Process:
    id: str
    title: str
    requirements: List[Requirement] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    informative: bool = False

    @property
    def discretionary(self) -> bool:
        """Все требования процесса применяются по усмотрению (как 5.15)."""
        return bool(self.requirements) and all(r.obligation == "discretionary" for r in self.requirements)


def process_of(clause: str) -> str:
    """Номер процесса для пункта: 5.10.3.4 -> 5.10."""
    return ".".join(clause.split(".")[:2])


def default_model_path() -> Path:
    """Путь к модели: переменная RBPO_MODEL, ./model/, каталог model/ рядом с пакетом
    (исходное дерево) или данные внутри установленного пакета (колесо)."""
    env = os.environ.get("RBPO_MODEL")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    for base in (Path.cwd(), here.parent, here / "_data"):
        p = base / "model" / MODEL_FILE
        if p.exists():
            return p
    raise FileNotFoundError(f"не найдена модель {MODEL_FILE}: укажите --model или RBPO_MODEL")


class Model:
    """Загруженная и проверенная модель стандарта."""

    def __init__(self, data: dict):
        self.data = data
        self.standard: dict = data.get("standard", {})
        self.version: str = str(data.get("model_version", ""))
        self.processes: List[Process] = []
        self.annex: List[Process] = []
        for key, target, informative in (("processes", self.processes, False), ("annex", self.annex, True)):
            for p in data.get(key, []) or []:
                proc = Process(id=str(p["id"]), title=p["title"], informative=informative or p.get("informative", False))
                for r in p.get("requirements", []) or []:
                    proc.requirements.append(Requirement(
                        id=str(r["id"]), label=r["label"], obligation=r["obligation"], process=proc.id,
                        considers=tuple(str(x) for x in r.get("considers", []) or []),
                        if_applicable=bool(r.get("if_applicable", False))))
                for a in p.get("artifacts", []) or []:
                    proc.artifacts.append(Artifact(id=str(a["id"]), label=a["label"], content=a["content"], process=proc.id))
                target.append(proc)
        self.process: Dict[str, Process] = {p.id: p for p in self.processes + self.annex}
        self.requirement: Dict[str, Requirement] = {r.id: r for p in self.process.values() for r in p.requirements}
        self.artifact: Dict[str, Artifact] = {a.id: a for p in self.process.values() for a in p.artifacts}
        self.validate()

    @classmethod
    def load(cls, path: Optional[os.PathLike] = None) -> "Model":
        p = Path(path) if path else default_model_path()
        with open(p, encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    # ---------- проверка целостности ----------
    def validate(self) -> None:
        errors: List[str] = []
        seen: Counter = Counter()
        for p in self.process.values():
            if not _PROC_ID.match(p.id):
                errors.append(f"неверный номер процесса {p.id}")
            seen[p.id] += 1
            for r in p.requirements:
                seen[r.id] += 1
                if not _REQ_ID.match(r.id) or process_of(r.id) != p.id:
                    errors.append(f"требование {r.id} не относится к процессу {p.id}")
                if r.obligation not in OBLIGATIONS:
                    errors.append(f"{r.id}: неизвестная обязательность {r.obligation}")
                if not r.label.strip():
                    errors.append(f"{r.id}: пустая формулировка")
                for t in r.considers:
                    if t not in self.artifact:
                        errors.append(f"{r.id}: ссылка на несуществующий артефакт {t}")
            for a in p.artifacts:
                seen[a.id] += 1
                if not _ART_ID.match(a.id) or process_of(a.id) != p.id:
                    errors.append(f"артефакт {a.id} не относится к процессу {p.id}")
                if a.content not in CONTENTS:
                    errors.append(f"{a.id}: неизвестный признак содержания {a.content}")
                if not a.label.strip():
                    errors.append(f"{a.id}: пустая формулировка")
        errors += [f"номер {k} встречается {n} раз" for k, n in seen.items() if n > 1]
        if errors:
            raise ModelError("; ".join(errors))

    # ---------- производные величины ----------
    def edges(self, include_annex: bool = False) -> List[Tuple[str, str]]:
        """Рёбра «требование -> учитываемый артефакт»."""
        procs = self.processes + (self.annex if include_annex else [])
        return [(r.id, t) for p in procs for r in p.requirements for t in r.considers]

    def process_edges(self) -> Dict[Tuple[str, str], int]:
        """Межпроцессные рёбра «процесс-источник артефакта -> процесс, который его учитывает» и их число."""
        out: Counter = Counter()
        for rid, aid in self.edges():
            src, dst = process_of(aid), process_of(rid)
            if src != dst:
                out[(src, dst)] += 1
        return dict(out)

    def stats(self) -> dict:
        reqs = [r for p in self.processes for r in p.requirements]
        arts = [a for p in self.processes for a in p.artifacts]
        edges = self.edges()
        cross = [e for e in edges if process_of(e[0]) != process_of(e[1])]
        indeg: Counter = Counter(aid for _, aid in cross)
        return {
            "processes": len(self.processes),
            "requirements": len(reqs),
            "requirements_by_obligation": dict(Counter(r.obligation for r in reqs)),
            "requirements_if_applicable": [r.id for r in reqs if r.if_applicable],
            "artifacts": len(arts),
            "artifacts_by_content": dict(Counter(a.content for a in arts)),
            "considers_edges": len(edges),
            "cross_process_edges": len(cross),
            "process_links": len(self.process_edges()),
            "most_considered_artifacts": indeg.most_common(5),
            "annex_processes": len(self.annex),
        }
