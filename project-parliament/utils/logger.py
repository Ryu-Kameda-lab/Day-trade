"""
Project Parliament - ロガーユーティリティ
ファイル出力（logs/parliament.log）とコンソール出力を提供
"""
import os
import logging
from logging.handlers import RotatingFileHandler

# ログディレクトリの絶対パス
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "parliament.log")
_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# ログディレクトリを作成
os.makedirs(_LOG_DIR, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """
    名前付きロガーを取得する。
    ファイル出力（RotatingFileHandler）とコンソール出力の両方を設定。

    Args:
        name: ロガー名（例: "MEXCService", "TradeExecutor"）

    Returns:
        logging.Logger: 設定済みロガー
    """
    logger = logging.getLogger(name)

    # 既にハンドラが設定されている場合はそのまま返す
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_FORMAT)

    # ファイルハンドラ（最大5MB、バックアップ3世代）
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
