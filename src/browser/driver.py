"""
浏览器驱动管理模块

负责创建和管理WebDriver实例
"""

import logging
from typing import Optional, Dict, Any

# 浏览器自动化导入
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )

    # 修复undetected_chromedriver的__del__方法以防止句柄错误
    def safe_del(self):
        """安全的析构方法，避免句柄无效错误"""
        try:
            if hasattr(self, "_is_patched") and self._is_patched:
                return  # 已经被安全关闭，不再处理
        except:
            pass

    # 应用补丁
    if hasattr(uc.Chrome, "__del__"):
        uc.Chrome.__del__ = safe_del

    UNDETECTED_AVAILABLE = True
except ImportError:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException,
            NoSuchElementException,
            WebDriverException,
        )

        UNDETECTED_AVAILABLE = False
    except ImportError:
        raise ImportError("请安装selenium: pip install selenium")


class SafeChrome:
    """安全Chrome驱动包装器"""

    def __init__(self, driver):
        self._driver = driver
        self._is_closed = False

    def __getattr__(self, name):
        """代理所有属性访问到原始driver"""
        if self._is_closed:
            raise RuntimeError("Driver has been closed")
        return getattr(self._driver, name)

    def close(self):
        """关闭浏览器窗口"""
        if not self._is_closed and self._driver:
            try:
                self._driver.close()
            except Exception:
                pass

    def quit(self):
        """退出Chrome驱动"""
        if not self._is_closed and self._driver:
            try:
                # 标记已被安全关闭，防止__del__重复处理
                self._driver._is_patched = True
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._is_closed = True
                self._driver = None

    def __del__(self):
        """析构函数，防止垃圾回收器错误"""
        # 什么都不做，避免在析构时出现错误
        pass


class BrowserDriverManager:
    """浏览器驱动管理器"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化浏览器驱动管理器

        Args:
            logger: 日志器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.driver: Optional[SafeChrome] = None
        self._is_cleanup_done = False
        self.wait: Optional[WebDriverWait] = None

    def create_driver(self, config: Dict[str, Any]) -> bool:
        """
        创建浏览器驱动

        Args:
            config: 浏览器配置

        Returns:
            是否创建成功
        """
        try:
            self.logger.info("开始创建浏览器驱动")

            headless = config.get("headless", True)

            if UNDETECTED_AVAILABLE:
                self.logger.info("使用undetected-chromedriver创建浏览器")
                options = uc.ChromeOptions()
            else:
                self.logger.info("使用标准selenium创建浏览器")
                # 这里 UNDETECTED_AVAILABLE == False 时，已经从 selenium 导入了 Options
                options = Options()

            # 基础配置
            if headless:
                options.add_argument("--headless")
                self.logger.debug("启用无头模式")
            else:
                self.logger.debug("使用有头模式（显示浏览器窗口）")

            # 添加浏览器选项
            browser_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--disable-popup-blocking",
            ]

            import os  # 放这里即可

            # Github Action 和 CI 环境的额外配置
            if os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
                self.logger.debug("检测到CI环境，添加额外配置")
                ci_args = [
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=TranslateUI",
                    "--disable-ipc-flooding-protection",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-default-apps",
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-sync",
                    "--disable-translate",
                    "--hide-scrollbars",
                    "--mute-audio",
                    "--no-zygote",
                    "--disable-background-networking",
                    "--disable-web-security",
                    "--allow-running-insecure-content",
                    "--window-size=1920,1080",
                    # 中文字体支持配置
                    "--font-render-hinting=none",
                    "--disable-font-subpixel-positioning",
                    "--force-device-scale-factor=1",
                ]
                browser_args.extend(ci_args)

            for arg in browser_args:
                options.add_argument(arg)
                self.logger.debug(f"添加浏览器参数: {arg}")

            # 配置浏览器偏好设置
            prefs = {
                "profile.default_content_setting_values": {"popups": 1},
                # 中文字体配置
                "webkit.webprefs.fonts.standard.Hans": "SimSun",
                "webkit.webprefs.fonts.serif.Hans": "SimSun",
                "webkit.webprefs.fonts.sansserif.Hans": "SimHei",
                "webkit.webprefs.fonts.cursive.Hans": "SimSun",
                "webkit.webprefs.fonts.fantasy.Hans": "SimSun",
                "webkit.webprefs.fonts.pictograph.Hans": "SimSun",
                "webkit.webprefs.default_encoding": "UTF-8",
            }

            # CI环境的额外字体配置
            if os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
                # 在CI环境中，使用系统可能安装的中文字体
                ci_font_prefs = {
                    "webkit.webprefs.fonts.standard.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.serif.Hans": "Noto Serif CJK SC",
                    "webkit.webprefs.fonts.sansserif.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.cursive.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.fantasy.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.pictograph.Hans": "Noto Sans CJK SC",
                }
                prefs.update(ci_font_prefs)
                self.logger.debug("配置CI环境中文字体偏好")

            options.add_experimental_option("prefs", prefs)
            self.logger.debug("配置浏览器偏好设置: 弹出窗口允许、中文字体支持")

            # =========================
            # ① 自动检测 Chrome 路径
            # =========================
            self.logger.debug("开始初始化浏览器实例 (Chrome 路径探测)")
            possible_paths = [
                "/root/chrome-linux64/chrome",           # 旧路径（兼容）
                "/usr/local/chrome-141/chrome",          # CI/CD 安装路径（141）
                "/usr/local/bin/google-chrome",          # 通用系统路径
                "/usr/bin/google-chrome",                # 备用路径
            ]

            custom_chrome_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    custom_chrome_path = path
                    break

            if custom_chrome_path:
                # 对于标准 selenium 是用 binary_location
                options.binary_location = custom_chrome_path
                self.logger.info(f"✅ 使用自定义 Chrome 路径: {custom_chrome_path}")
            else:
                self.logger.warning(
                    "⚠️ 未找到可用的自定义 Chrome 路径，将使用系统默认 Chrome"
                )

            # =========================
            # ② 自动检测 ChromeDriver 路径（关键）
            # =========================
            # 优先级：config > 环境变量 > 默认 /usr/local/bin/chromedriver
            driver_path = (
                config.get("chromedriver_path")
                or os.environ.get("CHROMEDRIVER_PATH")
                or "/usr/local/bin/chromedriver"
            )

            use_custom_driver = False
            if os.path.exists(driver_path):
                use_custom_driver = True
                self.logger.info(f"✅ 使用自定义 ChromeDriver 路径: {driver_path}")
            else:
                self.logger.warning(
                    f"⚠️ 未找到指定的 ChromeDriver 路径: {driver_path}，将使用默认驱动管理"
                )

            # =========================
            # ③ 创建驱动实例
            # =========================
            if UNDETECTED_AVAILABLE:
                # undetected-chromedriver 分支
                uc_args: Dict[str, Any] = {
                    "options": options,
                }

                # 指定浏览器和驱动路径（两者版本保持 141）
                if custom_chrome_path:
                    # 一些版本的 uc 支持 browser_executable_path
                    uc_args["browser_executable_path"] = custom_chrome_path
                if use_custom_driver:
                    # 这是关键：强制用我们安装的 141 版本 chromedriver
                    uc_args["driver_executable_path"] = driver_path

                raw_driver = uc.Chrome(**uc_args)
            else:
                # 标准 selenium 分支
                # 这里一定有 webdriver / Service / Options 的导入
                if use_custom_driver:
                    service = Service(executable_path=driver_path)
                else:
                    # 让 selenium 自己在 PATH 里找
                    service = Service()

                raw_driver = webdriver.Chrome(service=service, options=options)

            # 使用安全包装器
            self.driver = SafeChrome(raw_driver)
            self.wait = WebDriverWait(self.driver, 10)

            # 获取浏览器信息
            try:
                browser_version = self.driver.capabilities.get(
                    "browserVersion", "Unknown"
                )
                driver_version = self.driver.capabilities.get("chrome", {}).get(
                    "chromedriverVersion", "Unknown"
                )
                self.logger.debug(f"浏览器版本: {browser_version}")
                self.logger.debug(f"驱动版本: {driver_version}")
            except Exception as e:
                self.logger.debug(f"获取浏览器信息失败: {e}")

            self.logger.info("浏览器驱动创建成功")
            return True

        except Exception as e:
            self.logger.error(f"创建浏览器驱动失败: {e}")
            return False

    def get_driver(self):
        """获取WebDriver实例"""
        return self.driver

    def get_wait(self) -> Optional[WebDriverWait]:
        """获取WebDriverWait实例"""
        return self.wait

    def quit_driver(self) -> None:
        """关闭浏览器驱动"""
        if self.driver and not self._is_cleanup_done:
            try:
                # 先尝试关闭所有窗口
                try:
                    self.driver.close()
                except Exception:
                    pass  # 忽略关闭窗口的错误

                # 然后退出驱动
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.warning(f"关闭浏览器失败: {e}")
            finally:
                # 清空引用，防止垃圾回收器重复清理
                self._is_cleanup_done = True
                self.driver = None
                self.wait = None

    def force_quit_driver(self) -> None:
        """强制关闭浏览器驱动（用于异常情况）"""
        if self.driver and not self._is_cleanup_done:
            try:
                import os
                import signal

                # 尝试获取Chrome进程ID并强制结束
                try:
                    if hasattr(self.driver, "_driver") and hasattr(
                        self.driver._driver, "service"
                    ):
                        service = self.driver._driver.service
                        if hasattr(service, "process"):
                            process = service.process
                            if process and process.poll() is None:
                                process.terminate()
                                process.wait(timeout=3)
                except Exception:
                    pass

                # 正常退出
                self.driver.quit()
                self.logger.info("浏览器已强制关闭")
            except Exception as e:
                self.logger.warning(f"强制关闭浏览器失败: {e}")
            finally:
                self._is_cleanup_done = True
                self.driver = None
                self.wait = None

    def is_driver_alive(self) -> bool:
        """检查驱动是否仍然活跃"""
        if not self.driver:
            return False

        try:
            # 尝试获取当前URL来检查驱动是否仍然活跃
            self.driver.current_url
            return True
        except Exception:
            return False
