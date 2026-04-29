"""
DJI商城自动下单工具 - Osmo Pocket 4 全能套装
打包命令: pyinstaller --onefile --add-binary "playwright/driver/;." dji_order.py
"""

from playwright.sync_api import sync_playwright, TimeoutError
import os
import sys
import logging
import tempfile
import atexit

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# 配置区
# ============================================
PRODUCT_URL = "https://store.dji.com/cn/product/osmo-pocket-4-creator-combo?vid=218481"
PRODUCT_NAME = "Osmo Pocket 4 全能套装"

# 使用临时目录存放cookies
COOKIES_DIR = os.path.join(tempfile.gettempdir(), "dji_order_tool")
COOKIES_FILE = os.path.join(COOKIES_DIR, "cookies.json")


# ============================================


def setup_temp_dir():
    """创建临时目录"""
    if not os.path.exists(COOKIES_DIR):
        os.makedirs(COOKIES_DIR)


def cleanup_temp_dir():
    """程序退出时清理临时文件"""
    try:
        if os.path.exists(COOKIES_FILE):
            os.remove(COOKIES_FILE)
        if os.path.exists(COOKIES_DIR):
            os.rmdir(COOKIES_DIR)
    except:
        pass


def ensure_login():
    """确保已经登录"""
    setup_temp_dir()

    if os.path.exists(COOKIES_FILE):
        use_saved = input("\n发现上次登录状态，是否使用？(y/n): ").lower()
        if use_saved == 'y':
            return

    logger.info("需要登录DJI账号")
    print("\n浏览器即将打开，请手动登录...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://account.dji.com/login")

        input("\n登录成功后按回车继续...")
        context.storage_state(path=COOKIES_FILE)
        browser.close()
        logger.info("登录状态已保存")


def get_address():
    """让用户填写地址"""
    print("\n" + "=" * 40)
    print("请填写收货地址")
    print("=" * 40)

    address = {
        "name": input("收件人姓名: ").strip(),
        "phone": input("手机号码: ").strip(),
        "province": input("省份/直辖市 (如: 河北省): ").strip(),
        "city": input("城市 (如: 石家庄市): ").strip(),
        "district": input("区/县 (如: 长安区): ").strip(),
        "street": input("详细地址: ").strip()
    }

    # 验证必填项
    for key, value in address.items():
        if not value:
            print(f"错误: {key} 不能为空")
            return get_address()

    return address


def fill_form(page, address):
    """填写地址表单"""
    try:
        page.wait_for_selector("input[data-test-locator='inputFirstName']", timeout=15000)

        # 姓名和手机
        page.fill("input[data-test-locator='inputFirstName']", address["name"])
        page.fill("input[data-test-locator='inputPhone']", address["phone"])

        # 地区级联选择
        city_box = page.locator('div[tabindex="0"][role="textbox"]').first
        city_box.click()
        page.wait_for_timeout(1000)

        for part in [address["province"], address["city"], address["district"]]:
            option = page.locator(f'text="{part}"').last
            option.click()
            page.wait_for_timeout(400)

        # 详细地址
        page.fill("input[data-test-locator='inputAddress']", address["street"])

        return True
    except Exception as e:
        logger.error(f"填表失败: {e}")
        page.screenshot(path="fill_error.png")
        return False


def start_order():
    """主流程"""
    print(f"\n{'=' * 40}")
    print(f"DJI自动下单 - {PRODUCT_NAME}")
    print(f"{'=' * 40}")

    # 1. 登录
    ensure_login()

    # 2. 获取地址
    address = get_address()

    # 3. 开始下单
    print(f"\n开始自动下单...")
    print("浏览器操作中，请勿关闭窗口...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )

        context = browser.new_context(
            storage_state=COOKIES_FILE,
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()

        try:
            # 步骤1: 打开商品页
            page.goto(PRODUCT_URL, wait_until="commit")

            # 步骤2: 加入购物车
            add_btn = page.locator("text=加入购物车").first
            add_btn.wait_for(state="visible", timeout=10000)
            add_btn.click()
            logger.info("✓ 已加入购物车")

            # 步骤3: 进购物车
            page.goto("https://store.dji.com/cn/cart", wait_until="commit")

            # 步骤4: 去结算
            checkout = page.locator("text=去结算").first
            checkout.wait_for(state="visible", timeout=10000)
            checkout.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            # 步骤5: 如果回登录页就重试
            if "login" in page.url:
                logger.warning("会话过期，重试...")
                page.goto("https://store.dji.com/cn/cart", wait_until="commit")
                checkout = page.locator("text=去结算").first
                checkout.wait_for(state="visible", timeout=10000)
                checkout.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)

            # 步骤6: 填写地址
            if fill_form(page, address):
                print("\n" + "=" * 40)
                print("✓ 地址填写完成！")
                print("请在浏览器中手动完成滑块验证")
                print("=" * 40)
            else:
                print("\n地址填写失败，请查看截图")

            input("\n按回车关闭浏览器...")

        except TimeoutError:
            logger.error("操作超时，可能是网络问题")
            page.screenshot(path="timeout.png")
        except Exception as e:
            logger.error(f"出错: {e}")
            page.screenshot(path="error.png")
        finally:
            browser.close()


if __name__ == "__main__":
    # 注册退出清理
    atexit.register(cleanup_temp_dir)

    try:
        start_order()
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n程序出错: {e}")
        input("\n按回车退出...")