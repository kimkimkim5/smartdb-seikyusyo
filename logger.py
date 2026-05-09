import logging
import inspect

loglevel = 'info'

if loglevel == 'debug':
    LOG_LEVEL = logging.DEBUG
elif loglevel == 'info':
    LOG_LEVEL = logging.INFO
elif loglevel == 'warning':
    LOG_LEVEL = logging.WARNING
elif loglevel == 'error':
    LOG_LEVEL = logging.ERROR
elif loglevel == 'critical':
    LOG_LEVEL = logging.CRITICAL
else:
    LOG_LEVEL = logging.INFO

# ロガーを動的に取得する関数を定義
def get_dynamic_logger():
    # 呼び出し元のモジュール名を取得
    frame = inspect.stack()[2]
    module_name = inspect.getmodule(frame[0]).__name__
    logger = logging.getLogger(module_name)
    logger.setLevel(LOG_LEVEL)
    
    # ハンドラとフォーマッターを設定
    if not logger.handlers:  # 重複追加を防ぐ
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVEL)

        file_handler = logging.FileHandler('app.log', encoding='utf-8')
        file_handler.setLevel(LOG_LEVEL)

        formatter = logging.Formatter('%(asctime)s - %(filename)s - %(lineno)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    return logger

# 動的ロガーを使用する関数
def debug(text):
    logger = get_dynamic_logger()
    logger.debug(text, stacklevel=2)

def info(text):
    logger = get_dynamic_logger()
    logger.info(text, stacklevel=2)

def warning(text):
    logger = get_dynamic_logger()
    logger.warning(text, stacklevel=2)

def error(text):
    logger = get_dynamic_logger()
    logger.error(text, stacklevel=2, exc_info=True)

def critical(text):
    logger = get_dynamic_logger()
    logger.critical(text, stacklevel=2)
