-- Transforms staging_subscriber_events into a clean subscriber-risk table.
--
-- TODO (see churn_signal_pipeline_project.md, step 5):
--   - compute days_since_last_login from last_login_date
--   - bucket churn_score into risk_tier (low/medium/high)
--   - flag at_risk_priority where risk_tier = 'high' AND days_since_last_login > 14

select
    subscriber_id,
    signup_date,
    plan_tier,
    last_login_date,
    churn_score,
    sentiment
from {{ source('staging', 'staging_subscriber_events') }}
