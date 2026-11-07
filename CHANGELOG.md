# Изменения

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии — [SemVer](https://semver.org/lang/ru/). До 1.0 формат модели и манифеста может меняться.

## [Unreleased]

### Изменено
- README и CITATION.cff: DOI выпуска 0.1.0 в Zenodo (10.5281/zenodo.24045219).

## [0.1.0] - 2026-11-08

Первый выпуск.

### Добавлено
- Модель ГОСТ Р 56939-2024 (`model/gost-r-56939-2024.yaml`): 25 процессов, 118 требований
  с уровнем обязательности, 98 артефактов, 192 ссылки «учитываемые при выполнении требования»;
  справочное приложение А отдельно.
- Проверка полноты свидетельств по манифесту проекта (P, N, F), граф процессов (DOT, Mermaid),
  командная строка `rbpo-evidence`.
- Сопоставления: NIST SP 800-218 (SSDF) 1.1; типы свидетельств стенда scii-gate.
- Пример: манифест и отчёт для стенда scii-gate, сценарий B1.
- JSON Schema модели, манифеста и сопоставлений; сверка модели с текстом стандарта
  (`tools/verify_against_standard.py`).
- Модель, сопоставления и схемы входят в колесо (`rbpo_evidence/_data/`): установка
  `pip install git+https://github.com/alexqzm/rbpo-evidence` работает без исходного дерева,
  пакет можно использовать как зависимость (сборка — hatchling).
- Пакет расчётов статьи об архитектуре обеспечения целостности (`paper/integrity-architecture/`):
  все числа текста и таблица 3 по модели, сопоставлению scii-gate и копии результатов стенда
  scii-gate 0.1.5; тест сверяет пересчёт с сохранённым `results.json` побитово.

[Unreleased]: https://github.com/alexqzm/rbpo-evidence/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/alexqzm/rbpo-evidence/releases/tag/v0.1.0
