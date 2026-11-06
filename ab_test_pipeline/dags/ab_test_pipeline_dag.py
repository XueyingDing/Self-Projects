"""
第 4 步：用 Airflow 把整条 pipeline 串起来，每天自动跑

Airflow 的核心概念：
- DAG：一整条流程（有向无环图），定义什么时候跑、按什么顺序跑
- Task：流程里的一个步骤
- >>：表示依赖关系，前一个成功了才跑下一个

真实项目里，第一步一般不是"生成数据"，而是检查/加载前一天的原始日志，
dbt 那步会写成 `dbt run` 和 `dbt test`。

这个文件需要装了 Airflow 才能跑（pip install apache-airflow），
放进 Airflow 的 dags/ 目录，它就会出现在 Airflow 网页界面上。
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/ab_test_pipeline"
DB = f"{PROJECT}/data/warehouse.db"

default_args = {
    "owner": "analytics",
    "retries": 1,                         # 失败自动重试一次
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="ab_test_checkout_button_v2",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="0 6 * * *",                 # 每天早上 6 点跑
    catchup=False,
    tags=["experimentation"],
) as dag:

    load_raw_events = BashOperator(
        task_id="load_raw_events",
        bash_command=f"python {PROJECT}/scripts/generate_events.py {DB}",
    )

    dbt_run = BashOperator(
        task_id="dbt_run_and_test",
        # 真实 dbt 项目里这里写：cd {PROJECT} && dbt run && dbt test
        bash_command=f"python {PROJECT}/scripts/run_models.py {DB}",
    )

    analyze = BashOperator(
        task_id="analyze_experiment",
        bash_command=f"python {PROJECT}/scripts/analyze.py {DB}",
    )

    load_raw_events >> dbt_run >> analyze
