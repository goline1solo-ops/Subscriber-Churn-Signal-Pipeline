-- PATTERN: a dbt model is exactly ONE SELECT statement - the whole file
-- becomes the table. That means no CREATE TABLE / DROP TABLE / multiple
-- statements like you'd use in a T-SQL script. Multi-step logic instead
-- uses CTEs (WITH ... AS (...)) chained together, all inside this one
-- statement. See GUIDE.md for the full temp-table-to-CTE mapping.

with summary_stats as (

    -- TODO: your equivalent of "averages/stddev across all rows" here,
    -- if your logic needs to compare a row against a global/group baseline.
    select
        avg(some_numeric_column)    as avg_value,
        stddev(some_numeric_column) as stddev_value
    from {{ source('staging', 'staging_events') }}

),

scored as (

    select
        e.record_id,
        e.ai_score,
        case
            when e.ai_score >= 8 then 'HIGH'
            when e.ai_score >= 4 then 'MEDIUM'
            else 'LOW'
        end as tier
    from {{ source('staging', 'staging_events') }} e
    left join summary_stats s on 1 = 1

)

select
    record_id,
    ai_score,
    tier
from scored
