/*
  One row per prescriber per data year: the attributes CMS reported for that year.
  This is the input to the SCD Type 2 dimension.

  Missing specialty becomes 'UNKNOWN' (an explicit member) rather than NULL, so joins and
  group-bys never silently lose rows. If a year has conflicting attribute values (it should
  not), the row from the latest arrival wins and a warn-level test flags it.
*/
with accepted as (

    select * from {{ ref('int_part_d__accepted') }}

),

ranked as (

    select
        npi,
        data_year,
        prescriber_last_org_name,
        prescriber_first_name,
        prescriber_city,
        prescriber_state,
        coalesce(prescriber_specialty, 'UNKNOWN') as prescriber_specialty,
        row_number() over (
            partition by npi, data_year
            order by arrival_date desc, file_version desc, source_row_number
        ) as pick
    from accepted

)

select
    npi,
    data_year,
    prescriber_last_org_name,
    prescriber_first_name,
    prescriber_city,
    prescriber_state,
    prescriber_specialty,
    {{ surrogate_key(['prescriber_last_org_name', 'prescriber_first_name', 'prescriber_city',
                      'prescriber_state', 'prescriber_specialty']) }} as attribute_hash
from ranked
where pick = 1
