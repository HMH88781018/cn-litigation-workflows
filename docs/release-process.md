# Release process

1. Confirm the release scope and privacy/provenance review.
2. Refresh affected official-source registries and record transition rules.
3. Add deterministic regression cases for changed behavior.
4. Obtain engineering review and, where applicable, qualified legal-content
   review.
5. Run validation, tests, deterministic full-source packaging and, for an
   OpenAI directory submission, the allowlisted Skills-only packaging mode.
6. Synchronize `.codex-plugin/plugin.json`, `pyproject.toml`,
   `src/cn_litigation_workflows/validator.py`, `CHANGELOG.md`, and
   `CITATION.cff`.
7. Commit the exact release source and create a signed or annotated `vX.Y.Z`
   tag when possible.
8. Let the tag workflow rebuild the archive and checksum from the tagged
   source, then verify the published assets.
9. Record only observable usage or adopter evidence.

The GitHub release archive and the OpenAI directory upload are separate
artifacts. Build the latter with:

```bash
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-vX.Y.Z.zip
```

The submission ZIP may contain only the manifest, declared brand assets,
bundled Skills and the license/provenance notices. Portal listing copy, review
cases and unsigned author confirmations remain outside the installable ZIP.

The release workflow cannot approve legal content and must not be used to
publish real matter data.
