# Compatibility

## Required environment

- Python 3.10 or later for repository validation and packaging.
- A ZIP/OOXML-compatible DOCX/XLSX producer for real document work.
- ChatGPT or Codex surface capable of loading Agent Skills or the repository
  plugin marketplace.

## Verification status for 0.1.1

| Surface | Status |
|---|---|
| Python 3.10 and 3.12 | Covered by CI |
| Plugin manifest and repo marketplace | Deterministically validated |
| DOCX structural scripts | Covered with synthetic OOXML packages |
| XLSX structure | Sheet and formula topology validated |
| Microsoft Word, LibreOffice, WPS, mobile preview | Not certified; visual review required per output |
| Court filing systems | Not certified |

Compatibility claims should be updated only with a reproducible environment and
public evidence. A file opening successfully is not a release conclusion.
