"""
銘柄スクリーニングモジュール - MEXC先物から商機ある銘柄を自動抽出
ta ライブラリを使用（Python 3.14対応）
"""
import pandas as pd
import numpy as np
import ta as ta_lib
from exchange.mexc_client import MEXCClient
from config.trading_params import SCREENING_PARAMS


class Screener:
    """銘柄スクリーニングを実行するクラス"""

    def __init__(self, mexc_client: MEXCClient | None = None, params: dict | None = None):
        self.client = mexc_client or MEXCClient()
        self.params = params or SCREENING_PARAMS.copy()

    def run_screening(self) -> pd.DataFrame:
        """
        スクリーニングを実行し、スコアリング済みの銘柄一覧をDataFrameで返す
        """
        # 1. 全先物ティッカー取得
        tickers = self.client.fetch_tickers()
        if not tickers:
            return pd.DataFrame()

        # 2. ティッカーデータをDataFrame化
        rows = []
        for symbol, t in tickers.items():
            rows.append({
                "symbol": symbol,
                "last": t.get("last", 0),
                "change_pct": t.get("percentage", 0) or 0,
                "volume_quote": t.get("quoteVolume", 0) or 0,
                "high": t.get("high", 0) or 0,
                "low": t.get("low", 0) or 0,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # last が 0 の銘柄を除外
        df = df[df["last"] > 0].copy()
        if df.empty:
            return df

        # 3. フィルタリング
        df["abs_change"] = df["change_pct"].abs()

        # 24h変動率フィルタ
        min_change = self.params.get("min_change_rate", 3.0)
        df = df[df["abs_change"] >= min_change].copy()
        if df.empty:
            return df

        # 出来高パーセンタイルフィルタ
        min_vol_pct = self.params.get("min_volume_percentile", 80)
        vol_threshold = np.percentile(df["volume_quote"].values, 100 - min_vol_pct)
        df = df[df["volume_quote"] >= vol_threshold].copy()
        if df.empty:
            return df

        # 4. スコアリング
        scored_rows = []
        for _, row in df.iterrows():
            score_data = self._calculate_score(row)
            scored_rows.append(score_data)

        result = pd.DataFrame(scored_rows)
        if result.empty:
            return result

        # 5. スコアでソート、上位N銘柄
        top_n = self.params.get("top_n_symbols", 10)
        result = result.sort_values("total_score", ascending=False).head(top_n)
        result = result.reset_index(drop=True)
        result.index = result.index + 1  # 1始まりのランキング

        return result

    def _calculate_score(self, row: pd.Series) -> dict:
        """各銘柄のスコアを計算"""
        # 変動率スコア（0-30）
        change_score = min(row["abs_change"] / 10.0 * 30, 30)

        # 出来高スコア（0-30）
        vol_score = min(row["volume_quote"] / 1e8 * 30, 30)

        # ボラティリティスコア - 高値-安値 / 終値（0-20）
        if row["last"] > 0:
            hl_range = (row["high"] - row["low"]) / row["last"] * 100
            vol_score_hl = min(hl_range / 10 * 20, 20)
        else:
            vol_score_hl = 0

        # トレンド方向スコア（0-20）
        if row["change_pct"] > 5:
            trend_score = 20
        elif row["change_pct"] > 2:
            trend_score = 15
        elif row["change_pct"] < -5:
            trend_score = 20
        elif row["change_pct"] < -2:
            trend_score = 15
        else:
            trend_score = 5

        total_score = change_score + vol_score + vol_score_hl + trend_score

        return {
            "symbol": row["symbol"],
            "price": row["last"],
            "change_pct": round(row["change_pct"], 2),
            "volume_quote": round(row["volume_quote"], 0),
            "change_score": round(change_score, 1),
            "volume_score": round(vol_score, 1),
            "volatility_score": round(vol_score_hl, 1),
            "trend_score": round(trend_score, 1),
            "total_score": round(total_score, 1),
        }

    def get_detailed_analysis(self, symbol: str, timeframe: str = "15m") -> dict:
        """指定銘柄のOHLCVからATR / ADX等の詳細指標を計算"""
        df = self.client.fetch_ohlcv(symbol, timeframe, limit=200)
        if df.empty:
            return {"symbol": symbol, "error": "OHLCVデータ取得失敗"}

        result = {"symbol": symbol, "timeframe": timeframe}

        try:
            # ATR
            atr = ta_lib.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=14
            ).average_true_range()
            result["atr"] = round(float(atr.iloc[-1]), 6) if atr is not None and not atr.empty else None

            # ADX
            adx = ta_lib.trend.ADXIndicator(
                df["high"], df["low"], df["close"], window=14
            ).adx()
            result["adx"] = round(float(adx.iloc[-1]), 2) if adx is not None and not adx.empty else None

            # 出来高変化率
            vol_avg = df["volume"].rolling(60).mean().iloc[-1]
            vol_recent = df["volume"].iloc[-5:].mean()
            result["volume_spike_ratio"] = round(vol_recent / vol_avg, 2) if vol_avg > 0 else 0

        except Exception as e:
            result["error"] = str(e)

        return result


class ExpectedValueScreener:
    """
    期待値基準スクリーニング
    4つのスコアで「トレードしやすい銘柄」を評価:
      1. 流動性スコア（24H出来高、板の厚み、スプレッド）
      2. 値幅スコア（ATR、平均レンジ）
      3. 素直さスコア（出来高の継続性、ヒゲ率、急変頻度）
      4. 先物スコア（OI増減、Funding Rate極端さ）
    """

    def __init__(self, mexc_client: MEXCClient | None = None, params: dict | None = None):
        self.client = mexc_client or MEXCClient()
        self.params = params or SCREENING_PARAMS.copy()

    def run_screening(self, progress_callback=None) -> pd.DataFrame:
        """
        期待値基準スクリーニングを実行
        progress_callback: (current, total, symbol) を受け取るコールバック
        """
        # 1. 全先物ティッカー取得 → 出来高上位で絞る
        tickers = self.client.fetch_tickers()
        if not tickers:
            return pd.DataFrame()

        # ティッカーをDataFrame化して出来高降順ソート
        ticker_rows = []
        for symbol, t in tickers.items():
            vol = t.get("quoteVolume", 0) or 0
            last = t.get("last", 0) or 0
            if last > 0 and vol > 0:
                ticker_rows.append({
                    "symbol": symbol,
                    "last": last,
                    "volume_quote": vol,
                    "high": t.get("high", 0) or 0,
                    "low": t.get("low", 0) or 0,
                    "change_pct": t.get("percentage", 0) or 0,
                })

        if not ticker_rows:
            return pd.DataFrame()

        df = pd.DataFrame(ticker_rows)

        # 出来高上位N銘柄を候補にする（API負荷軽減）
        candidate_n = self.params.get("ev_candidate_n", 10)
        df = df.sort_values("volume_quote", ascending=False).head(candidate_n)

        # 2. 各銘柄の4次元スコアを計算
        scored_rows = []
        total = len(df)

        for idx, (_, row) in enumerate(df.iterrows()):
            symbol = row["symbol"]
            if progress_callback:
                progress_callback(idx + 1, total, symbol)

            try:
                score = self._evaluate_symbol(symbol, row)
                scored_rows.append(score)
            except Exception as e:
                print(f"[EVScreener] {symbol} スコア計算エラー: {e}")
                continue

        if not scored_rows:
            return pd.DataFrame()

        result = pd.DataFrame(scored_rows)
        top_n = self.params.get("top_n_symbols", 10)
        result = result.sort_values("total_score", ascending=False).head(top_n)
        result = result.reset_index(drop=True)
        result.index = result.index + 1
        return result

    def _evaluate_symbol(self, symbol: str, ticker_row: pd.Series) -> dict:
        """1銘柄の4次元スコアを算出"""
        # OHLCVデータ取得（15分足、200本）
        df = self.client.fetch_ohlcv(symbol, "15m", limit=200)
        ohlcv_ok = not df.empty and len(df) >= 50

        # --- 1. 流動性スコア (0-25) ---
        liquidity_score, liquidity_detail = self._calc_liquidity_score(
            symbol, ticker_row
        )

        # --- 2. 値幅スコア (0-25) ---
        range_score, range_detail = self._calc_range_score(df, ticker_row) if ohlcv_ok else (0, {})

        # --- 3. 素直さスコア (0-25) ---
        honest_score, honest_detail = self._calc_honesty_score(df) if ohlcv_ok else (0, {})

        # --- 4. 先物スコア (0-25) ---
        futures_score, futures_detail = self._calc_futures_score(symbol)

        total_score = liquidity_score + range_score + honest_score + futures_score

        return {
            "symbol": symbol,
            "price": ticker_row["last"],
            "change_pct": round(ticker_row["change_pct"], 2),
            "volume_quote": round(ticker_row["volume_quote"], 0),
            "liquidity_score": round(liquidity_score, 1),
            "range_score": round(range_score, 1),
            "honesty_score": round(honest_score, 1),
            "futures_score": round(futures_score, 1),
            "total_score": round(total_score, 1),
            # 詳細データ（展開表示用）
            "spread_pct": liquidity_detail.get("spread_pct", 0),
            "depth_value": liquidity_detail.get("depth_total_value", 0),
            "atr_pct": range_detail.get("atr_pct", 0),
            "wick_ratio": honest_detail.get("wick_ratio", 0),
            "funding_rate": futures_detail.get("funding_rate", 0),
            "oi_value": futures_detail.get("oi_value", 0),
        }

    # ──────────────────────────────
    # 1. 流動性スコア
    # ──────────────────────────────
    def _calc_liquidity_score(self, symbol: str, ticker_row: pd.Series) -> tuple[float, dict]:
        """24H出来高 + 板の厚み + スプレッド"""
        score = 0.0
        detail = {}

        # 24H出来高（USDT換算）
        vol = ticker_row["volume_quote"]
        if vol >= 1e8:        # 1億USDT以上
            vol_pts = 10
        elif vol >= 5e7:      # 5000万USDT以上
            vol_pts = 8
        elif vol >= 1e7:      # 1000万USDT以上
            vol_pts = 6
        elif vol >= 1e6:      # 100万USDT以上
            vol_pts = 3
        else:
            vol_pts = 1
        score += vol_pts

        # 板の厚み + スプレッド
        depth = self.client.fetch_orderbook_depth(symbol, limit=20)
        detail["spread_pct"] = depth.get("spread_pct", 0)
        detail["depth_total_value"] = depth.get("depth_total_value", 0)

        # スプレッド（小さいほど高スコア）
        sp = depth.get("spread_pct", 1)
        if sp <= 0.01:
            spread_pts = 8
        elif sp <= 0.03:
            spread_pts = 6
        elif sp <= 0.05:
            spread_pts = 4
        elif sp <= 0.1:
            spread_pts = 2
        else:
            spread_pts = 0
        score += spread_pts

        # 板の厚み（金額ベース）
        dtv = depth.get("depth_total_value", 0)
        if dtv >= 1e6:
            depth_pts = 7
        elif dtv >= 5e5:
            depth_pts = 5
        elif dtv >= 1e5:
            depth_pts = 3
        elif dtv >= 1e4:
            depth_pts = 1
        else:
            depth_pts = 0
        score += depth_pts

        return min(score, 25), detail

    # ──────────────────────────────
    # 2. 値幅スコア
    # ──────────────────────────────
    def _calc_range_score(self, df: pd.DataFrame, ticker_row: pd.Series) -> tuple[float, dict]:
        """ATR + 平均レンジ"""
        score = 0.0
        detail = {}

        try:
            close = df["close"]
            price = float(close.iloc[-1])

            # ATR（14期間）→ パーセンテージ化
            atr = ta_lib.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=14
            ).average_true_range()
            atr_val = float(atr.iloc[-1]) if atr is not None and not atr.empty else 0
            atr_pct = (atr_val / price * 100) if price > 0 else 0
            detail["atr_pct"] = round(atr_pct, 3)

            # ATRスコア（適度な値幅がベスト: 0.3%〜2%が最高点）
            if 0.5 <= atr_pct <= 2.0:
                atr_pts = 13
            elif 0.3 <= atr_pct <= 3.0:
                atr_pts = 10
            elif 0.1 <= atr_pct <= 5.0:
                atr_pts = 6
            elif atr_pct > 5.0:
                atr_pts = 3  # 変動激しすぎ
            else:
                atr_pts = 2  # 動かなさすぎ
            score += atr_pts

            # 平均レンジ（High-Low / Close の直近20本平均）
            hl_range_pct = ((df["high"] - df["low"]) / df["close"] * 100).tail(20).mean()
            detail["avg_range_pct"] = round(float(hl_range_pct), 3)

            if 0.5 <= hl_range_pct <= 2.5:
                range_pts = 12
            elif 0.2 <= hl_range_pct <= 4.0:
                range_pts = 8
            elif hl_range_pct > 4.0:
                range_pts = 4
            else:
                range_pts = 2
            score += range_pts

        except Exception as e:
            detail["error"] = str(e)

        return min(score, 25), detail

    # ──────────────────────────────
    # 3. 素直さスコア
    # ──────────────────────────────
    def _calc_honesty_score(self, df: pd.DataFrame) -> tuple[float, dict]:
        """出来高の継続性 + ヒゲ率 + 急変頻度"""
        score = 0.0
        detail = {}

        try:
            n = len(df)

            # 出来高の継続性（直近30本で出来高が安定しているか）
            vol_tail = df["volume"].tail(30)
            vol_cv = float(vol_tail.std() / vol_tail.mean()) if vol_tail.mean() > 0 else 999
            detail["volume_cv"] = round(vol_cv, 3)

            # CV（変動係数）が低いほど安定
            if vol_cv <= 0.5:
                vol_cont_pts = 9
            elif vol_cv <= 1.0:
                vol_cont_pts = 7
            elif vol_cv <= 1.5:
                vol_cont_pts = 4
            else:
                vol_cont_pts = 1
            score += vol_cont_pts

            # ヒゲ率（ヒゲの長さ / 実体 の平均）→ 小さいほど素直
            body = (df["close"] - df["open"]).abs()
            upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
            lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
            total_wick = upper_wick + lower_wick
            candle_range = df["high"] - df["low"]

            # ヒゲ率 = ヒゲ合計 / (ヒゲ+実体) の平均
            wick_ratio_series = total_wick / candle_range.replace(0, np.nan)
            wick_ratio = float(wick_ratio_series.tail(40).mean())
            detail["wick_ratio"] = round(wick_ratio, 3) if not np.isnan(wick_ratio) else 0

            # ヒゲ率が低い（0.2〜0.4）→ 素直な値動き
            if wick_ratio <= 0.3:
                wick_pts = 9
            elif wick_ratio <= 0.5:
                wick_pts = 7
            elif wick_ratio <= 0.65:
                wick_pts = 4
            else:
                wick_pts = 1
            score += wick_pts

            # 急変頻度（前足比で3%以上変動した足の割合）→ 少ないほど良い
            pct_change = df["close"].pct_change().abs()
            spike_count = int((pct_change > 0.03).sum())
            spike_ratio = spike_count / n if n > 0 else 0
            detail["spike_ratio"] = round(spike_ratio, 3)

            if spike_ratio <= 0.02:
                spike_pts = 7
            elif spike_ratio <= 0.05:
                spike_pts = 5
            elif spike_ratio <= 0.10:
                spike_pts = 3
            else:
                spike_pts = 1
            score += spike_pts

        except Exception as e:
            detail["error"] = str(e)

        return min(score, 25), detail

    # ──────────────────────────────
    # 4. 先物スコア
    # ──────────────────────────────
    def _calc_futures_score(self, symbol: str) -> tuple[float, dict]:
        """OI増減 + Funding Rate 極端さ"""
        score = 0.0
        detail = {}

        try:
            # OI取得
            oi_data = self.client.fetch_open_interest(symbol)
            oi_value = oi_data.get("open_interest_value", 0) or 0
            detail["oi_value"] = round(oi_value, 2)

            # OIが大きいほど市場の注目度が高い
            if oi_value >= 1e8:      # 1億以上
                oi_pts = 13
            elif oi_value >= 5e7:    # 5000万以上
                oi_pts = 10
            elif oi_value >= 1e7:    # 1000万以上
                oi_pts = 7
            elif oi_value >= 1e6:    # 100万以上
                oi_pts = 4
            else:
                oi_pts = 1
            score += oi_pts

            # Funding Rate
            fr_data = self.client.fetch_funding_rate(symbol)
            fr = fr_data.get("funding_rate", 0) or 0
            detail["funding_rate"] = round(fr * 100, 4)  # パーセント表示

            # 極端なFR（±0.1%以上）は逆張り機会 → 高スコア
            # 通常（±0.01%程度）は中スコア
            abs_fr = abs(fr) * 100  # パーセント化
            if abs_fr >= 0.1:
                fr_pts = 12  # 極端：逆張り狙い有り
            elif abs_fr >= 0.05:
                fr_pts = 9
            elif abs_fr >= 0.01:
                fr_pts = 6   # 通常
            else:
                fr_pts = 3   # 平穏
            score += fr_pts

        except Exception as e:
            detail["error"] = str(e)

        return min(score, 25), detail

