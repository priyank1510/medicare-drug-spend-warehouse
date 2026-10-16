-- Every accepted row comes from a prescriber-year that built a dimension version, so an
-- unknown-member hit here means the SCD2 ranges have a hole.
select prescription_id, npi, data_year
from {{ ref('fct_prescriptions') }}
where prescriber_sk = '-1'
