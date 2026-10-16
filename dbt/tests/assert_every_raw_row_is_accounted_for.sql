-- Nothing may be silently dropped between raw and staging: one staged row per raw row.
with raw_rows as (
    select count(*) as n from {{ source('raw', 'part_d_prescriber_drug') }}
),
staged_rows as (
    select count(*) as n from {{ ref('stg_part_d__prescriber_drug') }}
)
select r.n as raw_row_count, s.n as staged_row_count
from raw_rows as r
cross join staged_rows as s
where r.n <> s.n
