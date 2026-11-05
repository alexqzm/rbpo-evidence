# -*- coding: utf-8 -*-
"""Сверка модели с текстом ГОСТ Р 56939-2024.

У кого есть экземпляр стандарта, может проверить, что модель совпадает с ним по структуре:
номера требований и артефактов, уровни обязательности, признак «если применимо», признак
обязательности содержания артефактов и все ссылки «учитываемые при выполнении требования».
Текст стандарта в репозиторий не входит: скрипт читает ваш экземпляр.

Запуск:
  pdftotext -enc UTF-8 ГОСТ_Р_56939-2024.pdf 56939.txt
  python3 tools/verify_against_standard.py 56939.txt [model/gost-r-56939-2024.yaml]

Код возврата 0 — структура совпадает, 1 — есть расхождения (они печатаются).
"""
import re
import sys

SRC = sys.argv[1]
MODEL = sys.argv[2] if len(sys.argv) > 2 else str(__import__("pathlib").Path(__file__).resolve().parent.parent / "model" / "gost-r-56939-2024.yaml")
raw = open(SRC, encoding="utf-8").read()

# 1. Нормализация: колонтитулы, номера страниц, переносы с мягким дефисом.
lines = []
for ln in raw.splitlines():
    s = ln.strip()
    if not s:
        continue
    if re.fullmatch(r"ГОСТ Р 56939\s*[—-]\s*2024", s):
        continue
    if re.fullmatch(r"[IVX]+|\d{1,2}", s):  # номера страниц
        continue
    lines.append(s)

CLAUSE = re.compile(r"^((?:5|А)\.\d+(?:\.\d+){0,3})\s+(.*)$")
NOTE = re.compile(r"^Примечани[ея]")

# 2. Нарезка на пункты: пункт тянется до начала следующего пункта.
items, cur = [], None
BARE = re.compile(r"^((?:5|А)\.\d+(?:\.\d+){0,3})$")  # номер на отдельной строке, текст — ниже
for s in lines:
    b = BARE.match(s)
    if b:
        cur = {"id": b.group(1).replace("А", "A"), "lines": []}
        items.append(cur)
        continue
    m = CLAUSE.match(s)
    if m:
        # Номер с пробелом после него в начале строки — начало нового пункта. Строки-ссылки вида
        # «5.1.3.1, 5.1.3.2.» сюда не попадают: за номером идёт запятая или точка, а не пробел.
        num, rest = m.group(1), m.group(2)
        if re.fullmatch(r"[\d., А]+", s) or rest[:1] in (",", "."):
            cur["lines"].append(s) if cur else None
            continue
        cur = {"id": num.replace("А", "A"), "lines": [rest]}
        items.append(cur)
    elif cur is not None:
        cur["lines"].append(s)


SPACED = re.compile(r"(?<![А-Яа-яЁё])(?:[А-Яа-яЁё] ){3,}[А-Яа-яЁё](?![А-Яа-яЁё])")


def join(parts):
    txt = ""
    for p in parts:
        if txt.endswith("­"):
            txt = txt[:-1] + p
        else:
            txt = (txt + " " + p) if txt else p
    txt = re.sub(r"\s+", " ", txt).strip()
    # «П р и м е ч а н и е» в выводе pdftotext набрано вразрядку — собрать слово обратно.
    return SPACED.sub(lambda m: m.group(0).replace(" ", ""), txt)


for it in items:
    it["text"] = join(it["lines"])
    del it["lines"]

# 3. Сборка процессов.
REF = re.compile(r"(?:5|А|A)\.\d+\.3\.\d+")
REF_TAIL = "Артефакты реализации требований, учитываемые при выполнении требования, представлены в"
procs = {}
order = []
for it in items:
    parts = it["id"].split(".")
    if it["id"].startswith("A"):
        continue  # приложение А — справочное, моделируется отдельно
    if len(parts) == 2:
        title = re.split(r"Примечани[ея]", it["text"])[0].strip()
        procs[it["id"]] = {"id": it["id"], "title": title, "goals": [], "reqs": [], "arts": [],
                           "notes2": []}
        order.append(it["id"])
    elif len(parts) == 3:
        if parts[2] == "2":
            # заголовок «Требования к реализации» + возможное примечание об усмотрении
            procs[".".join(parts[:2])]["notes2"].append(it["text"])
    elif len(parts) == 4:
        p = procs[".".join(parts[:2])]
        body = it["text"]
        main, _, tail = body.partition(REF_TAIL)
        main_wo_note = re.split(r"Примечани[ея]", main)[0].strip()
        tail = re.split(r"Примечани[ея]", tail)[0]
        if parts[2] == "1":
            p["goals"].append({"id": it["id"], "text": main_wo_note})
        elif parts[2] == "2":
            refs = [r.replace("А", "A") for r in REF.findall(tail)] if tail else []
            low = main_wo_note.lower()
            ob = "recommended" if "рекомендуется" in low else "mandatory"
            p["reqs"].append({"id": it["id"], "text": main_wo_note, "obligation": ob,
                              "if_applicable": "(если применимо)" in main_wo_note,
                              "considers": refs, "ref_raw": tail.strip()})
        elif parts[2] == "3":
            low = main_wo_note.lower()
            if re.search(r"\bдолж(ен|на|но|ны)\b", low):
                content = "required"
            elif re.search(r"\bмо(жет|гут)\b", low):
                content = "optional"
            else:
                content = "required"
            p["arts"].append({"id": it["id"], "text": main_wo_note, "content": content})

# 4. Усмотрение пользователя: примечания к подразделу x.2.
for p in procs.values():
    for note in p["notes2"]:
        if "по их усмотрению" not in note:
            continue
        rng = re.findall(r"(5\.\d+\.2\.\d+)\s*[—-]\s*(5\.\d+\.2\.\d+)[^.]*?по их усмотрению", note)
        if not rng:
            for r in p["reqs"]:
                r["obligation"] = "discretionary"
        else:
            # явный диапазон «по усмотрению»; всё прочее остаётся обязательным
            m = re.search(r"(5\.\d+\.2\.(\d+))\s*[—-]\s*(5\.\d+\.2\.(\d+)),\s*применяются", note)
            lo, hi = (int(m.group(2)), int(m.group(4))) if m else (None, None)
            for r in p["reqs"]:
                k = int(r["id"].split(".")[3])
                if lo is not None and lo <= k <= hi:
                    r["obligation"] = "discretionary"

out = {"processes": [procs[k] for k in order]}

import yaml  # noqa: E402

model = yaml.safe_load(open(MODEL, encoding="utf-8"))
diffs = []
mp = {p["id"]: p for p in model["processes"]}
if [p["id"] for p in model["processes"]] != [p["id"] for p in out["processes"]]:
    diffs.append("состав процессов отличается")
for p in out["processes"]:
    m = mp.get(p["id"])
    if m is None:
        continue
    if m["title"] != p["title"]:
        diffs.append(f"{p['id']}: наименование процесса отличается")
    mr = {r["id"]: r for r in m["requirements"]}
    ma = {a["id"]: a for a in m["artifacts"]}
    if list(mr) != [r["id"] for r in p["reqs"]]:
        diffs.append(f"{p['id']}: состав требований отличается")
    if list(ma) != [a["id"] for a in p["arts"]]:
        diffs.append(f"{p['id']}: состав артефактов отличается")
    for r in p["reqs"]:
        x = mr.get(r["id"])
        if not x:
            continue
        if x["obligation"] != r["obligation"]:
            diffs.append(f"{r['id']}: обязательность {x['obligation']} в модели, {r['obligation']} по тексту")
        if bool(x.get("if_applicable", False)) != r["if_applicable"]:
            diffs.append(f"{r['id']}: признак «если применимо» отличается")
        if list(x.get("considers", [])) != r["considers"]:
            diffs.append(f"{r['id']}: ссылки {x.get('considers', [])} в модели, {r['considers']} по тексту")
    for a in p["arts"]:
        x = ma.get(a["id"])
        if x and x["content"] != a["content"]:
            diffs.append(f"{a['id']}: содержание {x['content']} в модели, {a['content']} по тексту")

nreq = sum(len(p["reqs"]) for p in out["processes"])
nart = sum(len(p["arts"]) for p in out["processes"])
nedge = sum(len(r["considers"]) for p in out["processes"] for r in p["reqs"])
print(f"по тексту: процессов {len(out['processes'])}, требований {nreq}, артефактов {nart}, ссылок {nedge}")
if diffs:
    print("расхождения:")
    for d_ in diffs:
        print("  " + d_)
    sys.exit(1)
print("структура модели совпадает с текстом стандарта")
