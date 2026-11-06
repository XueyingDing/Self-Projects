# Self-Projects

个人练习项目合集，每个文件夹是一个独立的项目，里面有各自的 README 说明怎么运行。

| 项目 | 简介 | 用到的技术 |
|---|---|---|
| [ab_test_pipeline](./ab_test_pipeline) | 从埋点日志到实验结论的完整 A/B 测试数据管道：按用户哈希分流、分层建模清洗数据、数据质量测试、SRM 检查和显著性检验，最后用 Airflow 每天自动运行 | Python, SQL, dbt 风格分层建模, Airflow, pandas, scipy |
