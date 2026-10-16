-- Rows that failed a quality rule. Kept (not deleted) so they can be inspected, reported
-- back to the producer, and replayed once fixed. Nothing here reaches the marts.
select
    raw_row_id,
    dq_issue,
    source_file,
    batch_id,
    source_row_number,
    npi,
    brand_name,
    generic_name,
    data_year,
    total_claims,
    total_drug_cost,
    loaded_at
from {{ ref('stg_part_d__prescriber_drug') }}
where row_status = 'quarantined'
