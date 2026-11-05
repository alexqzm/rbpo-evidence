from pathlib import Path

import pytest

from rbpo_evidence.model import Model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def model():
    return Model.load(ROOT / "model" / "gost-r-56939-2024.yaml")
