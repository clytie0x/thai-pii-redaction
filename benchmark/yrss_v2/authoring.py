"""Plan, brief and assemble the YRSS evaluation v2 test templates.

The plan gives every slot a genre, a length class, a field style and the
types it must use, so that every type reaches the size target. Authors get
the annotation guide and a brief. They never get dev templates, code or
results. Every command prints to stdout and never prints template text,
except ``assemble``, whose output is the draft itself.

``python -m benchmark.yrss_v2.authoring brief --author claude --batch 0``
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import corpus
from .types import DECOY_KINDS, LABELED_KINDS

PLAN_SEED = 20261114
AUTHORS = ("claude", "deepseek")
FAMILIES_PER_AUTHOR = 100
NEGATIVE_PER_AUTHOR = 20
BATCH_SIZE = 10
SHORT_PER_AUTHOR = 15  # at least 10% of families have at most two lines
LONG_PER_AUTHOR = 10  # at least 5% have over 600 characters of fixed text
MUST_USE = {"short": 2, "medium": 3, "long": 5}
LABELLED_SHARE = 0.4  # the rest put values in prose with no field label
GUIDE = (
    Path(__file__).resolve().parents[2] / "docs" / "research" / ("yrss-eval-v2-annotation-guide.md")
)
GENRES = (
    "ai_prompt",
    "bank_finance",
    "chat_informal",
    "ecommerce_support",
    "email",
    "gov_form",
    "hr_employment",
    "insurance",
    "legal_contract",
    "long_memo",
    "medical",
    "messy",
    "mixed_thai_english",
    "police_report",
    "school_parent",
    "travel",
    "utility_bill",
    "vehicle_transport",
)
# One placeholder stands for each type; NAME may also use name_en.
TYPE_PLACEHOLDER = {kind_type: kind for kind, kind_type in LABELED_KINDS.items()}
TYPE_PLACEHOLDER["NAME"] = "name"


@dataclass(frozen=True)
class Slot:
    slot: str
    author: str
    batch: int
    genre: str
    negative: bool
    length: str
    labelled: bool
    must_use: tuple[str, ...]


def _deal(rng: random.Random, deck: list[str], pool: tuple[str, ...], n: int) -> tuple[str, ...]:
    """Take n distinct items from a deck that refills from a shuffled pool."""
    picked: list[str] = []
    while len(picked) < n:
        if not deck:
            deck.extend(rng.sample(pool, len(pool)))
        item = deck.pop()
        if item in picked:
            deck.insert(0, item)
            continue
        picked.append(item)
    return tuple(picked)


def plan(seed: int = PLAN_SEED) -> list[Slot]:
    rng = random.Random(seed)
    types = tuple(sorted(TYPE_PLACEHOLDER.values()))
    type_deck: list[str] = []
    decoy_deck: list[str] = []
    genres = [GENRES[i % len(GENRES)] for i in range(len(AUTHORS) * FAMILIES_PER_AUTHOR)]
    rng.shuffle(genres)
    slots = []
    for a, author in enumerate(AUTHORS):
        n = FAMILIES_PER_AUTHOR
        lengths = ["short"] * SHORT_PER_AUTHOR + ["long"] * LONG_PER_AUTHOR
        lengths += ["medium"] * (n - len(lengths))
        rng.shuffle(lengths)
        negatives = set(rng.sample(range(n), NEGATIVE_PER_AUTHOR))
        for i in range(n):
            negative = i in negatives
            length = lengths[i]
            if negative:
                must = _deal(rng, decoy_deck, DECOY_KINDS, 2 if length == "short" else 3)
            else:
                must = _deal(rng, type_deck, types, MUST_USE[length])
            batch = i // BATCH_SIZE
            slots.append(
                Slot(
                    slot=f"{author[0]}{batch:02d}{i % BATCH_SIZE:02d}",
                    author=author,
                    batch=batch,
                    genre=genres[a * n + i],
                    negative=negative,
                    length=length,
                    labelled=rng.random() < LABELLED_SHARE,
                    must_use=must,
                )
            )
    return slots


def batch_slots(author: str, batch: int, seed: int = PLAN_SEED) -> list[Slot]:
    return [s for s in plan(seed) if s.author == author and s.batch == batch]


_LENGTH_TH = {
    "short": "1 ถึง 2 บรรทัด",
    "medium": "5 ถึง 15 บรรทัด",
    "long": "ยาวกว่า 600 ตัวอักษร ไม่นับ placeholder",
}

_RULES = """\
## กติกาเพิ่มเติมเรื่องความสมจริง (ใช้คู่กับคู่มือ)

8. เขียนให้เหมือนคนจริงพิมพ์ ในแนวแชตให้มีคำลงท้าย (ค่ะ ครับ นะ จ้า อ่ะ เนอะ)
   เว้นวรรคไม่สม่ำเสมอบ้าง พิมพ์ผิดบ้าง ประโยคค้างไม่จบบ้าง ตามแนวของเอกสาร
   เอกสารทางการก็ยังมีร่องรอยคนกรอก เช่น เว้นวรรคเกิน หรือช่องที่เว้นว่าง
9. คนพูดหนึ่งคนใช้คำลงท้ายเพศเดียวตลอด ห้ามปน ครับ กับ ค่ะ ในคนเดียวกัน
10. ห้ามตัดวรรณยุกต์และสระบนล่างออกทั้งเอกสาร และห้ามเอาช่องข้อมูลติดกันหมด
    โดยไม่มีช่องว่างหรือคำคั่นเลย
11. ห้ามพิมพ์ชื่อคนจริงหรือชื่อเล่นของคนลงในข้อความเอง ใช้ placeholder เสมอ
    คำเรียกอย่าง พี่ น้อง ลูกค้า คุณหมอ ใช้ได้ถ้าไม่มีชื่อตามมา
12. แต่ละ family ต้องต่างกันทั้งเรื่อง จุดประสงค์ และสำนวน
13. ช่อง "ป้ายกำกับช่อง" ในตาราง ถ้าเป็น "มี" ให้ค่าส่วนใหญ่มีป้ายช่องนำหน้า
    ถ้าเป็น "ไม่มี" ให้ค่าส่วนใหญ่อยู่ในประโยคหรือแชตโดยไม่มีป้ายช่อง
14. ต้องใช้ placeholder ทุกตัวในช่อง "ต้องใช้" อย่างน้อยหนึ่งครั้ง ใช้ตัวอื่นเพิ่มได้
    ช่องที่เขียนว่า name ใช้ {{name}} หรือ {{name_en}} ก็ได้
15. template ที่ negative เป็น true ห้ามมี placeholder ที่มี label เลย
    และห้ามมีข้อมูลส่วนบุคคลที่พิมพ์เอง แต่ควรชวนให้คิดว่ามี
"""


def brief(slots: list[Slot], guide_text: str) -> str:
    guide = "\n".join(line for line in guide_text.splitlines() if not line.startswith("Protocol:"))
    rows = [
        "| family | genre | negative | ความยาว | ป้ายกำกับช่อง | ต้องใช้ |",
        "|---|---|---|---|---|---|",
    ]
    for s in slots:
        rows.append(
            f"| {s.slot} | {s.genre} | {str(s.negative).lower()} | {_LENGTH_TH[s.length]} | "
            f"{'มี' if s.labelled else 'ไม่มี'} | {', '.join(s.must_use)} |"
        )
    return (
        "คุณคือผู้เขียน template เอกสารภาษาไทยสำหรับชุดทดสอบระบบตรวจจับข้อมูลส่วนบุคคล\n"
        "อย่าใช้เครื่องมือใดๆ อย่าอ่านไฟล์อื่น อย่าค้นเว็บ\n\n"
        "ด้านล่างคือคู่มือฉบับเต็ม (ภาษาอังกฤษ) ทำตามทุกข้อ\n\n"
        f"----- GUIDE START -----\n{guide}\n----- GUIDE END -----\n\n"
        f"{_RULES}\n"
        f"## งานรอบนี้\n\nเขียน {len(slots)} template ตามตาราง ใช้ค่า family genre negative ตามตาราง\n\n"
        + "\n".join(rows)
        + "\n\n## รูปแบบคำตอบ\n\n"
        f"ตอบเฉพาะ JSON {len(slots)} บรรทัด บรรทัดละหนึ่ง object ตามรูปแบบในคู่มือ เรียงตามตาราง\n"
        "ขึ้นบรรทัดใหม่ในเอกสารใช้ \\n ภายใน string ห้ามมี markdown ห้ามมีคำอธิบาย\n"
    )


def parse_output(raw: str) -> list[corpus.Template]:
    """Keep the JSON object lines of a model answer; ignore anything else."""
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                row = json.loads(line)
                rows.append(
                    corpus.Template(row["family"], row["genre"], bool(row["negative"]), row["text"])
                )
            except (ValueError, KeyError, TypeError):
                continue
    return rows


def check_batch(slots: list[Slot], templates: list[corpus.Template]) -> list[str]:
    """Return ``kind:slot`` errors. Messages never carry template text."""
    errors = []
    by_family = {t.family: t for t in templates}
    expected = {s.slot for s in slots}
    errors += [f"unexpected-family:{f}" for f in sorted(set(by_family) - expected)]
    for s in slots:
        t = by_family.get(s.slot)
        if t is None:
            errors.append(f"missing:{s.slot}")
            continue
        errors += [f"{kind}:{s.slot}" for kind in corpus.validate_templates([t])]
        if t.genre != s.genre:
            errors.append(f"wrong-genre:{s.slot}")
        if t.negative != s.negative:
            errors.append(f"wrong-negative:{s.slot}")
        kinds = set(corpus._kinds(t))
        if "name" in s.must_use and "name_en" in kinds:
            kinds.add("name")
        errors += [f"missing-{kind}:{s.slot}" for kind in s.must_use if kind not in kinds]
        lines = len([x for x in t.text.splitlines() if x.strip()])
        fixed = len(corpus._fixed(t))
        if s.length == "short" and lines > corpus.SHORT_LINES:
            errors.append(f"short-too-long:{s.slot}")
        if s.length == "long" and fixed <= corpus.LONG_CHARS:
            errors.append(f"long-too-short:{s.slot}")
        errors += [f"{e.split(':')[0]}:{s.slot}" for e in _realism_one(t)]
    return errors


def _realism_one(t: corpus.Template) -> list[str]:
    """The per-family realism checks, without the id and distribution checks."""
    return [
        e
        for e in corpus.validate_realism([t], dev_templates=[])
        if e.split(":")[0] in ("marks-stripped", "fields-glued", "genre-reveals-negative")
    ]


def assemble(templates: list[corpus.Template]) -> list[corpus.Template]:
    """Give every family a random opaque id and shuffle. Not reproducible on purpose."""
    rng = secrets.SystemRandom()
    ids: set[str] = set()
    out = []
    for t in templates:
        family = secrets.token_hex(6)
        while family in ids:
            family = secrets.token_hex(6)
        ids.add(family)
        out.append(corpus.Template(family, t.genre, t.negative, t.text))
    rng.shuffle(out)
    return out


def dumps(templates: list[corpus.Template]) -> str:
    return "".join(
        json.dumps(
            {"family": t.family, "genre": t.genre, "negative": t.negative, "text": t.text},
            ensure_ascii=False,
        )
        + "\n"
        for t in templates
    )


def check_draft(raw: bytes) -> dict:
    """Every check that ``seal`` runs, as counts. Never text."""
    templates = corpus._parse(raw)
    errors = corpus.validate_templates(templates)
    errors += corpus.validate_realism(templates, dev_templates=corpus.load_templates("dev"))
    built = corpus.build_corpus("test", raw)
    errors += corpus.validate_corpus(built)
    lock = corpus.public_lock(built)
    errors += corpus.check_targets(lock)
    return {
        "errors": dict(sorted(Counter(errors).items())),
        "type_counts": lock["type_counts"],
        "families": lock["families"],
        "negative_documents": lock["negative_documents"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.yrss_v2.authoring")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="print plan counts")
    for name in ("brief", "check"):
        p = sub.add_parser(name)
        p.add_argument("--author", choices=AUTHORS, required=True)
        p.add_argument("--batch", type=int, required=True)
        if name == "check":
            p.add_argument("--input", required=True, help="a model answer file")
    p = sub.add_parser("assemble", help="print the draft built from answer files")
    p.add_argument("inputs", nargs="+")
    p = sub.add_parser("check-draft")
    p.add_argument("draft")
    args = parser.parse_args(argv)

    if args.command == "plan":
        slots = plan()
        must = Counter(k for s in slots if not s.negative for k in s.must_use)
        summary = {
            "slots": len(slots),
            "negative": sum(s.negative for s in slots),
            "lengths": dict(Counter(s.length for s in slots)),
            "labelled": sum(s.labelled for s in slots),
            "genres_max": max(Counter(s.genre for s in slots).values()),
            "must_use_families": dict(sorted(must.items())),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "brief":
        sys.stdout.write(brief(batch_slots(args.author, args.batch), GUIDE.read_text("utf-8")))
        return 0
    if args.command == "check":
        raw = Path(args.input).read_text(encoding="utf-8")
        errors = check_batch(batch_slots(args.author, args.batch), parse_output(raw))
        print(json.dumps(errors))
        return 1 if errors else 0
    if args.command == "assemble":
        templates = []
        for path in args.inputs:
            templates += parse_output(Path(path).read_text(encoding="utf-8"))
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(dumps(assemble(templates)))
        return 0
    result = check_draft(Path(args.draft).read_bytes())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
