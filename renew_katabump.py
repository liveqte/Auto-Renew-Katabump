#!/usr/bin/env python3

import os
import time
import logging
import random
import re
import requests
import undetected_chromedriver as uc
from datetime import datetime, timezone, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from dotenv import load_dotenv

load_dotenv()

# ===================== 配置日志 =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== 全局配置 =====================
HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'
PAUSE_BETWEEN_ACCOUNTS_MS = int(os.getenv('PAUSE_BETWEEN_ACCOUNTS_MS', '10000'))
TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID', '')
ACCOUNTS_ENV = os.getenv('ACCOUNTS', '')
PROXY_SERVER = os.getenv('HTTP_PROXY', '')

# ===================== 工具函数 =====================
def rand_int(min_val, max_val):
    return random.randint(min_val, max_val)

def sleep(ms):
    time.sleep(ms / 1000)

def human_delay():
    delay = 7000 + random.random() * 5000
    sleep(delay)

def human_type(driver, selector_type, selector_value, text):
    try:
        element = WebDriverWait(driver, 15).until(EC.visibility_of_element_located((selector_type, selector_value)))
        element.clear()
        for char in text:
            element.send_keys(char)
            sleep(rand_int(50, 150))
        return True
    except Exception as e:
        logger.warning(f"打字失败: {e}")
        return False

# ===================== Telegram 通知 =====================
def send_telegram(message, screenshot_path=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    tz_offset = timezone(timedelta(hours=8))
    time_str = datetime.now(tz_offset).strftime("%Y-%m-%d %H:%M:%S") + " HKT"
    full_message = f"🎉 Katabump 续期通知\n\n续期时间：{time_str}\n\n{message}"
    try:
        if screenshot_path and os.path.exists(screenshot_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(screenshot_path, 'rb') as photo:
                requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": full_message}, files={'photo': photo}, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": full_message}, timeout=10)
        logger.info("✅ Telegram 通知发送成功")
    except Exception as e:
        logger.warning(f"⚠️ Telegram 发送失败: {e}")

# ===================== Katabump 核心续期类 =====================
class KatabumpAutoRenew:
    def __init__(self, user, password):
        self.user = user
        self.password = password
        self.driver = None
        self.screenshot_path = None
        #self.masked_user = self.mask_email()
        self.masked_user="Secret"
    def mask_email(self):
        try:
            if "@" in self.user:
                prefix, domain = self.user.split('@')
                if len(prefix) <= 2:
                    return f"{prefix[0]}***@{domain}"
                return f"{prefix[0]}***{prefix[-1]}@{domain}"
            return f"{self.user[0]}***{self.user[-1]}" if len(self.user) > 2 else self.user
        except:
            return "UnknownUser"

    def setup_driver(self):
        chrome_options = Options()
        if HEADLESS: chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--remote-debugging-port=9222')
        if PROXY_SERVER:
            chrome_options.add_argument(f'--proxy-server={PROXY_SERVER}')
        v_env = os.getenv('CHROME_VERSION', '')
        v_main = int(v_env) if v_env.isdigit() else None
        logger.info(f"🛠️ 驱动初始化 - 指定大版本: {v_main or '自动探测'}")
        for v in [v_main, None]: # 先试指定版本，后试自动探测
            try:
                self.driver = uc.Chrome(options=chrome_options, headless=HEADLESS, version_main=v, use_subprocess=True)
                return self.driver.set_window_size(1280, 720)
            except Exception as e:
                if getattr(self, 'driver', None): self.driver.quit(); self.driver = None
                if v is None: logger.error(f"❌ 驱动启动完全失败: {e}"); raise

    def _handle_turnstile(self, context=""):
        """优化后的 Cloudflare 验证逻辑"""
        try:
            container = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile"))
            )
            size = container.size
            base_offset_x = -(size['width'] / 2) + (size['width'] * 0.12)
            rand_x = base_offset_x + random.uniform(-5, 5)
            rand_y = random.uniform(-5, 5)

            actions = ActionChains(self.driver)
            actions.move_to_element(container)
            actions.pause(random.uniform(0.5, 0.8))
            actions.move_to_element_with_offset(container, rand_x, rand_y)
            actions.click_and_hold()
            actions.pause(random.uniform(0.1, 0.25))
            actions.release()
            actions.perform()
            
            logger.info(f"🖱️ {self.masked_user} - [{context}] 执行偏移点击...")
            
            # 轮询检查 Token
            validated = False
            for _ in range(15):
                token = self.driver.execute_script(
                    'return document.querySelector("input[name=\'cf-turnstile-response\']").value;'
                )
                if token and len(token) > 20:
                    logger.info(f"✅ {self.masked_user} - [{context}] 验证已通过 (Token Ready)")
                    sleep(1500 + random.random() * 1000)
                    validated = True
                    break
                sleep(1000)
            return validated
        except Exception as e:
            logger.error(f"❌ {self.masked_user} - [{context}] 验证交互失败: {e}")
            return False
    def _handle_turnstile2(self):
        checkbox_xpath = "//div[@class='altcha']//input[@type='checkbox' and @required]"
        checkbox = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, checkbox_xpath))
        )
        checkbox.click()
            
    def process(self):
        logger.info(f"🚀 开始登录账号: {self.masked_user}")
        self.driver.get("https://dashboard.katabump.com/auth/login")
        sleep(5000 + random.random() * 2000)

        # --- 第一步：输入用户名 ---
        logger.info(f"📝 {self.masked_user} - 填写用户名/邮箱...")
        if not human_type(self.driver, By.CSS_SELECTOR, "input#email", self.user):
            raise Exception("未找到用户名输入框")
        sleep(2000 + random.random() * 1000)

        # --- 第二步：输入密码 ---
        logger.info(f"🔒 {self.masked_user} - 填写密码...")
        if not human_type(self.driver, By.CSS_SELECTOR, "input#password", self.password):
            raise Exception("未找到密码输入框")
        sleep(2000 + random.random() * 1000)

        # --- 登录页 CF 验证 ---
        self._handle_turnstile("Login Auth")

        logger.info(f"📤 {self.masked_user} - 点击“Login”提交登录...")
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        human_delay()

        # --- 第三步： Manage Server ---
        logger.info(f"🎯 {self.masked_user} - 进入服务器详情页...")
        manage_btn = WebDriverWait(self.driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'See')]"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", manage_btn)
        sleep(1000 + random.random() * 1000)
        self.driver.execute_script("arguments[0].click();", manage_btn)
        human_delay()
 # =========== 🔹 新增：检查续期日期逻辑 🔹 ===========
        logger.info(f"📅 {self.masked_user} - 检查是否到达续期日期...")
        try:
            # 定位 Expiry 日期元素（匹配你提供的 HTML 结构）
            expiry_element = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Expiry')]/following-sibling::div"))
            )
            expiry_text = expiry_element.text.strip()
            logger.info(f"⌛ {self.masked_user} - 页面显示到期时间: {expiry_text}")
            
            # 解析日期（支持多种常见格式）
            from datetime import datetime, timezone, timedelta
            tz_hkt = timezone(timedelta(hours=8))  # 香港时间
            today = datetime.now(tz_hkt).date()
            
            expiry_date = None
            # 尝试解析不同日期格式
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y年%m月%d日"]:
                try:
                    expiry_date = datetime.strptime(expiry_text, fmt).date()
                    break
                except ValueError:
                    continue
            
            # 如果无法解析日期，记录警告但继续执行（避免误杀）
            if expiry_date is None:
                logger.warning(f"⚠️ {self.masked_user} - 无法解析日期格式 '{expiry_text}'，继续执行续期流程")
            # 如果到期日不是今天，跳过续期并发送通知
            elif expiry_date != today:
                days_diff = (expiry_date - today).days
                if days_diff > 0:
                    notice = f"⏰ {self.masked_user}\n📅 未到续期时间，到期日: {expiry_text}\n🔄 剩余 {days_diff} 天"
                else:
                    notice = f"⚠️ {self.masked_user}\n📅 日期异常，到期日: {expiry_text} (已过 {abs(days_diff)} 天)"
                
                logger.info(f"ℹ️ {self.masked_user} - {notice}")
                # 返回 True 表示"正常跳过"，避免触发重试机制
                return True, notice
            
            logger.info(f"✅ {self.masked_user} - 今天是续期日 ({expiry_text})，继续执行续期流程")
            
        except Exception as e:
            logger.warning(f"⚠️ {self.masked_user} - 检查续期日期时异常: {e}，继续执行续期流程")
        # =========== 🔹 新增逻辑结束 🔹 ===========
        # --- 第四步： Renew Server ---
        logger.info(f"🔄 {self.masked_user} - 准备续期流程...")
        initial_expiry = ""
        try:
            initial_expiry_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Expiry')]/following-sibling::div"))
            )
            initial_expiry = initial_expiry_element.text.strip()
            logger.info(f"⌛ {self.masked_user} - 当前到期时间: {initial_expiry}")
        except Exception:
            logger.warning(f"⚠️ {self.masked_user} - 无法读取初始时间")

        try:
            renew_trigger = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Renew')]"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", renew_trigger)
            self.driver.execute_script("arguments[0].click();", renew_trigger)
            logger.info(f"📑 {self.masked_user} - 已打开 Renew 弹窗")
        except Exception as e:
            raise Exception(f"无法打开弹窗: {e}")
        sleep(2000 + random.random() * 1000)

        # --- 续期弹窗 CF 验证 ---
        self._handle_turnstile2()

        # --- 最终 Renew 按钮 ---
        try:
            confirm_btn_xpath = "//div[@id='renew-modal']//button[@type='submit' and contains(text(), 'Renew')]"
            confirm_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, confirm_btn_xpath))
            )
            logger.info(f"🚀 {self.masked_user} - 点击最终 Renew 按钮...")
            self.driver.execute_script("arguments[0].click();", confirm_btn)
        except Exception as e:
            raise Exception(f"弹窗内提交失败: {e}")
            
        logger.info(f"⏳ {self.masked_user} - 等待数据更新...")
        sleep(7000 + random.random() * 2000)

        # 结果核验
        try:
            alerts = self.driver.find_elements(By.CSS_SELECTOR, ".alert-danger")
            if alerts and alerts[0].is_displayed():
                alertmsg = alerts[0].text.strip().replace('×', '')
                logger.warning(f"⚠️ {self.masked_user} - 续期失败: {alertmsg}")
                return False, f"⏳ {self.masked_user}\n⚠️ 续期失败: {alertmsg}"
            
            final_expiry_element = self.driver.find_element(By.XPATH, "//div[contains(text(), 'Expiry')]/following-sibling::div")
            final_expiry = final_expiry_element.text.strip()
            logger.info(f"✅ {self.masked_user} - 续期后到期时间: {final_expiry}")

            if final_expiry != initial_expiry and len(final_expiry) > 0:
                return True, f"✅ {self.masked_user}\n🎉 续期成功: {final_expiry}"
            else:
                return False, f"⚠️ {self.masked_user}\n⚠️ 时间未更新 ({initial_expiry})"
        except Exception as e:
            return False, f"❌ {self.masked_user}\n⚠️ 验证结果出错: {e}"

    def run(self):
        """引入重试机制的核心运行逻辑"""
        max_retries = 3
        last_error = ""
        
        for attempt in range(max_retries):
            try:
                if not self.driver:
                    self.setup_driver()
                
                if attempt > 0:
                    logger.info(f"🔄 {self.masked_user} - 正在进行第 {attempt + 1} 次尝试...")
                    self.driver.refresh()
                    sleep(5000 + random.random() * 3000)

                success, message = self.process()
                
                if success:
                    return True, message
                else:
                    last_error = message
                    if "时间未更新" in message or "续期失败" in message:
                        break
                    
            except Exception as e:
                last_error = f"异常：{str(e)[:50]}"
                logger.error(f"❌ {self.masked_user} 第 {attempt + 1} 次执行出错: {e}")
                
            if attempt < max_retries - 1:
                sleep(5000 + random.random() * 5000)
        
        # 最终失败处理
        self.screenshot_path = f"error-{self.user.split('@')[0]}.png"
        if self.driver:
            self.driver.save_screenshot(self.screenshot_path)
        return False, f"❌ {self.masked_user} 历经 {max_retries} 次尝试仍失败: {last_error}"

# ===================== 主逻辑管理 =====================
class MultiManager:
    def __init__(self):
        raw_accs = re.split(r'[,;]', ACCOUNTS_ENV)
        self.accounts = []
        for a in raw_accs:
            if ':' in a:
                u, p = a.split(':', 1)
                self.accounts.append({'user': u.strip(), 'pass': p.strip()})

    def run_all(self):
        total = len(self.accounts)
        logger.info(f"🔍 发现 {total} 个账号需要续期")
        results = []
        last_screenshot = None
        success_count = 0

        for i, acc in enumerate(self.accounts):
            logger.info(f"\n📋 处理第 {i+1}/{total} 个账号")
            bot = KatabumpAutoRenew(acc['user'], acc['pass'])
            success, msg = bot.run()
            results.append({'message': msg, 'success': success})
            if success: success_count += 1
            if bot.screenshot_path: last_screenshot = bot.screenshot_path

            if i < total - 1:
                wait_time = PAUSE_BETWEEN_ACCOUNTS_MS + random.random() * 5000
                logger.info(f"⏳ 账号间歇期：等待 {round(wait_time/1000)} 秒...")
                sleep(wait_time)

        summary = f"📊 登录汇总: {success_count}/{total} 个账号成功\n\n"
        summary += "\n\n".join([r['message'] for r in results])
        send_telegram(summary, last_screenshot)

        if last_screenshot and os.path.exists(last_screenshot):
            import glob
            for f in glob.glob("error-*.png"): os.remove(f)
        logger.info("\n✅ 所有账号处理完成！")

if __name__ == "__main__":
    if not ACCOUNTS_ENV:
        logger.error("❌ 未配置账号")
        exit(1)
    try:
        MultiManager().run_all()
    finally:
        os._exit(0)
