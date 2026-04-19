from pathlib import Path

PAIRS = [
    ("Login", "登录"), ("Register", "注册"), ("Email", "邮箱"), ("Password", "密码"),
    ("Sign in", "登录"), ("Signing in...", "登录中..."),
    ("Create account", "创建账号"), ("Creating account...", "创建中..."),
    ("Invitation Code", "邀请码"),
    ("Power-based training dashboard", "功率训练仪表盘"),
    ("Log in to connect your CLI plugin", "登录以连接 CLI 插件"),
    ("Email and password are required.", "请输入邮箱和密码。"),
    ("An unexpected error occurred.", "发生了意外错误。"),
    ("Leave blank for the first account. Required after that.", "首个账号可留空，之后必填。"),
    ("Today", "今日"), ("Training", "训练"), ("Goal", "目标"),
    ("Activities", "活动"), ("Science", "科学"), ("Settings", "设置"),
    ("Setup", "设置向导"), ("Admin", "管理"), ("Log out", "退出登录"),
    ("Theme", "主题"), ("Dark", "深色"), ("Light", "浅色"), ("System", "跟随系统"),
    ("Failed to load", "加载失败"), ("Retry", "重试"), ("Warnings", "警告"),
    ("Last Activity", "上次活动"), ("Weekly Load", "周训练负荷"),
    ("Planned Workout", "计划训练"), ("No Workout", "无训练"),
    ("Options", "选项"), ("Coming Up", "即将到来"),
    ("Target", "目标"), ("Current", "当前"),
    ("Recovery", "恢复"), ("Recovery Status", "恢复状态"),
    ("Fresh", "充分恢复"), ("Normal", "正常"), ("Fatigued", "疲劳"), ("No Data", "无数据"),
    ("Stable", "稳定"), ("Improving", "改善中"), ("Declining", "下降中"),
    ("Elevated", "升高"), ("Low", "偏低"),
    ("Sleep", "睡眠"), ("Other Signals", "其他信号"),
    ("GO", "开练"), ("EASY", "轻松"), ("MODIFY", "调整"), ("CAUTION", "注意"), ("REST", "休息"),
    ("Follow Plan", "按计划进行"), ("Go Easy", "轻松进行"),
    ("Adjust Workout", "调整训练"), ("Reduce Intensity", "降低强度"),
    ("Recovery Day", "恢复日"),
    ("Training Insights", "训练洞察"), ("Weekly Review", "周度回顾"),
    ("Training Diagnosis", "训练诊断"), ("Weekly Volume", "周里程"),
    ("Suggestions", "建议"),
    ("Training Science", "训练科学"),
    ("Load & Fitness", "负荷与体能"), ("Race Prediction", "比赛预测"),
    ("Training Zones", "训练区间"),
    ("Active", "当前使用"), ("Simple", "简要"), ("Advanced", "详细"),
    ("Use this", "使用此项"), ("References", "参考文献"), ("Zone Labels", "区间标签"),
    ("Goal Tracker", "目标追踪"), ("Change Goal", "修改目标"),
    ("Reality Check", "现实评估"), ("Assessment", "评估"), ("Milestones", "里程碑"),
    ("Current Fitness", "当前体能"), ("Fitness Trend", "体能趋势"), ("Trend", "趋势"),
    ("Comfortable", "轻松目标"), ("Stretch", "挑战目标"), ("Gap", "差距"),
    ("Rising", "上升"), ("Falling", "下降"), ("Flat", "持平"),
    ("Cancel", "取消"), ("Connect", "连接"), ("Connecting...", "连接中..."),
    ("Recommended", "推荐"), ("Syncing...", "同步中..."), ("Start sync", "开始同步"),
    ("Sync complete! Your data is ready.", "同步完成！数据已就绪。"),
    ("Data synced successfully", "数据同步成功"),
    ("Connect a platform", "连接平台"), ("Sync your data", "同步数据"),
    ("Choose training base", "选择训练基准"), ("Set a goal", "设定目标"),
    ("Set up Trainsight", "设置 Trainsight"),
    ("Previous", "上一页"), ("Next", "下一页"), ("Showing", "显示"), ("of", "共"),
    ("No activities found.", "未找到活动。"),
    ("Distance", "距离"), ("Duration", "时长"), ("Pace", "配速"), ("Elev", "爬升"),
    ("Avg Power", "平均功率"), ("Avg HR", "平均心率"),
    ("Warmup", "热身"), ("Cooldown", "放松"), ("Main", "主训练"),
    ("Run", "跑步"), ("Easy Run", "轻松跑"), ("Steady", "匀速"),
    ("Aerobic", "有氧"), ("Tempo", "节奏跑"), ("Threshold", "乳酸阈"),
    ("Rest", "休息"), ("Rep", "组"),
    ("AI Analysis", "AI 分析"), ("Findings", "发现"), ("Recommendations", "建议"),
    ("Hide details", "隐藏详情"),
    ("Zone", "区间"), ("Range", "范围"), ("Actual", "实际"),
    ("HRV Analysis", "HRV 分析"), ("Baseline", "基线"), ("7d Trend", "7天趋势"),
    ("High variability", "变异性偏高"),
    ("Language", "语言"), ("Auto", "自动"), ("Units", "单位"),
    ("Set your name", "设置您的名字"),
    ("Users", "用户"), ("Role", "角色"), ("Registered", "注册于"),
    ("Actions", "操作"), ("Generate", "生成"), ("Used", "已使用"),
    ("Available", "可用"), ("Revoked", "已撤销"), ("Revoke", "撤销"),
    ("Code", "代码"), ("Note", "备注"), ("Created", "创建时间"),
    ("Status", "状态"), ("Used By", "使用者"),
    ("Invitation Codes", "邀请码"), ("Registered accounts", "注册账号"),
    ("Manage users and invitation codes", "管理用户和邀请码"),
    ("Demo", "演示"), ("User", "用户"),
    ("you", "您"),
]

path = Path("web/src/locales/zh/messages.po")
content = path.read_text(encoding="utf-8")
count = 0
for src, tgt in PAIRS:
    esc = src.replace("\\", "\\\\").replace('"', '\\"')
    pattern = f'msgid "{esc}"\nmsgstr ""'
    replacement = f'msgid "{esc}"\nmsgstr "{tgt}"'
    if pattern in content:
        content = content.replace(pattern, replacement, 1)
        count += 1
path.write_text(content, encoding="utf-8")
print(f"Seeded {count}/{len(PAIRS)} translations")
