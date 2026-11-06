-- staging 层：清洗原始日志，一行 = 一个干净的事件
-- 1. 去重（同一个 event_id 被重复上报）
-- 2. 去掉测试账号
-- 3. 把 JSON 里的字段拆出来，统一类型

with deduped as (
    select
        *,
        row_number() over (partition by event_id order by event_ts) as rn
    from {{ source('raw_events') }}
)

select
    event_id,
    user_id,
    event_name,
    datetime(event_ts)                                   as event_ts,
    date(event_ts)                                       as event_date,
    experiment_id,
    variant,
    json_extract(properties, '$.platform')               as platform,
    cast(json_extract(properties, '$.revenue') as real)  as revenue
from deduped
where rn = 1
  and user_id not like 'test_%'
