"""
第 3 步：实验分析

读 mart 层的用户宽表，做三件事：
1. SRM 检查（sample ratio mismatch）：分组比例是不是真的接近 50/50。
   如果严重偏离，说明分流或埋点有 bug，后面的结果都不能信。
2. 转化率（purchased）：两比例 z 检验
3. 人均收入（revenue per user）：Welch t 检验（不假设两组方差相等）
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent


def srm_check(df, expected_share=0.5):
    counts = df["variant"].value_counts().reindex(["control", "treatment"])
    n = counts.sum()
    chi2, p = stats.chisquare(counts, [n * (1 - expected_share), n * expected_share])
    return counts, p


def two_prop_ztest(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    return p1, p2, z, 2 * (1 - stats.norm.cdf(abs(z)))


def main(db):
    df = pd.read_sql("SELECT * FROM fct_experiment_user", sqlite3.connect(db))
    c, t = df[df.variant == "control"], df[df.variant == "treatment"]
    lines = []

    counts, p_srm = srm_check(df)
    lines.append("== SRM 检查 ==")
    lines.append(f"control {counts['control']} / treatment {counts['treatment']}，p = {p_srm:.3f}")
    lines.append("通过，分组比例正常" if p_srm >= 0.001 else "未通过，先排查分流和埋点")

    p1, p2, z, p_conv = two_prop_ztest(c.purchased.sum(), len(c), t.purchased.sum(), len(t))
    lines.append("\n== 转化率（下单率）==")
    lines.append(f"control {p1:.2%} → treatment {p2:.2%}，相对提升 {(p2 / p1 - 1):+.1%}")
    lines.append(f"z = {z:.2f}，p = {p_conv:.2g}")

    tt = stats.ttest_ind(t.revenue, c.revenue, equal_var=False)  # equal_var=False 就是 Welch
    lines.append("\n== 人均收入（Welch t 检验）==")
    lines.append(f"control ${c.revenue.mean():.2f} → treatment ${t.revenue.mean():.2f}")
    lines.append(f"t = {tt.statistic:.2f}，p = {tt.pvalue:.2g}")

    report = "\n".join(lines)
    print(report)
    out = ROOT / "data" / "experiment_report.txt"
    out.write_text(report + "\n")
    print(f"\n[analyze] 报告写入 {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "warehouse.db"))
