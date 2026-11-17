"""Seal round-trip for YRSS evaluation v3. The key is created inside the test."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from benchmark import blind
from benchmark.yrss_v3 import corpus
from benchmark.yrss_v3.corpus import (
    CorpusSealError,
    enc_path,
    open_sealed,
    render_split,
    seal,
    verify_commitment,
)
from benchmark.yrss_v3.protocol import BLIND_VERSION, KEY_ENV

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sealed_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "yrss-v3"
    data_dir.mkdir()
    key = tmp_path / "key.txt"
    blind.generate_key(key)
    monkeypatch.setenv(KEY_ENV, str(key))
    monkeypatch.setattr(corpus, "DATA_DIR", data_dir)
    return data_dir, key


def test_round_trip_matches_the_keyed_render_and_hides_plaintext(sealed_env, capsys):
    data_dir, key = sealed_env
    assert corpus.main(["seal"]) == 0
    printed = capsys.readouterr().out
    documents = open_sealed(key, data_dir=data_dir)
    expected = render_split("test", fingerprint=corpus._fingerprint(blind.load_master(key)))
    assert documents == expected
    destination = enc_path(data_dir)
    lock_path = data_dir / "test.lock.json"
    blob = destination.read_bytes()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["ciphertext_sha256"] == hashlib.sha256(blob).hexdigest()
    assert (
        lock["plaintext_sha256"]
        == hashlib.sha256(
            corpus.canonical_bytes("test", documents, lock["templates_sha256"])
        ).hexdigest()
    )
    snippet = documents[0].text[:24].encode("utf-8")
    assert snippet not in blob
    assert snippet.decode("utf-8") not in lock_path.read_text(encoding="utf-8")
    assert snippet.decode("utf-8") not in printed
    assert key.read_text(encoding="ascii") not in printed
    names = {path.name for path in data_dir.iterdir()}
    assert names == {"test.lock.json"}
    assert destination.name == f"{BLIND_VERSION}.enc"
    assert not (data_dir / "test-templates.jsonl").exists()


def test_verify_does_not_decrypt_and_rejects_tampering(sealed_env, monkeypatch):
    data_dir, key = sealed_env
    seal(key, data_dir=data_dir)
    monkeypatch.delenv(KEY_ENV, raising=False)
    monkeypatch.setattr(blind, "decrypt", lambda *args: pytest.fail("decrypted"))
    lock = verify_commitment(data_dir)
    assert lock["split"] == "test"
    destination = enc_path(data_dir)
    destination.write_bytes(destination.read_bytes() + b" ")
    with pytest.raises(CorpusSealError, match="hash-mismatch"):
        verify_commitment(data_dir)


def test_wrong_key_and_missing_files_stay_generic(sealed_env, tmp_path, monkeypatch):
    data_dir, _key = sealed_env
    seal(sealed_env[1], data_dir=data_dir)
    other = tmp_path / "other.txt"
    blind.generate_key(other)
    with pytest.raises(CorpusSealError, match="open-failed") as info:
        open_sealed(other, data_dir=data_dir)
    assert other.read_text(encoding="ascii") not in str(info.value)
    enc_path(data_dir).unlink()
    with pytest.raises(CorpusSealError, match="not-sealed"):
        verify_commitment(data_dir)


def test_seal_refuses_overwrite_and_a_key_inside_a_work_tree(sealed_env, tmp_path):
    data_dir, key = sealed_env
    seal(key, data_dir=data_dir)
    with pytest.raises(CorpusSealError, match="already-exists"):
        seal(key, data_dir=data_dir)
    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True, capture_output=True)
    inside = work / "key.txt"
    blind.generate_key(inside)
    # enc_path sits next to the data dir, so this data dir needs its own parent.
    fresh_root = tmp_path / "other"
    fresh = fresh_root / "data"
    fresh.mkdir(parents=True)
    with pytest.raises(CorpusSealError, match="key-inside-repository"):
        seal(inside, data_dir=fresh)
    assert not enc_path(fresh).exists()
    assert not (fresh / "test.lock.json").exists()


def test_missing_env_and_repo_are_not_sealed(monkeypatch, capsys):
    monkeypatch.delenv(KEY_ENV, raising=False)
    assert corpus.main(["seal"]) == 1
    assert "missing-key-env" in capsys.readouterr().out
    assert corpus.main(["verify"]) == 2
    assert "not-sealed" in capsys.readouterr().out
    assert not (_ROOT / "benchmark" / "data" / "yrss-v3-test.enc").exists()
    assert not (_ROOT / "benchmark" / "data" / "yrss-v3" / "test.lock.json").exists()
    assert not (_ROOT / "benchmark" / "data" / "yrss-v3" / "test-templates.jsonl").exists()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "benchmark/data/yrss-v3/test-templates.jsonl"],
        cwd=_ROOT,
    )
    assert ignored.returncode == 0


def test_rendered_test_values_are_absent_from_tracked_files(tmp_path):
    key = tmp_path / "key.txt"
    blind.generate_key(key)
    documents = render_split("test", fingerprint=corpus._fingerprint(blind.load_master(key)))
    thai_id = next(
        documents[0].text[span.start : span.end]
        for span in documents[0].spans
        if span.entity_type == "THAI_ID"
    )
    needle = thai_id.encode("utf-8")
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    hits = []
    for name in filter(None, listed):
        path = _ROOT / name.decode()
        if path.is_file() and needle in path.read_bytes():
            hits.append(name.decode())
    assert hits == []


def test_sealed_bytes_do_not_follow_a_later_template_edit(sealed_env, monkeypatch):
    data_dir, key = sealed_env
    seal(key, data_dir=data_dir)
    opened = open_sealed(key, data_dir=data_dir)

    def _boom(split):
        raise AssertionError(f"templates-read:{split}")

    monkeypatch.setattr(corpus.families, "templates", _boom)
    assert open_sealed(key, data_dir=data_dir) == opened
