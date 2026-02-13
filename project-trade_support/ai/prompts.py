"""
プロンプトテンプレート集 - チャート分析・取引戦略・シナリオ監視
"""

SYSTEM_PROMPT = """あなたは仮想通貨先物のデイトレード専門のテクニカルアナリストです。
以下の原則に従って分析を行ってください：
- 客観的なテクニカル分析に基づいて判断すること
- 必ずしも取引提案を出す必要はない（見送りも立派な判断）
- リスク管理を最優先に考えること
- 出力は必ず指定されたJSON形式で返すこと
- 投資助言ではなく、テクニカル分析に基づく参考情報であること"""


CHART_ANALYSIS_PROMPT = """以下の仮想通貨先物のテクニカル指標データを分析し、総合的な相場判断を行ってください。

## 銘柄情報
- シンボル: {symbol}
- 現在価格: {current_price}
- 24h変動率: {change_24h}%

## テクニカル指標データ
{technical_data}

## マルチタイムフレーム分析結果
{multi_timeframe_data}

## 出力形式（JSON）
```json
{{
    "judgment": "bullish | bearish | neutral",
    "confidence": "high | medium | low",
    "summary": "分析サマリー（日本語、200文字以内）",
    "key_levels": {{
        "support": [サポートライン価格リスト],
        "resistance": [レジスタンスライン価格リスト]
    }},
    "signals": [
        {{"indicator": "指標名", "signal": "シグナル内容", "weight": "strong | moderate | weak"}}
    ],
    "risk_factors": ["リスク要因リスト"]
}}
```"""


STRATEGY_PROPOSAL_PROMPT = """以下のチャート分析結果を基に、具体的な取引戦略を提案してください。

## 銘柄情報
- シンボル: {symbol}
- 現在価格: {current_price}

## チャート分析結果
{analysis_result}

## リスク管理パラメータ
- 1トレード最大損失: 資金の{max_loss_pct}%
- 最小リスクリワード比: 1:{min_rr_ratio}

## ローソク足データ（直近20本）
{candle_data}

## 出力形式（JSON）
```json
{{
    "direction": "long | short | skip",
    "entry_price": {{
        "ideal": エントリー理想価格,
        "range_low": エントリー下限,
        "range_high": エントリー上限
    }},
    "take_profit": {{
        "tp1": 第1利確ライン,
        "tp2": 第2利確ライン
    }},
    "stop_loss": {{
        "price": 損切り価格,
        "reason": "損切り根拠"
    }},
    "risk_reward_ratio": リスクリワード比の数値,
    "confidence": "high | medium | low",
    "scenario_invalidation": "シナリオ崩壊条件の説明",
    "reasoning": "提案の根拠（日本語、300文字以内）"
}}
```

※ 取引を見送る場合は direction を "skip" とし、理由を reasoning に記載してください。"""


SCENARIO_CHECK_PROMPT = """以下のポジション情報と最新の市場データを確認し、シナリオが崩壊していないか判断してください。

## ポジション情報
- シンボル: {symbol}
- 方向: {direction}
- エントリー価格: {entry_price}
- 現在価格: {current_price}
- 利確ライン: TP1={tp1}, TP2={tp2}
- 損切りライン: {stop_loss}
- シナリオ崩壊条件: {invalidation_condition}

## 最新テクニカル指標
{technical_data}

## 出力形式（JSON）
```json
{{
    "scenario_status": "valid | warning | invalidated",
    "current_pnl_pct": 現在の損益率(%),
    "assessment": "現状の評価コメント（日本語、200文字以内）",
    "recommended_action": "hold | partial_close | close | tighten_sl",
    "updated_levels": {{
        "new_stop_loss": 新しい損切りライン（変更不要の場合はnull）,
        "new_tp": 新しい利確ライン（変更不要の場合はnull）
    }},
    "alert_level": "info | warning | critical"
}}
```"""


SECOND_OPINION_PROMPT = """以下は別のAIアナリストによるチャート分析と取引提案です。
独立した視点からこの分析を検証し、同意するか・修正を提案するかを判断してください。

## 元の分析（別のAIによる）
{original_analysis}

## 元の指標データ
{technical_data}

## 出力形式（JSON）
```json
{{
    "agreement": "agree | partially_agree | disagree",
    "review_comment": "レビューコメント（日本語、200文字以内）",
    "risk_assessment": "元の分析で見落とされているリスクがあれば指摘",
    "modified_proposal": {{}} // 修正提案がある場合のみ。なければ空オブジェクト
}}
```"""

GEMINI_REVIEW_PROMPT = """あなたはAIによる過去の取引提案を評価する監査役です。
提案時の情報と、その後の実際の値動き（結果）を比較し、提案の妥当性を0〜100点で採点してください。

## 提案の詳細
- 提案日時: {timestamp}
- 銘柄: {symbol}
- 推奨方向: {direction}
- エントリー推奨価格: {entry_price}
- TP（利確）: {tp}
- SL（損切り）: {stop_loss}
- 提案の根拠: {reasoning}

## その後の市場の動き（結果）
- 期間中の最高値: {highest_price}
- 期間中の最安値: {lowest_price}
- 期間中の最終価格: {close_price}
- TP到達: {hit_tp}
- SL到達: {hit_sl}
- 最大利益率: {max_profit_pct}%
- 最大損失率: {max_loss_pct}%

## 採点基準
- 100点: 完璧な予測（TP到達、かつ逆行ほとんどなし）
- 80点: 概ね正解（TP到達だが多少の含み損あり、または十分な利益）
- 50点: どちらとも言えない（エントリーしなかった、または横ばい）
- 20点: 期待外れ（すぐに損切りラインにかかった）
- 0点: 完全な逆行（ロング推奨で暴落など）

## 出力形式（JSON）
```json
{{
    "score": 0〜100の整数,
    "reason": "採点の理由（日本語、150文字以内）",
    "correct_action": "本来どうすべきだったか（例: 見送り、逆張り、など）"
}}
```"""
