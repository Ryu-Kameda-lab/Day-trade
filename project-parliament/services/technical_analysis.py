"""
Project Parliament - テクニカル分析エンジン
MEXC klines データに対して RSI / MACD / EMA / ボリンジャーバンド / 出来高分析 を計算し、
トレードシグナルを検出する。
"""
import math
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import ta

from models.analysis import (
    MultiTimeframeAnalysis,
    SymbolAnalysis,
    TechnicalIndicators,
)
from utils.logger import get_logger

logger = get_logger("TechnicalAnalyzer")


class TechnicalAnalyzer:
    """ローソク足データに対するテクニカル分析"""

    # ------------------------------------------------------------------
    # 定数
    # ------------------------------------------------------------------
    RSI_PERIOD = 14
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    EMA_PERIODS = [9, 21, 50, 200]
    BB_PERIOD = 20
    BB_STD_DEV = 2
    ATR_PERIOD = 14
    VOLUME_AVG_PERIOD = 20

    # シグナル閾値
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    VOLUME_SPIKE_THRESHOLD = 2.0  # 平均出来高の何倍で「急増」とするか

    # ------------------------------------------------------------------
    # パブリック API
    # ------------------------------------------------------------------
    def klines_to_dataframe(self, klines: list) -> pd.DataFrame:
        """
        MEXC klines レスポンスを pandas DataFrame に変換する。

        MEXC klines format (各要素は list):
            [open_time, open, high, low, close, volume, close_time, quote_volume]

        Returns:
            DataFrame with columns: open, high, low, close, volume, quote_volume
        """
        if not klines:
            return pd.DataFrame()

        # MEXC klines は list of lists
        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close",
            "volume", "close_time", "quote_volume",
        ])

        # 数値型に変換
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # タイムスタンプを datetime に変換
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        # 時系列順にソート
        df = df.sort_values("open_time").reset_index(drop=True)

        return df

    def analyze(self, klines: list, symbol: str, timeframe: str = "1h") -> SymbolAnalysis:
        """
        ローソク足データに対してテクニカル分析を一括実行する。

        Args:
            klines: MEXC klines API レスポンス
            symbol: 通貨ペアシンボル（例: "BTCUSDT"）
            timeframe: 時間足（例: "15m", "1h", "4h"）

        Returns:
            SymbolAnalysis データクラスインスタンス
        """
        df = self.klines_to_dataframe(klines)

        if df.empty or len(df) < self.BB_PERIOD:
            logger.warning(
                "%s (%s): データ不足 (%d行), 分析スキップ",
                symbol, timeframe, len(df),
            )
            return SymbolAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                indicators=TechnicalIndicators(),
                signals=["データ不足のため分析不可"],
                summary=f"{symbol} ({timeframe}): データ不足",
            )

        # 各指標を算出
        rsi_val = self.calc_rsi(df)
        macd_val = self.calc_macd(df)
        ema_val = self.calc_ema(df)
        bb_val = self.calc_bollinger(df)
        vol_val = self.calc_volume_profile(df)
        atr_val = self.calc_atr(df)

        indicators = TechnicalIndicators(
            rsi=rsi_val,
            macd=macd_val,
            ema=ema_val,
            bollinger=bb_val,
            volume_ratio=vol_val,
            atr=atr_val,
        )

        # シグナル検出
        signals = self.detect_signals(indicators, df)

        # サマリー生成
        current_price = float(df["close"].iloc[-1])
        summary = self.generate_summary(symbol, timeframe, current_price, indicators, signals)

        return SymbolAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            signals=signals,
            summary=summary,
            raw_price=current_price,
            timestamp=datetime.now(),
        )

    def analyze_multi_timeframe(
        self,
        klines_map: Dict[str, list],
        symbol: str,
    ) -> MultiTimeframeAnalysis:
        """
        複数時間足の分析を統合する。

        Args:
            klines_map: {timeframe: klines_list} の辞書
            symbol: 通貨ペアシンボル

        Returns:
            MultiTimeframeAnalysis
        """
        analyses: Dict[str, SymbolAnalysis] = {}

        for timeframe, klines in klines_map.items():
            analysis = self.analyze(klines, symbol, timeframe)
            analyses[timeframe] = analysis

        # 統合スコアとシグナル
        overall_score = self._calc_overall_score(analyses)
        overall_signals = self._merge_signals(analyses)
        recommendation = self._determine_recommendation(overall_score, analyses)

        return MultiTimeframeAnalysis(
            symbol=symbol,
            analyses=analyses,
            overall_score=overall_score,
            overall_signals=overall_signals,
            recommendation=recommendation,
            timestamp=datetime.now(),
        )

    # ------------------------------------------------------------------
    # 個別指標の算出
    # ------------------------------------------------------------------
    def calc_rsi(self, df: pd.DataFrame, period: int = None) -> Optional[float]:
        """RSI（相対力指数）を算出する"""
        period = period or self.RSI_PERIOD
        try:
            rsi_series = ta.momentum.rsi(df["close"], window=period)
            val = rsi_series.iloc[-1]
            return round(float(val), 2) if not math.isnan(val) else None
        except Exception as e:
            logger.warning("RSI計算エラー: %s", e)
            return None

    def calc_macd(self, df: pd.DataFrame) -> Optional[Dict]:
        """MACD（移動平均収束拡散法）を算出する"""
        try:
            macd_indicator = ta.trend.MACD(
                df["close"],
                window_slow=self.MACD_SLOW,
                window_fast=self.MACD_FAST,
                window_sign=self.MACD_SIGNAL,
            )
            macd_val = macd_indicator.macd().iloc[-1]
            signal_val = macd_indicator.macd_signal().iloc[-1]
            hist_val = macd_indicator.macd_diff().iloc[-1]

            # 前回のヒストグラムも取得（方向性判定用）
            prev_hist = macd_indicator.macd_diff().iloc[-2] if len(df) > 1 else 0

            return {
                "macd": round(float(macd_val), 6) if not math.isnan(macd_val) else None,
                "signal": round(float(signal_val), 6) if not math.isnan(signal_val) else None,
                "histogram": round(float(hist_val), 6) if not math.isnan(hist_val) else None,
                "prev_histogram": round(float(prev_hist), 6) if not math.isnan(prev_hist) else None,
            }
        except Exception as e:
            logger.warning("MACD計算エラー: %s", e)
            return None

    def calc_ema(self, df: pd.DataFrame, periods: list = None) -> Optional[Dict[str, float]]:
        """複数期間の EMA を算出する"""
        periods = periods or self.EMA_PERIODS
        result = {}
        try:
            for p in periods:
                if len(df) < p:
                    result[f"ema_{p}"] = None
                    continue
                ema_series = ta.trend.ema_indicator(df["close"], window=p)
                val = ema_series.iloc[-1]
                result[f"ema_{p}"] = round(float(val), 6) if not math.isnan(val) else None
            return result
        except Exception as e:
            logger.warning("EMA計算エラー: %s", e)
            return None

    def calc_bollinger(self, df: pd.DataFrame) -> Optional[Dict]:
        """ボリンジャーバンドを算出する"""
        try:
            bb = ta.volatility.BollingerBands(
                df["close"],
                window=self.BB_PERIOD,
                window_dev=self.BB_STD_DEV,
            )
            upper = bb.bollinger_hband().iloc[-1]
            middle = bb.bollinger_mavg().iloc[-1]
            lower = bb.bollinger_lband().iloc[-1]
            width = bb.bollinger_wband().iloc[-1]

            return {
                "upper": round(float(upper), 6) if not math.isnan(upper) else None,
                "middle": round(float(middle), 6) if not math.isnan(middle) else None,
                "lower": round(float(lower), 6) if not math.isnan(lower) else None,
                "width": round(float(width), 6) if not math.isnan(width) else None,
            }
        except Exception as e:
            logger.warning("ボリンジャーバンド計算エラー: %s", e)
            return None

    def calc_volume_profile(self, df: pd.DataFrame) -> Optional[float]:
        """直近の出来高が平均出来高の何倍かを返す"""
        try:
            avg_period = min(self.VOLUME_AVG_PERIOD, len(df))
            avg_vol = df["volume"].iloc[-avg_period:].mean()
            current_vol = df["volume"].iloc[-1]
            if avg_vol <= 0:
                return None
            ratio = current_vol / avg_vol
            return round(float(ratio), 2)
        except Exception as e:
            logger.warning("出来高分析エラー: %s", e)
            return None

    def calc_atr(self, df: pd.DataFrame, period: int = None) -> Optional[float]:
        """ATR（平均真の値幅）を算出する"""
        period = period or self.ATR_PERIOD
        try:
            atr_series = ta.volatility.average_true_range(
                df["high"], df["low"], df["close"], window=period,
            )
            val = atr_series.iloc[-1]
            return round(float(val), 6) if not math.isnan(val) else None
        except Exception as e:
            logger.warning("ATR計算エラー: %s", e)
            return None

    # ------------------------------------------------------------------
    # シグナル検出
    # ------------------------------------------------------------------
    def detect_signals(self, indicators: TechnicalIndicators, df: pd.DataFrame) -> List[str]:
        """各テクニカル指標からトレードシグナルを検出する"""
        signals = []
        current_price = float(df["close"].iloc[-1])

        # --- RSI シグナル ---
        if indicators.rsi is not None:
            if indicators.rsi <= self.RSI_OVERSOLD:
                signals.append(f"RSI売られすぎ ({indicators.rsi})")
            elif indicators.rsi >= self.RSI_OVERBOUGHT:
                signals.append(f"RSI買われすぎ ({indicators.rsi})")
            elif indicators.rsi <= 40:
                signals.append(f"RSI弱含み ({indicators.rsi})")
            elif indicators.rsi >= 60:
                signals.append(f"RSI強含み ({indicators.rsi})")

        # --- MACD シグナル ---
        if indicators.macd is not None:
            macd = indicators.macd
            hist = macd.get("histogram")
            prev_hist = macd.get("prev_histogram")

            if hist is not None and prev_hist is not None:
                # ゴールデンクロス（ヒストグラムが負→正に転換）
                if prev_hist < 0 and hist > 0:
                    signals.append("MACDゴールデンクロス")
                # デッドクロス（ヒストグラムが正→負に転換）
                elif prev_hist > 0 and hist < 0:
                    signals.append("MACDデッドクロス")

                # ヒストグラムの方向
                if hist > 0 and hist > prev_hist:
                    signals.append("MACD上昇モメンタム")
                elif hist < 0 and hist < prev_hist:
                    signals.append("MACD下降モメンタム")

        # --- EMA シグナル ---
        if indicators.ema is not None:
            ema = indicators.ema
            ema_9 = ema.get("ema_9")
            ema_21 = ema.get("ema_21")
            ema_50 = ema.get("ema_50")
            ema_200 = ema.get("ema_200")

            # 短期・中期EMAの位置関係
            if ema_9 and ema_21:
                if ema_9 > ema_21:
                    signals.append("短期EMA > 中期EMA (上昇トレンド)")
                else:
                    signals.append("短期EMA < 中期EMA (下降トレンド)")

            # ゴールデンクロス / デッドクロス（50 vs 200）
            if ema_50 and ema_200:
                if ema_50 > ema_200:
                    signals.append("EMA50 > EMA200 (長期上昇トレンド)")
                else:
                    signals.append("EMA50 < EMA200 (長期下降トレンド)")

            # 価格と EMA200 の位置関係
            if ema_200 and current_price:
                if current_price > ema_200:
                    signals.append("価格 > EMA200 (強気)")
                else:
                    signals.append("価格 < EMA200 (弱気)")

        # --- ボリンジャーバンド シグナル ---
        if indicators.bollinger is not None:
            bb = indicators.bollinger
            upper = bb.get("upper")
            lower = bb.get("lower")
            width = bb.get("width")

            if upper and lower and current_price:
                if current_price >= upper:
                    signals.append("ボリンジャー上限到達 (過熱)")
                elif current_price <= lower:
                    signals.append("ボリンジャー下限到達 (売られすぎ)")

            # スクイーズ検出（バンド幅が縮小）
            if width is not None and width < 0.03:
                signals.append("ボリンジャースクイーズ (ブレイクアウト間近)")

        # --- 出来高シグナル ---
        if indicators.volume_ratio is not None:
            if indicators.volume_ratio >= self.VOLUME_SPIKE_THRESHOLD:
                signals.append(f"出来高急増 (平均の{indicators.volume_ratio}倍)")
            elif indicators.volume_ratio <= 0.5:
                signals.append(f"出来高低迷 (平均の{indicators.volume_ratio}倍)")

        return signals

    # ------------------------------------------------------------------
    # サマリー生成
    # ------------------------------------------------------------------
    def generate_summary(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        indicators: TechnicalIndicators,
        signals: List[str],
    ) -> str:
        """AIに渡す用の構造化テキストサマリーを生成する"""
        lines = [f"【{symbol} ({timeframe}) テクニカル分析】"]
        lines.append(f"現在価格: {current_price}")

        # RSI
        if indicators.rsi is not None:
            lines.append(f"RSI(14): {indicators.rsi}")

        # MACD
        if indicators.macd:
            m = indicators.macd
            lines.append(
                f"MACD: {m.get('macd', 'N/A')} / Signal: {m.get('signal', 'N/A')} / "
                f"Histogram: {m.get('histogram', 'N/A')}"
            )

        # EMA
        if indicators.ema:
            ema_parts = []
            for k, v in indicators.ema.items():
                if v is not None:
                    ema_parts.append(f"{k.upper()}: {v}")
            if ema_parts:
                lines.append("EMA: " + " | ".join(ema_parts))

        # ボリンジャーバンド
        if indicators.bollinger:
            bb = indicators.bollinger
            lines.append(
                f"BB: Upper={bb.get('upper', 'N/A')} | "
                f"Middle={bb.get('middle', 'N/A')} | "
                f"Lower={bb.get('lower', 'N/A')} | "
                f"Width={bb.get('width', 'N/A')}"
            )

        # 出来高
        if indicators.volume_ratio is not None:
            lines.append(f"出来高比率: 平均の{indicators.volume_ratio}倍")

        # ATR
        if indicators.atr is not None:
            lines.append(f"ATR(14): {indicators.atr}")

        # シグナル
        if signals:
            lines.append("検出シグナル:")
            for s in signals:
                lines.append(f"  ● {s}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 統合スコアリング (Phase B で MarketScreener から呼ばれる)
    # ------------------------------------------------------------------
    def calculate_score(self, indicators: TechnicalIndicators, signals: List[str]) -> float:
        """
        テクニカル指標からスクリーニングスコア (0-100) を算出する。

        スコア配分:
            - RSI ポジション: 25 点
            - MACD 方向性: 25 点
            - EMA トレンド: 20 点
            - 出来高: 15 点
            - ボリンジャーバンド: 15 点
        """
        score = 0.0

        # --- RSI (25点) ---
        if indicators.rsi is not None:
            rsi = indicators.rsi
            if rsi <= self.RSI_OVERSOLD:
                # 売られすぎ ＝ 上昇の余地が大きい
                score += 25
            elif rsi <= 40:
                score += 20
            elif 40 < rsi < 60:
                # 中立
                score += 10
            elif rsi >= self.RSI_OVERBOUGHT:
                # 買われすぎ ＝ ショート機会
                score += 20
            else:
                score += 5

        # --- MACD (25点) ---
        if indicators.macd:
            hist = indicators.macd.get("histogram")
            prev_hist = indicators.macd.get("prev_histogram")
            if hist is not None and prev_hist is not None:
                # クロスオーバー検出時に高得点
                if (prev_hist < 0 and hist > 0) or (prev_hist > 0 and hist < 0):
                    score += 25
                # 同方向で加速中
                elif (hist > 0 and hist > prev_hist) or (hist < 0 and hist < prev_hist):
                    score += 18
                # 同方向で減速中
                elif (hist > 0 and hist <= prev_hist) or (hist < 0 and hist >= prev_hist):
                    score += 10
                else:
                    score += 5

        # --- EMA トレンド (20点) ---
        if indicators.ema:
            ema = indicators.ema
            ema_9 = ema.get("ema_9")
            ema_21 = ema.get("ema_21")
            ema_50 = ema.get("ema_50")

            if ema_9 and ema_21 and ema_50:
                # 「パーフェクトオーダー」（短期 > 中期 > 長期 or 逆）
                if ema_9 > ema_21 > ema_50:
                    score += 20
                elif ema_9 < ema_21 < ema_50:
                    score += 18  # ショート方向のトレンド
                else:
                    score += 8  # 混在

        # --- 出来高 (15点) ---
        if indicators.volume_ratio is not None:
            if indicators.volume_ratio >= self.VOLUME_SPIKE_THRESHOLD:
                score += 15  # 出来高急増 = 何か起きている
            elif indicators.volume_ratio >= 1.5:
                score += 12
            elif indicators.volume_ratio >= 1.0:
                score += 8
            else:
                score += 3

        # --- ボリンジャーバンド (15点) ---
        if indicators.bollinger:
            width = indicators.bollinger.get("width")
            if width is not None:
                if width < 0.03:
                    # スクイーズ = ブレイクアウト間近
                    score += 15
                elif width < 0.05:
                    score += 10
                else:
                    score += 5

        return round(score, 1)

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------
    def _calc_overall_score(self, analyses: Dict[str, SymbolAnalysis]) -> float:
        """複数時間足の統合スコアを算出する（加重平均）"""
        weights = {
            "15m": 0.2,
            "1h": 0.4,
            "4h": 0.4,
        }
        total_weight = 0
        weighted_sum = 0

        for tf, analysis in analyses.items():
            w = weights.get(tf, 0.3)
            weighted_sum += analysis.score * w
            total_weight += w

        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 1)

    def _merge_signals(self, analyses: Dict[str, SymbolAnalysis]) -> List[str]:
        """複数時間足のシグナルを統合する"""
        merged = []
        for tf, analysis in analyses.items():
            for sig in analysis.signals:
                merged.append(f"[{tf}] {sig}")
        return merged

    def _determine_recommendation(
        self,
        overall_score: float,
        analyses: Dict[str, SymbolAnalysis],
    ) -> str:
        """統合スコアからレコメンデーションを判定する"""
        if overall_score >= 80:
            return "strong_buy"
        elif overall_score >= 60:
            return "buy"
        elif overall_score >= 40:
            return "neutral"
        elif overall_score >= 20:
            return "sell"
        else:
            return "strong_sell"
