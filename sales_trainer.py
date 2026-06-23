"""銷售話術訓練引擎：場景 DNA 池、場景生成、AI 評估。"""

import random
import os
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

from utils import load_recent_dna, save_recent_dna, send_telegram

# ── 拒絕類型池（weight 越高越常出現）────────────────────────────
OBJECTION_TYPES = [
    {"name": "價錢太貴",   "weight": 3,
     "client_line": "你哋嘅價錢比其他公司貴好多喎，點解要揀你哋？",
     "tip": "唔好急住降價。先確認對方嘅比較基礎，再用「一分錢一分貨」框架拆解——貴嘅係乜，你嘅多咗咩。"},
    {"name": "我諗下先",   "weight": 3,
     "client_line": "唔急，等我諗下先，有需要我搵你囉。",
     "tip": "要探出「諗緊乜」，唔係逼對方，係幫對方理清疑慮。問「你主要係想諗清楚邊一點？」"},
    {"name": "同行比較",   "weight": 2,
     "client_line": "隔離X公司做同樣嘢，平你三成，點解唔揀佢？",
     "tip": "唔好攻擊競爭對手。承認差異存在，然後聚焦你獨有嘅價值，而唔係單純比價錢。"},
    {"name": "唔需要",     "weight": 2,
     "client_line": "其實我而家暫時冇呢個需要，唔好意思。",
     "tip": "「暫時」係關鍵字——探出「係咩令你覺得暫時唔需要？」幫對方看見未察覺嘅需求。"},
    {"name": "冇時間",     "weight": 2,
     "client_line": "而家真係好忙，你可唔可以之後再聯絡？",
     "tip": "唔好咁快答應「下次先傾」。用 30 秒講出最核心嘅一個價值點，再約具體時間。"},
    {"name": "信任問題",   "weight": 2,
     "client_line": "我對呢類嘢有啲顧慮，唔係好信，你點令我信你？",
     "tip": "先認同對方顧慮合理，再用具體社會認同（客戶案例、數字）建立信任，唔好自吹自擂。"},
    {"name": "問家人先",   "weight": 2,
     "client_line": "我要問下我老婆先，佢話得先得。",
     "tip": "邀請決策者一齊參與，唔係等對方回去「傳話」。「不如下次一齊坐低，咁你哋可以即場問我？」"},
    {"name": "等時機",     "weight": 1,
     "client_line": "依家市況唔係好好，等下個季度先考慮啦。",
     "tip": "「最好時機」永遠唔會自己出現。幫客戶算清楚「等」嘅機會成本——等緊係乜嘢？"},
    {"name": "已有供應商", "weight": 1,
     "client_line": "我哋已經同另一間公司合作咗好耐，唔想轉。",
     "tip": "唔好正面挑戰現有關係。先了解對方現有方案滿意度，再針對性展示差異價值。"},
    {"name": "要研究先",   "weight": 2,
     "client_line": "俾我研究下先，我會上網搵下資料再決定。",
     "tip": "主動提供資料並設定跟進時間點，避免對方靠片面網上資料決定。「我幫你整理個比較，你睇完再決定？」"},
]

# ── 客戶性格池 ────────────────────────────────────────────────────
CLIENT_PERSONAS = [
    {"name": "慳家算數型", "desc": "每分錢都要有交代，愛計算 ROI，不斷追問數字和回報"},
    {"name": "忙碌不耐型", "desc": "永遠很忙，回覆簡短，稍微囉唆就不耐煩"},
    {"name": "比較分析型", "desc": "已做過功課，不斷拿競爭對手比較，問題很具體"},
    {"name": "冷淡懷疑型", "desc": "對銷售員有戒心，語氣冷淡，不輕易相信任何說法"},
    {"name": "拖延逃避型", "desc": "永遠有藉口 push back，就是不想當下決定"},
    {"name": "情緒搖擺型", "desc": "容易受朋友／家人影響，態度反覆，需要情感共鳴"},
    {"name": "強勢主導型", "desc": "習慣主導對話，容易打斷你，覺得自己最懂"},
    {"name": "沉默保守型", "desc": "回應很少，你不知道他在想甚麼，需要主動探問"},
]

# ── 場景池 ────────────────────────────────────────────────────────
SCENARIOS = [
    "Cold call，對方剛接電話，語氣有點不耐煩",
    "WhatsApp 跟進，send proposal 後三日，對方已讀不回，今日終於回覆",
    "面對面 meeting 尾聲，氣氛還可以但對方還未表態",
    "轉介紹見面，朋友介紹但對方本身興趣一般",
    "對方帶了朋友一起來，那朋友在旁邊不斷潑冷水",
    "第二次跟進電話，上次說要考慮，今次你主動打去",
    "線上 Zoom 會議，氣氛比較疏離",
    "產品示範後，對方靜了幾秒，說出這句拒絕",
]

# ── 行業池 ────────────────────────────────────────────────────────
INDUSTRIES = [
    "保險（人壽／醫療）",
    "地產代理",
    "財務策劃／投資產品",
    "B2B 服務／SaaS 軟件",
    "培訓課程／教育",
    "直銷／網絡生意",
]

DIFFICULTY_LEVELS = {
    "初級": "客戶態度尚算友善，只是有些疑慮，比較容易說服",
    "中級": "客戶有明確抗拒點，需要技巧才能轉化，語氣有點強硬",
    "高級": "客戶態度強硬，步步為營，甚至有點咄咄逼人，需要高超技巧",
}

SCORE_LABELS = {
    1: "❌ 需要改善",
    2: "⚠️ 有進步空間",
    3: "✅ 不錯",
    4: "🌟 出色",
}


# ── DNA 抽選（防重複）────────────────────────────────────────────

def _pick_fresh_dict(pool: list, key: str, recent: dict, window: int = 4):
    """從 dict list 抽選，避開最近用過嘅（按 name 去重）。"""
    used  = set(recent.get(key, []))
    fresh = [x for x in pool if x["name"] not in used] or pool
    weights = [x.get("weight", 1) for x in fresh]
    return random.choices(fresh, weights=weights, k=1)[0]

def _pick_fresh_str(pool: list, key: str, recent: dict, window: int = 4):
    """從 string list 抽選，避開最近用過嘅。"""
    used  = set(recent.get(key, []))
    fresh = [x for x in pool if x not in used] or pool
    return random.choice(fresh)

def _update_recent(recent: dict, key: str, val: str, window: int = 4):
    lst = recent.get(key, [])
    if val in lst:
        lst.remove(val)
    lst.append(val)
    recent[key] = lst[-window:]


def pick_scenario_dna(force_objection: str = None, force_industry: str = None, difficulty: str = None) -> dict:
    """抽取一組場景 DNA，支援強制指定拒絕類型或行業，自動防重複。"""
    try:
        recent = load_recent_dna()
    except Exception:
        recent = {}

    # Objection
    if force_objection:
        obj = next((x for x in OBJECTION_TYPES if force_objection in x["name"]), None) \
              or _pick_fresh_dict(OBJECTION_TYPES, "objection", recent)
    else:
        obj = _pick_fresh_dict(OBJECTION_TYPES, "objection", recent)

    # Industry
    if force_industry:
        ind = next((x for x in INDUSTRIES if force_industry in x), None) \
              or _pick_fresh_str(INDUSTRIES, "industry", recent)
    else:
        ind = _pick_fresh_str(INDUSTRIES, "industry", recent)

    persona  = _pick_fresh_dict(CLIENT_PERSONAS, "persona", recent)
    scenario = _pick_fresh_str(SCENARIOS, "scenario", recent)
    diff     = difficulty or random.choices(
        list(DIFFICULTY_LEVELS.keys()), weights=[3, 4, 2], k=1
    )[0]

    # 更新 recent
    _update_recent(recent, "objection", obj["name"])
    _update_recent(recent, "industry",  ind)
    _update_recent(recent, "persona",   persona["name"])
    _update_recent(recent, "scenario",  scenario)
    try:
        save_recent_dna(recent)
    except Exception:
        pass

    return {
        "objection": obj,
        "persona":   persona,
        "scenario":  scenario,
        "industry":  ind,
        "difficulty": diff,
    }


# ── 場景生成 ──────────────────────────────────────────────────────

def generate_scenario(force_objection: str = None, force_industry: str = None, difficulty: str = None):
    """生成練習場景，返回 (展示文字, 場景 dict)。"""
    s = pick_scenario_dna(force_objection, force_industry, difficulty)
    obj     = s["objection"]
    persona = s["persona"]

    display = (
        f"🎯 練習開始！\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏭 行業：{s['industry']}\n"
        f"📍 場景：{s['scenario']}\n"
        f"👤 客戶：{persona['name']} — {persona['desc']}\n"
        f"⚡ 難度：{s['difficulty']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"客戶說：\n「{obj['client_line']}」\n\n"
        f"💬 你點答？直接打出你嘅回應 ⬇️"
    )
    return display, s


# ── AI 評估 ───────────────────────────────────────────────────────

def evaluate_response(user_response: str, scenario: dict, max_retries: int = 3) -> str:
    """用 DeepSeek 評估用戶銷售回應，返回評分＋反饋＋最佳示範。"""
    client  = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    obj     = scenario["objection"]
    persona = scenario["persona"]

    prompt = f"""你係一個頂尖銷售培訓教練，同時扮演客戶角色。

【練習場景】
行業：{scenario['industry']}
場景：{scenario['scenario']}
難度：{scenario['difficulty']} — {DIFFICULTY_LEVELS[scenario['difficulty']]}
客戶性格：{persona['name']} — {persona['desc']}
客戶說：「{obj['client_line']}」

【學員的回應】
{user_response}

【輸出格式——嚴格跟住以下結構】

**客戶反應：**
（以客戶身份自然回應學員剛才說嘅話，1-3句，保持客戶性格，唔好太快被說服）

**━━ 教練評分 ━━**
評分：X／4
（1=方向錯誤令客戶更反感｜2=方向對但技巧不足｜3=不錯有改善空間｜4=出色自然有說服力）

做得好的地方：

需要改善：

**━━ 最佳示範回應 ━━**
（用廣東話口語，自然流暢，符合香港銷售實戰習慣，針對呢個客戶性格同拒絕類型）

**━━ 技巧重點 ━━**
{obj['tip']}"""

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1200,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            print(f"[evaluate_response] 第{attempt}次失敗：{e}")
    return f"⚠️ 評估失敗（已重試 {max_retries} 次）：{last_err}"


# ── 對話分析 ──────────────────────────────────────────────────────

def analyze_conversation(conversation: str, profile: dict) -> str:
    industry = profile.get("industry", "銷售")
    company  = profile.get("company", "")
    product  = profile.get("product", "")
    ctx = f"行業：{industry}"
    if company: ctx += f"\n公司：{company}"
    if product: ctx += f"\n產品：{product}"
    prompt = f"""你係資深銷售教練，分析以下真實銷售對話並給出具體建議。

【銷售背景】
{ctx}

【真實對話記錄】
{conversation}

用廣東話，以下格式輸出：

⚠️ **失分關鍵點：**
[列出 2-3 個具體失分位，每點一行，指出對話哪句出問題]

✅ **應該咁講：**
[針對每個失分點，給出更強嘅替代話術]

🔄 **挽救方案：**
[如果而家想重新聯絡，建議發咩訊息，直接提供可用腳本]

📈 **下次記住：**
[一句精華總結，銘記於心]"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700, temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


# ── 社交媒體 ──────────────────────────────────────────────────────

SOCIAL_PLATFORMS = ["FB 評論", "IG 評論", "WhatsApp DM"]
SOCIAL_CONTENT_TYPES = ["銷售貼文", "DM 開場腳本", "評論回覆範本"]

SOCIAL_COMMENTS = {
    "FB 評論": ["呢啲係咪真㗎？唔好唔好用","貴到離晒地，唔抵買","我朋友買過，話冇用","有冇折扣㗎？","係咪傳銷㗎？"],
    "IG 評論": ["呢啲唔抵買，係呃人㗎","幾多錢？inbox 我","有冇試用㗎先？","我都想買但驚係假","比 XX 差好多"],
    "WhatsApp DM": ["你好，我係睇到你IG post，想了解下","幾錢㗎？直接講","我要考慮下，唔急","我朋友話唔好用","我已經有買緊其他嘅"],
}

def generate_social_scenario(platform: str, profile: dict) -> tuple:
    import random
    company = profile.get("company","") or profile.get("industry","銷售")
    comment = random.choice(SOCIAL_COMMENTS.get(platform, SOCIAL_COMMENTS["IG 評論"]))
    display = (f"📱 {platform} 場景\n{'─'*28}\n"
               f"你喺 {platform} 宣傳 {company}，有人留言：\n\n「{comment}」\n\n點回覆？")
    return display, {"type":"social","platform":platform,"comment":comment,"profile":profile}

def evaluate_social_response(user_response: str, scenario: dict) -> str:
    platform = scenario["platform"]; comment = scenario["comment"]
    company = scenario.get("profile",{}).get("company","你哋公司")
    prompt = f"""你係社交媒體銷售教練，評估以下回覆。
平台：{platform}\n客戶留言：「{comment}」\n銷售員回覆：{user_response}\n公司：{company}

廣東話輸出：
**效果預測：**[客戶反應，2句]
**評分：[1-4]**\n1=嚇走客戶 2=無功而返 3=有機會轉化 4=完美引入inbox
**點評：**[具體2句]
**更強版本：**[可直接用，40字內]"""
    resp = client.chat.completions.create(model="deepseek-chat",
        messages=[{"role":"user","content":prompt}],max_tokens=500,temperature=0.7)
    return resp.choices[0].message.content.strip()

def generate_social_content(content_type: str, profile: dict) -> str:
    industry = profile.get("industry","銷售"); company = profile.get("company","")
    product  = profile.get("product","")
    ctx = f"行業：{industry}" + (f"，公司：{company}" if company else "") + (f"，產品：{product}" if product else "")
    prompts = {
        "銷售貼文": f"幫我寫一篇 IG/FB 銷售貼文。{ctx}\n要求：廣東話貼地，痛點hook開頭，展示價值唔硬銷，結尾CTA叫人inbox，200字內加emoji，附3個hashtag",
        "DM 開場腳本": f"幫我寫完整WhatsApp DM銷售腳本。{ctx}\n包括：1.開場暖身 2.了解需求問題 3.自然介紹產品 4.處理「要考慮下」 5.成交收尾。廣東話自然語氣，每段附解釋",
        "評論回覆範本": f"幫我寫5套社交媒體評論回覆範本。{ctx}\n針對：1.太貴 2.係咪真 3.有冇試用 4.我考慮下 5.有冇折扣。每套廣東話親切專業，引導入inbox，30字內",
    }
    resp = client.chat.completions.create(model="deepseek-chat",
        messages=[{"role":"user","content":prompts.get(content_type,prompts["銷售貼文"])}],
        max_tokens=800,temperature=0.8)
    return resp.choices[0].message.content.strip()
