# Architecture

The installed plugin is skills-only. It has no MCP server, hook, telemetry,
remote runtime, or credential flow. A disabled-by-default maintainer workflow
in this source repository can separately pass an `OPENAI_API_KEY` GitHub secret
to the pinned official Codex Action; that CI-only path is not part of plugin
runtime behavior.

## Components

| Component | Responsibility | Trust boundary |
|---|---|---|
| `draft-cn-element-complaints` | Complaint template routing, controlled drafting, DOCX topology checks, final bundle state | Consumes only locked evidence and amount values |
| `prepare-cn-evidence-damages` | Evidence IDs, pagination, damages formulas, insurance and payment reconciliation | Owns evidence and amount source-of-truth data |
| `src/cn_litigation_workflows` | Deterministic repository validation and release packaging | Never processes client matters |
| `.github/workflows` | Public CI, source freshness, opt-in review, tagged releases | Public/synthetic repository content only |

The Skills contain operational instructions, one-level reference material,
deterministic local scripts, and a workbook asset. Model behavior is bounded by
human review and explicit `DRAFT`, `REVIEW`, and `RELEASE` states.

## Data flow

1. Lock jurisdiction, official source, template, parties, facts, and scope.
2. Build evidence IDs, page ranges, formulas, and amounts in the
   evidence/damages source of truth.
3. Consume locked values in the complaint workflow.
4. Compare structure, text, formulas, and cross-document totals.
5. Render and review every output page.
6. Mark `RELEASE` only after all applicable gates and human review pass.

No public test or automation step accepts real matter data.
