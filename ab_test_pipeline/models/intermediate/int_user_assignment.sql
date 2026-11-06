-- intermediate 层：每个用户在这个实验里的分组和第一次曝光时间
-- 一行 = 一个用户
-- 只统计"真正被曝光"的用户，没看到实验版本的人不算进分析

select
    experiment_id,
    user_id,
    min(variant)   as variant,
    count(distinct variant) as n_variants,  -- 正常应该是 1，>1 说明分流有问题
    min(event_ts)  as first_exposure_ts,
    min(platform)  as platform
from {{ ref('stg_events') }}
where event_name = 'experiment_exposure'
group by experiment_id, user_id
