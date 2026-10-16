/*
  Fact table. GRAIN: one row per prescriber (NPI) x drug (brand + generic) x data year.

  The prescriber join is POINT-IN-TIME: each fact links to the dimension version that was
  valid in its data_year, so 2021 spend is attributed to the prescriber's 2021 specialty
  and location even if they changed later.

  Materialized as a full-refresh table on purpose: a late correction can move SCD2 version
  boundaries, which changes prescriber_sk for historical facts. An incremental fact would
  keep pointing at keys that no longer exist. (See LEARN.md, "Why is the fact not incremental?")
*/
with accepted as (

    select * from {{ ref('int_part_d__accepted') }}

),

prescribers as (

    select * from {{ ref('dim_prescriber') }}
    where npi <> 'UNKNOWN'

),

drugs as (

    select * from {{ ref('dim_drug') }}
    where drug_sk <> '-1'

),

geography as (

    select * from {{ ref('dim_geography') }}

)

select
    {{ surrogate_key(['a.npi', 'a.brand_name', 'a.generic_name', 'a.data_year']) }} as prescription_id,
    coalesce(p.prescriber_sk, '-1')        as prescriber_sk,
    coalesce(d.drug_sk, '-1')              as drug_sk,
    coalesce(g.state_code, 'UNK')          as state_code,
    a.data_year,
    a.npi,                                  -- degenerate dimension: handy for drill-down
    cast(a.total_claims as integer)        as total_claims,
    a.total_30day_fills,
    cast(a.total_day_supply as integer)    as total_day_supply,
    a.total_drug_cost,
    cast(a.total_beneficiaries as integer) as total_beneficiaries,
    a.is_beneficiary_count_suppressed,
    round(a.total_drug_cost / nullif(a.total_claims, 0), 2)     as cost_per_claim,
    round(a.total_drug_cost / nullif(a.total_day_supply, 0), 4) as cost_per_day_supply,
    a.batch_id                             as source_batch_id
from accepted as a
left join prescribers as p
    on  a.npi = p.npi
    and a.data_year between p.valid_from_year and p.valid_to_year
left join drugs as d
    on  a.brand_name = d.brand_name
    and a.generic_name = d.generic_name
left join geography as g
    on  a.prescriber_state = g.state_code
