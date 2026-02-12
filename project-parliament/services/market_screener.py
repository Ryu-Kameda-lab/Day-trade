"""
Project Parliament - 市場スクリーニングエンジン
MEXC全市場からテクニカル分析に基づいてトレード候補を自動選定する。
"""
from datetime import datetime
from typing import List, Optional

from models.analysis import MultiTimeframeAnalysis, SymbolAnalysis
from services.technical_analysis import TechnicalAnalyzer
from utils.logger import get_logger

logger = get_logger("MarketScreener")

# 設定デフォルト値（Config から上書き可能）
DEFAULT_TOP_N = 10
DEFAULT_MIN_VOLUME = 100000  # USDT
DEFAULT_INTERVALS = ["15m", "1h", "4h"]


class MarketScreener:
    """MEXC全市場からトレード候補をスクリーニングする"""

    def __init__(self, mexc_service, analyzer: TechnicalAnalyzer = None, config=None):
        """
        Args:
            mexc_service: MEXCService インスタンス
            analyzer: TechnicalAnalyzer インスタンス（省略時は新規作成）
            config: Config オブジェクト（省略時はデフォルト値を使用）
        """
        self.mexc = mexc_service
        self.analyzer = analyzer or TechnicalAnalyzer()

        # 設定読み込み
        self.top_n = getattr(config, "SCREENING_TOP_N", DEFAULT_TOP_N) if config else DEFAULT_TOP_N
        self.min_volume = getattr(config, "SCREENING_MIN_VOLUME", DEFAULT_MIN_VOLUME) if config else DEFAULT_MIN_VOLUME
        self.intervals = DEFAULT_INTERVALS

    def screen_market(self, top_n: int = None, emit_callback=None) -> List[MultiTimeframeAnalysis]:
        """
        市場をスクリーニングし、トレード候補をスコア順で返す。

        手順:
            1. MEXC市場概要から出来高上位ペアを取得
            2. 各ペアの複数時間足klinesを取得
            3. テクニカル分析を実行しスコアリング
            4. スコア上位N件を返す

        Args:
            top_n: 返す候補数（デフォルト: self.top_n）
            emit_callback: 進捗通知用コールバック（opt）

        Returns:
            MultiTimeframeAnalysis のリスト（スコア降順）
        """
        top_n = top_n or self.top_n

        # Step 1: 市場概要を取得（出来高フィルタ済み）
        self._emit_progress(emit_callback, "市場概要を取得中...")
        try:
            market_data = self.mexc.get_market_overview(
                quote_asset="USDT",
                limit=50,
            )
        except Exception as e:
            logger.error("市場概要の取得に失敗: %s", e)
            return []

        pairs = market_data.get("pairs", [])
        if not pairs:
            logger.warning("市場データが空です")
            return []

        # 出来高でさらにフィルタ
        candidates = [
            p for p in pairs
            if p.get("volume_usdt", 0) >= self.min_volume
        ]
        logger.info(
            "スクリーニング対象: %d/%d ペア (最低出来高 %s USDT)",
            len(candidates), len(pairs), f"{self.min_volume:,.0f}",
        )

        # Step 2-3: 各ペアの複数時間足分析
        self._emit_progress(
            emit_callback,
            f"{len(candidates)}ペアのテクニカル分析を実行中...",
        )

        analyses: List[MultiTimeframeAnalysis] = []

        for i, pair_data in enumerate(candidates):
            symbol = pair_data["symbol"]
            try:
                analysis = self._analyze_symbol(symbol)
                if analysis:
                    # 市場データからの追加情報をセット
                    for tf_analysis in analysis.analyses.values():
                        tf_analysis.change_percent = pair_data.get("change_percent")
                        if tf_analysis.raw_price is None:
                            tf_analysis.raw_price = pair_data.get("price")

                    analyses.append(analysis)
            except Exception as e:
                logger.warning("分析エラー %s: %s", symbol, e)
                continue

            # 進捗通知（10ペアごと）
            if (i + 1) % 10 == 0:
                self._emit_progress(
                    emit_callback,
                    f"テクニカル分析: {i + 1}/{len(candidates)} ペア完了",
                )

        # Step 4: スコア順にソートして上位N件を返す
        analyses.sort(key=lambda a: a.overall_score, reverse=True)
        top_results = analyses[:top_n]

        logger.info(
            "スクリーニング完了: %d ペア分析、上位 %d 件を選定",
            len(analyses), len(top_results),
        )

        if top_results:
            for rank, result in enumerate(top_results, 1):
                logger.info(
                    "Top %d: %s (スコア: %.1f, 推奨: %s)",
                    rank, result.symbol, result.overall_score, result.recommendation,
                )

        return top_results

    def analyze_single(self, symbol: str) -> Optional[MultiTimeframeAnalysis]:
        """
        単一シンボルの詳細分析を実行する。

        Args:
            symbol: 通貨ペアシンボル（例: "BTCUSDT"）

        Returns:
            MultiTimeframeAnalysis or None
        """
        return self._analyze_symbol(symbol)

    def format_screening_results(self, results: List[MultiTimeframeAnalysis]) -> str:
        """
        スクリーニング結果をAI議論用のテキストに整形する。

        Args:
            results: スクリーニング結果リスト

        Returns:
            AI向けテキスト
        """
        if not results:
            return "スクリーニング結果: 条件に合致するペアが見つかりませんでした。"

        lines = [
            "【MEXC市場スクリーニング結果】",
            f"上位 {len(results)} ペアを選定しました。\n",
        ]

        for rank, result in enumerate(results, 1):
            lines.append(f"━━━ #{rank} {result.symbol} (スコア: {result.overall_score}/100) ━━━")
            lines.append(f"推奨: {self._recommendation_label(result.recommendation)}")

            # 各時間足のサマリー
            for tf in ["15m", "1h", "4h"]:
                analysis = result.analyses.get(tf)
                if analysis:
                    lines.append(f"\n[{tf}]")
                    # 指標
                    ind = analysis.indicators
                    parts = []
                    if ind.rsi is not None:
                        parts.append(f"RSI={ind.rsi}")
                    if ind.macd and ind.macd.get("histogram") is not None:
                        parts.append(f"MACD hist={ind.macd['histogram']}")
                    if ind.volume_ratio is not None:
                        parts.append(f"出来高={ind.volume_ratio}x")
                    if parts:
                        lines.append("  指標: " + " | ".join(parts))

                    # 現在価格
                    if analysis.raw_price:
                        lines.append(f"  現在価格: {analysis.raw_price}")

                    # シグナル（上位3件）
                    if analysis.signals:
                        for sig in analysis.signals[:3]:
                            lines.append(f"  ● {sig}")
            lines.append("")

        return "\n".join(lines)

    def format_detailed_analysis(self, analysis: MultiTimeframeAnalysis) -> str:
        """単一ペアの詳細分析テキストを生成する"""
        if not analysis:
            return "分析データがありません。"

        lines = [f"【{analysis.symbol} 詳細テクニカル分析】\n"]

        for tf in ["15m", "1h", "4h"]:
            tf_analysis = analysis.analyses.get(tf)
            if tf_analysis and tf_analysis.summary:
                lines.append(tf_analysis.summary)
                lines.append("")

        # 統合シグナル
        if analysis.overall_signals:
            lines.append("【統合シグナル】")
            for sig in analysis.overall_signals:
                lines.append(f"  ● {sig}")

        lines.append(f"\n総合スコア: {analysis.overall_score}/100")
        lines.append(f"推奨: {self._recommendation_label(analysis.recommendation)}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------
    def _analyze_symbol(self, symbol: str) -> Optional[MultiTimeframeAnalysis]:
        """単一シンボルの複数時間足分析を実行する"""
        try:
            klines_map = self.mexc.get_multi_timeframe_klines(
                symbol=symbol,
                intervals=self.intervals,
                limit=200,
            )
        except Exception as e:
            logger.warning("%s klines取得エラー: %s", symbol, e)
            return None

        # 有効なデータがあるか確認
        valid_klines = {tf: kl for tf, kl in klines_map.items() if kl}
        if not valid_klines:
            logger.debug("%s: 有効なklineデータなし", symbol)
            return None

        # テクニカル分析実行
        analysis = self.analyzer.analyze_multi_timeframe(valid_klines, symbol)

        # 各時間足のスコアを算出
        for tf, tf_analysis in analysis.analyses.items():
            tf_analysis.score = self.analyzer.calculate_score(
                tf_analysis.indicators, tf_analysis.signals,
            )

        # 統合スコアを再計算
        analysis.overall_score = self.analyzer._calc_overall_score(analysis.analyses)
        analysis.recommendation = self.analyzer._determine_recommendation(
            analysis.overall_score, analysis.analyses,
        )

        return analysis

    def _emit_progress(self, callback, message: str):
        """進捗メッセージを送信する"""
        if callback:
            try:
                callback("screening_progress", {
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception:
                pass
        logger.info("Screening: %s", message)

    @staticmethod
    def _recommendation_label(rec: str) -> str:
        """レコメンデーション文字列を日本語ラベルに変換"""
        labels = {
            "strong_buy": "🟢 強い買い",
            "buy": "🟡 買い",
            "neutral": "⚪ 中立",
            "sell": "🟠 売り",
            "strong_sell": "🔴 強い売り",
        }
        return labels.get(rec, rec)
