-- Where did every raw row go? accepted + exact_duplicate + superseded + quarantined = raw.
-- `drugspend report` compares these counts with the generator's injected-defect manifest.
select
    row_status,
    coalesce(dq_issue, 'n/a') as dq_issue,
    count(*)                  as row_count
from {{ ref('stg_part_d__prescriber_drug') }}
group by 1, 2
