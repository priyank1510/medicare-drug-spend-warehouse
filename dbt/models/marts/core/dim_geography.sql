select
    state_code,
    state_name,
    census_region
from {{ ref('state_reference') }}

union all

select 'UNK', 'Unknown', 'Unknown'
