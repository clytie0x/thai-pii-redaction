"""Stage 3 secretless parser and text-layer document contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "pdf-parser"
SCENARIO = PARSER / "scenarios" / "hr-resume-pdf-structured-v1.pdf"
SCENARIO_SHA256 = "57ffcd9cddfe5abbe3b5b276ad93d22a549d386f01967344315a97cbafc51e6c"

sys.path.insert(0, str(PARSER))
from protocol import (  # noqa: E402
    MAX_HEADER_BYTES,
    MAX_PDF_BYTES,
    MAX_RESPONSE_BYTES,
    ProtocolError,
    decode_json,
    encode_json,
    request_header,
    validated_result,
)


class SourceContractTests(unittest.TestCase):
    def test_dependency_lock_and_license_record_are_exact(self):
        requirement_input = (PARSER / "requirements.in").read_text(encoding="utf-8")
        requirements = [
            line
            for line in requirement_input.splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(
            requirements,
            ["pikepdf==10.10.0", "pdfplumber==0.11.10", "pypdfium2==5.12.1"],
        )
        lock = (PARSER / "requirements.lock").read_text(encoding="utf-8")
        for package in ("pikepdf==10.10.0", "pdfplumber==0.11.10", "pypdfium2==5.12.1"):
            self.assertIn(package, lock)
        self.assertNotIn("reportlab==", lock)
        notice = (PARSER / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        for fact in ("10.10.0", "12.3.2", "0.11.10", "5.12.1", "OFL-1.1"):
            self.assertIn(fact, notice)
        self.assertTrue((PARSER / "licenses" / "OFL-Anuphan.txt").is_file())

    def test_image_and_compose_boundary_source_is_secretless(self):
        dockerfile = (PARSER / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("--require-hashes", dockerfile)
        self.assertIn('assert pikepdf.__libqpdf_version__ == "12.3.2"', dockerfile)
        self.assertIn("USER appuser", dockerfile)
        self.assertNotRegex(
            dockerfile,
            re.compile(r"AIGUARD_API_KEY|AIFT_ACCESS_CODE|TOKENMIND|COOKIE_SIGNING", re.I),
        )
        seccomp = json.loads((PARSER / "seccomp.json").read_text(encoding="utf-8"))
        self.assertEqual(seccomp["defaultAction"], "SCMP_ACT_ERRNO")
        allowed = {
            name
            for row in seccomp["syscalls"]
            if row.get("action") == "SCMP_ACT_ALLOW"
            for name in row["names"]
        }
        self.assertNotIn("io_uring_setup", allowed)
        source = (PARSER / "seccomp.SOURCE").read_text(encoding="utf-8")
        self.assertIn("seccomp/v0.2.3", source)
        self.assertIn(
            hashlib.sha256((PARSER / "seccomp.json").read_bytes()).hexdigest(), source
        )

    def test_scenario_bytes_and_generator_are_pinned(self):
        self.assertEqual(hashlib.sha256(SCENARIO.read_bytes()).hexdigest(), SCENARIO_SHA256)
        server = (PARSER / "server.py").read_text(encoding="utf-8")
        self.assertIn(SCENARIO_SHA256, server)
        generator = (PARSER / "generate_scenario.py").read_text(encoding="utf-8")
        self.assertIn("invariant=1", generator)
        self.assertIn("เอกสารนี้เป็นข้อมูลสมมติ ไม่ใช่บุคคลจริง", generator)
        self.assertNotIn("C:\\\\Windows", generator)

    def test_protocol_is_strict_and_bounded(self):
        self.assertEqual(MAX_HEADER_BYTES, 4_096)
        self.assertEqual(MAX_PDF_BYTES, 5 * 1024 * 1024)
        self.assertEqual(MAX_RESPONSE_BYTES, 128 * 1024)
        valid = {
            "protocol_version": 1,
            "operation": "parse_document",
            "body_bytes": 1,
            "source_kind": "standard",
        }
        self.assertEqual(request_header(valid), valid)
        for invalid in (
            valid | {"extra": True},
            valid | {"body_bytes": 0},
            valid | {"body_bytes": MAX_PDF_BYTES + 1},
            valid | {"source_kind": "invite"},
            valid | {"protocol_version": 2},
        ):
            with self.assertRaises(ProtocolError):
                request_header(invalid)
        self.assertEqual(
            request_header(valid | {"body_bytes": MAX_PDF_BYTES}),
            valid | {"body_bytes": MAX_PDF_BYTES},
        )
        with self.assertRaises(ProtocolError):
            decode_json(b'{"a":1,"a":2}', maximum=100)
        with self.assertRaises(ProtocolError):
            encode_json({"value": "x" * 100}, maximum=10)

    def test_worker_result_boundary_recomputes_every_sensitive_fact(self):
        segments = [{"page": 1, "segment_id": "seg_001", "text": "safe text"}]
        manifest = hashlib.sha256(
            json.dumps(
                segments,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        source = "a" * 64
        value = {
            "parser_revision": "aiguard-pdf-parser-v1",
            "extraction_revision": "pdfplumber-lines-v1",
            "segmentation_revision": "immutable-lines-v1",
            "source_sha256": source,
            "page_count": 1,
            "character_count": 9,
            "segment_count": 1,
            "omitted_visual_page_numbers": [],
            "segments": segments,
            "segment_manifest_sha256": manifest,
            "extracted_text": "safe text",
        }
        self.assertEqual(validated_result(value, expected_source_sha256=source), value)
        corruptions = (
            value | {"raw_source": "forbidden"},
            value | {"source_sha256": "b" * 64},
            value | {"character_count": 8},
            value | {"segment_count": 2},
            value | {"segment_manifest_sha256": "0" * 64},
            value | {"segments": [segments[0] | {"segment_id": "seg_002"}]},
        )
        for corrupt in corruptions:
            with self.assertRaises(ProtocolError):
                validated_result(corrupt, expected_source_sha256=source)


@unittest.skipUnless(os.environ.get("AIGUARD_PARSER_CONTRACT") == "1", "parser image only")
class ParserImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pikepdf
        from PIL import Image
        from parser_engine import DocumentError, parse_pdf

        cls.pikepdf = pikepdf
        cls.Image = Image
        cls.DocumentError = DocumentError
        cls.parse_pdf = staticmethod(parse_pdf)
        cls.work = Path(tempfile.mkdtemp(prefix="aiguard-doc-", dir="/work"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def mutate(self, name, callback):
        output = self.work / name
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            callback(document)
            document.save(output, deterministic_id=True)
        return output

    def assert_code(self, expected, path):
        with self.assertRaises(self.DocumentError) as caught:
            self.parse_pdf(path)
        self.assertEqual(caught.exception.code, expected)

    def text_pdf(self, name, pages, *, width=595, height=842, font_size=8):
        """Create deterministic inert Type-1 text fixtures without ReportLab."""

        output = self.work / name
        document = self.pikepdf.Pdf.new()
        font = document.make_indirect(
            self.pikepdf.Dictionary(
                Type=self.pikepdf.Name.Font,
                Subtype=self.pikepdf.Name.Type1,
                BaseFont=self.pikepdf.Name.Helvetica,
                Encoding=self.pikepdf.Name.WinAnsiEncoding,
            )
        )
        for lines in pages:
            page = document.add_blank_page(page_size=(width, height))
            page.obj["/Resources"] = self.pikepdf.Dictionary(
                Font=self.pikepdf.Dictionary(F1=font)
            )
            if len(lines) == 1:
                positions = [height / 2]
            else:
                step = (height - 40) / (len(lines) - 1)
                positions = [height - 20 - (step * index) for index in range(len(lines))]
            commands = []
            for line, y in zip(lines, positions):
                self.assertTrue(line.isascii())
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.append(
                    f"BT /F1 {font_size} Tf 1 0 0 1 20 {y:.4f} Tm ({escaped}) Tj ET"
                )
            page.obj["/Contents"] = document.make_stream(
                "\n".join(commands).encode("ascii")
            )
        document.save(output, deterministic_id=True)
        document.close()
        return output

    def add_raster(self, document, *, name, x, y, width, height):
        page = document.pages[0]
        image = document.make_stream(b"\x80\x80\x80")
        image["/Type"] = self.pikepdf.Name.XObject
        image["/Subtype"] = self.pikepdf.Name.Image
        image["/Width"] = 1
        image["/Height"] = 1
        image["/ColorSpace"] = self.pikepdf.Name.DeviceRGB
        image["/BitsPerComponent"] = 8
        resources = page.obj["/Resources"]
        if "/XObject" not in resources:
            resources["/XObject"] = self.pikepdf.Dictionary()
        resources["/XObject"][f"/{name}"] = image
        drawing = document.make_stream(
            f"q {width:.6f} 0 0 {height:.6f} {x:.6f} {y:.6f} cm /{name} Do Q".encode(
                "ascii"
            )
        )
        contents = page.obj["/Contents"]
        if isinstance(contents, self.pikepdf.Array):
            contents.append(drawing)
        else:
            page.obj["/Contents"] = self.pikepdf.Array([contents, drawing])

    def test_valid_scenario_is_deterministic_and_complete(self):
        first = self.parse_pdf(SCENARIO)
        second = self.parse_pdf(SCENARIO)
        self.assertEqual(first, second)
        self.assertEqual(first["source_sha256"], SCENARIO_SHA256)
        self.assertEqual(first["page_count"], 1)
        self.assertEqual(first["segment_count"], 31)
        self.assertEqual(first["omitted_visual_page_numbers"], [1])
        self.assertEqual(
            [row["segment_id"] for row in first["segments"]],
            [f"seg_{index:03d}" for index in range(1, 32)],
        )
        self.assertIn("kanthida.s@example.com", first["extracted_text"])
        self.assertIn("081-234-5678", first["extracted_text"])

    def test_active_content_and_interactive_structures_fail_closed(self):
        pikepdf = self.pikepdf
        mutations = {
            "open-action.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.OpenAction,
                pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="app.alert('x')"),
            ),
            "names.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.Names, pikepdf.Dictionary()
            ),
            "form.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.AcroForm, pikepdf.Dictionary(Fields=pikepdf.Array())
            ),
            "annotation.pdf": lambda pdf: pdf.pages[0].obj.__setitem__(
                pikepdf.Name.Annots,
                pikepdf.Array(
                    [
                        pikepdf.Dictionary(
                            Type=pikepdf.Name.Annot,
                            Subtype=pikepdf.Name.Text,
                            Rect=pikepdf.Array([10, 10, 20, 20]),
                        )
                    ]
                ),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self.assert_code("document_unsupported", self.mutate(name, mutation))

    def test_attachments_xfa_layers_collections_and_external_references_fail_closed(self):
        pikepdf = self.pikepdf
        mutations = {
            "associated-file.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.AF, pikepdf.Array([pikepdf.Dictionary(Type=pikepdf.Name.Filespec)])
            ),
            "embedded-name-tree.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.Names,
                pikepdf.Dictionary(EmbeddedFiles=pikepdf.Dictionary(Names=pikepdf.Array())),
            ),
            "xfa.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.AcroForm,
                pikepdf.Dictionary(Fields=pikepdf.Array(), XFA="forbidden"),
            ),
            "optional-content.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.OCProperties, pikepdf.Dictionary()
            ),
            "collection.pdf": lambda pdf: pdf.Root.__setitem__(
                pikepdf.Name.Collection, pikepdf.Dictionary()
            ),
            "external-reference.pdf": lambda pdf: pdf.pages[0].obj.__setitem__(
                pikepdf.Name.PieceInfo,
                pikepdf.Dictionary(F="https://invalid.example/remote.pdf"),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self.assert_code("document_unsupported", self.mutate(name, mutation))

    def test_compressed_objects_and_tiny_inline_raster_are_inspected(self):
        compressed = self.work / "compressed-object-streams.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            document.save(
                compressed,
                deterministic_id=True,
                compress_streams=True,
                object_stream_mode=self.pikepdf.ObjectStreamMode.generate,
            )
        parsed = self.parse_pdf(compressed)
        self.assertEqual(parsed["segment_count"], 31)
        self.assertEqual(parsed["omitted_visual_page_numbers"], [1])

        inline = self.work / "tiny-inline-image.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            page = document.pages[0]
            stream = document.make_stream(
                b"q 4 0 0 4 10 10 cm BI /W 1 /H 1 /CS /RGB /BPC 8 ID "
                b"\x80\x80\x80 EI Q"
            )
            page.obj["/Contents"] = self.pikepdf.Array([page.obj["/Contents"], stream])
            document.save(inline, deterministic_id=True)
        inline_result = self.parse_pdf(inline)
        self.assertEqual(inline_result["segment_count"], 31)
        self.assertEqual(inline_result["omitted_visual_page_numbers"], [1])

    def test_encryption_page_count_dimensions_and_malformed_fail_closed(self):
        encrypted = self.work / "encrypted.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            document.save(
                encrypted,
                encryption=self.pikepdf.Encryption(owner="owner", user="user", R=6),
            )
        self.assert_code("document_unsupported", encrypted)
        oversized = self.mutate(
            "oversized-page.pdf",
            lambda pdf: pdf.pages[0].obj.__setitem__(
                self.pikepdf.Name.MediaBox,
                self.pikepdf.Array([0, 0, 2001, 842]),
            ),
        )
        self.assert_code("document_unsupported", oversized)
        too_many = self.work / "eleven-pages.pdf"
        output = self.pikepdf.Pdf.new()
        with self.pikepdf.Pdf.open(SCENARIO) as source:
            for _ in range(11):
                output.pages.append(source.pages[0])
        output.save(too_many, deterministic_id=True)
        output.close()
        self.assert_code("document_unsupported", too_many)
        malformed = self.work / "malformed.pdf"
        malformed.write_bytes(b"%PDF-1.7\nnot a valid xref\n%%EOF\n")
        self.assert_code("document_unsupported", malformed)

    def test_exact_page_dimension_text_and_segment_boundaries(self):
        ten_pages = self.text_pdf(
            "ten-pages.pdf",
            [["A" * 90 for _ in range(5)] for _ in range(10)],
        )
        ten_result = self.parse_pdf(ten_pages)
        self.assertEqual(ten_result["page_count"], 10)
        self.assertEqual(ten_result["segment_count"], 50)

        width_2000 = self.text_pdf(
            "width-2000.pdf",
            [["A" * 300 for _ in range(5)]],
            width=2_000,
        )
        self.assertEqual(self.parse_pdf(width_2000)["page_count"], 1)
        width_over = self.text_pdf(
            "width-2000-point-1.pdf",
            [["A" * 300 for _ in range(5)]],
            width=2_000.1,
        )
        self.assert_code("document_unsupported", width_over)

        exact_text_lines = ["A" * 98 for _ in range(79)] + ["A" * 100]
        exact_text = self.text_pdf("exact-8000-codepoints.pdf", [exact_text_lines])
        exact_result = self.parse_pdf(exact_text)
        self.assertEqual(exact_result["character_count"], 8_000)
        self.assertEqual(exact_result["segment_count"], 80)

        over_text_lines = ["A" * 98 for _ in range(79)] + ["A" * 101]
        over_text = self.text_pdf("over-8000-codepoints.pdf", [over_text_lines])
        self.assert_code("document_too_complex", over_text)

        over_segments = self.text_pdf(
            "over-80-segments.pdf",
            [["A" * 80 for _ in range(81)]],
        )
        self.assert_code("document_too_complex", over_segments)

    def test_image_only_and_large_raster_overlay_are_rejected_without_ocr(self):
        image_pdf = self.work / "image-only.pdf"
        self.Image.new("RGB", (1000, 1400), "white").save(image_pdf, "PDF", resolution=144)
        self.assert_code("pdf_text_layer_required", image_pdf)

        overlay_pdf = self.work / "overlay-source.pdf"
        self.Image.new("RGB", (1000, 1400), "#dddddd").save(
            overlay_pdf, "PDF", resolution=144
        )
        overlaid = self.work / "large-overlay.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as base, self.pikepdf.Pdf.open(
            overlay_pdf
        ) as overlay:
            base.pages[0].add_overlay(overlay.pages[0])
            base.save(overlaid, deterministic_id=True)
        self.assert_code("pdf_visual_content_unsupported", overlaid)

    def test_exact_raster_area_boundaries(self):
        page_width = 595.0
        page_height = 842.0
        cases = (
            ("single-exact-10.pdf", ((0.0, 0.0, page_width * 0.10, page_height),), True),
            ("single-over-10.pdf", ((0.0, 0.0, page_width * 0.101, page_height),), False),
            (
                "combined-exact-15.pdf",
                (
                    (0.0, 0.0, page_width * 0.075, page_height),
                    (page_width * 0.20, 0.0, page_width * 0.075, page_height),
                ),
                True,
            ),
            (
                "combined-over-15.pdf",
                (
                    (0.0, 0.0, page_width * 0.076, page_height),
                    (page_width * 0.20, 0.0, page_width * 0.075, page_height),
                ),
                False,
            ),
        )
        for filename, rectangles, accepted in cases:
            output = self.work / filename
            with self.pikepdf.Pdf.open(SCENARIO) as document:
                for index, (x, y, width, height) in enumerate(rectangles):
                    self.add_raster(
                        document,
                        name=f"Boundary{index}",
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                    )
                document.save(output, deterministic_id=True)
            with self.subTest(filename=filename):
                if accepted:
                    self.assertEqual(self.parse_pdf(output)["segment_count"], 31)
                else:
                    self.assert_code("pdf_visual_content_unsupported", output)

    def test_tiny_text_overlay_form_cycles_depth_and_container_bombs_fail_closed(self):
        tiny = self.work / "tiny-text-overlay.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            page = document.pages[0]
            page.obj["/Contents"] = self.pikepdf.Array(
                [
                    document.make_stream(b"q 0.01 0 0 0.01 0 0 cm"),
                    page.obj["/Contents"],
                    document.make_stream(b"Q"),
                ]
            )
            document.save(tiny, deterministic_id=True)
        self.assert_code("pdf_text_layer_required", tiny)

        def form(document, content, resources):
            value = document.make_stream(content)
            value["/Type"] = self.pikepdf.Name.XObject
            value["/Subtype"] = self.pikepdf.Name.Form
            value["/FormType"] = 1
            value["/BBox"] = self.pikepdf.Array([0, 0, 595, 842])
            value["/Resources"] = resources
            return value

        cycle = self.work / "form-cycle.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            resources = self.pikepdf.Dictionary(XObject=self.pikepdf.Dictionary())
            looping = form(document, b"/Self Do", resources)
            resources["/XObject"]["/Self"] = looping
            document.pages[0].obj["/Resources"] = self.pikepdf.Dictionary(
                XObject=self.pikepdf.Dictionary(Cycle=looping)
            )
            document.pages[0].obj["/Contents"] = document.make_stream(b"/Cycle Do")
            document.save(cycle, deterministic_id=True)
        self.assert_code("document_unsupported", cycle)

        deep = self.work / "form-depth-bomb.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            page = document.pages[0]
            current = form(document, page.obj["/Contents"].read_bytes(), page.obj["/Resources"])
            for index in range(42):
                current = form(
                    document,
                    b"/Next Do",
                    self.pikepdf.Dictionary(XObject=self.pikepdf.Dictionary(Next=current)),
                )
            page.obj["/Resources"] = self.pikepdf.Dictionary(
                XObject=self.pikepdf.Dictionary(Deep=current)
            )
            page.obj["/Contents"] = document.make_stream(b"/Deep Do")
            document.save(deep, deterministic_id=True)
        self.assert_code("document_unsupported", deep)

        bomb = self.work / "container-member-bomb.pdf"
        with self.pikepdf.Pdf.open(SCENARIO) as document:
            values = self.pikepdf.Dictionary()
            for index in range(20_001):
                values[self.pikepdf.Name(f"/K{index:05d}")] = 0
            document.Root["/ViewerPreferences"] = values
            document.save(bomb, deterministic_id=True)
        self.assert_code("document_unsupported", bomb)

    def test_invisible_or_clip_only_text_is_not_a_usable_text_layer(self):
        for render_mode in (3, 4, 5, 6, 7):
            output = self.work / f"text-render-mode-{render_mode}.pdf"
            with self.pikepdf.Pdf.open(SCENARIO) as document:
                content = document.pages[0].obj["/Contents"]
                raw = content.read_bytes()
                content.write(raw.replace(b"BT", f"BT {render_mode} Tr".encode("ascii")))
                document.save(output, deterministic_id=True)
            self.assert_code("pdf_text_layer_required", output)

        for clip_operator in (b"W", b"W*"):
            output = self.work / f"graphics-clip-{clip_operator.decode().replace('*', 'star')}.pdf"
            with self.pikepdf.Pdf.open(SCENARIO) as document:
                content = document.pages[0].obj["/Contents"]
                raw = content.read_bytes()
                content.write(b"q 0 0 1 1 re " + clip_operator + b" n\n" + raw + b"\nQ")
                document.save(output, deterministic_id=True)
            self.assert_code("document_unsupported", output)

        def form(document, content, resources):
            value = document.make_stream(content)
            value["/Type"] = self.pikepdf.Name.XObject
            value["/Subtype"] = self.pikepdf.Name.Form
            value["/FormType"] = 1
            value["/BBox"] = self.pikepdf.Array([0, 0, 595, 842])
            value["/Resources"] = resources
            return value

        for nested in (False, True):
            output = self.work / f"graphics-clip-form-{'nested' if nested else 'direct'}.pdf"
            with self.pikepdf.Pdf.open(SCENARIO) as document:
                page = document.pages[0]
                raw = page.obj["/Contents"].read_bytes()
                original_resources = page.obj["/Resources"]
                inner = form(
                    document,
                    b"q 0 0 1 1 re W n\n" + raw + b"\nQ",
                    original_resources,
                )
                if nested:
                    outer_resources = self.pikepdf.Dictionary(
                        XObject=self.pikepdf.Dictionary(Inner=inner)
                    )
                    outer = form(document, b"/Inner Do", outer_resources)
                    page.obj["/Resources"] = self.pikepdf.Dictionary(
                        XObject=self.pikepdf.Dictionary(Outer=outer)
                    )
                    page.obj["/Contents"] = document.make_stream(b"/Outer Do")
                else:
                    page.obj["/Resources"] = self.pikepdf.Dictionary(
                        XObject=self.pikepdf.Dictionary(Clipped=inner)
                    )
                    page.obj["/Contents"] = document.make_stream(b"/Clipped Do")
                document.save(output, deterministic_id=True)
            self.assert_code("document_unsupported", output)

    def test_killable_worker_timeout_reaps_before_return(self):
        import asyncio
        import server

        output = self.work / "result-00000000000000000000000000000000.json"
        prior = server.PARSE_TIMEOUT_SECONDS
        server.PARSE_TIMEOUT_SECONDS = 0.000001
        try:
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(server._run_worker(SCENARIO, output))
        finally:
            server.PARSE_TIMEOUT_SECONDS = prior
            output.unlink(missing_ok=True)
        children = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children").read_text(
            encoding="ascii"
        )
        self.assertEqual(children.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
