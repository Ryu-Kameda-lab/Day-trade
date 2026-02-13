"""
Streamlit ダッシュボード - AI仮想通貨デイトレードアシスタント
マルチページ構成: ホーム / 分析＆提案 / 監視モニター / 設定
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime
import sys
import os
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    MEXC_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,
    GOOGLE_API_KEY, DISCORD_WEBHOOK_URL, is_configured,
)
from config.trading_params import (
    SCREENING_PARAMS, RISK_PARAMS, ANALYSIS_PARAMS, TIMEFRAMES, MONITOR_PARAMS,
)
from exchange.mexc_client import MEXCClient
from ai.llm_client import LLMClient
from modules.screener import Screener, ExpectedValueScreener
from modules.analyzer import Analyzer
from modules.strategist import Strategist
from modules.strategist import Strategist
from modules.monitor import MarketMonitor
from modules.notifier import Notifier
from modules.gemini_reviewer import GeminiReviewer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="AI Trading Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# カスタムCSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown label {
        color: #e0e0ff !important;
    }

    /* メトリクスカード */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e1e3f 0%, #2a2a5a 100%);
        border: 1px solid rgba(100, 100, 255, 0.2);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    }
    div[data-testid="stMetric"] label {
        color: #8888cc !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 600;
    }

    /* ボタン */
    .stButton > button {
        background: linear-gradient(135deg, #4a00e0 0%, #8e2de2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 24px;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(74, 0, 224, 0.3);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(74, 0, 224, 0.5);
    }

    /* タブ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(30, 30, 63, 0.5);
        border-radius: 8px;
        padding: 8px 16px;
        color: #8888cc;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #4a00e0 0%, #8e2de2 100%) !important;
        color: white !important;
    }

    /* テーブル */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* 成功/警告ボックス */
    .success-box {
        background: linear-gradient(135deg, rgba(0, 200, 117, 0.15) 0%, rgba(0, 200, 117, 0.05) 100%);
        border: 1px solid rgba(0, 200, 117, 0.3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .warning-box {
        background: linear-gradient(135deg, rgba(255, 165, 0, 0.15) 0%, rgba(255, 165, 0, 0.05) 100%);
        border: 1px solid rgba(255, 165, 0, 0.3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .danger-box {
        background: linear-gradient(135deg, rgba(255, 71, 87, 0.15) 0%, rgba(255, 71, 87, 0.05) 100%);
        border: 1px solid rgba(255, 71, 87, 0.3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .info-box {
        background: linear-gradient(135deg, rgba(52, 152, 219, 0.15) 0%, rgba(52, 152, 219, 0.05) 100%);
        border: 1px solid rgba(52, 152, 219, 0.3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }

    /* ヘッダー */
    .main-header {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #2d1b69 100%);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        border: 1px solid rgba(100, 100, 255, 0.15);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        background: linear-gradient(135deg, #a78bfa, #818cf8, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem !important;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #8888cc;
        margin: 4px 0 0 0;
        font-size: 0.9rem;
    }

    /* スコアカード */
    .score-card {
        background: linear-gradient(135deg, #1e1e3f 0%, #2a2a5a 100%);
        border: 1px solid rgba(100, 100, 255, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    .score-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #a78bfa, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* 期待値タブ用 */
    .ev-score-bar {
        background: linear-gradient(90deg, rgba(100,100,255,0.2) 0%, rgba(100,100,255,0.05) 100%);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
        border-left: 4px solid rgba(100,100,255,0.5);
    }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セッション状態の初期化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def init_session_state():
    defaults = {
        "screening_results": None,
        "ev_screening_results": None,
        "selected_symbol": None,
        "analysis_result": None,
        "strategy_result": None,
        "market_monitor": None,
        "notifier": None,
        "notification_history": [],
        "screening_params": SCREENING_PARAMS.copy(),
        "risk_params": RISK_PARAMS.copy(),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()

PAGE_HOME = "\U0001f3e0 \u30db\u30fc\u30e0"
PAGE_ANALYSIS = "\U0001f4c8 \u5206\u6790 & \u63d0\u6848"
PAGE_LOGS = "\U0001f4cb \u63d0\u6848\u30ed\u30b0"
PAGE_SETTINGS = "\u2699\ufe0f \u8a2d\u5b9a"
PAGE_OPTIONS = [PAGE_HOME, PAGE_ANALYSIS, PAGE_LOGS, PAGE_SETTINGS]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 常駐ボット管理 (Singleton)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class BotService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.monitor = MarketMonitor()
        self.reviewer = GeminiReviewer()
        self._setup_jobs()
        
    def _setup_jobs(self):
        # 15分ごとの市場監視
        self.scheduler.add_job(
            self.monitor.run_market_cycle,
        #    'interval', minutes=15,
            CronTrigger(minute='0,15,30,45'),
            id='market_monitor',
            replace_existing=True
        )
        # 1時間ごとの査読
        self.scheduler.add_job(
            self.reviewer.review_past_logs,
        #    'interval', minutes=60,
            CronTrigger(minute='10'),
            id='gemini_reviewer',
            replace_existing=True
        )

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            print("BotService started.")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("BotService stopped.")

    @property
    def is_running(self):
        return self.scheduler.running

@st.cache_resource
def get_bot_service():
    service = BotService()
    # デフォルトで起動 (初期ON)
    service.start()
    return service


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 共有コンポーネント初期化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_resource
def get_mexc_client():
    return MEXCClient()

@st.cache_resource
def get_llm_client():
    return LLMClient()

def get_screener():
    return Screener(get_mexc_client(), st.session_state.screening_params)

def get_ev_screener():
    return ExpectedValueScreener(get_mexc_client(), st.session_state.screening_params)

def get_analyzer():
    return Analyzer(get_mexc_client(), get_llm_client())

def get_strategist():
    return Strategist(get_llm_client(), st.session_state.risk_params)

def get_market_monitor():
    if st.session_state.market_monitor is None:
        st.session_state.market_monitor = MarketMonitor(get_mexc_client(), get_llm_client(), get_notifier())
    return st.session_state.market_monitor

def get_gemini_reviewer():
    return GeminiReviewer(get_mexc_client(), get_llm_client())

def get_notifier():
    if st.session_state.notifier is None:
        st.session_state.notifier = Notifier()
    return st.session_state.notifier


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# サイドバー ナビゲーション
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown("## 📊 AI Trading Assistant")
    st.markdown("---")

    page = st.radio(
        "ナビゲーション",
        PAGE_OPTIONS,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # API接続ステータス
    st.markdown("### 接続ステータス")
    apis = {
        "MEXC": is_configured("MEXC_API_KEY"),
        "OpenAI": is_configured("OPENAI_API_KEY"),
        "Claude": is_configured("ANTHROPIC_API_KEY"),
        "Gemini": is_configured("GOOGLE_API_KEY"),
        "Discord": is_configured("DISCORD_WEBHOOK_URL"),
    }
    for name, connected in apis.items():
        icon = "🟢" if connected else "🔴"
        st.markdown(f"{icon} {name}")

    st.markdown("---")
    
    # 時間表示 (リアルタイム更新用)
    time_placeholder = st.empty()
    time_placeholder.caption(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("⚠️ 投資助言ではありません")

    # ボット制御パネル
    st.markdown("---")
    st.markdown("### 🤖 自動売買ボット")
    
    bot_service = get_bot_service()
    
    # 状態確認
    state = bot_service.scheduler.state
    # 0=STOPPED, 1=RUNNING, 2=PAUSED
    
    if state == 1: # RUNNING
        st.success("稼働中 🟢")
        if st.button("一時停止 (Pause)", key="btn_pause_bot"):
            bot_service.scheduler.pause()
            st.rerun()
            
    elif state == 2: # PAUSED
        st.warning("一時停止中 ⏸️")
        if st.button("再開 (Resume)", key="btn_resume_bot"):
            bot_service.scheduler.resume()
            st.rerun()
            
    else: # STOPPED
        st.error("停止中 🔴")
        if st.button("起動 (Start)", key="btn_start_bot"):
            bot_service.start()
            st.rerun()
            
    st.caption("※ 基準: 毎時 00/15/30/45分に監視、10分に査読")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ 1: ホーム（スクリーニング結果 - タブ切替）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def page_home():
    st.markdown("""
    <div class="main-header">
        <h1>🏠 スクリーニング</h1>
        <p>MEXC先物市場から銘柄を自動抽出 — 指標基準 / 期待値基準を切替えて分析</p>
    </div>
    """, unsafe_allow_html=True)

    screening_tab1, screening_tab2 = st.tabs([
        "\U0001f4ca \u30b9\u30af\u30ea\u30fc\u30cb\u30f3\u30b0\u7d50\u679c\u4e00\u89a7\uff08\u6307\u6a19\u57fa\u6e96\uff09",
        "\U0001f3af \u30b9\u30af\u30ea\u30fc\u30cb\u30f3\u30b0\u7d50\u679c\u4e00\u89a7\uff08\u671f\u5f85\u5024\u57fa\u6e96\uff09",
    ])

    # ── タブ1: 指標基準 ──
    with screening_tab1:
        _render_indicator_screening()

    # ── タブ2: 期待値基準 ──
    with screening_tab2:
        _render_ev_screening()


def _render_indicator_screening():
    """指標基準スクリーニング"""
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔍 スクリーニング実行（指標基準）", use_container_width=True, key="btn_ind"):
            with st.spinner("MEXC先物市場をスキャン中..."):
                screener = get_screener()
                results = screener.run_screening()
                st.session_state.screening_results = results

    with col2:
        min_change = st.number_input(
            "最小変動率 (%)", value=st.session_state.screening_params["min_change_rate"],
            min_value=0.5, max_value=20.0, step=0.5, key="ind_min_change"
        )
        st.session_state.screening_params["min_change_rate"] = min_change

    with col3:
        top_n = st.number_input(
            "表示銘柄数", value=st.session_state.screening_params["top_n_symbols"],
            min_value=3, max_value=30, step=1, key="ind_top_n"
        )
        st.session_state.screening_params["top_n_symbols"] = top_n

    results = st.session_state.screening_results

    if results is not None and not results.empty:
        st.markdown("---")

        # サマリーメトリクス
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("候補銘柄数", f"{len(results)} 銘柄")
        with c2:
            avg_score = results["total_score"].mean()
            st.metric("平均スコア", f"{avg_score:.1f}")
        with c3:
            top_symbol = results.iloc[0]["symbol"]
            st.metric("トップ銘柄", top_symbol.split("/")[0] if "/" in top_symbol else top_symbol)
        with c4:
            max_change = results["change_pct"].abs().max()
            st.metric("最大変動率", f"{max_change:.1f}%")

        st.markdown("---")

        # 結果テーブル
        st.markdown("### 📋 スクリーニング結果一覧（指標基準）")
        display_cols = ["symbol", "price", "change_pct", "total_score",
                       "change_score", "volume_score", "volatility_score", "trend_score"]
        available = [c for c in display_cols if c in results.columns]

        styled_df = results[available].copy()
        styled_df.columns = [
            c.replace("symbol", "シンボル")
             .replace("price", "価格")
             .replace("change_pct", "変動率(%)")
             .replace("total_score", "総合スコア")
             .replace("change_score", "変動スコア")
             .replace("volume_score", "出来高スコア")
             .replace("volatility_score", "ボラスコア")
             .replace("trend_score", "トレンドスコア")
            for c in available
        ]

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=min(400, 40 + 35 * len(styled_df)),
        )

        # 銘柄選択
        _render_symbol_selector(results)

    elif results is not None and results.empty:
        st.markdown("""
        <div class="warning-box">
        <h4>⚠️ 該当銘柄なし</h4>
        <p>現在のスクリーニング条件に一致する銘柄が見つかりませんでした。条件を緩和してみてください。</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-box">
        <h4>💡 スクリーニングを開始してください</h4>
        <p>上の「🔍 スクリーニング実行」ボタンを押してMEXC先物市場をスキャンします。</p>
        </div>
        """, unsafe_allow_html=True)


def _render_ev_screening():
    """期待値基準スクリーニング"""
    st.markdown("""
    <div class="info-box">
    <h4>🎯 期待値基準スクリーニングとは</h4>
    <p>「トレードしやすい銘柄」を4つの視点で評価します：</p>
    <ul>
    <li><b>流動性スコア</b> — 24H出来高、板の厚み、スプレッド</li>
    <li><b>値幅スコア</b> — ATR、平均レンジ（適度な値幅か）</li>
    <li><b>素直さスコア</b> — 出来高の継続性、ヒゲ率、急変頻度</li>
    <li><b>先物スコア</b> — OI（未決済建玉）、Funding Rate の極端さ</li>
    </ul>
    <p>各スコア0〜25点、合計0〜100点で評価します。</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🎯 期待値スクリーニング実行", use_container_width=True, key="btn_ev"):
            ev_screener = get_ev_screener()
            progress_bar = st.progress(0, text="スキャン準備中...")
            status_text = st.empty()

            def on_progress(current, total, symbol):
                pct = current / total
                progress_bar.progress(pct, text=f"分析中 ({current}/{total}): {symbol}")

            with st.spinner("MEXC先物市場を期待値基準でスキャン中（板・OI・FR取得のため時間がかかります）..."):
                results = ev_screener.run_screening(progress_callback=on_progress)
                st.session_state.ev_screening_results = results

            progress_bar.empty()

    with col2:
        ev_n = st.number_input(
            "候補銘柄数", value=st.session_state.screening_params["ev_candidate_n"],
            min_value=10, max_value=50, step=5, key="ev_cand_n"
        )
        st.session_state.screening_params["ev_candidate_n"] = ev_n

    ev_results = st.session_state.ev_screening_results

    if ev_results is not None and not ev_results.empty:
        st.markdown("---")

        # サマリー
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("候補銘柄数", f"{len(ev_results)} 銘柄")
        with c2:
            avg_score = ev_results["total_score"].mean()
            st.metric("平均スコア", f"{avg_score:.1f} / 100")
        with c3:
            top_sym = ev_results.iloc[0]["symbol"]
            st.metric("トップ銘柄", top_sym.split("/")[0] if "/" in top_sym else top_sym)
        with c4:
            top_score = ev_results.iloc[0]["total_score"]
            st.metric("最高スコア", f"{top_score:.1f}")

        st.markdown("---")

        # 結果テーブル
        st.markdown("### 📋 スクリーニング結果一覧（期待値基準）")
        display_cols = [
            "symbol", "price", "change_pct", "total_score",
            "liquidity_score", "range_score", "honesty_score", "futures_score",
            "spread_pct", "atr_pct", "wick_ratio", "funding_rate",
        ]
        available = [c for c in display_cols if c in ev_results.columns]

        styled_df = ev_results[available].copy()
        col_names = {
            "symbol": "シンボル", "price": "価格", "change_pct": "変動率(%)",
            "total_score": "総合スコア",
            "liquidity_score": "流動性", "range_score": "値幅",
            "honesty_score": "素直さ", "futures_score": "先物",
            "spread_pct": "スプレッド(%)", "atr_pct": "ATR(%)",
            "wick_ratio": "ヒゲ率", "funding_rate": "FR(%)",
        }
        styled_df.columns = [col_names.get(c, c) for c in available]

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=min(500, 40 + 35 * len(styled_df)),
        )

        # 各銘柄のスコア内訳
        st.markdown("### 📊 スコア内訳")
        for i, (_, row) in enumerate(ev_results.iterrows()):
            sym = row["symbol"]
            short_sym = sym.split("/")[0] if "/" in sym else sym
            with st.expander(f"#{i} {short_sym} — 総合 {row['total_score']:.1f}pt"):
                mc1, mc2, mc3, mc4 = st.columns(4)
                with mc1:
                    st.markdown(f"""<div class="ev-score-bar">
                    <b>💧 流動性</b><br>{row['liquidity_score']:.1f} / 25
                    </div>""", unsafe_allow_html=True)
                    st.caption(f"Spread: {row.get('spread_pct', 0):.4f}%")
                    st.caption(f"板厚: ${row.get('depth_value', 0):,.0f}")
                with mc2:
                    st.markdown(f"""<div class="ev-score-bar">
                    <b>📏 値幅</b><br>{row['range_score']:.1f} / 25
                    </div>""", unsafe_allow_html=True)
                    st.caption(f"ATR: {row.get('atr_pct', 0):.3f}%")
                with mc3:
                    st.markdown(f"""<div class="ev-score-bar">
                    <b>🎯 素直さ</b><br>{row['honesty_score']:.1f} / 25
                    </div>""", unsafe_allow_html=True)
                    st.caption(f"ヒゲ率: {row.get('wick_ratio', 0):.3f}")
                with mc4:
                    st.markdown(f"""<div class="ev-score-bar">
                    <b>📈 先物</b><br>{row['futures_score']:.1f} / 25
                    </div>""", unsafe_allow_html=True)
                    st.caption(f"FR: {row.get('funding_rate', 0):.4f}%")
                    st.caption(f"OI: ${row.get('oi_value', 0):,.0f}")

        # 銘柄選択
        _render_symbol_selector(ev_results, key_suffix="_ev")

    elif ev_results is not None and ev_results.empty:
        st.markdown("""
        <div class="warning-box">
        <h4>⚠️ 該当銘柄なし</h4>
        <p>期待値基準でスコアリング可能な銘柄が見つかりませんでした。</p>
        </div>
        """, unsafe_allow_html=True)


def _render_symbol_selector(results, key_suffix=""):
    """銘柄選択UI（両タブ共通）"""
    st.markdown("### 🎯 銘柄を選択して分析 & 提案へ")
    symbols = results["symbol"].tolist()
    selected = st.selectbox("銘柄を選択", symbols, index=0, key=f"select_sym{key_suffix}")
    if st.button("📈 この銘柄を分析する", key=f"btn_analyze{key_suffix}"):
        st.session_state.selected_symbol = selected
        st.success(f"✅ {selected} を選択しました。「📈 分析 & 提案」ページへ移動してください。")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ 2: 分析 & 提案（統合ページ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def page_analysis_and_strategy():
    st.markdown("""
    <div class="main-header">
        <h1>📈 分析 & 提案</h1>
        <p>チャート・テクニカル分析・AI判断・取引提案を1画面で確認</p>
    </div>
    """, unsafe_allow_html=True)

    symbol = st.session_state.selected_symbol
    if not symbol:
        st.info("🏠 ホームページで銘柄を選択してください。")
        manual = st.text_input("または銘柄を手動入力", placeholder="例: BTC/USDT:USDT")
        if manual:
            symbol = manual
            st.session_state.selected_symbol = symbol

    if not symbol:
        return

    st.markdown(f"### 分析対象: `{symbol}`")

    # コントロール行
    ctl1, ctl2, ctl3 = st.columns([1, 1, 1])
    with ctl1:
        timeframe = st.selectbox("時間足", ["5m", "15m", "1h", "4h"], index=1)
    with ctl2:
        run_analysis = st.button("🔬 AI分析を実行", use_container_width=True)
    with ctl3:
        run_proposal = st.button("💡 取引提案を生成", use_container_width=True)

    if run_analysis:
        with st.spinner(f"{symbol} を分析中... (AIに問い合わせています)"):
            analyzer = get_analyzer()
            result = analyzer.get_ai_analysis(symbol, timeframe)
            st.session_state.analysis_result = result

    # ─────── チャート ───────
    st.markdown("---")
    _render_chart(symbol, timeframe)

    # ─────── AI分析結果 ───────
    result = st.session_state.analysis_result
    if result and result.get("symbol") == symbol:
        _render_ai_analysis(result)

    # ─────── 取引提案 ───────
    if run_proposal:
        analysis = st.session_state.analysis_result
        if not analysis:
            st.warning("先にAI分析を実行してください。")
        else:
            with st.spinner("AIが取引戦略を考案中..."):
                strategist = get_strategist()
                proposal = strategist.generate_proposal(analysis)
                st.session_state.strategy_result = {
                    "main_proposal": proposal,
                    "second_opinion": None,
                    "final_decision": None,
                }

    strategy = st.session_state.strategy_result
    if strategy and st.session_state.analysis_result:
        _render_strategy(symbol, strategy)


def _render_chart(symbol, timeframe):
    """チャート描画"""
    st.markdown("### 📊 チャート")
    analyzer = get_analyzer()
    df = analyzer.get_ohlcv_df(symbol, timeframe, 200)

    if not df.empty:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=("", "出来高"),
        )

        # ローソク足チャート
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="OHLC",
            increasing_line_color="#00c853",
            decreasing_line_color="#ff1744",
        ), row=1, col=1)

        # EMA
        import ta as ta_chart
        for period in [9, 21, 55]:
            ema = ta_chart.trend.EMAIndicator(df["close"], window=period).ema_indicator()
            if ema is not None and not ema.empty:
                colors = {9: "#ffd700", 21: "#00bcd4", 55: "#ff6b6b"}
                fig.add_trace(go.Scatter(
                    x=df.index, y=ema,
                    name=f"EMA {period}",
                    line=dict(width=1, color=colors.get(period, "#888")),
                ), row=1, col=1)

        # ボリンジャーバンド
        bb_indicator = ta_chart.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        bb_upper = bb_indicator.bollinger_hband()
        bb_lower = bb_indicator.bollinger_lband()
        if bb_upper is not None and not bb_upper.empty:
            fig.add_trace(go.Scatter(
                x=df.index, y=bb_upper, name="BB Upper",
                line=dict(width=1, dash="dash", color="rgba(150,150,255,0.4)"),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=bb_lower, name="BB Lower",
                line=dict(width=1, dash="dash", color="rgba(150,150,255,0.4)"),
                fill="tonexty", fillcolor="rgba(150,150,255,0.05)",
            ), row=1, col=1)

        # 出来高
        colors = ["#00c853" if c >= o else "#ff1744" for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["volume"], name="Volume",
            marker_color=colors, opacity=0.5,
        ), row=2, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis_rangeslider_visible=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,15,35,0.8)",
            margin=dict(l=60, r=20, t=40, b=40),
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("チャートデータを取得できませんでした。")


def _render_ai_analysis(result):
    """AI分析結果の表示"""
    st.markdown("---")
    st.markdown("### 🤖 AI分析結果")

    ai = result.get("ai_analysis", {})

    if "error" in ai or "raw_response" in ai:
        st.warning("AI分析結果のパースに問題がありました。")
        st.json(ai)
    else:
        judgment = ai.get("judgment", "N/A")
        confidence = ai.get("confidence", "N/A")
        summary = ai.get("summary", "")

        judgment_icon = {"bullish": "🟢 強気", "bearish": "🔴 弱気", "neutral": "🟡 中立"}.get(judgment, judgment)
        conf_icon = {"high": "⭐⭐⭐", "medium": "⭐⭐", "low": "⭐"}.get(confidence, confidence)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("判定", judgment_icon)
        with c2:
            st.metric("信頼度", conf_icon)
        with c3:
            st.metric("現在価格", f"{result.get('current_price', 'N/A')}")

        if summary:
            st.markdown(f"""
            <div class="info-box">
            <h4>📝 分析サマリー</h4>
            <p>{summary}</p>
            </div>
            """, unsafe_allow_html=True)

        # シグナル一覧
        signals = ai.get("signals", [])
        if signals:
            st.markdown("#### 📡 シグナル一覧")
            for sig in signals:
                weight_icon = {"strong": "🔵", "moderate": "🟡", "weak": "⚪"}.get(sig.get("weight", ""), "")
                st.markdown(f"- {weight_icon} **{sig.get('indicator', '')}**: {sig.get('signal', '')}")

        # キーレベル + リスク要因（横並び）
        kl1, kl2 = st.columns(2)
        key_levels = ai.get("key_levels", {})
        if key_levels:
            with kl1:
                st.markdown("#### 🛡️ サポート / 🚧 レジスタンス")
                for level in key_levels.get("support", []):
                    st.markdown(f"- 🟢 `{level}`")
                for level in key_levels.get("resistance", []):
                    st.markdown(f"- 🔴 `{level}`")

        risk_factors = ai.get("risk_factors", [])
        if risk_factors:
            with kl2:
                st.markdown("#### ⚠️ リスク要因")
                for rf in risk_factors:
                    st.markdown(f"- {rf}")

    # テクニカル指標の詳細
    with st.expander("📊 テクニカル指標データ（詳細）"):
        indicators = result.get("indicators", {})
        st.json(indicators)


def _render_strategy(symbol, strategy):
    """取引提案セクションの表示"""
    st.markdown("---")
    st.markdown("### 💡 取引提案")

    # ダブルチェックボタン
    if st.button("🔄 ダブルチェック（Claude）", use_container_width=False, key="btn_dc"):
        if strategy.get("main_proposal"):
            with st.spinner("Claudeでセカンドオピニオンを取得中..."):
                strategist = get_strategist()
                so = strategist.get_second_opinion(
                    strategy["main_proposal"], st.session_state.analysis_result
                )
                strategy["second_opinion"] = so
                strategy["final_decision"] = strategist._make_final_decision(
                    strategy["main_proposal"], so
                )
                st.session_state.strategy_result = strategy

    # メイン提案
    main = strategy.get("main_proposal", {})
    proposal = main.get("proposal", {})

    if "raw_response" in proposal:
        st.warning("提案のパースに問題がありました。")
        st.json(proposal)
        return

    direction = proposal.get("direction", "skip")

    if direction == "skip":
        st.markdown("""
        <div class="warning-box">
        <h3>⏸️ 取引見送り</h3>
        <p>AIは現在の相場状況では取引を見送ることを推奨します。</p>
        </div>
        """, unsafe_allow_html=True)
        reasoning = proposal.get("reasoning", "")
        if reasoning:
            st.markdown(f"**理由**: {reasoning}")
    else:
        dir_icon = "🟢 LONG" if direction == "long" else "🔴 SHORT"
        st.markdown(f"## {dir_icon}")

        entry = proposal.get("entry_price", {})
        tp = proposal.get("take_profit", {})
        sl = proposal.get("stop_loss", {})

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            <div class="score-card">
            <h4>🎯 エントリー</h4>
            </div>
            """, unsafe_allow_html=True)
            st.metric("理想価格", entry.get("ideal", "N/A"))
            st.caption(f"レンジ: {entry.get('range_low', '?')} 〜 {entry.get('range_high', '?')}")

        with c2:
            st.markdown("""
            <div class="score-card">
            <h4>✅ 利確ライン</h4>
            </div>
            """, unsafe_allow_html=True)
            st.metric("TP1", tp.get("tp1", "N/A"))
            st.metric("TP2", tp.get("tp2", "N/A"))

        with c3:
            st.markdown("""
            <div class="score-card">
            <h4>🛑 損切りライン</h4>
            </div>
            """, unsafe_allow_html=True)
            st.metric("SL", sl.get("price", "N/A"))
            st.caption(f"根拠: {sl.get('reason', 'N/A')}")

        # メタ情報
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            rr = proposal.get("risk_reward_ratio", "N/A")
            st.metric("R:R比", f"1:{rr}")
        with c2:
            conf = proposal.get("confidence", "N/A")
            conf_icon = {"high": "⭐⭐⭐ 高", "medium": "⭐⭐ 中", "low": "⭐ 低"}.get(conf, conf)
            st.metric("信頼度", conf_icon)
        with c3:
            st.metric("現在価格", main.get("current_price", "N/A"))

        # シナリオ崩壊条件
        invalidation = proposal.get("scenario_invalidation", "")
        if invalidation:
            st.markdown(f"""
            <div class="danger-box">
            <h4>⚠️ シナリオ崩壊条件</h4>
            <p>{invalidation}</p>
            </div>
            """, unsafe_allow_html=True)

        # 根拠
        reasoning = proposal.get("reasoning", "")
        if reasoning:
            st.markdown(f"""
            <div class="info-box">
            <h4>💬 提案の根拠</h4>
            <p>{reasoning}</p>
            </div>
            """, unsafe_allow_html=True)

        # 警告
        warning = proposal.get("warning", "")
        if warning:
            st.warning(f"⚠️ {warning}")

    # セカンドオピニオン
    so = strategy.get("second_opinion")
    if so:
        st.markdown("---")
        st.markdown("#### 🔄 セカンドオピニオン（Claude）")

        agreement = so.get("agreement", "N/A")
        agree_icon = {
            "agree": "✅ 同意",
            "partially_agree": "⚠️ 部分同意",
            "disagree": "❌ 不同意",
        }.get(agreement, agreement)

        st.markdown(f"**判定**: {agree_icon}")
        review = so.get("review_comment", "")
        if review:
            st.markdown(f"**コメント**: {review}")

        risk = so.get("risk_assessment", "")
        if risk:
            st.markdown(f"**リスク評価**: {risk}")

    # 最終判定
    fd = strategy.get("final_decision")
    if fd:
        st.markdown("---")
        st.markdown("#### 🏁 最終判定")
        message = fd.get("message", "")
        status = fd.get("status", "")

        box_class = {
            "confirmed": "success-box",
            "partial": "warning-box",
            "rejected": "danger-box",
            "skip": "warning-box",
            "single_check": "info-box",
        }.get(status, "info-box")

        st.markdown(f"""
        <div class="{box_class}">
        <h4>{message}</h4>
        </div>
        """, unsafe_allow_html=True)

    # 監視登録ボタン
    if direction != "skip" and proposal.get("entry_price"):
        st.markdown("---")
        st.markdown("### 👁️ ポジション監視に登録")

        entry = proposal.get("entry_price", {})
        tp = proposal.get("take_profit", {})
        sl = proposal.get("stop_loss", {})

        with st.form("register_position"):
            fc1, fc2 = st.columns(2)
            with fc1:
                leverage = st.number_input("レバレッジ", 1, 50, 5)
                quantity = st.number_input("数量", 0.001, 10000.0, 0.1, step=0.01)
            with fc2:
                custom_entry = st.number_input(
                    "エントリー価格（調整可）",
                    value=float(entry.get("ideal", 0)) if entry.get("ideal") else 0.0,
                    format="%.6f",
                )
                custom_sl = st.number_input(
                    "損切り価格（調整可）",
                    value=float(sl.get("price", 0)) if sl.get("price") else 0.0,
                    format="%.6f",
                )

            submitted = st.form_submit_button("👁️ 監視を開始", use_container_width=True)
            if submitted:
                pos = Position(
                    symbol=symbol,
                    direction=direction,
                    entry_price=custom_entry,
                    tp1=float(tp.get("tp1", 0)),
                    tp2=float(tp.get("tp2", 0)),
                    stop_loss=custom_sl,
                    invalidation_condition=proposal.get("scenario_invalidation", ""),
                    leverage=leverage,
                    quantity=quantity,
                )
                monitor = get_monitor()
                monitor.add_position(pos)
                st.success(f"✅ {symbol} の監視を開始しました。「👁️ 監視モニター」ページで確認できます。")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ 3: 提案ログ (旧監視モニター)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def page_proposal_logs():
    st.markdown("""
    <div class="main-header">
        <h1>📋 提案ログ</h1>
        <p>AIによる市場監視の結果と、Geminiによる事後評価（査読）を確認</p>
    </div>
    """, unsafe_allow_html=True)

    monitor = get_market_monitor()
    
    # 制御パネル
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 最新の市場サイクルを実行 (15分推奨)", use_container_width=True):
            with st.spinner("市場をスキャンして分析中..."):
                proposals = monitor.run_market_cycle()
                if proposals:
                    st.success(f"{len(proposals)} 件の有望な提案が見つかりました！")
                else:
                    st.info("条件を満たす提案はありませんでした。")
                    
    with c2:
        if st.button("🕵️ 過去ログを査読 (Gemini)", use_container_width=True):
            with st.spinner("Geminiが過去の提案を評価中..."):
                reviewer = get_gemini_reviewer()
                reviewer.review_past_logs()
                st.success("査読プロセスが完了しました。")

    st.markdown("---")

    # ログ表示タブ
    tab1, tab2 = st.tabs([
        "\U0001f195 \u6700\u65b0\u306e\u63d0\u6848\u30ed\u30b0",
        "\u2705 \u67fb\u8aad\u6e08\u307f\u30ed\u30b0",
    ])

    # 最新ログ (limit=50)
    with tab1:
        logs = monitor.get_latest_logs(50)
        _render_log_list(logs, reviewed_only=False)

    # 査読済みログ (Reviewed_*) -> 実装簡易化のため、ここでは「gemini_review」があるものを抽出表示する形でも良いが
    # ファイルベースで分かれているので、gemini_reviewerのロジックに合わせて表示する
    with tab2:
        # 査読済みファイルのみ読み込むロジックをmonitorに追加してもいいが、
        # ここでは単純に全ログから `gemini_review` があるものを抽出して表示する
        logs = monitor.get_latest_logs(100)
        reviewed_logs = [l for l in logs if l.get("gemini_review")]
        _render_log_list(reviewed_logs, reviewed_only=True)


def _render_log_list(logs: list, reviewed_only: bool = False):
    """ログリストを表示"""
    if not logs:
        st.info("表示できるログはありません。")
        return

    for i, log in enumerate(logs):
        symbol = log.get("symbol", "N/A")
        timestamp = log.get("timestamp", "")
        direction = log.get("direction", "skip")
        conf = log.get("confidence", "low")
        score = log.get("screening_score", 0)
        
        gemini = log.get("gemini_review")
        
        # ヘッダー作成
        time_str = datetime.fromisoformat(timestamp).strftime('%m/%d %H:%M') if timestamp else ""
        dir_icon = "🟢" if direction == "long" else "🔴"
        
        header = f"{time_str} | {dir_icon} {symbol} | 信頼度: {conf} | スコア: {score}"
        
        if gemini:
            g_score = gemini.get("score", 0)
            header += f" | 🕵️ 採点: {g_score}点"

        with st.expander(header):
            # 2カラムレイアウト
            c1, c2 = st.columns(2)
            
            # 左: 提案内容
            with c1:
                st.markdown("#### 💡 提案内容")
                main = log.get("main_proposal", {})
                entry = main.get("entry_price", {}).get("ideal", "N/A")
                tp = main.get("take_profit", {}).get("tp1", "N/A")
                sl = main.get("stop_loss", {}).get("price", "N/A")
                
                st.markdown(f"**価格**: {log.get('price')}")
                st.markdown(f"**Entry**: {entry}")
                st.markdown(f"**TP**: {tp} / **SL**: {sl}")
                st.markdown(f"**根拠**: {main.get('reasoning')}")
                
                if log.get("so_executed"):
                    st.markdown("---")
                    st.markdown("#### 🔄 セカンドオピニオン")
                    so = log.get("second_opinion", {})
                    st.markdown(f"**判定**: {so.get('agreement')}")
                    st.markdown(f"**コメント**: {so.get('review_comment')}")

            # 右: 査読結果 (あれば)
            with c2:
                if gemini:
                    st.markdown("#### 🕵️ Gemini査読結果")
                    g_score = gemini.get("score", 0)
                    
                    # スコア色分け
                    color = "red"
                    if g_score >= 80: color = "#00cc00" # Green
                    elif g_score >= 50: color = "orange"
                    
                    st.markdown(f"<h2 style='color: {color}'>{g_score} 点</h2>", unsafe_allow_html=True)
                    st.markdown(f"**理由**: {gemini.get('reason')}")
                    st.markdown(f"**あるべき行動**: {gemini.get('correct_action')}")
                else:
                    if reviewed_only:
                        st.warning("査読データがありません")
                    else:
                        st.info("まだ査読されていません (1時間後に実行されます)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページ 4: 設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def page_settings():
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ 設定</h1>
        <p>APIキー・リスク管理・スクリーニングパラメータの設定</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "\U0001f511 API\u30ad\u30fc",
        "\U0001f4ca \u30b9\u30af\u30ea\u30fc\u30cb\u30f3\u30b0",
        "\U0001f3af \u30ea\u30b9\u30af\u7ba1\u7406",
    ])

    # ── APIキー設定 ──
    with tab1:
        st.markdown("### API接続状態")
        st.markdown("""
        <div class="info-box">
        <p>APIキーは <code>.env</code> ファイルで管理します。プロジェクトルートの <code>.env.example</code> をコピーして <code>.env</code> を作成し、各APIキーを設定してください。</p>
        </div>
        """, unsafe_allow_html=True)

        apis = [
            ("MEXC API", "MEXC_API_KEY", "取引所データ取得に必要"),
            ("OpenAI API", "OPENAI_API_KEY", "メインAI分析（GPT-5）"),
            ("Anthropic API", "ANTHROPIC_API_KEY", "セカンドオピニオン（Claude）"),
            ("Google API", "GOOGLE_API_KEY", "補助分析（Gemini）"),
            ("Discord Webhook", "DISCORD_WEBHOOK_URL", "通知送信"),
        ]

        for name, key, desc in apis:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                icon = "🟢" if is_configured(key) else "🔴"
                st.markdown(f"{icon} **{name}**")
            with c2:
                status = "設定済み ✅" if is_configured(key) else "未設定 ❌"
                st.markdown(status)
            with c3:
                st.caption(desc)

    # ── スクリーニング設定 ──
    with tab2:
        st.markdown("### スクリーニングパラメータ")
        params = st.session_state.screening_params

        c1, c2 = st.columns(2)
        with c1:
            params["min_change_rate"] = st.slider(
                "最小24h変動率 (%)", 0.5, 20.0,
                value=params["min_change_rate"], step=0.5,
            )
            params["min_volume_percentile"] = st.slider(
                "最小出来高パーセンタイル", 50, 99,
                value=params["min_volume_percentile"],
            )
            params["top_n_symbols"] = st.slider(
                "選出銘柄数", 3, 30,
                value=params["top_n_symbols"],
            )

        with c2:
            params["min_adx"] = st.slider(
                "最小ADX（トレンド強度）", 10, 50,
                value=params["min_adx"],
            )
            params["volume_spike_ratio"] = st.slider(
                "出来高急変倍率", 1.0, 5.0,
                value=params["volume_spike_ratio"], step=0.5,
            )
            params["ev_candidate_n"] = st.slider(
                "期待値スクリーニング候補数", 10, 50,
                value=params["ev_candidate_n"], step=5,
            )

        st.session_state.screening_params = params

    # ── リスク管理設定 ──
    with tab3:
        st.markdown("### リスク管理パラメータ")
        risk = st.session_state.risk_params

        c1, c2 = st.columns(2)
        with c1:
            risk["max_loss_per_trade_pct"] = st.slider(
                "1トレード最大損失 (%)", 0.5, 10.0,
                value=risk["max_loss_per_trade_pct"], step=0.5,
            )
            risk["max_leverage"] = st.slider(
                "最大レバレッジ", 1, 50,
                value=risk["max_leverage"],
            )

        with c2:
            risk["min_risk_reward_ratio"] = st.slider(
                "最小リスクリワード比", 1.0, 5.0,
                value=risk["min_risk_reward_ratio"], step=0.5,
            )
            risk["max_consecutive_losses"] = st.slider(
                "連続損失休止回数", 1, 10,
                value=risk["max_consecutive_losses"],
            )

        st.session_state.risk_params = risk

        st.markdown("""
        <div class="warning-box">
        <h4>⚠️ リスク管理の重要性</h4>
        <p>先物取引はレバレッジにより元本以上の損失が発生する可能性があります。適切なリスク管理を心がけてください。</p>
        </div>
        """, unsafe_allow_html=True)

    # 免責事項
    st.markdown("---")
    st.markdown("""
    <div class="danger-box">
    <h4>⚖️ 免責事項</h4>
    <p>本システムはテクニカル分析に基づく参考情報を提供するツールであり、投資助言には該当しません。
    AIの分析結果は必ずしも正確ではなく、先物取引は元本以上の損失が発生する可能性があります。
    全ての投資判断はユーザー自身の責任で行ってください。</p>
    </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページルーティング
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pages = {
    PAGE_HOME: page_home,
    PAGE_ANALYSIS: page_analysis_and_strategy,
    PAGE_LOGS: page_proposal_logs,
    PAGE_SETTINGS: page_settings,
}

selected_page = pages.get(page)
if selected_page is None:
    st.error(f"Invalid page selection: {page}")
    selected_page = page_home
selected_page()


