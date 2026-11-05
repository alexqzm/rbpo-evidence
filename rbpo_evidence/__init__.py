# -*- coding: utf-8 -*-
"""rbpo-evidence: ГОСТ Р 56939-2024 как граф доказательств — модель, проверка полноты свидетельств,
граф процессов и сопоставления с внешними рамками."""
__version__ = "0.1.0"

from .check import Manifest, evaluate  # noqa: E402,F401
from .model import Model  # noqa: E402,F401
