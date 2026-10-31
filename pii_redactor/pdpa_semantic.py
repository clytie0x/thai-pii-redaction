"""Optional pinned local sentence similarity. Similarity is not legal confidence."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_FILES = {
    "1_Pooling/config.json": "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
    "config.json": "6300193cb75e01cf80c96decef7187dfb33094d97cc1490b7ead6ff134476e4e",
    "config_sentence_transformers.json": "b8c64b5cece00d8424b4896ea75b512b6008576088497609dfeb6bd63e6d36b8",
    "model.safetensors": "eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b",
    "modules.json": "8f4b264b80206c830bebbdcae377e137925650a433b689343a63bdc9b3145460",
    "sentence_bert_config.json": "70f4448f31320443fe3557cacea5abf2dcc4915dda8c80646bec9f3bb0aa5a1f",
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
    "special_tokens_map.json": "378eb3bf733eb16e65792d7e3fda5b8a4631387ca04d2015199c4d4f22ae554d",
    "tokenizer.json": "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8",
    "tokenizer_config.json": "5036ea374ffedd706e3bef33e2e0d6953cb868ef8a490e76e32ba0faa37a6b9b",
}
PROTOTYPES = {
    "IDENTITY": [
        "ชื่อ นามสกุล เลขประจำตัวและเอกสารยืนยันตัวตนของฉัน",
        "My personal name and identity document details.",
    ],
    "CONTACT": [
        "ช่องทางติดต่อส่วนตัว เบอร์โทรและอีเมลของฉัน",
        "My private contact details, telephone and email.",
    ],
    "LOCATION": [
        "ที่อยู่ที่พัก พิกัดบ้านและตำแหน่งของฉัน",
        "My residential address and personal location coordinates.",
    ],
    "FINANCIAL": [
        "รายได้ ยอดเงิน หนี้สินและบัญชีธนาคารของฉัน",
        "My income, debts, payments and bank account records.",
    ],
    "EDUCATION": [
        "ประวัติการเรียน ผลการเรียนและรหัสนักศึกษาของฉัน",
        "My education history, school results and enrolment record.",
    ],
    "EMPLOYMENT": [
        "ประวัติการทำงาน ตำแหน่งและรหัสพนักงานของฉัน",
        "My employment history, job position and employee identifier.",
    ],
    "ONLINE": [
        "บัญชีผู้ใช้ รหัสอุปกรณ์และประวัติหมายเลขไอพีของฉัน",
        "My online account, device identifier, IP address and cookie ID.",
    ],
    "ACTIVITY": [
        "ประวัติการใช้งาน การเดินทางและรายการซื้อสินค้าของฉัน",
        "My browsing activity, purchases and travel history.",
    ],
    "RELATIONSHIPS": [
        "ข้อมูลคู่สมรส ครอบครัวและผู้ติดต่อฉุกเฉินของฉัน",
        "My family relationships, spouse and emergency contact.",
    ],
    "MEDIA": [
        "ภาพถ่าย คลิปเสียงและลายมือชื่อที่ระบุตัวฉันได้",
        "My identifiable photograph, voice recording and signature.",
    ],
    "QUASI_IDENTIFIERS": [
        "อายุ อาชีพและพื้นที่อยู่อาศัยที่ใช้เชื่อมโยงระบุตัวฉัน",
        "My combined age, occupation and district allowing indirect identification.",
    ],
    "RACE": ["ฉันระบุเชื้อชาติของตนในทะเบียน", "My racial background is recorded."],
    "ETHNICITY": ["ฉันมีเชื้อสายและชาติพันธุ์ตามประวัติครอบครัว", "My ethnic ancestry is recorded."],
    "POLITICAL_OPINION": [
        "ฉันสนับสนุนแนวคิดและพรรคการเมืองนี้",
        "My political opinions and party affiliation.",
    ],
    "BELIEF": ["ฉันนับถือศาสนาและมีความเชื่อทางปรัชญานี้", "My religious and philosophical beliefs."],
    "SEXUAL_BEHAVIOR": [
        "ประวัติพฤติกรรมทางเพศและรสนิยมทางเพศของฉัน",
        "My sexual life and sexual behavior.",
    ],
    "CRIMINAL_RECORD": ["ฉันมีประวัติต้องโทษจำคุกในคดีอาญา", "My criminal conviction record."],
    "HEALTH": [
        "ฉันป่วยและกำลังรับการรักษา ผลตรวจเลือดของฉัน",
        "My medical diagnosis, symptoms and treatment.",
    ],
    "DISABILITY": [
        "ฉันมีความพิการและต้องใช้เครื่องช่วยในการดำรงชีวิต",
        "My disability and functional impairment.",
    ],
    "LABOR_UNION": ["ฉันเป็นสมาชิกสหภาพแรงงานของพนักงาน", "My trade union membership."],
    "GENETIC_DATA": [
        "ผลตรวจดีเอ็นเอ ยีนและพันธุกรรมของฉัน",
        "My DNA test, genetic variants and genome information.",
    ],
    "BIOMETRIC_IDENTITY": [
        "แม่แบบลายนิ้วมือและใบหน้าของฉันใช้ยืนยันตัวตน",
        "My biometric fingerprint and face template used for unique identification.",
    ],
}


class SemanticModel:
    def __init__(self, model_dir: str):
        path = Path(model_dir)
        if not path.is_dir() or path.name != REVISION or not (path / "model.safetensors").is_file():
            raise RuntimeError("semantic engine requires pinned local artifacts")
        try:
            if any(
                hashlib.sha256((path / name).read_bytes()).hexdigest() != digest
                for name, digest in MODEL_FILES.items()
            ):
                raise RuntimeError("semantic model identity mismatch")
        except OSError:
            raise RuntimeError("semantic model identity mismatch") from None
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                str(path),
                device="cpu",
                local_files_only=True,
                trust_remote_code=False,
                token=False,
                model_kwargs={"use_safetensors": True},
                processor_kwargs={"use_fast": True},
            )
            self.tokenizer = self.model.tokenizer
            if not self.tokenizer.is_fast or self.model.max_seq_length != 128:
                raise RuntimeError("unsupported semantic tokenizer")
            self.labels = [category for category, phrases in PROTOTYPES.items() for _ in phrases]
            self.prototype_vectors = self.model.encode(
                [phrase for phrases in PROTOTYPES.values() for phrase in phrases],
                prompt="",
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=16,
            )
        except Exception:
            raise RuntimeError("semantic engine unavailable") from None
        self.identity = {
            "model": MODEL,
            "revision": REVISION,
            "weights_sha256": hashlib.sha256((path / "model.safetensors").read_bytes()).hexdigest(),
            "prototype_sha256": hashlib.sha256(
                json.dumps(PROTOTYPES, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
            "max_tokens": 128,
            "device": "cpu",
            "scores": "cosine_similarity_not_probability",
        }

    def windows(self, text: str) -> list[tuple[int, int]]:
        encoded = self.tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            return_offsets_mapping=True,
            verbose=False,
        )
        offsets = encoded["offset_mapping"]
        budget = (
            self.model.max_seq_length - self.tokenizer.num_special_tokens_to_add(pair=False) - 4
        )
        windows = []
        index = 0
        while index < len(offsets):
            end = min(index + budget, len(offsets))
            lo, hi = offsets[index][0], offsets[end - 1][1]
            while (
                end > index + 1
                and len(
                    self.tokenizer(text[lo:hi], add_special_tokens=True, truncation=False)[
                        "input_ids"
                    ]
                )
                > self.model.max_seq_length
            ):
                end -= 1
                hi = offsets[end - 1][1]
            if (
                hi <= lo
                or len(
                    self.tokenizer(text[lo:hi], add_special_tokens=True, truncation=False)[
                        "input_ids"
                    ]
                )
                > self.model.max_seq_length
            ):
                raise RuntimeError("semantic window integrity failure")
            windows.append((lo, hi))
            if end == len(offsets):
                break
            index = max(index + 1, end - 16)
        return windows

    def topics(self, text: str, *, threshold: float) -> list[dict]:
        try:
            import numpy as np

            windows = self.windows(text)
            if not windows:
                return []
            vectors = self.model.encode(
                [text[a:b] for a, b in windows],
                prompt="",
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=16,
            )
            scores = vectors @ self.prototype_vectors.T
            if scores.shape != (len(windows), len(self.labels)) or not np.isfinite(scores).all():
                raise RuntimeError("semantic vector integrity failure")
            result = []
            for row, (start, end) in zip(scores, windows):
                maxima = {}
                for label, similarity in zip(self.labels, row):
                    maxima[label] = max(maxima.get(label, -1.0), float(similarity))
                for category, similarity in maxima.items():
                    if similarity >= threshold:
                        result.append(
                            {
                                "category": category,
                                "start": start,
                                "end": end,
                                "similarity": similarity,
                            }
                        )
            return result
        except Exception:
            raise RuntimeError("semantic inference failed") from None


@lru_cache(maxsize=1)
def semantic_model(model_dir: str | None) -> SemanticModel:
    if not model_dir:
        raise RuntimeError("semantic engine requires explicit local model directory")
    return SemanticModel(model_dir)
