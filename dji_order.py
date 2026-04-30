"""
DJI商城自动下单工具 - Osmo Pocket 4 全能套装
使用说明：
1. 首次使用会自动打开浏览器登录
2. 登录状态自动保存，下次无需重复登录
3. 地址提前填写好，一键开始
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
# 固定商品
# ============================================
PRODUCT_URL = "https://store.dji.com/cn/product/osmo-pocket-4-creator-combo?vid=218481"
PRODUCT_NAME = "Osmo Pocket 4 全能套装"

# Cookies保存位置（系统临时文件夹）
COOKIES_DIR = os.path.join(tempfile.gettempdir(), "dji_order_tool")
COOKIES_FILE = os.path.join(COOKIES_DIR, "cookies.json")
ADDRESS_FILE = os.path.join(COOKIES_DIR, "address.txt")
# ============================================


def setup():
    """初始化：创建临时文件夹"""
    if not os.path.exists(COOKIES_DIR):
        os.makedirs(COOKIES_DIR)


def cleanup():
    """程序退出时清理"""
    pass


def ensure_login():
    """检查登录状态，如果失效就重新登录"""
    setup()
    
    if os.path.exists(COOKIES_FILE):
        # 检查cookies是否还有效
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(storage_state=COOKIES_FILE)
                page = context.new_page()
                
                # 访问需要登录的页面测试
                page.goto("https://store.dji.com/cn/cart", wait_until="commit")
                page.wait_for_timeout(2000)
                
                # 如果跳转到登录页，说明cookies失效
                if "login" in page.url:
                    browser.close()
                    os.remove(COOKIES_FILE)
                    logger.warning("登录已过期，需要重新登录")
                    return login()
                
                browser.close()
                logger.info("登录状态有效")
                return True
                
        except Exception:
            # 如果检查失败，删除旧cookies重新登录
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
            return login()
    else:
        return login()


def login():
    """手动登录并保存cookies"""
    logger.info("需要登录DJI账号")
    print("\n" + "="*50)
    print("浏览器即将打开，请手动登录DJI账号")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://account.dji.com/login")
        
        input("\n登录成功后，按回车键继续...")
        
        context.storage_state(path=COOKIES_FILE)
        browser.close()
        logger.info("登录状态已保存")
        print("✓ 登录成功！下次无需重复登录\n")
        return True


def get_address():
    """获取地址：从文件读取或让用户输入"""
    if os.path.exists(ADDRESS_FILE):
        with open(ADDRESS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 6:
                address = {
                    "name": lines[0].strip(),
                    "phone": lines[1].strip(),
                    "province": lines[2].strip(),
                    "city": lines[3].strip(),
                    "district": lines[4].strip(),
                    "street": lines[5].strip()
                }
                print("\n已保存的地址：")
                print(f"  {address['name']} {address['phone']}")
                print(f"  {address['province']}{address['city']}{address['district']} {address['street']}")
                
                use_saved = input("\n使用此地址？(y/n): ").lower()
                if use_saved == 'y':
                    return address
    
    # 让用户输入新地址
    print("\n" + "="*50)
    print("请填写收货地址（按回车确认）")
    print("="*50)
    
    address = {
        "name": input("收件人姓名: ").strip(),
        "phone": input("手机号码: ").strip(),
        "province": input("省份 (如: 广东省): ").strip(),
        "city": input("城市 (如: 深圳市): ").strip(),
        "district": input("区/县 (如: 南山区): ").strip(),
        "street": input("详细地址: ").strip()
    }
    
    # 保存地址到文件
    with open(ADDRESS_FILE, 'w', encoding='utf-8') as f:
        f.write(f"{address['name']}\n")
        f.write(f"{address['phone']}\n")
        f.write(f"{address['province']}\n")
        f.write(f"{address['city']}\n")
        f.write(f"{address['district']}\n")
        f.write(f"{address['street']}\n")
    
    print("✓ 地址已保存")
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
    """主流程：登录检查 → 填写地址 → 开始下单"""
    
    print(f"\n{'='*50}")
    print(f"DJI自动下单工具 - {PRODUCT_NAME}")
    print(f"{'='*50}")
    
    # 1. 检查登录
    print("\n🔐 检查登录状态...")
    ensure_login()
    
    # 2. 获取地址
    address = get_address()
    
    # 3. 准备开始
    print("\n" + "="*50)
    print("准备自动下单：")
    print(f"商品：{PRODUCT_NAME}")
    print(f"收件人：{address['name']}")
    print(f"地址：{address['province']}{address['city']}{address['district']} {address['street']}")
    print("="*50)
    print("\n⚠️  重要：请确保网络畅通，浏览器会自动操作")
    print("⚠️  程序会在滑块验证处停止，需手动完成")
    
    input("\n按回车键开始自动下单...")
    
    # 4. 执行下单
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
            print("\n⏳ 正在打开商品页...")
            page.goto(PRODUCT_URL, wait_until="commit")
            page.wait_for_timeout(2000)  # 等页面完全加载
            
            # 步骤2: 智能点击购买按钮（兼容"加入购物车"和"立即购买"）
            print("⏳ 查找购买按钮...")
            
            # 等待按钮出现
            page.wait_for_selector("button:has-text('购买'), button:has-text('加入购物车')", timeout=10000)
            
            # 判断是哪种按钮
            buy_btn = page.locator("button:has-text('立即购买')").first
            cart_btn = page.locator("button:has-text('加入购物车')").first
            
            is_direct_buy = False
            
            if buy_btn.count() > 0 and buy_btn.is_visible():
                buy_btn.click()
                print("✓ 已点击【立即购买】")
                is_direct_buy = True
            elif cart_btn.count() > 0 and cart_btn.is_visible():
                cart_btn.click()
                print("✓ 已点击【加入购物车】")
                is_direct_buy = False
            else:
                # 都找不到，尝试用ID
                page.locator("#gtm_ShopNow").click()
                print("✓ 已点击购买按钮（备用方案）")
                is_direct_buy = True
            
            # 步骤3: 如果不是直接购买，就去购物车结算
            if not is_direct_buy:
                print("⏳ 进入购物车...")
                page.goto("https://store.dji.com/cn/cart", wait_until="commit")
                page.wait_for_timeout(1000)
                
                print("⏳ 去结算...")
                checkout = page.locator("text=去结算").first
                checkout.wait_for(state="visible", timeout=10000)
                checkout.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            else:
                # 直接购买，等待页面跳转
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            
            # 步骤4: 如果回登录页就重试
            if "login" in page.url:
                print("⏳ 会话过期，重试中...")
                page.goto("https://store.dji.com/cn/cart", wait_until="commit")
                checkout = page.locator("text=去结算").first
                checkout.wait_for(state="visible", timeout=10000)
                checkout.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            
            # 步骤5: 填写地址
            print("⏳ 填写地址...")
            if fill_form(page, address):
                print("\n" + "="*50)
                print("✅ 地址填写完成！")
                print("请在浏览器中手动完成滑块验证")
                print("="*50)
            else:
                print("\n❌ 地址填写失败，请查看截图")
            
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
    atexit.register(cleanup)
    
    try:
        start_order()
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n程序出错: {e}")
        input("\n按回车退出...")
