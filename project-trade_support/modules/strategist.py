"""
取引手法考案モジュール - AIによるエントリー/TP/SL提案 + ダブルチェック
"""
import json
from ai.llm_client import LLMClient
from ai.prompts import SYSTEM_PROMPT, STRATEGY_PROPOSAL_PROMPT, SECOND_OPINION_PROMPT
from config.trading_params import RISK_PARAMS
from config.settings import is_configured


class Strategist:
    """取引戦略を提案するクラス"""

    def __init__(self, llm_client: LLMClient | None = None, risk_params: dict | None = None):
        self.llm = llm_client or LLMClient()
        self.risk = risk_params or RISK_PARAMS.copy()

    def generate_proposal(self, analysis_result: dict) -> dict:
        """
        分析結果からAIが取引戦略を提案する

        Args:
            analysis_result: Analyzer.get_ai_analysis() の返り値

        Returns:
            取引提案のdict
        """
        symbol = analysis_result.get("symbol", "N/A")
        current_price = analysis_result.get("current_price", "N/A")
        indicators = analysis_result.get("indicators", {})
        ai_analysis = analysis_result.get("ai_analysis", {})

        # ローソク足データ（直近20本）のサマリー
        candle_summary = self._format_candle_summary(indicators)

        prompt = STRATEGY_PROPOSAL_PROMPT.format(
            symbol=symbol,
            current_price=current_price,
            analysis_result=json.dumps(ai_analysis, indent=2, ensure_ascii=False, default=str),
            max_loss_pct=self.risk.get("max_loss_per_trade_pct", 2.0),
            min_rr_ratio=self.risk.get("min_risk_reward_ratio", 2.0),
            candle_data=candle_summary,
        )

        proposal = self.llm.query_json(prompt, SYSTEM_PROMPT, provider="openai")

        # バリデーション
        proposal = self._validate_proposal(proposal, current_price)

        return {
            "symbol": symbol,
            "current_price": current_price,
            "proposal": proposal,
            "provider": "openai",
        }

    def get_second_opinion(self, proposal: dict, analysis_result: dict) -> dict:
        """
        ダブルチェック - Claude でセカンドオピニオンを取得

        Returns:
            セカンドオピニオンのdict
        """
        if not is_configured("ANTHROPIC_API_KEY"):
            return {"agreement": "skip", "review_comment": "Anthropic APIキーが未設定のためスキップ"}

        indicators = analysis_result.get("indicators", {})
        prompt = SECOND_OPINION_PROMPT.format(
            original_analysis=json.dumps(proposal, indent=2, ensure_ascii=False, default=str),
            technical_data=json.dumps(indicators, indent=2, ensure_ascii=False, default=str),
        )

        return self.llm.query_json(prompt, SYSTEM_PROMPT, provider="anthropic")

    def generate_full_strategy(self, analysis_result: dict) -> dict:
        """
        完全な取引戦略を生成（メイン提案 + セカンドオピニオン + 最終判定）
        """
        # 1. メイン提案（GPT-5）
        main_proposal = self.generate_proposal(analysis_result)

        # 2. セカンドオピニオン（Claude）
        second_opinion = self.get_second_opinion(main_proposal, analysis_result)

        # 3. 最終判定
        final_decision = self._make_final_decision(main_proposal, second_opinion)

        return {
            "symbol": analysis_result.get("symbol", "N/A"),
            "main_proposal": main_proposal,
            "second_opinion": second_opinion,
            "final_decision": final_decision,
        }

    def _validate_proposal(self, proposal: dict, current_price) -> dict:
        """提案のバリデーション"""
        if not proposal or "raw_response" in proposal:
            return proposal

        direction = proposal.get("direction", "skip")
        if direction == "skip":
            return proposal

        # R:Rチェック
        rr = proposal.get("risk_reward_ratio", 0)
        min_rr = self.risk.get("min_risk_reward_ratio", 2.0)

        try:
            rr_float = float(rr) if rr else 0
        except (ValueError, TypeError):
            rr_float = 0

        if rr_float < min_rr and rr_float > 0:
            proposal["warning"] = f"R:R比 ({rr_float:.1f}) が推奨値 (1:{min_rr}) を下回っています"

        return proposal

    def _format_candle_summary(self, indicators: dict) -> str:
        """テクニカル指標データからローソク足サマリーを作成"""
        parts = []
        for key, val in indicators.items():
            if key not in ("error",):
                parts.append(f"- {key}: {json.dumps(val, ensure_ascii=False, default=str)}")
        return "\n".join(parts) if parts else "（データなし）"

    def _make_final_decision(self, main_proposal: dict, second_opinion: dict) -> dict:
        """メイン提案とセカンドオピニオンから最終判定"""
        main_direction = main_proposal.get("proposal", {}).get("direction", "skip")
        agreement = second_opinion.get("agreement", "skip")

        if agreement == "skip":
            # セカンドオピニオン未実行 → メイン提案をそのまま採用
            return {
                "status": "single_check",
                "direction": main_direction,
                "confidence": main_proposal.get("proposal", {}).get("confidence", "low"),
                "message": "セカンドオピニオンなし（APIキー未設定）。メイン分析のみの結果です。",
            }

        if main_direction == "skip":
            return {
                "status": "skip",
                "direction": "skip",
                "confidence": "high",
                "message": "メイン分析が取引見送りと判断しました。",
            }

        if agreement == "agree":
            return {
                "status": "confirmed",
                "direction": main_direction,
                "confidence": "high",
                "message": "✅ 2つのAIモデルが一致。提案を採用します。",
            }
        elif agreement == "partially_agree":
            return {
                "status": "partial",
                "direction": main_direction,
                "confidence": "medium",
                "message": "⚠️ セカンドオピニオンが部分的に同意。注意して検討してください。",
            }
        else:  # disagree
            return {
                "status": "rejected",
                "direction": "skip",
                "confidence": "high",
                "message": "❌ AIモデル間で意見が大きく乖離。取引を見送ります。",
            }
