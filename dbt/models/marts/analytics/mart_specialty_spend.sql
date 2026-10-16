-- Spend by prescriber specialty, using the specialty that was valid IN THAT YEAR (SCD2).
with facts as (

    select f.data_year, p.prescriber_specialty, f.npi, f.total_drug_cost, f.total_claims
    from {{ ref('fct_prescriptions') }} as f
    inner join {{ ref('dim_prescriber') }} as p on f.prescriber_sk = p.prescriber_sk

),

yearly as (

    select
        prescriber_specialty,
        data_year,
        count(distinct npi)  as prescriber_count,
        sum(total_drug_cost) as total_drug_cost,
        sum(total_claims)    as total_claims
    from facts
    group by 1, 2

),

year_totals as (

    select data_year, sum(total_drug_cost) as year_drug_cost
    from yearly
    group by 1

)

select
    y.prescriber_specialty,
    y.data_year,
    y.prescriber_count,
    round(y.total_drug_cost, 2)                                    as total_drug_cost,
    y.total_claims,
    round(y.total_drug_cost / nullif(y.prescriber_count, 0), 2)    as cost_per_prescriber,
    round(100.0 * y.total_drug_cost / nullif(t.year_drug_cost, 0), 2) as share_of_year_spend_pct
from yearly as y
inner join year_totals as t on y.data_year = t.data_year
