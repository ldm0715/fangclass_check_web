import sys
import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    _BUNDLE_DIR = Path(sys._MEIPASS)  # PyInstaller 资源目录（_internal/）
    _APP_DIR = Path(sys.executable).parent  # exe 所在目录
else:
    _BUNDLE_DIR = Path(__file__).parent.absolute()
    _APP_DIR = _BUNDLE_DIR

# 模板：打包后在 _internal/ 中，开发时在项目根目录
TEMPLATES_DIR = _BUNDLE_DIR / "templates"

# 静态文件 + 运行时数据：始终在 exe（或项目根）旁边
STATIC_DIR = _APP_DIR / "static"
BUNDLE_STATIC_DIR = _BUNDLE_DIR / "static"  # 打包后在 _internal/static，存放只读资源（icon 等）
INFO_DIR = STATIC_DIR / "info"
QRCODE_DIR = STATIC_DIR / "qrcode"
REPORT_DIR = STATIC_DIR / "report_cards"
LOG_DIR = _APP_DIR / "log"
CONFIG_PATH = _APP_DIR / "config.json"

# 确保运行时目录存在（仅 info 和 log 需要在 exe 旁创建）
for _d in [INFO_DIR, LOG_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """配置日志系统：同时输出到控制台和按天分割的日志文件"""
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler — 按天切割，保留 30 天
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # 配置根 logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # 将 print 也重定向到日志文件（同时保留控制台输出）
    sys.stdout = _TeeWriter(sys.stdout, file_handler.stream)
    sys.stderr = _TeeWriter(sys.stderr, file_handler.stream)


class _TeeWriter:
    """同时写入两个流"""

    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file

    def write(self, msg):
        self.original.write(msg)
        try:
            self.log_file.write(msg)
            self.log_file.flush()
        except Exception:
            pass

    def flush(self):
        self.original.flush()
        try:
            self.log_file.flush()
        except Exception:
            pass

    def isatty(self):
        return hasattr(self.original, "isatty") and self.original.isatty()

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8000,
}


def load_config():
    """加载配置，不存在则自动创建默认配置"""
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"已生成默认配置文件: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return {**DEFAULT_CONFIG, **json.load(f)}
