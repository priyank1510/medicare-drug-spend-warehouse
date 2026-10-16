-- Which molecules drive spend, and how fast is each growing year over year?
with facts as (

    select f.data_year, d.generic_name, f.npi,
           f.total_drug_cost, f.total_claims, f.total_day_supply
    from {{ ref('fct_prescriptions') }} as f
    inner join {{ ref('dim_drug') }} as d on f.drug_sk = d.drug_sk

),

yearly as (

    select
        generic_name,
        data_year,
        sum(total_drug_cost)  as total_drug_cost,
        sum(total_claims)     as total_claims,
        sum(total_day_supply) as total_day_supply,
        count(distinct npi)   as prescriber_count
    from facts
    group by 1, 2

),

with_prior as (

    select
        *,
        lag(data_year)       over (partition by generic_name order by data_year) as prior_data_year,
        lag(total_drug_cost) over (partition by generic_name order by data_year) as prior_year_drug_cost
    from yearly

)

select
    generic_name,
    data_year,
    round(total_drug_cost, 2)                                   as total_drug_cost,
    total_claims,
    total_day_supply,
    prescriber_count,
    round(total_drug_cost / nullif(total_claims, 0), 2)         as cost_per_claim,
    round(prior_year_drug_cost, 2)                              as prior_year_drug_cost,
    -- only a true YoY when the previous row is the adjacent year
    case when prior_data_year = data_year - 1 then
        round(100.0 * (total_drug_cost - prior_year_drug_cost) / nullif(prior_year_drug_cost, 0), 1)
    end                                                         as yoy_cost_change_pct,
    rank() over (partition by data_year order by total_drug_cost desc) as spend_rank_in_year
from with_prior
