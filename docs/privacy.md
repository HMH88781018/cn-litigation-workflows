# Privacy model

This repository collects no telemetry and sends no matter data to a bundled
service. Public automation operates only on committed public-project content
or a size-bounded public pull-request diff; it must never receive matter files.

Never submit real names, identity numbers, contact information, addresses,
medical records, financial information, evidence, privileged communications,
signatures, account identifiers, or other confidential material to public
issues, pull requests, examples, fixtures, CI logs, or model-review workflows.

Use synthetic data by default. Redaction must be irreversible and must include
document properties, comments, tracked changes, custom XML, embedded files,
relationships, filenames, screenshots, and image metadata—not only visible
text.

The repository validator detects a limited set of high-risk patterns and Office
package metadata. A clean scan does not prove anonymization. Human review
remains mandatory.
