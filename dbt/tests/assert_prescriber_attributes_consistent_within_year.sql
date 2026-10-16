{{ config(severity = 'warn') }}
-- CMS reports one set of attributes per prescriber per year. If a file disagrees with
-- itself we still build (latest arrival wins) but surface a warning.
select npi, data_year, count(distinct
    coalesce(prescriber_city, '') || '|' || coalesce(prescriber_state, '') || '|' ||
    coalesce(prescriber_specialty, '')) as attribute_variants
from {{ ref('int_part_d__accepted') }}
group by npi, data_year
having count(distinct
    coalesce(prescriber_city, '') || '|' || coalesce(prescriber_state, '') || '|' ||
    coalesce(prescriber_specialty, '')) > 1
