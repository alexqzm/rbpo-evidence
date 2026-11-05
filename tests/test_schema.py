# -*- coding: utf-8 -*-
"""Данные репозитория соответствуют JSON Schema."""
import json

import pytest
import yaml

jsonschema = pytest.importorskip("jsonschema")


@pytest.mark.parametrize("schema, data", [
    ("schema/model.schema.json", "model/gost-r-56939-2024.yaml"),
    ("schema/manifest.schema.json", "examples/scii-gate-B1/manifest.yaml"),
    ("schema/crosswalk.schema.json", "crosswalk/nist-ssdf-1.1.yaml"),
    ("schema/crosswalk.schema.json", "crosswalk/scii-gate.yaml"),
])
def test_valid(root, schema, data):
    jsonschema.validate(yaml.safe_load(open(root / data, encoding="utf-8")),
                        json.load(open(root / schema, encoding="utf-8")))
