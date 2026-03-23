import time
import json
import os
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import requests
from PIL import Image

from config import INFO_DIR as info_dir, QRCODE_DIR as qrcode_dir


def _build_headers(token):
    """构建 API 请求头"""
    return {
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Windows"',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "token": token,
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://class.fangban.net/course",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
        "Cookie": "token=%s" % token,
    }


def login_with_qrcode(qrcode_callback=None, abort_check=None):
    """
    使用Selenium进行二维码登录并获取cookie
    qrcode_callback: 可选，回调函数接收 base64 编码的二维码截图
    abort_check: 可选，返回 True 时中止登录流程
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)

    try:
        login_url = "https://class.fangban.net/login"
        print(f"正在打开登录页面: {login_url}")
        driver.get(login_url)

        if abort_check and abort_check():
            return None

        print("等待二维码加载...")
        wait = WebDriverWait(driver, 20)

        qr_code_img = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt='二维码']"))
        )

        print("✓ 二维码已加载")

        # 获取二维码图片
        if qrcode_callback:
            # Web 模式：通过元素截图获取 base64，不保存文件
            qr_base64 = qr_code_img.screenshot_as_base64
            qrcode_callback(qr_base64)
            print("✓ 二维码已通过回调传递")
        else:
            # CLI 模式：下载保存文件
            qr_code_url = qr_code_img.get_attribute("src")
            print(f"二维码URL: {qr_code_url}")
            save_qrcode(qr_code_url)

        print("\n等待扫码中... (超时时间: 120秒)")

        original_url = driver.current_url
        login_success = False
        timeout = 120
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 检查是否需要中止
            if abort_check and abort_check():
                print("登录流程已被取消")
                return None

            # 检查页面跳转
            if driver.current_url != original_url:
                print("✓ 检测到页面跳转，登录成功！")
                login_success = True
                break

            # 检查 token cookie 是否已设置
            for cookie in driver.get_cookies():
                if cookie["name"] == "token" and cookie.get("value"):
                    print("✓ 检测到 token cookie，登录成功！")
                    login_success = True
                    break
            if login_success:
                break

            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0 and elapsed > 0:
                print(f"已等待 {elapsed} 秒...")

            time.sleep(2)

        if not login_success:
            print("❌ 登录超时，请重试")
            return None

        print("\n正在获取登录后的token...")

        cookies = driver.get_cookies()
        session_cookies = {}
        for cookie in cookies:
            session_cookies[cookie["name"]] = cookie["value"]

        print("\n验证cookie有效性...")
        verify, nick = verify_cookies(session_cookies)
        if verify:
            print("✓ Cookie验证成功！")
            save_cookies_to_file(session_cookies, nick)
            return session_cookies
        else:
            print("❌ Cookie验证失败")
            return None

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        driver.quit()
        print("浏览器已关闭")


def save_qrcode(qr_code_url):
    """下载二维码并保存到文件（不弹窗）"""
    if not qrcode_dir.exists():
        qrcode_dir.mkdir(parents=True)

    try:
        print("正在下载二维码...")
        response = requests.get(qr_code_url, timeout=10)
        img = Image.open(BytesIO(response.content))

        qrimg_path = qrcode_dir / "qrcode.png"
        img.save(qrimg_path)
        print(f"✓ 二维码已保存为 {qrimg_path}")

    except Exception as e:
        print(f"保存二维码时出错: {e}")


def display_qrcode(qr_code_url):
    """下载并显示二维码（CLI 模式用，会弹窗）"""
    save_qrcode(qr_code_url)
    try:
        qrimg_path = qrcode_dir / "qrcode.png"
        img = Image.open(qrimg_path)
        img.show()
    except Exception as e:
        print(f"显示二维码时出错: {e}")


def verify_cookies(cookies):
    """验证cookie是否有效"""
    token = cookies.get("token", "")

    try:
        test_url = "https://class.fangban.net/api/users/info/"
        headers = _build_headers(token)

        response = requests.get(test_url, headers=headers, timeout=10)
        response_data = response.json()
        if response_data.get("code") == 200:
            return True, response_data["data"]["nick"]
        else:
            print(f"验证失败，响应内容: {response_data.get('msg')}")
            return False, None

    except Exception as e:
        print(f"验证过程中出错: {e}")
        return False, None


def save_cookies_to_file(cookies, nick_name, filename="cookies.json"):
    """保存cookie到文件"""
    cookies["name"] = nick_name

    if not info_dir.exists():
        info_dir.mkdir(parents=True)

    filepath = info_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    print(f"✓ Cookie已保存到 {filepath}")


def load_cookies_from_file(filename="cookies.json"):
    """从文件加载cookie"""
    if not info_dir.exists():
        info_dir.mkdir(parents=True)

    filepath = info_dir / filename

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        print(f"✓ 从 {filepath} 加载cookie成功")
        return cookies
    else:
        print(f"❌ 文件 {filepath} 不存在")
        return None


def delete_cookies(filename="cookies.json"):
    """删除已保存的cookie文件"""
    filepath = info_dir / filename
    if filepath.exists():
        filepath.unlink()
        print("✓ 已退出登录，删除cookie文件")
        return True
    else:
        print("❌ cookie文件不存在")
        return False


def has_saved_cookies(filename="cookies.json"):
    """仅检测 cookies 文件是否存在，返回 (exists, name)"""
    filepath = info_dir / filename
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return True, data.get("name")
        except Exception:
            return False, None
    return False, None


def check_login_status():
    """检查当前登录状态，返回 {"logged_in": bool, "name": str|None, "token": str|None}"""
    saved_cookies = load_cookies_from_file()
    if not saved_cookies:
        return {"logged_in": False, "name": None, "token": None}

    verify, nick = verify_cookies(saved_cookies)
    if verify:
        return {
            "logged_in": True,
            "name": nick,
            "token": saved_cookies.get("token", ""),
        }
    else:
        return {"logged_in": False, "name": None, "token": None}


def get_token_auto(reuse=True):
    """
    自动获取 token（无 input 交互）。
    reuse=True 时优先复用已有 cookie。
    返回 {"token": str, "name": str} 或 None。
    """
    saved_cookies = load_cookies_from_file()

    if saved_cookies and reuse:
        verify, nick = verify_cookies(saved_cookies)
        if verify:
            return {"token": saved_cookies.get("token", ""), "name": nick}

    cookies = login_with_qrcode()
    if cookies:
        return {"token": cookies.get("token", ""), "name": cookies.get("name", "")}
    return None


def get_token():
    """原始 CLI 交互式获取 token"""
    saved_cookies = load_cookies_from_file()

    if saved_cookies:
        print("发现已保存的cookie，正在验证...")
        verify, nick = verify_cookies(saved_cookies)
        if verify:
            choice = input(f"当前用户:{nick},是否要继续使用该用户登录？(y/n)")
            if choice.lower() == "y":
                print("使用已保存的cookie...")
                cookies = saved_cookies
            else:
                print("重新登录流程...")
                cookies = login_with_qrcode()
        else:
            print("已保存的cookie已失效，需要重新登录")
            cookies = login_with_qrcode()
    else:
        print("没有找到已保存的cookie，开始登录流程")
        cookies = login_with_qrcode()

    return cookies


if __name__ == "__main__":
    get_token()
