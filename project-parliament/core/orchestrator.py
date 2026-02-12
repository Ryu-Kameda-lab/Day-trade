"""議論フロー制御 - DiscussionOrchestrator"""
import uuid
from datetime import datetime
from typing import List, Optional, Callable, Any

import gevent

from models.message import Message, MessageType
from models.analysis import MultiTimeframeAnalysis
from config import AI_PROFILES


# 発言順序定義
SPEAKING_ORDER = [
    # 1. 調査員が市場分析を提示
    "gpt_worker_1",
    "gpt_worker_2",
    "gem_worker",
    # 2. クリティック/提案役が反証・提案
    "gpt_critic_1",
    "gpt_critic_2",
    "gem_proposer",
    # 3. リーダー2体がまとめ
    "gpt_leader",
    "gem_leader",
    # 4. Claude議長が進行判断
    "claude_chair",
]

# 役割別システムプロンプト
ROLE_PROMPTS = {
    "worker": (
        "あなたは仮想通貨トレーディングチームの調査員です。"
        "MEXC取引所から取得した市場データと、自動算出されたテクニカル指標を活用して分析してください。\n\n"
        "提供されるテクニカル指標:\n"
        "- RSI（14期間）: 30以下=売られすぎ（買い検討）、70以上=買われすぎ（売り検討）\n"
        "- MACD: ヒストグラムが正→負はデッドクロス（弱気）、負→正はゴールデンクロス（強気）\n"
        "- EMA（9/21/50/200期間）: 短期>中期>長期=上昇トレンド、その逆=下降トレンド\n"
        "- ボリンジャーバンド: 上限到達=過熱、下限到達=売られすぎ、スクイーズ=ブレイクアウト間近\n"
        "- 出来高比率: 平均の2倍以上=注目度上昇\n\n"
        "分析の視点:\n"
        "- テクニカル指標の複合シグナル（複数が同方向を示す場合は確度が高い）\n"
        "- RSIとMACDの「ダイバージェンス」の有無\n"
        "- 出来高を伴ったトレンド変化\n\n"
        "あなたが選んだ通貨ペアについて、以下を含めて分析結果を提示してください:\n"
        "- 選定した通貨ペアとその理由（テクニカル指標の根拠を含む）\n"
        "- エントリーポイント（価格）\n"
        "- 利確目標（価格）\n"
        "- 損切りライン（価格）\n"
        "- リスクリワード比"
    ),
    "critic": (
        "あなたは仮想通貨トレーディングチームの監査役です。"
        "直前の分析に対して、リスクや見落としている点を指摘してください。"
        "反証データや代替シナリオを提示し、過度に楽観的な分析に歯止めをかけてください。"
        "ただし建設的な批判を心がけ、代替案があれば併せて提示してください。"
    ),
    "leader": (
        "あなたは仮想通貨トレーディングチームのリーダーです。"
        "チームメンバーの分析と監査結果を総合的にまとめてください。"
        "合意点と分岐点を明確にし、トレード提案が可能であれば稟議書の草案を提示してください。"
        "以下の形式で稟議書を提示してください:\n"
        "- 戦略: long / short\n"
        "- 通貨ペア: (例: BTC/USDT)\n"
        "- エントリー価格: \n"
        "- 利確目標: \n"
        "- 損切りライン: \n"
        "- 根拠: \n"
    ),
    "proposer": (
        "あなたは仮想通貨トレーディングチームの提案役です。"
        "調査員の分析結果とクリティックの指摘を踏まえ、"
        "具体的なトレード戦略を提案してください。"
        "エントリー価格、利確目標、損切りライン、ポジションサイズの根拠を"
        "明確に示し、リスクリワード比を計算してください。"
    ),
    "chair": (
        "あなたはAI議会の議長（Claude）です。"
        "全ての議論を俯瞰し、以下の判断を行ってください:\n"
        "1. 議論が十分に成熟しているか\n"
        "2. 稟議書の提出に進むべきか、さらに議論が必要か\n"
        "3. 追加で検討すべき論点があるか\n\n"
        "判断結果を以下の形式で示してください:\n"
        "[DECISION: PROPOSE] - 稟議書を提出する\n"
        "[DECISION: CONTINUE] - さらに議論を続行する\n"
        "[DECISION: ABORT] - 議論を終了する（トレード機会なし）\n"
    ),
}


class DiscussionOrchestrator:
    """議論フローを制御するオーケストレーター"""

    def __init__(self, ai_manager: Any, emit_callback: Callable, proposal_manager: Any = None):
        """
        Args:
            ai_manager: AIManagerインスタンス（AI呼び出し用）
            emit_callback: SocketIO emit用コールバック関数
            proposal_manager: ProposalManagerインスタンス（稟議書作成用、オプション）
        """
        self.ai_manager = ai_manager
        self.emit = emit_callback
        self.proposal_manager = proposal_manager
        self.round_count = 0
        self.max_rounds = 3
        self.discussion_history: List[Message] = []
        self.is_running = False
        self.market_data: Optional[dict] = None
        self.screening_results: Optional[List[MultiTimeframeAnalysis]] = None
        self.last_decision = "ABORT"

    def start_discussion(
        self,
        market_data: Optional[dict] = None,
        screening_results: Optional[list] = None,
    ) -> str:
        """議論を開始する（同期版 - gevent greenlet内で実行）"""
        self.market_data = market_data
        self.screening_results = screening_results
        self.round_count = 0
        self.discussion_history = []
        self.is_running = True
        self.last_decision = "ABORT"

        if screening_results:
            self._emit_system_message(
                f"MEXC市場スクリーニング完了。スコア上位 {len(screening_results)} ペアの"
                "テクニカル分析データを各AIに共有します。"
            )
        else:
            self._emit_system_message("MEXC市場データを取得しました。各AIが順番に分析を提示します。")

        while self.is_running and self.round_count < self.max_rounds:
            self.round_count += 1
            self._emit_system_message(
                f"--- ラウンド {self.round_count}/{self.max_rounds} ---"
            )
            decision = self.run_round()
            self.last_decision = decision

            if decision == "PROPOSE":
                self._emit_system_message("議長の判断: 稟議書を提出します。")
                # 議長に最終稟議書を作成させる
                proposal_data = self._create_final_proposal()
                if proposal_data:
                    # 稟議書を提出
                    self.emit("submit_proposal", proposal_data)
                break
            elif decision == "ABORT":
                self._emit_system_message(
                    "議長の判断: トレード機会なし。議論を終了します。"
                )
                self.is_running = False
                break
            # "CONTINUE" の場合は次のラウンドへ

        if self.round_count >= self.max_rounds and self.is_running:
            self._emit_system_message(
                f"最大ラウンド数（{self.max_rounds}）に達しました。"
                "議長に最終判断を求めます。"
            )
        self.is_running = False
        return self.last_decision

    def run_round(self) -> str:
        """
        1ラウンド実行。発言順序に沿って各AIを呼び出す。
        Returns: 議長の判断 ("PROPOSE" / "CONTINUE" / "ABORT")
        """
        speaking_order = self.get_speaking_order()

        for ai_id in speaking_order:
            if not self.is_running:
                break

            profile = AI_PROFILES.get(ai_id)
            if not profile:
                continue

            # オンライン確認
            if not self.ai_manager.is_online(ai_id):
                continue

            # 発言中通知
            self.emit("ai_speaking", {"ai_id": ai_id, "speaking": True})

            # プロンプト構築
            system_prompt = self._build_system_prompt(ai_id, profile)
            user_prompt = self._build_user_prompt(ai_id, profile)

            # AI呼び出し（同期・画像なし）
            response = self.ai_manager.send_message(
                ai_id=ai_id,
                content=user_prompt,
                system_prompt=system_prompt,
            )

            if response is None:
                response = f"（{profile['name']}からの応答がありませんでした）"

            # メッセージ作成・記録
            message = Message(
                id=str(uuid.uuid4()),
                type=MessageType.AI_MESSAGE,
                ai_id=ai_id,
                ai_name=profile["name"],
                icon=profile["icon"],
                avatar_color=profile["avatar_color"],
                content=response,
                timestamp=datetime.now(),
                metadata={"round": self.round_count, "role": profile["role"]},
            )
            self.discussion_history.append(message)

            # フロントエンドに送信
            self.emit("new_message", message.to_dict())
            self.emit("ai_speaking", {"ai_id": ai_id, "speaking": False})

            # gevent に制御を渡す（UIの更新を確保）
            gevent.sleep(0.1)

        # 議長の判断をパース
        return self._parse_chair_decision()

    def get_speaking_order(self) -> List[str]:
        """発言順序リストを返す"""
        return list(SPEAKING_ORDER)

    def stop(self):
        """議論を強制停止"""
        self.is_running = False

    def _build_system_prompt(self, ai_id: str, profile: dict) -> str:
        """役割に応じたシステムプロンプトを構築"""
        role = profile["role"]
        base_prompt = ROLE_PROMPTS.get(role, "")
        name_context = (
            f"あなたの名前は「{profile['name']}」、"
            f"役割は「{profile['role_label']}」です。\n\n"
        )
        return name_context + base_prompt

    def _build_user_prompt(self, ai_id: str, profile: dict) -> str:
        """市場データ・テクニカル分析と直前の議論内容を含むユーザープロンプトを構築"""
        role = profile["role"]

        # テクニカル分析データ（スクリーニング結果がある場合）
        analysis_text = self._format_analysis_table() if self.screening_results else ""

        if not self.discussion_history:
            if role == "worker":
                # workerにはテクニカル分析付き市場データを提示
                market_table = self._format_market_data_table()
                prompt = (
                    f"以下はMEXC取引所から取得したリアルタイムの市場データです（USDT建てペア、出来高順）:\n\n"
                    f"{market_table}\n\n"
                )
                if analysis_text:
                    prompt += (
                        f"以下は自動算出されたテクニカル分析結果です:\n\n"
                        f"{analysis_text}\n\n"
                    )
                prompt += (
                    "上記のテクニカル指標を参考に、デイトレードで利益を獲得できそうな銘柄を選定し、"
                    "その銘柄について詳細なトレードシナリオを提示してください。"
                )
                return prompt
            return "議論が始まったばかりです。他のメンバーの発言を待ってから発言してください。"

        # 直近の議論をコンテキストとして含める
        recent_messages = self.discussion_history[-10:]
        context_lines = []
        for msg in recent_messages:
            context_lines.append(
                f"[{msg.ai_name}（{msg.metadata.get('role', '')}）]: {msg.content}"
            )
        context = "\n\n".join(context_lines)

        if role == "worker":
            market_table = self._format_market_data_table()
            prompt = f"現在の市場データ:\n{market_table}\n\n"
            if analysis_text:
                prompt += f"テクニカル分析:\n{analysis_text}\n\n"
            prompt += (
                f"これまでの議論:\n{context}\n\n"
                "上記を踏まえて、テクニカル指標を根拠にした追加分析を提示してください。"
            )
            return prompt
        elif role == "critic":
            return (
                f"これまでの議論:\n{context}\n\n"
                "上記の分析に対して、テクニカル指標の解釈に問題がないか、"
                "リスクや見落としている点を指摘し、反証を提示してください。"
            )
        elif role == "proposer":
            return (
                f"これまでの議論:\n{context}\n\n"
                "調査員の分析とクリティックの指摘を踏まえ、具体的なトレード戦略を提案してください。"
                "テクニカル指標を根拠にしたエントリー/利確/損切ポイントを明示してください。"
            )
        elif role == "leader":
            return (
                f"これまでの議論:\n{context}\n\n"
                "上記の分析と反証を総合し、チームとしてのまとめを提示してください。"
                "トレード提案が可能であれば稟議書の草案を含めてください。"
            )
        else:  # chair
            return (
                f"これまでの議論:\n{context}\n\n"
                "全ての議論を総合し、稟議書の提出に進むべきか判断してください。"
                "判断は [DECISION: PROPOSE] / [DECISION: CONTINUE] / [DECISION: ABORT] で示してください。"
            )

    def _format_market_data_table(self) -> str:
        """市場データをテーブル形式で整形"""
        if not self.market_data or not self.market_data.get("pairs"):
            return "（市場データがありません）"

        pairs = self.market_data.get("pairs", [])
        lines = ["通貨ペア       | 現在価格    | 変動率   | 高値        | 安値        | 出来高(USDT)"]
        lines.append("-" * 85)

        for p in pairs[:30]:  # 上位30件に制限
            symbol = p["symbol"].ljust(14)
            price = f"${p['price']:.6g}".ljust(11)
            change = f"{p['change_percent']:+.2f}%".ljust(8)
            high = f"${p['high']:.6g}".ljust(11)
            low = f"${p['low']:.6g}".ljust(11)
            vol = f"${p['volume_usdt']:,.0f}"
            lines.append(f"{symbol} | {price} | {change} | {high} | {low} | {vol}")

        total = self.market_data.get("total_pairs", 0)
        lines.append(f"\n（全{total}ペア中、出来高上位{len(pairs)}ペアを表示。上記は抜粋版）")

        return "\n".join(lines)

    def _format_analysis_table(self) -> str:
        """スクリーニング結果をテクニカル分析テーブルとして整形する"""
        if not self.screening_results:
            return "（テクニカル分析データがありません）"

        lines = []
        for rank, result in enumerate(self.screening_results, 1):
            lines.append(f"\n━━━ #{rank} {result.symbol} (スコア: {result.overall_score}/100) ━━━")

            for tf in ["15m", "1h", "4h"]:
                tf_analysis = result.analyses.get(tf)
                if not tf_analysis:
                    continue

                ind = tf_analysis.indicators
                parts = []
                if ind.rsi is not None:
                    parts.append(f"RSI={ind.rsi}")
                if ind.macd and ind.macd.get("histogram") is not None:
                    parts.append(f"MACD_hist={ind.macd['histogram']}")
                if ind.ema:
                    for k, v in ind.ema.items():
                        if v is not None:
                            parts.append(f"{k.upper()}={v}")
                if ind.bollinger:
                    bb = ind.bollinger
                    if bb.get("upper") is not None:
                        parts.append(f"BB_upper={bb['upper']}")
                    if bb.get("lower") is not None:
                        parts.append(f"BB_lower={bb['lower']}")
                if ind.volume_ratio is not None:
                    parts.append(f"出来高比={ind.volume_ratio}x")

                if parts:
                    lines.append(f"  [{tf}] {' | '.join(parts)}")

                # シグナル（上位3件）
                if tf_analysis.signals:
                    for sig in tf_analysis.signals[:3]:
                        lines.append(f"    ● {sig}")

        return "\n".join(lines)

    def _parse_chair_decision(self) -> str:
        """議長の最後の発言から判断をパースする"""
        for msg in reversed(self.discussion_history):
            if msg.ai_id == "claude_chair":
                content = msg.content.upper()
                if "[DECISION: PROPOSE]" in content:
                    return "PROPOSE"
                elif "[DECISION: ABORT]" in content:
                    return "ABORT"
                elif "[DECISION: CONTINUE]" in content:
                    return "CONTINUE"
                break
        return "CONTINUE"

    def _create_final_proposal(self) -> Optional[dict]:
        """
        議長に最終稟議書を作成させ、構造化データとして返す

        Returns:
            稟議書データの辞書、または None（作成失敗時）
        """
        self._emit_system_message("議長が最終稟議書を作成しています...")

        # 議論履歴を要約
        recent_messages = self.discussion_history[-15:]
        context_lines = []
        for msg in recent_messages:
            if msg.type == MessageType.AI_MESSAGE:
                context_lines.append(f"[{msg.ai_name}]: {msg.content}")
        context = "\n\n".join(context_lines)

        # 議長に稟議書作成を依頼
        proposal_prompt = f"""これまでの議論:
{context}

上記の議論を踏まえ、最終稟議書を作成してください。
以下のフォーマットに**厳密に従って**出力してください:

---PROPOSAL---
STRATEGY: long または short
PAIR: 通貨ペア（例: BTCUSDT）
ENTRY_PRICE: エントリー価格（数値のみ）
TAKE_PROFIT: 利確目標価格（数値のみ）
STOP_LOSS: 損切り価格（数値のみ）
REASONING: トレード根拠（100文字程度）
---END---

重要: 上記フォーマットを必ず守ってください。数値は数字のみで、通貨記号や単位は不要です。
"""

        system_prompt = "あなたはAI議会の議長（Claude）です。議論を総括し、最終稟議書を作成してください。"

        response = self.ai_manager.send_message(
            ai_id="claude_chair",
            content=proposal_prompt,
            system_prompt=system_prompt,
        )

        if not response:
            self._emit_system_message("議長からの応答がありませんでした。稟議書作成を中止します。")
            return None

        # 稟議書をパース
        proposal_data = self._parse_proposal_text(response)

        if proposal_data:
            self._emit_system_message(f"稟議書を作成しました: {proposal_data['pair']} {proposal_data['strategy'].upper()}")
            return proposal_data
        else:
            self._emit_system_message("稟議書のパースに失敗しました。")
            return None

    def _parse_proposal_text(self, text: str) -> Optional[dict]:
        """
        議長の返答から稟議書データをパースする

        Args:
            text: 議長の返答テキスト

        Returns:
            稟議書データの辞書、または None（パース失敗時）
        """
        import re

        try:
            # フォーマットマーカーを探す
            if "---PROPOSAL---" not in text or "---END---" not in text:
                return None

            # PROPOSAL部分を抽出
            match = re.search(r"---PROPOSAL---(.*?)---END---", text, re.DOTALL)
            if not match:
                return None

            proposal_section = match.group(1)

            # 各フィールドを抽出
            strategy_match = re.search(r"STRATEGY:\s*(long|short)", proposal_section, re.IGNORECASE)
            pair_match = re.search(r"PAIR:\s*([A-Z0-9/]+)", proposal_section, re.IGNORECASE)
            entry_match = re.search(r"ENTRY_PRICE:\s*([\d.]+)", proposal_section)
            tp_match = re.search(r"TAKE_PROFIT:\s*([\d.]+)", proposal_section)
            sl_match = re.search(r"STOP_LOSS:\s*([\d.]+)", proposal_section)
            reasoning_match = re.search(r"REASONING:\s*(.+?)(?=\n---|$)", proposal_section, re.DOTALL)

            if not all([strategy_match, pair_match, entry_match, tp_match, sl_match, reasoning_match]):
                return None

            # ペア名を正規化（BTCUSDT → BTC/USDT）
            pair = pair_match.group(1).strip()
            if "/" not in pair and "USDT" in pair:
                pair = pair.replace("USDT", "/USDT")

            return {
                "submitted_by": "claude_chair",
                "strategy": strategy_match.group(1).lower(),
                "pair": pair,
                "entry_price": float(entry_match.group(1)),
                "take_profit": float(tp_match.group(1)),
                "stop_loss": float(sl_match.group(1)),
                "reasoning": reasoning_match.group(1).strip(),
            }
        except (ValueError, AttributeError) as e:
            return None

    def _emit_system_message(self, content: str):
        """システムメッセージを送信"""
        msg = Message(
            id=str(uuid.uuid4()),
            type=MessageType.SYSTEM,
            ai_id="system",
            ai_name="System",
            icon="",
            avatar_color="#6b7280",
            content=content,
            timestamp=datetime.now(),
        )
        self.discussion_history.append(msg)
        self.emit("new_message", msg.to_dict())
