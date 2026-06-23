import sys, os, re, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
from datetime import datetime, timedelta
import requests as req

from sales_trainer import (
    generate_scenario, evaluate_response,
    OBJECTION_TYPES, DIFFICULTY_LEVELS,
    SOCIAL_PLATFORMS, SOCIAL_CONTENT_TYPES,
    generate_social_scenario, evaluate_social_response,
    generate_social_content, analyze_conversation,
)
from utils import (
    load_stats, save_stats, load_session, save_session, clear_session,
    load_profile, save_profile,
    load_setup_session, save_setup_session, clear_setup_session,
    send_telegram,
)

app = Flask(__name__)
TOKEN = lambda: os.getenv("TELEGRAM_BOT_TOKEN")

INDUSTRIES = ["保險","地產","企業SaaS","零售消費品","金融投資","教育培訓"]


def answer_cb(cb_id):
    req.post(f"https://api.telegram.org/bot{TOKEN()}/answerCallbackQuery",
             json={"callback_query_id":cb_id},timeout=5)

def cmd(text,command):
    return text==command or text.startswith(command+" ") or text.startswith(command+"@")

def record_score(obj_name,score):
    data=load_stats(); scores=data.setdefault("objection_scores",{})
    h=scores.setdefault(obj_name,[]); h.append(score); scores[obj_name]=h[-20:]
    data["total_sessions"]=data.get("total_sessions",0)+1
    today=datetime.now().strftime("%Y-%m-%d")
    yesterday=(datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
    s=data.setdefault("streak",{"last_date":"","count":0})
    if s["last_date"]==today: pass
    elif s["last_date"]==yesterday: s["count"]+=1; s["last_date"]=today
    else: s["count"]=1; s["last_date"]=today
    save_stats(data)

def _send_main_menu(profile=None):
    name=profile.get("company","") if profile else ""
    title=f"你好！{name} 練習中心" if name else "銷售話術訓練"
    send_telegram(f"🥊 {title}\n\n揀你想做咩：",reply_markup={"inline_keyboard":[
        [{"text":"🎯 開始練習","callback_data":"practice_new"}],
        [{"text":"🔍 分析我嘅對話","callback_data":"review_start"}],
        [{"text":"📱 社交媒體幫手","callback_data":"social_menu"}],
        [{"text":"📊 我嘅進度","callback_data":"show_stats"},
         {"text":"💡 今日技巧","callback_data":"show_tip"}],
        [{"text":"⚙️ 更改設定","callback_data":"setup_start"}],
    ]})

def handle_start():
    profile=load_profile()
    if not profile:
        send_telegram("🥊 歡迎使用銷售話術訓練機器人！\n\n先設定你嘅背景，AI 就能定制練習：",
            reply_markup={"inline_keyboard":[[{"text":"⚙️ 開始設定","callback_data":"setup_start"}]]})
    else: _send_main_menu(profile)

def handle_setup_start():
    clear_setup_session(); save_setup_session({"step":"industry"})
    kb=[]; row=[]
    for ind in INDUSTRIES:
        row.append({"text":ind,"callback_data":f"setup_industry_{ind}"})
        if len(row)==2: kb.append(row); row=[]
    if row: kb.append(row)
    kb.append([{"text":"✏️ 自訂行業","callback_data":"setup_industry_custom"}])
    send_telegram("⚙️ 第一步：你係做咩行業？",reply_markup={"inline_keyboard":kb})

def handle_setup_industry(industry):
    sess=load_setup_session()
    if industry=="custom":
        sess["step"]="industry_custom"; save_setup_session(sess)
        send_telegram("請輸入你嘅行業（例如：美容、健身、旅遊）："); return
    sess["industry"]=industry; sess["step"]="company"; save_setup_session(sess)
    send_telegram(f"✅ 行業：{industry}\n\n第二步：公司名 + 主打產品係？\n（例如：AIA，危疾保，目標 30-50 歲專業人士）")

def handle_setup_text(text):
    sess=load_setup_session(); step=sess.get("step","")
    if step=="industry_custom":
        sess["industry"]=text; sess["step"]="company"; save_setup_session(sess)
        send_telegram(f"✅ 行業：{text}\n\n第二步：公司名 + 主打產品係？")
    elif step=="company":
        profile={"industry":sess.get("industry",""),
                 "company":text.split("，")[0].split(",")[0].strip(),"product":text}
        save_profile(profile); clear_setup_session()
        send_telegram(f"🎉 設定完成！\n\n行業：{profile['industry']}\n公司：{profile['company']}\n\n之後所有練習都會定制！")
        _send_main_menu(profile)

def start_practice(force_objection=None,force_industry=None,difficulty=None):
    profile=load_profile(); industry=force_industry or (profile.get("industry") if profile else None)
    display,scenario=generate_scenario(force_objection,industry,difficulty)
    save_session({"state":"waiting_response","scenario":scenario}); send_telegram(display)

def handle_user_response(user_text):
    session=load_session()
    if not session or session.get("state")!="waiting_response":
        send_telegram("唔係練習模式。由主選單開始！"); return
    clear_session(); scenario=session["scenario"]; obj_name=scenario["objection"]
    send_telegram("🤔 AI 評估緊你嘅回應，稍等⋯⋯")
    feedback=evaluate_response(user_text,scenario)
    m=re.search(r"評分[：:]\s*\[?([1-4])\]?",feedback)
    if m: record_score(obj_name,int(m.group(1)))
    send_telegram(feedback,reply_markup={"inline_keyboard":[[
        {"text":"🔄 再練一個","callback_data":"practice_new"},
        {"text":f"🎯 再練「{obj_name}」","callback_data":f"drill_{obj_name}"},
        {"text":"🏠 主選單","callback_data":"main_menu"},
    ]]})

def handle_review_start():
    save_session({"state":"waiting_review"})
    send_telegram("🔍 Paste 你同客戶嘅真實對話\n（WhatsApp 截圖文字、電話記錄等）\n\nAI 會分析失分點同挽救方案：")

def handle_review_text(text):
    send_telegram("🔍 分析緊你嘅對話⋯⋯")
    profile=load_profile(); result=analyze_conversation(text,profile or {})
    send_telegram(result,reply_markup={"inline_keyboard":[[
        {"text":"🎯 針對呢個情況練習","callback_data":"practice_new"},
        {"text":"🏠 主選單","callback_data":"main_menu"},
    ]]})

def handle_social_menu():
    send_telegram("📱 社交媒體幫手\n\n揀你想做咩：",reply_markup={"inline_keyboard":[
        [{"text":"🎯 練習回覆評論/DM","callback_data":"social_practice_menu"}],
        [{"text":"✍️ 幫我生成內容","callback_data":"social_generate_menu"}],
        [{"text":"🏠 返回主選單","callback_data":"main_menu"}],
    ]})

def handle_social_practice_menu():
    kb=[[{"text":p,"callback_data":f"social_platform_{p}"}] for p in SOCIAL_PLATFORMS]
    kb.append([{"text":"🔙 返回","callback_data":"social_menu"}])
    send_telegram("揀平台：",reply_markup={"inline_keyboard":kb})

def handle_social_generate_menu():
    profile=load_profile()
    if not profile:
        send_telegram("請先完成設定！",reply_markup={"inline_keyboard":[[{"text":"⚙️ 立即設定","callback_data":"setup_start"}]]}); return
    kb=[[{"text":t,"callback_data":f"social_generate_{t}"}] for t in SOCIAL_CONTENT_TYPES]
    kb.append([{"text":"🔙 返回","callback_data":"social_menu"}])
    send_telegram("揀內容類型：",reply_markup={"inline_keyboard":kb})

def start_social_practice(platform):
    profile=load_profile() or {}
    display,scenario=generate_social_scenario(platform,profile)
    save_session({"state":"waiting_social_response","scenario":scenario}); send_telegram(display)

def handle_social_response(user_text):
    session=load_session()
    if not session or session.get("state")!="waiting_social_response":
        send_telegram("唔係練習模式！"); return
    clear_session(); scenario=session["scenario"]; platform=scenario["platform"]
    send_telegram("🤔 評估緊你嘅回覆⋯⋯")
    feedback=evaluate_social_response(user_text,scenario)
    send_telegram(feedback,reply_markup={"inline_keyboard":[[
        {"text":f"🔄 再練「{platform}」","callback_data":f"social_platform_{platform}"},
        {"text":"📱 換平台","callback_data":"social_practice_menu"},
        {"text":"🏠 主選單","callback_data":"main_menu"},
    ]]})

def do_generate_content(content_type):
    profile=load_profile() or {}
    send_telegram(f"✍️ 生成「{content_type}」中⋯⋯")
    result=generate_social_content(content_type,profile)
    send_telegram(result,reply_markup={"inline_keyboard":[[
        {"text":"✍️ 生成另一種","callback_data":"social_generate_menu"},
        {"text":"🏠 主選單","callback_data":"main_menu"},
    ]]})

def handle_stats():
    data=load_stats(); scores=data.get("objection_scores",{}); total=data.get("total_sessions",0)
    streak=data.get("streak",{})
    if not scores: send_telegram("未有記錄，由主選單開始第一次練習！"); return
    ranked=sorted([(n,sum(sc)/len(sc),len(sc)) for n,sc in scores.items() if sc],key=lambda x:x[1],reverse=True)
    lines=[f"📊 銷售訓練進度\n總練習：{total} 次  |  連續 {streak.get('count',0)} 日\n","【各類型掌握度】"]
    for name,avg,count in ranked:
        lines.append(f"{'█'*round(avg)}{'░'*(4-round(avg))}  {name}  {round(avg/4*100)}%（{count}次）")
    weak=[x for x in ranked if x[1]<2.5]
    if weak: lines.append(f"\n⚠️ 薄弱：{', '.join(x[0] for x in weak[:3])}")
    send_telegram("\n".join(lines),reply_markup={"inline_keyboard":[[{"text":"🏠 主選單","callback_data":"main_menu"}]]})

def handle_tip():
    import random; obj=random.choice(OBJECTION_TYPES)
    send_telegram(f"💡 今日技巧\n\n【{obj['name']}】\n\n{obj['tip']}",
        reply_markup={"inline_keyboard":[[{"text":f"🎯 練習呢個","callback_data":f"drill_{obj['name']}"},
                                          {"text":"🏠 主選單","callback_data":"main_menu"}]]})

def handle_drill_menu():
    keyboard=[]; row=[]
    for obj in OBJECTION_TYPES:
        row.append({"text":obj["name"],"callback_data":f"drill_{obj['name']}"})
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([{"text":"🎲 隨機場景","callback_data":"practice_new"},{"text":"🏠 主選單","callback_data":"main_menu"}])
    send_telegram("🎯 針對練習——揀拒絕類型：",reply_markup={"inline_keyboard":keyboard})

def handle_callback(cb):
    answer_cb(cb["id"]); data=cb.get("data","")
    if data=="main_menu": _send_main_menu(load_profile()); return
    if data=="setup_start": threading.Thread(target=handle_setup_start,daemon=True).start(); return
    if data.startswith("setup_industry_"):
        threading.Thread(target=handle_setup_industry,args=(data[len("setup_industry_"):],),daemon=True).start(); return
    if data=="practice_new": threading.Thread(target=start_practice,daemon=True).start(); return
    if data.startswith("drill_"):
        threading.Thread(target=start_practice,kwargs={"force_objection":data[6:]},daemon=True).start(); return
    if data=="review_start": handle_review_start(); return
    if data=="social_menu": handle_social_menu(); return
    if data=="social_practice_menu": handle_social_practice_menu(); return
    if data=="social_generate_menu": handle_social_generate_menu(); return
    if data.startswith("social_platform_"):
        threading.Thread(target=start_social_practice,args=(data[len("social_platform_"):],),daemon=True).start(); return
    if data.startswith("social_generate_"):
        threading.Thread(target=do_generate_content,args=(data[len("social_generate_"):],),daemon=True).start(); return
    if data=="show_stats": threading.Thread(target=handle_stats,daemon=True).start(); return
    if data=="show_tip": threading.Thread(target=handle_tip,daemon=True).start(); return

def handle_message(text):
    setup_sess=load_setup_session()
    if setup_sess.get("step") in ("industry_custom","company") and not text.startswith("/"):
        threading.Thread(target=handle_setup_text,args=(text,),daemon=True).start(); return
    session=load_session(); state=session.get("state","") if session else ""
    if state=="waiting_response" and not text.startswith("/"):
        threading.Thread(target=handle_user_response,args=(text,),daemon=True).start(); return
    if state=="waiting_review" and not text.startswith("/"):
        clear_session(); threading.Thread(target=handle_review_text,args=(text,),daemon=True).start(); return
    if state=="waiting_social_response" and not text.startswith("/"):
        threading.Thread(target=handle_social_response,args=(text,),daemon=True).start(); return
    if cmd(text,"/start") or cmd(text,"/help"): handle_start(); return
    if cmd(text,"/setup"): threading.Thread(target=handle_setup_start,daemon=True).start(); return
    if cmd(text,"/practice"):
        parts=text.split(maxsplit=1); extra=parts[1].strip() if len(parts)>1 else None
        diff=extra if extra in DIFFICULTY_LEVELS else None; ind=extra if extra and extra not in DIFFICULTY_LEVELS else None
        send_telegram("🎯 生成練習場景⋯⋯")
        threading.Thread(target=start_practice,kwargs={"force_industry":ind,"difficulty":diff},daemon=True).start(); return
    if cmd(text,"/drill"): handle_drill_menu(); return
    if cmd(text,"/review"): handle_review_start(); return
    if cmd(text,"/social"): handle_social_menu(); return
    if cmd(text,"/stats"): threading.Thread(target=handle_stats,daemon=True).start(); return
    if cmd(text,"/tip"): threading.Thread(target=handle_tip,daemon=True).start(); return
    profile=load_profile()
    if not profile: handle_start(); return
    _send_main_menu(profile)

@app.route("/api/webhook",methods=["POST"])
def webhook():
    update=request.json or {}
    if "callback_query" in update: handle_callback(update["callback_query"])
    elif "message" in update:
        text=update["message"].get("text","").strip()
        if text: handle_message(text)
    return jsonify({"ok":True})

@app.route("/",methods=["GET"])
def health(): return "Sales Trainer Bot V2",200

if __name__=="__main__": app.run(debug=False)
