{#- Generic test: the combination of columns is unique. Written here instead of pulling in
    the dbt_utils package so the project has zero external dependencies. -#}
{% test dbt_utils_free_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
