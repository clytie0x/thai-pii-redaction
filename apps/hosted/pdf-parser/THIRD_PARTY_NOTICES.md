# AI Guard PDF parser third-party notices

The parser image is intentionally isolated and contains no AI Guard application
secret. Python dependency bytes are installed only from `requirements.lock` with
package hashes. The image build also asserts the exact embedded qpdf version.

| Component | Locked version | License | Primary source |
| --- | --- | --- | --- |
| pikepdf | 10.10.0 | MPL-2.0 | https://github.com/pikepdf/pikepdf |
| qpdf (bundled by pikepdf wheel) | 12.3.2 | Apache-2.0 | https://github.com/qpdf/qpdf |
| pdfplumber | 0.11.10 | MIT | https://github.com/jsvine/pdfplumber |
| pypdfium2 / PDFium binary | 5.12.1 | Apache-2.0 / BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2 |
| Anuphan (embedded subset in synthetic scenario) | v6 source font | SIL OFL-1.1 | https://github.com/cadsondemak/Anuphan |

Complete license texts shipped by Python wheels remain in their installed
distribution metadata. The Anuphan OFL text is copied into `licenses/` next to
the scenario. No dependency or embedded font is loaded from a network at runtime.
