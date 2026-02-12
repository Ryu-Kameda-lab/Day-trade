"""
Project Parliament - トレード事後分析レポーター
クローズ済みトレードに対してAI分析レポートを生成する。
"""
import uuid
from datetime import datetime

from models.report import TradeReport
from models.trade import TradeRecord
from utils.logger import get_logger

logger = get_logger("TradeReporter")


class TradeReporter:
    """クローズ済みトレードの事後分析レポートを生成する"""

    def __init__(self, ai_manager, mexc_service, analyzer, emit_callback=None):
        """
        Args:
            ai_manager: AIManager インスタンス（レポート生成用AI呼び出し）
            mexc_service: MEXCService インスタンス（クローズ時データ取得）
            analyzer: TechnicalAnalyzer インスタンス（クローズ時テクニカル分析）
            emit_callback: WebSocket 送信コールバック
        """
        self.ai_manager = ai_manager
        self.mexc = mexc_service
        self.analyzer = analyzer
        self.emit = emit_callback
        self.reports: dict = {}  # report_id -> TradeReport

    def generate_report(self, trade: TradeRecord) -> TradeReport:
        """
        クローズ済みトレードの事後分析レポートを生成する。

        手順:
            1. クローズ時点のテクニカル指標を取得
            2. エントリー時 vs クローズ時の指標を比較
            3. AIにレポート作成を依頼
            4. 構造化レポートを保存

        Args:
            trade: クローズ済みの TradeRecord

        Returns:
            TradeReport
        """
        logger.info("レポート生成開始: %s (%s)", trade.trade_id, trade.symbol)

        # 1. クローズ時点のテクニカル分析
        exit_analysis = self._get_exit_analysis(trade.symbol)

        # 2. エントリー時の分析（price_historyの最初のスナップショットから復元）
        entry_analysis = self._get_entry_analysis(trade)

        # 3. 保有期間の計算
        duration = self._calc_duration(trade)

        # 4. AIによる分析テキスト生成
        ai_analysis, lessons = self._generate_ai_analysis(
            trade, entry_analysis, exit_analysis,
        )

        # 5. 価格推移サマリー
        price_summary = self._summarize_price_history(trade)

        # 6. レポート作成
        report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
        report = TradeReport(
            report_id=report_id,
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            strategy=trade.strategy,
            pnl=trade.pnl or 0,
            pnl_percent=trade.pnl_percent or 0,
            duration=duration,
            entry_price=trade.entry_price,
            close_price=trade.close_price or 0,
            close_reason=trade.close_reason or "unknown",
            entry_analysis=entry_analysis,
            exit_analysis=exit_analysis,
            ai_analysis=ai_analysis,
            lessons_learned=lessons,
            price_history_summary=price_summary,
            created_at=datetime.now(),
        )

        self.reports[report_id] = report
        trade.report_id = report_id

        logger.info(
            "レポート生成完了: %s | %s | P/L: %s",
            report_id, trade.symbol, report.result_label,
        )

        # WebSocket通知
        if self.emit:
            try:
                self.emit("report_generated", report.to_dict())
            except Exception as e:
                logger.warning("レポート通知の送信エラー: %s", e)

        return report

    def get_report(self, report_id: str) -> dict:
        """レポートを取得する"""
        report = self.reports.get(report_id)
        return report.to_dict() if report else None

    def get_all_reports(self) -> list:
        """全レポートのサマリーリストを返す"""
        return [
            {
                "report_id": r.report_id,
                "trade_id": r.trade_id,
                "symbol": r.symbol,
                "pnl": r.pnl,
                "pnl_percent": r.pnl_percent,
                "result_label": r.result_label,
                "close_reason": r.close_reason_label,
                "duration": r.duration,
                "created_at": r.created_at.isoformat(),
            }
            for r in sorted(
                self.reports.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
        ]

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------
    def _get_exit_analysis(self, symbol: str) -> dict:
        """クローズ時点のテクニカル指標を取得する"""
        try:
            klines = self.mexc.get_klines(symbol, "1h", 100)
            analysis = self.analyzer.analyze(klines, symbol, "1h")
            return analysis.indicators.to_dict()
        except Exception as e:
            logger.warning("クローズ時分析の取得エラー (%s): %s", symbol, e)
            return {}

    def _get_entry_analysis(self, trade: TradeRecord) -> dict:
        """エントリー時の分析データを復元する"""
        if trade.price_history and len(trade.price_history) > 0:
            first = trade.price_history[0]
            return {
                "rsi": first.rsi,
                "macd_histogram": first.macd_histogram,
                "volume_ratio": first.volume_ratio,
                "price": first.price,
            }
        return {"price": trade.entry_price}

    def _calc_duration(self, trade: TradeRecord) -> str:
        """保有期間を人間が読める形式で返す"""
        if not trade.closed_at:
            return "不明"
        delta = trade.closed_at - trade.opened_at
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}時間{minutes}分"
        return f"{minutes}分"

    def _generate_ai_analysis(
        self,
        trade: TradeRecord,
        entry_analysis: dict,
        exit_analysis: dict,
    ) -> tuple:
        """AIに事後分析を依頼する"""
        prompt = self._build_report_prompt(trade, entry_analysis, exit_analysis)

        try:
            # 議長AI（claude_chair）でレポート生成
            response = self.ai_manager.send_message(
                ai_id="claude_chair",
                system_prompt=(
                    "あなたはプロのトレードアナリストです。"
                    "クローズ済みトレードの詳細データを分析し、以下の2つのセクションに分けてレポートを作成してください。\n\n"
                    "【分析】セクション: このトレードの結果とその要因を説明してください。"
                    "テクニカル指標の変化がどう結果に影響したかを考察してください。\n\n"
                    "【改善ポイント】セクション: 次回のトレードに向けた具体的な改善点を提示してください。"
                ),
                user_prompt=prompt,
            )

            # レスポンスを分割
            ai_text = response.get("content", "分析生成に失敗しました。")
            analysis = ai_text
            lessons = ""

            # 「改善ポイント」セクションを分離
            if "【改善ポイント】" in ai_text:
                parts = ai_text.split("【改善ポイント】", 1)
                analysis = parts[0].replace("【分析】", "").strip()
                lessons = parts[1].strip()
            elif "改善ポイント" in ai_text:
                parts = ai_text.split("改善ポイント", 1)
                analysis = parts[0].strip()
                lessons = parts[1].strip()

            return analysis, lessons

        except Exception as e:
            logger.warning("AI分析の生成エラー: %s", e)
            # フォールバック: 基本的な統計情報のみ
            fallback_analysis = self._generate_fallback_analysis(trade)
            return fallback_analysis, ""

    def _build_report_prompt(
        self,
        trade: TradeRecord,
        entry_analysis: dict,
        exit_analysis: dict,
    ) -> str:
        """AIに渡すレポート作成プロンプトを構築する"""
        lines = [
            "以下のトレードの事後分析を行ってください。\n",
            "【トレード情報】",
            f"  通貨ペア: {trade.symbol}",
            f"  戦略: {'ロング（買い）' if trade.strategy == 'long' else 'ショート（売り）'}",
            f"  エントリー価格: {trade.entry_price}",
            f"  クローズ価格: {trade.close_price}",
            f"  利確目標: {trade.take_profit}",
            f"  損切ライン: {trade.stop_loss}",
            f"  保有期間: {self._calc_duration(trade)}",
            f"  クローズ理由: {trade.close_reason}",
            f"  損益: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)" if trade.pnl is not None else "  損益: 不明",
            "",
        ]

        # エントリー時テクニカル指標
        if entry_analysis:
            lines.append("【エントリー時のテクニカル指標】")
            for k, v in entry_analysis.items():
                if v is not None:
                    lines.append(f"  {k}: {v}")
            lines.append("")

        # クローズ時テクニカル指標
        if exit_analysis:
            lines.append("【クローズ時のテクニカル指標】")
            for k, v in exit_analysis.items():
                if v is not None:
                    lines.append(f"  {k}: {v}")
            lines.append("")

        # 価格推移（概要）
        if trade.price_history:
            lines.append("【価格推移（抜粋）】")
            # 先頭、中間、末尾の3点
            snapshots = trade.price_history
            sample_indices = [0]
            if len(snapshots) > 2:
                sample_indices.append(len(snapshots) // 2)
            if len(snapshots) > 1:
                sample_indices.append(len(snapshots) - 1)

            for idx in sample_indices:
                s = snapshots[idx]
                lines.append(
                    f"  [{s.timestamp.strftime('%H:%M')}] "
                    f"価格={s.price}"
                    + (f", RSI={s.rsi}" if s.rsi else "")
                    + (f" {s.note}" if s.note else "")
                )
            lines.append("")

        return "\n".join(lines)

    def _generate_fallback_analysis(self, trade: TradeRecord) -> str:
        """AI呼び出しに失敗した場合のフォールバック分析"""
        result = "勝ち" if (trade.pnl or 0) > 0 else "負け"
        lines = [
            f"トレード結果: {result}",
            f"損益: ${trade.pnl:.2f}" if trade.pnl is not None else "損益: 不明",
            f"クローズ理由: {trade.close_reason}",
        ]
        if trade.pnl and trade.pnl > 0:
            lines.append("利確目標に到達、または有利な条件でクローズされました。")
        elif trade.pnl and trade.pnl < 0:
            lines.append("損切りまたは不利な条件でクローズされました。エントリー条件の見直しが推奨されます。")
        return "\n".join(lines)

    def _summarize_price_history(self, trade: TradeRecord) -> list:
        """価格推移のサマリーリストを生成する"""
        if not trade.price_history:
            return []

        # 最大20点に間引く
        history = trade.price_history
        if len(history) <= 20:
            samples = history
        else:
            step = len(history) / 20
            indices = [int(i * step) for i in range(20)]
            samples = [history[i] for i in indices if i < len(history)]

        return [s.to_dict() for s in samples]
