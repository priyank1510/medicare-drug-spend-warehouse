/*
  Generic substitution opportunity: if the days of supply dispensed as BRAND had been
  dispensed at the GENERIC cost per day of the same molecule, how much gross spend is
  avoided? Only molecules with both a brand and a generic version are included.

  Caveat worth saying in an interview: CMS cost is gross, before manufacturer rebates,
  so real savings are smaller than this upper bound.
*/
with facts as (

    select f.data_year, d.generic_name, d.is_generic,
           f.total_drug_cost, f.total_day_supply
    from {{ ref('fct_prescriptions') }} as f
    inner join {{ ref('dim_drug') }} as d on f.drug_sk = d.drug_sk
    where d.drug_sk <> '-1'

),

by_type as (

    select
        generic_name,
        data_year,
        sum(case when is_generic then total_drug_cost else 0 end)      as generic_cost,
        sum(case when is_generic then total_day_supply else 0 end)     as generic_day_supply,
        sum(case when not is_generic then total_drug_cost else 0 end)  as brand_cost,
        sum(case when not is_generic then total_day_supply else 0 end) as brand_day_supply
    from facts
    group by 1, 2

),

rates as (

    select
        *,
        generic_cost / nullif(generic_day_supply, 0) as generic_cost_per_day,
        brand_cost   / nullif(brand_day_supply, 0)   as brand_cost_per_day
    from by_type
    where brand_day_supply > 0
      and generic_day_supply > 0

)

select
    generic_name,
    data_year,
    round(brand_cost, 2)                                                       as brand_cost,
    brand_day_supply,
    round(generic_cost, 2)                                                     as generic_cost,
    generic_day_supply,
    round(brand_cost_per_day, 4)                                               as brand_cost_per_day,
    round(generic_cost_per_day, 4)                                             as generic_cost_per_day,
    round(100.0 * brand_day_supply / (brand_day_supply + generic_day_supply), 1) as brand_share_of_days_pct,
    round(brand_cost - brand_day_supply * generic_cost_per_day, 2)             as potential_gross_savings
from rates
