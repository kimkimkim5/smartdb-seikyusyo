from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logger as logger
import util as util
import subprocess
import tempfile
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

        service = Service(executable_path=util.CHROMEDRIVER_PATH)   
        driver = webdriver.Chrome(service=service, options=options)
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