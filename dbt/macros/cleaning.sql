{#- Small, reusable cleaning rules. Defining them once means every column is cleaned the
    same way, and a rule change is a one-line, reviewable diff. -#}

{% macro clean_text(expr) -%}
    nullif(upper(trim({{ expr }})), '')
{%- endmacro %}

{#- Parses "1234.5", " 1,234.50 " and legacy "$1,234.50". Anything unparseable becomes NULL
    (and is then caught by the quality rules) instead of crashing the whole run. -#}
{% macro to_number(expr) -%}
    try_cast(nullif(replace(replace(trim({{ expr }}), '$', ''), ',', ''), '') as double)
{%- endmacro %}

{#- Deterministic surrogate key: same inputs -> same key on every rebuild. -#}
{% macro surrogate_key(columns) -%}
    md5(concat_ws('||'
    {%- for c in columns -%}
        , coalesce(cast({{ c }} as varchar), '__null__')
    {%- endfor -%}
    ))
{%- endmacro %}
