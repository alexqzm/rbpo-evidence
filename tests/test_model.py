# -*- coding: utf-8 -*-
"""Модель: сводные числа, ссылки и обязательность сверены с текстом ГОСТ Р 56939-2024."""
import copy

import pytest

from rbpo_evidence.model import Model, ModelError


def test_counts(model):
    s = model.stats()
    assert s["processes"] == 25
    assert s["requirements"] == 118
    assert s["artifacts"] == 98
    assert s["requirements_by_obligation"] == {"mandatory": 110, "recommended": 2, "discretionary": 6}
    assert s["artifacts_by_content"] == {"required": 89, "optional": 9}
    assert s["considers_edges"] == 192
    assert s["cross_process_edges"] == 79
    assert s["process_links"] == 28
    assert s["requirements_if_applicable"] == ["5.13.2.6"]


def test_process_numbering_is_contiguous(model):
    assert [p.id for p in model.processes] == [f"5.{i}" for i in range(1, 26)]


def test_release_analysis_considers_evidence_of_other_processes(model):
    # 5.20.2.2: анализ влияния неустранённых ошибок перед выпуском
    assert model.requirement["5.20.2.2"].considers == (
        "5.9.3.2", "5.20.3.1", "5.10.3.4", "5.11.3.5", "5.16.3.5", "5.18.3.2")


def test_glued_reference_numbers_are_split(model):
    # в тексте стандарта у 5.7.2.4 номера слиплись: «5.7.3.1.5.7.3.3, 5.7.3.4»
    assert model.requirement["5.7.2.4"].considers == ("5.7.3.1", "5.7.3.3", "5.7.3.4")


def test_obligation_levels(model):
    assert all(r.obligation == "discretionary" for r in model.process["5.15"].requirements)
    assert model.process["5.15"].discretionary
    assert [r.obligation for r in model.process["5.24"].requirements] == [
        "mandatory", "mandatory", "discretionary", "discretionary"]
    rec = sorted(r.id for r in model.requirement.values() if r.obligation == "recommended")
    assert rec == ["5.8.2.4", "5.9.2.3"]


def test_threat_model_and_attack_surface_are_the_hubs(model):
    top = dict(model.stats()["most_considered_artifacts"])
    assert top["5.7.3.1"] == 18 and top["5.7.3.3"] == 18


def test_annex_is_informative_and_excluded_from_counts(model):
    assert [p.id for p in model.annex] == ["A.1"] and model.annex[0].informative
    assert "A.1.3.1" in model.artifact


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["processes"][0]["requirements"][2]["considers"].append("5.99.3.1"), "несуществующий артефакт"),
    (lambda d: d["processes"][0]["artifacts"].append(
        {"id": "5.2.3.1", "label": "x", "content": "required"}), "не относится к процессу"),
    (lambda d: d["processes"][0]["requirements"].append(
        {"id": "5.1.2.1", "label": "x", "obligation": "mandatory"}), "встречается"),
    (lambda d: d["processes"][0]["requirements"][0].update(obligation="maybe"), "обязательность"),
])
def test_validation_catches_broken_models(model, mutate, message):
    d = copy.deepcopy(model.data)
    mutate(d)
    with pytest.raises(ModelError, match=message):
        Model(d)
