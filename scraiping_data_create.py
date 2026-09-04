from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logger as logger
import util as util
import subprocess
import tempfile
import os
from scraiping_smartdb import scraiping_smartdb
from selenium import webdriver
from selenium.webdriver.chrome.service import Service


def execute_sub(driver, url): 
    """
    ECサイトからスクレイピングをして情報(金額)を取得する処理

    引数:
        ドライバーインスタンス、クラファンサイト名、URL

    返り値:
        なし

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """
    try:
            
        # ==================== スクレイピング処理 ====================
        # 既存Chromeプロファイル（拡張機能/復元/会社ポリシー）を使っている
        # 会社PCだと特に、起動直後に別UI（サイドパネル/関連ウィンドウ/復元タブ）を出してきます。
        # 最も効くのは 一時プロファイルで起動です。
        options = Options()
        tmp_profile = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={tmp_profile}")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--start-maximized")

        # ★ ChromeのDL先はローカル一時ディレクトリ（Box同期フォルダを避ける）
        download_dir = util.get_download_dir()
        logger.info(f"DLフォルダ: {download_dir}")

        # ★ Chrome prefs：DL先固定＋PDFはビューアで開かずファイル保存
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # PDFをビューアで開かずDLさせる
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(executable_path=util.CHROMEDRIVER_PATH)   
        driver = webdriver.Chrome(service=service, options=options)

        # ★ 診断：Chrome / chromedriver バージョンとDL設定確認
        try:
            logger.info(f"Chrome version: {driver.capabilities.get('browserVersion')}")
            logger.info(
                f"chromedriver version: "
                f"{driver.capabilities.get('chrome', {}).get('chromedriverVersion')}"
            )
        except Exception:
            pass

        # ★ CDPでもDL先を強制（prefsが効かない環境の保険）
        try:
            driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_dir,
                "eventsEnabled": True,
            })
        except Exception:
            try:
                driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                    "behavior": "allow",
                    "downloadPath": download_dir,
                })
            except Exception as e:
                logger.warning(f"CDPダウンロード設定に失敗: {e}")

        driver.get(url)
        scraiping_smartdb(driver, url)

    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")



def execute(url): 
    """
    ECサイトからスクレイピングをして情報(インボイス番号・金額・商品名など)を取得する処理

    引数:
        URL

    返り値:
        なし

    エラー:
        Exception

    著作権:
        Ryusuke Kimura (ogi.kimura@gmail.com)

    """

    command = util.DEBUG_MODE_COMMAND
    subprocess.Popen(command, shell=True)

    chrome_options = Options()
    chrome_options.debugger_address = util.DEBUG_MODE_URL

    try:
        service = Service(executable_path=util.CHROMEDRIVER_PATH)   
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        execute_sub(driver, url)
            
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
    
    ## エラーが発生してもCLOSEする
    finally:
        driver.close()
        driver.quit()


############# メイン処理 #############
if __name__ == "__main__":
    url = util.BASE_URL
    execute(url)
