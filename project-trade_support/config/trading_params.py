"""
取引パラメータ - リスク許容度・スクリーニング閾値などのデフォルト値
"""


# ── スクリーニングパラメータ ──
SCREENING_PARAMS = {
    "min_change_rate": 3.0,          # 24h変動率の最小値 (%)
    "min_volume_percentile": 80,     # 24h取引量の最小パーセンタイル
    "min_atr_multiplier": 1.0,       # ATRの最小倍率
    "min_adx": 25,                   # ADX最小値（トレンド強度）
    "volume_spike_ratio": 2.0,       # 出来高急変の倍率閾値
    "top_n_symbols": 10,             # 上位N銘柄を選出
    "ev_candidate_n": 10,            # 期待値スクリーニング候補数
}

# ── リスク管理パラメータ ──
RISK_PARAMS = {
    "max_loss_per_trade_pct": 2.0,   # 1トレード最大損失（資金比 %）
    "max_leverage": 10,              # 最大レバレッジ
    "min_risk_reward_ratio": 2.0,    # 最小リスクリワード比
    "max_consecutive_losses": 3,     # 連続損失で休止提案する回数
}

# ── テクニカル分析パラメータ ──
ANALYSIS_PARAMS = {
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "ema_periods": [9, 21, 55, 200],
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bb_period": 20,
    "bb_std": 2,
    "volume_avg_period": 20,
    "atr_period": 14,
    "fibonacci_levels": [0.236, 0.382, 0.5, 0.618],
}

# ── 時間足設定 ──
TIMEFRAMES = {
    "upper": ["4h", "1h"],      # 上位足（トレンド確認用）
    "lower": ["15m", "5m"],     # 下位足（エントリータイミング用）
    "default": "15m",           # デフォルト分析足
}

# ── 監視パラメータ ──
MONITOR_PARAMS = {
    "price_check_interval_sec": 30,       # 価格チェック間隔（秒）
    "technical_check_interval_min": 5,    # テクニカル確認間隔（分）
    "scenario_check_interval_min": 15,    # シナリオ判定間隔（分）
    "volume_check_interval_min": 1,       # 出来高チェック間隔（分）
    "tp_alert_threshold_pct": 90,         # TP接近アラート閾値 (%)
    "sl_alert_threshold_pct": 80,         # SL接近アラート閾値 (%)
    "report_interval_hours": 1,           # 定期レポート間隔（時間）
}
