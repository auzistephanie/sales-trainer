import sys, os, re, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
from sales_trainer import generate_scenario, evaluate_response, OBJECTION_TYPES, DIFFICULTY_LEVELS
from utils import load_stats, save_stats, load_session, save_session, clear_session, send_telegram
from datetime import datetime, timedelta
import requests as req

app = Flask(__name__)

def record_score(obj_name, score):
    data=load_stats(); scores=data.setdefault("objection_scores",{})
    h=scores.setdefault(obj_name,[]); h.append(score); scores[obj_name]=h[-20:]
    data["total_sessions"]=data.get("total_sessions",0)+1
    today=datetime.now().strftime("%Y-%m-%d"); yesterday=(datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
    s=data.setdefault("streak",{"last_date":"","count":0})
    if s["last_date"]==today: pass
    elif s["last_date"]==yesterday: s["count"]+=1; s["last_date"]=today
    else: s["count"]=1; s["last_date"]=today
    save_stats(data)

def start_practice(force_objection=None, force_industry=None, difficulty=None):
    display,scenario=generate_scenario(force_objection,force_industry,difficulty)
    save_session({"state":"waiting_response","scenario":scenario}); send_telegram(display)

def handle_user_response(user_text):
    session=load_session()
    if not session or session.get("state")!="waiting_response":
        send_telegram("唔係練習模式。用 /practice 開始！"); return
    clear_session(); scenario=session["scenario"]; obj_name=scenario["objection"]
    send_telegram("🤔 AI 評估緊你嘅回應，稍等⋯⋯")
    feedback=evaluate_response(user_text,scenario)
    m=re.search(r"評分[：:]\s*\[?([1-4])\]?",feedback)
    if m: record_score(obj_name,int(m.group(1)))
    send_telegram(feedback,reply_markup={"inline_keyboard":[[
        {"text":"🔄 再練一個","callback_data":"practice_new"},
        {"text":f"🎯 再練「{obj_name}」","callback_data":f"drill_{obj_name}"}]]})

def handle_stats():
    data=load_stats(); scores=data.get("objection_scores",{}); total=data.get("total_sessions",0)
    streak=data.get("streak",{})
    if not scores: send_telegram("未有記錄，用 /practice 開始！"); return
    ranked=sorted([(n,sum(sc)/len(sc),len(sc)) for n,sc in scores.items() if sc],key=lambda x:x[1],reverse=True)
    lines=[f"📊 進度\n總練習：{total}次  連續：{streak.get('count',0)}日\n","【掌握度】"]
    for name,avg,count in ranked:
        lines.append(f"{'█'*round(avg)}{'░'*(4-round(avg))}  {name}  {round(avg/4*100)}%（{count}次）")
    weak=[x for x in ranked if x[1]<2.5]
    if weak: lines.append(f"\n⚠️ 薄弱：{','.join(x[0] for x in weak[:3])}  → /drill")
    send_telegram("\n".join(lines))

def handle_drill_menu():
    keyboard=[]; row=[]
    for obj in OBJECTION_TYPES:
        row.append({"text":obj["name"],"callback_data":f"drill_{obj['name']}"})
        if len(row)==2: keyboard.append(row); row=[]
    if row: keyboard.append(row)
    keyboard.append([{"text":"🎲 隨機","callback_data":"practice_new"}])
    send_telegram("🎯 選擇拒絕類型：",reply_markup={"inline_keyboard":keyboard})

def cmd(text,command): return text==command or text.startswith(command+" ") or text.startswith(command+"@")

def handle_message(text):
    session=load_session()
    if session and session.get("state")=="waiting_response" and not text.startswith("/"):
        threading.Thread(target=handle_user_response,args=(text,),daemon=True).start(); return
    if cmd(text,"/start") or cmd(text,"/help"):
        send_telegram("🥊 銷售話術訓練機器人\n\n/practice — 隨機練習\n/practice 初級／中級／高級\n/drill — 針對類型\n/stats — 進度\n/streak — 連續天數\n/tip — 技巧"); return
    if cmd(text,"/practice"):
        parts=text.split(maxsplit=1); extra=parts[1].strip() if len(parts)>1 else None
        diff=extra if extra in DIFFICULTY_LEVELS else None; ind=extra if extra and extra not in DIFFICULTY_LEVELS else None
        send_telegram("🎯 生成場景⋯⋯")
        threading.Thread(target=start_practice,kwargs={"force_industry":ind,"difficulty":diff},daemon=True).start(); return
    if cmd(text,"/drill"): handle_drill_menu(); return
    if cmd(text,"/stats"): handle_stats(); return
    if cmd(text,"/tip"):
        import random; obj=random.choice(OBJECTION_TYPES)
        send_telegram(f"💡 今日技巧\n\n【{obj['name']}】\n\n{obj['tip']}"); return
    if cmd(text,"/streak"):
        data=load_stats(); s=data.get("streak",{}); count=s.get("count",0)
        send_telegram(f"{'🔥' if count>=7 else '💪' if count>=3 else '🌱'} 連續：{count}日  總練習：{data.get('total_sessions',0)}次"); return

def handle_callback(cb):
    req.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/answerCallbackQuery",
             json={"callback_query_id":cb["id"]},timeout=5)
    data=cb.get("data","")
    if data=="practice_new": threading.Thread(target=start_practice,daemon=True).start()
    elif data.startswith("drill_"):
        threading.Thread(target=start_practice,kwargs={"force_objection":data[6:]},daemon=True).start()

@app.route("/api/webhook",methods=["POST"])
def webhook():
    update=request.json or {}
    if "callback_query" in update: handle_callback(update["callback_query"])
    elif "message" in update:
        text=update["message"].get("text","").strip()
        if text: handle_message(text)
    return jsonify({"ok":True})

@app.route("/",methods=["GET"])
def health(): return "Sales Trainer Bot OK",200

if __name__=="__main__": app.run(debug=False)
