"""Seal and load path for the encrypted YRSS v2 test templates.

Every template here is a tiny synthetic string and every key is generated
inside the test. No real test content exists in the repository.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from benchmark import blind
from benchmark.yrss_v2 import agreement, corpus, harness

KEY_ENV = "YRSS_V2_TEST_KEY_FILE"
_ROOT = Path(__file__).resolve().parents[1]
_DRAFT = (
    json.dumps(
        {"family": "0123456789ab", "genre": "memo", "negative": False, "text": "ติดต่อ {{phone}}"},
        ensure_ascii=False,
    )
    + "\n"
    + json.dumps(
        {"family": "ba9876543210", "genre": "note", "negative": True, "text": "ไม่มีข้อมูล"},
        ensure_ascii=False,
    )
    + "\n"
)


@pytest.fixture
def sealed_env(tmp_path, monkeypatch):
    """A temp data dir, a temp key, and a draft outside it. Returns the paths."""
    data_dir = tmp_path / "yrss-v2"
    data_dir.mkdir()
    (data_dir / "dev-templates.jsonl").write_bytes(b"")
    key = tmp_path / "key.txt"
    blind.generate_key(key)
    draft = tmp_path / "draft.jsonl"
    draft.write_bytes(_DRAFT.encode("utf-8"))
    monkeypatch.setattr(corpus, "DATA_DIR", data_dir)
    monkeypatch.setenv(KEY_ENV, str(key))
    # Sandbox quirk: tmp_path can sit inside the repository.
    monkeypatch.setattr(agreement, "inside_work_tree", lambda path: False)
    # A two-template fixture cannot meet the registered size or distribution.
    monkeypatch.setattr(corpus, "check_targets", lambda lock: [])
    monkeypatch.setattr(corpus, "validate_realism", lambda templates, dev_templates: [])
    return data_dir, key, draft


def _seal(env):
    data_dir, key, draft = env
    corpus.seal(draft, key, data_dir=data_dir)
    return data_dir.parent / "yrss-v2-test.enc", data_dir / "test.lock.json"


def test_round_trip_builds_the_test_corpus_from_ciphertext(sealed_env):
    enc, lock = _seal(sealed_env)
    built = corpus.build_corpus("test")
    assert len(built.documents) == 2 * corpus.VARIANTS["test"]
    assert built.templates_sha256 == hashlib.sha256(_DRAFT.encode("utf-8")).hexdigest()
    saved = json.loads(lock.read_text(encoding="utf-8"))
    assert saved["ciphertext_sha256"] == hashlib.sha256(enc.read_bytes()).hexdigest()
    assert {k: v for k, v in saved.items() if k != "ciphertext_sha256"} == corpus.public_lock(built)
    assert [t.family for t in corpus.load_templates("test")] == ["0123456789ab", "ba9876543210"]
    assert harness._locked_corpus("test").documents == built.documents


def test_ciphertext_holds_no_plaintext_and_draft_is_untouched(sealed_env):
    enc, _ = _seal(sealed_env)
    assert "ติดต่อ".encode() not in enc.read_bytes()
    assert sealed_env[2].read_bytes() == _DRAFT.encode("utf-8")


def test_wrong_key_is_a_lock_error_without_secrets(sealed_env, tmp_path, monkeypatch):
    _seal(sealed_env)
    other = tmp_path / "other.txt"
    blind.generate_key(other)
    monkeypatch.setenv(KEY_ENV, str(other))
    with pytest.raises(harness.CorpusLockError) as info:
        harness._locked_corpus("test")
    assert "ติดต่อ" not in str(info.value)
    assert other.read_text(encoding="ascii") not in str(info.value)


def test_tampered_ciphertext_fails_the_hash_check(sealed_env):
    enc, _ = _seal(sealed_env)
    enc.write_bytes(enc.read_bytes() + b" ")
    with pytest.raises(corpus.CorpusSealError, match="hash"):
        corpus.build_corpus("test")


def test_missing_env_var_and_missing_files_are_clear_errors(sealed_env, monkeypatch):
    enc, lock = _seal(sealed_env)
    monkeypatch.delenv(KEY_ENV)
    with pytest.raises(corpus.CorpusSealError, match=KEY_ENV):
        corpus.build_corpus("test")
    with pytest.raises(harness.CorpusLockError):
        harness._locked_corpus("test")
    monkeypatch.setenv(KEY_ENV, str(sealed_env[1]))
    lock.unlink()
    with pytest.raises(corpus.CorpusSealError):
        corpus.build_corpus("test")
    enc.unlink()
    with pytest.raises(corpus.CorpusSealError):
        corpus.build_corpus("test")


def test_run_guard_fires_before_any_decryption(sealed_env, monkeypatch):
    _seal(sealed_env)
    monkeypatch.setattr(blind, "decrypt", lambda *a: pytest.fail("decrypted"))
    with pytest.raises(harness.TestSplitRefused):
        harness.run("test", ["aiguard"])


def test_lock_with_wrong_content_is_rejected(sealed_env):
    _, lock = _seal(sealed_env)
    saved = json.loads(lock.read_text(encoding="utf-8"))
    saved["entities"] += 1
    lock.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(harness.CorpusLockError, match="lock"):
        harness._locked_corpus("test")


def test_seal_refuses_to_overwrite(sealed_env):
    enc, lock = _seal(sealed_env)
    with pytest.raises(corpus.CorpusSealError, match="exists"):
        _seal(sealed_env)
    lock.unlink()
    with pytest.raises(corpus.CorpusSealError, match="exists"):
        _seal(sealed_env)
    enc.unlink()
    _seal(sealed_env)


def test_seal_refuses_a_draft_inside_a_work_tree(sealed_env, monkeypatch, tmp_path):
    data_dir, key, _draft = sealed_env
    monkeypatch.undo()
    monkeypatch.setattr(corpus, "DATA_DIR", data_dir)
    # pytest's temp dir is a work tree on some machines and not on CI.
    # The draft has to sit in a tree this test creates, on every OS.
    work = tmp_path / "draft-repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True, capture_output=True)
    draft = work / "draft.jsonl"
    draft.write_bytes(_DRAFT.encode("utf-8"))
    assert agreement.inside_work_tree(draft)
    with pytest.raises(corpus.CorpusSealError, match="repository"):
        corpus.seal(draft, key, data_dir=data_dir)
    assert not (data_dir / "test.lock.json").exists()
    assert not (data_dir.parent / "yrss-v2-test.enc").exists()


def test_inside_work_tree_sees_this_repository():
    assert agreement.inside_work_tree(_ROOT / "benchmark")


def test_seal_refuses_template_errors(sealed_env):
    data_dir, key, draft = sealed_env
    draft.write_text(
        json.dumps({"family": "0123456789ab", "genre": "m", "negative": False, "text": "ไม่มี"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(corpus.CorpusSealError, match="positive-without-labeled"):
        corpus.seal(draft, key, data_dir=data_dir)
    assert not (data_dir / "test.lock.json").exists()


def test_seal_calls_realism_with_dev_templates_and_refuses(sealed_env, monkeypatch):
    data_dir, key, draft = sealed_env
    (data_dir / "dev-templates.jsonl").write_text(
        json.dumps({"family": "d-001", "genre": "memo", "negative": True, "text": "dev"}) + "\n",
        encoding="utf-8",
    )
    seen = {}

    def fake(templates, dev_templates):
        seen["dev"] = [t.family for t in dev_templates]
        return ["near-duplicate-family:0123456789ab"]

    monkeypatch.setattr(corpus, "validate_realism", fake)
    with pytest.raises(corpus.CorpusSealError, match="near-duplicate"):
        corpus.seal(draft, key, data_dir=data_dir)
    assert seen["dev"] == ["d-001"]
    assert not (data_dir.parent / "yrss-v2-test.enc").exists()


def test_seal_calls_check_targets_with_the_lock_and_refuses(sealed_env, monkeypatch):
    data_dir, key, draft = sealed_env
    seen = {}

    def fake(lock):
        seen["lock"] = lock
        return ["documents-not-800"]

    monkeypatch.setattr(corpus, "check_targets", fake)
    with pytest.raises(corpus.CorpusSealError, match="documents-not-800"):
        corpus.seal(draft, key, data_dir=data_dir)
    assert seen["lock"]["documents"] == 8
    assert not (data_dir.parent / "yrss-v2-test.enc").exists()
    assert not (data_dir / "test.lock.json").exists()


def test_real_validators_refuse_a_tiny_draft(sealed_env, monkeypatch):
    data_dir, key, draft = sealed_env
    monkeypatch.undo()
    monkeypatch.setattr(corpus, "DATA_DIR", data_dir)
    monkeypatch.setattr(agreement, "inside_work_tree", lambda path: False)
    with pytest.raises(corpus.CorpusSealError, match="too-few-long-families"):
        corpus.seal(draft, key, data_dir=data_dir)


def test_write_lock_refuses_the_test_split(monkeypatch):
    with pytest.raises(SystemExit) as info:
        corpus.main(["--split", "test", "--write-lock"])
    assert info.value.code != 0


def test_dev_split_ignores_the_key_and_the_ciphertext(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    lock = Path(corpus.lock_path("dev"))
    before = lock.read_bytes()
    assert corpus.main(["--split", "dev"]) == 0
    assert lock.read_bytes() == before
    assert "ciphertext_sha256" not in json.loads(before)
    assert harness._locked_corpus("dev").split == "dev"


def test_blind_py_is_hashed_into_run_files():
    assert "benchmark/blind.py" in harness._HASHED_FILES


def test_no_tracked_file_has_a_line_of_exactly_64_hex_characters():
    names = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    pattern = re.compile(rb"^[0-9a-fA-F]{64}$", re.MULTILINE)
    hits = []
    for name in filter(None, names):
        path = _ROOT / name.decode()
        # A sealed blob ends with its 64-hex MAC line by design.
        if path.suffix != ".enc" and path.is_file() and pattern.search(path.read_bytes()):
            hits.append(name.decode())
    # Locks and lists of hashes sit inside JSON or tables; a bare line is a key.
    assert hits == []
