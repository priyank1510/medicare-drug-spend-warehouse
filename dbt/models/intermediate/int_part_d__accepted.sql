-- The rows that are allowed to reach the star schema.
select *
from {{ ref('stg_part_d__prescriber_drug') }}
where row_status = 'accepted'
