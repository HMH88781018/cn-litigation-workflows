# Repository instructions

Run these checks before proposing or committing a change:

```bash
python3 scripts/validate_project.py .
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py
python3 scripts/package_plugin.py --output /tmp/cn-litigation-workflows.zip
```

Never add real client, matter, identity, contact, medical, financial, evidence
or privileged information. Use synthetic fixtures only.

For a time-sensitive legal claim, cite an official source and record issuer,
title, URL, effective date and verification date. Do not label a legal or
statistical value current solely because it exists in this repository.

Keep each Skill focused. Put operational instructions in `SKILL.md`, detailed
rules in one-level `references/` files, deterministic operations in `scripts/`
and reusable output materials in `assets/`.

Do not:

- silently change routing between the two Skills;
- write dynamic legal/statistical values into formulas;
- auto-merge legal-source updates;
- treat passing automation as substantive legal approval;
- add MCP servers, hooks, telemetry or network calls without a concrete,
  reviewed requirement;
- change the plugin version without updating the changelog and citation file.

Changes to legal rules, templates, damages formulas, insurance allocation or
release gates need both engineering and qualified legal-content review.
