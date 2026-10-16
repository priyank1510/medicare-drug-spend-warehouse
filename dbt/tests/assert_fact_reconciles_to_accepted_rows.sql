-- The fact must carry exactly the accepted rows and exactly their dollars (to the cent).
with accepted as (
    select count(*) as n, round(sum(total_drug_cost), 2) as cost
    from {{ ref('int_part_d__accepted') }}
),
fact as (
    select count(*) as n, round(sum(total_drug_cost), 2) as cost
    from {{ ref('fct_prescriptions') }}
)
select a.n as accepted_rows, f.n as fact_rows, a.cost as accepted_cost, f.cost as fact_cost
from accepted as a
cross join fact as f
where a.n <> f.n
   or abs(a.cost - f.cost) > 0.01
