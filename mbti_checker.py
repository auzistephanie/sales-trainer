"""MBTI 精簡檢測（20條問題，參考 16personalities 設計）"""

# ── 20條問題（每個維度 5 條）────────────────────────────────────
MBTI_QUESTIONS = [
    # ── E/I 維度（外向／內向）────────────────────────────────
    {
        "id": 1, "dimension": "E/I",
        "question": "參加派對或社交活動之後，你通常會覺得？",
        "a": "充滿能量，想繼續同人傾計",
        "b": "有啲累，需要靜一靜恢復能量",
        "mapping": {"A": "E", "B": "I"},
    },
    {
        "id": 2, "dimension": "E/I",
        "question": "你比較鍾意點樣度過週末？",
        "a": "約朋友見面、參加活動、去熱鬧嘅地方",
        "b": "留喺屋企睇書/睇戲、小圈子聚會",
        "mapping": {"A": "E", "B": "I"},
    },
    {
        "id": 3, "dimension": "E/I",
        "question": "喺工作環境入面，你通常係？",
        "a": "鍾意同同事多互動，傾計 brainstorming",
        "b": "鍾意專注自己做嘢，少啲 interruption",
        "mapping": {"A": "E", "B": "I"},
    },
    {
        "id": 4, "dimension": "E/I",
        "question": "你覺得自己喺邊種情況表現最好？",
        "a": "同人合作、即場互動、有 audience 嘅時候",
        "b": "自己獨立思考、有充足時間準備嘅時候",
        "mapping": {"A": "E", "B": "I"},
    },
    {
        "id": 5, "dimension": "E/I",
        "question": "你通常點樣處理壓力？",
        "a": "搵人傾訴、通過社交 release",
        "b": "自己靜靜諗、通過獨處消化",
        "mapping": {"A": "E", "B": "I"},
    },
    # ── S/N 維度（感官／直覺）────────────────────────────────
    {
        "id": 6, "dimension": "S/N",
        "question": "你覺得自己係邊種人？",
        "a": "務實型 — 重視具體事實、細節、實際經驗",
        "b": "概念型 — 重視大方向、可能性、未來願景",
        "mapping": {"A": "S", "B": "N"},
    },
    {
        "id": 7, "dimension": "S/N",
        "question": "當你學習新嘢嘅時候，你通常？",
        "a": "由具體例子同實作開始，一步步嚟",
        "b": "先理解整體概念同原理，再睇細節",
        "mapping": {"A": "S", "B": "N"},
    },
    {
        "id": 8, "dimension": "S/N",
        "question": "你比較擅長邊方面？",
        "a": "留意細節、記住具體資訊、執行精準",
        "b": "睇到 pattern、連接概念、創新思維",
        "mapping": {"A": "S", "B": "N"},
    },
    {
        "id": 9, "dimension": "S/N",
        "question": "你點樣描述自己嘅思考方式？",
        "a": "實際、現實、基於已有經驗",
        "b": "抽象、想像力豐富、鍾意諗未來可能性",
        "mapping": {"A": "S", "B": "N"},
    },
    {
        "id": 10, "dimension": "S/N",
        "question": "你傾向點樣理解新資訊？",
        "a": "靠事實同數據，親眼見到先信",
        "b": "靠直覺，感受個概念嘅本質同關聯",
        "mapping": {"A": "S", "B": "N"},
    },
    # ── T/F 維度（思考／情感）────────────────────────────────
    {
        "id": 11, "dimension": "T/F",
        "question": "做重要決定嘅時候，你主要靠？",
        "a": "邏輯分析、客觀數據、pros and cons",
        "b": "個人價值觀、對人嘅影響、直覺感受",
        "mapping": {"A": "T", "B": "F"},
    },
    {
        "id": 12, "dimension": "T/F",
        "question": "咩 feedback 對你嚟講更有價值？",
        "a": "直接指出問題所在，理性分析點改善",
        "b": "先肯定努力，再溫柔講可以點做更好",
        "mapping": {"A": "T", "B": "F"},
    },
    {
        "id": 13, "dimension": "T/F",
        "question": "當團隊有意見分歧，你通常？",
        "a": "用邏輯同數據說服對方，搵最合理嘅方案",
        "b": "重視團隊和諧，理解每個人嘅感受同需要",
        "mapping": {"A": "T", "B": "F"},
    },
    {
        "id": 14, "dimension": "T/F",
        "question": "你覺得自己比較似邊種人？",
        "a": "理性、客觀、直接，唔會因人情改變判斷",
        "b": "有同理心、sensitive to 人哋情緒、重視人際",
        "mapping": {"A": "T", "B": "F"},
    },
    {
        "id": 15, "dimension": "T/F",
        "question": "要 critique 人哋嘅工作時，你會？",
        "a": "直接講事實同改善位，唔會太多修飾",
        "b": "小心選擇用詞，避免傷害對方感受",
        "mapping": {"A": "T", "B": "F"},
    },
    # ── J/P 維度（判斷／感知）────────────────────────────────
    {
        "id": 16, "dimension": "J/P",
        "question": "你對計劃同 schedule 嘅態度係？",
        "a": "鍾意有清晰計劃，跟住時間表做，早啲完成",
        "b": "鍾意有彈性，可以隨時調整，最後衝刺都 ok",
        "mapping": {"A": "J", "B": "P"},
    },
    {
        "id": 17, "dimension": "J/P",
        "question": "你嘅工作空間／書桌通常係點嘅？",
        "a": "整齊有組織，每樣嘢都有佢嘅位置",
        "b": "有啲亂，但我知每樣嘢喺邊，creative chaos",
        "mapping": {"A": "J", "B": "P"},
    },
    {
        "id": 18, "dimension": "J/P",
        "question": "你對「截止日期」嘅感覺係？",
        "a": "有 deadline 我先會 focus，鍾意早啲完成",
        "b": "deadline 係指引，我通常最後衝刺先做到最好",
        "mapping": {"A": "J", "B": "P"},
    },
    {
        "id": 19, "dimension": "J/P",
        "question": "你比較鍾意邊種工作方式？",
        "a": "有清晰流程、步驟、predictable 嘅環境",
        "b": "多變、新挑戰、可以即興發揮嘅環境",
        "mapping": {"A": "J", "B": "P"},
    },
    {
        "id": 20, "dimension": "J/P",
        "question": "你通常點樣處理「要做決定」嘅情況？",
        "a": "盡快決定，唔想拖，決定咗就向前行",
        "b": "保持開放，收集多啲資訊先，唔急住決定",
        "mapping": {"A": "J", "B": "P"},
    },
]

# ── MBTI 描述 ─────────────────────────────────────────────────────
MBTI_QUICK_DESC = {
    "INTJ": "策略家 — 獨立、有遠見、鍾意解決複雜問題",
    "INTP": "學者 — 分析力強、鍾意理論、追求深度理解",
    "ENTJ": "指揮官 — 天生領袖、果斷、推動力強",
    "ENTP": "辯論家 — 靈活、有創意、鍾意挑戰常規",
    "INFJ": "提倡者 — 有使命感、同理心強、理想主義",
    "INFP": "調停者 — 真誠、有原則、價值觀清晰",
    "ENFJ": "主人公 — 感染力強、有魅力、擅長激勵人",
    "ENFP": "競選者 — 熱情、有創意、擅長 connect 人",
    "ISTJ": "物流師 — 可靠、有條理、負責任",
    "ISFJ": "守衛者 — 細心、有同理心、默默支持團隊",
    "ESTJ": "總經理 — 果斷、有組織力、重視效率",
    "ESFJ": "執政官 — 熱心、重視和諧、擅長照顧人",
    "ISTP": "鑑賞家 — 冷靜、手藝好、擅長拆解問題",
    "ISFP": "探險家 — 真誠、有藝術感、活在當下",
    "ESTP": "企業家 — 反應快、大膽、行動力強",
    "ESFP": "表演者 — 充滿能量、樂觀、擅長帶動氣氛",
}


def validate_mbti(mbti: str) -> bool:
    return mbti.upper().strip() in MBTI_QUICK_DESC


def format_mbti_list() -> str:
    types = list(MBTI_QUICK_DESC.keys())
    return "\n".join(" · ".join(types[i:i+4]) for i in range(0, 16, 4))


def calculate_mbti(answers: list) -> dict | None:
    """傳入 20 個 A/B 答案，返回 MBTI 結果 + 信心度。"""
    if len(answers) != 20:
        return None

    dims = {"E/I": [], "S/N": [], "T/F": [], "J/P": []}
    for i, ans in enumerate(answers):
        ans = ans.strip().upper()
        if ans not in ["A", "B"]:
            return None
        q = MBTI_QUESTIONS[i]
        dims[q["dimension"]].append(q["mapping"][ans])

    def _confidence(win, total):
        if win == total:    return "非常高 👍👍"
        if win >= total - 1: return "高 👍"
        return "中 ⚠️"

    result = {}
    letters = []
    for dim, vals in dims.items():
        total = len(vals)  # 5
        pair  = dim.split("/")
        a_letter, b_letter = pair[0], pair[1]
        a_count = vals.count(a_letter)
        b_count = total - a_count
        winner  = a_letter if a_count >= b_count else b_letter
        letters.append(winner)
        result[dim] = {
            a_letter: round(a_count / total * 100),
            b_letter: round(b_count / total * 100),
            "result":     winner,
            "confidence": _confidence(max(a_count, b_count), total),
        }

    mbti = "".join(letters)
    high = sum(1 for v in result.values() if "高" in v["confidence"])
    if high == 4:   overall, note = "非常高 👍👍", "呢個結果好值得參考！"
    elif high >= 3: overall, note = "高 👍",       "大致可靠，有啲維度可以再確認。"
    elif high >= 2: overall, note = "中 ⚠️",       "部分維度比較接近，建議去 16personalities 做正式測試。"
    else:           overall, note = "低 ❓",        "建議去 16personalities.com 做正式測試確認。"

    return {"mbti": mbti, "dimensions": result, "overall": overall, "note": note, "high": high}


def mbti_question_keyboard(step: int) -> dict:
    """返回問題 step 嘅 inline keyboard（A/B 按鈕）。"""
    q = MBTI_QUESTIONS[step]
    return {"inline_keyboard": [[
        {"text": f"A) {q['a'][:30]}…" if len(q['a']) > 30 else f"A) {q['a']}",
         "callback_data": f"mbti_ans_{step}_A"},
        {"text": f"B) {q['b'][:30]}…" if len(q['b']) > 30 else f"B) {q['b']}",
         "callback_data": f"mbti_ans_{step}_B"},
    ]]}


def mbti_question_text(step: int) -> str:
    """返回問題 step 嘅文字（含進度條）。"""
    q      = MBTI_QUESTIONS[step]
    total  = len(MBTI_QUESTIONS)
    filled = "█" * (step * 10 // total)
    empty  = "░" * (10 - len(filled))
    dim_emoji = {"E/I": "🧑‍🤝‍🧑", "S/N": "🔍", "T/F": "⚖️", "J/P": "📋"}
    return (
        f"{dim_emoji.get(q['dimension'], '')} 進度：{step}/{total}  {filled}{empty}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*問題 {step+1}/{total}* — {q['dimension']}\n\n"
        f"{q['question']}\n\n"
        f"A) {q['a']}\n"
        f"B) {q['b']}"
    )


def mbti_result_text(result: dict) -> str:
    """格式化 MBTI 結果訊息。"""
    mbti = result["mbti"]
    dims = result["dimensions"]
    desc = MBTI_QUICK_DESC.get(mbti, "")
    dim_emoji = {"E/I": "🧑‍🤝‍🧑", "S/N": "🔍", "T/F": "⚖️", "J/P": "📋"}

    lines = [
        f"✅ *檢測完成！*\n",
        f"🧠 *{mbti}* — {desc}\n",
        f"📊 *維度分析：*",
    ]
    for dim, v in dims.items():
        pair    = dim.split("/")
        a, b    = pair[0], pair[1]
        lines.append(
            f"{dim_emoji.get(dim, '')} {dim}：{a} {v[a]}% · {b} {v[b]}%  →  *{v['result']}*  {v['confidence']}"
        )

    lines += [
        f"\n🎯 整體信心度：{result['overall']}",
        f"💡 {result['note']}",
    ]

    if result["high"] < 3:
        lines.append(
            "\n建議去 [16personalities.com](https://www.16personalities.com/ch) 做正式測試（免費，約10分鐘），"
            f"做完用 `/mbti {mbti}` 直接輸入結果。"
        )

    lines.append(f"\n✅ 呢個 MBTI 會用嚟個人化你嘅面試 coaching！")
    return "\n".join(lines)
