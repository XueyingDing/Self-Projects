"""
第 1 步：模拟埋点日志（tracking events）

真实场景里，这些事件由网站/App 前端或后端发出，写进日志系统
（比如 Kafka → S3 / 数据仓库的原始表）。这里用 Python 模拟同样的结构。

关键点：
1. 分流（traffic split）用 user_id 做哈希，保证同一个用户永远进同一组。
2. 每个事件都带上 event_id、user_id、event_name、event_ts、experiment_id、variant、properties。
"""
import hashlib
import json
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

EXPERIMENT_ID = "checkout_button_v2"
N_USERS = 20000
SEED = 42
START = datetime(2026, 10, 1)
DAYS = 14

# 真实效果：treatment 的下单率更高一点
BASE_RATES = {
    "control":   {"add_to_cart": 0.30, "purchase_given_cart": 0.35},
    "treatment": {"add_to_cart": 0.30, "purchase_given_cart": 0.39},
}


def assign_variant(user_id: str, experiment_id: str, treatment_share: float = 0.5) -> str:
    """哈希分流：同一个 user + 同一个实验，结果永远一样。

    把 "实验ID:用户ID" 做 md5，取前 8 位转成整数，映射到 0~1 之间。
    小于 treatment_share 进 treatment，否则进 control。
    把 experiment_id 放进哈希里，是为了不同实验之间的分组互相独立。
    """
    key = f"{experiment_id}:{user_id}".encode()
    bucket = int(hashlib.md5(key).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "treatment" if bucket < treatment_share else "control"


def make_event(user_id, name, ts, variant, props=None):
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": user_id,
        "event_name": name,
        "event_ts": ts.isoformat(timespec="seconds"),
        "experiment_id": EXPERIMENT_ID,
        "variant": variant,
        "properties": json.dumps(props or {}),
    }


def simulate(n_users=N_USERS, seed=SEED):
    rng = random.Random(seed)
    events = []
    for i in range(n_users):
        user_id = f"u{i:06d}"
        variant = assign_variant(user_id, EXPERIMENT_ID)
        rates = BASE_RATES[variant]

        # 用户第一次进入实验的时间
        t = START + timedelta(seconds=rng.randint(0, DAYS * 86400 - 3600))
        platform = rng.choice(["web", "ios", "android"])

        # exposure：用户真正"看到"了实验版本，这是分析的入口事件
        events.append(make_event(user_id, "experiment_exposure", t, variant, {"platform": platform}))

        # 看商品页
        for _ in range(rng.randint(1, 4)):
            t += timedelta(seconds=rng.randint(10, 300))
            events.append(make_event(user_id, "page_view", t, variant, {"page": "product"}))

        # 加购
        if rng.random() < rates["add_to_cart"]:
            t += timedelta(seconds=rng.randint(10, 600))
            events.append(make_event(user_id, "add_to_cart", t, variant))

            # 下单
            if rng.random() < rates["purchase_given_cart"]:
                t += timedelta(seconds=rng.randint(30, 900))
                revenue = round(rng.lognormvariate(4.0, 0.6), 2)  # 金额右偏，更接近真实
                events.append(make_event(user_id, "purchase", t, variant, {"revenue": revenue}))

    # 模拟真实日志里的脏数据：重复上报 + 测试账号
    dupes = rng.sample(events, 200)
    events.extend(dict(e) for e in dupes)  # 同一个 event_id 出现两次
    for j in range(30):
        events.append(make_event(f"test_{j}", "page_view", START, "control", {"page": "product"}))

    rng.shuffle(events)  # 日志到达顺序是乱的
    return events


def main(db_path):
    events = simulate()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("DROP TABLE IF EXISTS raw_events")
    con.execute("""
        CREATE TABLE raw_events (
            event_id TEXT, user_id TEXT, event_name TEXT, event_ts TEXT,
            experiment_id TEXT, variant TEXT, properties TEXT
        )
    """)
    con.executemany(
        "INSERT INTO raw_events VALUES (:event_id,:user_id,:event_name,:event_ts,:experiment_id,:variant,:properties)",
        events,
    )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    con.close()
    print(f"[generate_events] 写入 raw_events {n} 行 -> {db_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/warehouse.db")
