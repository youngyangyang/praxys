from pathlib import Path
PAIRS = [
    ("Weekly Load Compliance", "周负荷对比"),
    ("Sleep Score vs Power", "睡眠评分 vs 功率"),
    ("Fitness / Fatigue / Form", "体能 / 疲劳 / 状态"),
    ("Projected", "预测"),
    ("Planned", "计划"),
    ("Actual", "实际"),
    ("Sleep Score", "睡眠评分"),
    ("Avg Power", "平均功率"),
    ("Avg Power (W)", "平均功率 (W)"),
    ("CTL (Fitness)", "CTL（体能）"),
    ("ATL (Fatigue)", "ATL（疲劳）"),
    ("TSB (Form)", "TSB（状态）"),
    ("Target", "目标"),
]
path = Path("web/src/locales/zh/messages.po")
content = path.read_text(encoding="utf-8")
count = 0
for src, tgt in PAIRS:
    esc = src.replace("\\", "\\\\").replace('"', '\\"')
    p = f'msgid "{esc}"\nmsgstr ""'
    r = f'msgid "{esc}"\nmsgstr "{tgt}"'
    if p in content:
        content = content.replace(p, r, 1)
        count += 1
path.write_text(content, encoding="utf-8")
print(f"Seeded additional {count}/{len(PAIRS)}")
