/*
  SCD Type 2 prescriber dimension, built from BUSINESS-EFFECTIVE time (data_year),
  not from processing time.

  Why not a dbt snapshot? Snapshots record "what the table looked like when the job ran".
  Our 2022 correction file arrives AFTER the 2023 file. A snapshot would have frozen the
  wrong 2022 specialty into history and could never fix it. Rebuilding the history from
  data_year every run means a late correction simply rewrites the affected years.
  (See docs/decisions/0004-scd2-from-effective-dates.md.)

  A new version starts whenever a prescriber's attribute_hash differs from the previous
  year they appear in. valid_to_year = (next version's start - 1), or 9999 if open-ended.
*/
with yearly as (

    select * from {{ ref('int_prescriber_yearly_attributes') }}

),

with_previous as (

    select
        *,
        lag(attribute_hash) over (partition by npi order by data_year) as previous_hash
    from yearly

),

version_starts as (

    select *
    from with_previous
    where previous_hash is null
       or previous_hash <> attribute_hash

),

versions as (

    select
        *,
        lead(data_year) over (partition by npi order by data_year)  as next_version_start,
        row_number()   over (partition by npi order by data_year)   as version_number
    from version_starts

)

select
    {{ surrogate_key(['npi', 'data_year']) }}             as prescriber_sk,
    npi,
    prescriber_last_org_name,
    prescriber_first_name,
    prescriber_city,
    prescriber_state,
    prescriber_specialty,
    data_year                                              as valid_from_year,
    coalesce(next_version_start - 1, 9999)                 as valid_to_year,
    case when next_version_start is null then true else false end as is_current,
    version_number
from versions

union all

-- Unknown member: facts that cannot be matched still land, pointing here, instead of
-- disappearing in an inner join.
select
    '-1', 'UNKNOWN', 'UNKNOWN', cast(null as varchar), 'UNKNOWN', 'UNK', 'UNKNOWN',
    0, 9999, true, 1
