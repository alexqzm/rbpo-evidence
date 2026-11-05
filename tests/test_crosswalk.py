# -*- coding: utf-8 -*-
import copy

import pytest

from rbpo_evidence.crosswalk import Crosswalk, CrosswalkError


def test_ssdf_coverage(model, root):
    cov = Crosswalk.load(str(root / "crosswalk" / "nist-ssdf-1.1.yaml"), model).coverage()
    assert cov["targets"] == 19
    assert cov["processes_not_covered"] == ["5.25"]
    assert cov["targets_unmapped"] == ["PW.9", "RV.3"]


def test_scii_gate_coverage(model, root):
    cov = Crosswalk.load(str(root / "crosswalk" / "scii-gate.yaml"), model).coverage()
    assert cov["targets"] == 17
    assert len(cov["artifacts_covered"]) == 12
    assert cov["targets_unmapped"] == ["s52", "s53", "s54"]


def test_broken_crosswalk_is_rejected(model, root):
    cw = Crosswalk.load(str(root / "crosswalk" / "nist-ssdf-1.1.yaml"), model)
    d = copy.deepcopy(cw.data)
    d["mappings"][0]["processes"].append("5.99")
    with pytest.raises(CrosswalkError, match="нет процесса"):
        Crosswalk(d, model)
