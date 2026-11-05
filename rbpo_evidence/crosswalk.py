# -*- coding: utf-8 -*-
"""Сопоставления модели с внешними рамками и свидетельствами.

Файл сопоставления (crosswalk/*.yaml) перечисляет внешние элементы (практики NIST SSDF,
типы свидетельств стенда scii-gate и т. п.) и для каждого — процессы или артефакты модели.
Сопоставления — интерпретация автора модели на уровне «связано», а не эквивалентность.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import yaml

from .model import Model


class CrosswalkError(ValueError):
    """Сопоставление ссылается на то, чего нет в модели."""


@dataclass(frozen=True)
class Mapping:
    target: str
    label: str
    processes: Tuple[str, ...]
    artifacts: Tuple[str, ...]
    note: str = ""


class Crosswalk:
    def __init__(self, data: dict, model: Model):
        self.data = data
        self.target = data.get("target", {})
        self.mappings: List[Mapping] = [
            Mapping(target=str(m["target"]), label=m.get("label", ""),
                    processes=tuple(str(x) for x in m.get("processes", []) or []),
                    artifacts=tuple(str(x) for x in m.get("artifacts", []) or []),
                    note=m.get("note", ""))
            for m in data.get("mappings", [])
        ]
        self.model = model
        self.validate()

    @classmethod
    def load(cls, path: str, model: Model) -> "Crosswalk":
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f), model)

    def validate(self) -> None:
        errors = []
        seen = set()
        for m in self.mappings:
            if m.target in seen:
                errors.append(f"элемент {m.target} повторяется")
            seen.add(m.target)
            errors += [f"{m.target}: нет процесса {p}" for p in m.processes if p not in self.model.process]
            errors += [f"{m.target}: нет артефакта {a}" for a in m.artifacts if a not in self.model.artifact]
            if not m.processes and not m.artifacts and not m.note:
                errors.append(f"{m.target}: нет сопоставления и нет пояснения")
        if errors:
            raise CrosswalkError("; ".join(errors))

    def coverage(self) -> dict:
        procs = {p for m in self.mappings for p in m.processes}
        procs |= {".".join(a.split(".")[:2]) for m in self.mappings for a in m.artifacts}
        arts = {a for m in self.mappings for a in m.artifacts}
        model_procs = [p.id for p in self.model.processes]
        return {
            "targets": len(self.mappings),
            "targets_unmapped": [m.target for m in self.mappings if not m.processes and not m.artifacts],
            "processes_covered": sorted((p for p in procs if p in model_procs), key=lambda x: float(x[2:])),
            "processes_not_covered": [p for p in model_procs if p not in procs],
            "artifacts_covered": sorted(arts, key=lambda x: [int(y) for y in x.split(".")]),
        }
