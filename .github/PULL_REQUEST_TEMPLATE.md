## What changed

Describe the bounded change and why it is needed.

## Workflow and risk

- Affected Skill or tool:
- DRAFT/REVIEW/RELEASE behavior affected:
- Routing or cross-document contract affected:

## Source and provenance

For legal-source, template, or formula changes, identify the official issuer,
title, URL, effective date, verification date, and transition rule.

## Verification

- [ ] `python3 scripts/validate_project.py .`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 scripts/package_plugin.py --output /tmp/cn-litigation-workflows.zip`
- [ ] Tests and examples contain only synthetic or irreversibly redacted data.
- [ ] I reviewed the diff for credentials, local paths, personal data, and client data.
- [ ] I updated release notes when behavior changed.

## Human review

- [ ] Engineering review completed.
- [ ] Qualified legal-content review completed, or the change does not affect
      legal rules, templates, formulas, insurance allocation, or release gates.

Model-generated feedback is advisory and cannot satisfy either human approval.
