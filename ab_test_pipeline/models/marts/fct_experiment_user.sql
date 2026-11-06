-- mart 层：分析用的用户级宽表，一行 = 一个用户
-- 只算曝光之后发生的行为，避免把曝光前的行为错算进实验效果

with post_exposure as (
    select
        a.experiment_id,
        a.user_id,
        e.event_name,
        e.revenue
    from {{ ref('int_user_assignment') }} a
    join {{ ref('stg_events') }} e
      on e.user_id = a.user_id
     and e.experiment_id = a.experiment_id
     and e.event_ts >= a.first_exposure_ts
)

select
    a.experiment_id,
    a.user_id,
    a.variant,
    a.platform,
    a.first_exposure_ts,
    coalesce(sum(case when p.event_name = 'page_view'   then 1 end), 0) as n_page_views,
    max(case when p.event_name = 'add_to_cart' then 1 else 0 end)       as added_to_cart,
    max(case when p.event_name = 'purchase'    then 1 else 0 end)       as purchased,
    coalesce(sum(p.revenue), 0)                                         as revenue
from {{ ref('int_user_assignment') }} a
left join post_exposure p
  on p.user_id = a.user_id
 and p.experiment_id = a.experiment_id
group by a.experiment_id, a.user_id, a.variant, a.platform, a.first_exposure_ts
