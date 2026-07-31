# Testing

The merge gate is deterministic and uses the Python standard library.

```bash
python3 scripts/validate_project.py .
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py
python3 scripts/package_plugin.py --output /tmp/cn-litigation-workflows.zip
```

Checks cover:

- plugin and marketplace manifests, versions, Skill names, frontmatter, links,
  and explicit default prompts;
- credential-like files, identity-number and phone patterns, local paths,
  Office author/account metadata, embedded objects, and external workbook links;
- workbook sheet topology and formula presence;
- DOCX package/XML resource limits, all relationship parts, privacy-preserving
  audit output, identical comparisons, and text-only differences;
- cross-Skill ownership and synthetic routing cases;
- eval dataset structure and scored observed-property results;
- deterministic, bounded release archives and SHA-256 checksums.

The checks do not prove current law, factual accuracy, formula applicability,
visual quality, legal sufficiency, or confidentiality. Those remain explicit
human review gates.

The no-argument eval command validates the public case set. To exercise the
installed Skills and score recorded observations, follow [the eval guide](evals.md).
