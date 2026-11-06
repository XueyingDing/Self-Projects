"""
第 2 步：一个迷你版的 `dbt run` + `dbt test`

真实项目里直接装 dbt（pip install dbt-duckdb / dbt-snowflake 等），
然后在项目目录下跑 `dbt run` 和 `dbt test` 就行。
这个脚本模仿 dbt 做的三件事，方便你看清楚 dbt 背后在干什么：

1. 读 models/ 下的 .sql 文件，把 {{ ref('xxx') }} 和 {{ source('xxx') }} 换成真实表名
2. 根据 ref 依赖关系自动排出执行顺序（staging → intermediate → mart）
3. 每个模型建成一张表，然后按 schema.yml 跑数据质量测试
"""
import re
import sqlite3
import sys
from graphlib import TopologicalSorter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
REF_RE = re.compile(r"\{\{\s*ref\('([\w]+)'\)\s*\}\}")
SRC_RE = re.compile(r"\{\{\s*source\('([\w]+)'\)\s*\}\}")


def load_models():
    models = {}
    for path in MODELS_DIR.rglob("*.sql"):
        sql = path.read_text()
        models[path.stem] = {"sql": sql, "deps": set(REF_RE.findall(sql)), "layer": path.parent.name}
    return models


def compile_sql(sql):
    sql = REF_RE.sub(lambda m: m.group(1), sql)
    return SRC_RE.sub(lambda m: m.group(1), sql)


def run(con, models):
    order = list(TopologicalSorter({k: v["deps"] for k, v in models.items()}).static_order())
    for name in order:
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(f"CREATE TABLE {name} AS {compile_sql(models[name]['sql'])}")
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"[dbt run]  {models[name]['layer']:<13} {name:<22} {n:>7} 行")
    con.commit()


def test_sql(model, col, test):
    if test == "unique":
        return f"SELECT {col} FROM {model} GROUP BY {col} HAVING COUNT(*) > 1"
    if test == "not_null":
        return f"SELECT * FROM {model} WHERE {col} IS NULL"
    if isinstance(test, dict) and "accepted_values" in test:
        vals = ", ".join(repr(v) for v in test["accepted_values"]["values"])
        return f"SELECT * FROM {model} WHERE {col} NOT IN ({vals})"
    raise ValueError(f"unknown test {test}")


def run_tests(con):
    spec = yaml.safe_load((MODELS_DIR / "schema.yml").read_text())
    failures = 0
    for m in spec["models"]:
        for c in m["columns"]:
            for t in c["tests"]:
                label = t if isinstance(t, str) else "accepted_values"
                bad = con.execute(f"SELECT COUNT(*) FROM ({test_sql(m['name'], c['name'], t)})").fetchone()[0]
                status = "PASS" if bad == 0 else f"FAIL ({bad} 行)"
                failures += bad > 0
                print(f"[dbt test] {m['name']}.{c['name']:<12} {label:<16} {status}")
    if failures:
        sys.exit(f"{failures} 个测试失败，pipeline 停止")


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "warehouse.db")
    con = sqlite3.connect(db)
    run(con, load_models())
    run_tests(con)
    con.close()
