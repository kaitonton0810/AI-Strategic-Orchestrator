# AI Strategic Orchestrator

**An autonomous multi-agent system that executes MBA-level strategic discussions.***(MBAフレームワークに基づく戦略議論を自律実行するマルチエージェントシステム)*

## 📖 Overview (概要)

**AI Strategic Orchestrator** は、単なるチャットボットではありません。ユーザーがビジネス課題を入力すると、AIによる「プロジェクトマネージャー（PM）」が自律的に最適な専門家チーム（CFO、CTO、戦略コンサルタント等）を編成し、議論をリードして結論を導き出す **「自律型マルチエージェントシステム」** です。

MBAで学ぶ意思決定プロセス（発散・深化・収束）をアルゴリズムに落とし込み、**「AIにコードを書かせる」のではなく「AIにビジネスプロセスを回させる」** ことを目的として設計されました。

> Concept:
Instead of chatting with an AI, you assign a task to a team of AI experts. The system orchestrates the entire discussion autonomously.
> 

## 🚀 Key Features (主な機能)

### 1. Autonomous Agent Orchestration (自律的エージェント指揮)

システム内のPMエージェント（`_pm_brain`）が、議論の文脈を読み取り、**「次に誰が発言すべきか」を自律的に判断**します。

- 例: 予算の話になれば「CFO」を指名し、技術的な懸念が出れば「CTO」を指名します。

### 2. Strategic Phase Management (戦略的フェーズ管理)

議論を以下の3つのフェーズで構造化し、質の高いアウトプットを保証します。

- **Phase 1: DIVERGE (発散)** - アイデアの広がりと可能性の探索
- **Phase 2: DEEPEN (深化)** - 批判的検証、リスク分析、数値的根拠の追求
- **Phase 3: CONVERGE (収束)** - 実行計画への落とし込み

### 3. Real-time Streaming UX (リアルタイム・ストリーミング)

Server-Sent Events (SSE) を実装し、AIエージェントたちが議論している様子（思考プロセス）をリアルタイムで可視化します。ユーザーは「会議を傍聴している」ような体験が得られます。

## 🛠 Architecture & Tech Stack (技術構成)

このシステムは、軽量かつ高速なプロトタイピングを実現するために以下のスタックで構築されています。

| **Layer** | **Technology** | **Description** |
| --- | --- | --- |
| **Frontend** | HTML5, Tailwind CSS | モダンでレスポンシブなUI。marked.jsによるMarkdownレンダリング。 |
| **Backend** | Python (Flask) | エージェント制御ロジックとAPIサーバー。 |
| **Database** | SQLite | 議論ログ、エージェント定義の軽量な永続化。 |
| **AI Engine** | Google Gemini 2.0 Flash | 高速かつ安価な推論エンジン。JSONモードを活用した制御。 |
| **Protocol** | Server-Sent Events (SSE) | 非同期ストリーミング通信。 |

### The "Brain" Logic (`_pm_brain`)

PMエージェントの判断ロジックは以下のように実装されています。

```
# 疑似コード (Pseudo-code)
def _pm_brain(context, current_phase):
    # 議論の履歴と現在のフェーズ(発散/収束)を分析
    analysis = llm.analyze(context, phase=current_phase)

    # 最適な専門家を指名
    next_speaker = analysis.select_expert(from=AGENT_POOL)

    # 具体的な指示出し
    instruction = analysis.generate_instruction()

    return next_speaker, instruction

```

## 💻 Installation & Usage (インストールと使い方)

### Prerequisites

- Python 3.9+
- Google AI Studio API Key

### 1. Clone the repository

```
git clone https://github.com/kaitonton0810/AI-Strategic-Orchestrator.git
cd AI-Strategic-Orchestrator

```

### 2. Setup Environment

`.env` ファイルを作成し、APIキーを設定します。

```
GOOGLE_API_KEY=your_api_key_here

```

### 3. Install Dependencies

```
pip install -r requirements.txt

```

### 4. Run

```
python server.py

```

Access `http://localhost:5050` in your browser.

## 🧠 Why I Built This (開発の背景)

ビジネスの現場において、意思決定には多角的な視点（財務、技術、リスク管理など）が不可欠です。しかし、専門家を集めて会議を行うコストは非常に高いのが現状です。

私は自身のMBAでの学びとコンサルティング経験をソフトウェア化できないかと考えました。「要件定義」さえ的確であれば、生成AIはコーディングだけでなく、高度なビジネスロジックの実行も可能です。

このプロジェクトは、**「非エンジニアがドメイン知識（専門知識）を武器に、AIを活用してSaaSレベルのシステムを爆速（約8時間）で構築する」** という、次世代の開発スタイルの実証実験でもあります。

## 👤 Author

**Kaito Shioya**

- Business Strategist / MBA Candidate
- AI-Native Developer
