-- One row per brand x generic product. CMS repeats the generic name in the brand column
-- for generic products, which is how is_generic is derived.
with drugs as (

    select distinct brand_name, generic_name
    from {{ ref('int_part_d__accepted') }}

)

select
    {{ surrogate_key(['brand_name', 'generic_name']) }}               as drug_sk,
    brand_name,
    generic_name,
    case when brand_name = generic_name then true else false end      as is_generic,
    case when brand_name = generic_name then 'Generic' else 'Brand' end as drug_type
from drugs

union all

select '-1', 'UNKNOWN', 'UNKNOWN', false, 'Unknown'
