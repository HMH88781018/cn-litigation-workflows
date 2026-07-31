# Governance

## Maintainer

Huang Minghuan (`@HMH88781018`) is the founding primary maintainer and release
sign-off owner.

## Decision model

The project uses maintainer consensus when more than one maintainer is active.
Until then, the primary maintainer decides after the required reviews.

Legal-source, template, formula and release-gate changes require a recorded
legal-content review in addition to engineering review. A model cannot be the
sole approving reviewer.

## Maintainer responsibilities

- triage public issues without requesting confidential case data;
- verify contributor rights and source provenance;
- keep CI and synthetic evals reproducible;
- record releases and breaking workflow changes;
- distinguish verified usage from estimates;
- disclose conflicts of interest relevant to a contribution;
- remove access from inactive or compromised maintainer accounts.

## Adding maintainers

Candidates should show sustained, reviewable contributions and sound handling
of legal-source, privacy and engineering risks. The primary maintainer records
the decision in a pull request that updates this file and `CODEOWNERS`.

## Releases

Releases follow Semantic Versioning while the plugin is `0.x`:

- patch: compatible corrections and documentation;
- minor: new workflow capability or materially stronger checks;
- major: incompatible routing, data-model or release-contract change.

Every release must pass the release checklist, update `CHANGELOG.md`, use the
same version in the plugin manifest and tag, and include a generated archive
plus SHA-256 checksum.
