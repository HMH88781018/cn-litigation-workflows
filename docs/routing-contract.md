# Routing contract

## Complaint Skill

Use `draft-cn-element-complaints` when the primary deliverable is a Chinese
element-based or tabular complaint, a controlled point edit, a template repair,
or a complaint-bundle release review.

It owns:

- official complaint-template selection and structural preservation;
- complaint parties, claims, facts, and procedural selections;
- DOCX structural audit and authorized-difference review;
- the final state of the complaint bundle.

## Evidence and damages Skill

Use `prepare-cn-evidence-damages` when the primary deliverable is an evidence
list, evidence-bundle directory, continuous pagination map, traffic-accident
damages calculation, insurance allocation audit, or payment reconciliation.

It owns:

- evidence IDs, order, page ranges, and proof-purpose mapping;
- damages parameters, formulas, line items, subtotals, and total;
- insurance layers, policy limits, prior payments, and reconciliation;
- the values exported to the complaint.

## Handoff invariant

When both Skills apply, evidence and damages data has one source of truth. The
complaint Skill must not create parallel numbering or calculations. Any
difference in IDs, page ranges, formulas, subtotals, or totals forces the
combined output back to `DRAFT`.

Generic legal advice, non-Chinese pleadings, evidence objections, and strategy
analysis outside these deliverables are out of scope.
