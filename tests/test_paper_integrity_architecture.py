"""Пакет расчётов статьи об архитектуре обеспечения целостности (paper/integrity-architecture).

Пересчёт по модели, сопоставлению и копии результатов scii-gate 0.1.5 должен побитово совпасть
с сохранённым results.json, а копия входных файлов scii-gate совпадать с выпуском по SHA-256.
"""
import hashlib
import importlib.util
import json

import pytest

# Файлы scii-gate 0.1.5 (тег v0.1.5, коммит d210811, DOI 10.5281/zenodo.24005892)
SCII_GATE_SHA256 = {
    "results/results.json": "91b2b28f4642e3b2c552e9a4edc38dd4fdb9a84b9c66d08e46955267986d4b08",
    "paper/evidence-graph-method/profile.json": "b597a5363803ba6d48e219e2c6eaebc56a90eff707d2e780cc7f1e15dd875690",
}


@pytest.fixture(scope="module")
def paper(root):
    return root / "paper" / "integrity-architecture"


@pytest.fixture(scope="module")
def stored(paper):
    return json.loads((paper / "results.json").read_text(encoding="utf-8"))


def load_calc(paper):
    spec = importlib.util.spec_from_file_location("integrity_architecture_calc", paper / "calc.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scii_gate_copy_matches_release(paper):
    for rel, digest in SCII_GATE_SHA256.items():
        data = (paper / "scii-gate-0.1.5" / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, rel


def test_recalculation_matches_stored(paper, tmp_path):
    out = tmp_path / "results.json"
    assert load_calc(paper).main(["--quiet", "--json", str(out)]) == 0
    assert out.read_bytes() == (paper / "results.json").read_bytes()


def test_numbers_of_the_article(stored):
    s, c, t = stored["structure"], stored["coupling"], stored["tallies"]
    assert (s["processes"], s["requirements"], s["artifacts"], s["considers_refs"]) == (25, 118, 98, 192)
    assert (s["cross_process_refs"], s["process_links"], len(s["R_rel"])) == (79, 28, 9)
    assert s["ancestors_of_5_20"] == ["5.3", "5.6", "5.7", "5.9", "5.10", "5.11", "5.16", "5.18"]
    assert {"5.12", "5.13", "5.14", "5.17", "5.21"} <= set(s["not_ancestors_of_5_20"])
    assert (c["evidence_types"], c["chain_artifacts_count"], len(c["chain_processes"])) == (17, 12, 9)
    assert len(c["reference_confirms"]) == 11

    def admitted(group):
        return [t[k][group]["допуск"] for k in ("P0", "P1", "P2", "gate")]

    # табл. 3 статьи: проверки X0, X1, X2 и правило (4)
    assert admitted("dangerous") == [7, 6, 1, 0]
    assert admitted("benign") == [4, 4, 3, 2]
    assert stored["run_checks"] == {"decision_match": 16, "scenarios": 16, "state_pairs": 272, "state_mismatches": 0}
