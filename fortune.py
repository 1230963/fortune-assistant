#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日运势 · 桌面算命小助手

一个悬浮在桌面上的每日运势小挂件：
  - 每日签文（上上签 / 上吉 / 中吉 / 小吉 / 平签）
  - 综合 / 爱情 / 事业 / 财运 星级运势
  - 今日宜忌、幸运色、幸运数字、吉利方位、贵人星座
  - 每日小贴士、本命星座运势（可设置）
  - 拖动标题栏移动，右键打开菜单，跨天自动刷新

同一天内运势是固定的（按日期生成），点「再求一签」可重新求签。
直接运行 `python3 fortune.py --print` 可在终端查看今日运势。
"""
import datetime
import fcntl
import json
import os
import random
import subprocess
import sys

APP_NAME = "每日运势"
CONFIG_PATH = os.path.expanduser("~/.fortune_assistant.json")
LOCK_PATH = os.path.expanduser("~/.fortune_assistant.lock")
AGENT_LABEL = "com.zcode.fortune-assistant"
AGENT_PLIST = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % AGENT_LABEL)
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PNG = os.path.join(HERE, "icon_1024.png")

# ---------------------------------------------------------------- 历法

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ZODIAC = "鼠牛虎兔龙蛇马羊猴鸡狗猪"
WEEKDAYS = "一二三四五六日"

# 春节（正月初一）日期，用于干支年 / 生肖切换
CNY = {
    2015: (2, 19), 2016: (2, 8), 2017: (1, 28), 2018: (2, 16),
    2019: (2, 5), 2020: (1, 25), 2021: (2, 12), 2022: (2, 1),
    2023: (1, 22), 2024: (2, 10), 2025: (1, 29), 2026: (2, 17),
    2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3),
    2031: (1, 23), 2032: (2, 11), 2033: (1, 31), 2034: (2, 19),
    2035: (2, 8),
}

def ganzhi_day(d):
    """1949-10-01 为甲子日，依次推排。"""
    n = (d - datetime.date(1949, 10, 1)).days
    return STEMS[n % 10] + BRANCHES[n % 12]

def ganzhi_year(d):
    """1984 为甲子年；春节之前仍属上一年。"""
    y = d.year
    m, dd = CNY.get(y, (2, 4))
    if (d.month, d.day) < (m, dd):
        y -= 1
    n = (y - 1984) % 60
    return STEMS[n % 10] + BRANCHES[n % 12], ZODIAC[n % 12]

CN_DIG = "零一二三四五六七八九"

def cn_num(n):
    if n < 10:
        return CN_DIG[n]
    if n < 20:
        return "十" + (CN_DIG[n % 10] if n % 10 else "")
    t, o = divmod(n, 10)
    return CN_DIG[t] + "十" + (CN_DIG[o] if o else "")

# ---------------------------------------------------------------- 五行

STEM_EL = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
BR_EL = dict(zip("寅卯巳午申酉亥子辰戌丑未", "木木火火金金水水土土土土"))
NAYIN = ["海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火", "涧下水", "城头土",
         "白蜡金", "杨柳木", "泉中水", "屋上土", "霹雳火", "松柏木", "长流水", "沙中金",
         "山下火", "平地木", "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
         "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水"]
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 我生
EL_DIR = {"木": "正东", "火": "正南", "金": "正西", "水": "正北", "土": "东北/西南"}

def year_gz_index(d):
    y = d.year
    m, dd = CNY.get(y, (2, 4))
    if (d.month, d.day) < (m, dd):
        y -= 1
    return (y - 1984) % 60

def wuxing_today(d):
    """日主五行、纳音、能量分布、喜用、冲煞。"""
    day_idx = (d - datetime.date(1949, 10, 1)).days % 60
    yidx = year_gz_index(d)
    day_gz = ganzhi_day(d)
    year_gz = STEMS[yidx % 10] + BRANCHES[yidx % 12]
    day_el = STEM_EL[day_gz[0]]
    day_nayin = NAYIN[day_idx // 2]
    votes = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for e in (STEM_EL[year_gz[0]], BR_EL[year_gz[1]], STEM_EL[day_gz[0]],
              BR_EL[day_gz[1]], day_nayin[-1]):
        votes[e] += 1
    strong = votes[day_el] >= 2
    sheng_wo = [e for e in "木火土金水" if SHENG[e] == day_el][0]
    xiyong = SHENG[day_el] if strong else sheng_wo
    bi = BRANCHES.index(day_gz[1])
    chong = BRANCHES[(bi + 6) % 12]
    return {
        "day_gz": day_gz, "year_gz": year_gz, "day_el": day_el,
        "nayin": day_nayin, "votes": votes, "strong": strong,
        "xiyong": xiyong, "chong_branch": chong, "chong_zodiac": ZODIAC[(bi + 6) % 12],
    }

# ---------------------------------------------------------------- 签文库

LEVELS = ["上上签", "上吉", "中吉", "小吉", "平签"]
LEVEL_W = [10, 22, 30, 24, 14]
STAR_RANGE = {"上上签": (4, 5), "上吉": (3, 5), "中吉": (2, 5), "小吉": (2, 4), "平签": (1, 3)}

POEMS = {
    "上上签": [
        "云开见月明，诸事皆顺遂。\n今日所求之事，十有八九能成。",
        "东风送暖百花开，贵人迎面来。\n大胆去做吧，连老天都在帮你。",
        "锦鲤跃龙门，好运正当时。\n适合许愿，今天特别灵。",
        "山重水复疑无路，柳暗花明又一村。\n困扰已久的事，今日迎来转机。",
        "紫气东来，财星高照。\n宜谈合作、做决断、定大事。",
        "一帆风顺吉星到，万事如意福临门。\n今天，你就是主角。",
    ],
    "上吉": [
        "春水初生，万物向暖。\n稳步前行，自有收获。",
        "贵人运在线。\n开口求助不丢人，还很赚。",
        "小财不断，大财可期。\n钱包今天对你很友好。",
        "桃花微绽，春意萌动。\n心动不如行动。",
        "思路清奇，灵感迸发。\n适合创作、提案、开脑洞。",
        "旧友带来新机会。\n记得回消息，别已读不回。",
    ],
    "中吉": [
        "平平淡淡才是真。\n小确幸藏在今天的细节里。",
        "稳中有升，急不得。\n慢工出细活。",
        "付出七分，收获六分。\n剩下一分，明天补上。",
        "宜守不宜攻。\n把手头的事做漂亮就是胜利。",
        "心情是自己的。\n别为别人的坏情绪买单。",
        "小波折只是调味剂。\n跨过去，前面是坦途。",
    ],
    "小吉": [
        "多云转晴，先抑后扬。\n上午苟住，下午发力。",
        "无功无过，亦是修行。\n今天适合养精蓄锐。",
        "小幸运会迟到，但不会缺席。\n留心身边的小消息。",
        "慢一点没关系。\n别停下来就行。",
        "适合囤货的一天：\n囤快乐、囤零食、囤好觉。",
        "机会在敲门，只是敲得轻。\n竖起耳朵听。",
    ],
    "平签": [
        "躺平也是一种修行。\n今天，请原谅不完美的自己。",
        "水逆退散咒：\n多喝水，早睡觉，少抬杠。",
        "平平无奇的一天，\n也是宇宙限量发行的一天。",
        "宜降低期待。\n惊喜会自己找上门。",
        "摸鱼不可耻，而且有用。\n但别摸一整天。",
        "今天的烦恼，\n睡一觉就能解决一半。",
    ],
}

YI_POOL = [
    "喝奶茶", "摸鱼", "早睡早起", "发朋友圈", "给爸妈打电话", "表白",
    "存钱", "整理桌面", "学点新东西", "出门走走", "运动出汗", "吃火锅",
    "看星星", "买张彩票", "断舍离", "穿红色", "听歌摇摆", "夸同事",
    "撸猫", "给花浇水", "写日记", "泡泡脚", "敷面膜", "大扫除",
    "约朋友吃饭", "主动搭话", "晒太阳", "读书半小时", "备份文件",
    "清理相册", "多吃水果", "对镜子微笑", "记账", "做计划", "逛公园",
    "换个新头像", "收藏好运", "早一站下车走走",
]

JI_POOL = [
    "熬夜", "冲动消费", "跟人抬杠", "立flag", "吃瓜上头", "久坐不动",
    "空腹喝冰饮", "赖床到中午", "翻旧账", "深夜emo", "暴饮暴食",
    "翘班", "借钱给人", "背后议论人", "刷手机到半夜", "拖延症发作",
    "连点三顿外卖", "和杠精讲道理", "乱发脾气", "轻信小道消息",
    "出门不带伞", "忘带钥匙", "碰运气赌博", "过度脑补", "深夜回工作消息",
    "喝第三杯奶茶", "冲动剪头发", "删聊天记录", "翻前任动态",
    "买用不上的平替", "开盲盒", "充用不上的会员", "跟人比惨",
    "深夜做重大决定", "忘记吃饭", "憋尿赶工",
]

COLORS = [
    ("正红", "#D64541"), ("明黄", "#E9C46A"), ("天青", "#7FB3D5"),
    ("月白", "#EFEBE0"), ("黛蓝", "#34495E"), ("绯红", "#E74C3C"),
    ("竹青", "#52BE80"), ("杏色", "#F5CBA7"), ("藕荷", "#BB8FCE"),
    ("墨色", "#2C3E50"), ("珊瑚橙", "#FF7F50"), ("薄荷绿", "#98D8C8"),
    ("奶茶棕", "#C8A27A"), ("樱花粉", "#F4A7B9"), ("锦鲤红", "#EE4C2B"),
    ("星空蓝", "#5D6D7E"), ("香芋紫", "#D7BDE2"), ("鹅黄", "#F7DC6F"),
]

DIRECTIONS = ["正东", "正南", "正西", "正北", "东南", "东北", "西南", "西北"]

SIGNS = ["白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
         "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座"]

SIGN_TRAITS = {
    "白羊座": ["冲劲十足", "火力全开", "有点坐不住"],
    "金牛座": ["稳重在线", "对美食毫无抵抗力", "财运嗅觉灵敏"],
    "双子座": ["话痨模式开启", "灵感噼里啪啦", "一心二用也游刃有余"],
    "巨蟹座": ["情绪细腻", "恋家指数上升", "直觉格外准"],
    "狮子座": ["气场两米八", "自信放光芒", "特别想被夸夸"],
    "处女座": ["细节控上线", "效率拉满", "看什么都想改两笔"],
    "天秤座": ["选择困难症发作", "人缘爆棚", "审美在线"],
    "天蝎座": ["洞察力拉满", "神秘感十足", "直觉准得吓人"],
    "射手座": ["心已经飞出去了", "运气偏好", "说话有点直"],
    "摩羯座": ["事业心拉满", "稳如泰山", "在悄悄努力惊艳所有人"],
    "水瓶座": ["脑洞清奇", "有点想独处", "忽而emo忽而快乐"],
    "双鱼座": ["浪漫细胞活跃", "容易心软", "白日梦含量偏高"],
}

ADVICE = [
    "重要决定放在上午做", "先听完别人说话再拍板", "别为小事内耗",
    "想到就去做，别拖", "多喝水，少熬夜", "花钱之前三思",
    "适合主动联系在意的人", "把大目标拆成小步骤", "远离消耗你的人和事",
    "好心情要自己给自己", "凡事留一手，别太满", "抬头看看天，颈椎会感谢你",
]

TIPS = [
    "在电脑前坐久了，起来倒杯水，顺便看看窗外。",
    "一天里脑子最清醒的是上午，重要的事先做。",
    "给很久没联系的朋友发个表情，缘分需要维护。",
    "睡前把手机放远一点，睡眠质量提升百分之五十。",
    "夸自己一句：我已经很棒了。",
    "少点一次外卖，余额和健康都会感谢你。",
    "把待办清单砍到三件以内，做完就是胜利。",
    "今天的云很好看，记得抬头。",
    "洗完热水澡再回消息，脾气会变好。",
    "钱包和身体，总要有一个在路上。",
    "把「改天」改成「今晚」，很多好事就会发生。",
    "删掉一个再也不会打开的APP，手机和你都轻松了。",
    "别人没回消息，大概率只是在忙，不是你不好。",
    "今日份的快乐建议自提，不设找零。",
    "把椅子调低一点，离地面越近，心越踏实。",
    "认真吃晚饭的人，运气都不会太差。",
]

# ---------------------------------------------------------------- 生成运势

def daily_seed(d, nonce):
    return int(d.strftime("%Y%m%d")) * 100 + nonce

def make_fortune(d, sign, nonce):
    rnd = random.Random(daily_seed(d, nonce))
    level = rnd.choices(LEVELS, weights=LEVEL_W)[0]
    poem = rnd.choice(POEMS[level])
    lo, hi = STAR_RANGE[level]
    stars = {}
    for name in ["综合运势", "爱情运", "事业运", "财运"]:
        stars[name] = rnd.randint(lo, hi)
    yi = rnd.sample(YI_POOL, 3)
    ji = rnd.sample(JI_POOL, 3)
    color = rnd.choice(COLORS)
    number = rnd.randint(1, 99)
    direction = rnd.choice(DIRECTIONS)
    benefactor = rnd.choice(SIGNS)
    tip = rnd.choice(TIPS)
    sign_no = rnd.randint(1, 60)
    note = None
    if sign:
        note = "%s。%s。" % (rnd.choice(SIGN_TRAITS[sign]), rnd.choice(ADVICE))
    return {
        "level": level, "poem": poem, "stars": stars, "yi": yi, "ji": ji,
        "color": color, "number": number, "direction": direction,
        "benefactor": benefactor, "tip": tip, "sign_no": sign_no,
        "sign_note": note,
    }

def star_text(n):
    return "★" * n + "☆" * (5 - n)

# ---------------------------------------------------------------- 配置

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if isinstance(cfg, dict):
                return cfg
    except Exception:
        pass
    return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

# ---------------------------------------------------------------- 开机自启

def autostart_enabled():
    return os.path.exists(AGENT_PLIST)

def agent_plist_text():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        '  <key>Label</key><string>%s</string>\n'
        '  <key>ProgramArguments</key>\n  <array>\n'
        '    <string>%s</string>\n'
        '    <string>%s</string>\n'
        '  </array>\n'
        '  <key>RunAtLoad</key><true/>\n'
        '  <key>KeepAlive</key><false/>\n'
        '  <key>ProcessType</key><string>Interactive</string>\n'
        '</dict>\n</plist>\n'
    ) % (AGENT_LABEL, sys.executable, os.path.abspath(__file__))

def set_autostart(on):
    uid = os.getuid()
    if on:
        try:
            os.makedirs(os.path.dirname(AGENT_PLIST), exist_ok=True)
            with open(AGENT_PLIST, "w", encoding="utf-8") as f:
                f.write(agent_plist_text())
            subprocess.call(["launchctl", "enable", "gui/%d/%s" % (uid, AGENT_LABEL)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.call(["launchctl", "bootstrap", "gui/%d" % uid, AGENT_PLIST],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        try:
            if os.path.exists(AGENT_PLIST):
                os.remove(AGENT_PLIST)
        except Exception:
            pass

# ---------------------------------------------------------------- 终端模式

def print_fortune():
    today = datetime.date.today()
    cfg = load_config()
    sign = cfg.get("sign")
    f = make_fortune(today, sign, 0)
    gz, zc = ganzhi_year(today)
    line1 = "%d年%d月%d日 星期%s · %s%s年 · %s日" % (
        today.year, today.month, today.day, WEEKDAYS[today.weekday()], gz, zc, ganzhi_day(today))
    print("【每日运势】%s" % line1)
    print("第%s签 · %s" % (cn_num(f["sign_no"]), f["level"]))
    print("「%s」" % f["poem"].replace("\n", "\n  "))
    s = f["stars"]
    print("综合 %s  爱情 %s" % (star_text(s["综合运势"]), star_text(s["爱情运"])))
    print("事业 %s  财运 %s" % (star_text(s["事业运"]), star_text(s["财运"])))
    print("宜：%s" % " / ".join(f["yi"]))
    print("忌：%s" % " / ".join(f["ji"]))
    print("幸运色：%s   幸运数字：%d" % (f["color"][0], f["number"]))
    print("吉位：%s   贵人星座：%s" % (f["direction"], f["benefactor"]))
    wx = wuxing_today(today)
    dist = " ".join("%s%s" % (e, "●" * wx["votes"][e] or "○") for e in "木火土金水")
    print("五行：日主%s(%s) · 纳音「%s」 · 日元偏%s" % (
        wx["day_gz"][0], wx["day_el"], wx["nayin"], "旺" if wx["strong"] else "弱"))
    print("能量：%s" % dist)
    print("喜用「%s」：吉位%s · 冲%s(%s)，属%s者宜低调" % (
        wx["xiyong"], EL_DIR[wx["xiyong"]], wx["chong_zodiac"],
        wx["chong_branch"], wx["chong_zodiac"]))
    if f["sign_note"]:
        print("%s今日：%s" % (sign, f["sign_note"]))
    print("小贴士：%s" % f["tip"])

# ---------------------------------------------------------------- 桌面挂件

PAPER = "#FBF5EA"
CARD = "#FFFDF7"
BORDER = "#E5D9C3"
INK = "#43302B"
GREY = "#8A7A6A"
RED = "#B03A2E"
RED_DARK = "#8E2A21"
GOLD = "#B8860B"
GOLD_HOVER = "#9A7209"
GOLD_TEXT = "#A87B0A"
GREEN = "#2E7D32"
JIRED = "#C62828"
BTN_LIGHT = "#F1E7D2"
BTN_LIGHT_HOVER = "#E6D7BC"

F_TITLE = ("PingFang SC", 15, "bold")
F_SUB = ("PingFang SC", 10)
F_SIGN = ("PingFang SC", 14, "bold")
F_POEM = ("PingFang SC", 12)
F_SEC = ("PingFang SC", 11, "bold")
F_BODY = ("PingFang SC", 11)
F_STAR = ("PingFang SC", 12)
F_BTN = ("PingFang SC", 10, "bold")
F_TINY = ("PingFang SC", 9)

class FortuneApp(object):
    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.cfg = load_config()
        self.date = datetime.date.today()
        nonces = self.cfg.setdefault("nonces", {})
        self.nonce = nonces.get(self.date.isoformat(), 0)

        r = tk.Tk()
        self.root = r
        r.title(APP_NAME)
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.configure(bg=PAPER)

        self._build_header()
        self._build_sign_card()
        self._build_stars_card()
        self._build_yiji_card()
        self._build_lucky_card()
        self._build_note_card()
        self._build_tip_card()
        self._build_buttons()
        self._build_footer()

        # 右键菜单
        r.bind_all("<Button-2>", self._maybe_menu)
        r.bind_all("<Button-3>", self._maybe_menu)

        self.refresh()

        x = int(self.cfg.get("x", 120))
        y = int(self.cfg.get("y", 120))
        r.update_idletasks()
        r.geometry("320x%d+%d+%d" % (r.winfo_reqheight(), x, y))

        self._set_dock_icon()
        r.after(30000, self._tick)

    # ---------------- 界面 ----------------

    def _build_header(self):
        tk = self.tk
        h = tk.Frame(self.root, bg=RED)
        h.pack(fill="x")
        row = tk.Frame(h, bg=RED)
        row.pack(fill="x", padx=12, pady=(10, 0))
        self.w_title = tk.Label(row, text="◆ 每日运势 ◆", bg=RED, fg="#FDEBD0", font=F_TITLE)
        self.w_title.pack(side="left")
        close = tk.Label(row, text="✕", bg=RED, fg="#F5CDBF", font=("PingFang SC", 13, "bold"),
                         padx=4, cursor="pointinghand")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.on_close())
        close.bind("<Enter>", lambda e: close.configure(fg="#FFFFFF"))
        close.bind("<Leave>", lambda e: close.configure(fg="#F5CDBF"))
        self.w_date = tk.Label(h, text="", bg=RED, fg="#F0D5C5", font=F_SUB)
        self.w_date.pack(anchor="w", padx=12, pady=(2, 10))
        for w in (h, row, self.w_title, self.w_date):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)

    def _card(self):
        tk = self.tk
        f = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill="x", padx=10, pady=(8, 0))
        return f

    def _build_sign_card(self):
        tk = self.tk
        c = self._card()
        self.w_level = tk.Label(c, text="", bg=CARD, fg=GOLD_TEXT, font=F_SIGN)
        self.w_level.pack(pady=(10, 2))
        self.w_poem = tk.Label(c, text="", bg=CARD, fg=INK, font=F_POEM,
                               justify="center", wraplength=276)
        self.w_poem.pack(padx=10)
        self.w_reroll_hint = tk.Label(c, text="", bg=CARD, fg=GREY, font=F_TINY)
        self.w_reroll_hint.pack(pady=(2, 10))

    def _build_stars_card(self):
        tk = self.tk
        c = self._card()
        inner = tk.Frame(c, bg=CARD)
        inner.pack(padx=12, pady=8)
        self.w_stars = {}
        names = ["综合运势", "爱情运", "事业运", "财运"]
        for i, name in enumerate(names):
            rowi, coli = divmod(i, 2)
            tk.Label(inner, text=name, bg=CARD, fg=GREY, font=F_BODY
                     ).grid(row=rowi, column=coli * 2, sticky="e", padx=(0, 4), pady=2)
            lab = tk.Label(inner, text="", bg=CARD, fg="#D9A441", font=F_STAR)
            lab.grid(row=rowi, column=coli * 2 + 1, sticky="w", padx=(0, 14), pady=2)
            self.w_stars[name] = lab

    def _build_yiji_card(self):
        tk = self.tk
        c = self._card()
        row1 = tk.Frame(c, bg=CARD)
        row1.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(row1, text=" 宜 ", bg=GREEN, fg="#FFFFFF", font=F_SEC).pack(side="left")
        self.w_yi = tk.Label(row1, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_yi.pack(side="left", padx=(8, 0))
        row2 = tk.Frame(c, bg=CARD)
        row2.pack(fill="x", padx=12, pady=(2, 8))
        tk.Label(row2, text=" 忌 ", bg=JIRED, fg="#FFFFFF", font=F_SEC).pack(side="left")
        self.w_ji = tk.Label(row2, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_ji.pack(side="left", padx=(8, 0))

    def _build_lucky_card(self):
        tk = self.tk
        c = self._card()
        inner = tk.Frame(c, bg=CARD)
        inner.pack(padx=12, pady=8, fill="x")
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

        tk.Label(inner, text="幸运色", bg=CARD, fg=GREY, font=F_BODY
                 ).grid(row=0, column=0, sticky="e", padx=(0, 4), pady=2)
        cw = tk.Frame(inner, bg=CARD)
        cw.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=2)
        self.w_dot = tk.Canvas(cw, width=14, height=14, bg=CARD,
                               highlightthickness=0, bd=0)
        self.w_dot.pack(side="left", pady=2)
        self.w_color = tk.Label(cw, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_color.pack(side="left", padx=(4, 0))

        tk.Label(inner, text="幸运数字", bg=CARD, fg=GREY, font=F_BODY
                 ).grid(row=0, column=2, sticky="e", padx=(0, 4), pady=2)
        self.w_number = tk.Label(inner, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_number.grid(row=0, column=3, sticky="w", pady=2)

        tk.Label(inner, text="吉利方位", bg=CARD, fg=GREY, font=F_BODY
                 ).grid(row=1, column=0, sticky="e", padx=(0, 4), pady=2)
        self.w_dir = tk.Label(inner, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_dir.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(inner, text="贵人星座", bg=CARD, fg=GREY, font=F_BODY
                 ).grid(row=1, column=2, sticky="e", padx=(0, 4), pady=2)
        self.w_benefactor = tk.Label(inner, text="", bg=CARD, fg=INK, font=F_BODY)
        self.w_benefactor.grid(row=1, column=3, sticky="w", pady=2)

    def _build_note_card(self):
        tk = self.tk
        c = self._card()
        self.note_card = c
        self.w_note_title = tk.Label(c, text="", bg=CARD, fg=GOLD_TEXT, font=F_SEC)
        self.w_note_title.pack(anchor="w", padx=12, pady=(8, 0))
        self.w_note = tk.Label(c, text="", bg=CARD, fg=INK, font=F_BODY,
                               wraplength=272, justify="left")
        self.w_note.pack(anchor="w", padx=12, pady=(0, 8))

    def _build_tip_card(self):
        tk = self.tk
        c = self._card()
        self.tip_card = c
        tk.Label(c, text="✦ 每日小贴士", bg=CARD, fg=GOLD_TEXT, font=F_SEC
                 ).pack(anchor="w", padx=12, pady=(8, 0))
        self.w_tip = tk.Label(c, text="", bg=CARD, fg=INK, font=F_BODY,
                              wraplength=272, justify="left")
        self.w_tip.pack(anchor="w", padx=12, pady=(0, 8))

    def _soft_button(self, parent, text, cmd, bg, hover, fg="#FFFFFF"):
        tk = self.tk
        b = tk.Label(parent, text=text, bg=bg, fg=fg, font=F_BTN,
                     padx=12, pady=5, cursor="pointinghand")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def _build_buttons(self):
        tk = self.tk
        row = tk.Frame(self.root, bg=PAPER)
        row.pack(fill="x", padx=10, pady=(10, 0))
        self._soft_button(row, " 再求一签 ", self.reroll, GOLD, GOLD_HOVER).pack(side="left")
        self.w_sign_btn = self._soft_button(row, "", self._sign_btn_click,
                                            BTN_LIGHT, BTN_LIGHT_HOVER, INK)
        self.w_sign_btn.pack(side="right")

    def _build_footer(self):
        tk = self.tk
        tk.Label(self.root, text="拖动标题栏移动 · 右键打开菜单 · 每天自动更新",
                 bg=PAPER, fg=GREY, font=F_TINY).pack(pady=(6, 8))

    # ---------------- 逻辑 ----------------

    def refresh(self):
        sign = self.cfg.get("sign")
        f = make_fortune(self.date, sign, self.nonce)
        d = self.date
        gz, zc = ganzhi_year(d)
        self.w_date.configure(
            text="%d年%d月%d日 星期%s · %s%s年 · %s日"
            % (d.year, d.month, d.day, WEEKDAYS[d.weekday()], gz, zc, ganzhi_day(d)))
        self.w_level.configure(text="第 %s 签 · %s" % (cn_num(f["sign_no"]), f["level"]))
        self.w_poem.configure(text="「%s」" % f["poem"])
        if self.nonce:
            self.w_reroll_hint.configure(text="今日已求 %d 签，心诚则灵" % (self.nonce + 1))
        else:
            self.w_reroll_hint.configure(text="")
        for name, lab in self.w_stars.items():
            lab.configure(text=star_text(f["stars"][name]))
        self.w_yi.configure(text="  ".join(f["yi"]))
        self.w_ji.configure(text="  ".join(f["ji"]))
        cname, chex = f["color"]
        self.w_color.configure(text=cname)
        self.w_dot.delete("all")
        self.w_dot.create_oval(2, 2, 13, 13, fill=chex, outline="#B0A48E")
        self.w_number.configure(text=str(f["number"]))
        self.w_dir.configure(text=f["direction"])
        self.w_benefactor.configure(text=f["benefactor"])
        self.w_tip.configure(text=f["tip"])
        if f["sign_note"]:
            self.w_note_title.configure(text="✦ %s今日运势" % sign)
            self.w_note.configure(text=f["sign_note"])
            self.note_card.pack(fill="x", padx=10, pady=(8, 0), before=self.tip_card)
        else:
            self.note_card.pack_forget()
        self.w_sign_btn.configure(
            text=" 星座：%s ▾ " % (sign if sign else "未设置"))

        self.root.update_idletasks()
        h = self.root.winfo_reqheight()
        x = self.root.winfo_x() or int(self.cfg.get("x", 120))
        y = self.root.winfo_y() or int(self.cfg.get("y", 120))
        self.root.geometry("320x%d+%d+%d" % (h, x, y))

    def reroll(self):
        self.nonce += 1
        self.cfg.setdefault("nonces", {})[self.date.isoformat()] = self.nonce
        save_config(self.cfg)
        self.refresh()

    def set_sign(self, sign):
        self.cfg["sign"] = sign
        save_config(self.cfg)
        self.refresh()

    def _sign_btn_click(self):
        x = self.root.winfo_x() + self.root.winfo_width() - 130
        y = self.root.winfo_y() + self.root.winfo_height() - 60
        self._open_sign_menu(x, y)

    def _open_sign_menu(self, x, y):
        tk = self.tk
        m = tk.Menu(self.root, tearoff=0)
        cur = self.cfg.get("sign")
        m.add_command(label=("✓ " if not cur else "") + "不设置星座",
                      command=lambda: self.set_sign(None))
        m.add_separator()
        for s in SIGNS:
            m.add_command(label=("✓ " if s == cur else "") + s,
                          command=lambda s=s: self.set_sign(s))
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _maybe_menu(self, event):
        widget = event.widget
        try:
            if widget.winfo_class() == "Menu":
                return
        except Exception:
            pass
        tk = self.tk
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="再求一签", command=self.reroll)
        sm = tk.Menu(m, tearoff=0)
        cur = self.cfg.get("sign")
        sm.add_command(label=("✓ " if not cur else "") + "不设置星座",
                       command=lambda: self.set_sign(None))
        for s in SIGNS:
            sm.add_command(label=("✓ " if s == cur else "") + s,
                           command=lambda s=s: self.set_sign(s))
        m.add_cascade(label="我的星座", menu=sm)
        self.autostart_var = tk.IntVar(value=1 if autostart_enabled() else 0)
        m.add_checkbutton(label="开机自动启动", variable=self.autostart_var,
                          command=self._toggle_autostart)
        m.add_separator()
        m.add_command(label="关闭每日运势", command=self.on_close)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _toggle_autostart(self):
        set_autostart(bool(self.autostart_var.get()))

    def _tick(self):
        today = datetime.date.today()
        if today != self.date:
            self.date = today
            self.nonce = self.cfg.setdefault("nonces", {}).get(today.isoformat(), 0)
            self.refresh()
        self.root.after(30000, self._tick)

    def _drag_start(self, event):
        self._dx = event.x
        self._dy = event.y

    def _drag_move(self, event):
        self.root.geometry("+%d+%d" % (event.x_root - self._dx,
                                       event.y_root - self._dy))

    def _drag_end(self, event):
        self.cfg["x"] = self.root.winfo_x()
        self.cfg["y"] = self.root.winfo_y()
        save_config(self.cfg)

    def _set_dock_icon(self):
        """运行时把 Dock 图标换成自家图标（需要 pyobjc，没有就算了）。"""
        try:
            if not os.path.exists(ICON_PNG):
                return
            import AppKit
            app = AppKit.NSApplication.sharedApplication()
            img = AppKit.NSImage.alloc().initWithContentsOfFile_(ICON_PNG)
            if img:
                app.setApplicationIcon_(img)
        except Exception:
            pass

    def on_close(self):
        self.cfg["x"] = self.root.winfo_x()
        self.cfg["y"] = self.root.winfo_y()
        save_config(self.cfg)
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# ---------------------------------------------------------------- 入口

def acquire_lock():
    """单实例：已经运行时就直接退出。"""
    f = open(LOCK_PATH, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)
    return f

def main():
    if "--print" in sys.argv:
        print_fortune()
        return
    _lock = acquire_lock()
    app = FortuneApp()
    app.run()

if __name__ == "__main__":
    main()
