/*
  Silver layer. One output row per raw row: nothing is silently dropped.

  Every row gets exactly one row_status, decided in this order:
    1. exact_duplicate  - byte-identical copy of an earlier row in the same file
    2. superseded       - a later file version restated this prescriber x drug x year
                          (late-arriving correction wins: highest file_version, then latest arrival)
    3. quarantined      - fails a row-level quality rule; dq_issue says which
    4. accepted         - flows to the star schema

  Downstream models filter on row_status; the quality models report on it.
*/

with source as (

    select * from {{ source('raw', 'part_d_prescriber_drug') }}

),

typed as (

    select
        trim(prscrbr_npi)                           as npi,
        {{ clean_text('prscrbr_last_org_name') }}   as prescriber_last_org_name,
        {{ clean_text('prscrbr_first_name') }}      as prescriber_first_name,
        {{ clean_text('prscrbr_city') }}            as prescriber_city,
        {{ clean_text('prscrbr_state_abrvtn') }}    as prescriber_state,
        {{ clean_text('prscrbr_type') }}            as prescriber_specialty,
        {{ clean_text('brnd_name') }}               as brand_name,
        {{ clean_text('gnrc_name') }}               as generic_name,
        {{ to_number('tot_clms') }}                 as total_claims,
        {{ to_number('tot_30day_fills') }}          as total_30day_fills,
        {{ to_number('tot_day_suply') }}            as total_day_supply,
        {{ to_number('tot_drug_cst') }}             as total_drug_cost,
        {{ to_number('tot_benes') }}                as total_beneficiaries,
        nullif(trim(ge65_sprsn_flag), '')           as ge65_suppression_flag,
        cast(_data_year as integer)                 as data_year,
        cast(_file_version as integer)              as file_version,
        cast(_row_number as integer)                as source_row_number,
        _batch_id                                   as batch_id,
        _source_file                                as source_file,
        _arrival_date                               as arrival_date,
        _row_hash                                   as row_hash,
        _schema_fingerprint                         as schema_fingerprint,
        _loaded_at                                  as loaded_at
    from source

),

exact_copies as (

    select
        *,
        row_number() over (
            partition by batch_id, row_hash
            order by source_row_number
        ) as exact_copy_rank
    from typed

),

versions as (

    select
        *,
        -- rank versions only among first copies (the last partition term keeps
        -- exact duplicates out of the race)
        row_number() over (
            partition by npi, brand_name, generic_name, data_year,
                         case when exact_copy_rank = 1 then 1 else 0 end
            order by file_version desc, arrival_date desc, source_row_number
        ) as version_rank
    from exact_copies

),

quality as (

    select
        *,
        case
            when npi is null or not regexp_matches(npi, '^[0-9]{10}$')        then 'invalid_npi'
            when brand_name is null or generic_name is null                   then 'missing_drug_name'
            when total_claims is null or total_day_supply is null             then 'missing_measure'
            when total_drug_cost is null                                      then 'missing_drug_cost'
            when total_claims < 0 or total_day_supply < 0
              or total_drug_cost < 0 or total_30day_fills < 0                 then 'negative_measure'
        end as dq_rule_failed
    from versions

)

select
    {{ surrogate_key(['batch_id', 'source_row_number']) }} as raw_row_id,
    npi,
    prescriber_last_org_name,
    prescriber_first_name,
    prescriber_city,
    prescriber_state,
    prescriber_specialty,
    brand_name,
    generic_name,
    data_year,
    total_claims,
    total_30day_fills,
    total_day_supply,
    total_drug_cost,
    total_beneficiaries,
    case when total_beneficiaries is null then true else false end as is_beneficiary_count_suppressed,
    ge65_suppression_flag,
    case
        when exact_copy_rank > 1         then 'exact_duplicate'
        when version_rank > 1            then 'superseded'
        when dq_rule_failed is not null  then 'quarantined'
        else 'accepted'
    end as row_status,
    case
        when exact_copy_rank = 1 and version_rank = 1 then dq_rule_failed
    end as dq_issue,
    file_version,
    batch_id,
    source_file,
    arrival_date,
    source_row_number,
    row_hash,
    schema_fingerprint,
    loaded_at
from quality
