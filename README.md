# CN Litigation Workflows

[简体中文](README.zh-CN.md)

Auditable, open-source agent Skills for high-risk Chinese litigation document
workflows. The project turns practitioner procedures into versioned,
testable workflows for ChatGPT and Codex.

[![CI](https://github.com/HMH88781018/cn-litigation-workflows/actions/workflows/ci.yml/badge.svg)](https://github.com/HMH88781018/cn-litigation-workflows/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/HMH88781018/cn-litigation-workflows?include_prereleases)](https://github.com/HMH88781018/cn-litigation-workflows/releases)

> Initial public release. This repository does not claim court approval,
> guaranteed legal accuracy, broad adoption, or eligibility for any OpenAI
> program. OpenAI reviews Codex for Open Source applications independently.

## Included Skills

| Skill | Owns | Does not own |
|---|---|---|
| `draft-cn-element-complaints` | Element-based complaint routing, official-template preservation, point edits, DOCX structural audit, cross-document release gates | General legal advice or non-Chinese pleadings |
| `prepare-cn-evidence-damages` | Evidence lists, evidence-bundle directories and pagination, traffic-accident damage calculations, insurance/payment reconciliation | The complaint body or generic evidence objections |

The contract between the two Skills is explicit: the evidence/damages Skill is
the source of truth for evidence IDs, page ranges, formulas and amounts; the
complaint Skill consumes those locked values and owns the final complaint
bundle state.

## Why this repository exists

Chinese standardized pleadings are not ordinary text-generation tasks. They
combine current legal sources, court templates, merged tables, multiple
parties, checkboxes, continuous exhibit pagination, formulas and cross-file
consistency. A plausible paragraph can still produce an unusable filing.

This project therefore emphasizes:

- source provenance and verification dates;
- deterministic DOCX topology audits and point-edit diffs;
- evidence-to-issue and claim-to-damages traceability;
- formula and page-number closure;
- explicit `DRAFT`, `REVIEW` and `RELEASE` states;
- human legal and visual review before release;
- synthetic public tests instead of client files.

## Install as a plugin

Add this GitHub repository as a Codex marketplace and install the plugin:

```bash
codex plugin marketplace add HMH88781018/cn-litigation-workflows --ref v0.1.1
codex plugin add cn-litigation-workflows@cn-litigation-workflows
```

In the ChatGPT desktop app, open **Plugins**, choose the
`CN Litigation Workflows` source, then install and enable the plugin.

GitHub marketplace installation is not public directory publication. For an
OpenAI Plugins Directory submission, build the allowlisted Skills-only ZIP:

```bash
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-v0.1.1.zip
```

Then use the OpenAI Platform plugin submission portal with the
[submission materials](submission/listing.zh-CN.md). Directory review and
publication do not by themselves establish eligibility for any creator
payment program.

To use only the standalone Skills in Codex:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/draft-cn-element-complaints "$HOME/.agents/skills/"
cp -R skills/prepare-cn-evidence-damages "$HOME/.agents/skills/"
```

## Examples

```text
Use $draft-cn-element-complaints to review this element-based complaint in
REVIEW mode. Do not modify the file. Identify the official template version,
structural drift, missing locked fields and release blockers.
```

```text
Use $prepare-cn-evidence-damages to create an evidence manifest and traffic
damages worksheet from these redacted materials. Keep dynamic legal and
statistical values as sourced parameters and mark the output DRAFT until all
release gates pass.
```

See [synthetic examples](examples/README.md) and the
[architecture](docs/architecture.md).

## Validate and test

The required checks use the Python standard library:

```bash
python3 scripts/validate_project.py .
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py
python3 scripts/package_plugin.py --output dist/cn-litigation-workflows.zip
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-v0.1.1.zip
```

The checks validate manifests, Skill contracts, referenced resources,
privacy-sensitive patterns, DOCX audit behavior, the workbook structure and
the release archive boundary. See the [eval guide](docs/evals.md) to run the
synthetic prompts and score observed Skill behavior.

An optional Codex pull-request review workflow is committed but disabled by
default. Maintainers can add an `OPENAI_API_KEY` secret and set the repository
variable `ENABLE_CODEX_REVIEW=true`. It runs read-only on a size-bounded,
isolated PR diff and must never receive client files.

## Safety and scope

- Mainland China is the default jurisdictional scope. Re-verify current law,
  causes of action, official templates, local filing rules, statistical
  parameters and insurance limits for every matter.
- Outputs remain `DRAFT` until the applicable gates and independent review
  pass. The project cannot determine legal correctness by itself.
- Never put client names, identity numbers, contact details, medical records,
  evidence or confidential matter data in public issues, pull requests,
  fixtures or CI logs.
- No telemetry, remote service, MCP server or credential collection is bundled.
- The 67-template `yaosushi-suzhuang` project and the generic
  `legal-logic-analysis` Skill are intentionally not bundled; see
  [provenance](docs/provenance.md).

Read [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md),
[TERMS.md](TERMS.md) and the [legal-source policy](docs/legal-source-policy.md)
before real-world use.

## Contributing and governance

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Changes to legal rules,
templates, formulas or release gates require both engineering review and
qualified legal-content review. The project never auto-merges legal-source
updates.

Current maintainers and decision rules are in [GOVERNANCE.md](GOVERNANCE.md).
Verified public adopters may add themselves to [ADOPTERS.md](ADOPTERS.md) by
pull request. Empty fields and zero usage are preferable to invented metrics.

## License

Original project material is licensed under [Apache-2.0](LICENSE). The license
does not grant rights in third-party court forms, laws, external websites or
other material that the project does not own. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
