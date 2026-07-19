"""数据迁移脚本：将旧版本数据库迁移到规则组架构

用法：
    python migrate_to_rules.py

功能：
    1. 创建 rule_groups / rules 表
    2. 为 videos 表添加 rule_group_id 列
    3. 创建"默认"规则组（含一条定长规则）
    4. 将所有旧视频绑定到默认组
    5. 可选：将旧 config 表中的 interval 值同步到默认规则
"""

import sqlite3
import sys
from datetime import datetime

DB_PATH = "monitor.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")

    print("=".ljust(50, "="))
    print("  规则组架构迁移脚本")
    print("=".ljust(50, "="))
    print()

    # 1. 创建新表
    print("[1/4] 创建 rule_groups / rules 表 ...", end=" ")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rule_groups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rules (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id   INTEGER NOT NULL REFERENCES rule_groups(id) ON DELETE CASCADE,
            rule_type  INTEGER NOT NULL,
            value      TEXT NOT NULL,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    print("OK")

    # 2. 为 videos 表添加 rule_group_id 列
    print("[2/4] 添加 videos.rule_group_id 列 ...", end=" ")
    try:
        conn.execute(
            "ALTER TABLE videos ADD COLUMN rule_group_id INTEGER REFERENCES rule_groups(id)"
        )
        conn.commit()
        print("OK（新增）")
    except sqlite3.OperationalError:
        print("OK（已存在）")

    # 3. 创建默认规则组
    print("[3/4] 创建默认规则组 ...", end=" ")
    existing = conn.execute("SELECT COUNT(*) FROM rule_groups").fetchone()[0]
    if existing == 0:
        # 尝试读取旧的 interval 配置
        old_interval = 60
        try:
            row = conn.execute("SELECT value FROM config WHERE key='interval'").fetchone()
            if row:
                old_interval = int(row["value"])
        except Exception:
            pass

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO rule_groups (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("默认", now, now),
        )
        gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO rules (group_id, rule_type, value, position, created_at) VALUES (?, ?, ?, ?, ?)",
            (gid, 1, f'{{"interval": {old_interval}}}', 0, now),
        )
        conn.commit()
        print(f"OK（创建组 id={gid}，定长 {old_interval}s）")
    else:
        # 默认组已存在（可能 init_db 已创建），找到它
        gid = conn.execute("SELECT id FROM rule_groups ORDER BY id LIMIT 1").fetchone()["id"]
        print(f"OK（已存在，组 id={gid}）")

    # 4. 将旧视频绑定到默认组
    print("[4/4] 迁移现有视频 ...", end=" ")
    null_count = conn.execute(
        "SELECT COUNT(*) FROM videos WHERE rule_group_id IS NULL"
    ).fetchone()[0]
    if null_count > 0:
        conn.execute(
            "UPDATE videos SET rule_group_id=? WHERE rule_group_id IS NULL",
            (gid,),
        )
        conn.commit()
        print(f"OK（已绑定 {null_count} 个视频到默认组）")
    else:
        print("OK（无需迁移）")

    conn.close()

    print()
    print("=".ljust(50, "="))
    print("  迁移完成！")
    print("=".ljust(50, "="))

    # 验证
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    v_total = conn2.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    v_bound = conn2.execute(
        "SELECT COUNT(*) FROM videos WHERE rule_group_id IS NOT NULL"
    ).fetchone()[0]
    g_total = conn2.execute("SELECT COUNT(*) FROM rule_groups").fetchone()[0]
    r_total = conn2.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    conn2.close()

    print(f"  视频总数: {v_total}  已绑定: {v_bound}")
    print(f"  规则组数: {g_total}  规则数: {r_total}")
    print()


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n迁移失败: {e}", file=sys.stderr)
        sys.exit(1)
