{% docs __overview__ %}
# Medicare Part D Drug Spend Warehouse

**Question this answers:** which drugs, prescribers and specialties drive Medicare Part D
spending growth, and how much could be saved by dispensing generics instead of brands?

**Layers**
- `raw` (bronze): text-only copy of every delivered file + lineage
- `staging` (silver): typed and cleaned; every raw row labelled `accepted`, `exact_duplicate`,
  `superseded` (by a later restatement) or `quarantined` (with a reason)
- `marts` (gold): Kimball star schema (`fct_prescriptions` + conformed dimensions, SCD Type 2
  prescriber history) and analytics marts
- `quality`: quarantine table and a row-level reconciliation

Start with the lineage graph (bottom-right button) to see how data flows.
{% enddocs %}
