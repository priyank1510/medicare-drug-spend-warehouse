select npi, sum(case when is_current then 1 else 0 end) as current_versions
from {{ ref('dim_prescriber') }}
group by npi
having sum(case when is_current then 1 else 0 end) <> 1
