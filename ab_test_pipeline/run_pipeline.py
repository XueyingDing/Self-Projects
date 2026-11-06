"""
本地一键运行（不需要装 Airflow）：按 DAG 里的顺序依次跑三个步骤。
用法：python run_pipeline.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = str(ROOT / "data" / "warehouse.db")

for step in ["generate_events.py", "run_models.py", "analyze.py"]:
    print(f"\n========== {step} ==========")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / step), DB])
    if result.returncode != 0:
        sys.exit(f"{step} 失败，pipeline 停止")
