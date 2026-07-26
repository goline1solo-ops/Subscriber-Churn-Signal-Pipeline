-- Transforms staging_subscriber_events into a clean subscriber-risk table.
-- Thresholds are a known first pass - churn_score currently skews heavily
-- toward 8-9 (root cause: _generate_ticket_text()'s is_frustrated condition
-- is too loose for this dataset's real averages). Revisit later.

with avg_for_all_custs as (

    select
        avg(payment_failures)    as avg_payment_failures_ac,
        stddev(payment_failures) as stddev_payment_failures_ac,
        avg(support_tickets)     as avg_support_tickets_ac,
        stddev(support_tickets)  as stddev_support_tickets_ac
    from {{ source('staging', 'staging_subscriber_events') }}

),

subs_risk_tier as (

    select
        sse.subscriber_id,
        sse.last_login_days_ago,
        case
            when sse.tenure_months < 1 then 'LOW'
            when sse.churn_score >= 8
                 or (sse.payment_failures - ac.avg_payment_failures_ac) / nullif(ac.stddev_payment_failures_ac, 0) >= 2
                 or (sse.support_tickets - ac.avg_support_tickets_ac) / nullif(ac.stddev_support_tickets_ac, 0) >= 2
                 then 'HIGH'
            when sse.churn_score >= 4
                 or (sse.payment_failures - ac.avg_payment_failures_ac) / nullif(ac.stddev_payment_failures_ac, 0) >= 1
                 or (sse.support_tickets - ac.avg_support_tickets_ac) / nullif(ac.stddev_support_tickets_ac, 0) >= 1
                 then 'MEDIUM'
            else 'LOW'
        end as risk_tier
    from {{ source('staging', 'staging_subscriber_events') }} sse
    left join avg_for_all_custs ac on 1 = 1

)

select
    subscriber_id,
    risk_tier,
    (risk_tier = 'HIGH' and last_login_days_ago > 14) as at_risk_priority
from subs_risk_tier
