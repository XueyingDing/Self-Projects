# A/B Test Mini Pipeline

一个从"埋点日志"到"实验结论"的完整小项目，用来理解自建实验分流和数据管道是怎么回事。

## 先搞懂两个概念

**埋点（tracking / instrumentation）**：在网站或 App 的代码里，在用户做关键动作的地方"埋"一段代码，动作发生时就往日志系统发一条记录。比如用户点了"加入购物车"，前端就发一条 `add_to_cart` 事件。

**日志设计（event schema design）**：决定每条事件长什么样、带哪些字段。设计不好，后面根本分析不了。这个项目里每条事件的字段：

| 字段 | 含义 | 为什么需要 |
|---|---|---|
| `event_id` | 事件唯一 ID | 用来去重，日志经常重复上报 |
| `user_id` | 用户 ID | 分流单位，也是分析单位 |
| `event_name` | 事件名 | exposure / page_view / add_to_cart / purchase |
| `event_ts` | 时间戳 | 判断行为发生在曝光前还是曝光后 |
| `experiment_id` + `variant` | 实验名和分组 | 知道这个用户在哪个实验、哪一组 |
| `properties` | JSON 附加信息 | 平台、金额等，随事件不同而不同 |

其中最关键的是 **exposure（曝光）事件**：用户真正看到实验版本的那一刻。分析只算曝光过的用户，否则会把没看到改动的人也算进来，稀释效果。

## 流程

```
埋点日志 (raw_events)
   │  scripts/generate_events.py   按 user_id 哈希分流 + 模拟事件（含重复和测试账号）
   ▼
staging      stg_events            去重、去测试账号、拆 JSON
   ▼
intermediate int_user_assignment   每个用户一行：分组、第一次曝光时间
   ▼
mart         fct_experiment_user   每个用户一行：曝光后的加购、下单、收入
   │  schema.yml                   数据质量测试（唯一、非空、取值范围、一人只在一组）
   ▼
scripts/analyze.py                 SRM 检查 → 转化率 z 检验 → 人均收入 Welch t 检验
```

`dags/ab_test_pipeline_dag.py` 是 Airflow 版本：把上面三步写成三个 task，每天早上 6 点自动跑，前一步失败后面就不跑。

## 每个文件是干嘛的

| 文件 | 作用 |
|---|---|
| `scripts/generate_events.py` | 模拟埋点日志。`assign_variant` 用 `hash(实验ID:用户ID)` 给用户分组，然后生成曝光、浏览、加购、下单事件，写进 `raw_events` 表 |
| `models/staging/stg_events.sql` | 清洗原始日志：按 `event_id` 去重、去掉测试账号、把 JSON 里的平台和金额拆成列 |
| `models/intermediate/int_user_assignment.sql` | 每个曝光过的用户一行：所在分组、第一次曝光时间、出现在几个组里（正常是 1） |
| `models/marts/fct_experiment_user.sql` | 分析用的宽表：每个用户曝光之后有没有加购、有没有下单、花了多少钱 |
| `models/schema.yml` | 数据质量测试：主键唯一、非空、分组取值合法、一个人只能在一组 |
| `scripts/run_models.py` | 迷你版 dbt：按依赖顺序把上面的 SQL 建成表，再跑 `schema.yml` 里的测试，测试失败就停止 |
| `scripts/analyze.py` | 实验分析：SRM 检查、下单率 z 检验、人均收入 Welch t 检验，结果写进 `data/experiment_report.txt` |
| `dags/ab_test_pipeline_dag.py` | Airflow DAG：把三个步骤串成每天自动跑的流程（需要装 Airflow） |
| `run_pipeline.py` | 不用 Airflow 的本地一键运行，按同样顺序跑三个步骤 |
| `data/experiment_report.txt` | 跑一遍之后生成的实验结论示例 |

## 怎么跑

```bash
python run_pipeline.py
```

只需要 Python、pandas、scipy、pyyaml。`scripts/run_models.py` 是一个迷你版 dbt：解析 `{{ ref() }}`、按依赖排序建表、跑 schema 测试。换成真实 dbt 的话，把 models/ 放进 dbt 项目，用 `dbt run && dbt test` 即可，SQL 基本不用改。

## 面试时可以怎么讲

- **分流**：用 `hash(experiment_id + user_id)` 决定分组，同一个人永远在同一组；不同实验用不同的 experiment_id，分组互相独立
- **数据质量**：日志去重、排除测试账号、只算曝光后的行为、测试保证一人只在一组
- **先查 SRM**：分组比例不对，说明分流或埋点有 bug，结果不能用
- **指标选检验**：比例指标用 z 检验，收入这类右偏、方差可能不等的指标用 Welch t 检验
