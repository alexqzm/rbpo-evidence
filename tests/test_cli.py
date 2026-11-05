# -*- coding: utf-8 -*-
from rbpo_evidence.cli import main


def test_stats_and_validate(root, monkeypatch, capsys):
    monkeypatch.chdir(root)
    assert main(["stats"]) == 0
    assert "процессов: 25" in capsys.readouterr().out
    assert main(["validate"]) == 0


def test_check_exit_codes(root, monkeypatch, capsys):
    monkeypatch.chdir(root)
    assert main(["check", "examples/scii-gate-B1/manifest.yaml"]) == 10
    assert main(["check", "nonexistent.yaml"]) == 2


def test_graph(root, monkeypatch, capsys):
    monkeypatch.chdir(root)
    assert main(["graph", "--mermaid"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("flowchart LR") and "p5_7 -->" in out
    assert main(["graph"]) == 0
    assert capsys.readouterr().out.startswith("digraph rbpo")


def test_readme_graph_is_current(root, monkeypatch, capsys):
    """Граф в README совпадает с тем, что строит пакет по модели."""
    monkeypatch.chdir(root)
    assert main(["graph", "--mermaid"]) == 0
    graph = capsys.readouterr().out.strip()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "```mermaid\n" + graph + "\n```" in readme
