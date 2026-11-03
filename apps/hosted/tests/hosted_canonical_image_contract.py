#!/usr/bin/env python3
"""Run inside the exact offline image; print no content or mapping."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace


def main() -> int:
    assert os.environ.get("PYTHAINLP_OFFLINE") == "1"
    for verifier in ("verify_core_install.py", "verify_thainer_assets.py"):
        subprocess.run([sys.executable, f"/app/{verifier}"], check=True)

    from aift_hosted3.execution import _generated_pii_spans, _mask_spans
    from aift_hosted3.protection import ProtectionService

    from pii_redactor.stateless import restore_stateless

    source = "ผู้สมัครสังเคราะห์ สมชาย ใจดี ติดต่อ test@example.invalid"
    protected = ProtectionService().protect(
        source, mode="token", salt="hosted-image-smoke", generation_seed=b"S" * 32
    )
    try:
        assert protected.mapping and protected.protected_text != source
        exact = restore_stateless(
            "**คำตอบ:**\n\n" + protected.protected_text,
            mapping=protected.mapping,
            mode="token",
        )
        assert exact.restored_text == "**คำตอบ:**\n\n" + source
        assert exact.generated_pii_count == 0 and not exact.leftover_pseudonyms
        generated = restore_stateless(
            "ผู้ติดต่อใหม่ นายสมหญิง ทดสอบดี\n" + protected.protected_text,
            mapping=protected.mapping,
            mode="token",
        )
        assert generated.generated_pii_count > 0
        assert generated.generated_pii_spans_complete is True
        spans = _generated_pii_spans(generated, len(generated.restored_text))
        assert spans
        masked = _mask_spans(generated.restored_text, spans)
        assert "สมหญิง" not in masked and "สมชาย ใจดี" in masked
        unknown = replace(generated, generated_pii_spans_complete=False)
        assert not _generated_pii_spans(unknown, len(unknown.restored_text))
        partial = replace(
            generated,
            generated_pii_spans=((0, 2), (3, len(generated.restored_text) + 1)),
            generated_pii_spans_complete=True,
        )
        assert not _generated_pii_spans(partial, len(partial.restored_text))
    finally:
        protected.mapping.clear()
    print("Hosted canonical installed adapter, offline assets and complete-offset gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
