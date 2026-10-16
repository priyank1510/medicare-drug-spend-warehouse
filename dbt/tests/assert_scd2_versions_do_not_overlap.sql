-- Two versions of the same prescriber must never be valid in the same year,
-- otherwise the point-in-time join in fct_prescriptions would duplicate facts.
select a.npi, a.prescriber_sk as version_a, b.prescriber_sk as version_b
from {{ ref('dim_prescriber') }} as a
inner join {{ ref('dim_prescriber') }} as b
    on  a.npi = b.npi
    and a.prescriber_sk < b.prescriber_sk
    and a.valid_from_year <= b.valid_to_year
    and b.valid_from_year <= a.valid_to_year
