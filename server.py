import json
import re
import time
import sqlite3
import uuid
import os
import traceback
from datetime import datetime
from flask import Flask, request, Response, jsonify, stream_with_context
from flask_cors import CORS
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv

# ==========================================
# 環境設定 & セキュリティ
# ==========================================
# .envファイルから環境変数を読み込む
load_dotenv()

# APIキーの取得とチェック
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Error: API Key not found. Please set GOOGLE_API_KEY in .env file.")

genai.configure(api_key=GOOGLE_API_KEY)

# 設定値
PORT = int(os.getenv("PORT", 5050))
DB_PATH = "discussions.db"
AGENTS_FILE = "agents.json"
MODEL_NAME = "gemini-2.0-flash"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 安全性フィルター（ブロック回避のため緩和）
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# ==========================================
# DB & データロード
# ==========================================
def init_db():
    """データベースとテーブルの初期化"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS discussions (id TEXT PRIMARY KEY, task TEXT, goal TEXT, status TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, discussion_id TEXT, sender TEXT, content TEXT, timestamp TEXT, FOREIGN KEY(discussion_id) REFERENCES discussions(id))")
        conn.execute("CREATE TABLE IF NOT EXISTS roles (discussion_id TEXT, role_name TEXT, description TEXT, agent_id TEXT, FOREIGN KEY(discussion_id) REFERENCES discussions(id))")

def load_agent_pool():
    """エージェント定義ファイルの読み込み"""
    if not os.path.exists(AGENTS_FILE):
        return [] 
    with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# アプリ起動時に実行
init_db()
AGENT_POOL = load_agent_pool()

# ==========================================
# LLM クライアント
# ==========================================
class LLMClient:
    def generate_sync(self, prompt, temperature=0.7, json_mode=False):
        try:
            generation_config = {"temperature": temperature}
            if json_mode:
                generation_config["response_mime_type"] = "application/json"

            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=SAFETY_SETTINGS
            )
            
            if not response.parts:
                return "{}" if json_mode else "Error: Blocked content."
            return response.text.strip()
        except Exception as e:
            print(f"Gemini Sync Error: {e}")
            return "{}" if json_mode else f"Error: {str(e)}"

    def generate_stream(self, prompt, temperature=0.7):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(
                prompt,
                stream=True,
                generation_config={"temperature": temperature},
                safety_settings=SAFETY_SETTINGS
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"Gemini Stream Error: {e}")
            yield f"\n[System Error: {str(e)}]"

llm = LLMClient()

# ==========================================
# ビジネスロジック (Discussion Service)
# ==========================================
class DiscussionService:
    def create_discussion(self, task):
        discussion_id = str(uuid.uuid4())
        
        # 1. Team Selection
        selected_agents = self._select_best_team(task)
        
        # 2. Goal Setting
        goal = self._define_strategic_goal(task)
        
        # 3. DB Save & Initial Message
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO discussions VALUES (?, ?, ?, ?, ?)",
                         (discussion_id, task, goal, "active", datetime.now().isoformat()))
            
            roles_desc = {}
            for agent in selected_agents:
                conn.execute("INSERT INTO roles VALUES (?, ?, ?, ?)",
                             (discussion_id, agent['role'], agent['description'], agent['id']))
                roles_desc[agent['role']] = agent['description']
            
            pm_msg = f"プロジェクトを開始します。\n\n【戦略ゴール定義】\n{goal}\n\n【アサインされた専門家チーム（5名）】\n" + \
                     "\n".join([f"・{a['role']}" for a in selected_agents])
            self._save_msg(conn, discussion_id, "PM", pm_msg)
            
        return discussion_id, roles_desc, goal, pm_msg

    def _select_best_team(self, task):
        simple_pool = [{"id": a["id"], "role": a["role"], "desc": a["description"][:50]} for a in AGENT_POOL]
        
        prompt = f"""
Task: {task}
Candidates: {json.dumps(simple_pool, ensure_ascii=False)}

Select exactly 5 expert IDs best suited for this task.
Return JSON list of strings ONLY. Example: ["id1", "id2", "id3", "id4", "id5"]
"""
        res = llm.generate_sync(prompt, temperature=0.1, json_mode=True)
        try:
            match = re.search(r'\[.*?\]', res, re.DOTALL)
            ids = json.loads(match.group(0)) if match else json.loads(res)
            selected = [a for a in AGENT_POOL if a['id'] in ids]
            
            # 不足分の補填ロジック
            if len(selected) < 5:
                defaults = ['strategy_consultant', 'financial_controller', 'tech_lead', 'marketing_strategist', 'risk_manager']
                existing = {a['id'] for a in selected}
                for d in defaults:
                    if d not in existing and len(selected) < 5:
                        fallback = next((a for a in AGENT_POOL if a['id'] == d), None)
                        if fallback: selected.append(fallback)
            return selected[:5]
        except:
            # エラー時のフォールバック
            defaults = ['strategy_consultant', 'financial_controller', 'tech_lead', 'marketing_strategist', 'risk_manager']
            return [a for a in AGENT_POOL if a['id'] in defaults]

    def _define_strategic_goal(self, task):
        prompt = f"""
Task: {task}
Define a Strategic Business Goal (Japanese Markdown).
Sections: Vision, Quantitative Goal, Target, Value Proposition, Execution Plan.
"""
        return llm.generate_sync(prompt, temperature=0.7)

    def run_stream(self, discussion_id):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            disc = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
            roles_rows = conn.execute("SELECT * FROM roles WHERE discussion_id = ?", (discussion_id,)).fetchall()
            
            roles_map = {}
            for r in roles_rows:
                agent_def = next((a for a in AGENT_POOL if a['id'] == r['agent_id']), None)
                roles_map[r['role_name']] = agent_def if agent_def else {'style': 'Expert', 'frameworks': []}

        if not disc: return

        task = disc['task']
        goal = disc['goal']
        last_speaker = "PM"
        total_turns = 10 

        for turn in range(1, total_turns + 1):
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    msgs = conn.execute("SELECT * FROM messages WHERE discussion_id = ? ORDER BY id ASC", (discussion_id,)).fetchall()
                
                history_text = "\n".join([f"[{m['sender']}]: {m['content'][:200]}..." for m in msgs[-10:]])

                # フェーズ管理
                if turn <= 3: phase = "DIVERGE (Ideation)"
                elif turn <= 7: phase = "DEEPEN (Critique & Feasibility)"
                else: phase = "CONVERGE (Planning)"

                yield self._sse_event("status", f"Phase: {phase} - PM Coordinating...")

                # PMの意思決定
                candidates = list(roles_map.keys())
                pm_decision = self._pm_brain(task, phase, history_text, candidates, last_speaker)
                
                next_role = pm_decision['next_speaker']
                instruction = pm_decision['instruction']
                
                if next_role not in roles_map:
                    next_role = candidates[turn % len(candidates)]

                last_speaker = next_role

                # PM発言送信
                pm_content = f"({phase}) {next_role}さん、{instruction}"
                with sqlite3.connect(DB_PATH) as conn:
                    self._save_msg(conn, discussion_id, "PM", pm_content)
                yield self._sse_event("message", json.dumps({"sender": "PM", "content": pm_content, "type": "pm"}))

                # Expert発言生成
                yield self._sse_event("status", f"{next_role} is thinking...")
                
                agent_prompt = self._construct_agent_prompt(next_role, roles_map.get(next_role, {}), instruction, history_text, task, phase)
                
                yield self._sse_event("stream_start", json.dumps({"sender": next_role, "type": "agent"}))
                
                full_response = ""
                for token in llm.generate_stream(agent_prompt):
                    full_response += token
                    yield self._sse_event("stream_chunk", json.dumps({"token": token}))
                
                yield self._sse_event("stream_end", "")
                
                with sqlite3.connect(DB_PATH) as conn:
                    self._save_msg(conn, discussion_id, next_role, full_response)
                
                time.sleep(0.5)

            except Exception as e:
                print(f"Turn Error: {e}")
                continue

        # 最終レポート生成
        yield self._sse_event("status", "Synthesizing Final Strategic Report...")
        report = self._generate_report(discussion_id, task, goal)
        yield self._sse_event("finished", report)

    def _pm_brain(self, task, phase, history, candidates, last_speaker):
        candidates_str = json.dumps([c for c in candidates if c != last_speaker], ensure_ascii=False)
        prompt = f"""
Task: {task}
Phase: {phase}
History: {history}
Available Experts: {candidates_str}
Decide the NEXT speaker and provide a specific question in Japanese.
Output JSON: {{ "next_speaker": "ExactRoleName", "instruction": "Japanese Text" }}
"""
        res = llm.generate_sync(prompt, temperature=0.5, json_mode=True)
        try:
            match = re.search(r'\{.*\}', res, re.DOTALL)
            return json.loads(match.group(0)) if match else json.loads(res)
        except:
            return {"next_speaker": candidates[0], "instruction": "意見をお願いします。"}

    def _construct_agent_prompt(self, role, agent_def, instruction, history, task, phase):
        return f"""
You are {role}. Style: {agent_def.get('style', 'Expert')}. Frameworks: {", ".join(agent_def.get('frameworks', []))}.
Task: {task}
Phase: {phase}
History: {history}
Instruction: "{instruction}"
Respond in Japanese. Be specific and professional.
"""

    def _generate_report(self, did, task, goal):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            msgs = conn.execute("SELECT * FROM messages WHERE discussion_id = ?", (did,)).fetchall()
        full_log = "\n".join([f"{m['sender']}: {m['content']}" for m in msgs])
        
        prompt = f"""
Task: {task}
Goal: {goal}
Log: {full_log}
Generate a comprehensive "Strategic Execution Plan" in Japanese Markdown.
Structure: Executive Summary, Discussion Synthesis, Strategic Framework, Risk Analysis, Action Plan.
"""
        return llm.generate_sync(prompt, temperature=0.3)

    def _save_msg(self, conn, did, sender, content):
        conn.execute("INSERT INTO messages (discussion_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
                     (did, sender, content, datetime.now().isoformat()))

    def _sse_event(self, event_type, data):
        data_str = str(data).replace('\n', '\\n')
        return f"event: {event_type}\ndata: {data_str}\n\n"

service = DiscussionService()

# ==========================================
# ルーティング
# ==========================================
@app.route('/start', methods=['POST'])
def start():
    task = request.json.get("task")
    if not task: return jsonify({"error": "Task required"}), 400
    did, roles, goal, pm_msg = service.create_discussion(task)
    return jsonify({"id": did, "roles": roles, "goal": goal, "initial_message": pm_msg})

@app.route('/stream/<discussion_id>', methods=['GET'])
def stream(discussion_id):
    return Response(stream_with_context(service.run_stream(discussion_id)), content_type='text/event-stream')

if __name__ == '__main__':
    print(f"Starting Server on port {PORT}...")
    app.run(port=PORT, debug=True, threaded=True)