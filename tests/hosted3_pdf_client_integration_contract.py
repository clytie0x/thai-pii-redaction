"""Real Linux UDS contract between Core and the secretless PDF parser."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "pdf-parser" / "scenarios" / "hr-resume-pdf-structured-v1.pdf"
PARSER_IMAGE = os.environ.get(
    "AIGUARD_PARSER_IMAGE", "aiguard-pdf-parser-stage3:local"
)
CORE_IMAGE = os.environ.get("AIGUARD_CORE_IMAGE", "aiguard-stage3b-core:local")
RUN_IMAGES = os.environ.get("AIGUARD_STAGE3B_INTEGRATION") == "1"


def _run(arguments: list[str], *, input_bytes: bytes | None = None, check: bool = True):
    return subprocess.run(
        arguments,
        input=input_bytes,
        check=check,
        capture_output=True,
    )


@unittest.skipUnless(RUN_IMAGES, "Stage 3B image integration only")
class PDFClientIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suffix = uuid.uuid4().hex[:12]
        cls.volume = f"aiguard-stage3b-{suffix}"
        cls.parser = f"aiguard-parser-{suffix}"
        _run(["docker", "volume", "create", cls.volume])
        profile = str((ROOT / "pdf-parser" / "seccomp.json").resolve())
        _run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                cls.parser,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--security-opt",
                f"seccomp={profile}",
                "--pids-limit",
                "32",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--tmpfs",
                "/work:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700",
                "--mount",
                f"type=volume,src={cls.volume},dst=/run/aiguard-pdf",
                PARSER_IMAGE,
            ]
        )
        for _ in range(50):
            ready = _run(
                ["docker", "exec", cls.parser, "python", "/app/healthcheck.py"],
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("parser image did not become ready")

    @classmethod
    def tearDownClass(cls):
        _run(["docker", "rm", "--force", cls.parser], check=False)
        _run(["docker", "volume", "rm", cls.volume], check=False)

    def run_core(self, script: str, *, input_bytes: bytes | None = None):
        completed = _run(
            [
                "docker",
                "run",
                "--rm",
                "--interactive",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--mount",
                f"type=volume,src={self.volume},dst=/run/aiguard-pdf",
                CORE_IMAGE,
                "python",
                "-c",
                script,
            ],
            input_bytes=input_bytes,
        )
        lines = completed.stdout.decode("utf-8").splitlines()
        self.assertTrue(lines, completed.stderr.decode("utf-8", errors="replace"))
        return json.loads(lines[-1])

    def test_real_stream_recomputes_source_and_exact_segment_manifest(self):
        source = SCENARIO.read_bytes()
        result = self.run_core(
            """
import asyncio, hashlib, json, logging, sys
logging.disable(logging.CRITICAL)
from aift_hosted3.pdf_client import PDFParserClient
body = sys.stdin.buffer.read()
chunks = [body[:3], body[3:137], body[137:]]
calls = 0
async def receive():
    global calls
    value = chunks.pop(0)
    calls += 1
    return {"type":"http.request","body":value,"more_body":bool(chunks)}
async def main():
    parsed = await PDFParserClient().parse_document(
        receive, body_bytes=len(body), source_kind="standard"
    )
    output = {
        "calls": calls,
        "source_sha256": parsed.source_pdf_sha256,
        "segment_count": parsed.segment_count,
        "separator_count": parsed.extracted_text.count("\\n\\n"),
        "scenario": parsed.scenario,
    }
    parsed.clear()
    output["cleared"] = not parsed.extracted_text and not parsed.segments
    print(json.dumps(output,separators=(",",":"),sort_keys=True))
asyncio.run(main())
""",
            input_bytes=source,
        )
        self.assertEqual(result["calls"], 3)
        self.assertEqual(result["source_sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(result["segment_count"], 31)
        self.assertEqual(result["separator_count"], 30)
        self.assertIsNone(result["scenario"])
        self.assertTrue(result["cleared"])

    def test_real_document_preview_mints_source_free_bound_tickets(self):
        source = SCENARIO.read_bytes()
        result = self.run_core(
            """
import asyncio, json, logging, sys, time
logging.disable(logging.CRITICAL)
from aift_hosted3.approval import ApprovalEngine
from aift_hosted3.authority import AuthorityContext
from aift_hosted3.document_preview import DocumentPreviewService,SCENARIO_REGISTRY_SHA256
from aift_hosted3.preview import default_bindings,document_bindings
body=sys.stdin.buffer.read()
now=int(time.time())
authority=AuthorityContext(scope='public_guest',service_class='standard',session_nonce='stage3b-real',subject_id=None,expires_at_unix=now+2000)
counter={'value':0}
def random_bytes(size):
    counter['value']+=1
    return bytes([counter['value']%251])*size
engine=ApprovalEngine(b'K'*32,default_bindings(),document_bindings=document_bindings(),now=lambda:now,random_bytes=random_bytes,boot_nonce=b'B'*16)
service=DocumentPreviewService(engine,hosted_version='2.5.0',now=lambda:now,random_bytes=random_bytes)
chunks=[body[:7],body[7:]]
async def receive():
    value=chunks.pop(0)
    return {'type':'http.request','body':value,'more_body':bool(chunks)}
async def main():
    scenario=await service.preview_scenario({'scenario_id':'hr-resume-pdf-structured-v1'},authority=authority)
    scenario_ticket=engine.inspect(scenario['ticket'],authority=authority,expected_kind='synthetic_document_v1')
    uploaded=await service.preview_upload(receive,body_bytes=len(body),authority=authority)
    upload_ticket=engine.inspect(uploaded['ticket'],authority=authority,expected_kind='standard_document_v1')
    forbidden={'source_pdf_sha256','source_sha256','extracted_text','segments','mapping','authority'}
    print(json.dumps({
        'scenario_can_execute':scenario['can_execute'],
        'scenario_status':scenario['outbound_gate']['status'],
        'scenario_kind':scenario_ticket['kind'],
        'scenario_prompt':scenario_ticket['prompt_revision'],
        'scenario_registry':scenario_ticket['scenario_registry_sha256'],
        'scenario_source':scenario_ticket['source_pdf_sha256'],
        'scenario_segment_count':scenario['segment_count'],
        'scenario_raw_fields':sorted(set(scenario)&forbidden),
        'uploaded_can_execute':uploaded['can_execute'],
        'uploaded_status':uploaded['outbound_gate']['status'],
        'uploaded_kind':upload_ticket['kind'],
        'uploaded_prompt':upload_ticket['prompt_revision'],
        'uploaded_source':upload_ticket['source_pdf_sha256'],
        'uploaded_segment_count':uploaded['segment_count'],
        'uploaded_raw_fields':sorted(set(uploaded)&forbidden),
        'registry':SCENARIO_REGISTRY_SHA256,
        'review_seconds':uploaded['queue_join_before_unix']-now,
    },separators=(',',':'),sort_keys=True))
asyncio.run(main())
""",
            input_bytes=source,
        )
        source_sha = hashlib.sha256(source).hexdigest()
        self.assertTrue(result["scenario_can_execute"])
        self.assertEqual(result["scenario_status"], "no_residual_signal_detected")
        self.assertEqual(result["scenario_kind"], "synthetic_document_v1")
        self.assertEqual(
            result["scenario_prompt"],
            "structure-protected-document-classifications-v1",
        )
        self.assertEqual(result["scenario_registry"], result["registry"])
        self.assertEqual(result["scenario_source"], source_sha)
        self.assertEqual(result["scenario_segment_count"], 31)
        self.assertEqual(result["scenario_raw_fields"], [])
        self.assertTrue(result["uploaded_can_execute"])
        self.assertEqual(result["uploaded_status"], "no_residual_signal_detected")
        self.assertEqual(result["uploaded_kind"], "standard_document_v1")
        self.assertEqual(
            result["uploaded_prompt"],
            "structure-protected-document-classifications-v1",
        )
        self.assertEqual(result["uploaded_source"], source_sha)
        self.assertEqual(result["uploaded_segment_count"], 31)
        self.assertEqual(result["uploaded_raw_fields"], [])
        self.assertEqual(result["review_seconds"], 900)

    def test_busy_admission_never_calls_asgi_receive(self):
        holder = f"aiguard-holder-{uuid.uuid4().hex[:12]}"
        script = """
import json,socket,struct,time
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.connect('/run/aiguard-pdf/parser.sock')
v=json.dumps({'protocol_version':1,'operation':'parse_document','body_bytes':100,'source_kind':'standard'},separators=(',',':'),sort_keys=True).encode('ascii')
s.sendall(struct.pack('>I',len(v))+v)
n=struct.unpack('>I',s.recv(4))[0]
assert json.loads(s.recv(n)) == {'ok':True,'status':'ready'}
print('READY',flush=True)
time.sleep(5)
"""
        _run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                holder,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=volume,src={self.volume},dst=/run/aiguard-pdf",
                CORE_IMAGE,
                "python",
                "-c",
                script,
            ]
        )
        try:
            for _ in range(30):
                logs = _run(["docker", "logs", holder], check=False)
                if b"READY" in logs.stdout:
                    break
                time.sleep(0.1)
            else:
                self.fail("holder did not acquire parser admission")
            result = self.run_core(
                """
import asyncio,json
from aift_hosted3.pdf_client import PDFParserClient,PDFParserError
calls=0
async def receive():
    global calls
    calls+=1
    return {'type':'http.request','body':b'%PDF-x','more_body':False}
async def main():
    code=None
    try:
        await PDFParserClient().parse_document(receive,body_bytes=6,source_kind='standard')
    except PDFParserError as error:
        code=error.code
    print(json.dumps({'code':code,'receive_calls':calls},separators=(',',':'),sort_keys=True))
asyncio.run(main())
"""
            )
            self.assertEqual(result, {"code": "document_busy", "receive_calls": 0})
        finally:
            _run(["docker", "rm", "--force", holder], check=False)

    def test_invalid_signature_and_bounded_message_count_fail_closed(self):
        invalid = self.run_core(
            """
import asyncio,json
from aift_hosted3.pdf_client import PDFParserClient,PDFParserError
calls=0
async def receive():
    global calls
    calls+=1
    return {'type':'http.request','body':b'NOTPDF','more_body':False}
async def main():
    code=None
    try:
        await PDFParserClient().parse_document(receive,body_bytes=6,source_kind='standard')
    except PDFParserError as error:
        code=error.code
    print(json.dumps({'code':code,'receive_calls':calls},separators=(',',':'),sort_keys=True))
asyncio.run(main())
"""
        )
        self.assertEqual(
            invalid, {"code": "document_unsupported", "receive_calls": 1}
        )
        excessive = self.run_core(
            """
import asyncio,json
from aift_hosted3.pdf_client import MAX_BODY_MESSAGES,PDFParserClient,PDFParserError
calls=0
async def receive():
    global calls
    calls+=1
    return {'type':'http.request','body':b'','more_body':True}
async def main():
    code=None
    try:
        await PDFParserClient().parse_document(receive,body_bytes=1,source_kind='standard')
    except PDFParserError as error:
        code=error.code
    print(json.dumps({'code':code,'receive_calls':calls,'limit':MAX_BODY_MESSAGES},separators=(',',':'),sort_keys=True))
asyncio.run(main())
"""
        )
        self.assertEqual(excessive["code"], "document_unsupported")
        self.assertEqual(excessive["receive_calls"], excessive["limit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
