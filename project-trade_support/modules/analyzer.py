"""
チャート分析モジュール - テクニカル指標からAI総合判断を取得
ta ライブラリを使用（Python 3.14対応）
"""
import pandas as pd
import numpy as np
import ta as ta_lib
from exchange.mexc_client import MEXCClient
from ai.llm_client import LLMClient
from ai.prompts import SYSTEM_PROMPT, CHART_ANALYSIS_PROMPT
from config.trading_params import ANALYSIS_PARAMS, TIMEFRAMES


class Analyzer:
    """テクニカル分析 + AI判断クラス"""

    def __init__(
        self,
        mexc_client: MEXCClient | None = None,
        llm_client: LLMClient | None = None,
        params: dict | None = None,
    ):
        self.client = mexc_client or MEXCClient()
        self.llm = llm_client or LLMClient()
        self.params = params or ANALYSIS_PARAMS.copy()

    def calculate_indicators(self, df: pd.DataFrame) -> dict:
        """DataFrameからテクニカル指標を計算"""
        if df.empty or len(df) < 30:
            return {"error": "データ不足（30本以上のローソク足が必要）"}

        indicators = {}
        p = self.params

        try:
            # RSI
            rsi_series = ta_lib.momentum.RSIIndicator(df["close"], window=p["rsi_period"]).rsi()
            if rsi_series is not None and not rsi_series.empty:
                rsi_val = float(rsi_series.iloc[-1])
                indicators["rsi"] = {
                    "value": round(rsi_val, 2),
                    "status": "oversold" if rsi_val < p["rsi_oversold"]
                             else "overbought" if rsi_val > p["rsi_overbought"]
                             else "neutral",
                }

            # EMA
            ema_values = {}
            ema_series_map = {}
            for period in p["ema_periods"]:
                ema_series = ta_lib.trend.EMAIndicator(df["close"], window=period).ema_indicator()
                if ema_series is not None and not ema_series.empty:
                    ema_values[f"ema_{period}"] = round(float(ema_series.iloc[-1]), 6)
                    ema_series_map[period] = ema_series
            indicators["ema"] = ema_values

            # ゴールデン/デッドクロス検出
            if 9 in ema_series_map and 21 in ema_series_map:
                ema9 = ema_series_map[9]
                ema21 = ema_series_map[21]
                if len(ema9) >= 2 and len(ema21) >= 2:
                    cross_up = ema9.iloc[-2] < ema21.iloc[-2] and ema9.iloc[-1] > ema21.iloc[-1]
                    cross_down = ema9.iloc[-2] > ema21.iloc[-2] and ema9.iloc[-1] < ema21.iloc[-1]
                    indicators["ema_cross"] = (
                        "golden_cross" if cross_up
                        else "dead_cross" if cross_down
                        else "none"
                    )

            # MACD
            macd_indicator = ta_lib.trend.MACD(
                df["close"],
                window_fast=p["macd_fast"],
                window_slow=p["macd_slow"],
                window_sign=p["macd_signal"],
            )
            macd_line = macd_indicator.macd()
            signal_line = macd_indicator.macd_signal()
            hist_line = macd_indicator.macd_diff()
            if macd_line is not None and not macd_line.empty:
                indicators["macd"] = {
                    "macd": round(float(macd_line.iloc[-1]), 6),
                    "signal": round(float(signal_line.iloc[-1]), 6) if signal_line is not None else None,
                    "histogram": round(float(hist_line.iloc[-1]), 6) if hist_line is not None else None,
                }

            # ボリンジャーバンド
            bb = ta_lib.volatility.BollingerBands(
                df["close"], window=p["bb_period"], window_dev=p["bb_std"]
            )
            upper = float(bb.bollinger_hband().iloc[-1])
            middle = float(bb.bollinger_mavg().iloc[-1])
            lower = float(bb.bollinger_lband().iloc[-1])
            width = float(bb.bollinger_wband().iloc[-1])
            current_price = float(df["close"].iloc[-1])

            indicators["bollinger"] = {
                "upper": round(upper, 6),
                "middle": round(middle, 6),
                "lower": round(lower, 6),
                "width": round(width, 4),
                "position": (
                    "above_upper" if current_price > upper
                    else "below_lower" if current_price < lower
                    else "within"
                ),
            }

            # 出来高分析
            vol_avg = df["volume"].rolling(p["volume_avg_period"]).mean().iloc[-1]
            vol_current = df["volume"].iloc[-1]
            indicators["volume"] = {
                "current": round(float(vol_current), 2),
                "average": round(float(vol_avg), 2),
                "ratio": round(float(vol_current / vol_avg), 2) if vol_avg > 0 else 0,
                "trend": "high" if vol_current > vol_avg * 1.5 else "low" if vol_current < vol_avg * 0.5 else "normal",
            }

            # ATR
            atr = ta_lib.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=p["atr_period"]
            ).average_true_range()
            if atr is not None and not atr.empty:
                indicators["atr"] = round(float(atr.iloc[-1]), 6)

            # ADX
            adx = ta_lib.trend.ADXIndicator(
                df["high"], df["low"], df["close"], window=14
            ).adx()
            if adx is not None and not adx.empty:
                indicators["adx"] = round(float(adx.iloc[-1]), 2)

            # フィボナッチリトレースメント
            high_val = float(df["high"].max())
            low_val = float(df["low"].min())
            diff = high_val - low_val
            indicators["fibonacci"] = {
                str(level): round(high_val - diff * level, 6)
                for level in p["fibonacci_levels"]
            }
            indicators["fibonacci"]["high"] = round(high_val, 6)
            indicators["fibonacci"]["low"] = round(low_val, 6)

            # 現在価格
            indicators["current_price"] = round(float(df["close"].iloc[-1]), 6)

        except Exception as e:
            indicators["error"] = str(e)

        return indicators

    def analyze_multi_timeframe(self, symbol: str) -> dict:
        """マルチタイムフレーム分析"""
        results = {}
        all_timeframes = TIMEFRAMES["upper"] + TIMEFRAMES["lower"]

        for tf in all_timeframes:
            df = self.client.fetch_ohlcv(symbol, tf, limit=200)
            if not df.empty:
                indicators = self.calculate_indicators(df)
                results[tf] = indicators
            else:
                results[tf] = {"error": f"{tf}のデータ取得失敗"}

        return results

    def get_ai_analysis(self, symbol: str, timeframe: str = "15m") -> dict:
        """AIによる総合分析を取得"""
        # OHLCV取得
        df = self.client.fetch_ohlcv(symbol, timeframe, limit=200)
        if df.empty:
            return {"error": "OHLCVデータ取得失敗"}

        # テクニカル指標計算
        indicators = self.calculate_indicators(df)

        # マルチタイムフレーム分析
        mtf = self.analyze_multi_timeframe(symbol)

        # ティッカー情報
        ticker = self.client.fetch_ticker_detail(symbol)
        current_price = ticker.get("last", indicators.get("current_price", "N/A"))
        change_24h = ticker.get("percentage", 0)

        # AIにプロンプト送信
        import json
        prompt = CHART_ANALYSIS_PROMPT.format(
            symbol=symbol,
            current_price=current_price,
            change_24h=round(change_24h, 2) if change_24h else 0,
            technical_data=json.dumps(indicators, indent=2, ensure_ascii=False, default=str),
            multi_timeframe_data=json.dumps(mtf, indent=2, ensure_ascii=False, default=str),
        )

        ai_result = self.llm.query_json(prompt, SYSTEM_PROMPT, provider="openai")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators,
            "multi_timeframe": mtf,
            "ai_analysis": ai_result,
            "current_price": current_price,
        }

    def get_ohlcv_df(self, symbol: str, timeframe: str = "15m", limit: int = 200) -> pd.DataFrame:
        """チャート表示用にOHLCVデータを返す"""
        return self.client.fetch_ohlcv(symbol, timeframe, limit)
