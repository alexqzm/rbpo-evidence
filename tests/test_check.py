# -*- coding: utf-8 -*-
"""Проверка полноты свидетельств: статусы процессов, итог, межпроцессные последствия."""
import pytest

from rbpo_evidence.check import Manifest, ManifestError, evaluate


def manifest(model, states=None, exclude=None):
    d = {"schema": "rbpo-evidence/manifest/v1", "project": "test",
         "artifacts": {k: {"state": v} for k, v in (states or {}).items()}}
    if exclude:
        d["scope"] = {"exclude": exclude}
    return Manifest.from_dict(d, model)


def all_p(model):
    return {a.id: "P" for p in model.processes for a in p.artifacts}


def status(rep, pid):
    return next(p.status for p in rep.processes if p.id == pid)


def test_empty_manifest_lacks_evidence(model):
    rep = evaluate(model, manifest(model))
    assert rep.overall == "missing"
    assert status(rep, "5.15") == "optional"  # 5.15 применяется по усмотрению
    assert rep.artifacts_presented == 0 and rep.artifacts_total == 98


def test_all_confirmed(model):
    rep = evaluate(model, manifest(model, all_p(model)))
    assert rep.overall == "confirmed" and not rep.impacts
    assert all(p.status == "confirmed" for p in rep.processes)


def test_optional_artifacts_do_not_block(model):
    st = all_p(model)
    for aid in ("5.1.3.2", "5.13.3.5", "5.13.3.6", "5.16.3.5"):
        st.pop(aid)
    rep = evaluate(model, manifest(model, st))
    assert rep.overall == "confirmed"


def test_refuted_artifact_is_a_veto(model):
    st = all_p(model)
    st["5.17.3.5"] = "F"  # антивирусная проверка нашла вредоносный код
    rep = evaluate(model, manifest(model, st))
    assert rep.overall == "refuted" and status(rep, "5.17") == "refuted"


def test_missing_sast_report_reaches_release(model):
    st = all_p(model)
    st.pop("5.10.3.4")
    rep = evaluate(model, manifest(model, st))
    assert status(rep, "5.10") == "missing"
    assert any(i.requirement == "5.20.2.2" and i.artifact == "5.10.3.4" and i.state == "N" for i in rep.impacts)


def test_exclusion_needs_reason_and_is_respected(model):
    with pytest.raises(ManifestError, match="без обоснования"):
        manifest(model, exclude=[{"process": "5.25", "reason": ""}])
    st = all_p(model)
    for a in model.process["5.25"].artifacts:
        st.pop(a.id)
    rep = evaluate(model, manifest(model, st, exclude=[{"process": "5.25", "reason": "ПО не выводится из эксплуатации"}]))
    assert status(rep, "5.25") == "excluded" and rep.overall == "confirmed"


def test_unknown_artifact_and_state_are_rejected(model):
    with pytest.raises(ManifestError, match="неизвестный артефакт"):
        manifest(model, {"5.99.3.1": "P"})
    with pytest.raises(ManifestError, match="допустимо"):
        manifest(model, {"5.10.3.4": "X"})


def test_scii_gate_b1_example(model, root):
    rep = evaluate(model, Manifest.load(str(root / "examples" / "scii-gate-B1" / "manifest.yaml"), model))
    assert rep.overall == "missing"
    assert rep.artifacts_presented == 11
    assert status(rep, "5.15") == "optional"
