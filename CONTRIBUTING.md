# Contributing

Contributions are welcome when they improve a reproducible public workflow
without exposing real matter data.

## Before opening a change

1. Search existing issues.
2. Use only synthetic or irreversibly redacted examples.
3. Identify the affected Skill and workflow boundary.
4. For a legal-source change, provide the official issuer, title, URL,
   effective date, access date and the exact rule affected.
5. For a template or formula change, describe the before/after structure and
   add a regression test.

## Required checks

```bash
python3 scripts/validate_project.py .
python3 -m unittest discover -s tests -v
python3 scripts/package_plugin.py --output /tmp/cn-litigation-workflows.zip
```

Do not commit generated reports, local paths, credentials, unredacted files or
customer names. Do not change a locked legal value silently.

## Review requirements

Changes limited to general documentation or test infrastructure need one
maintainer review. Changes to legal rules, court-template behavior, evidence
logic, damages formulas, insurance allocation or release gates need:

- an engineering review for deterministic behavior and compatibility; and
- a qualified legal-content review against the cited official source.

Model-generated review is advisory and cannot replace either human review.
Legal-source update automation may open an issue but must never change the rule
or merge a pull request automatically.

## Commit and pull-request scope

Keep each pull request focused. Explain:

- what changed and why;
- the workflow and risk affected;
- source/provenance;
- tests and synthetic fixtures used;
- privacy review;
- whether versions or release notes must change.

By contributing, you agree that your contribution is licensed under
Apache-2.0 and that you have the right to submit it.
