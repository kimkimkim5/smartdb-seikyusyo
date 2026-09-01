from time import sleep
import os
import time

import logger as logger
import util as util
import generate_api

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    NoSuchFrameException,
    NoSuchWindowException,
    ElementClickInterceptedException,
    WebDriverException,
)


# =========================
# 共通ヘルパー
# =========================

DEFAULT_TIMEOUT = 20
SHORT_TIMEOUT = 5
FRAME_MAX_DEPTH = 5


def safe_click(driver, element, timeout=10):
    """
    要素が表示され、クリック可能になるまで待機してからクリックする関数
    """
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'center'});", element
        )
    except Exception:
        pass

    try:
        WebDriverWait(driver, timeout).until(
            lambda d: element.is_displayed() and element.is_enabled()
        )
    except Exception:
        pass

    try:
        ActionChains(driver).move_to_element(element).pause(0.1).click().perform()
        return
    except Exception:
        pass

    try:
        element.click()
        return
    except Exception:
        pass

    driver.execute_script("arguments[0].click();", element)


def wait_document_ready(driver, timeout=DEFAULT_TIMEOUT):
    """
    現在のドキュメントの読み込み完了を待つ
    """
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def set_text(driver, xpath, value, timeout=DEFAULT_TIMEOUT):
    """
    XPATHで指定したテキストボックスに入力
    """
    logger.debug(f"set_text START xpath={xpath}")
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.clear()
    element.send_keys(value)
    logger.debug(f"set_text END xpath={xpath}")


def click_xpath(driver, xpath, timeout=DEFAULT_TIMEOUT):
    """
    XPATHで指定した要素を待機してクリック
    """
    logger.debug(f"click_xpath START xpath={xpath}")
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    safe_click(driver, element, timeout=timeout)
    logger.debug(f"click_xpath END xpath={xpath}")


def wait_new_window_and_switch(driver, before_windows, timeout=DEFAULT_TIMEOUT):
    """
    新しいウィンドウが開くまで待って切り替える
    """
    WebDriverWait(driver, timeout).until(
        lambda d: len(d.window_handles) > len(before_windows)
    )
    after_windows = set(driver.window_handles)
    new_windows = list(after_windows - before_windows)

    if not new_windows:
        raise TimeoutException("新しいウィンドウが検出できませんでした。")

    new_window = new_windows[0]
    driver.switch_to.window(new_window)
    wait_document_ready(driver, timeout=timeout)
    return new_window


def switch_to_frame(driver, frame_name, timeout=DEFAULT_TIMEOUT):
    """
    default_content に戻ってから frame に切り替える
    """
    driver.switch_to.default_content()
    WebDriverWait(driver, timeout).until(
        EC.frame_to_be_available_and_switch_to_it((By.NAME, frame_name))
    )
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
    )


def find_element_in_frame(driver, frame_name, xpath, timeout=DEFAULT_TIMEOUT, clickable=False):
    """
    指定frameに切り替えて要素を取得
    """
    switch_to_frame(driver, frame_name, timeout=timeout)

    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def get_text_in_frame(driver, frame_name, xpath, timeout=DEFAULT_TIMEOUT):
    """
    指定frame内の要素テキストを取得
    """
    element = find_element_in_frame(driver, frame_name, xpath, timeout=timeout, clickable=False)
    return extract_element_text(element)


def try_accept_alert(driver, timeout=3):
    """
    アラートが出ていればOKを押す
    """
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert_text = alert.text
        alert.accept()
        logger.info(f"アラートを承認しました。text={alert_text}")
        return True
    except TimeoutException:
        return False


def accept_alerts_until_gone(driver, timeout_each=2, max_count=3):
    """
    複数回 alert が出る場合に備えて、出なくなるまで承認
    """
    accepted = []
    for _ in range(max_count):
        try:
            WebDriverWait(driver, timeout_each).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            text = alert.text
            alert.accept()
            accepted.append(text)
            logger.info(f"アラートを承認しました。text={text}")
            sleep(0.5)
        except TimeoutException:
            break
    return accepted


def extract_element_text(element):
    """
    .text が空でも textContent / innerText / value を拾う
    """
    try:
        text = element.text
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    for attr in ["textContent", "innerText", "value"]:
        try:
            text = element.get_attribute(attr)
            if text and str(text).strip():
                return str(text).strip()
        except Exception:
            pass

    return ""


def safe_window_handles(driver):
    try:
        return driver.window_handles
    except Exception:
        return []


def is_window_alive(driver, handle):
    try:
        return handle in driver.window_handles
    except Exception:
        return False


def switch_to_alive_window(driver, preferred_handle=None, fallback_handle=None):
    """
    まだ存在する window に切り替える
    """
    handles = safe_window_handles(driver)

    if preferred_handle and preferred_handle in handles:
        driver.switch_to.window(preferred_handle)
        return preferred_handle

    if fallback_handle and fallback_handle in handles:
        driver.switch_to.window(fallback_handle)
        return fallback_handle

    if handles:
        driver.switch_to.window(handles[-1])
        return handles[-1]

    raise NoSuchWindowException("利用可能な window がありません。")


def get_top_level_frames(driver):
    """
    現在のwindow直下の frame / iframe 情報を取得
    """
    driver.switch_to.default_content()
    frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
    results = []
    for i, frame in enumerate(frames):
        try:
            results.append({
                "index": i,
                "name": frame.get_attribute("name") or "",
                "id": frame.get_attribute("id") or "",
                "src": frame.get_attribute("src") or "",
            })
        except Exception:
            results.append({
                "index": i,
                "name": "",
                "id": "",
                "src": "",
            })
    return results


def frame_path_to_text(frame_path):
    if not frame_path:
        return "default_content"

    parts = []
    for p in frame_path:
        parts.append(
            f"[{p.get('index')}] name={p.get('name')} id={p.get('id')} src={p.get('src')}"
        )
    return " -> ".join(parts)


def switch_to_frame_path(driver, frame_path):
    driver.switch_to.default_content()

    for step in frame_path:
        frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
        idx = step["index"]
        if idx >= len(frames):
            raise NoSuchFrameException(
                f"frame index out of range. index={idx}, frames={len(frames)}"
            )
        driver.switch_to.frame(frames[idx])


def enumerate_frame_paths(driver, max_depth=FRAME_MAX_DEPTH):
    """
    再帰的に frame / iframe を列挙
    """
    paths = []

    def walk(current_path, depth):
        if depth > max_depth:
            return

        frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
        for idx, frame in enumerate(frames):
            try:
                info = {
                    "index": idx,
                    "name": frame.get_attribute("name") or "",
                    "id": frame.get_attribute("id") or "",
                    "src": frame.get_attribute("src") or "",
                }
            except Exception:
                info = {
                    "index": idx,
                    "name": "",
                    "id": "",
                    "src": "",
                }

            next_path = current_path + [info]
            paths.append(next_path)

            try:
                driver.switch_to.frame(frame)
                walk(next_path, depth + 1)
                driver.switch_to.parent_frame()
            except Exception:
                driver.switch_to.default_content()
                switch_to_frame_path(driver, current_path)

    driver.switch_to.default_content()
    walk([], 1)
    driver.switch_to.default_content()
    return paths


def restore_context(driver, context):
    frame_path = context.get("frame_path", []) if context else []
    switch_to_frame_path(driver, frame_path)


def find_context_anywhere(driver, xpaths, timeout=DEFAULT_TIMEOUT, label="element"):
    """
    default_content および全frameを探索して、最初に見つかったコンテキストを返す
    """
    end_time = time.time() + timeout
    last_frames = []

    while time.time() < end_time:
        frame_paths = [[]] + enumerate_frame_paths(driver, max_depth=FRAME_MAX_DEPTH)
        last_frames = [frame_path_to_text(p) for p in frame_paths if p]

        for frame_path in frame_paths:
            try:
                switch_to_frame_path(driver, frame_path)
            except Exception:
                continue

            for xpath in xpaths:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements:
                        return {
                            "frame_path": frame_path,
                            "xpath": xpath,
                            "count": len(elements),
                        }
                except Exception:
                    continue

        sleep(0.3)

    logger.error(f"{label} が見つかりませんでした xpath={xpaths} frames={last_frames}")
    raise TimeoutException(f"{label} が見つかりませんでした xpath={xpaths}")


def find_element_by_context(driver, context, index=0, label="element"):
    restore_context(driver, context)
    xpath = context["xpath"]
    elements = driver.find_elements(By.XPATH, xpath)

    if not elements:
        raise NoSuchElementException(f"{label} が見つかりません xpath={xpath}")

    if index >= len(elements):
        raise IndexError(
            f"{label} index={index} ですが、要素数は {len(elements)} 件です xpath={xpath}"
        )

    return elements[index]


def find_element_anywhere(driver, xpaths, timeout=DEFAULT_TIMEOUT, label="element", index=0):
    context = find_context_anywhere(
        driver,
        xpaths=xpaths,
        timeout=timeout,
        label=label,
    )
    element = find_element_by_context(driver, context, index=index, label=label)
    return element, context


def get_text_anywhere(driver, xpaths, timeout=DEFAULT_TIMEOUT, label="element"):
    element, context = find_element_anywhere(
        driver,
        xpaths=xpaths,
        timeout=timeout,
        label=label,
    )
    restore_context(driver, context)
    element = find_element_by_context(driver, context, label=label)
    return extract_element_text(element)


def wait_post_approve_completed(driver, approve_context, approve_xpaths, timeout=15):
    """
    alert OK の後、承認処理の反映を待つ。
    成功の目安:
      - 承認ボタンが消える
      - もとの承認ボタン要素が stale になる
      - 画面が閉じる
    """
    end_time = time.time() + timeout

    while time.time() < end_time:
        try:
            handles = safe_window_handles(driver)
            if not handles:
                logger.info("承認後、window が存在しなくなりました。")
                return True

            # 画面がまだある場合、対象コンテキストで承認ボタン有無を見る
            try:
                restore_context(driver, approve_context)
                for xp in approve_xpaths:
                    elements = driver.find_elements(By.XPATH, xp)
                    visible_elements = []
                    for el in elements:
                        try:
                            if el.is_displayed():
                                visible_elements.append(el)
                        except Exception:
                            pass

                    if visible_elements:
                        # まだ承認ボタンが見えている = 未反映の可能性
                        sleep(0.5)
                        break
                else:
                    logger.info("承認ボタンが見つからなくなりました。承認反映とみなします。")
                    return True

            except (NoSuchWindowException, NoSuchFrameException, StaleElementReferenceException):
                logger.info("承認後、画面構造が変化しました。承認反映とみなします。")
                return True

        except Exception:
            pass

        sleep(0.5)

    return False


def wait_list_item_disappear(driver, target_text, timeout=15):
    """
    元一覧に戻った後、対象行が消えた/変化したことを待つ
    """
    end_time = time.time() + timeout

    while time.time() < end_time:
        try:
            driver.switch_to.default_content()
            elements = driver.find_elements(By.XPATH, "//div[@role='button' and @tabindex='0' and @aria-disabled='false']")
            texts = []
            for el in elements:
                try:
                    texts.append(el.text.strip())
                except Exception:
                    pass

            if target_text not in texts:
                logger.info("一覧から対象行が見えなくなりました。状態変化が反映された可能性があります。")
                return True
        except Exception:
            pass

        sleep(0.5)

    return False


def dump_diagnostic(driver, label, work_item_xpath=None):
    """
    失敗時の診断情報をログ出力し、スクリーンショットとHTMLソースを保存する

    引数:
        driver, 診断ラベル, 対象XPath(任意)

    返り値:
        なし
    """
    try:
        url = driver.current_url
    except Exception as e:
        url = f"(取得失敗: {e})"

    try:
        title = driver.title
    except Exception as e:
        title = f"(取得失敗: {e})"

    logger.error(f"[診断:{label}] current_url={url}")
    logger.error(f"[診断:{label}] title={title}")

    if work_item_xpath:
        try:
            count = len(driver.find_elements(By.XPATH, work_item_xpath))
        except Exception as e:
            count = f"(取得失敗: {e})"
        logger.error(f"[診断:{label}] work_item_xpath マッチ件数={count}")

    # ページ内テキスト抜粋
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        excerpt = body_text[:500].replace("\n", " | ")
        logger.error(f"[診断:{label}] ページテキスト抜粋: {excerpt}")
    except Exception as e:
        logger.error(f"[診断:{label}] ページテキスト取得失敗: {e}")

    # ログイン画面に留まっているかの判別
    try:
        login_inputs = driver.find_elements(By.XPATH, "//input[@id='username']")
        if login_inputs:
            logger.error(f"[診断:{label}] ログイン画面に留まっています（ログイン処理が失敗している可能性）")
        else:
            logger.error(f"[診断:{label}] ログイン画面ではありません（ログインは通過済み）")
    except Exception:
        pass

    # スクリーンショット保存
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        shot_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), f"debug_{label}_{ts}.png"
        )
        driver.save_screenshot(shot_path)
        logger.error(f"[診断:{label}] スクリーンショット保存: {shot_path}")
    except Exception as e:
        logger.error(f"[診断:{label}] スクリーンショット保存失敗: {e}")

    # HTMLソース保存
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        html_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), f"debug_{label}_{ts}.html"
        )
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"[診断:{label}] HTMLソース保存: {html_path}")
    except Exception as e:
        logger.error(f"[診断:{label}] HTMLソース保存失敗: {e}")


# =========================
# SmartDBスクレイピング本体
# =========================

def scraiping_smartdb(driver, base_url):
    """
    SmartDBのスクレイピングをして情報(金額)を取得する処理
    """

    # ★ プロジェクト直下の専用DLフォルダ（scraiping_data_create.py 側と同じパス）
    download_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "downloads"
    )
    if not os.path.isdir(download_dir):
        os.makedirs(download_dir, exist_ok=True)

    # ---------------------
    # XPath定義
    # ---------------------
    login_user_xpath = "//input[@id='username']"
    login_next_xpath = "//span[contains(@class,'MuiButton-label') and .//div[normalize-space()='次へ']]"
    login_password_xpath = "//input[@data-testid='password-input']"
    login_submit_xpath = "//span[normalize-space()='パスワードでログイン']"

    # work_item_xpath = "//div[@role='button'][.//*[contains(@aria-label,'責任者承認①')]]"
    work_item_xpath = (
        "//div[@role='button' and contains(concat(' ', normalize-space(@class), ' '), ' MuiListItemButton-root ')]"
        "[.//*[contains(normalize-space(.), '責任者承認①')]]"
    )
    next_page_xpath = "//button[.//p[normalize-space()='次へ']]"

    pdf_link_xpath_candidates = [
        "//a[contains(@class,'TextLink') and contains(normalize-space(.), '.pdf')]",
        "//a[contains(concat(' ', normalize-space(@class), ' '), ' TextLink ') and contains(normalize-space(.), '.pdf')]",
    ]

    amount_all_xpath = "//*[@id='itemId_i10252_10907']"
    amount_decluding_xpath = "//*[@id='itemId_i10252_10061']"
    amount_tax_xpath = "//*[@id='itemId_i10252_10062']"

    approve_xpath_candidates = [
        "//a[contains(@class,'neo-vm-button') and .//span[normalize-space()='責任者承認']]",
        "//a[contains(@href,'clickHandleButton') and contains(@href,'責任者承認')]",
        "//span[normalize-space()='責任者承認']/ancestor::a[1]",
        "//button[normalize-space()='責任者承認']",
        "//*[@role='button' and normalize-space()='責任者承認']",
    ]

    logger.info("SmartDB処理 START")

    # ----- ログイン -----
    wait_document_ready(driver)

    set_text(driver, login_user_xpath, os.environ.get("SMART_DB_USER"), timeout=DEFAULT_TIMEOUT)
    click_xpath(driver, login_next_xpath, timeout=DEFAULT_TIMEOUT)

    set_text(driver, login_password_xpath, os.environ.get("SMART_DB_PASSWORD"), timeout=DEFAULT_TIMEOUT)
    click_xpath(driver, login_submit_xpath, timeout=DEFAULT_TIMEOUT)

    # ログイン後の一覧表示を待つ（タイムアウト時に診断情報を出力）
    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(
            lambda d: len(d.find_elements(By.XPATH, work_item_xpath)) > 0
        )
    except TimeoutException:
        dump_diagnostic(driver, "login_wait", work_item_xpath=work_item_xpath)
        raise

    # =======================================
    # ============ 一覧ページ処理 ============
    # =======================================
    # ★ 全ページ共通の処理済みキー（ページ送りで先頭に戻っても再処理しない）
    processed_all = set()

    for page_no in range(util.ITER_COUNT):
        logger.info(f"一覧ページ {page_no + 1} の処理を開始します。")

        processed_this_page = 0  # このページで処理した件数（0件なら全件処理済みとみなして終了）

        while True:
            driver.switch_to.default_content()

            try:
                WebDriverWait(driver, DEFAULT_TIMEOUT).until(
                    lambda d: len(d.find_elements(By.XPATH, work_item_xpath)) > 0
                )
            except TimeoutException:
                dump_diagnostic(driver, "list_wait", work_item_xpath=work_item_xpath)
                logger.info("一覧上の対象要素が見つからないため、このページの処理を終了します。")
                break

            elements = driver.find_elements(By.XPATH, work_item_xpath)

            target_element = None
            target_text = None

            for element in elements:
                try:
                    element_text = element.text.strip()
                except StaleElementReferenceException:
                    continue

                if "支払依頼" in element_text and "一覧" not in element_text and element_text not in processed_all:
                    target_element = element
                    target_text = element_text
                    break

            if target_element is None:
                logger.info("このページで未処理の『支払依頼』が見つからなかったため、次ページへ進みます。")
                break

            processed_all.add(target_text)
            processed_this_page += 1
            logger.info(f"########## {target_text} 処理 START ##########")

            original_window = driver.current_window_handle
            new_window = None
            approve_completed = False
            pdf_path = None

            # =======================================
            # ============ 詳細ページ処理 ============
            # =======================================
            try:
                    
                before_windows = set(driver.window_handles)
                safe_click(driver, target_element, timeout=DEFAULT_TIMEOUT)

                new_window = wait_new_window_and_switch(driver, before_windows, timeout=DEFAULT_TIMEOUT)
                logger.info(f"新しいウィンドウへ切り替えました: {new_window}")

                current_handle = switch_to_alive_window(
                    driver,
                    preferred_handle=new_window,
                    fallback_handle=original_window
                )
                logger.info(f"現在のhandle: {current_handle}")
                logger.info(f"現在のframes: {[frame_path_to_text([f]) for f in get_top_level_frames(driver)]}")
                
                before_pdf_set = util.list_pdf_files(download_dir)

                pdf_link_element = None
                pdf_context = None

                # ----- フレームからエレメント取得 -----
                try:
                    pdf_link_element = find_element_in_frame(
                        driver,
                        "operation",
                        pdf_link_xpath_candidates[0],
                        timeout=DEFAULT_TIMEOUT,
                        clickable=False
                    )
                    pdf_context = {
                        "frame_path": [{"index": 1, "name": "operation", "id": "", "src": ""}],
                        "xpath": pdf_link_xpath_candidates[0]
                    }
                except Exception:
                    pdf_link_element, pdf_context = find_element_anywhere(
                        driver,
                        pdf_link_xpath_candidates,
                        timeout=DEFAULT_TIMEOUT,
                        label="pdf_link"
                    )

                # ----- 請求書(pdfファイル)取得・分析処理 -----
                restore_context(driver, pdf_context)
                pdf_link_element = find_element_by_context(driver, pdf_context, label="pdf_link")

                pdf_link_text = extract_element_text(pdf_link_element)
                logger.info(f"PDFリンクを検出しました: {pdf_link_text}")

                safe_click(driver, pdf_link_element, timeout=DEFAULT_TIMEOUT)

                pdf_path = util.wait_new_pdf(download_dir, before_pdf_set, timeout=60)
                logger.info(f"PDFダウンロード完了: {pdf_path}")

                # pdfファイルから、合計金額・消費税・税抜金額を抽出
                total_including_tax, consumption_tax, total_decluding_tax = generate_api.main(pdf_path)
                logger.info(
                    f"PDF解析結果: 合計={total_including_tax}, 消費税={consumption_tax}, 税抜={total_decluding_tax}"
                )

                # ----- HTMLファイルから合計金額・消費税・税抜金額を抽出 -----
                amount_all = get_text_anywhere(
                    driver,
                    [amount_all_xpath],
                    timeout=DEFAULT_TIMEOUT,
                    label="amount_all"
                )
                amount_decluding = get_text_anywhere(
                    driver,
                    [amount_decluding_xpath],
                    timeout=DEFAULT_TIMEOUT,
                    label="amount_decluding"
                )
                amount_tax = get_text_anywhere(
                    driver,
                    [amount_tax_xpath],
                    timeout=DEFAULT_TIMEOUT,
                    label="amount_tax"
                )

                logger.info(
                    f"HTML取得値: 合計={amount_all}, 税抜支払={amount_decluding}, 請求消費税={amount_tax}"
                )

                # =======================================================
                # ============ pdfファイルとHTMLの突合処理実施 ============
                # =======================================================
                mismatch_flag = 0

                if total_including_tax != util.normalize_money(amount_all):
                    mismatch_flag = 1
                    logger.warning(
                        f"pdf合計金額とhtml合計金額が不一致です(pdf:{total_including_tax} html:{amount_all})"
                    )

                if consumption_tax != util.normalize_money(amount_tax):
                    if "日本アイ・ビー・エム" not in pdf_link_text:
                        mismatch_flag = 1
                        logger.warning(
                            f"pdf消費税金額とhtml請求消費税額が不一致です(pdf:{consumption_tax} html:{amount_tax})"
                        )

                try:
                    if total_decluding_tax != util.normalize_money(amount_decluding):
                        if "日本アイ・ビー・エム" not in pdf_link_text:
                            mismatch_flag = 1
                            logger.warning(
                                f"pdf税抜支払金額とhtml税抜支払金額が不一致です"
                                f"(pdf:{total_decluding_tax} html:{amount_decluding})"
                            )
                except TypeError:
                    mismatch_flag = 1
                    logger.warning(
                        f"pdf税抜支払金額とhtml税抜支払金額が不一致です"
                        f"(pdf:{total_decluding_tax} html:{amount_decluding})"
                    )

                # ------ 承認ボタンクリック処理 ------
                if mismatch_flag == 0:
                    approve_element, approve_context = find_element_anywhere(
                        driver,
                        approve_xpath_candidates,
                        timeout=DEFAULT_TIMEOUT,
                        label="approve_button"
                    )

                    logger.info(
                        f"承認ボタンを検出しました frame={frame_path_to_text(approve_context.get('frame_path', []))} "
                        f"xpath={approve_context.get('xpath')}"
                    )

                    restore_context(driver, approve_context)
                    approve_element = find_element_by_context(driver, approve_context, label="approve_button")
                    safe_click(driver, approve_element, timeout=DEFAULT_TIMEOUT)

                    logger.info("承認ボタン押下を実施しました。アラート承認と画面反映を確認します。")

                    # ------ アラート画面のボタンクリック処理 ------
                    accepted_alerts = accept_alerts_until_gone(driver, timeout_each=3, max_count=3)
                    if not accepted_alerts:
                        logger.warning("承認後のアラートが検出できませんでした。")

                    approve_completed = wait_post_approve_completed(
                        driver,
                        approve_context=approve_context,
                        approve_xpaths=approve_xpath_candidates,
                        timeout=15
                    )

                    if approve_completed:
                        logger.info("承認後の画面変化を確認しました。")
                    else:
                        logger.warning("承認後の画面変化を確認できませんでした。未反映の可能性があります。")

                else:
                    logger.warning("金額不一致のため、承認処理は実施しませんでした。")

                if pdf_path:
                    util.delete_file(pdf_path)
                    logger.info(f"PDFファイルを削除しました: {pdf_path}")

            except Exception as e:
                logger.error(f"帳票処理中にエラーが発生しました: {str(e)}")

            finally:
                try:
                    current_handles = safe_window_handles(driver)
                    current_handle = None
                    try:
                        current_handle = driver.current_window_handle
                    except Exception:
                        current_handle = None

                    if current_handle and current_handle in current_handles and current_handle != original_window:
                        if approve_completed:
                            sleep(1)
                        driver.close()
                except Exception:
                    pass

                try:
                    switch_to_alive_window(driver, preferred_handle=original_window)
                    wait_document_ready(driver)

                    if approve_completed and target_text:
                        changed = wait_list_item_disappear(driver, target_text, timeout=10)
                        if changed:
                            logger.info("一覧側でも対象案件の状態変化を確認できました。")
                        else:
                            logger.warning("一覧側で対象案件の状態変化を確認できませんでした。手動確認を推奨します。")

                except Exception as e:
                    logger.error(f"元ウィンドウへの復帰に失敗しました: {str(e)}")

            logger.info(f"########## {target_text} 処理 END ##########")

        # ★ このページで1件も処理できなかった = 全案件を処理済み → 全体を終了
        if processed_this_page == 0:
            logger.info("全案件の処理が完了したため、処理を終了します。")
            break

        # ----- iframeから抜ける（親画面に戻る） -----
        driver.switch_to.default_content()
        
        # ----- 「次へ」ボタンを探す（一覧表示画面の中に「次へ」があれば実行してページネーション） -----
        next_buttons = driver.find_elements(By.XPATH, next_page_xpath)

        if not next_buttons:
            logger.info("次へボタンが見つからないため、ページ送りを終了します。")
            break

        try:
            next_button = next_buttons[0]
            disabled_attr = next_button.get_attribute("disabled")
            aria_disabled = next_button.get_attribute("aria-disabled")

            if disabled_attr or aria_disabled == "true":
                logger.info("次へボタンが無効のため、ページ送りを終了します。")
                break

            safe_click(driver, next_button, timeout=DEFAULT_TIMEOUT)
            sleep(1)

        except Exception as e:
            logger.info(f"次ページへの移動を終了します: {str(e)}")
            break

    logger.info("SmartDB処理 END")
