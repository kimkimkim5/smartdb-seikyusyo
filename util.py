from attrs import NOTHING
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time
import sys
import re
import os
import tempfile
import logger as logger
import configparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional



config = configparser.ConfigParser(interpolation=None)
config.read("config.ini", encoding="utf-8")
section = sys.argv[1] if len(sys.argv) >= 2 else "default"
config = config[section]

# スリープ
SLEEP_TIME = int(config.get('sleep_time'))
SLEEP_TIME_FOR_COMFIRM = int(config.get('sleep_time_for_comfirm'))

# ポップアップ
POPUP_ACCEPT = 1
POPUP_DISMISS = 2

# 返り値
FLAG_SUCCESS = 0
FLAG_ERROR = -1


# Webサーバ
API_URL              = config.get("api_url")

# OpenAI モデル
OPENAI_MODEL         = config.get("openai_model")

# デバッグモード立ち上げコマンド
DEBUG_MODE_COMMAND = config.get("debug_mode_command")
DEBUG_MODE_URL     = config.get("debug_mode_url")

# Chrome Driverパス
CHROMEDRIVER_PATH = config.get("chromedriver_path")

# SmartDB URL
BASE_URL = config.get("base_url")


# ダイアログボタン
RUN_BUTTON = ''
PROCEED_BUTTON =  ''

# exeモード
EXE_MODE = config.get('exe_mode')


# 旧定義（config.ini の download_dir）は使わない。ローカル一時ディレクトリ固定で上書き。
# DOWNLOAD_DIR = config.get('download_dir')


# イテレーション回数
ITER_COUNT = int(config.get('iter_count'))


def get_download_dir():
    """
    ChromeのDL先として使うローカル一時ディレクトリを返す。
    Box同期フォルダなどネットワーク同期フォルダはファイル出現遅延・ファイルロックの
    原因になるため、必ずローカル一時ディレクトリを使う（会社環境対応）。
    """
    base_dir = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    base = os.path.join(base_dir, "smartdb_downloads")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


# ★ DOWNLOAD_DIR は get_download_dir() 経由でローカル一時ディレクトリ固定（Box同期パス排除）
DOWNLOAD_DIR = get_download_dir()


def link_click(driver, link_text, index):
    """
    XPATHを基に該当するリンクをクリックする処理

    引数:
        Chromeドライバ、XPATH、インデックス
        複数エレメントを拾い出したときに、外から明示的に設定できるようにindexを追加

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'link_text START {link_text}')
        # エレメント取得
        # WebDriverWait(driver, SLEEP_TIME).until(EC.element_to_be_clickable(By.LINK_TEXT, link_text))
        element = driver.find_elements(By.LINK_TEXT, link_text)
        # クリック
        element[index].click()
        logger.debug(f'link_text END {link_text}')
        time.sleep(SLEEP_TIME)
        return FLAG_SUCCESS

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR


def xpath_click(driver, xpath_text, index):
    """
    XPATHを基に該当するボタンをクリックする処理

    引数:
        Chromeドライバ、XPATH、インデックス
        複数エレメントを拾い出したときに、外から明示的に設定できるようにindexを追加

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'xpath_click START {xpath_text}')
        # エレメント取得
        # WebDriverWait(driver, SLEEP_TIME).until(EC.element_to_be_clickable(By.XPATH, xpath_text))
        element = driver.find_elements(By.XPATH, xpath_text)
        # クリック
        element[index].click()
        logger.debug(f'xpath_click END {xpath_text}')
        time.sleep(SLEEP_TIME)
        return FLAG_SUCCESS
    
    except Exception as e:
        logger.error(f"予期しないエラー: index {index}  {str(e)}")
        return FLAG_ERROR



def xpath_select(driver, xpath_text, var, index:int = 0):
    """
    XPATHを基にリスト選択する処理

    引数:
        Chromeドライバ、XPATH、入力文字、インデックス

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'xpath_select START {xpath_text}')
        # エレメント取得
        # WebDriverWait(driver, SLEEP_TIME).until(EC.presence_of_element_located(By.XPATH, xpath_text))
        elements = driver.find_elements(By.XPATH, xpath_text)
        # セレクト
        dropdown = Select(elements[index])
        dropdown.select_by_visible_text(var)  
        logger.debug(f'xpath_select END {xpath_text}')
        time.sleep(SLEEP_TIME)
        return FLAG_SUCCESS

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR



def get_elements_xpath(driver, xpath_text):
    """
    XPATHを基に該当するエレメントを取得

    引数:
        Chromeドライバ、XPATH

    返り値:
        エレメント群

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'get_element_xpath START {xpath_text}')
        # エレメント取得
        # WebDriverWait(driver, SLEEP_TIME).until(EC.presence_of_element_located(By.XPATH, xpath_text))
        elements = driver.find_elements(By.XPATH, xpath_text)
        logger.debug(f'get_element_xpath END {xpath_text}')
        return elements

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")



def popup_click(driver, f):
    """
    ポップアップ画面のボタンをクリックする処理
    
    引数:
        Chromeドライバ
        フラグ： POPUP_ACCEPTの場合は「OK」、それ以外は「キャンセル」をクリック

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'popup_click START {f}')
        alert = driver.switch_to.alert
        if f == POPUP_ACCEPT:
            alert.accept()
        else:
            alert.dismiss()
        logger.debug(f'popup_click END {f}')
        time.sleep(SLEEP_TIME)
        return FLAG_SUCCESS

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR



def switch_window(driver, all_windows, original_window):
    """
    Windowをスイッチングする処理
    現在のWindow以外のものを探し、存在すれば新たなWindowとして返す

    引数:
        全てのWindowインスタンス、現在のWindowインスタンス

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'switch_window START')
        for window in all_windows:
            if window != original_window:
                driver.switch_to.window(window)
                break
        time.sleep(SLEEP_TIME)
        logger.debug(f'switch_window END')
        return FLAG_SUCCESS

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR



def set_textbox(driver, xpath_text, value, index):
    """
    テキストボックスにデータを設定する処理
        複数エレメントを拾い出したときに、外から明示的に設定できるようにindexを追加

    引数:
        Chromeドライバ、XPATH、入力文字、インデックス

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        logger.debug(f'set_textbox START {value}')
        # エレメント取得
        # WebDriverWait(driver, SLEEP_TIME).until(EC.presence_of_element_located(By.XPATH, xpath_text))
        textbox = driver.find_elements(By.XPATH, xpath_text)
        textbox[index].clear()
        textbox[index].send_keys(value)
        logger.debug(f'set_textbox END {value}')
        time.sleep(SLEEP_TIME)
        return FLAG_SUCCESS

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR



def set_cookie_data(driver, session):
    """
    Cookieにセッション情報を設定する
    Amazonの場合、インボイス帳票をpdf保存しようとしてもそのままではエラーになる。
    Cookieにセッション情報を入れて送信することで、正常に処理を実行することができる。

    引数:
        Chromeドライバ、セッション

    返り値:
        成功: 0
        失敗: 1

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        # Cookieを取得し、requestsに渡す
        cookies = driver.get_cookies()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        return FLAG_SUCCESS
           
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return FLAG_ERROR
            
            
            
def is_date_multi_format(string):
    """
    文字列が日付フォーマットであるか否かをチェック

    引数:
        文字列

    返り値:
        True: 日付フォーマットである
        False: 日付フォーマットではない

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
        formats = ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y年%m月%d日"]
        for date_format in formats:
            try:
                datetime.strptime(string, date_format)
                return True
            except ValueError:
                continue

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        return False
    



def get_jst_time():
    """
    日本時間を返却する処理

    引数:
        なし

    返り値:
        日時情報(日本時間)

    エラー:
        なし

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    JST = timezone(timedelta(hours=9))
    japan_now = datetime.now(JST)
    return japan_now.strftime('%Y-%m-%d %H:%M:%S')



def list_pdf_files(download_dir: str):
    """
    ダウンロードフォルダ内のPDFファイル名リストを取得する

    引数:
        ダウンロードフォルダパス

    返り値:
        PDFファイル名セット

    エラー:
        なし

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    d = Path(download_dir)
    return {p.name for p in d.glob("*.pdf")}



def wait_new_pdf(download_dir: str, before_set: set, timeout: int = 60):
    """
    ダウンロードフォルダに新しく増えたPDFを待つ
    Chromeのダウンロード中ファイル(.crdownload)が消えるまで待つ

    引数:
        ダウンロードフォルダパス、事前のPDFファイル名セット、タイムアウト秒数

    返り値:
        新規PDFファイルパス

    エラー:
        なし

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    d = Path(download_dir)
    end = time.time() + timeout
    last_size = {}

    while time.time() < end:
        try:
            after = {p.name for p in d.glob("*.pdf")}
        except OSError:
            time.sleep(0.5)
            continue

        new = sorted(after - before_set)

        if new:
            partials = list(d.glob("*.crdownload")) + list(d.glob("*.tmp"))
            if not partials:
                for name in new:
                    p = d / name
                    try:
                        size = p.stat().st_size
                    except OSError:
                        continue
                    if size > 0 and last_size.get(name) == size:
                        return str(p)
                    last_size[name] = size

        time.sleep(0.5)

    try:
        listing = [p.name for p in d.iterdir()]
    except Exception as e:
        listing = f"(一覧取得失敗: {e})"

    raise TimeoutError(
        f"新規PDFのダウンロード完了を検知できませんでした "
        f"(監視先={download_dir} の一覧={listing})"
    )



def delete_file(path: str):
    """
    指定ファイルを削除する処理

    引数:
        ファイルパス

    返り値:
        なし

    エラー:
        なし

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    p = Path(path)
    if p.exists():
        p.unlink()


def normalize_money(s: Optional[str]) -> Optional[int]:
    """
    '1,292円' '¥14,208' '14208' などを int に正規化

    引数:
        文字列（金額）

    返り値:
        金額（整数）

    エラー:
        なし

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    if not s:
        return None
    s = s.strip()
    # 数字以外をざっくり落とす（カンマ、円記号、空白など）
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None
