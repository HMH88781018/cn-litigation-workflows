# Security Policy

## Supported versions

Security fixes are provided for the latest released minor version. The initial
supported line is `0.1.x`.

## Report privately

Use GitHub private vulnerability reporting when available. Do not open a public
issue containing client data, repository secrets, identity data, exploitable
document samples or a working attack payload.

Include:

- affected version and component;
- a minimal synthetic reproducer;
- impact and preconditions;
- whether document text, credentials or external systems are exposed;
- a suggested mitigation, if known.

## Security model

The plugin includes no hosted service, telemetry, bundled MCP server or
credential handling. Its primary risks are:

- malicious or malformed DOCX/XLSX/PDF inputs;
- path traversal during archive processing;
- formula injection or unsafe external links;
- prompt injection embedded in matter files;
- personal-data leakage to logs, fixtures or public collaboration;
- over-trusting a successful structural check as substantive legal approval.

The included tools are read-only unless a user explicitly invokes the release
packager. CI uses synthetic files and minimum permissions.

The optional Codex PR-review workflow is disabled by default. If enabled, it
passes a maintainer-supplied `OPENAI_API_KEY` secret only to the pinned official
Codex Action, runs on an isolated size-bounded diff with a read-only permission
profile, and makes Codex the final step in that job. Never expose the secret to
pull-request code or repository scripts.

## Disclosure

Maintainers will acknowledge a valid private report when reasonably possible,
investigate it, publish a fix and credit the reporter if requested. No fixed
response-time guarantee is made.
