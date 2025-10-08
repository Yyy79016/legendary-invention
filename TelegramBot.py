# —— 通用工具函数 —— #
# ==============================================
# 单文件全自动依赖处理 + 赛博朋克风格彩色日志（最终优化版）
# ==============================================

# ---------------------------- 基础导入（核心依赖检测前的必要导入） ----------------------------
import sys
import subprocess
import importlib
import os
import time
import shutil
import site
import pkg_resources
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime


# ---------------------------- 日志配置基础函数（无第三方依赖） ----------------------------
def setup_logger():
    """初始化日志系统，确保只添加一次处理器，防止重复输出"""
    logger = logging.getLogger("tg_bot")
    logger.setLevel(logging.INFO)  # 默认日志级别：INFO
    logger.propagate = False  # 禁止日志向上传播（避免重复输出）

    if logger.handlers:
        return logger

    # 初始使用默认格式化器（无颜色），后续安装colorama后替换
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

    return logger

# 初始化全局日志对象（基础版，后续会补充彩色配置）
logger = setup_logger()


# ---------------------------- 临时文件清理函数 ----------------------------
def _cleanup_temp_files():
    """清理可能生成的临时文件和目录"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 检查并删除名为"1.23.0"的文件或目录
    target = os.path.join(current_dir, "1.23.0")
    if os.path.exists(target):
        try:
            if os.path.isfile(target) or os.path.islink(target):
                os.unlink(target)
                logger.debug(f"已删除临时文件: {target}")
            elif os.path.isdir(target):
                shutil.rmtree(target)
                logger.debug(f"已删除临时目录: {target}")
        except Exception as e:
            logger.warning(f"清理临时文件时出错: {str(e)}")


# ---------------------------- 环境路径处理函数 ----------------------------
def _force_standard_paths():
    """强制添加所有标准Python路径，确保site-packages被正确识别"""
    python_exe = os.path.abspath(sys.executable)
    python_dir = os.path.dirname(python_exe)
    
    standard_paths = [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(python_dir, "Lib"),
        os.path.join(python_dir, "Lib", "site-packages"),
        site.getusersitepackages(),
        os.path.join(python_dir, "DLLs"),
        os.path.join(python_dir, "lib", "site-packages"),
        os.path.join(os.path.expanduser("~"), ".local", "lib", "python3.11", "site-packages")
    ]
    
    for path in standard_paths:
        if path and os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.debug(f"添加依赖路径: {path}")
    
    return python_exe


def _force_correct_python_env() -> str:
    """获取当前Python路径并确保路径正确"""
    python_exe = _force_standard_paths()
    
    try:
        version = sys.version_info
        if version < (3, 8):
            logger.error(f"不支持Python{version.major}.{version.minor}，请安装Python3.8+")
            sys.exit(1)
    except:
        logger.error("无法检测Python版本，请手动安装Python3.8+")
        sys.exit(1)
    
    return f'"{python_exe}"'


# ---------------------------- 依赖检测与安装函数 ----------------------------
def _is_package_installed(pkg_name, required_version):
    """
    优化依赖检测逻辑：
    1. 支持PyMuPDF与fitz的关联检测（安装PyMuPDF即视为fitz已安装）
    2. 版本兼容检查（支持>=模糊匹配，如PyMuPDF>=1.23.0）
    """
    pkg_mapping = {
        "google-auth-oauthlib": "google.auth.oauthlib",
        "protobuf": "google.protobuf",
        "PyMuPDF": "fitz",  # 关键映射：安装PyMuPDF = 可用fitz模块
        "opencv-python": "cv2",
        "google-api-python-client": "googleapiclient",
        "psutil": "psutil"
    }
    
    check_names = [pkg_name]
    if pkg_name in pkg_mapping:
        check_names.append(pkg_mapping[pkg_name])
    if pkg_name == "fitz":
        check_names.append("PyMuPDF")

    # 方法1：pkg_resources版本检测（支持>=模糊匹配）
    try:
        if required_version.startswith(">="):
            required_min_ver = required_version[2:].strip()
            installed_version = pkg_resources.get_distribution(pkg_name).version
            if pkg_resources.parse_version(installed_version) >= pkg_resources.parse_version(required_min_ver):
                logger.debug(f"{pkg_name} 已安装（需求: {required_version}，实际: {installed_version}）")
                return True
        else:
            installed_version = pkg_resources.get_distribution(pkg_name).version
            if installed_version == required_version:
                logger.debug(f"{pkg_name} 已安装（需求: {required_version}，实际: {installed_version}）")
                return True
    except pkg_resources.DistributionNotFound:
        pass
    except Exception as e:
        logger.warning(f"检查{pkg_name}版本时出错：{str(e)}")

    # 方法2：文件系统检测（检查是否存在包文件）
    for name in check_names:
        name_path = name.replace(".", os.sep)
        for path in sys.path:
            if (os.path.exists(os.path.join(path, f"{name}.py")) or
                os.path.exists(os.path.join(path, f"{name}.pyd")) or
                os.path.exists(os.path.join(path, name_path)) or
                os.path.exists(os.path.join(path, name_path, "__init__.py"))):
                logger.debug(f"在路径 {path} 中找到 {name} 的安装文件")
                return True

    # 方法3：导入验证（直接尝试导入模块，最可靠）
    for name in check_names:
        try:
            if name in sys.modules:
                del sys.modules[name]
            importlib.import_module(name)
            logger.debug(f"成功导入 {name}，确认已安装")
            return True
        except ImportError:
            continue
        except Exception as e:
            logger.warning(f"导入{name}时出错（但视为已安装）：{str(e)}")
            return True

    logger.debug(f"{pkg_name} 未安装或无法检测到")
    return False


def _install_deps_step_by_step(missing_deps: list):
    """分步安装缺失依赖（日志优化：彻底解决换行和过长问题）"""
    if not missing_deps:
        return True
    
    python_cmd = _force_correct_python_env()
    pip_cmd = f"{python_cmd} -m pip"
    mirror_config = "-i https://pypi.doubanio.com/simple/ -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.doubanio.com --trusted-host pypi.tuna.tsinghua.edu.cn"
    
    logger.info(f"开始安装缺失依赖（共{len(missing_deps)}个）")
    
    failed = []
    for idx, dep in enumerate(missing_deps, 1):
        # 分离包名和版本
        if ">=" in dep:
            pkg_name = dep.split(">=")[0].strip()
            install_dep = dep
        else:
            pkg_name = dep.split("==")[0].strip()
            install_dep = dep

        logger.info(f"--- 第{idx}/{len(missing_deps)}个：{dep} ---")
        no_deps = "--no-deps" if pkg_name in ["google-auth-oauthlib", "protobuf"] else ""
        install_cmd = f"{pip_cmd} install --upgrade {mirror_config} {no_deps} {install_dep} --timeout 300 --no-cache-dir --no-warn-script-location"
        
        try:
            process = subprocess.Popen(
                install_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8"
            )
            
            # 日志精简逻辑
            en_to_cn = {
                "Collecting": "📥 正在获取",
                "Downloading": "📥 正在下载",
                "Installing collected packages": "🔧 正在安装",
                "Successfully installed": "✅ 安装成功",
                "Requirement already satisfied": "✅ 已存在依赖"
            }
            download_size = ""
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    if any(key in line for key in ["Looking in indexes", "[notice]", "https://", "http://", "---", "from", "in"]):
                        continue
                    if "Downloading" in line and "(" in line and ")" in line:
                        download_size = f"（{line.split('(')[-1].split(')')[0]}）"
                        continue
                    for en_key, cn_val in en_to_cn.items():
                        if en_key in line:
                            if en_key == "Downloading":
                                logger.info(f"{cn_val} {pkg_name} {download_size}")
                            else:
                                if en_key == "Requirement already satisfied":
                                    dep_path = line.split(":")[-1].strip().split("==")[0]
                                    dep_name = dep_path.split('/')[-1].split('\\')[-1]
                                    logger.info(f"{cn_val}：{dep_name}")
                                elif en_key == "Successfully installed":
                                    dep_list = line.replace(en_key, "").strip()
                                    logger.info(f"{cn_val}：{dep_list}")
                                else:
                                    processed_line = line.replace(en_key, "").strip()
                                    processed_line = processed_line.split('/')[-1].split('\\')[-1]
                                    logger.info(f"{cn_val}：{processed_line}")
                            break
            
            if process.poll() == 0:
                logger.info(f"✅ 依赖安装完成：{dep}")
                _cleanup_temp_files()
                time.sleep(1)
            else:
                raise Exception(f"安装命令返回错误码：{process.poll()}")
        
        except Exception as e:
            logger.error(f"首次安装失败：{str(e)[:50]}")
            logger.info(f"🔄 重试安装：{dep}")
            time.sleep(3)
            try:
                subprocess.run(install_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                logger.info(f"✅ 重试成功：{dep}")
                _cleanup_temp_files()
            except:
                logger.error(f"❌ 重试失败：{dep}")
                failed.append(dep)
    
    _cleanup_temp_files()
    
    if failed:
        logger.error(f"以下依赖安装失败：{', '.join(failed)}")
        manual_cmd = f"{pip_cmd} install --upgrade {mirror_config} {' '.join(failed)}"
        logger.info(f"💡 手动安装命令：{manual_cmd}")
        return True
    
    return True


def _check_and_fix_deps():
    """检测并修复所有依赖（解决日志过长和换行问题）"""
    # 第三方依赖列表（仅包含需要通过pip安装的库，标准库无需列出）
    REQUIRED_DEPS = [
        "aiolimiter==1.2.1",
        "aiosqlite==0.21.0",
        "APScheduler==3.6.3",
        "colorama==0.4.6",
        "PyMuPDF>=1.23.0",  # 对应fitz模块
        "google-api-python-client==2.176.0",
        "google-auth-oauthlib==1.2.2",
        "opencv-python==4.11.0.86",  # 对应cv2模块
        "protobuf==6.32.0",
        "pydrive==1.3.1",
        "pyotp==2.9.0",
        "pytz==2025.2",
        "Telethon==1.39.0",
        "requests==2.32.3",
        "psutil==5.9.8"
    ]
    
    _force_standard_paths()
    
    # 环境检测日志输出
    logger.info("="*40)
    logger.info("      🔍 检测脚本运行环境（精简版）")
    logger.info("="*40)
    logger.info(f"Python路径：{os.path.abspath(sys.executable)}")
    logger.info(f"Python版本：{sys.version.split()[0]}     有效依赖路径（前3个）：")
    for i, path in enumerate(sys.path[:3]):
        logger.info(f"   {i+1}. {path}")
    
    # 检测已安装/缺失依赖
    installed = []
    missing = []
    for dep in REQUIRED_DEPS:
        if ">=" in dep:
            pkg_name = dep.split(">=")[0].strip()
            pkg_version = ">=" + dep.split(">=")[1].strip()
        else:
            pkg_name = dep.split("==")[0].strip()
            pkg_version = dep.split("==")[1].strip()
        
        if _is_package_installed(pkg_name, pkg_version):
            installed.append(dep)
        else:
            missing.append(dep)
    
    # 显示依赖检测结果
    if installed:
        logger.info(f"✅ 已安装依赖（共{len(installed)}个）：")
        for dep in installed:
            logger.info(f"   {dep}")
    
    if not missing:
        logger.info("\n✅ 所有依赖已就绪，启动脚本...")
        logger.info("="*40 + "\n")
        return True
    
    if missing:
        logger.info(f"❌ 缺失依赖（共{len(missing)}个）：")
        for dep in missing:
            logger.info(f"   {dep}")
    
    logger.info("✅ 开始自动安装缺失依赖...")
    return _install_deps_step_by_step(missing)


# ---------------------------- 执行环境检测与修复 ----------------------------
try:
    # 先清理可能存在的临时文件
    _cleanup_temp_files()
    _check_and_fix_deps()
    
    # 验证核心模块加载
    logger.info("✅ 脚本启动成功！所有依赖已正常加载（包括fitz模块）")
    try:
        import fitz
        logger.info(f"✅ fitz模块加载成功（PyMuPDF版本：{fitz.VersionFitz}）")
    except ImportError:
        logger.error("❌ fitz模块加载失败（请检查PyMuPDF安装）")

except Exception as e:
    logger.error(f"\n环境检测失败：{str(e)[:80]}")
    logger.warning("请确保：1. 已安装Python3.8+ 2. 网络正常 3. 有管理员权限")
finally:
    # 脚本结束时再次清理临时文件
    _cleanup_temp_files()


# ==============================================
# 模块导入（按类型分组，去重优化）
# ==============================================

# ---------------------------- 启动计时与日志 ----------------------------
_t0 = time.perf_counter()
logger.info("✅ 脚本启动，正在加载依赖…")


# ---------------------------- 标准库（Python自带，无需安装） ----------------------------
import os
import math
import uuid
import random
import hashlib
import tempfile
import json
import pickle
import ctypes
import shutil  # 用于清理文件
import re 
import asyncio
import imaplib  # 邮件协议处理
import functools
import urllib.parse
import psutil  # 系统资源监控
import threading  # 多线程支持
from typing import List, Tuple, Dict, Any, Optional  # 类型注解
from time import monotonic
from email import policy
import unicodedata
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from collections import defaultdict, deque
import base64  # 编码处理
import sqlite3  # 数据库支持
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path  # 路径处理
from imapclient import imap_utf7  # 邮件编码处理
from email.parser import BytesParser  # 邮件解析
from email import policy as email_policy  # 邮件解析策略


# ---------------------------- 第三方库（需通过pip安装，已在REQUIRED_DEPS中声明） ----------------------------
# Google相关服务
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow

# 其他第三方库
import pyotp  # 验证码生成
import aiosqlite  # 异步SQLite
import cv2  # 图像处理
import pytz  # 时区处理
from aiolimiter import AsyncLimiter  # 异步限流
from colorama import Fore, Back, init  # 终端彩色输出
from pydrive.auth import GoogleAuth  # Google Drive认证
from pydrive.drive import GoogleDrive  # Google Drive操作
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # 异步定时任务


# ---------------------------- 懒加载体积较大的第三方库 ----------------------------
class _LazyModule:
    def __init__(self, name):
        self._name = name
        self._mod = None

    def __getattr__(self, item):
        if self._mod is None:  # 第一次真正导入
            start = time.perf_counter()
            import importlib
            # 暂时从sys.modules移除，避免递归
            placeholder = sys.modules.get(self._name)
            if placeholder is self:
                del sys.modules[self._name]
            try:
                self._mod = importlib.import_module(self._name)
            finally:
                # 确保模块成功加载后放回
                sys.modules[self._name] = self._mod
            logger.info("⏱ 延迟加载 %s，用时 %.2f s",
                        self._name, time.perf_counter() - start)
        return getattr(self._mod, item)

# 懒加载fitz（PyMuPDF），减少启动时间
sys.modules["fitz"] = _LazyModule("fitz")
import fitz  # 实际使用时才会真正导入


# ---------------------------- Telegram 相关（Telethon库） ----------------------------
from telethon import TelegramClient, events, errors, utils
from telethon.events import NewMessage
from telethon.tl import types, functions
from telethon.tl.types import (
    InputPeerUser, InputPeerChannel, ChatBannedRights,
    ChannelParticipantsSearch, InputPeerChat,
    DocumentAttributeImageSize, ChatAdminRights,
    Channel, Chat, User
)
from telethon.tl.functions.channels import (
    InviteToChannelRequest, EditBannedRequest,
    CreateChannelRequest, EditAdminRequest,
    LeaveChannelRequest, DeleteChannelRequest
)
from telethon.tl.functions.messages import (
    ExportChatInviteRequest, AddChatUserRequest
)
from telethon.utils import get_peer_id, get_display_name
from telethon.errors import (
    ChatAdminRequiredError, UsernameNotOccupiedError,
    UserIdInvalidError, UserNotMutualContactError,
    RightForbiddenError, UserAlreadyParticipantError,
    ChatIdInvalidError, PeerIdInvalidError, UserNotParticipantError,
    RPCError, ChatWriteForbiddenError, FloodWaitError,
    SessionPasswordNeededError, UserPrivacyRestrictedError,
    ChannelPrivateError
)


# ==============================================
# 日志与异常处理配置（依赖加载完成后）
# ==============================================

# 初始化colorama（终端彩色输出）
init(autoreset=True)

class ColorFormatter(logging.Formatter):
    """彩色日志格式化器"""
    def format(self, record):
        color = Fore.CYAN
        if record.levelno == logging.DEBUG:
            color = Fore.MAGENTA
        elif record.levelno == logging.INFO:
            color = Fore.CYAN
        elif record.levelno == logging.WARNING:
            color = Fore.LIGHTYELLOW_EX
        elif record.levelno == logging.ERROR:
            color = Fore.LIGHTRED_EX
        elif record.levelno == logging.CRITICAL:
            color = Fore.BLACK + Back.MAGENTA
        return color + super().format(record)

# 优化日志配置（替换基础版配置）
logger = logging.getLogger("tg_bot")
logger.setLevel(logging.INFO)
logger.propagate = False

# 清除已有处理器，避免重复输出
for h in logger.handlers[:]:
    logger.removeHandler(h)

# ---------------------------- 核心修改：只保留当天日志（无多文件） ----------------------------
# 使用普通FileHandler，但添加每日清空机制
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

# 添加每日凌晨清空日志的定时任务
async def clear_log_file():
    """清空日志文件内容（保留文件本身）"""
    try:
        # 临时移除文件处理器，避免清空时写入冲突
        logger.removeHandler(file_handler)
        # 清空文件（截断为0字节）
        with open("bot.log", "w", encoding="utf-8") as f:
            f.truncate()
        # 重新添加处理器
        logger.addHandler(file_handler)
        logger.info("✅ 日志文件已清空（保留当天记录）")
    except Exception as e:
        logger.error(f"清空日志失败：{str(e)}")

# 初始化定时任务调度器
scheduler = AsyncIOScheduler()
# 每天凌晨0点执行清空操作（指定pytz时区）
scheduler.add_job(
    clear_log_file,
    trigger="cron",
    hour=0,
    minute=0,
    timezone=pytz.timezone('Asia/Shanghai')  # 可替换为你的时区，如pytz.utc
)
scheduler.start()

# ---------------------------- 控制台输出配置 ----------------------------
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# 调整telethon日志级别（减少冗余输出）
logging.getLogger('telethon').setLevel(logging.WARNING)


# ---------------------------- 全局异常钩子 ----------------------------
import traceback
def global_exception_hook(exctype, value, tb):
    """全局异常捕获，统一处理未捕获的异常"""
    print("\n======[全局异常捕获]======")
    print("异常类型:", exctype)
    print("异常内容:", value)
    traceback.print_tb(tb)
    input("程序异常，按任意键关闭窗口...")

sys.excepthook = global_exception_hook


# ---------------------------- 资源监控线程 ----------------------------
def monitor_resource():
    """定时监控系统资源使用情况"""
    while True:
        process = psutil.Process()
        mem = process.memory_info().rss / 1024 / 1024  # MB
        cpu = process.cpu_percent(interval=1)
        disk = psutil.disk_usage('.').percent
        logger.info(f"[资源监控] 内存:{mem:.2f}MB, CPU:{cpu}%, 磁盘:{disk}%")
        time.sleep(600)  # 每10分钟记录一次

# 启动资源监控线程（后台运行）
threading.Thread(target=monitor_resource, daemon=True).start()

# ---------------------------- 初始化（保留原逻辑） ----------------------------
# 获取当前时间并指定 UTC 时区
current_time = datetime.now(timezone(timedelta(hours=8)))  # 设置为 UTC+8 时区
PAT = {
    "payer_name"   : re.compile(r"付款方[^\n]*?账户名[:：]\s*([^\n]+)"),
    "payee_name"   : re.compile(r"收款方[^\n]*?账户名[:：]\s*([^\n]+)"),
    "amt_num"      : re.compile(r"小写[:：]?\s*([0-9]+\.[0-9]{2})"),
    "amt_cn"       : re.compile(r"大写[:：]?\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元[整角分]*)"),
    "pay_time"     : re.compile(r"(?:支付|付款|交易)时间[:：]?\s*([\d\-年月日 :/]+)"),
    "flow_no"      : re.compile(r"(?:支付宝|交易)?流水号[:：]?\s*([^\n]+)"),
}


# ---------------------------- 工具函数：同步函数异步执行（线程池调度） ----------------------------
async def run_blocking(func, *args, **kw):
    """把耗时的同步函数丢到线程池，避免阻塞 Telegram 事件循环"""
    loop = asyncio.get_running_loop()
    part = functools.partial(func, *args, **kw)
    return await loop.run_in_executor(None, part)


# ---------------------------- 全局配置：可调参数（环境变量优先） ----------------------------
# 消息发送速率限制：每秒最多发 10 条（支持通过环境变量覆盖）
MAX_MSGS_PER_SEC = int(os.getenv("MAX_MSGS_PER_SEC", 10))
# 速率限制窗口：1 秒（支持通过环境变量覆盖）
LIMIT_WINDOW_SEC = int(os.getenv("LIMIT_WINDOW_SEC", 1))
# 线程池大小：24（默认值 ≈ 32 线程 × 0.75，支持通过环境变量覆盖）
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 24))
# 机器人ID：登录成功后自动填充（初始为 None）
BOT_USER_ID: int | None = None


# ---------------------------- 全局状态变量：运行时数据记录 ----------------------------
# 脚本启动时间（初始化为0，脚本启动时更新）
start_time = 0
# 机器人加入各群组的时间映射（key：群组ID，value：加入时间戳）
group_join_times = {}
# 关键词删除操作锁：标记是否正在执行关键词删除（避免并发冲突）
is_deleting_keyword = False


# ---------------------------- 工具函数：资源路径处理（兼容打包/本地运行） ----------------------------
def resource_path(rel_path: str) -> str:
    """
    获取打包后或本地运行时的资源文件绝对路径。
    PyInstaller 打包时会把资源解压到 sys._MEIPASS，本地运行时使用脚本所在目录。
    rel_path: 相对于脚本的资源文件相对路径（如 "credentials.json"、"token.json"）
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, rel_path)
    

# ---------------------------- 环境配置：系统兼容性与日志开关 ----------------------------
# 日志显示开关：True 显示环境相关日志，False 隐藏（用于控制冗余日志）
SHOW_ENV_LOGS = False

# Windows 系统兼容性处理（设置控制台编码为 UTF-8，避免中文乱码）
if os.name == 'nt':
    os.system('chcp 65001 >nul 2>&1')  # 执行编码设置命令，隐藏输出（>nul 2>&1）
    if SHOW_ENV_LOGS:
        logger.info("Windows 环境，已自动设置控制台编码为 UTF-8")


# ---------------------------- 工具函数：安全日志输出（避免崩溃） ----------------------------
def safe_print(msg: str):
    """安全输出日志：捕获日志输出时的异常，避免因日志问题导致程序崩溃"""
    try:
        logger.info(msg)
    except Exception as e:
        # 日志输出失败时，降级使用 print 输出（附带错误信息）
        print(f"日志输出失败: {str(e)} | 原日志内容: {msg}")


# ---------------------------- 数据库配置：读取配置文件（默认值兜底） ----------------------------
# 配置文件路径（config.json，与脚本同目录）
CONFIG_PATH = Path("config.json")

# 读取配置文件：存在则加载，不存在则使用默认配置
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    # 默认配置（数据库路径、并发数、速率限制、日志文件）
    config = {
        "db_path": "database.db",        # 数据库文件路径
        "max_concurrency": 10,           # 最大并发数
        "rate_limit": 5,                 # 额外速率限制（可根据业务扩展）
        "log_file": "bot.log"            # 日志文件路径（若后续添加文件日志可使用）
    }


#---------------------------- 数据库操作：群组 ID 查询（按类型筛选） ----------------------------
async def get_group_ids_by_type(group_type):
    db = await DB.get_conn()
    async with db.execute(
        "SELECT chat_id FROM group_config WHERE group_type = ?", (group_type,)
    ) as cursor:
        return [row[0] for row in await cursor.fetchall()]

#---------------------------- 数据库操作：附文匹配（按文本关键词） ----------------------------
async def get_appendix_for_text(text):
    db = await DB.get_conn()
    async with db.execute("SELECT keyword, content FROM appendices") as cursor:
        appendices = await cursor.fetchall()
        for keyword, content in appendices:
            if keyword in text:
                return content
    return ""  # 如果没有匹配的附文，返回空字符串

# ---------------------------- 数据库核心工具类（封装通用操作） ----------------------------
class DBHelper:
    def __init__(self, db_pool, logger: logging.Logger | None = None):
        self.db_pool = db_pool
        self.logger = logger or logging.getLogger("tg_bot")

    async def execute(
        self,
        sql: str,
        params: Tuple[Any, ...] | None = None,
        *,
        commit: bool = True,
        retries: int = 3,
    ):
        """执行写操作；失败自动重试。返回 cursor。"""
        params = params or ()
        for attempt in range(retries):
            try:
                conn = await self.db_pool.get_connection()
                async with conn.execute(sql, params) as cursor:
                    if commit:
                        await conn.commit()
                    await self.db_pool.release_connection(conn)
                    return cursor
            except Exception as e:  # noqa: BLE001
                self.logger.warning(
                    "[DBHelper] 执行 SQL 出错：%s，尝试第 %s/%s", e, attempt + 1, retries
                )
                await asyncio.sleep(1)
                if attempt == retries - 1:
                    raise

    async def fetch_all(
        self, sql: str, params: Tuple[Any, ...] | None = None
    ) -> List[Tuple]:
        """执行查询并返回所有结果。"""
        conn = await self.db_pool.get_connection()
        try:
            async with conn.execute(sql, params or ()) as cursor:
                rows = await cursor.fetchall()
                return rows
        finally:
            await self.db_pool.release_connection(conn)

    async def transaction(self, operations: List[Tuple[str, Tuple[Any, ...]]]):
        """
        一次性执行多条 SQL，全部成功才提交。
        operations 形如：[(sql1, params1), (sql2, params2), ...]
        """
        conn = await self.db_pool.get_connection()
        try:
            await conn.execute("BEGIN")
            for sql, params in operations:
                await conn.execute(sql, params)
            await conn.commit()
        except Exception as e:  # noqa: BLE001
            self.logger.error("[DBHelper] 事务执行失败：%s", e)
            await conn.rollback()
            raise
        finally:
            await self.db_pool.release_connection(conn)


# ---------------------------- 管理员数据访问对象（Admin 表操作） ----------------------------
class AdminDAO:
    def __init__(self, db: DBHelper):
        self.db = db

    async def add_admin(self, user_id: int, username: str):
        await self.db.execute(
            "INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )

    async def remove_admin(self, user_id: int):
        await self.db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))

    async def is_admin_by_id(self, user_id: int) -> bool:
        rows = await self.db.fetch_all(
            "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
        )
        return bool(rows)

    async def get_all_admins(self):
        return await self.db.fetch_all("SELECT username FROM admins")


# ---------------------------- 群组绑定数据访问对象（bindings 表操作） ----------------------------
class GroupDAO:
    def __init__(self, db: DBHelper):
        self.db = db

    async def bind_group(self, from_id: int, to_id: int):
        await self.db.execute(
            "INSERT OR IGNORE INTO bindings (from_id, to_id) VALUES (?, ?)",
            (from_id, to_id),
        )

    async def unbind_group(self, from_id: int, to_id: int):
        await self.db.execute(
            "DELETE FROM bindings WHERE from_id = ? AND to_id = ?",
            (from_id, to_id),
        )

    async def get_bound_groups(self, from_id: int) -> List[int]:
        rows = await self.db.fetch_all(
            "SELECT to_id FROM bindings WHERE from_id = ?", (from_id,)
        )
        return [row[0] for row in rows]

    async def get_mutual_bindings(self, chat_id: int) -> List[int]:
        sql = """
        SELECT b1.to_id
        FROM bindings AS b1
        JOIN bindings AS b2
          ON b1.to_id = b2.from_id
         AND b2.to_id = b1.from_id
        WHERE b1.from_id = ?
        """
        rows = await self.db.fetch_all(sql, (chat_id,))
        return [row[0] for row in rows]

# ---------------------------- 并发控制（信号量限制） ----------------------------
# 控制并发执行的信号量
semaphore = asyncio.BoundedSemaphore(config.get("max_concurrency", 10))

async def limited_run(coro_func, *args, **kwargs):
    async with semaphore:
        return await coro_func(*args, **kwargs)

# ---------------------------- 数据库连接池与基础操作 ----------------------------
# 数据库连接池实现
class DatabasePool:
    def __init__(self, db_file: str, pool_size: int = 5):
        self.db_file = db_file
        self.pool_size = pool_size
        self.pool: list[aiosqlite.Connection] = []
        self.lock = asyncio.Lock()

    async def _new_conn(self) -> aiosqlite.Connection:
        """创建新连接并切 WAL"""
        conn = await aiosqlite.connect(self.db_file)
        await conn.execute("PRAGMA journal_mode=WAL;")        # ★ 关键
        # 可选：写性能再提升
        # await conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    async def get_connection(self) -> aiosqlite.Connection:
        async with self.lock:
            if self.pool:
                return self.pool.pop()
            return await self._new_conn()

    async def release_connection(self, conn: aiosqlite.Connection):
        async with self.lock:
            if len(self.pool) < self.pool_size:
                self.pool.append(conn)
            else:
                await conn.close()

db_pool = DatabasePool("database.db", pool_size=5)   # ← 若用其他文件名改这里

# 通用查询工具函数
async def fetch_all(query: str, *params) -> List[aiosqlite.Row]:
    conn = await db_pool.get_connection()
    async with conn.execute(query, params) as cur:
        rows = await cur.fetchall()
    await db_pool.release_connection(conn)
    return rows

async def execute_write(query: str, *params) -> None:
    """写操作，自动重试 3 次避免瞬时锁"""
    conn = await db_pool.get_connection()
    for _ in range(3):
        try:
            await conn.execute(query, params)
            await conn.commit()
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                await asyncio.sleep(0.1)       # 100 ms 退避
                continue
            raise
    await db_pool.release_connection(conn)

# 保持旧名兼容
execute_query = fetch_all   # type: ignore

# ---------------------------- Google 验证密钥数据访问（GASecretDAO） ----------------------------
class GASecretDAO:
    """ga_secrets CRUD + Rename（Name/Secret 都去重）"""

    @staticmethod
    async def list_names() -> List[str]:
        rows = await fetch_all("SELECT name FROM ga_secrets")
        return [r[0] for r in rows]

    @staticmethod
    async def get_secret(name: str) -> str | None:
        rows = await fetch_all(
            "SELECT secret FROM ga_secrets WHERE name = ?", name.lower()
        )
        return rows[0][0] if rows else None

    @staticmethod
    async def add_secret(name: str, secret: str) -> bool:
        """
        若 name 或 secret 任何一个已存在，则返回 False
        否则插入并返回 True
        """
        name = re.sub(r"\s+", "", name).lower()

        # 查重
        rows = await fetch_all(
            "SELECT 1 FROM ga_secrets WHERE name = ? OR secret = ?", name, secret
        )
        if rows:
            return False

        await execute_write(
            "INSERT INTO ga_secrets (name, secret) VALUES (?, ?)",
            name, secret,
        )
        return True

    @staticmethod
    async def delete_secret(name: str) -> bool:
        await execute_write("DELETE FROM ga_secrets WHERE name = ?", name.lower())
        return True

    # -------- 新增：重命名 --------
    @staticmethod
    async def rename_secret(old_name: str, new_name: str) -> Tuple[bool, str]:
        old_name = re.sub(r"\s+", "", old_name).lower()
        new_name = re.sub(r"\s+", "", new_name).lower()

        # 旧名不存在
        if not await GASecretDAO.get_secret(old_name):
            return False, "❌ 未找到旧名称"

        # 新名已占用
        if await GASecretDAO.get_secret(new_name):
            return False, "⚠️ 新名称已存在，请先删除或换一个"

        await execute_write(
            "UPDATE ga_secrets SET name = ? WHERE name = ?",
            new_name, old_name
        )
        return True, f"✅ 已将 «{old_name}» 改名为 «{new_name}»"

    # —— 新增：一次性取出全部 (name, secret) —— #
    @staticmethod
    async def list_all() -> List[Tuple[str, str]]:
        """返回 [(name, secret), …]"""
        return [
            (row[0], row[1])
            for row in await fetch_all("SELECT name, secret FROM ga_secrets")
        ]

# ---------------------------- Telegram API 限流控制 ----------------------------
# 2. Request Limiting for Telegram API
limiter = AsyncLimiter(MAX_MSGS_PER_SEC, LIMIT_WINDOW_SEC)


async def send_message_with_limit(client, chat_id, message):
    async with limiter:
        await client.send_message(chat_id, message)

# ---------------------------- CPU 密集型任务处理（线程池） ----------------------------
# 3. CPU-Intensive Tasks → ThreadPool
ThreadPoolExecutor(max_workers=MAX_WORKERS)

def cpu_intensive_task(data):
    return sum(x * x for x in data)  # 示例计算

async def handle_cpu_task(data):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, cpu_intensive_task, data)

# ---------------------------- 网络请求重试工具 ----------------------------
# 4. Retry helper --------------------------------------------------
async def retry_request(request_func, retries=5, delay=2):
    for attempt in range(retries):
        try:
            return await request_func()
        except Exception as e:
            if attempt == retries - 1:
                raise e
            await asyncio.sleep(delay + random.uniform(0, 2))

# ---------------------------- 异步临界区锁 ----------------------------
# 5. Async lock for critical section ------------------------------
lock = asyncio.Lock()

async def critical_section(task_id):
    async with lock:
        logging.info(f"任务 {task_id} 正在执行临界区操作")
        await asyncio.sleep(1)
        logging.info(f"任务 {task_id} 完成临界区操作")

# ---------------------------- 控制台输出辅助函数 ----------------------------
def print_task_operation(task_name, details):
    print(f"【任务操作】{task_name}: {details}", file=sys.stdout)

def print_admin_operation(admin_id, operation, target_id=None, details=""):
    print(f"【管理员操作】管理员 {admin_id} 执行 {operation}，目标: {target_id}，详情: {details}", file=sys.stdout)


# ---------------------------- 目录与缓存初始化 ----------------------------
# 确保 temp 临时目录存在
os.makedirs("temp", exist_ok=True)

# 全局缓存：记录最近处理过的 (群ID, order_id) 及对应时间
recent_payback_requests = {}
PAYBACK_DEDUPE_INTERVAL = 30  # 30 秒内重复忽略
_pdf_text_cache = {} 
# 缓存所有“代付”分组的群ID，启动时加载 & “设置代付”时维护
payback_groups = set()


# ---------------------------- Telegram 客户端配置 ----------------------------
# Telegram API 配置（请勿修改）
api_id = 26010560
api_hash = "6b9c5cf31915896ea54656cd04c7fbbb"

# 模拟为 Windows Telegram Desktop 登录
client = TelegramClient(
    session="session",  
    api_id=api_id,
    api_hash=api_hash,
    device_model="PC 64bit",
    system_version="Windows 10.0.22621",
    app_version="4.15.0 x64",
    lang_code="zh",
    system_lang_code="zh-cn"
)


# ---------------------------- 消息日志记录功能 ----------------------------
# 定义接收指令的日志记录功能
@client.on(events.NewMessage(incoming=True))
async def log_received_message(event):
    try:
        # 跳过脚本启动之前的消息
        message_time = int(event.date.timestamp())
        if message_time < start_time:
            logger.debug(f"跳过脚本启动之前的消息（消息时间：{message_time}, 启动时间：{start_time}）")
            return

        # 判断消息是否来自群组
        if event.is_group:
            group_id = event.chat_id  # 获取群组的 ID
            logger.info(f"收到指令：{event.raw_text} 来自群组 {group_id}")
        else:
            logger.info(f"收到指令：{event.raw_text} 来自私聊")

        # 回复消息
        if event.is_reply:  # 如果是对某条消息的回复
            reply = await event.get_reply_message()
            logger.info(f"回复了：{reply.text}")  # 记录回复的内容

        # 记录执行操作的内容（根据你的操作类型修改这里的判断条件）
        if event.raw_text.startswith("绑定群组"):
            logger.info("执行了绑定群组操作")
        elif event.raw_text.startswith("设置管理"):
            logger.info("执行了设置管理员操作")
        elif event.raw_text.startswith("添加管理员"):
            logger.info("执行了添加管理员操作")
        elif event.raw_text.startswith("删除管理员"):
            logger.info("执行了删除管理员操作")
        
    except Exception as e:
        logger.error(f"日志记录出错: {e}")


# ---------------------------- 全局配置变量 ----------------------------
DB_TIMEOUT = 30  # 数据库操作超时时间（秒）
DB_PATH = "database.db"  # 数据库文件存储路径
bot_info = None  # 机器人信息存储变量（预留，可用于存储机器人详细信息）
BOT_USER_ID: int | None = None  # 机器人用户ID（登录后初始化）
start_time = int(time.time())  # 脚本启动时间戳（用于过滤启动前的历史消息）


# ---------------------------- 数据库配置与连接池 ----------------------------
# 增强型全局数据库连接池，支持异步和多线程安全
class DB:
    _conn = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_conn(cls):
        async with cls._lock:
            if not cls._conn:
                cls._conn = await aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT)
                await cls._conn.execute("PRAGMA journal_mode=WAL")
                await cls._conn.execute("PRAGMA synchronous=NORMAL")
                await cls._conn.execute("PRAGMA busy_timeout=5000")  # 数据库繁忙时等待5秒
            return cls._conn

# ---------------------------- 线程池配置 ----------------------------
# 创建共享线程池执行器
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ---------------------------- 数据库表初始化 ----------------------------
async def init_all_tables():
    """初始化数据库表结构，包含性能优化配置及所有业务表创建"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 并发写入性能优化设置
            await db.execute("PRAGMA journal_mode=WAL;")  # 启用WAL模式，提升并发读写性能
            await db.execute("PRAGMA synchronous=NORMAL;")  # 平衡性能与安全性
            await db.execute("PRAGMA busy_timeout=5000;")  # 数据库繁忙时等待5秒

            # 基础业务表
            # 管理员表：存储管理员用户ID和用户名
            await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)")

            # 黑名单表：存储需过滤的关键词
            await db.execute("CREATE TABLE IF NOT EXISTS blacklist (word TEXT PRIMARY KEY)")

            # 附录表：存储关键词对应的补充内容
            await db.execute("CREATE TABLE IF NOT EXISTS appendices (keyword TEXT PRIMARY KEY, content TEXT)")

            # 群组配置表：存储群组ID和群组类型
            await db.execute("CREATE TABLE IF NOT EXISTS group_config (chat_id INTEGER PRIMARY KEY, group_type TEXT)")

            # 绑定关系表：存储转发绑定关系（去重处理）
            await db.execute("CREATE TABLE IF NOT EXISTS bindings (from_id INTEGER, to_id INTEGER, user_id INTEGER)")
            await db.execute("""
                DELETE FROM bindings
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM bindings GROUP BY from_id, to_id
                )
            """)  # 清理重复绑定关系
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bind_unique ON bindings(from_id, to_id)")

            # 提及用户表：存储群组ID及对应的多个逗号分隔用户
            await db.execute("CREATE TABLE IF NOT EXISTS mentions (group_id INTEGER, usernames TEXT)")
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique ON mentions(group_id)")

            # 员工信息表：存储用户ID、哈希值、用户名及更新时间
            await db.execute("""
                CREATE TABLE IF NOT EXISTS staff (
                    user_id INTEGER PRIMARY KEY,
                    access_hash BIGINT NOT NULL,
                    username TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 群组加入时间记录表：存储群组ID、机器人用户ID和加入时间
            await db.execute("""
                CREATE TABLE IF NOT EXISTS group_join_times (
                    chat_id INTEGER PRIMARY KEY,
                    bot_user_id INTEGER NOT NULL,
                    join_time INTEGER NOT NULL
                )
            """)

            # Google API相关表
            # 异步凭证表：存储凭证类型、客户端密钥、token及更新时间
            await db.execute("""
                CREATE TABLE IF NOT EXISTS google_api_credentials (
                    type TEXT PRIMARY KEY,
                    client_secret TEXT NOT NULL,
                    token TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 【新增】FastMail API 凭证表：存储FastMail的用户邮箱和App专用密钥
            await db.execute("""
                CREATE TABLE IF NOT EXISTS fastmail_api_credentials (
                    type TEXT PRIMARY KEY DEFAULT 'pay',  -- 固定为'pay'，仅存储代付凭证
                    user TEXT NOT NULL,                  -- FastMail邮箱账号
                    app_password TEXT NOT NULL,          -- FastMail App专用密钥
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)


            # 扩展功能表
            # 敏感配置存储表：存储配置名称和对应的敏感内容
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ga_secrets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    secret TEXT NOT NULL
                )
            """)
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ga_secrets_name ON ga_secrets(name)")

            # 群发失败次数记录表：存储群组ID和失败次数
            await db.execute("""
                CREATE TABLE IF NOT EXISTS group_failure_log (
                    group_id INTEGER PRIMARY KEY,
                    failure_count INTEGER DEFAULT 1
                )
            """)

            # 催单转发计数表：限制单日转发频率
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminder_forward_log (
                    original_msg_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    forward_count INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (original_msg_id, chat_id)
                )
            """)

            # 群组实体持久化表：存储序列化的群组信息
            await db.execute("""
                CREATE TABLE IF NOT EXISTS group_entities (
                    chat_id INTEGER PRIMARY KEY,
                    entity_data BLOB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 停止催单标记表：无需回复原始消息即可停止催单
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stopped_reminders (
                    chat_id BIGINT NOT NULL,
                    order_identifier TEXT NOT NULL,
                    stopped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, order_identifier)
                )
            """)

            # 消息记录表：支持精确停止催单
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sent_messages (
                    msg_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    raw_text TEXT,
                    order_identifier TEXT,
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sent_order ON sent_messages(order_identifier)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_sent_chat ON sent_messages(chat_id)")

            # 提交所有表结构更改
            await db.commit()
            logger.info("✅ 数据库初始化完成")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}", exc_info=True)
        raise


# ---------------------------- 管理员权限验证 ----------------------------
# 检查是否为管理员
async def is_admin(uid):
    try:
        admin_dao = AdminDAO(DBHelper(db_pool))
        return await admin_dao.is_admin_by_id(uid)
    except Exception as e:
        logger.error(f"检查管理员失败: {e}")
        return False

# 检查是否存在管理员
async def has_admins():
    try:
        admin_dao = AdminDAO(DBHelper(db_pool))
        admins = await admin_dao.get_all_admins()
        return len(admins) > 0
    except Exception as e:
        logger.error(f"检查是否存在管理员失败: {e}")
        return False


# ---------------------------- Telegram 客户端管理 ----------------------------
# 创建 Telegram 客户端实例
client = TelegramClient('session', api_id, api_hash)

# 登录并处理流程
async def connect_client():
    try:
        # 使用 start() 来自动处理手机号输入、验证码、2FA 等
        await client.start()

        me = await client.get_me()
        global BOT_USER_ID
        if BOT_USER_ID is None:          # ← 关键判断：只赋值一次
            BOT_USER_ID = me.id          # 初始化机器人 ID
            # 已移除机器人ID初始化的日志输出

        logger.info(f"✅ 登录成功：当前登录账号 - {me.first_name} (@{me.username})")
        return True

    except SessionPasswordNeededError:
        # 处理二次验证
        password = input("请输入 Telegram 二次验证密码: ")
        await client.sign_in(password=password)
        logger.info("二次验证通过")
        return True

    except Exception as e:
        logger.error(f"连接失败: {e}")
        return False


# ---------------------------- 管理员初始化命令 ----------------------------
# 首次运行设置管理员
@client.on(events.NewMessage(pattern="设置管理"))
async def set_first_admin(event):
    sender = await event.get_sender()
    user_id = sender.id
    username = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()

    if event.is_private:
        try:
            if not await has_admins():
                db = await DB.get_conn()
                await db.execute(
                    "INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                await db.commit()

                await event.reply("✅ 已将你设置为管理员")
                logger.info(f"用户 {username} (ID: {user_id}) 已设置为初始管理员")
            else:
                await event.reply("已有管理员，不能重复设置")
        except Exception as e:
            logger.error(f"设置管理员失败: {e}")
            await event.reply("❌ 设置管理员失败，请查看日志")



# ---------------------------- 管理员管理命令 ----------------------------

# 添加管理员
@client.on(events.NewMessage(pattern=r"^添加管理员(?:\s+@?(\w+))?$", incoming=True))
async def add_admin(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    reply = await event.get_reply_message()
    if reply:
        user = await reply.get_sender()
    else:
        username_input = event.pattern_match.group(1)
        if not username_input:
            return await event.reply("❌ 请引用用户消息或提供“@用户名”来添加管理员")
        user = await client.get_entity(username_input)

    user_id = user.id
    username = user.username

    # 拦截无用户名用户
    if not username:
        return await event.reply(
            "❌ 该用户未设置 Telegram 用户名，无法添加为管理员。\n"
            "请让对方前往 Telegram 设置页面添加用户名后再试。"
        )

    db = await DB.get_conn()
    async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
        if await cursor.fetchone():
            return await event.reply(f"⚠ 用户 @{username} 已经是管理员")

    await db.execute("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)", (user_id, username))
    await db.commit()

    logger.info(f"管理员 {event.sender_id} 添加了管理员 @{username} (ID: {user_id})")

    await event.reply(f"✅ 用户 `@{username}` 已成为管理员", parse_mode="markdown")


# 删除管理员
@client.on(events.NewMessage(pattern=r"^删除管理员(?:\s+@?(\w+))?$", incoming=True))
async def remove_admin(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    reply = await event.get_reply_message()
    if reply:
        user = await reply.get_sender()
    else:
        username_input = event.pattern_match.group(1)
        if not username_input:
            return await event.reply("❌ 请引用用户消息或提供“@用户名”来删除管理员")
        user = await client.get_entity(username_input)

    user_id = user.id
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()

    db = await DB.get_conn()
    async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
        if not await cursor.fetchone():
            return await event.reply(f"⚠ 用户 @{username} 不在管理员列表中")

    await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    await db.commit()

    logger.info(f"管理员 {event.sender_id} 删除了管理员 {username}")

    await event.reply(f"✅ 用户 `@{username}` 的管理员权限已移除", parse_mode="markdown")


# 查看管理员
@client.on(events.NewMessage(pattern="查看管理员", incoming=True))
async def view_admins(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    db = await DB.get_conn()
    async with db.execute("SELECT username FROM admins") as cursor:
        rows = await cursor.fetchall()
        if not rows:
            return await event.reply("当前没有管理员")

        # 所有人都有 username，直接展示
        admin_list = [f"@{row[0]}" for row in rows if row[0]]

        text = "👑 当前管理员列表：\n" + "\n".join(admin_list)
        await event.reply(text)

        logger.info(f"管理员 {event.sender_id} 查看了管理员列表")


# ---------------------------- 机器人客户端初始化 ----------------------------

async def initialize_bot():
    """初始化机器人客户端，完成登录并获取机器人信息"""
    global bot_info
    try:
        await client.start()
        bot_info = await client.get_me()
        logger.info(f"用户已登录: {bot_info.username or bot_info.first_name}")

        # 立即初始化 BOT_USER_ID，确保后续消息处理正常工作
        await get_bot_user_id()

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise


async def ensure_client_initialized():
    """
    确保客户端与机器人ID已正确初始化：
      • 首次初始化时记录并打印机器人ID
      • 断线后自动恢复客户端信息，不重复打印日志
    """
    global BOT_USER_ID

    # 情况A：BOT_USER_ID已初始化
    if BOT_USER_ID is not None:
        if getattr(client, "me", None) is None:          # 断线后客户端信息丢失
            client.me = await client.get_me()            # 恢复信息但不记录日志
        return client.me

    # 情况B：首次初始化客户端信息
    client.me = await client.get_me()
    BOT_USER_ID = client.me.id
    logger.info(f"机器人ID初始化: {BOT_USER_ID}")        # 仅首次打印日志
    return client.me


async def get_bot_user_id():
    """获取机器人用户ID（确保已初始化）"""
    await ensure_client_initialized()
    return BOT_USER_ID


# ---------------------------- 机器人入群事件处理 ----------------------------

async def handle_bot_join(event):
    """处理机器人加入群组的事件（包含去重逻辑）"""
    global bot_info

    # 1. 确保客户端与机器人ID已初始化
    await ensure_client_initialized()

    # 2. 缓存机器人信息（若未缓存）
    if bot_info is None:
        bot_info = client.me  # client.me已由ensure_client_initialized()初始化

    bot_user_id = BOT_USER_ID  # 此时全局ID必定已赋值
    if bot_user_id is None:
        logger.error("BOT_USER_ID 仍为 None，这不应该发生")
        return

    # 3. 验证是否为机器人自身入群事件
    if event.user_joined and event.user_id == bot_user_id:
        chat_id = event.chat_id
        current_time = int(time.time())

        if chat_id in group_join_times:  # 去重处理：跳过重复的入群事件
            logger.debug(f"跳过重复加入事件：群组 {chat_id}")
            return

        group_join_times[chat_id] = current_time  # 记录入群时间到内存
        # 异步保存入群时间到数据库（不阻塞主流程）
        asyncio.create_task(_save_group_join_time(chat_id, current_time))
        logger.info(f"机器人 {bot_user_id} 加入群组 {chat_id}，记录时间 {current_time}")
        

# ---------------------------- 群组绑定与分组管理命令 ----------------------------

# 绑定群组（默认未分组）
@client.on(events.NewMessage(pattern="绑定群组"))
async def bind_group(event):
    user_id = event.sender_id

    if not await is_admin(user_id):
        logger.warning(f"❌ 非管理员 {user_id} 尝试绑定群组")
        return

    if not event.is_group:
        return await event.reply("❌ 请在群组中发送该指令")

    # 跳过脚本启动之前的消息
    message_time = int(event.date.timestamp())
    if message_time < start_time:
        logger.debug(f"跳过脚本启动之前的消息（消息时间：{message_time}, 启动时间：{start_time}）")
        return

    logger.debug(f"处理绑定群组指令，群组ID: {event.chat_id}")

    # 检查该群组是否已经绑定
    db = await DB.get_conn()
    async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (event.chat_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            # 如果已经绑定，提示当前分组类型
            logger.info(f"[绑定] 该群组 [{event.chat_id:>14}] 已绑定为『{row[0]}』分组，已忽略重复绑定请求")
            return await event.reply(f"❌ 该群组已经绑定，当前分组为『{row[0]}』")
        else:
            # 如果没有绑定，进行绑定操作，默认未分组
            await db.execute(
                "INSERT INTO group_config (chat_id, group_type) VALUES (?, ?)",
                (event.chat_id, "未分组"),
            )
            await db.commit()
            logger.info(f"[绑定] 已绑定 [{event.chat_id:>14}] 群组为未分组，数据库更新完成分组操作")
            await event.reply("✅ 群组已成功绑定，当前分组为『未分组』")


# 解绑群组
@client.on(events.NewMessage(pattern="解绑群组", incoming=True))
async def unbind_group(event):
    user_id = event.sender_id

    if not await is_admin(user_id):
        logger.warning(f"❌ 非管理员 {user_id} 尝试解绑群组")
        return

    if not event.is_group:
        return await event.reply("❌ 请在群组中发送该指令")

    # 跳过脚本启动之前的消息
    message_time = int(event.date.timestamp())
    if message_time < start_time:
        logger.debug(f"跳过脚本启动之前的消息（消息时间：{message_time}, 启动时间：{start_time}）")
        return

    chat_id = event.chat_id
    logger.debug(f"处理解绑群组指令，群组ID: {chat_id}")

    # 检查该群组是否已经绑定
    db = await DB.get_conn()
    async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        # 如果已经绑定，执行解绑操作
        group_type = row[0]
        
        # 从数据库删除记录
        await db.execute("DELETE FROM group_config WHERE chat_id = ?", (chat_id,))
        await db.commit()
        
        # 从内存缓存中移除
        payback_groups.discard(chat_id)
        
        logger.info(f"[解绑] 已解绑 [{chat_id:>14}] 群组，原分组类型：『{group_type}』，已更新数据库")
        await event.reply(f"✅ 群组已成功解绑，原分组类型为『{group_type}』")
    else:
        # 如果没有绑定，提示用户
        logger.info(f"管理员 {user_id} 尝试解绑未绑定的群组 {chat_id}")
        return await event.reply("❌ 该群组尚未绑定任何分组")


# 设置群组类型（代收、代付、码商）
@client.on(events.NewMessage(pattern=r"^设置(代收|代付|码商)$", incoming=True))
async def set_group_type(event):
    if not await is_admin(event.sender_id):
        return
    if not event.is_group:
        return await event.reply("❌ 请在群组中设置分组类型")

    gtype = event.raw_text[-2:]
    chat_id = event.chat_id

    # 跳过脚本启动之前的消息
    message_time = int(event.date.timestamp())
    if message_time < start_time:
        logger.debug(f"跳过脚本启动之前的消息（消息时间：{message_time}, 启动时间：{start_time}）")
        return

    logger.debug(f"处理设置群组类型指令，群组ID: {event.chat_id}, 类型：{gtype}")

    # 检查该群组是否已经绑定
    db = await DB.get_conn()
    async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        # 如果该群已经绑定了分组，直接修改分组
        await db.execute(
            "UPDATE group_config SET group_type = ? WHERE chat_id = ?",
            (gtype, chat_id),
        )
        await db.commit()

        # 同时维护内存缓存 payback_groups
        if gtype == "代付":
            payback_groups.add(chat_id)
        else:
            payback_groups.discard(chat_id)

        logger.info(f"[设置] 已将群 [{chat_id:>14}] 群组设置为『{gtype}』分组，在数据库更新完成")
        await event.reply(f"✅ 当前群组分组已设置为『{gtype}』")
    else:
        # 如果该群组没有绑定任何分组，绑定并设置类型
        await db.execute(
            "INSERT INTO group_config (chat_id, group_type) VALUES (?, ?)",
            (chat_id, gtype),
        )
        await db.commit()

        # 同时维护内存缓存 payback_groups
        if gtype == "代付":
            payback_groups.add(chat_id)
        else:
            payback_groups.discard(chat_id)

        logger.info(f"[绑定] 已绑定 [{chat_id:>14}] 群为『{gtype}』分组，数据库更新完成分组操作")
        await event.reply(f"✅ 当前群组成功绑定，并设置为『{gtype}』")


# 查看分组类型
@client.on(events.NewMessage(pattern="查看分组"))
async def view_group_type(event):
    # 1. 权限与场景校验
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")
    if not event.is_group:
        return await event.reply("❌ 请在群组中发送该指令")

    chat_id = event.chat_id
    # 获取消息的时间戳（秒级）
    message_time = int(event.date.timestamp())

    # 2. 从 group_join_times 表查询机器人加入当前群组的时间
    try:
        db = await DB.get_conn()
        # 精确匹配当前机器人的 bot_user_id 和群组 chat_id
        async with db.execute(
            'SELECT join_time FROM group_join_times WHERE chat_id = ? AND bot_user_id = ?',
            (chat_id, (await client.get_me()).id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                join_time = row[0]
            else:
                join_time = None
    except Exception as e:
        logger.error(f"查询群组 {chat_id} 加入时间失败: {e}")
        return

    # 3. 跳过机器人加入群组之前的消息
    if join_time is not None and message_time < join_time:
        logger.debug(f"跳过进群前消息：群组 {chat_id}，消息时间 {message_time}，进群时间 {join_time}")
        return

    # 4. 查询群组分组类型并回复
    logger.debug(f"处理查看分组类型指令，群组ID: {chat_id}")
    async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        logger.info(f"管理员 {event.sender_id} 查看了群组 {chat_id} 的分组类型：{row[0]}")
        await event.reply(f"📋 当前群组的分组类型为『{row[0]}』")
    else:
        logger.info(f"管理员 {event.sender_id} 查看了群组 {chat_id} 的分组类型，但该群未绑定任何分组")
        await event.reply("❌ 当前群组未绑定任何分组")
        
        

# ---------------------------- 操作菜单命令 ----------------------------

@client.on(events.NewMessage(pattern="菜单", incoming=True))
async def show_menu(event):
    """展示管理员可执行的所有操作命令菜单"""
    if not await is_admin(event.sender_id):
        return

    menu = """
📌 **三方辅助机器人操作指南** 📌

━━━━━━━━━━━━━━━━━━━━━━━━━━━
👑 **管理员核心权限**
• 初始化：🎖️ `设置管理`
• 权限：➕ `添加管理员 @用户名` / ➖ `删除管理员 @用户名`
• 查看：👥 `查看管理员`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧩 **群组基础设置**
• 绑定：📥 `绑定群组` / 📤 `解绑群组`
• 分组：📂 `设置代收` / `设置代付` / `设置码商`
• 查ID：🆔 `获取群组id`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 **跨群互通管理**
• 单向：➡️ `绑定群组 群ID`
• 双向：↔️ 需双向执行绑定
• 解绑：❌ `解绑群组 群ID`
• 查看：📊 `查看绑定`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 **内容安全控制**
• 添加黑词：➕ `添加黑词 关键词`
• 删除黑词：➖ `删除黑词 关键词`
• 查看黑词：📜 `查看黑词`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 **关键词管理**
• 查看：📜 `查看关键词`
• 删除：➖ `删除关键词 关键词`
• 添加：➕ `添加关键词 关键词 内容`
• 更新：✏️ `更新关键词 关键词 内容`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📩 **获取回单**
• 代付：📩 `代付回单 姓名` → 返回最新代付凭证
• 代收：📩 `代收回单 姓名` → 返回最新代收凭证
━━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 **成员邀请系统**
• 单邀：➡️ `邀请 @用户名`
• 批量：📤 `邀请成员`
• 踢出：🚫 `踢成员 @用户名`
• 查看：👀 `查看成员 名单`
• 添加：➕ `添加成员 @用户名`
• 建群：🏠 `拉群`
• 设置管理员：👑 `设置管理员 @用户名`
• 移除管理员：🚫 `移除管理员 @用户名`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📮 **消息批量分发**（私聊机器人）
• 群发：📤 引用消息 + `发送代收` / `代付` / `码商`
• 删除：📤 引用消息 + `删除信息`
• 置顶：📤 引用消息 + `置顶`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **高危操作**（二次确认）
• 解散：💥 `解散群组` → 确认 `确认解散`
• 退群：🚪 `退群` → 确认 `确认退群`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 **谷歌验证器管理** 
• 添加：➕ `添加密钥 名称 密钥`
• 更名：✏️ `更名密钥 原名称 新名称`
• 删除：➖ `删除密钥 名称`
• 列表：📋 `列出密钥`（含动态码，15秒撤回）
• 取码：🔑 `取验证码 名称`
• 查看：👁️ `查看密钥 名称`（敏感）
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 **@通知管理**
• 添加：➕ `消息通知 @用户1 @用户2`
• 查看：👀 `查看通知`
• 删除：➖ 引用消息 + `删除通知`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕵️ **快捷入口**
• 菜单：📌 `菜单` → 随时唤出本菜单
"""
    await event.reply(menu)
    logger.info(f"管理员 {event.sender_id} 请求了操作菜单")
    


# ---------------------------- 内容安全控制命令 ----------------------------

async def _keyword_management(
    event, 
    operation: str,  # "add" 或 "delete"
    word: str,
    db_table: str,
    cache_vars: tuple  # (CACHE_VAR, CACHE_TIME_VAR)
):
    """
    通用关键词管理工具函数，封装重复逻辑
    保留原有日志格式和功能逻辑
    """
    # 权限校验（保持原有逻辑）
    if not await is_admin(event.sender_id):
        return
    
    # 参数处理（保持原有逻辑）
    word = word.strip()
    if not word:
        return await event.reply(f"❌ 请输入要{('添加' if operation == 'add' else '删除')}的关键词")
    
    try:
        db = await DB.get_conn()
        cache_var, cache_time_var = cache_vars
        
        # 存在性检查（保持原有逻辑）
        async with db.execute(f"SELECT COUNT(*) FROM {db_table} WHERE word = ?", (word,)) as cursor:
            count = await cursor.fetchone()
            
            if operation == "add" and count[0] > 0:
                return await event.reply(f"❌ 关键词「{word}」已存在，无需重复添加")
            if operation == "delete" and count[0] == 0:
                return await event.reply(f"❌ 关键词「{word}」不存在，无法删除")
        
        # 执行数据库操作（保持原有逻辑）
        if operation == "add":
            await db.execute(f"INSERT INTO {db_table} (word) VALUES (?)", (word,))
            action_text = "已添加"
        else:
            await db.execute(f"DELETE FROM {db_table} WHERE word = ?", (word,))
            action_text = "已删除"
        
        await db.commit()
        
        # 清空缓存（保持原有逻辑）
        globals()[cache_var] = None
        globals()[cache_time_var] = 0
        
        # 回复消息（保持原有逻辑）
        await event.reply(f"✅ 关键词{action_text}：{word}")
        
        # 日志记录（严格保留原有格式）
        logger.info(f"[管理] 在群组 [{event.chat_id:>14}] 管理员 {event.sender_id} {('添加' if operation == 'add' else '删除')}关键词：{word}")
        
    except Exception as e:
        # 错误处理（严格保留原有格式）
        logger.error(f"{('添加' if operation == 'add' else '删除')}关键词失败：{e}")
        await event.reply(f"❌ {('添加' if operation == 'add' else '删除')}关键词失败：{e}")
        logger.error(f"[管理] 在群组 [{event.chat_id:>14}] 管理员 {event.sender_id} 尝试{('添加' if operation == 'add' else '删除')}关键词失败：{word} 错误信息：{e}")


# 添加黑词（使用封装函数）
@client.on(events.NewMessage(pattern=r"^添加黑词\s+(.+)"))
async def add_blackword(event):
    word = event.pattern_match.group(1)
    await _keyword_management(
        event, 
        operation="add",
        word=word,
        db_table="blacklist",
        cache_vars=("BLACKLIST_CACHE", "BLACKLIST_CACHE_TIME")
    )


# 删除黑词（使用封装函数）
@client.on(events.NewMessage(pattern=r"^删除黑词\s+(.+)"))
async def remove_blackword(event):
    word = event.pattern_match.group(1)
    await _keyword_management(
        event, 
        operation="delete",
        word=word,
        db_table="blacklist",
        cache_vars=("BLACKLIST_CACHE", "BLACKLIST_CACHE_TIME")
    )


# 查看黑词（保持原有逻辑）
@client.on(events.NewMessage(pattern="查看黑词"))
async def view_blacklist(event):
    if not await is_admin(event.sender_id):
        return
    db = await DB.get_conn()
    async with db.execute("SELECT word FROM blacklist") as cursor:
        rows = await cursor.fetchall()
        if not rows:
            await event.reply("黑名单为空")
            logger.info(f"[管理] 在群组 [{event.chat_id:>14}] 管理员 {event.sender_id} 查询黑名单：黑名单为空")
            return
        text = "📛 当前黑名单关键词：\n" + "\n".join(f"- {r[0]}" for r in rows)
        await event.reply(text)
        logger.info(f"[管理] 在群组 [{event.chat_id:>14}] 管理员 {event.sender_id} 查询黑名单：{len(rows)} 个黑词")



# ---------------------------- 群组加入时间管理类 ----------------------------

class GroupJoinTimeManager:
    """管理群组加入时间、订单转发缓存及相关验证逻辑"""
    join_log_cache = {}  # chat_id -> 上次记录时间戳（用于防抖）
    join_time_cache = {}  # chat_id -> 已记录的加入时间戳
    
    # 订单号防重复缓存 {chat_id: {order_id: timestamp}}
    order_forward_cache = defaultdict(dict)  # 用于跟踪30秒内已转发的订单号
    CACHE_EXPIRY_SECONDS = 30  # 订单号缓存过期时间（30秒）

    @staticmethod
    def _is_private_chat_id(chat_id: int) -> bool:          
        """判断是否为私聊会话（Telegram规则：私聊chat_id > 0；群/频道chat_id < 0）"""
        return chat_id > 0                                   

    @staticmethod
    def should_log_join(chat_id: int, threshold_sec: int = 10) -> bool:
        """防抖控制：判断是否需要记录入群时间（避免重复记录）"""
        now = int(time.time())
        last_logged = GroupJoinTimeManager.join_log_cache.get(chat_id, 0)
        if now - last_logged >= threshold_sec:
            GroupJoinTimeManager.join_log_cache[chat_id] = now
            return True
        return False

    @staticmethod
    async def record_join_time(
        chat_id: int,
        bot_user_id: int = None,
        is_private: bool | None = None       
    ) -> int:
        """
        记录机器人加入群组的时间到数据库，并更新内存缓存
        私聊：立即返回当前时间，不写库、不写缓存
        """
        if is_private is None:                                   
            is_private = GroupJoinTimeManager._is_private_chat_id(chat_id)

        # 私聊直接短路处理
        if is_private:                                           
            logger.debug(f"跳过私聊会话 [{chat_id}] 的加入时间记录")
            return int(time.time())                              

        global group_join_times

        # 先检查内存缓存，已有记录则直接返回
        if chat_id in GroupJoinTimeManager.join_time_cache:
            cached_time = GroupJoinTimeManager.join_time_cache[chat_id]
            logger.debug(f"群组 [{chat_id:>14}] 已有加入时间记录（缓存）：{cached_time}，跳过重复记录")
            return cached_time

        # 获取 bot_user_id
        if bot_user_id is None:
            await ensure_client_initialized()                    
            bot_user_id = BOT_USER_ID                            

        if bot_user_id is None:
            logger.critical(f"[严重] 无法获取 BOT_USER_ID，跳过群组 {chat_id} 的加入时间记录")
            return int(time.time())

        join_time = int(time.time())

        try:
            db = await DB.get_conn()
            async with db.execute(
                "INSERT OR REPLACE INTO group_join_times (chat_id, bot_user_id, join_time) VALUES (?, ?, ?)",
                (chat_id, bot_user_id, join_time)
            ):
                await db.commit()
            # 更新双缓存（全局group_join_times + 类内join_time_cache）
            group_join_times[chat_id] = join_time
            GroupJoinTimeManager.join_time_cache[chat_id] = join_time

            tz_offset = timedelta(hours=8)
            local_timezone = timezone(tz_offset)
            join_time_local = datetime.fromtimestamp(join_time, local_timezone)
            join_time_formatted = join_time_local.strftime('%Y-%m-%d %H:%M:%S')

            # 仅输出一次日志（无重复）
            logger.info(f"[记录] 加入群 [{chat_id:>14}] 时间：{join_time_formatted} （北京时间）")
            return join_time
        except Exception as e:
            logger.error(f"记录群组 [{chat_id}] 加入时间失败: {e}")
            return int(time.time())

    @staticmethod
    async def get_join_time(
        chat_id: int,
        bot_user_id: int = None,
        is_private: bool | None = None       
    ) -> int:
        """
        从数据库获取群组加入时间，优先返回内存缓存
        私聊：直接返回当前时间，不访问数据库
        """
        if is_private is None:                                   
            is_private = GroupJoinTimeManager._is_private_chat_id(chat_id)

        if is_private:                                           
            return int(time.time())                              

        global group_join_times

        # 先查类内缓存，减少数据库查询和重复record调用
        if chat_id in GroupJoinTimeManager.join_time_cache:
            return GroupJoinTimeManager.join_time_cache[chat_id]

        if bot_user_id is None:
            await ensure_client_initialized()                    
            bot_user_id = BOT_USER_ID                            

        if bot_user_id is None:
            logger.critical(f"[严重] 无法获取 BOT_USER_ID，使用当前时间作为群组 {chat_id} 的加入时间")
            return int(time.time())

        if chat_id in group_join_times:
            return group_join_times[chat_id]

        try:
            db = await DB.get_conn()
            async with db.execute(
                "SELECT join_time FROM group_join_times WHERE chat_id = ?",
                (chat_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    join_time = row[0]
                    # 数据库查询到记录后，同步更新类内缓存
                    group_join_times[chat_id] = join_time
                    GroupJoinTimeManager.join_time_cache[chat_id] = join_time
                    return join_time
        except Exception as e:
            logger.error(f"获取群组 {chat_id} 加入时间失败: {e}")

        # 未查询到记录时，调用record（此时record会检查缓存，避免重复）
        return await GroupJoinTimeManager.record_join_time(chat_id, bot_user_id)

    # 视频消息过滤逻辑
    @staticmethod
    def is_video_message(message):
        """判断消息是否为视频类型（包括视频文件和视频文档）"""
        if hasattr(message, 'video') and message.video:
            return True
        if hasattr(message, 'document') and message.document:
            mime_type = getattr(message.document, 'mime_type', '')
            return mime_type.startswith('video/')
        return False

    @staticmethod
    def handle_message(message):
        """过滤视频消息，仅处理非视频类型的消息"""
        return not GroupJoinTimeManager.is_video_message(message)

    # 删除 join_time 记录
    @staticmethod
    async def delete_join_time(chat_id: int):
        """
        解散群/退群成功后调用：
        同步移除内存缓存和数据库中的 join_time 记录
        """
        global group_join_times
        group_join_times.pop(chat_id, None)
        # 删除时同步清理类内缓存
        GroupJoinTimeManager.join_time_cache.pop(chat_id, None)

        try:
            db = await DB.get_conn()
            async with db.execute(
                "DELETE FROM group_join_times WHERE chat_id = ?", (chat_id,)
            ):
                await db.commit()
        except Exception as e:
            logger.error(f"删除群组 {chat_id} join_time 记录失败: {e}")
    
    # 订单号防重复和缓存清理功能
    @staticmethod
    def is_order_recently_forwarded(chat_id: int, order_id: str) -> bool:
        """检查订单号是否在30秒内已转发（防重复）"""
        now = time.time()
        chat_cache = GroupJoinTimeManager.order_forward_cache.get(chat_id, {})
        
        # 检查订单是否存在且未过期
        if order_id in chat_cache:
            if now - chat_cache[order_id] < GroupJoinTimeManager.CACHE_EXPIRY_SECONDS:
                return True  # 订单号在30秒内已转发
            else:
                # 移除过期记录
                del chat_cache[order_id]
        
        # 记录当前订单转发时间
        chat_cache[order_id] = now
        GroupJoinTimeManager.order_forward_cache[chat_id] = chat_cache
        return False
    
    @staticmethod
    async def cleanup_expired_orders():
        """定时清理过期的订单号缓存（每60秒执行一次）"""
        while True:
            now = time.time()
            expired_chats = []
            
            # 遍历所有群组缓存
            for chat_id, order_cache in GroupJoinTimeManager.order_forward_cache.items():
                # 清理当前群组的过期订单
                expired_orders = [
                    order_id for order_id, timestamp in order_cache.items()
                    if now - timestamp >= GroupJoinTimeManager.CACHE_EXPIRY_SECONDS
                ]
                
                for order_id in expired_orders:
                    del order_cache[order_id]
                
                # 如果群组缓存为空，标记删除
                if not order_cache:
                    expired_chats.append(chat_id)
            
            # 清理空缓存的群组
            for chat_id in expired_chats:
                del GroupJoinTimeManager.order_forward_cache[chat_id]
            
            # 等待60秒后再次清理
            await asyncio.sleep(60)


# ---------------------------- 群组加入事件监听 ----------------------------

@client.on(events.ChatAction())  # 不提前固定 BOT_USER_ID
async def on_bot_added(event):
    """处理机器人被加入群组的事件，记录加入时间"""
    try:
        # 动态判断是否是“机器人被拉入”
        await ensure_client_initialized()                       # 确保 BOT_USER_ID 已赋值
        if not (event.user_added and event.user_id == BOT_USER_ID):
            return

        chat_id = event.chat_id
        entity = await event.get_chat()
        is_private = isinstance(entity, types.User)

        if not GroupJoinTimeManager.should_log_join(chat_id):
            return

        # 真正的写库 + 日志 都在这里
        await GroupJoinTimeManager.record_join_time(chat_id, BOT_USER_ID, is_private)

    except Exception as e:
        logger.error(f"处理加入事件时出错: {e}")


# ---------------------------- 代收群消息处理 ----------------------------

@client.on(events.NewMessage(
    incoming=True,
    # 添加视频过滤逻辑，仅处理“非视频的媒体消息”
    func=lambda e: e.is_group and e.media and GroupJoinTimeManager.handle_message(e.message)
))
async def handle_collection_media(event):
    """
    监听代收群图文消息（仅处理非视频媒体）：
    1. 仅处理机器人加入群组后产生的新消息
    2. 保留原有黑词过滤、代收群判断、转发逻辑
    3. 必须包含有效订单号才转发，统一日志格式
    4. 对特定格式的查单信息进行修改后再转发
    """
    # 初始化默认结果（避免提前return时变量未定义）
    result = "未触发转发（提前过滤）"
    order_id = "未知"  # 初始化订单号，避免日志中变量缺失
    chat_id = event.chat_id  # 提前提取chat_id，方便日志使用
    temp_path = None  # 初始化临时文件路径变量

    try:
        await ensure_client_initialized()
        bot_user_id = BOT_USER_ID
        
        join_time = await GroupJoinTimeManager.get_join_time(chat_id)
        
        if not join_time:
            join_time = int(time.time())
            await GroupJoinTimeManager.record_join_time(chat_id, bot_user_id)
            logger.info(f"群组 {chat_id} 无加入时间记录，已使用当前时间初始化")
        
        message_time = int(event.date.timestamp())
        
        logger.debug(
            f"群组 {chat_id} 消息时间：{datetime.fromtimestamp(message_time)}，"
            f"加入时间：{datetime.fromtimestamp(join_time)}"
        )
        
        # 跳过历史消息：更新结果并return
        if message_time < join_time:
            result = f"跳过历史消息（消息时间戳：{message_time}）"
            logger.debug(f"[代收] 在群组 [{chat_id:>14}] {result}")
            return

        sender = await event.get_sender()
        # 非机器人发送：更新结果并return
        if not getattr(sender, "bot", False):
            result = "非机器人发送，跳过"
            return

        db = await DB.get_conn()
        async with db.execute(
            "SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            # 非代收群：更新结果并return
            if not row or row[0] != "代收":
                result = "非代收群组，跳过"
                return

        # 无图/无文字：更新结果并return
        if not event.media or not event.raw_text:
            result = "无图或无文字，跳过"
            logger.debug(f"[代收] 在群组 [{chat_id:>14}] {result}")
            return
        
        text_to_check = (event.raw_text or "").lower().strip()
        if not text_to_check:
            prev_msg = await event.get_reply_message()
            while prev_msg:
                if prev_msg.raw_text:
                    text_to_check = prev_msg.raw_text.lower().strip()
                    break
                prev_msg = await prev_msg.get_reply_message()

        # 命中黑名单：更新结果并return
        blacklist = await get_cached_blacklist()
        for word in blacklist:
            if word and word.lower() in text_to_check:
                result = f"命中黑名单关键词“{word}”，跳过"
                logger.info(f"[代收] 在群组 [{chat_id:>14}] {result}")
                return

        # 提取订单号
        order_id = extract_order_identifier(event.raw_text) or "未识别"
        # 无有效订单号：更新结果并return
        if order_id == "未识别":
            result = "未提取到有效订单号，跳过"
            logger.info(f"[代收] 在群组 [{chat_id:>14}] 订单：{order_id} - {result}")
            return

        # 30秒内重复转发：更新结果并return
        if GroupJoinTimeManager.is_order_recently_forwarded(chat_id, order_id):
            result = "30秒内已转发，跳过"
            logger.info(f"[代收] 在群组 [{chat_id:>14}] 订单：{order_id} - {result}")
            return

        # 检查是否是需要修改的特定格式查单信息
        modified_text, is_modified = modify_appeal_order_message(event.raw_text)
        
        # 执行转发：根据是否修改决定发送方式
        if is_modified:
            # 创建临时文件（系统默认temp文件夹）
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_path = temp_file.name
                # 下载媒体到临时文件
                await event.download_media(file=temp_path)
                
                # 发送修改后的内容和原图
                await client.send_file(
                    chat_id,
                    temp_path,
                    caption=modified_text
                )
            
            # 发送完成后删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"[代收] 已删除临时文件: {temp_path}")
            result = "已修改处理完成"
        else:
            # 执行原始转发（同样使用临时文件处理）
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_path = temp_file.name
                await event.download_media(file=temp_path)
                await client.forward_messages(chat_id, event.message)
            
            # 发送完成后删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"[代收] 已删除临时文件: {temp_path}")
            result = "已处理完成"

    except Exception as e:
        # 捕获所有异常，更新结果为失败
        result = f"处理失败: {str(e)}"
        # 异常时确保删除临时文件
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"[代收] 异常时删除临时文件: {temp_path}")

    # 统一输出日志（所有场景都会执行，无提前return问题）
    logger.info(f"[代收] 在群组 [{chat_id:>14}] 订单：{order_id} - {result}")


# ---------------------------- 订单号提取工具 ----------------------------

def extract_order_identifier(text):
    """
    提取文本中的订单号（增强版）：
    支持字母+数字组合、纯数字、纯字母及带前缀的订单号格式
    """
    if not text:
        return None

    # 增强版订单号规则：
    # 1. 字母+数字组合，或数字+字母组合，或纯数字，或纯字母
    # 2. 长度在8到30之间
    patterns = [
        # 字母+数字组合（必须同时包含字母和数字）
        r'(?<![a-zA-Z0-9])(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{8,30}(?![a-zA-Z0-9])',
        # 纯数字
        r'(?<![a-zA-Z0-9])\d{8,30}(?![a-zA-Z0-9])',
        # 纯字母
        r'(?<![a-zA-Z0-9])[A-Za-z]{8,30}(?![a-zA-Z0-9])',
        # 带前缀的订单号（订单/单号:XXX）
        r'(?<![a-zA-Z0-9])订单[:：\s]*[A-Za-z0-9]{8,30}(?![a-zA-Z0-9])',
        r'(?<![a-zA-Z0-9])单号[:：\s]*[A-Za-z0-9]{8,30}(?![a-zA-Z0-9])'
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # 移除可能的前缀和空白字符
            return re.sub(r'[:：\s]', '', match.group(0))  

    # 检查回复消息
    if hasattr(text, 'is_reply') and text.is_reply:
        replied_msg = getattr(text, 'reply_to_msg', None) or getattr(text, 'get_reply_message', lambda: None)()
        if replied_msg:
            return extract_order_identifier(replied_msg.raw_text)

    return None


# ---------------------------- 特定格式消息修改工具 ----------------------------

def modify_appeal_order_message(text):
    """
    检测并修改特定格式的查单信息：
    - 匹配"代收申诉订单"格式的消息
    - 提取平台订单号并构建新消息（仅包含订单号）
    - 返回修改后的文本和是否修改的标记
    """
    if not text:
        return text, False
        
    # 检测是否是代收申诉订单格式
    if text.strip().startswith("代收申诉订单"):
        # 提取平台订单号
        platform_order_pattern = r'平台订单号[:：\s]*([A-Za-z0-9]+)'
        match = re.search(platform_order_pattern, text)
        
        if match and match.group(1):
            # 构建修改后的文本（仅包含订单号）
            modified = match.group(1)
            return modified, True
    
    # 不是目标格式，返回原文本和未修改标记
    return text, False


# ---------------------------- 催单消息处理 ----------------------------

@client.on(events.NewMessage(
    incoming=True,
    func=lambda e: e.is_group and e.reply_to_msg_id and
    (re.search(r'加急|超时|未处理|等待|掉单', e.raw_text or '') and
     re.search(r'\d+分(?:钟)?|超过\s*\d+', e.raw_text or ''))
))
async def handle_reminder_messages(event):
    """识别催单消息，转发被回复的由机器人发出的原始图文消息，最多转发3次"""
    temp_path = None  # 初始化临时文件路径变量
    try:
        await ensure_client_initialized()
        chat_id = event.chat_id

        # 获取数据库连接
        db = await DB.get_conn()

        # 检查群组配置
        async with db.execute(
                "SELECT group_type FROM group_config WHERE chat_id = ?",
                (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()

            if not row:
                logger.debug(f"[代收] 在群组 [{chat_id:>14}] [event:{event.id}] 未找到群组配置，跳过处理")
                return

            group_type = row[0]
            if group_type != "代收":
                logger.debug(f"[代收] 在群组 [{chat_id:>14}] [event:{event.id}] 群组类型为 {group_type}，非代收组，跳过处理")
                return

        # 获取被回复的原始消息
        original_msg = await event.get_reply_message()

        # 获取原始消息的发送者
        original_sender = await original_msg.get_sender()

        # 提取订单标识（仅从原始消息提取）
        order_identifier = extract_order_identifier(original_msg.raw_text or '')

        # 必须包含有效订单号才继续处理
        if not order_identifier:
            logger.info(f"[代收] 在群组 [{chat_id:>14}] 催单消息中未提取到有效订单号，跳过转发")
            return

        # 检查订单是否已被停止（无论转发计数如何）
        if order_identifier:
            async with db.execute(
                    "SELECT 1 FROM stopped_reminders WHERE chat_id = ? AND order_identifier = ?",
                    (chat_id, order_identifier)
            ) as cursor:
                if await cursor.fetchone():
                    logger.info(f"[代收] 在群组 [{chat_id:>14}] 订单 {order_identifier} 已停止，跳过转发")
                    return  # 已停止则直接跳过转发

        # 检查30秒内是否已转发过同一订单
        if GroupJoinTimeManager.is_order_recently_forwarded(chat_id, order_identifier):
            logger.info(f"[代收] 在群组 [{chat_id:>14}] 订单 {order_identifier} 30秒内已转发，跳过重复转发")
            return

        # 校验条件：图文消息且由机器人发送
        if (original_msg and original_msg.media and
            original_msg.raw_text.strip() and
            not GroupJoinTimeManager.is_video_message(original_msg) and
            getattr(original_sender, "bot", False)):

            # 获取原始消息ID
            original_msg_id = original_msg.id

            # 获取转发计数（如果不存在则视为0）
            async with db.execute(
                    "SELECT forward_count FROM reminder_forward_log WHERE original_msg_id = ? AND chat_id = ?",
                    (original_msg_id, chat_id)
            ) as cursor:
                row = await cursor.fetchone()

            # 检查转发次数是否达到上限（无论记录是否存在）
            current_count = row[0] if row else 0  # 不存在记录则视为0次
            if current_count >= 3:
                logger.info(f"[代收] 在群组 [{chat_id:>14}] 原始消息 {original_msg_id} 今日已达最大转发次数 (3次)")
                return

            # 检查是否是需要修改的特定格式查单信息
            modified_text, is_modified = modify_appeal_order_message(original_msg.raw_text)
            
            # 执行转发：根据是否修改决定发送方式
            if is_modified:
                # 创建临时文件（系统默认temp文件夹）
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                    temp_path = temp_file.name
                    # 下载媒体到临时文件
                    await original_msg.download_media(file=temp_path)
                    
                    # 发送修改后的内容和原图
                    await client.send_file(
                        chat_id,
                        temp_path,
                        caption=modified_text
                    )
                
                # 发送完成后删除临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"[催单] 已删除临时文件: {temp_path}")
            else:
                # 执行原始转发（同样使用临时文件处理）
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                    temp_path = temp_file.name
                    await original_msg.download_media(file=temp_path)
                    await client.forward_messages(chat_id, original_msg)
                
                # 发送完成后删除临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"[催单] 已删除临时文件: {temp_path}")

            # 更新转发计数（使用UPSERT替代手动事务）
            await db.execute("""
                INSERT INTO reminder_forward_log (original_msg_id, chat_id, forward_count)
                VALUES (?, ?, 1)
                ON CONFLICT (original_msg_id, chat_id) DO UPDATE 
                SET forward_count = forward_count + 1
            """, (original_msg_id, chat_id))
            await db.commit()  # 确保操作提交

            logger.info(f"[代收] 在群组 [{chat_id:>14}] 检测到催单，已转发催单，当前转发次数: {current_count+1}/3")
        else:
            # 记录不转发的原因
            reason = []
            if not original_msg:
                reason.append("原始消息不存在")
            if not original_msg.media:
                reason.append("无媒体内容")
            if not original_msg.raw_text.strip():
                reason.append("无有效文本")
            if GroupJoinTimeManager.is_video_message(original_msg):
                reason.append("是视频消息")
            if not getattr(original_sender, "bot", False):
                reason.append("用户发送")

            logger.info(f"[代收] 在群组 [{chat_id:>14}] 监测到催单信息，静默处理原因：{', '.join(reason)}")

    except Exception as e:
        logger.info(f"[代收] 在群组 [{chat_id:>14}] 处理催单消息失败: {str(e)}")
        # 异常时确保删除临时文件
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"[催单] 异常时删除临时文件: {temp_path}")


# ---------------------------- 停止催单指令处理 ----------------------------

@client.on(events.NewMessage(
    incoming=True,
    # 匹配内容为纯“停止”或“停止+订单号”的消息
    func=lambda e: e.is_group and (re.fullmatch(r'^停止$', e.raw_text or '') or 
                                  re.fullmatch(r'^停止\s+\S+$', e.raw_text or ''))
))
async def handle_stop_reminder(event):
    """
    处理“停止”指令：
    - 仅数据库中记录的管理员可执行
    - 支持回复催单消息或直接发送（格式：停止 [订单号]）
    - 通过订单号标记停止，必须包含有效订单号
    """
    try:
        # 初始化客户端（保持原有逻辑）
        await ensure_client_initialized()
        chat_id = event.chat_id
        sender = await event.get_sender()
        sender_id = sender.id  # 获取发送者ID

        # 1. 数据库读取管理员列表
        db = await DB.get_conn()
        try:
            async with db.execute("SELECT user_id FROM admins") as cursor:
                admin_rows = await cursor.fetchall()
                admin_ids = [row[0] for row in admin_rows]  # 提取所有管理员ID
        except Exception as db_e:
            logger.error(f"[停止] 读取管理员列表失败: {db_e}")
            await event.reply("权限校验失败，请联系管理员")
            return

        # 2. 权限校验
        if sender_id not in admin_ids:
            return  # 非管理员直接拦截

        # 3. 检查群组类型
        async with db.execute(
            "SELECT group_type FROM group_config WHERE chat_id = ?", 
            (chat_id,)
        ) as cursor:
            group_row = await cursor.fetchone()
            if not group_row or group_row[0] != "代收":
                return

        # 4. 提取订单标识（回复消息或当前消息中的订单号）
        order_identifier = None
        # 4.1 回复消息场景
        if event.is_reply:
            replied_msg = await event.get_reply_message()
            order_identifier = extract_order_identifier(replied_msg.raw_text or '')
            if not order_identifier:
                original_msg = await replied_msg.get_reply_message()
                if original_msg:
                    order_identifier = extract_order_identifier(original_msg.raw_text or '')
        # 4.2 非回复消息场景（需在消息中附带订单号，如“停止 123456”）
        if not order_identifier:
            order_identifier = extract_order_identifier(event.raw_text or '')

        # 5. 订单号校验（强化检查，必须有有效订单号）
        if not order_identifier:
            await event.reply(
                "未找到有效订单号，请包含订单号发送“停止”（支持格式：\n"
                "1. 回复包含订单号的消息并发送“停止”\n"
                "2. 直接发送“停止 订单号”，其中订单号为字母+数字组合、纯数字或带“订单”/“单号”前缀）"
            )
            return

        # 6. 标记订单停止
        try:
            async with db.execute(
                "INSERT INTO stopped_reminders (chat_id, order_identifier) VALUES (?, ?) "
                "ON CONFLICT(chat_id, order_identifier) DO NOTHING",
                (chat_id, order_identifier)
            ):
                await db.commit()
        except Exception as db_e:
            logger.error(f"[停止] 标记订单停止失败: {db_e}")
            await event.reply("标记订单失败，请联系管理员")
            return

        # 7. 删除转发计数
        delete_success = False
        try:
            async with db.execute(
                "DELETE FROM reminder_forward_log WHERE chat_id = ? "
                "AND original_msg_id IN (SELECT msg_id FROM sent_messages WHERE order_identifier = ?)",
                (chat_id, order_identifier)
            ):
                await db.commit()
            delete_success = True
        except Exception as db_e:
            logger.error(f"[停止] 删除转发计数失败: {db_e}")

        # 8. 回复与日志
        reply_msg = f"已停止订单 {order_identifier} 的催单转发，后续不再转发"
        log_content = f"[停止] 在群组 [{chat_id:>14}] 已停止催单 关联订单{order_identifier}"
        
        await event.reply(reply_msg)
        logger.info(log_content)

    except Exception as e:
        logger.error(
            f"[停止] 群组 [{chat_id:>14}] 处理失败: {e}", 
            exc_info=True
        )
        await event.reply("处理“停止”指令时出错，请稍后再试")
    

    
    
    

# ---------------------------- 黑名单缓存配置 ----------------------------
# 黑名单缓存存储容器（存储从数据库加载的黑词列表）
# 初始为None，首次使用时加载，后续直接从缓存读取
BLACKLIST_CACHE = None

# 黑名单缓存最后更新时间戳（记录缓存加载/刷新的时间）
# 用于判断缓存是否过期，避免频繁查询数据库
BLACKLIST_CACHE_LAST_REFRESH = 0

# 黑名单缓存超时时间（单位：秒），设置为5分钟(300秒)
# 超过此时长后，下次访问会自动重新从数据库加载最新黑词
BLACKLIST_CACHE_TIMEOUT = 300




# ---------------------------- 黑名单缓存管理 ----------------------------

async def get_cached_blacklist():
    """
    获取缓存的黑名单关键词列表（带自动刷新机制）
    - 缓存未初始化或过期时自动从数据库加载最新数据
    - 仅在数据有变化时更新缓存，减少不必要的内存修改
    """
    # 引用全局缓存变量
    global BLACKLIST_CACHE, BLACKLIST_CACHE_LAST_REFRESH
    current_time = time.time()

    # 缓存过期或未初始化时重新加载
    if not BLACKLIST_CACHE or current_time - BLACKLIST_CACHE_LAST_REFRESH > BLACKLIST_CACHE_TIMEOUT:
        # 从数据库读取最新黑词列表
        async with aiosqlite.connect("database.db") as conn:
            async with conn.execute("SELECT word FROM blacklist") as cursor:
                new_blacklist = [row[0] async for row in cursor]

        # 仅在黑名单数据有变化时更新缓存（减少内存操作）
        if new_blacklist != BLACKLIST_CACHE:
            BLACKLIST_CACHE = new_blacklist
            BLACKLIST_CACHE_LAST_REFRESH = current_time
            logger.debug(f"黑名单缓存已更新，当前包含 {len(BLACKLIST_CACHE)} 个关键词")

    return BLACKLIST_CACHE


# ---------------------------- 群组初始化管理 ----------------------------

async def init_existing_collection_groups():
    """
    为所有已配置的代收群组初始化机器人加入时间
    - 仅处理数据库中无加入时间记录的群组
    - 确保新部署或数据迁移后历史群组能正常过滤历史消息
    """
    # 确保客户端已初始化并获取机器人ID
    await ensure_client_initialized()
    bot_user_id = BOT_USER_ID
    logger.info(f"开始为机器人 {bot_user_id} 初始化现有代收群组的加入时间...")
    
    # 连接数据库
    db = await DB.get_conn()
    
    # 获取所有已配置的代收群组ID
    async with db.execute(
        "SELECT chat_id FROM group_config WHERE group_type = '代收'"
    ) as cursor:
        existing_chats = [row[0] for row in await cursor.fetchall()]
    
    current_time = int(time.time())
    initialized_count = 0  # 记录新初始化的群组数量
    
    # 逐个检查并初始化群组
    for chat_id in existing_chats:
        # 检查该群组是否已有加入时间记录
        join_time = await GroupJoinTimeManager.get_join_time(chat_id, bot_user_id)
        
        if not join_time:
            # 无记录时初始化加入时间
            await GroupJoinTimeManager.record_join_time(chat_id, bot_user_id)
            initialized_count += 1
    
    logger.info(f"初始化完成：共处理 {len(existing_chats)} 个代收群组，新初始化 {initialized_count} 个")
    




# ✅ 三方辅助机器人 - 监听代付群图文（bot 消息图片+订单号）

# 全局变量保持不变，添加必要的优化变量
pending_images = defaultdict(list)  # 待处理图片队列：{提示消息ID: [图片路径列表]}
PENDING_SEND_DELAY = 2.0  # 图片发送延迟时间（秒）
REPLY_PAYBACK_DELAY = 1.5  # 代付回复延迟时间（秒）
active_send_tasks = set()  # 活跃的图片发送任务集合
recent_payback_records = dict()  # 近期代付操作记录：{键: 时间戳}
recent_cd_responses = dict()  # 近期查单回复记录：{键: 时间戳}

# 新增优化相关变量
cache_lock = asyncio.Lock()  # 缓存操作锁
CACHE_EXPIRE_SECONDS = 30  # 缓存过期时间(30秒)
blacklist_cache = set()      # 黑词缓存集合
blacklist_last_refresh = 0   # 黑词缓存最后刷新时间戳
BLACKLIST_REFRESH_INTERVAL = 300  # 黑词缓存刷新间隔（秒）

# 订单号与指令正则表达式
_order_pattern = re.compile(r"(?<![@A-Za-z0-9])\b([A-Za-z0-9_]{10,})\b")  # 匹配订单号
_c_pattern = re.compile(r'^c\s+([A-Za-z0-9_]{10,})\s*$', re.IGNORECASE)  # 匹配查单指令
_cd_pattern = re.compile(r'^cd\s+([A-Za-z0-9_]{10,})\s*$', re.IGNORECASE)  # 匹配撤单查单指令

# 指令映射表：{用户输入关键词: 标准化指令}
_instruction_map = {
    "代付回单": "代付回单",
    "回单": "代付回单",
    "回执": "代付回单",
    "凭证": "代付回单",
    "代付撤单": "代付撤单",
    "撤单": "代付撤单",
    "驳回": "代付撤单",
    "拦截": "代付撤单",
    "取消": "代付撤单",
    "撤回": "代付撤单",
}

# 新增：定时清理过期缓存的任务
async def clean_expired_cache():
    """定期清理过期缓存，防止内存溢出"""
    while True:
        try:
            current_time = monotonic()
            async with cache_lock:
                # 清理过期的代付操作记录
                expired_keys = [
                    key for key, timestamp in recent_payback_records.items()
                    if current_time - timestamp > CACHE_EXPIRE_SECONDS
                ]
                for key in expired_keys:
                    del recent_payback_records[key]
                
                # 清理过期的图片缓存
                expired_tip_ids = []
                for tip_id in pending_images:
                    create_time = recent_payback_records.get((tip_id, "create_time"), 0)
                    if current_time - create_time > CACHE_EXPIRE_SECONDS:
                        expired_tip_ids.append(tip_id)
                
                for tip_id in expired_tip_ids:
                    del pending_images[tip_id]
            
            # 每小时清理一次
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"[代付] 缓存清理任务失败: {e}")
            await asyncio.sleep(60)  # 出错后缩短间隔重试

# 刷新黑词缓存函数
async def refresh_blacklist_cache():
    """定期刷新黑词缓存，减少数据库访问"""
    global blacklist_cache, blacklist_last_refresh
    try:
        current_time = time.time()
        # 检查是否到达刷新时间
        if current_time - blacklist_last_refresh < BLACKLIST_REFRESH_INTERVAL:
            return
            
        db = await DB.get_conn()
        async with db.execute("SELECT word FROM blacklist") as cursor:
            rows = await cursor.fetchall()
            blacklist_cache = {row[0].lower() for row in rows}
            blacklist_last_refresh = current_time
    except Exception as e:
        logger.error(f"[代付] 刷新黑词缓存失败: {e}")

# 优化黑词检测函数
async def contains_blacklist_keywords(text: str) -> bool:
    """检查文本是否包含黑词（使用缓存）"""
    if not text:
        return False
    
    # 先尝试刷新缓存
    await refresh_blacklist_cache()
    
    text_lower = text.lower()
    return any(word in text_lower for word in blacklist_cache)

# 提取订单指令（同步函数）
def extract_order_instruction_sync(text: str):
    """从文本中提取标准化指令和订单号"""
    original_keyword = None
    for keyword in _instruction_map.keys():
        if keyword in text:  
            original_keyword = keyword
            break
    if not original_keyword:
        return None, [], False, False
    
    instruction = _instruction_map[original_keyword]
    order_ids = _order_pattern.findall(text)
    
    is_long_instruction = original_keyword.startswith("代付")
    instruction_before = False
    if order_ids:
        first_order = order_ids[0]
        keyword_pos = text.find(original_keyword)
        order_pos = text.find(first_order)
        if keyword_pos != -1 and order_pos != -1:
            instruction_before = keyword_pos < order_pos
    
    return instruction, order_ids, is_long_instruction, instruction_before

# 检查是否为代付群组
async def is_payback_group(chat_id: int) -> bool:
    """判断指定群组是否为代付群组"""
    db = await DB.get_conn()
    async with db.execute(
        "SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row and row[0] == "代付"

# 监听代付请求
@client.on(events.NewMessage(incoming=True))
async def catch_payback_request(event):
    """监听新消息，捕捉代付相关请求并处理"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        logger.warning(f"机器人 ID 未初始化，跳过消息处理。来源: {event.chat_id}")
        return

    chat_id = event.chat_id
    message_time = int(event.date.timestamp())
    try:
        join_time = await GroupJoinTimeManager.get_join_time(chat_id, BOT_USER_ID)
    except Exception as e:
        logger.error(f"获取群组 {chat_id} 加入时间失败: {e}")
        return
    if message_time < join_time:
        logger.debug(f"跳过群组 {chat_id} 加入前的消息（{message_time} < {join_time}）")
        return

    if not event.is_group or not await is_payback_group(chat_id):
        return
    text = (event.raw_text or "").strip()
    if not text:
        return

    # 检查黑词
    blacklist = await get_cached_blacklist()
    for word in blacklist:
        if word and word.lower() in text.lower():
            return

    # 获取发送者信息
    sender = await event.get_sender()
    username = getattr(sender, 'username', '')
    is_bot_sender = sender.bot or (username.lower().endswith('bot') if username else False)

    # 提取指令和订单号
    instruction, order_ids, is_long_instruction, instruction_before = extract_order_instruction_sync(text)
    if not instruction or not order_ids:
        return

    if instruction == "代付撤单":
        valid_orders = []
        async with cache_lock:  # 添加锁确保线程安全
            for order_id in order_ids:
                key = (chat_id, order_id)
                if monotonic() - recent_payback_records.get(key, 0) < PAYBACK_DEDUPE_INTERVAL:
                    continue
                recent_payback_records[key] = monotonic()

                if is_long_instruction and instruction_before and not is_bot_sender:
                    continue
                valid_orders.append(order_id)

        if not valid_orders:
            return

        order_list = " ".join(valid_orders)
        try:
            sent = await event.reply(f"代付撤单 {order_list}", reply_to=event.id)
        except Exception as e:
            logger.error(f"[代付] 回复撤单提示失败：{e}", exc_info=True)
            return

        # 记录日志
        if len(valid_orders) == 1:
            logger.info(
                f"[代付] 在群组 [{chat_id:>14}] 代付撤单 {valid_orders[0]}（{'Bot' if is_bot_sender else '用户'}）"
            )
        else:
            logger.info(
                f"[代付] 在群组 [{chat_id:>14}] 已完成批量代付撤单（{len(valid_orders)}个订单）（{'Bot' if is_bot_sender else '用户'}）"
            )

        # 缓存相关信息
        tip_msg_id = sent.id
        pending_images[tip_msg_id] = []
        async with cache_lock:
            recent_payback_records[(tip_msg_id, "orders")] = valid_orders
            recent_payback_records[(tip_msg_id, "group")] = chat_id
            recent_payback_records[(tip_msg_id, "first_trigger_msg_id")] = event.id
            recent_payback_records[(tip_msg_id, "is_bot_sender")] = is_bot_sender
            recent_payback_records[(tip_msg_id, "create_time")] = monotonic()  # 记录创建时间

    else:
        order_id = order_ids[0] if order_ids else None
        if not order_id:
            return

        key = (chat_id, order_id)
        async with cache_lock:  # 添加锁确保线程安全
            if monotonic() - recent_payback_records.get(key, 0) < PAYBACK_DEDUPE_INTERVAL:
                return
            recent_payback_records[key] = monotonic()

        if is_long_instruction and instruction_before and not is_bot_sender:
            logger.info(f"[代付] 在群组 [{chat_id:>14}] 跳过订单：{order_id}")
            return

        try:
            sent = await event.reply(f"{instruction} {order_id}", reply_to=event.id)
        except Exception as e:
            logger.error(f"[代付] 回复提示失败：{e}", exc_info=True)
            return

        # 缓存相关信息
        tip_msg_id = sent.id
        pending_images[tip_msg_id] = []
        async with cache_lock:
            recent_payback_records[(tip_msg_id, "order")] = order_id
            recent_payback_records[(tip_msg_id, "group")] = chat_id
            recent_payback_records[(tip_msg_id, "first_trigger_msg_id")] = event.id
            recent_payback_records[(tip_msg_id, "is_bot_sender")] = is_bot_sender
            recent_payback_records[(tip_msg_id, "create_time")] = monotonic()  # 记录创建时间

        logger.info(
            f"[代付] 在群组 [{chat_id:>14}] {instruction} {order_id}（{'Bot' if is_bot_sender else '用户'}）"
        )

# 处理代付相关回复
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group and e.reply_to_msg_id))
async def handle_payback_reply(event):
    """
    处理代付群组中的回复消息：
    1. 仅代付群组生效
    2. 识别指令类型（撤单/回单）
    3. 提取被回复消息中的订单号
    4. 双重去重：消息级 + 订单级
    5. 回单拆分：一个订单触发一次回单（带延迟避免发送过快）
    6. 严格对齐原有日志格式
    7. 新增黑词检测：同时检测当前消息和被回复消息
    """
    try:
        chat_id = event.chat_id
        # 检测当前消息和被回复消息的黑词
        current_text = (event.raw_text or "").strip()
        if await contains_blacklist_keywords(current_text):
            return
        
        # 检测被回复消息
        reply_msg = await event.get_reply_message()
        if not reply_msg:
            logger.debug(f"[代付] 在群组 [{chat_id:>14}] 未获取到被回复消息，跳过处理")
            return
        
        reply_text = (reply_msg.raw_text or "").strip()
        if await contains_blacklist_keywords(reply_text):
            return

        # 1. 代付群组校验
        if not await is_payback_group(chat_id):
            return
        
        # 2. 基础消息校验
        raw_text = current_text
        if not raw_text:
            return
        
        # 3. 识别指令类型
        instruction = None
        for keyword in _instruction_map:
            if keyword in raw_text:
                instruction = _instruction_map[keyword]
                break
        if instruction not in ["代付撤单", "代付回单"]:
            return
        
        # 4. 提取订单号
        order_ids = _order_pattern.findall(reply_text)
        if not order_ids:
            return
        
        # 5. 消息级去重（添加锁和单调时间）
        message_key = (chat_id, event.id)
        async with cache_lock:
            last_process_time = recent_payback_records.get(message_key, 0)
            if monotonic() - last_process_time < PAYBACK_DEDUPE_INTERVAL:
                logger.debug(f"[代付] 在群组 [{chat_id:>14}] 消息 {event.id} 触发{instruction}，仍在去重间隔内，跳过")
                return
            recent_payback_records[message_key] = monotonic()
        
        # 6. 订单级去重 + 回单延迟处理
        sender = await event.get_sender()
        is_bot_sender = sender.bot or (getattr(sender, 'username', '').lower().endswith('bot') if sender.username else False)
        
        # 回单单独处理
        if instruction == "代付回单":
            for idx, order_id in enumerate(order_ids):
                order_key = (chat_id, order_id)
                async with cache_lock:
                    last_order_time = recent_payback_records.get(order_key, 0)
                    if monotonic() - last_order_time < PAYBACK_DEDUPE_INTERVAL:
                        logger.debug(f"[代付] 在群组 [{chat_id:>14}] 订单 {order_id} 触发回单，仍在去重间隔内，跳过")
                        continue
                
                # 增加延迟（带异常处理）
                if idx > 0:
                    try:
                        await asyncio.sleep(REPLY_PAYBACK_DELAY)
                    except asyncio.CancelledError:
                        logger.warning(f"[代付] 在群组 [{chat_id:>14}] 订单 {order_id} 延迟被中断，跳过")
                        continue
                
                # 执行单个回单（带重试）
                sent = None
                for retry in range(3):  # 最多重试3次
                    try:
                        sent = await event.reply(f"代付回单 {order_id}", reply_to=event.id)
                        break
                    except Exception as e:
                        logger.error(f"[代付] 在群组 [{chat_id:>14}] 回复回单 {order_id} 第{retry+1}次失败: {e}")
                        if retry < 2:
                            await asyncio.sleep(1)  # 重试间隔1秒
                
                if not sent:
                    continue  # 多次失败则跳过
                
                logger.info(
                    f"[代付] 在群组 [{chat_id:>14}] 代付回单 {order_id}（{'Bot' if is_bot_sender else '用户'}）"
                )
                
                # 缓存单个回单信息
                tip_msg_id = sent.id
                pending_images[tip_msg_id] = []
                async with cache_lock:
                    recent_payback_records[(tip_msg_id, "order")] = order_id
                    recent_payback_records[(tip_msg_id, "group")] = chat_id
                    recent_payback_records[(tip_msg_id, "first_trigger_msg_id")] = event.id
                    recent_payback_records[(tip_msg_id, "is_bot_sender")] = is_bot_sender
                    recent_payback_records[(tip_msg_id, "create_time")] = monotonic()  # 记录创建时间
                    recent_payback_records[order_key] = monotonic()
            
            return
        
        # 7. 撤单处理
        if instruction == "代付撤单":
            valid_orders = []
            async with cache_lock:
                for order_id in order_ids:
                    order_key = (chat_id, order_id)
                    last_order_time = recent_payback_records.get(order_key, 0)
                    if monotonic() - last_order_time < PAYBACK_DEDUPE_INTERVAL:
                        logger.debug(f"[代付] 在群组 [{chat_id:>14}] 订单 {order_id} 触发撤单，仍在去重间隔内，跳过")
                        continue
                    valid_orders.append(order_id)
                    recent_payback_records[order_key] = monotonic()
            
            if not valid_orders:
                return
            
            order_list = " ".join(valid_orders)
            # 发送撤单消息（带重试）
            sent = None
            for retry in range(3):
                try:
                    sent = await event.reply(f"代付撤单 {order_list}", reply_to=event.id)
                    break
                except Exception as e:
                    logger.error(f"[代付] 在群组 [{chat_id:>14}] 回复撤单第{retry+1}次失败: {e}")
                    if retry < 2:
                        await asyncio.sleep(1)
            
            if not sent:
                return
            
            if len(valid_orders) == 1:
                logger.info(
                    f"[代付] 在群组 [{chat_id:>14}] 代付撤单 {valid_orders[0]}（{'Bot' if is_bot_sender else '用户'}）"
                )
            else:
                logger.info(
                    f"[代付] 在群组 [{chat_id:>14}] 已完成批量代付撤单（{len(valid_orders)}个订单）（{'Bot' if is_bot_sender else '用户'}）"
                )
            
            # 缓存撤单信息
            tip_msg_id = sent.id
            pending_images[tip_msg_id] = []
            async with cache_lock:
                recent_payback_records[(tip_msg_id, "orders")] = valid_orders
                recent_payback_records[(tip_msg_id, "group")] = chat_id
                recent_payback_records[(tip_msg_id, "first_trigger_msg_id")] = event.id
                recent_payback_records[(tip_msg_id, "is_bot_sender")] = is_bot_sender
                recent_payback_records[(tip_msg_id, "create_time")] = monotonic()  # 记录创建时间
                
    except Exception as e:
        safe_chat_id = chat_id if 'chat_id' in locals() else "未知群组"
        logger.error(f"[代付] 在群组 [{safe_chat_id:>14}] 处理回复触发异常: {e}", exc_info=True)

# 新增：启动时初始化缓存清理任务
async def init_payback_optimizations():
    """初始化优化相关的定时任务"""
    asyncio.create_task(clean_expired_cache())
    # 初次加载黑词缓存
    await refresh_blacklist_cache()
    logger.info("代付处理优化任务已初始化")

# 自动回复查单消息
@client.on(events.NewMessage(incoming=True))
async def auto_reply_cd_messages(event):
    """自动回复查单(c)和撤单查单(cd)消息"""
    try:
        if not event.is_group:
            return
        
        chat_id = event.chat_id
        msg_id = event.id
        text = (event.raw_text or "").strip()
        
        if not await is_payback_group(chat_id):
            return
        
        sender = await event.get_sender()
        if not getattr(sender, "bot", False):
            return
        
        c_match = _c_pattern.match(text)
        cd_match = _cd_pattern.match(text)
        
        if not (c_match or cd_match):
            return
            
        dedupe_key = (chat_id, msg_id)
        async with cache_lock:
            if monotonic() - recent_cd_responses.get(dedupe_key, 0) < 60:
                return
            recent_cd_responses[dedupe_key] = monotonic()
        
        order_id = cd_match.group(1) if cd_match else c_match.group(1)
        
        await event.reply(text, reply_to=msg_id)
        
        logger.info(
            f"[代付] 在群组 [{chat_id:>14}] 发送查单信息 {'cd' if cd_match else 'c'} {order_id}（Bot）"
        )
        
    except Exception as e:
        logger.error(f"[代付] 在群组 [{chat_id:>14}] 处理{'cd' if cd_match else 'c'}消息回复失败: {e}")

# 捕捉所有图片消息
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group and e.message.photo is not None))
async def catch_all_images(event):
    """捕捉代付群组中的图片消息并关联订单"""
    chat_id = event.chat_id
    if not await is_payback_group(chat_id):
        return

    is_album = hasattr(event.message, 'grouped_id')
    order_ids = []
    reply_to = await event.get_reply_message()
    tip_msg_id = None
    
    if reply_to:
        tip_msg_id = reply_to.id
        async with cache_lock:
            order_ids = recent_payback_records.get((tip_msg_id, "orders"), [])
            if not order_ids:
                order_ids = [recent_payback_records.get((tip_msg_id, "order"))]
            order_ids = [oid for oid in order_ids if oid is not None]

    if not order_ids:
        logger.info(f"[代付] 在群组 [{chat_id:>14}] 已收到无关联订单的图片，将不进行缓存处理")
        return

    current_count = 1
    if tip_msg_id is not None and tip_msg_id in pending_images:
        current_count = len(pending_images[tip_msg_id]) + 1

    order_info = order_ids[0] if len(order_ids) == 1 else f"{len(order_ids)}个"
    logger.info(f"[代付] 在群组 [{chat_id:>14}] 收到并缓存{current_count}张图，关联订单 {order_info}")

    if not reply_to:
        logger.debug(f"[代付] 在群组 [{chat_id:>14}] 收到图片但无回复对象，清理缓存")
        if tip_msg_id is not None and tip_msg_id in pending_images:
            await _cleanup_pending_images(tip_msg_id)
        return

    if tip_msg_id not in pending_images:
        logger.debug(f"[代付] 在群组 [{chat_id:>14}] 收到图片但回复对象不在缓存，清理缓存")
        return

    async with cache_lock:
        is_bot_sender = recent_payback_records.get((tip_msg_id, "is_bot_sender"), False)
    
    if not is_bot_sender:
        logger.info(f"[代付] 在群组 [{chat_id:>14}] 收到图片由用户发起请求，将跳过图片处理")
        await _cleanup_pending_images(tip_msg_id)
        return

    async with cache_lock:
        order_ids = recent_payback_records.get((tip_msg_id, "orders"), [])
        if not order_ids:
            order_ids = [recent_payback_records.get((tip_msg_id, "order"))]
        order_ids = [oid for oid in order_ids if oid is not None]
        group_id = recent_payback_records.get((tip_msg_id, "group"))
    
    if not order_ids or not group_id:
        logger.warning(f"[代付] 在群组 [{chat_id:>14}] 收到图片但未找到有效订单或群信息，清理缓存")
        await _cleanup_pending_images(tip_msg_id)
        return

    try:
        prefix = "album" if is_album else "single"
        filename = f"temp/{prefix}_{'_'.join(order_ids)}_{event.id}.jpg"
        local_path = await event.download_media(filename)
    except Exception as e:
        logger.error(f"[代付] 在群组 [{chat_id:>14}] 图片下载失败：{e}")
        return

    pending_images[tip_msg_id].append(local_path)
    image_count = len(pending_images[tip_msg_id])
    
    if image_count == 1:
        asyncio.create_task(send_merged_images(tip_msg_id))
    elif image_count == 2:
        asyncio.create_task(send_merged_images(tip_msg_id))
    else:
        if len(order_ids) == 1:
            order_desc = f"订单{order_ids[0]}"
        else:
            order_desc = f"{len(order_ids)}个订单"
        logger.info(f"[代付] 在群组 [{group_id:>14}] 缓存第{image_count}张  关联{order_desc}")

# 清理待处理图片缓存
async def _cleanup_pending_images(tip_msg_id):
    """清理指定提示消息ID关联的图片缓存和记录"""
    if tip_msg_id in pending_images:
        image_paths = pending_images[tip_msg_id]
        for path in image_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"[代付] 清理图片文件：{path}")
            except Exception as e:
                logger.error(f"[代付] 清理图片文件失败：{e}")
        async with cache_lock:
            pending_images.pop(tip_msg_id, None)
            recent_payback_records.pop((tip_msg_id, "orders"), None)
            recent_payback_records.pop((tip_msg_id, "order"), None)
            recent_payback_records.pop((tip_msg_id, "group"), None)
            recent_payback_records.pop((tip_msg_id, "first_trigger_msg_id"), None)
            recent_payback_records.pop((tip_msg_id, "is_bot_sender"), None)
            recent_payback_records.pop((tip_msg_id, "create_time"), None)
        logger.debug(f"[代付] 已清理tip_msg_id {tip_msg_id} 的缓存")


# 发送合并的图片
async def send_merged_images(tip_msg_id: int):
    """发送并合并缓存的图片"""
    if tip_msg_id in active_send_tasks:
        logger.debug(f"[代付] 任务重复，跳过")
        return
    active_send_tasks.add(tip_msg_id)

    try:
        await asyncio.sleep(0.5)
        if tip_msg_id not in pending_images:
            return

        async with cache_lock:
            order_ids = recent_payback_records.get((tip_msg_id, "orders"), [])
            if not order_ids:
                order_ids = [recent_payback_records.get((tip_msg_id, "order"))]
            order_ids = [oid for oid in order_ids if oid is not None]
            group_id = recent_payback_records.get((tip_msg_id, "group"))
            is_bot_sender = recent_payback_records.get((tip_msg_id, "is_bot_sender"), False)
        
        if not order_ids or not group_id:
            return

        if not is_bot_sender:
            logger.info(f"[代付] 在群组 [{group_id:>14}] 用户订单（{len(order_ids)}个），跳过发送")
            return

        images = pending_images.get(tip_msg_id, [])
        if not images:
            logger.warning(f"[代付] 在群组 [{group_id:>14}] 订单（{len(order_ids)}个）无图片，跳过")
            return

        first_trigger_msg_id = recent_payback_records.get((tip_msg_id, "first_trigger_msg_id"))
        caption = ""  
        try:
            await client.send_file(
                group_id,
                images,
                reply_to=first_trigger_msg_id,
                caption=caption
            )
            send_count = len(images)
            if len(order_ids) == 1:
                order_desc = f"订单{order_ids[0]}"
            else:
                order_desc = f"{len(order_ids)}个订单"
            logger.info(f"[代付] 在群组 [{group_id:>14}] 发送并清理{send_count}张，关联{order_desc}（Bot）")
        except Exception as e:
            logger.error(f"[代付] 在群组 [{group_id:>14}] 发送图片失败：{e}")
    finally:
        to_remove = pending_images.get(tip_msg_id, [])
        await asyncio.gather(*(asyncio.to_thread(os.remove, path) for path in to_remove))
        
        async with cache_lock:
            pending_images.pop(tip_msg_id, None)
            recent_payback_records.pop((tip_msg_id, "orders"), None)
            recent_payback_records.pop((tip_msg_id, "order"), None)
            recent_payback_records.pop((tip_msg_id, "group"), None)
            recent_payback_records.pop((tip_msg_id, "first_trigger_msg_id"), None)
            recent_payback_records.pop((tip_msg_id, "is_bot_sender"), None)
            recent_payback_records.pop((tip_msg_id, "create_time"), None)
        
        active_send_tasks.discard(tip_msg_id)
    

# 异步保存群组加入时间（辅助函数）
async def _save_group_join_time(chat_id, join_time):
    """保存群组加入时间到数据库"""
    try:
        db = await DB.get_conn()
        await db.execute(
            'INSERT OR REPLACE INTO group_join_times (chat_id, bot_user_id, join_time) VALUES (?, ?, ?)',
            (chat_id, (await client.get_me()).id, join_time)
        )
        await db.commit()
    except Exception as e:
        logger.error(f"保存群组 {chat_id} 加入时间到数据库失败: {e}")


# ✅ 获取群组id
@client.on(events.NewMessage(pattern=re.compile(r"获取群组id", re.IGNORECASE), incoming=True))
async def get_group_id(event):
    """
    管理员在群组内发送“获取群组id”，
    机器人回复当前群聊的 chat_id。
    """
    # 只允许管理员使用
    if not await is_admin(event.sender_id):
        logger.info(f"管理员 {event.sender_id} 尝试使用“获取群组id”命令，但没有权限")
        return

    # 只在群组内生效
    if not event.is_group:
        logger.info(f"管理员 {event.sender_id} 在私聊中尝试使用“获取群组id”命令")
        return await event.reply("❌ 请在群组中使用“获取群组id”命令")

    # 记录管理员请求并返回群组id
    logger.info(f"管理员 {event.sender_id} 请求群组 ID，当前群组 ID: {event.chat_id}")
    await event.reply(f"📎 当前群组 ID 是 `{event.chat_id}`", parse_mode="markdown")
    


# ✅ 三方辅助机器人 - Part 9：群组互通功能模块（下载+重新上传，保留媒体和格式）
# --------- 1. 绑定群组 ---------
@client.on(events.NewMessage(pattern=r'^绑定群组\s+(-?\d+)$'))
async def bind_group_handler(event):
    from_id = event.chat_id
    target_id = int(event.pattern_match.group(1))

    # 1. 不能绑定自己
    if target_id == from_id:
        await event.reply('❌ 不能绑定自己本身。')
        logger.info(f"管理员 {event.sender_id} 尝试在群 {from_id} 绑定自己本身，操作失败")
        return

    # 2. 将单向绑定关系插入到主数据库的 bindings 表
    db = await DB.get_conn()
    try:
        await db.execute(
            'INSERT OR IGNORE INTO bindings (from_id, to_id) VALUES (?, ?)',
            (from_id, target_id)
        )
        await db.commit()
        await event.reply(
            f'✅ 已为本群（{from_id}）绑定目标群组：{target_id}\n'
            '请在对方群组中也执行一次 “绑定群组 {本群ID}” 命令，完成双向绑定后即可互通消息。'
        )
        logger.info(f"管理员 {event.sender_id} 在群 {from_id} 成功绑定目标群组 {target_id}")
    except Exception as e:
        await event.reply(f'❌ 绑定失败：{e}')
        logger.error(f"管理员 {event.sender_id} 在群 {from_id} 尝试绑定目标群组 {target_id} 时失败: {e}")


# --------- 2. 查看已绑定群组 ---------
@client.on(events.NewMessage(pattern=r'^查看绑定$'))
async def view_bindings_handler(event):
    # 只在群聊里生效
    if not event.is_group:
        return

    from_id = event.chat_id

    # 1) 查询所有本群“单向”绑定出去的记录（from_id -> to_id）
    db = await DB.get_conn()
    async with db.execute(
        "SELECT to_id FROM bindings WHERE from_id = ?", (from_id,)
    ) as cursor:
        all_rows = await cursor.fetchall()
    all_to = set(r[0] for r in all_rows)  # 本群绑定出去的所有目标群 ID

    # 2) 查询本群与哪些群是双向绑定关系
    sql_two_way = """
        SELECT b1.to_id
        FROM bindings AS b1
        JOIN bindings AS b2
          ON b1.to_id = b2.from_id
         AND b2.to_id = b1.from_id
        WHERE b1.from_id = ?
    """
    async with db.execute(sql_two_way, (from_id,)) as cursor:
        two_way_rows = await cursor.fetchall()
    two_to = set(r[0] for r in two_way_rows)  # 本群所有双向绑定的群 ID

    # 3) 计算单向绑定（存在 all_to 但不在 two_to）
    one_way_to = all_to - two_to

    # 4) 拼接输出行：单向 ➡️，双向 ↔️
    lines = []
    for tid in sorted(one_way_to):
        lines.append(f"{from_id}➡️{tid}")
    for tid in sorted(two_to):
        lines.append(f"{from_id}↔️{tid}")

    # 5) 回复
    if not lines:
        await event.reply('ℹ️ 本群尚未绑定任何群组。')
        logger.info(f"管理员 {event.sender_id} 在群 {from_id} 查询绑定关系，结果无绑定群组")
    else:
        text = "📋 当前群的绑定关系：\n" + "\n".join(lines)
        await event.reply(text)
        logger.info(f"管理员 {event.sender_id} 在群 {from_id} 查询绑定关系，结果：\n{text}")


# --------- 3. 解绑群组 ---------
@client.on(events.NewMessage(pattern=r'^解绑群组\s+(-?\d+)$'))
async def unbind_group_handler(event):
    from_id = event.chat_id
    target_id = int(event.pattern_match.group(1))

    db = await DB.get_conn()
    try:
        # 删除双向绑定记录
        await db.execute(
            '''
            DELETE FROM bindings
            WHERE (from_id = ? AND to_id = ?)
               OR (from_id = ? AND to_id = ?)
            ''',
            (from_id, target_id, target_id, from_id)
        )
        await db.commit()
        await event.reply(f'✅ 已从本群（{from_id}）解除与群组 {target_id} 的双向绑定。')
        logger.info(f"管理员 {event.sender_id} 在群 {from_id} 成功解除与群组 {target_id} 的双向绑定")
    except Exception as e:
        await event.reply(f'❌ 解绑失败：{e}')
        logger.error(f"管理员 {event.sender_id} 在群 {from_id} 尝试解除与群组 {target_id} 的双向绑定时失败: {e}")


# ✅ 三方辅助机器人 - 优化回单与撤单指令的同步逻辑（回单支持多个订单号 + 延迟处理）
@client.on(events.NewMessage(incoming=True))
async def forward_between_groups(event):
    # 1. 基础过滤
    if not event.is_group or event.out or event.fwd_from:
        return
    text = (event.raw_text or '').strip()
    if text.startswith(('绑定群组', '解绑群组', '查看绑定')):
        return

    from_id = event.chat_id

    # 2. 检查消息是否包含黑词
    if await contains_blacklist_keywords(text):  # 检查是否包含黑词
        # 继续同步到目标群
        await sync_message_to_groups(event, from_id)
        return

    # 3. 查询双向绑定群组
    sql = '''
        SELECT b1.to_id
        FROM bindings AS b1
        JOIN bindings AS b2
          ON b1.to_id = b2.from_id
         AND b2.to_id = b1.from_id
        WHERE b1.from_id = ?
    '''
    try:
        db = await DB.get_conn()
        async with db.execute(sql, (from_id,)) as cursor:
            rows = await cursor.fetchall()
    except Exception:
        await init_db()
        db = await DB.get_conn()
        async with db.execute(sql, (from_id,)) as cursor:
            rows = await cursor.fetchall()
    if not rows:
        return
    target_ids = [r[0] for r in rows]

    sync_success = True  # 是否所有目标都成功同步

    # 4. 判断回单与撤单指令，并支持多个订单号 + 延迟处理
    instr = None
    order_ids = []

    if "回单" in text:
        instr = "代付回单"
        order_ids = _order_pattern.findall(text)

    elif "撤单" in text or "驳回" in text:
        instr = "代付撤单"
        order_ids = _order_pattern.findall(text)

    if instr and order_ids:
        # 5. 对回单进行延迟处理
        if instr == "代付回单":
            # 回单支持多个订单号，每个订单号之间有延迟
            for idx, order_id in enumerate(order_ids):
                if idx > 0:
                    try:
                        await asyncio.sleep(REPLY_PAYBACK_DELAY)  # 延迟处理每个订单号
                    except asyncio.CancelledError:
                        logger.warning(f"[代付] 在群组 [{from_id}] 延迟被中断，跳过")
                        continue

                # 6. 串行执行 + 节流：补充传递 db 和 from_id 参数
                for tid in target_ids:
                    await send_to_group(tid, instr, [order_id], event, db, from_id)
                    await asyncio.sleep(0.5)

            # 7. 总结日志
            status_msg = " 成功" if sync_success else " 失败"
            logger.info(
                f"[互通] 来自群 [{from_id}] 回单，同步群组：{target_ids}"
            )
        elif instr == "代付撤单":
            # 撤单支持多个订单号，补充传递 db 和 from_id 参数
            for tid in target_ids:
                await send_to_group(tid, instr, order_ids, event, db, from_id)
                await asyncio.sleep(0.5)

            # 7. 总结日志
            status_msg = " 成功" if sync_success else " 失败"
            logger.info(
                f"[互通] 来自群 [{from_id}] 的消息，已成功同步群组：{target_ids}"
            )

    else:
        # 其他信息的同步，保持原有的消息格式与逻辑
        await sync_message_to_groups(event, from_id)


# --------- 发送普通消息到群组 ---------
async def sync_message_to_groups(event, from_id):
    # 查询双向绑定群组
    sql = '''
        SELECT b1.to_id
        FROM bindings AS b1
        JOIN bindings AS b2
          ON b1.to_id = b2.from_id
         AND b2.to_id = b1.from_id
        WHERE b1.from_id = ?
    '''
    try:
        db = await DB.get_conn()
        async with db.execute(sql, (from_id,)) as cursor:
            rows = await cursor.fetchall()
    except Exception:
        await init_db()
        db = await DB.get_conn()
        async with db.execute(sql, (from_id,)) as cursor:
            rows = await cursor.fetchall()
    if not rows:
        return
    target_ids = [r[0] for r in rows]

    # 转发普通消息：补充传递 db 和 from_id 参数
    for tid in target_ids:
        await send_to_group(tid, None, [], event, db, from_id)
        await asyncio.sleep(0.5)
    logger.info(f"[互通] 来自群 [{from_id}] 的消息，已成功同步群组：{target_ids}")


# --------- 发送消息到指定群组（修正重复定义，保留唯一实现） ---------
async def send_to_group(target_id, instr, order_ids, event, db, from_id):
    # 转发处理函数（支持回单与撤单的区分）
    async def _try_send():
        # 生成消息格式：回单或撤单
        if instr in ["代付回单", "代付撤单"]:
            message = f"{instr} {' '.join(order_ids)}"
        else:
            message = event.message.text or ""

        if not event.message.media:
            await client.send_message(
                entity=target_id,
                message=message,
                parse_mode='markdown'
            )
            return

        media = event.message.media

        if isinstance(media, types.MessageMediaWebPage):
            webpage = media.webpage
            await client.send_message(
                entity=target_id,
                message=f"[{webpage.title or '网页'}]({webpage.url})",
                parse_mode='markdown',
                link_preview=True
            )
            if message:
                await client.send_message(
                    entity=target_id,
                    message=message,
                    parse_mode='markdown'
                )
            return

        await client.send_file(
            entity=target_id,
            file=media,
            caption=message or None,
            parse_mode='markdown'
        )

    try:
        await _try_send()

    except FloodWaitError as e:
        logger.warning(f"⚠️ 发送到群组 [{target_id}] 触发限流，等待 {e.seconds} 秒后重试")
        await asyncio.sleep(e.seconds)
        try:
            await _try_send()
        except Exception as e2:
            sync_success = False
            logger.error(f"同步到 {target_id} 二次尝试仍失败: {e2}")
            if event.message.text:
                try:
                    await client.send_message(
                        entity=target_id,
                        message=event.message.text,
                        parse_mode='markdown'
                    )
                except Exception as e_text:
                    logger.error(f"纯文本降级发送仍失败: {e_text}")

    except ChannelPrivateError:
        sync_success = False
        logger.error(f"❌ 群组 [{target_id}] 无访问权限，尝试自动解除绑定")
        try:
            await db.execute(
                '''
                DELETE FROM bindings
                WHERE (from_id = ? AND to_id = ?)
                   OR (from_id = ? AND to_id = ?)
                ''',
                (from_id, target_id, target_id, from_id)
            )
            await db.commit()
            logger.info(f"✅ 已自动解除 [{from_id}] 与 [{target_id}] 的绑定关系")
        except Exception as e_db:
            logger.error(f"⚠️ 自动解除绑定失败: {e_db}")

    except ValueError as e:
        sync_success = False
        logger.error(f"❌ 无法找到群组 [{target_id}] 的实体：{e}，尝试自动解除绑定")
        try:
            await db.execute(
                '''
                DELETE FROM bindings
                WHERE (from_id = ? AND to_id = ?)
                   OR (from_id = ? AND to_id = ?)
                ''',
                (from_id, target_id, target_id, from_id)
            )
            await db.commit()
            logger.info(f"✅ 已自动解除 [{from_id}] 与 [{target_id}] 的绑定关系")
        except Exception as e_db:
            logger.error(f"⚠️ 自动解除绑定失败: {e_db}")

    except Exception as e:
        sync_success = False
        logger.error(f"同步到 {target_id} 失败: {e}")
        if event.message.text:
            try:
                await client.send_message(
                    entity=target_id,
                    message=event.message.text,
                    parse_mode='markdown'
                )
            except Exception as e2:
                logger.error(f"纯文本降级发送仍失败: {e2}")



# 全局存储结构：{原始消息ID: {群组ID: 机器人发送的消息ID}}
sent_messages = defaultdict(dict)
# 全局实体缓存（优化：移至函数外部，避免重复解析实体）
global_group_entities = {}

# 新增：验证用户是否为管理员（从数据库读取）
async def is_admin(user_id):
    db = await DB.get_conn()
    async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
        # 若查询到记录，则返回True（是管理员）
        return await cursor.fetchone() is not None

# 新增：将实体同步到数据库（持久化）
async def save_entity_to_db(chat_id, entity):
    """将实体序列化后存入数据库"""
    try:
        db = await DB.get_conn()
        # 序列化实体
        entity_data = pickle.dumps(entity)
        # 移除事务嵌套，使用自动提交模式
        await db.execute("""
            INSERT OR REPLACE INTO group_entities 
            (chat_id, entity_data, updated_at) 
            VALUES (?, ?, ?)
        """, (chat_id, entity_data, datetime.now()))
        await db.commit()  # 新增：强制提交
        logger.debug(f"群组 [{chat_id}] 实体已持久化到数据库")
    except Exception as e:
        logger.error(f"持久化群组 [{chat_id}] 实体失败: {e}")

async def forward_to_groups(group_type, reply, sender_id, notify_event):
    # 获取数据库连接
    db = await DB.get_conn()
    
    # 全局限速器（限制实体解析频率）
    entity_limiter = AsyncLimiter(max_rate=15, time_period=1)  # 每秒最多15次实体解析
    
    # API调用统计
    api_call_stats = {
        "entity_calls": 0,
        "message_calls": 0,
        "last_reset": time.time()
    }

    # 封装删除无效群组的公共函数
    async def _delete_invalid_group(group_id):
        try:
            # 每个数据库操作使用独立连接
            db = await DB.get_conn()
            # 移除事务嵌套，按顺序执行删除操作
            await db.execute("DELETE FROM group_config WHERE chat_id = ?", (group_id,))
            await db.execute("DELETE FROM mentions WHERE group_id = ?", (group_id,))
            await db.execute("DELETE FROM group_failure_log WHERE group_id = ?", (group_id,))
            await db.execute("DELETE FROM group_entities WHERE chat_id = ?", (group_id,))
            await db.commit()  # 新增：强制提交删除操作
            # 同步删除内存缓存中的无效实体
            global_group_entities.pop(group_id, None)
            logger.info(f"[群发] 在群组 [{str(group_id):>14}] 累计3次发送失败，已删除群组配置及实体")
        except Exception as e:
            logger.error(f"删除群组配置失败 [群组ID:{group_id}]: {e}")

    # 新增：记录失败次数并判断是否需要删除（优化：使用独立连接）
    async def _record_failure_and_check(group_id):
        try:
            # 每个数据库操作使用独立连接
            db = await DB.get_conn()
            # 查询当前失败次数
            async with db.execute(
                "SELECT failure_count FROM group_failure_log WHERE group_id = ?", 
                (group_id,)
            ) as cursor:
                row = await cursor.fetchone()
            
            if row:
                failure_count = row[0] + 1
                # 达到3次失败，删除群组
                if failure_count >= 3:
                    await _delete_invalid_group(group_id)
                    return True
                else:
                    # 更新失败次数
                    await db.execute(
                        "UPDATE group_failure_log SET failure_count = ? WHERE group_id = ?",
                        (failure_count, group_id)
                    )
                    await db.commit()  # 新增：强制提交更新
                    logger.info(f"[群发] 在群组 [{str(group_id):>14}] 发送失败，累计次数: {failure_count}/3")
            else:
                # 首次失败，插入记录
                await db.execute(
                    "INSERT INTO group_failure_log (group_id, failure_count) VALUES (?, 1)",
                    (group_id,)
                )
                await db.commit()  # 新增：强制提交插入
                logger.info(f"[群发] 在群组 [{str(group_id):>14}] 发送失败，累计次数: 1/3")
            
            return False  # 未达到删除条件
            
        except Exception as e:
            logger.error(f"记录群组失败次数失败 [群组ID:{group_id}]: {e}")
            return False

    # 提取公共发送逻辑（包含实体持久化和自动更新）
    async def send_to_group(group_id, message, original_message_id):
        # 更新API调用统计
        api_call_stats["message_calls"] += 1
        
        # 初始化entity变量，确保在所有分支中都被定义
        entity = None
        
        # 优先从缓存获取实体
        if group_id in global_group_entities:
            entity = global_group_entities[group_id]
            # 校验缓存的实体是否有效（非None）
            if not entity:
                logger.warning(f"群组 [{group_id}] 缓存实体无效，重新解析")
                global_group_entities.pop(group_id, None)  # 删除无效缓存
                # 同步删除数据库中的无效实体
                db = await DB.get_conn()
                await db.execute("DELETE FROM group_entities WHERE chat_id = ?", (group_id,))
                await db.commit()  # 新增：强制提交删除
        
        # 缓存无有效实体时，从数据库加载
        if entity is None:
            db = await DB.get_conn()
            async with db.execute(
                "SELECT entity_data FROM group_entities WHERE chat_id = ?", 
                (group_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        entity = pickle.loads(row[0])
                        global_group_entities[group_id] = entity
                        logger.debug(f"从数据库加载群组 [{group_id}] 实体到内存")
                    except Exception as e:
                        logger.error(f"反序列化数据库实体失败 [群组ID:{group_id}]: {e}")
                        # 删除数据库中的无效记录
                        await db.execute("DELETE FROM group_entities WHERE chat_id = ?", (group_id,))
                        await db.commit()  # 新增：强制提交删除
        
        # 数据库也无实体时，重新解析并持久化
        if entity is None:
            async with entity_limiter:
                try:
                    entity = await client.get_entity(group_id)
                    global_group_entities[group_id] = entity
                    await save_entity_to_db(group_id, entity)  # 持久化到数据库
                    api_call_stats["entity_calls"] += 1
                    logger.debug(f"成功解析并持久化群组实体 [群组ID:{group_id}]")
                except Exception as e:
                    logger.error(f"实体解析失败 [群组ID:{group_id}]: {e}")
                    await _record_failure_and_check(group_id)
                    return False
        
        # 最终校验：确保entity有效
        if not entity:
            logger.error(f"群组 [{group_id}] 实体无效，无法发送消息")
            await _record_failure_and_check(group_id)
            return False
        
        # 发送消息并处理异常（增加实体自动更新逻辑）
        try:
            # 发送消息时指定Markdown格式，确保加粗生效
            if not reply.media:
                sent_message = await client.send_message(entity, message, parse_mode='markdown')
            else:
                sent_message = await client.send_file(
                    entity, 
                    file=reply.media, 
                    caption=message,
                    parse_mode='markdown'
                )
            
            # 发送成功，清除失败记录
            try:
                db = await DB.get_conn()
                await db.execute("DELETE FROM group_failure_log WHERE group_id = ?", (group_id,))
                await db.commit()  # 新增：强制提交删除
            except Exception as e:
                logger.error(f"清除群组 [{group_id}] 失败记录时出错: {e}")
                
            sent_messages[original_message_id][group_id] = sent_message.id
            await asyncio.sleep(0.05)
            return True
            
        except Exception as e:
            # 过滤特定错误日志（不输出PeerIdInvalidError且由SendMediaRequest引起的错误）
            if not (isinstance(e, errors.PeerIdInvalidError) and "caused by SendMediaRequest" in str(e)):
                # 记录详细错误
                error_details = (
                    f"[群发] 群组 [{str(group_id):>14}] 发送失败，详细原因：{type(e).__name__} - {str(e)} | "
                    f"消息前20字符：{message[:20]}... | "
                    f"包含媒体：{bool(reply.media)} | "
                    f"媒体类型：{type(reply.media).__name__ if reply.media else '无'}"
                )
                logger.error(error_details)
            
            # 特定错误类型触发实体更新（实体可能过期）
            update_failed = False  # 标记实体更新是否失败
            if isinstance(e, (errors.PeerIdInvalidError, errors.ChannelPrivateError)):
                # 合并实体更新相关日志为一条
                update_log_flag = False  # 标记是否需要输出合并日志
                try:
                    async with entity_limiter:
                        new_entity = await client.get_entity(group_id)
                        # 更新内存缓存和数据库
                        global_group_entities[group_id] = new_entity
                        await save_entity_to_db(group_id, new_entity)
                        update_log_flag = True  # 更新成功，标记需要输出日志
                        
                        # 更新后重试发送一次，同样指定Markdown格式
                        try:
                            if not reply.media:
                                sent_message = await client.send_message(new_entity, message, parse_mode='markdown')
                            else:
                                sent_message = await client.send_file(
                                    new_entity, 
                                    file=reply.media, 
                                    caption=message,
                                    parse_mode='markdown'
                                )
                            # 发送成功处理
                            db = await DB.get_conn()
                            await db.execute("DELETE FROM group_failure_log WHERE group_id = ?", (group_id,))
                            await db.commit()  # 新增：强制提交删除
                            sent_messages[original_message_id][group_id] = sent_message.id
                            await asyncio.sleep(0.05)
                            return True
                        except Exception as e2:
                            # 过滤特定错误日志
                            if not (isinstance(e2, errors.PeerIdInvalidError) and "caused by SendMediaRequest" in str(e2)):
                                logger.error(f"更新实体后再次发送仍失败: {e2}")
                except Exception as e3:
                    logger.error(f"更新实体失败: {e3}")
                    update_failed = True  # 明确标记实体更新失败（无权限/被封禁）
                
                # 输出合并后的实体更新日志（修正原日志前缀“[群群]”为“[群发]”）
                if update_log_flag:
                    logger.info(f"[群发] [{group_id}] 实体可能过期，已尝试更新并完成")
            
            # 核心修复：ChannelPrivateError且实体更新失败时，直接记录失败次数（加速删除）
            if isinstance(e, errors.ChannelPrivateError) and update_failed:
                logger.info(f"[群发] 在群组 [{str(group_id):>14}] 无访问权限且实体更新失败，直接记录失败次数")
                await _record_failure_and_check(group_id)
                return False
            
            # 普通错误：记录失败次数并检查是否需要删除群组
            logger.info(f"[群发] 在群组 [{str(group_id):>14}] 消息发送失败，记录失败次数")
            await _record_failure_and_check(group_id)
            return False

    # 基础校验（保持原有逻辑不变）
    if not reply or not hasattr(reply, 'text'):
        logger.warning("无效的回复消息")
        if notify_event and hasattr(notify_event, 'reply'):
            await notify_event.reply("❌ 请引用有效的消息进行群发")
        return
    
    text = reply.text or ""  # 初始化text变量

    # 获取目标群组（保持原有逻辑不变）
    target_groups = await get_group_ids_by_type(group_type)
    if not target_groups:
        logger.info(f"未找到类型为 {group_type} 的群组")
        if notify_event and hasattr(notify_event, 'reply'):
            await notify_event.reply(f"❌ 未找到类型为 {group_type} 的群组")
        return
    
    # 获取关键词与附文（保持原有逻辑不变）
    keyword = None
    appendix = ""
    total_mentions = 0  # 用于统计总的艾特用户数
    final_messages = []  # 存储所有群组的消息，避免重复发送

    # 清除文本中的#符号，并获取关键词
    cleaned_text = text.replace("#", "")  # 去除所有的#符号

    # 如果文本中存在关键词，获取附文
    for word in cleaned_text.split():  # 分割文本并逐个检查是否为关键词
        appendix = await get_appendix_for_text(word)
        if appendix:
            keyword = word.strip('#').replace('*', '')  # 去掉关键词前后的 # 符号，并去掉 * 符号
            break  # 找到第一个匹配的关键词就停止

    # 构建最终发送的文本（所有内容都自动加粗）
    # 使用Markdown的**符号包裹文本实现加粗
    bolded_text = f"**{text}**"  # 原始文本加粗
    bolded_appendix = f"**{appendix}**" if appendix else ""  # 附文加粗
    
    if keyword:  # 有关键词时拼接附文和艾特
        for group_id in target_groups:
            # 新表逻辑：查询usernames字段，按逗号拆分用户
            async with db.execute("SELECT usernames FROM mentions WHERE group_id = ?", (group_id,)) as cursor:
                row = await cursor.fetchone()
                users = []
                if row:
                    # 拆分并过滤空值（避免@空用户）
                    users = [u.strip() for u in row[0].split(',') if u.strip()]
                # 生成艾特列表并统计总数
                group_mentions = [f"@{u}" for u in users]
                total_mentions += len(group_mentions)
                
                # 拼接最终消息，所有内容都已加粗
                group_message = f"{bolded_text}\n\n{bolded_appendix}\n\n{' '.join(group_mentions)}"
                final_messages.append((group_id, group_message))
    else:
        # 没有关键词时，仅发送加粗的原始文本
        final_text = bolded_text

    # 执行发送并统计成功数量（保持原有逻辑不变）
    success_count = 0
    original_message_id = reply.id
    
    try:
        if final_messages:
            for group_id, group_message in final_messages:
                if await send_to_group(group_id, group_message, original_message_id):
                    success_count += 1
        else:
            for group_id in target_groups:
                if await send_to_group(group_id, final_text, original_message_id):
                    success_count += 1
        
        logger.info(
            f"[完成]：发送 {success_count}/{len(target_groups)} 个群组 | "
            f"API： {api_call_stats['entity_calls']} 次，发送 {api_call_stats['message_calls']} 次 | "
            f"实体数：{len(global_group_entities)}"
        )
        
        # 仅保留这一套通知逻辑（原始的成功通知格式）
        if notify_event and hasattr(notify_event, 'reply'):
            if keyword:
                await notify_event.reply(f"✅ 群发成功 | 成功发送 {success_count}/{len(target_groups)} 个群 | 附文:{bool(appendix)} | @用户:{total_mentions}人")
            else:
                await notify_event.reply(f"✅ 群发成功 | 成功发送 {success_count}/{len(target_groups)} 个群 | 无附文 | @用户:0人")
            
    except Exception as e:
        logger.error(f"群发流程异常: {e}")
        if notify_event and hasattr(notify_event, 'reply'):
            await notify_event.reply(f"❌ 群发失败: {e}")
    finally:
        pass

# 删除指定消息的功能（保持原有逻辑不变）
async def delete_specific_message(event):
    """删除管理员引用的消息在所有相关群组中对应的群发消息，统一日志和回复格式"""
    if event.is_reply:
        replied_message = await event.get_reply_message()
        if replied_message:
            original_message_id = replied_message.id
            if original_message_id not in sent_messages:
                return await event.reply("❌ 未找到该消息的群发记录")
            
            groups_to_delete = list(sent_messages[original_message_id].items())
            total_groups = len(groups_to_delete)
            deleted_count = 0
            failed_count = 0

            # 执行删除并统计结果
            for group_id, message_id in groups_to_delete:
                try:
                    await client.delete_messages(group_id, message_id)  # client 需根据实际定义替换
                    deleted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.debug(f"[删除] 群组 {group_id} 消息删除失败，原因：{str(e)}")  #  debug 记录详细错误

            # 构造统一格式的 INFO 日志
            logger.info(
                f"[删除] 删除完成：删除 {deleted_count}/{total_groups} 个群组 | "
                f"失败 {failed_count} 个群组"
            )

            # 构造统一格式的回复
            reply_content = f"✅ 删除成功 | 成功删除 {deleted_count}/{total_groups} 个群 | 失败 {failed_count} 个群"
            await event.reply(reply_content)

            # 清理已删除记录（删除成功才清理）
            if deleted_count > 0:
                del sent_messages[original_message_id]
        else:
            await event.reply("❌ 无法获取被引用的消息")
    else:
        await event.reply("❌ 请先引用需要删除的消息")


# 监听删除指令（增加管理员验证）
@client.on(events.NewMessage(pattern="删除信息", func=lambda e: e.is_private))
async def handle_delete_command(event):
    user_id = event.sender_id
    # 验证是否为管理员（从数据库读取）
    if not await is_admin(user_id):
        logger.warning(f"非管理员 {user_id} 尝试执行删除命令")
        return await event.reply("❌ 你没有权限执行此操作")
    
    logger.info(f"[删除] 管理员 {user_id} 请求删除消息")
    await delete_specific_message(event)

# 生成发送指令的通用处理函数（增加管理员验证）
def generate_send_handler(command, group_type):
    @client.on(events.NewMessage(pattern=command))
    async def handler(event):
        if not event.is_private:
            return
        
        user_id = event.sender_id
        # 验证是否为管理员（从数据库读取）
        if not await is_admin(user_id):
            logger.warning(f"非管理员 {user_id} 尝试执行“{command}”命令")
            return await event.reply("❌ 你没有权限执行此操作")
        
        reply = await event.get_reply_message()
        if not reply:
            logger.info(f"[群发] 管理员 {user_id} 执行“{command}”时未引用消息")
            return await event.reply("请引用要发送的消息")
        
        logger.info(f"[群发] 管理员 [{str(user_id):>14}] 执行“{command}”命令（目标群组类型：{group_type}）")
        await forward_to_groups(group_type, reply, user_id, event)
    return handler

# 生成三个指令的处理函数（保持原有逻辑不变）
generate_send_handler("发送代收", "代收")
generate_send_handler("发送代付", "代付")
generate_send_handler("发送码商", "码商")
    



# ====================== 全局变量 ======================
pinned_queue = deque()  
last_failure_rate = 0.0  

async def _preload_group_entities(group_data_list, progress_msg):
    """从数据库读取序列化的实体数据，无需调用API"""
    entity_cache = {}
    total = len(group_data_list)
    loaded = 0
    
    # 初始进度
    await progress_msg.edit(f"📡 从数据库加载 {total} 个群组实体...\n进度：0/{total}")
    
    db = await DB.get_conn()
    
    for group_id, _ in group_data_list:
        try:
            # 从数据库查询序列化的实体数据
            async with db.execute(
                "SELECT entity_data FROM group_entities WHERE chat_id = ?",
                (group_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or not row[0]:
                    logger.warning(f"[置顶] 数据库中未找到群组 {group_id} 的实体数据")
                    entity_cache[group_id] = None
                    continue
                    
                # 反序列化实体数据
                entity = pickle.loads(row[0])
                entity_cache[group_id] = entity
                loaded += 1
                
                # 更新进度
                if loaded % 10 == 0 or loaded == total:
                    await progress_msg.edit(f"📡 加载中...\n进度：{loaded}/{total}")
                    
        except Exception as e:
            logger.warning(f"[置顶] 加载群组 {group_id} 实体失败：{e}")
            entity_cache[group_id] = None
    
    # 加载完成
    await progress_msg.edit(f"✅ 实体加载完成 | 成功: {loaded}/{total}\n即将开始置顶任务...")
    return entity_cache


async def pin_message(event):
    global pinned_queue, last_failure_rate  

    # 1. 基础校验（完全保留）
    if not event.is_reply:
        return await event.reply("❌ 请先引用需要置顶的消息")
    replied_msg = await event.get_reply_message()
    original_msg_id = replied_msg.id
    if original_msg_id not in sent_messages:
        return await event.reply(f"❌ 未找到该消息的群发记录（ID: {original_msg_id}）")

    # 2. 创建唯一进度消息（后续所有进度通过编辑这条消息更新）
    progress_msg = await event.reply("⏳ 置顶任务初始化中...")

    # 3. 初始化冷却队列（完全保留）
    all_group_data = list(sent_messages[original_msg_id].items())
    total_groups = len(all_group_data)
    pinned_queue.clear()
    for group_id, msg_id in all_group_data:
        pinned_queue.append( (group_id, msg_id, 0) )

    # 4. 预解析群组实体（从数据库加载）
    entity_cache = await _preload_group_entities(all_group_data, progress_msg)
    if not entity_cache:
        return await progress_msg.edit("❌ 群组实体加载失败，无法继续置顶")

    # 5. 动态速率控制参数（优化：更保守的初始值）
    rate_config = {
        "base_time": 15,       # 单群操作间隔延长到15秒（原10秒）
        "batch_size": 5,       # 每批处理5个群（原10个）
        "silence_step": 90,    # 批次间隔延长到90秒（原60秒）
    }

    # 6. 发送任务启动通知（编辑进度消息）
    await progress_msg.edit(
        f"✅ 置顶任务启动 | 共需处理 {total_groups} 个群\n"
        "将优先处理「冷却时间短」的群组，实时更新进度"
    )

    # 7. 主处理循环（优化：动态调整速率 + 增强错误处理）
    success_count = 0
    failure_count = 0
    batch_idx = 0

    while pinned_queue:
        batch_idx += 1
        current_time = time.time()
        current_batch = []

        # 筛选本批可处理的群组（逻辑不变）
        while pinned_queue and len(current_batch) < rate_config["batch_size"]:
            group_id, msg_id, cooldown_end = pinned_queue.popleft()
            if cooldown_end <= current_time:
                current_batch.append( (group_id, msg_id) )
            else:
                pinned_queue.appendleft( (group_id, msg_id, cooldown_end) )
                break

        if not current_batch:
            await asyncio.sleep(60)
            continue

        # 动态调整速率（优化：结合失败率和最大等待时间）
        if last_failure_rate > 0.5:
            rate_config["base_time"] = min(rate_config["base_time"] * 1.5, 120)  # 最长120秒/群
            rate_config["batch_size"] = max(rate_config["batch_size"] // 2, 2)    # 最小每批2个群
            rate_config["silence_step"] = min(rate_config["silence_step"] * 1.5, 300)  # 最长300秒/批
        else:
            rate_config["base_time"] = max(rate_config["base_time"] * 0.9, 5)     # 最短5秒/群
            rate_config["silence_step"] = max(rate_config["silence_step"] * 0.9, 30)  # 最短30秒/批

        # 本批处理（优化：准确获取FloodWait时间 + 记录最大等待）
        batch_limiter = AsyncLimiter(max_rate=1, time_period=rate_config["base_time"])
        batch_success = 0
        batch_failure = 0
        error_agg = defaultdict(int)
        max_wait_in_batch = 0  # 记录本批遇到的最大等待时间

        for group_id, msg_id in current_batch:
            entity = entity_cache.get(group_id)
            if not entity:
                batch_failure += 1
                error_agg["无效实体"] += 1
                continue

            try:
                async with batch_limiter:
                    await client.pin_message(entity, msg_id, notify=False)
                    batch_success += 1
                    success_count += 1
                    logger.info(f"[置顶] 在群组 [{str(group_id):>14}] 成功置顶消息（ID: {msg_id}）")
            except FloodWaitError as e:
                # 限速错误使用普通日志，不再使用ERROR级别
                wait_sec = e.seconds
                logger.info(f"[置顶] 在群组 [{str(group_id):>14}] 触发限速，需等待 {wait_sec} 秒（ID: {msg_id}）")
                
                batch_failure += 1
                failure_count += 1
                max_wait_in_batch = max(max_wait_in_batch, wait_sec)  # 更新最大等待时间
                new_cooldown = current_time + wait_sec
                error_agg[wait_sec] += 1
                _insert_sorted(pinned_queue, (group_id, msg_id, new_cooldown))
            except Exception as e:
                # 其他错误保持ERROR级别
                batch_failure += 1
                failure_count += 1
                logger.error(f"[置顶] 在群组 [{str(group_id):>14}] 置顶失败（ID: {msg_id}）：{e}")

        # 更新失败率（逻辑不变）
        total_in_batch = batch_success + batch_failure
        last_failure_rate = batch_failure / total_in_batch if total_in_batch != 0 else 0

        # 根据最大等待时间再次调整速率（避免持续触发高等待限流）
        if max_wait_in_batch > 300:  # 若存在需要等待>5分钟的群组
            rate_config["base_time"] = min(rate_config["base_time"] * 2, 120)
            rate_config["batch_size"] = max(rate_config["batch_size"] // 2, 2)
            rate_config["silence_step"] = min(rate_config["silence_step"] * 2, 300)
        elif max_wait_in_batch > 100:  # 等待1-5分钟
            rate_config["base_time"] = min(rate_config["base_time"] * 1.5, 60)
            rate_config["silence_step"] = min(rate_config["silence_step"] * 1.5, 180)

        # 构建进度内容（编辑同一条消息）
        progress_text = (
            f"✅ 第 {batch_idx} 批处理完成\n"
            f"本批成功: {batch_success} | 失败: {batch_failure}\n"
            f"累计成功: {success_count}/{total_groups}"
        )
        if error_agg:
            progress_text += "\n\n❌ 本批错误聚合:"
            for err_type, count in error_agg.items():
                if isinstance(err_type, int):
                    progress_text += f"\n需等待 {err_type} 秒: {count} 个群"
                else:
                    progress_text += f"\n{err_type}: {count} 个群"

        # 编辑消息更新进度
        await progress_msg.edit(progress_text)

        # 批次间隔（逻辑不变）
        if batch_idx < (total_groups // rate_config["batch_size"] + 1):
            await asyncio.sleep(rate_config["silence_step"])

    # 最终结果（编辑同一条消息）
    await progress_msg.edit(
        f"🏁 所有批次处理完成\n"
        f"总成功: {success_count}/{total_groups} | 总失败: {failure_count}"
    )
    # 新增总进度日志
    logger.info(f"[置顶] 全部任务完成 | 总成功: {success_count}/{total_groups} | 总失败: {failure_count}")


# 优化队列插入逻辑（按冷却时间分组处理，短等待优先）
def _insert_sorted(queue, item):
    """优化：按冷却时间分段插入，短等待的群组优先处理"""
    group_id, msg_id, new_cooldown = item
    now = time.time()
    # 区分“短等待（<300秒）”和“长等待（≥300秒）”
    if new_cooldown - now < 300:
        # 短等待：按原逻辑插入到队列前面（优先处理）
        for i in range(len(queue)):
            if queue[i][2] > new_cooldown:
                queue.insert(i, item)
                return
        queue.append(item)
    else:
        # 长等待：直接放到队列末尾（避免阻塞短等待群组）
        queue.append(item)


# 指令监听（保持原逻辑不变，仅修改日志格式）
@client.on(events.NewMessage(pattern="置顶", func=lambda e: e.is_private))
async def handle_pin_command(event):
    # 统一日志格式
    logger.info(f"[置顶] 管理员 {event.sender_id} 发起置顶任务")
    await pin_message(event)
    
    

# —— 自动回复并@绑定用户 —— 
@client.on(events.NewMessage(incoming=True))
async def keyword_mention(event):
    global is_deleting_keyword

    # 只处理群组消息
    if not event.is_group:
        return

    chat_id = event.chat_id
    text = event.raw_text

    # 过滤所有管理命令，避免触发自动回复
    if text.startswith(("添加关键词", "删除关键词",  "查看关键词", "更新关键词")):
        return

    # 如果正在删除关键词，不做自动回复
    if is_deleting_keyword:
        return

    # 消息的时间戳（精确到秒）
    message_time = int(event.date.timestamp())
    logger.debug(f"接收到群组消息，消息时间戳：{message_time}")

    # 核心过滤逻辑：只处理脚本启动之后的消息
    if message_time < start_time:
        logger.debug(f"跳过脚本启动之前的消息（消息时间：{message_time}, 启动时间：{start_time}）")
        return

    # 机器人管理员校验（从数据库查询）
    sender_id = event.sender_id
    if not await is_admin(sender_id):
        logger.debug(f"[回复] 在群组 [{str(chat_id):>14}] 非管理员 {sender_id} 发送消息，不触发回复")
        return

    # 检查群组类型是否有效，排除"码商"分组
    db = await DB.get_conn()
    async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()
        if not row or row[0] == "码商":
            return

    # 获取附文（即关键词关联的内容）
    content = await get_appendix_for_text(text)

    # 获取数据库中存储的所有关键词
    async with db.execute("SELECT keyword FROM appendices") as cursor:
        keywords = [row[0] for row in await cursor.fetchall()]

    # 检查文本中是否包含数据库中的关键词
    matched_keywords = [keyword for keyword in keywords if keyword in text]

    if content:
        # —— 适配新mentions表：读取逗号分隔的用户字符串并拆分 ——
        async with db.execute("SELECT usernames FROM mentions WHERE group_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()  # 新表：一个群组ID对应一行数据
            users = []
            if row:
                # 按逗号拆分用户，过滤空值（避免@空用户）
                username_str = row[0]
                users = [
                    f"@{u.strip()}" 
                    for u in username_str.split(',') 
                    if u.strip()  # 去除空格和空字符串
                ]

            # 获取绑定用户数量
            user_count = len(users)
            if user_count > 0:
                # 统一日志格式：绑定用户数量记录
                logger.info(f"[回复] 在群组 [{str(chat_id):>14}] 成功获取到 {user_count} 位已绑定通知用户")

        # 拼接回复内容（使用**将内容加粗）
        if users:
            # 内容加粗，@用户保持原样
            response_text = f"**{content}**\n{' '.join(users)}"
        else:
            # 只有内容时也加粗显示
            response_text = f"**{content}**"

        # 回复消息（保持markdown解析模式）
        await event.reply(response_text, parse_mode="markdown")

        # 输出日志时，统一格式并去除#符号
        if matched_keywords:
            for keyword in matched_keywords:
                clean_keyword = keyword.lstrip('#')
                # 统一日志格式：回复记录
                limited_keyword = clean_keyword[:8]
                logger.info(f"[回复] 在群组 [{str(chat_id):>14}] 已回复管理员消息，包含关键词：{limited_keyword}")


# 以下为其他功能代码（保持不变）
# 3、添加关键词及其内容
@client.on(events.NewMessage(pattern=r"^添加关键词\s+(\S+)\s+(.+)$", incoming=True))
async def add_keyword(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    keyword = event.pattern_match.group(1)
    content = event.pattern_match.group(2)

    db = await DB.get_conn()

    # 检查关键词是否已经存在
    async with db.execute("SELECT 1 FROM appendices WHERE keyword = ?", (keyword,)) as cursor:
        if await cursor.fetchone():
            return await event.reply(f"🔔 关键词 {keyword} 已存在啦～想更新内容可以用更新功能重新设置哟")

    # 插入或更新关键词及内容
    await db.execute(
        "INSERT OR REPLACE INTO appendices (keyword, content) VALUES (?, ?)",
        (keyword, content)
    )
    await db.commit()

    # 去除日志中的#符号
    clean_keyword = keyword.lstrip('#')

    # 统一日志格式：[回复] 在群组 [ID] 操作描述
    logger.info(f"[添加] 在群组 [{str(event.chat_id):>14}] 成功添加关键词: {clean_keyword}")
    await event.reply(f"✅ 已成功添加关键词 {clean_keyword}。")



# 4、查看所有关键词及其对应内容
@client.on(events.NewMessage(pattern=r"^查看关键词$", incoming=True))
async def view_keywords(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    db = await DB.get_conn()
    async with db.execute("SELECT keyword, content FROM appendices") as cursor:
        rows = await cursor.fetchall()
        if rows:
            # 拼接所有关键词和内容，去除#符号
            response_text = "\n".join([f"**{keyword.lstrip('#')}**: {content}" for keyword, content in rows])
            # 统一日志格式
            logger.info(f"[查看] 在群组 [{str(event.chat_id):>14}] 查询到关键词：{len(rows)} 条")
        else:
            response_text = "❌ 当前没有任何关键词记录"
            # 统一日志格式
            logger.info(f"[查看] 在群组 [{str(event.chat_id):>14}] 没有查询到任何关键词")

    await event.reply(response_text, parse_mode="markdown")


# 5、删除关键词
@client.on(events.NewMessage(pattern=r"^删除关键词\s+(\S+)$", incoming=True))
async def remove_keyword(event):
    global is_deleting_keyword

    # 确保只有管理员才能操作
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    keyword = event.pattern_match.group(1).strip()

    db = await DB.get_conn()

    # 检查关键词是否存在
    async with db.execute("SELECT 1 FROM appendices WHERE keyword = ?", (keyword,)) as cursor:
        if not await cursor.fetchone():
            return await event.reply(f"❌ 关键词 `{keyword}` 不存在。")

    # 设置标志，防止进行自动回复
    is_deleting_keyword = True

    # 删除关键词
    await db.execute("DELETE FROM appendices WHERE keyword = ?", (keyword,))
    await db.commit()

    # 去除日志中的#符号
    clean_keyword = keyword.lstrip('#')

    # 仅回复删除成功的提示，不进行自动回复
    await event.reply(f"✅ 关键词 `{clean_keyword}` 已成功删除")

    # 删除完后重置标志
    is_deleting_keyword = False

    # 统一日志格式
    logger.info(f"[删除] 在群组 [{str(event.chat_id):>14}] 已删除关键词: {clean_keyword}")



# 6、更新关键词及其内容
@client.on(events.NewMessage(pattern=r"^更新关键词\s+(\S+)\s+(.+)$", incoming=True))
async def update_keyword(event):
    if not await is_admin(event.sender_id):
        return await event.reply("❌ 你没有权限执行此操作")

    keyword = event.pattern_match.group(1)
    new_content = event.pattern_match.group(2)

    db = await DB.get_conn()

    # 检查关键词是否存在
    async with db.execute("SELECT 1 FROM appendices WHERE keyword = ?", (keyword,)) as cursor:
        if not await cursor.fetchone():
            return await event.reply(f"❌ 关键词 `{keyword}` 不存在，无法更新。")

    # 更新关键词内容
    await db.execute(
        "UPDATE appendices SET content = ? WHERE keyword = ?",
        (new_content, keyword)
    )
    await db.commit()

    # 去除日志中的#符号
    clean_keyword = keyword.lstrip('#')

    # 统一日志格式
    logger.info(f"[更新] 在群组 [{str(event.chat_id):>14}] 成功更新关键词: {clean_keyword} 新内容: {new_content}")
    await event.reply(f"✅ 已成功更新关键词 {clean_keyword}，新内容为：{new_content}")





# 删除无权限信息
@client.on(events.NewMessage(incoming=True))
async def delete_forbidden_message(event):
    # 确保是群组消息且群组类型是 "码商"
    if event.is_group:
        chat_id = event.chat_id

        # 快速检查群组类型是否为 "码商"
        db = await DB.get_conn()
        async with db.execute("SELECT group_type FROM group_config WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] != "码商":
                return  # 如果不是 "码商" 群组，跳过处理

        # 获取消息内容
        message_text = event.raw_text

        # 如果消息包含指定文本，直接删除
        if "当前命令-因为角色或者权限设置-不支持访问" in message_text:
            try:
                # 立即删除该消息
                await event.delete()
            except Exception as e:
                pass  # 不输出任何日志


# ============================== 统一导入模块（仅保留确认可用的类）==============================

@client.on(NewMessage(pattern=r'^邀请\s+@([\w\d_]+)$', incoming=True))
async def invite_single_user(event: NewMessage.Event):
    # 权限校验
    if not await is_admin(event.sender_id):
        logger.info(f"[邀请] 在群组 [无] 邀请 @无 失败原因：用户 [{event.sender_id:>14}] 无管理员权限")
        return
    if not event.is_group:
        logger.info(f"[邀请] 在群组 [无] 邀请 @无 失败原因：非群组环境，无法邀请")
        return await event.reply("❌ 请在目标群组内发送该指令")

    chat_id = event.chat_id
    username = event.pattern_match.group(1)

    # 1. 获取用户实体（统一处理用户名错误）
    try:
        user_entity = await client.get_input_entity(f"@{username}")
    except (UsernameNotOccupiedError, UserIdInvalidError, ValueError) as e:
        if any(keyword in str(e).lower() for keyword in ["no user", "username", "invalid"]):
            reply_msg = f"❌ 找不到用户名 @{username}（未注册或拼写错误）"
            logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：未注册或拼写错误")
        else:
            reply_msg = f"❌ 解析用户失败：{str(e)[:20]}..."
            logger.error(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：解析用户异常（{str(e)}）")
        return await event.reply(reply_msg)

    # 2. 获取完整聊天实体（用于判断群组类型）
    try:
        chat_entity = await client.get_entity(chat_id)
    except Exception as e:
        reply_msg = f"❌ 获取群组信息失败：{str(e)[:20]}..."
        await event.reply(reply_msg)
        logger.error(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：获取群组实体异常（{str(e)}）")
        return

    # 3. 检查用户是否已在群组中（通过ID精准匹配）
    try:
        # 获取目标用户的实际ID（兼容不同实体类型）
        if hasattr(user_entity, 'user_id'):
            target_user_id = user_entity.user_id
        elif hasattr(user_entity, 'id'):
            target_user_id = user_entity.id
        else:
            raise ValueError("无法获取目标用户ID")

        # 遍历所有成员进行ID精确匹配
        async for member in client.iter_participants(chat_entity):
            if member.id == target_user_id:
                reply_msg = f"❌ 邀请失败：用户 @{username} 已经在该群组中"
                await event.reply(reply_msg)
                logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：用户已在群组中（ID匹配）")
                return

    except RPCError as e:
        logger.warning(f"[邀请] 在群组 [{chat_id:>14}] 查询成员失败（{str(e)}），继续执行邀请逻辑")
    except Exception as e:
        logger.error(f"[邀请] 检查用户是否在群时发生错误：{str(e)}", exc_info=True)

    # 4. 核心：按群组类型分支处理邀请
    try:
        if isinstance(chat_entity, Chat):
            # 4.1 基础群组（Chat 类型）：使用 AddChatUserRequest
            input_chat = InputPeerChat(chat_id=chat_entity.id)
            await client(AddChatUserRequest(
                chat_id=input_chat.chat_id,
                user_id=user_entity,
                fwd_limit=0
            ))
            invite_method = "基础群组邀请"

        elif isinstance(chat_entity, Channel):
            # 4.2 超级群组/频道（Channel 类型）：使用 InviteToChannelRequest
            input_channel = await client.get_input_entity(chat_entity)
            await client(InviteToChannelRequest(
                channel=input_channel,
                users=[user_entity]
            ))
            invite_method = "超级群组/频道邀请"

        else:
            raise TypeError(f"不支持的群组类型：{type(chat_entity).__name__}")

        # 5. 验证邀请结果（使用ID再次确认）
        await asyncio.sleep(3)
        user_joined = False
        async for member in client.iter_participants(chat_entity, limit=200):
            if member.id == target_user_id:
                user_joined = True
                break

        if not user_joined:
            raise RPCError(400, "INVITE_FAILED", "邀请发送成功，但用户未加入（可能隐私限制）")

        # 6. 邀请成功反馈
        reply_msg = f"✅ 已成功邀请 @{username} 入群（{invite_method}）"
        await event.reply(reply_msg)
        logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 成功（{invite_method}）")

    # 7. 错误处理（仅修复时间计算部分）
    except FloodWaitError as e:
        wait_time = e.seconds
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        seconds = wait_time % 60
        wait_msg = f"{hours}小时{minutes}分钟{seconds}秒" if hours > 0 else f"{minutes}分钟{seconds}秒"
        
        # 修复：使用已导入的datetime和timedelta（移除asyncio前缀）
        now = datetime.now(timezone.utc).astimezone()  # 获取本地时间（含时区）
        expected_recovery_time = now + timedelta(seconds=wait_time)
        reply_msg = (
            f"❌ 邀请触发频率限制\n"
            f"⚠️ 需等待 {wait_msg} 后重试\n"
            f"预计恢复时间：{expected_recovery_time.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）"
        )
        await event.reply(reply_msg)
        logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 触发频率限制（需等{wait_msg}）")

    except RPCError as e:
        error_str = str(e).upper()
        if any(keyword in error_str for keyword in ["PRIVACY", "MUTUAL", "USER_PRIVACY_RESTRICTED", "NOT_MUTUAL_CONTACT"]):
            try:
                invite = await client(ExportChatInviteRequest(peer=chat_entity))
                reply_msg = (
                    f"⚠️ 由于对方隐私设置/非互相关系，无法直接邀请 @{username} 入群。\n"
                    f"邀请链接：{invite.link}"
                )
                logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：对方隐私/互相关系限制")
            except Exception as inner_e:
                reply_msg = f"❌ 生成邀请链接失败：{str(inner_e)[:20]}..."
                logger.error(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：生成链接异常（{str(inner_e)}）")
        elif any(keyword in error_str for keyword in ["WRITE_FORBIDDEN", "ADMIN_REQUIRED", "CHAT_ADMIN_REQUIRED"]):
            reply_msg = f"❌ 邀请失败：您没有足够权限执行此操作（需管理员权限）"
            logger.warning(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：操作权限不足")
        elif "USER_KICKED" in error_str:
            reply_msg = f"❌ 邀请失败：用户 @{username} 已被该群组封禁，无法重新邀请"
            logger.info(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：用户已被封禁")
        else:
            error_msg = f"未知RPC错误（{str(e)[:30]}...）"
            reply_msg = f"❌ 邀请失败：{error_msg}"
            logger.error(f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：{error_msg}")
        await event.reply(reply_msg)

    except Exception as e:
        reply_msg = f"❌ 邀请失败：系统内部错误（{str(e)[:20]}...）"
        await event.reply(reply_msg)
        logger.error(
            f"[邀请] 在群组 [{chat_id:>14}] 邀请 @{username} 失败原因：系统内部错误（{str(e)}）",
            exc_info=True
        )
    


@client.on(NewMessage(pattern=r"^添加成员\s+(.+)$", incoming=True))
async def add_member(event):
    # 只有管理员可以使用
    if not await is_admin(event.sender_id):
        logger.info(f"[添加] 权限拒绝：用户 [{event.sender_id:>14}] 尝试添加成员，但无管理员权限")
        return

    # 提取参数（按空格分割@用户名列表）
    mentions = event.pattern_match.group(1).split()
    if not mentions:
        return await event.reply("❌ 格式错误，应为：添加成员 @用户名1 @用户名2 …")

    db = await DB.get_conn()
    added = []      # 成功添加的用户名
    existed = []    # 已存在的用户名
    invalid = []    # 无效/不存在的用户名

    for m in mentions:
        # 必须以@开头
        if not m.startswith("@"):
            invalid.append(m)
            continue

        # 解析用户实体（用通用Exception捕获所有解析失败）
        try:
            user = await client.get_entity(m)  # 获取完整用户实体（含username）
        except Exception:
            invalid.append(m)
            continue

        # 检查是否已在staff表
        async with db.execute("SELECT 1 FROM staff WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            existed.append(m)
        else:
            # 插入完整数据（必须包含 username！）
            await db.execute(
                "INSERT INTO staff (user_id, access_hash, username) VALUES (?, ?, ?)",
                (user.id, user.access_hash, user.username)  # 这里必须显式存入 username
            )
            added.append(m)

    # 提交事务
    await db.commit()

    # 构建回复
    parts = []
    if added:
        parts.append(f"✅ 成功添加：{', '.join(added)}")
        logger.info(f"[添加] 管理员 [{event.sender_id:>14}] 添加成员：{', '.join(added)}")
    if existed:
        parts.append(f"⚠ 已存在于列表：{', '.join(existed)}")
        for m in existed:
            logger.info(f"[添加] 管理员 [{event.sender_id:>14}] 添加成员 {m}：已存在，添加失败")
    if invalid:
        parts.append(f"❌ 无效或不存在用户名：{', '.join(invalid)}")
        for m in invalid:
            logger.info(f"[添加] 管理员 [{event.sender_id:>14}] 添加成员 {m}：无效/不存在，添加失败")
    if not parts:
        parts.append("❌ 未添加任何成员，请检查@用户名是否正确")

    await event.reply("\n".join(parts))


# ============================== 2. 删除成员（一次@一位）==============================
@client.on(NewMessage(pattern=r"^删除成员\s+@?(\w+)$", incoming=True))
async def remove_member(event):
    # 只有管理员可以使用
    if not await is_admin(event.sender_id):
        logger.info(f"[删除] 权限拒绝：用户 [{event.sender_id:>14}] 尝试删除成员，但无管理员权限")
        return

    username = event.pattern_match.group(1)
    if not username:
        return await event.reply("❌ 格式错误，应为：删除成员 @用户名")

    # 解析用户实体（用通用Exception捕获）
    try:
        user = await client.get_entity(username if username.startswith("@") else "@" + username)
    except Exception:
        logger.info(f"[删除] 管理员 [{event.sender_id:>14}] 删除成员 @{username}：无法找到用户，删除失败")
        return await event.reply(f"❌ 无法找到用户 @{username}")

    db = await DB.get_conn()
    # 检查是否在staff表
    async with db.execute("SELECT 1 FROM staff WHERE user_id = ?", (user.id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        logger.info(f"[删除] 管理员 [{event.sender_id:>14}] 删除成员 @{username}（ID: {user.id}）：不在列表，删除失败")
        return await event.reply(f"⚠ 用户 @{username} 不在成员列表中")

    # 执行删除
    await db.execute("DELETE FROM staff WHERE user_id = ?", (user.id,))
    await db.commit()

    await event.reply(f"✅ 已删除成员 @{username}")
    logger.info(f"[删除] 管理员 [{event.sender_id:>14}] 删除成员（ID: {user.id} | @{username}）：删除成功")


# ============================== 3. 查看成员（username兜底解析）==============================
@client.on(NewMessage(pattern="查看成员", incoming=True))
async def view_members(event):
    # 只有管理员可以使用
    if not await is_admin(event.sender_id):
        logger.info(f"[查看] 权限拒绝：用户 [{event.sender_id:>14}] 尝试查看成员，但无管理员权限")
        return await event.reply("❌ 你没有权限执行此操作")

    chat_id = event.chat_id
    db = await DB.get_conn()
    # 查询完整数据（user_id + access_hash + username）
    async with db.execute("SELECT user_id, access_hash, username FROM staff") as cursor:
        rows = await cursor.fetchall()
    total_members = len(rows)

    if not rows:
        logger.info(f"[查看] 在群组 [{chat_id:>14}] 查看成员列表（共 0 人）：查看成功（无成员）")
        return await event.reply("❌ 当前没有成员")

    # 解析成员信息（优先access_hash，失败用username兜底）
    members = []
    for row in rows:
        user_id, access_hash, username = row
        try:
            # 方案1：用access_hash构造实体（高效无缓存依赖）
            user_entity = InputPeerUser(user_id=user_id, access_hash=access_hash)
            user = await client.get_entity(user_entity)
            display_name = f"@{user.username}" if user.username else f"ID {user_id}（{user.first_name}）"
            members.append(f"✅ {display_name}")
        except RPCError as e:
            # 用错误代码+消息判断“找不到用户”（替代 PeerNotFoundError）
            if hasattr(e, 'code') and e.code == 400 and "NOT_FOUND" in str(e).upper():
                # 方案2：access_hash失效，用username重试
                if username:
                    try:
                        user = await client.get_entity(f"@{username}")
                        members.append(f"✅ @{username}（ID {user_id}，{user.first_name}）")
                    except Exception:
                        members.append(f"⚠ ID {user_id}（用户名 @{username} 无效，可能已改名）")
                else:
                    members.append(f"⚠ ID {user_id}（无用户名，需让用户给机器人发消息）")
            else:
                # 其他RPC错误
                members.append(f"⚠ ID {user_id}（解析失败：{str(e)[:10]}...）")
        except Exception as e:
            # 非RPC错误（如参数错误）
            members.append(f"⚠ ID {user_id}（解析失败：{str(e)[:10]}...）")

    # 构建回复
    text = f"📋 当前成员列表（共 {total_members} 人）：\n" + "\n".join(members)
    await event.reply(text)

    # 记录日志
    logger.info(f"[查看] 在群组 [{chat_id:>14}] 查看成员列表（共 {total_members} 人）：查看成功")


# ============================== 4. 邀请成员进群（批量邀请staff成员）==============================
@client.on(NewMessage(pattern=r"^邀请成员$", incoming=True))
async def invite_member(event):
    # 仅管理员在群组内可用
    if not event.is_group or not await is_admin(event.sender_id):
        logger.info(f"[邀请] 权限拒绝：用户 [{event.sender_id:>14}] 尝试批量邀请，但无权限或非群组环境")
        return

    chat_id = event.chat_id
    db = await DB.get_conn()
    # 查询staff表完整数据
    async with db.execute("SELECT user_id, access_hash, username FROM staff") as cursor:
        rows = await cursor.fetchall()
    # 过滤无效数据，转为字典列表
    staff_list = [
        {"user_id": r[0], "access_hash": r[1], "username": r[2]} 
        for r in rows if r[0] and r[1]
    ]

    # 无有效成员提示
    if not staff_list:
        logger.info(f"[邀请] 在群组 [{chat_id:>14}]：管理员 [{event.sender_id:>14}] 批量邀请：暂无成员可邀请")
        return await event.reply("ℹ️ 暂无成员可邀请，请先使用“添加成员 @用户名”")

    # 验证成员有效性（支持username重试）
    invalid_ids = []
    valid_members = []
    for member in staff_list:
        try:
            # 优先用access_hash验证
            await client.get_entity(InputPeerUser(
                user_id=member["user_id"],
                access_hash=member["access_hash"]
            ))
            valid_members.append(member)
        except RPCError as e:
            # 用错误特征判断“找不到用户”（替代 PeerNotFoundError）
            if hasattr(e, 'code') and e.code == 400 and "NOT_FOUND" in str(e).upper():
                if member["username"]:
                    try:
                        await client.get_entity(f"@{member['username']}")
                        valid_members.append(member)
                    except Exception:
                        invalid_ids.append(member["user_id"])
                else:
                    invalid_ids.append(member["user_id"])
            else:
                invalid_ids.append(member["user_id"])
        except Exception:
            invalid_ids.append(member["user_id"])
    # 记录无效成员日志
    for uid in invalid_ids:
        logger.info(f"[邀请] 在群组 [{chat_id:>14}]：批量邀请验证：用户（ID: {uid}）无法找到，标记无效")

    # 获取当前群成员ID
    try:
        participants = await client.get_participants(chat_id)
        current_member_ids = {user.id for user in participants}
    except Exception:
        current_member_ids = set()
        logger.warning(f"[邀请] 在群组 [{chat_id:>14}]：获取群成员失败，默认按“无已知成员”处理")

    # 分类：已在群内/待邀请
    already_in = [m for m in valid_members if m["user_id"] in current_member_ids]
    to_invite = [m for m in valid_members if m["user_id"] not in current_member_ids]

    # 无待邀请成员提示
    if not to_invite:
        if already_in:
            names = []
            for member in already_in:
                try:
                    u = await client.get_entity(member["user_id"])
                    names.append(f"@{u.username}" if u.username else f"[{u.first_name}](tg://user?id={member['user_id']})")
                    logger.info(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']} | @{u.username}）已在群内，跳过")
                except:
                    names.append(str(member["user_id"]))
                    logger.info(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）已在群内，跳过")
            text = "ℹ️ 暂无新成员可邀请，以下成员已在本群内：\n" + "、".join(names)
            logger.info(f"[邀请] 在群组 [{chat_id:>14}]：管理员 [{event.sender_id:>14}] 批量邀请：无新成员")
            return await event.reply(text, parse_mode="markdown")
        else:
            logger.info(f"[邀请] 在群组 [{chat_id:>14}]：管理员 [{event.sender_id:>14}] 批量邀请：暂无成员可邀请")
            return await event.reply("ℹ️ 暂无成员可邀请，请先使用“添加成员 @用户名”")

    # 批量邀请（支持username兜底构造实体）
    invited = []          # 成功邀请
    privacy_failed = []   # 隐私限制
    flood_wait_failed = []# 限流
    other_failed = []     # 其他失败

    # 构造正确的InputChannel
    chat = await client.get_entity(chat_id)
    input_channel = InputPeerChannel(
        channel_id=chat.id,
        access_hash=chat.access_hash
    ) if hasattr(chat, 'access_hash') else utils.get_input_channel(chat)

    # 逐个邀请
    for member in to_invite:
        try:
            # 方案1：用存储的access_hash构造实体
            user_entity = InputPeerUser(
                user_id=member["user_id"],
                access_hash=member["access_hash"]
            )
        except Exception:
            # 方案2：access_hash失效，用username重新获取实体
            if not member["username"]:
                other_failed.append(member["user_id"])
                logger.error(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）无用户名，无法兜底邀请")
                continue
            try:
                user = await client.get_entity(f"@{member['username']}")
                user_entity = InputPeerUser(
                    user_id=user.id,
                    access_hash=user.access_hash
                )
            except Exception as e:
                other_failed.append(member["user_id"])
                logger.error(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']} | @{member['username']}）兜底邀请失败：{str(e)}")
                continue

        # 执行邀请
        try:
            await client(InviteToChannelRequest(input_channel, [user_entity]))
            invited.append(member["user_id"])
            await asyncio.sleep(1)  # 减少限流概率
            logger.info(f"[邀请] 在群组 [{chat_id:>14}]：批量邀请用户（ID: {member['user_id']}）：成功")
        except RPCError as e:
            # 用错误特征判断隐私限制（替代 UserPrivacyRestrictedError）
            if "PRIVACY" in str(e).upper() or "USER_PRIVACY_RESTRICTED" in str(e):
                privacy_failed.append(member["user_id"])
                logger.info(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）：隐私限制，邀请失败")
            # 限流错误
            elif isinstance(e, FloodWaitError):
                flood_wait_failed.append(f"{member['user_id']}（需等{e.seconds}秒）")
                logger.error(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）：触发限流，需等{e.seconds}秒")
            # 其他RPC错误
            else:
                other_failed.append(member["user_id"])
                logger.error(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）：未知RPC错误，邀请失败：{str(e)}")
        except Exception as e:
            other_failed.append(member["user_id"])
            logger.error(f"[邀请] 在群组 [{chat_id:>14}]：用户（ID: {member['user_id']}）：未知错误，邀请失败：{str(e)}")

    # 构建回复
    parts = []
    if invited:
        names = []
        for uid in invited:
            try:
                u = await client.get_entity(uid)
                names.append(f"@{u.username}" if u.username else str(uid))
            except:
                names.append(str(uid))
        parts.append(f"✅ 成功邀请：{', '.join(names)}")
    if privacy_failed:
        names = []
        for uid in privacy_failed:
            try:
                u = await client.get_entity(uid)
                names.append(f"@{u.username}" if u.username else str(uid))
            except:
                names.append(str(uid))
        parts.append(f"⚠ 无法邀请（隐私设置）：{', '.join(names)}")
    if flood_wait_failed:
        parts.append(f"⚠ 邀请限流（需等待）：{', '.join(flood_wait_failed)}")
    if other_failed:
        names = []
        for uid in other_failed:
            try:
                u = await client.get_entity(uid)
                names.append(f"@{u.username}" if u.username else str(uid))
            except:
                names.append(str(uid))
        parts.append(f"❌ 邀请失败（其他原因）：{', '.join(names)}")
    if already_in:
        names = []
        for m in already_in:
            try:
                u = await client.get_entity(m["user_id"])
                names.append(f"@{u.username}" if u.username else str(m["user_id"]))
            except:
                names.append(str(m["user_id"]))
        parts.append(f"ℹ️ 已在群内，跳过：{', '.join(names)}")
    if invalid_ids:
        parts.append("❌ 无效成员（无法找到）：" + "、".join(str(uid) for uid in invalid_ids))
    if not parts:
        parts.append("ℹ️ 没有任何成员可以邀请或已是最新状态。")

    await event.reply("\n".join(parts), parse_mode="markdown")

    # 记录汇总日志
    logger.info(
        f"[邀请] 在群组 [{chat_id:>14}] 管理员 [{event.sender_id:>14}] 批量邀请 -> "
        f"成功：{len(invited)}，隐私失败：{len(privacy_failed)}，限流失败：{len(flood_wait_failed)}，"
        f"其他失败：{len(other_failed)}，已在群内：{len(already_in)}，无效成员：{len(invalid_ids)}"
    )


# ============================== 5. 踢出成员（一次@一位）==============================
@client.on(NewMessage(pattern=r"^踢成员\s+@?(\w+)$", incoming=True))
async def kick_member(event):
    # 仅管理员在群组内可用
    if not event.is_group or not await is_admin(event.sender_id):
        if not event.is_group:
            logger.info(f"[踢出] 非群组环境：用户 [{event.sender_id:>14}] 尝试踢成员")
        else:
            logger.info(f"[踢出] 权限拒绝：用户 [{event.sender_id:>14}] 无管理员权限，无法踢成员")
        return

    chat_id = event.chat_id
    username = event.pattern_match.group(1)
    full_username = f"@{username}" if not username.startswith("@") else username
    operation_result = "操作失败"

    # 解析用户实体（用通用Exception捕获）
    try:
        user = await client.get_entity(full_username)
    except Exception:
        await event.reply(f"❌ 无法找到用户 {full_username}")
        logger.info(f"[踢出] 在群组 [{chat_id:>14}] 踢出成员 {full_username} {operation_result}")
        return

    # 构造踢人权限（永久禁止查看消息）
    banned_rights = ChatBannedRights(
        until_date=None,
        view_messages=True,
        send_messages=False, send_media=False, send_stickers=False,
        send_gifs=False, send_games=False, send_inline=False, embed_links=False
    )

    # 执行踢人
    try:
        await client(EditBannedRequest(chat_id, user.id, banned_rights))
        operation_result = "操作成功"
        await event.reply(f"✅ 已踢出成员 {full_username}")
    except Exception as e:
        await event.reply(f"❌ 踢出失败：{e}")
        logger.error(f"[踢出] 在群组 [{chat_id:>14}] 踢出成员 {full_username} 失败原因：{str(e)}")
    
    # 记录结果日志
    logger.info(f"[踢出] 在群组 [{chat_id:>14}] 踢出成员 {full_username} {operation_result}")




# ---------------------------- 设置群成员为管理员 ----------------------------
@client.on(events.NewMessage(
    pattern=r'^设置管理员(?:\s+@([\w\d_]+))?$',
    incoming=True))
async def set_admin(event: events.NewMessage.Event):
    """
    用法 1：设置管理员 @username
    用法 2：先回复目标成员的消息 → 再发送 '设置管理员'
    支持普通群组、超级群组和频道，日志格式统一为 [管理] 前缀
    """
    # 只允许群内触发
    if not event.is_group:
        return await event.reply("❌ 该指令只能在群聊内使用")

    operator_id = event.sender_id
    chat = await event.get_chat()
    chat_title = getattr(chat, "title", f"id={event.chat_id}")
    is_supergroup = getattr(chat, 'megagroup', False)  # 是否为超级群组
    is_channel = event.is_channel  # 是否为频道
    is_normal_group = event.is_group and not is_supergroup and not is_channel  # 普通群组
    full_chat_id = event.chat_id  # 统一命名为full_chat_id，匹配日志格式要求
    group_type = "普通群组" if is_normal_group else "超级群组" if is_supergroup else "频道"  # 提前定义群组类型

    # ---------------------------- 权限校验1：机器人自身权限检查 ----------------------------
    try:
        bot_permissions = await client.get_permissions(full_chat_id, "me")
        
        if not bot_permissions.is_admin:
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 机器人无管理员权限，无法执行设置管理员操作")
            return await event.reply("❌ 机器人需要先成为本群管理员，才能设置其他成员为管理员")
        
        # 检查机器人是否具有“添加管理员”的权限
        if not bot_permissions.add_admins:
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 机器人没有「添加管理员」的权限，无法设置管理员")
            return await event.reply("❌ 机器人没有「添加管理员」的权限，无法设置管理员")
    except ChatAdminRequiredError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 无权限查看群权限，无法验证自身管理员身份")
        return await event.reply("❌ 机器人无权限查看群权限，请先将机器人设为管理员")

    # ---------------------------- 权限校验2：操作者权限检查 ----------------------------
    if not await is_admin(operator_id):
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 非管理员 {operator_id} 试图执行设置管理员操作，已拦截")
        return await event.reply("❌ 只有群管理员才能使用此命令")

    # ---------------------------- 1. 目标用户解析 ----------------------------
    target_entity = None
    target_mention = None
    target_username = event.pattern_match.group(1)

    try:
        if target_username:
            target_mention = f"@{target_username}"
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 收到设置管理员请求，目标：{target_mention}")
            target_entity = await client.get_entity(target_username)
        elif event.is_reply:
            reply_msg = await event.get_reply_message()
            if not (reply_msg and reply_msg.sender_id):
                raise PeerIdInvalidError("无法识别被回复者的身份")
            target_entity = await client.get_entity(reply_msg.sender_id)
            # 获取用户名，如果没有则使用显示名称
            username = getattr(target_entity, 'username', None)
            target_mention = f"@{username}" if username else get_display_name(target_entity)
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 收到设置管理员请求，目标：{target_mention}")
        else:
            return await event.reply("❌ 请在命令后写 @用户名，或直接回复目标成员的消息再发送此命令")
    except UsernameNotOccupiedError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：用户名 {target_mention} 不存在")
        return await event.reply(f"❌ 错误：用户名 {target_mention} 不存在（请检查拼写）")
    except (UserIdInvalidError, PeerIdInvalidError):
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：无法识别目标成员 {target_mention}")
        return await event.reply(f"❌ 错误：无法识别目标成员（可能是无效用户ID或未公开账号）")
    except UserNotMutualContactError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：目标成员 {target_mention} 未与机器人互相关注")
        return await event.reply(f"❌ 错误：目标成员未与机器人互相关注，无法获取其信息")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 获取目标用户信息失败：{str(e)}")
        return await event.reply(f"❌ 错误：获取目标成员信息失败，请重试")

    target_id = target_entity.id
    # 优先使用用户名，无用户名则使用显示名称
    target_username = getattr(target_entity, 'username', None)
    target_display_name = f"@{target_username}" if target_username else get_display_name(target_entity)

    # ---------------------------- 2. 检查目标成员是否在群组内 ----------------------------
    try:
        # 检查目标成员是否为群组成员
        await client.get_permissions(full_chat_id, target_entity)
    except UserNotParticipantError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：{target_mention} 不是群组成员")
        return await event.reply(f"❌ 错误：{target_display_name} 不是本群成员，请先邀请其加入群组")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 检查目标成员是否在群组内失败：{str(e)}")
        return await event.reply(f"❌ 错误：无法验证目标成员是否在群组内，请重试")

    # ---------------------------- 3. 检查目标成员是否已经是管理员 ----------------------------
    try:
        permissions = await client.get_permissions(full_chat_id, target_entity)
        if permissions.is_admin:
            # 合并日志为一条
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员请求：目标 {target_mention} 已是管理员")
            return await event.reply(f"✅ 无需重复设置：{target_display_name} 已是本群管理员")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 检查目标成员是否为管理员失败：{str(e)}")
        return await event.reply(f"❌ 错误：无法验证目标成员是否为管理员，请重试")

    # ---------------------------- 4. 分群组类型设置管理员 ----------------------------
    try:
        if is_normal_group:
            # 普通群组：无法设置管理员，跳过
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 普通群组不支持设置管理员")
            await event.reply(f"❌ 错误：普通群组无法设置管理员")
        else:
            # 超级群组/频道：使用 EditAdminRequest
            base_rights = ChatAdminRights(
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                add_admins=False,
                change_info=False,
                post_messages=False,
                edit_messages=False,
                pin_messages=False,
                manage_call=False
            )

            extra_rights = {}
            if is_channel:
                extra_rights = {"change_info": True, "post_messages": True, "edit_messages": True, "pin_messages": True, "manage_call": True}
            elif is_supergroup:
                extra_rights = {"change_info": True, "post_messages": True, "edit_messages": True, "pin_messages": True, "manage_call": True}

            # 执行基础权限设置
            channel_entity = await client.get_entity(full_chat_id)
            channel_peer = InputPeerChannel(channel_entity.id, channel_entity.access_hash)

            await client(EditAdminRequest(
                channel=channel_peer,  # 使用正确的 InputPeerChannel
                user_id=target_id,
                admin_rights=base_rights,
                rank="管理员"
            ))

            # 追加额外权限
            for perm_name, value in extra_rights.items():
                base_dict = {k: v for k, v in base_rights.to_dict().items() if not k.startswith('_')}
                new_rights = ChatAdminRights(**base_dict)
                setattr(new_rights, perm_name, value)
                try:
                    await client(EditAdminRequest(
                        channel=channel_peer,
                        user_id=target_id,
                        admin_rights=new_rights,
                        rank="管理员"
                    ))
                    base_rights = new_rights
                except RightForbiddenError:
                    logger.debug(f"[管理] 在群组 [{full_chat_id:>14}] 不支持 {perm_name} 权限，已跳过")
                    continue

            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 成功将 {target_mention} 设置为{group_type}管理员")

        # 成功回复（带群组类型提示，使用用户名格式）
        await event.reply(f"✅ 已成功在{group_type} [{chat_title}] 将 {target_display_name} 设置为管理员")

    # ---------------------------- 5. 错误处理 ----------------------------
    except UserAlreadyParticipantError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员请求无效：{target_mention} 已是管理员")
        await event.reply(f"✅ 无需重复设置：{target_display_name} 已是本群管理员")
    except ChatAdminRequiredError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：机器人非管理员")
        await event.reply("❌ 失败原因：机器人不是本群管理员，请先将机器人设为管理员")
    except RightForbiddenError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：机器人缺少设置权限")
        await event.reply("❌ 失败原因：机器人权限不足（缺少“设置管理员”的权限），请提升机器人权限")
    except (ChatIdInvalidError, PeerIdInvalidError):
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：群组ID无效（{group_type}）")
        await event.reply("❌ 失败原因：群组ID无效（可能是群组类型识别错误），建议升级为超级群组后重试")
    except UserNotParticipantError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：{target_mention} 已退出群聊")
        await event.reply(f"❌ 失败原因：{target_display_name} 已退出本群，请重新邀请后重试")
    except Exception as e:
        error_detail = str(e).split('\n')[0]
        if "not in chat" in str(e).lower() or "user not found" in str(e).lower():
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员失败：{target_mention} 不在群聊中")
            await event.reply(f"❌ 失败原因：{target_display_name} 不在本群中，请先邀请加入")
        else:
            logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 设置管理员通用错误：{error_detail}")
            await event.reply(f"❌ 失败原因：{error_detail}\n建议：若为普通群组，可尝试升级为超级群组后重试")


# ---------------------------- 移除群成员管理员身份 ----------------------------
@client.on(events.NewMessage(
    pattern=r'^移除管理员(?:\s+@([\w\d_]+))?$',          # @username 可选
    incoming=True))
async def remove_admin(event: events.NewMessage.Event):
    """
    用法 1：移除管理员 @username
    用法 2：先回复目标成员的消息，再发送 '移除管理员'
    """

    # 只允许群内触发
    if not event.is_group:
        return await event.reply("❌ 该指令只能在群聊内使用")

    operator_id = event.sender_id
    chat = await event.get_chat()
    chat_title = getattr(chat, "title", f"id={event.chat_id}")
    is_supergroup = getattr(chat, 'megagroup', False)  # 是否为超级群组
    is_channel = event.is_channel  # 是否为频道
    is_normal_group = event.is_group and not is_supergroup and not is_channel  # 普通群组
    full_chat_id = event.chat_id  # 统一命名为full_chat_id
    group_type = "普通群组" if is_normal_group else "超级群组" if is_supergroup else "频道"

    # ---------------------------- 权限校验1：机器人自身权限检查 ----------------------------
    try:
        bot_permissions = await client.get_permissions(full_chat_id, "me")
        
        if not bot_permissions.is_admin:
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 机器人无管理员权限，无法执行移除管理员操作")
            return await event.reply("❌ 机器人需要先成为本群管理员，才能移除其他成员的管理员权限")
        
        # 检查机器人是否有移除管理员的权限（添加管理员权限通常包含移除权限）
        if not bot_permissions.add_admins:
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 机器人没有「添加/移除管理员」的权限")
            return await event.reply("❌ 机器人没有「管理管理员」的权限，无法执行此操作")
    except ChatAdminRequiredError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 无权限查看群权限，无法验证自身管理员身份")
        return await event.reply("❌ 机器人无权限查看群权限，请先将机器人设为管理员")

    # ---------------------------- 权限校验2：操作者权限检查 ----------------------------
    if not await is_admin(operator_id):
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 非管理员 {operator_id} 试图执行移除管理员操作，已拦截")
        return await event.reply("❌ 只有群管理员才能使用此命令")

    # ---------------------------- 1. 目标用户解析 ----------------------------
    target_entity = None
    target_mention = None  # 日志中显示的目标标识
    target_username = event.pattern_match.group(1)

    try:
        if target_username:  # @username 方式
            target_mention = f"@{target_username}"
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 请求取消 {target_mention} 的管理员权限")
            target_entity = await client.get_entity(target_username)
        elif event.is_reply:  # 回复方式
            reply_msg = await event.get_reply_message()
            if not (reply_msg and reply_msg.sender_id):
                raise PeerIdInvalidError("无法识别被回复者的身份")
            target_entity = await client.get_entity(reply_msg.sender_id)
            # 获取用户名，如果没有则使用显示名称
            username = getattr(target_entity, 'username', None)
            target_mention = f"@{username}" if username else get_display_name(target_entity)
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 请求取消 {target_mention} 的管理员权限")
        else:
            return await event.reply("❌ 请在命令后写 @用户名，或直接回复目标成员的消息再发送此命令")
    except UsernameNotOccupiedError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：用户名 {target_mention} 不存在")
        return await event.reply(f"❌ 错误：用户名 {target_mention} 不存在（请检查拼写）")
    except (UserIdInvalidError, PeerIdInvalidError):
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：无法识别目标成员 {target_mention}")
        return await event.reply(f"❌ 错误：无法识别目标成员（可能是无效用户ID或未公开账号）")
    except UserNotMutualContactError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：目标成员 {target_mention} 未与机器人互相关注")
        return await event.reply(f"❌ 错误：目标成员未与机器人互相关注，无法获取其信息")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 获取目标用户信息失败：{str(e)}")
        return await event.reply(f"❌ 错误：获取目标成员信息失败，请重试")

    target_id = target_entity.id
    # 优先使用用户名，无用户名则使用显示名称
    target_username = getattr(target_entity, 'username', None)
    target_display_name = f"@{target_username}" if target_username else get_display_name(target_entity)

    # ---------------------------- 2. 检查目标成员是否在群组内 ----------------------------
    try:
        await client.get_permissions(full_chat_id, target_entity)
    except UserNotParticipantError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：{target_mention} 不是群组成员")
        return await event.reply(f"❌ 错误：{target_display_name} 不是本群成员")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 检查目标成员是否在群组内失败：{str(e)}")
        return await event.reply(f"❌ 错误：无法验证目标成员是否在群组内，请重试")

    # ---------------------------- 3. 检查目标是否是管理员 ----------------------------
    try:
        perms = await client.get_permissions(full_chat_id, target_entity)
        if not getattr(perms, "is_admin", False):  # 检查是否为管理员
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员请求无效：{target_mention} 并非管理员")
            return await event.reply(f"ℹ️ 无需操作：{target_display_name} 当前并非管理员")
    except Exception as e:
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 检查目标成员是否为管理员失败：{str(e)}")
        return await event.reply(f"❌ 错误：无法验证目标成员是否为管理员，请重试")

    # ---------------------------- 4. 执行移除管理员操作 ----------------------------
    try:
        if is_normal_group:
            # 普通群组：无法移除管理员（通常需要手动操作）
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 普通群组不支持移除管理员")
            await event.reply(f"❌ 错误：普通群组无法移除管理员，请手动操作")
        else:
            # 构造空权限（降级为普通成员）
            no_rights = ChatAdminRights()  

            # 超级群组/频道需要使用InputPeerChannel
            channel_entity = await client.get_entity(full_chat_id)
            channel_peer = InputPeerChannel(channel_entity.id, channel_entity.access_hash)

            await client(EditAdminRequest(
                channel=channel_peer,
                user_id=target_id,
                admin_rights=no_rights,
                rank=""  # 清空管理员头衔
            ))
            
            logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 已取消 {target_mention} 的管理员权限")
            await event.reply(f"✅ 已成功在{group_type} [{chat_title}] 取消 {target_display_name} 的管理员权限")

    # ---------------------------- 5. 错误处理 ----------------------------
    except ChatAdminRequiredError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：机器人非管理员")
        await event.reply("❌ 失败原因：机器人不是本群管理员，请先将机器人设为管理员")
    except RightForbiddenError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：机器人缺少权限")
        await event.reply("❌ 失败原因：机器人权限不足（缺少“管理管理员”的权限），请提升机器人权限")
    except UserNotParticipantError:
        logger.info(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员失败：{target_mention} 已退出群聊")
        await event.reply(f"❌ 失败原因：{target_display_name} 已退出本群")
    except Exception as e:
        error_detail = str(e).split('\n')[0]
        logger.error(f"[管理] 在群组 [{full_chat_id:>14}] 移除管理员通用错误：{error_detail}")
        await event.reply(f"❌ 失败原因：{error_detail}\n建议：若为普通群组，可尝试升级为超级群组后重试")

    


# ---------------------------- 拉群功能（创建群组并邀请成员） ----------------------------
@client.on(events.NewMessage(pattern=r'^拉群$', incoming=True))
async def create_new_group(event):
    user_id = event.sender_id
    group_name = f"{datetime.now():%Y%m%d-%H%M%S} 对接群"

    logger.info(f"[拉群] 收到拉群命令，管理员 {user_id} 正在创建群组…")

    # 管理员权限校验
    if not await is_admin(user_id):
        return await event.reply("❌ 只有管理员才能使用“拉群”命令")

    logger.info(f"[拉群] 管理员 {user_id} 校验通过，正在创建群组：{group_name}")
    reply_msg = await event.reply("⏳ 正在创建群组，请稍候…")

    # 新增：用于存储管理员设置结果（成功/失败信息），后续合并到最终回复
    admin_result_msg = ""
    full_chat_id = ""  # 初始化群组ID，避免后续引用报错
    invite_link = "无法生成邀请链接"  # 初始化邀请链接，默认值

    try:
        db = await DB.get_conn()
        # 从 staff 表读取 user_id + access_hash（适配新表结构）
        async with db.execute("SELECT user_id, access_hash FROM staff") as cursor:
            rows = await cursor.fetchall()
        # 转为字典列表，便于构造实体（过滤空值）
        staff_list = [{"user_id": r[0], "access_hash": r[1]} for r in rows if r[0] and r[1]]
        
        # 确保发起人（当前管理员）在邀请列表中
        if not any(m["user_id"] == user_id for m in staff_list):
            try:
                user = await client.get_entity(user_id)
                staff_list.append({"user_id": user_id, "access_hash": user.access_hash})
                logger.info(f"[拉群] 已补充发起人 {user_id} 到邀请列表")
            except Exception as e:
                logger.warning(f"[拉群] 无法获取发起人 {user_id} 的信息，可能无法加入群组：{str(e)[:30]}...")
                await reply_msg.edit(f"⚠️ 注意：无法获取您的账号信息，创建群组后需手动加入\n⏳ 继续创建群组中...")

        # 1. 创建新超级群组
        result = await client(CreateChannelRequest(
            title=group_name, about="", megagroup=True  # megagroup=True 表示创建超级群组
        ))
        new_channel = result.chats[0]
        full_chat_id = get_peer_id(new_channel)  # 赋值群组ID
        logger.info(f"[拉群] 创建群 [{full_chat_id:>14}] 成功，群组名称：{group_name}")
        await reply_msg.edit(f"✅ 群组创建成功：{group_name}\n⏳ 正在邀请成员加入...")

        # 2. 构造用户实体列表（避免依赖缓存）
        user_entities = []
        invalid_ids = []
        for member in staff_list:
            try:
                # 手动构造 InputPeerUser（需确保 user_id 和 access_hash 匹配）
                entity = InputPeerUser(
                    user_id=member["user_id"],
                    access_hash=member["access_hash"]
                )
                user_entities.append(entity)
            except Exception as e:
                invalid_ids.append(str(member["user_id"]))
                logger.warning(f"[拉群] 无法构造用户 {member['user_id']} 的实体：{str(e)[:20]}...")

        # 3. 邀请成员（核心：优化限速提示）
        invite_link = ""  # 初始化邀请链接变量
        if user_entities:
            try:
                await client(InviteToChannelRequest(
                    channel=new_channel, 
                    users=user_entities
                ))
                logger.info(f"[邀请] 已在群 [{full_chat_id:>14}] 成功邀请 {len(user_entities)} 位成员")
                await reply_msg.edit(f"✅ 群组创建成功：{group_name}\n✅ 已邀请 {len(user_entities)} 位成员加入\n⏳ 正在设置管理员权限...")
            # 专门处理 Telegram 频率限制错误
            except FloodWaitError as e:
                wait_time = e.seconds
                logger.error(f"[拉群] 在群组 [{full_chat_id:>14}] 邀请成员触发频率限制，需等待 {wait_time} 秒")
                
                # 生成邀请链接（备选方案）
                try:
                    invite = await client(ExportChatInviteRequest(
                        peer=new_channel, 
                        expire_date=int(time.time()) + 24 * 3600  # 24小时有效
                    ))
                    invite_link = invite.link
                except Exception as inner_e:
                    invite_link = "无法生成邀请链接（权限不足）"
                    logger.error(f"[拉群] 生成邀请链接失败：{str(inner_e)}")
            # 处理其他邀请错误
            except Exception as e:
                logger.error(f"[拉群] 邀请成员失败：{str(e)}", exc_info=True)
                await reply_msg.edit(f"✅ 群组创建成功，但邀请成员失败：{str(e)[:30]}...\n⏳ 尝试设置管理员权限...")
        # 无有效成员可邀请的处理
        else:
            logger.warning(f"[拉群] 无有效成员可邀请（无效用户ID：{','.join(invalid_ids) if invalid_ids else '无'}）")
            await reply_msg.edit(f"✅ 群组创建成功：{group_name}\n⚠️ 无有效成员可邀请（部分用户ID/哈希无效）\n⏳ 尝试设置管理员权限...")

        # 4. 为成员分配管理员权限（核心修改：结果存入 admin_result_msg）
        # 只有在未触发频率限制且有有效成员时执行
        if user_entities and not (isinstance(locals().get('e'), FloodWaitError)):
            rights = ChatAdminRights(
                change_info=True, post_messages=True, edit_messages=True,
                delete_messages=True, ban_users=True, invite_users=True,
                pin_messages=True, add_admins=True, manage_call=True
            )
            success_admins = []
            fail_admins = []

            # 生成24小时有效邀请链接（用于权限设置失败时备用）
            try:
                invite = await client(ExportChatInviteRequest(
                    peer=new_channel, 
                    expire_date=int(time.time()) + 24 * 3600
                ))
                invite_link = invite.link
            except Exception as e:
                invite_link = "无法生成邀请链接"
                logger.error(f"[拉群] 生成管理员备用邀请链接失败：{str(e)}")

            # 遍历成员设置管理员
            for member in staff_list:
                sid = member["user_id"]
                try:
                    await client(EditAdminRequest(
                        channel=new_channel, 
                        user_id=sid,
                        admin_rights=rights, 
                        rank="管理员"
                    ))
                    success_admins.append(str(sid))
                except Exception as e:
                    fail_admins.append(str(sid))
                    logger.warning(f"⚠️ 无法将用户 {sid} 设置为管理员：{str(e)[:30]}...")
                    # 隐私设置导致失败时，向用户发送提醒
                    if "privacy" in str(e).lower() or "mutual" in str(e).lower():
                        try:
                            await client.send_message(
                                sid,
                                "⚠️ 机器人无法将你设为群管理员，请检查隐私设置：\n"
                                "1. 打开 Telegram → 设置 → 隐私与安全\n"
                                "2. 找到“群组与频道” → “谁可以将我添加至群组”\n"
                                "3. 设置为“所有人”或“我的联系人”\n\n"
                                f"📱 临时加入链接（24h有效）：{invite_link}"
                            )
                        except Exception:
                            logger.warning(f"⚠️ 无法向用户 {sid} 发送隐私提醒")

            # 核心修改：将管理员设置结果存入 admin_result_msg（不再单独发送）
            admin_result_msg = "✅ 管理员设置完成：\n"
            if success_admins:
                admin_result_msg += f"✅ 成功设置 {len(success_admins)} 位管理员\n"
            if fail_admins:
                admin_result_msg += f"⚠️ 无法设置 {len(fail_admins)} 位管理员（ID：{','.join(fail_admins[:5])}{'...' if len(fail_admins)>5 else ''}）\n"
            logger.info(f"[拉群] 在群组 [{full_chat_id:>14}] 管理员设置完成（成功{len(success_admins)}人/失败{len(fail_admins)}人）")
        # 频率限制时补充生成邀请链接
        elif not invite_link:
            try:
                invite = await client(ExportChatInviteRequest(
                    peer=new_channel, 
                    expire_date=int(time.time()) + 24 * 3600
                ))
                invite_link = invite.link
            except Exception:
                invite_link = "无法生成邀请链接"

        # 5. 向发起人发送最终结果（核心修改：合并 admin_result_msg）
        try:
            # 合并后的私聊最终消息
            final_private_msg = (
                f"🎉 拉群操作完成！\n"
                f"{admin_result_msg}"  # 插入管理员设置结果
                f"群组名称：{group_name}\n"
                f"群组ID：{full_chat_id}\n"
                f"邀请链接（24小时有效）：{invite_link}\n"
                f"💡 提示：若成员无法加入，可转发此链接"
            )
            await client.send_message(user_id, final_private_msg)

        except Exception as e:
            logger.warning(f"[拉群] 无法向管理员 {user_id} 私聊发送结果：{str(e)}")

        # 群内最终反馈（核心修改：合并 admin_result_msg）
        if event.is_group:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', f'id={event.chat_id}')
            # 合并后的群内最终消息
            final_group_msg = (
                f"✅ 拉群操作已完成！\n"
                f"{admin_result_msg}"  # 插入管理员设置结果
                f"新群名称：{group_name}\n"
                f"群组ID：{full_chat_id}\n"  # 群内也展示群组ID，与私聊一致
                f"📱 详细结果已私聊发送给你\n"
                f"🔗 若需手动邀请：{invite_link}"
            )
            await reply_msg.edit(final_group_msg)
            logger.info(f"[拉群] 已向会话 {chat_title} 发送合并后的最终反馈")

    # 全局异常处理（覆盖所有步骤的错误）
    except Exception as e:
        # 区分频率限制错误（创建群组时也可能触发）
        if isinstance(e, FloodWaitError):
            wait_time = e.seconds
            logger.error(f"[拉群] 创建群组触发频率限制，需等待 {wait_time} 秒")
            # 生成邀请链接（若已创建群组）
            try:
                invite = await client(ExportChatInviteRequest(
                    peer=new_channel, 
                    expire_date=int(time.time()) + 24 * 3600
                ))
                invite_link = invite.link
            except Exception:
                invite_link = "无法生成邀请链接"
            # 合并异常场景的最终反馈
            final_msg = (
                f"✅ 拉群操作已完成！\n"
                f"{admin_result_msg}"  # 即使异常，也带上已获取的管理员结果
                f"新群名称：{group_name}\n"
                f"群组ID：{full_chat_id}\n"
                f"📱 详细结果已私聊发送给你\n"
                f"🔗 若需手动邀请：{invite_link}"
            )
            await reply_msg.edit(final_msg)
        else:
            error_msg = f"❌ 群创建或邀请时出错：{str(e)[:50]}...\n请查看日志获取详细信息"
            logger.error(f"[拉群] 全局异常：{str(e)}", exc_info=True)
            try:
                await reply_msg.edit(error_msg)
            except Exception:
                await event.reply(error_msg)
        logger.warning(f"[拉群] 管理员 {user_id} 拉群操作失败：{str(e)[:30]}...")

    

# ---------------------------- 更改群名功能 ----------------------------
@client.on(events.NewMessage(pattern=r'更改群名\s+(.+)'))
async def change_group_name(event):
    logger.info(f"收到命令：{event.raw_text}")  # 确认事件是否触发

    user_id = event.sender_id
    chat_id = event.chat_id
    new_group_name = event.pattern_match.group(1)  # 从命令中提取新群名

    # 获取群组信息，代替 chat_id
    group = await client.get_entity(chat_id)
    group_name = group.title if isinstance(group, (Channel, Chat)) else "未知群组"

    logger.info(f"用户 {user_id} 请求更改群名：来自群组 {group_name}，新群名：{new_group_name}")

    # 校验管理员权限
    if not await is_admin(user_id):
        logger.warning(f"用户 {user_id} 没有管理员权限，无法执行更改群名操作")
        return await event.reply("❌ 只有管理员才能使用“更改群名”命令")

    # 确保群名不为空
    if not new_group_name:
        logger.warning("新群名为空，无法执行更改群名操作")
        return await event.reply("❌ 请提供新的群名")

    try:
        # 获取群组的详细信息
        logger.info(f"成功获取群组信息：{group.title}")

        # 创建 InputPeerChannel
        channel = InputPeerChannel(group.id, group.access_hash)

        # 使用 EditTitleRequest 来更改群名
        response = await client(functions.channels.EditTitleRequest(
            channel=channel,    # 目标群组
            title=new_group_name  # 新的群名称
        ))

        logger.info(f"群组 {group_name} 名称已成功更改为：{new_group_name}")

        # 回复管理员
        await event.reply(f"✅ 群名已成功更改为：{new_group_name}")

    except ChannelPrivateError:
        logger.error(f"群组 {group_name} 是私密的，无法更改群名。")
        await event.reply(f"❌ 群组 {group_name} 是私密的，无法更改群名。")
    except UserNotParticipantError:
        logger.error(f"用户 {user_id} 不是该群的成员，无法更改群名。")
        await event.reply(f"❌ 用户 {user_id} 不是该群的成员，无法更改群名。")
    except FloodWaitError as e:
        logger.error(f"更改群名失败，由于API限流，需要等待 {e.seconds} 秒。")
        await event.reply(f"❌ 更改群名失败，由于API限流，请稍等 {e.seconds} 秒后重试。")
    except Exception as e:
        logger.error(f"更改群名失败：{e}")
        await event.reply(f"❌ 更改群名失败：{e}")


# ---------------------------- 群组操作公共工具函数 ----------------------------
def create_pending_store():
    """创建用于存储待确认操作的临时缓存"""
    return {}

async def verify_operation_permissions(event, user_id, chat_id, pending_store, operation_type):
    """
    验证操作权限和待确认状态
    operation_type: 操作类型，"disband" 表示解散群组，"leave" 表示退群
    返回值: (是否验证通过, 错误消息)
    """
    # 检查是否在群组中
    if not event.is_group:
        return (False, "❌ 该命令只能在群组内使用")
    
    # 检查是否为管理员
    if not await is_admin(user_id):
        return (False, "❌ 你没有权限执行此操作")
    
    # 检查是否有对应的待确认请求
    if chat_id not in pending_store or pending_store.get(chat_id) != user_id:
        base_command = "解散群组" if operation_type == "disband" else "退群"
        return (False, f"ℹ️ 尚未检测到你的“{base_command}”请求，若要{base_command}请先发送“{base_command}”。")
    
    return (True, None)

async def get_group_info(client, chat_id):
    """获取群组信息并返回群组对象和名称"""
    group = await client.get_entity(chat_id)
    if isinstance(group, (Channel, Chat)):
        group_name = group.title
    elif hasattr(group, 'title'):
        group_name = group.title
    else:
        group_name = "未知群组"
    return group, group_name

async def handle_operation_cancellation(event, user_id, chat_id, pending_store, operation_name, operation_type):
    """处理操作取消的公共逻辑"""
    group, group_name = await get_group_info(client, chat_id)
    
    # 记录取消日志
    logger.info(f"[取消] 在群组 [{chat_id:>14}] ({group_name}) 的{operation_name}请求已取消，管理员 {user_id}")
    
    # 验证权限
    is_valid, error_msg = await verify_operation_permissions(event, user_id, chat_id, pending_store, operation_type)
    if not is_valid:
        return await event.reply(error_msg)
    
    # 移除待确认状态
    pending_store.pop(chat_id, None)
    
    # 回复取消成功
    await event.reply(f"✅ 已取消{operation_name} {group_name} 请求。")


# ---------------------------- 解散群组功能（双重确认） ----------------------------

# 全局临时缓存：记录哪些群正在等待确认解散
pending_disband = create_pending_store()

@client.on(events.NewMessage(pattern=r'^解散群组$', incoming=True))
async def disband_group_start(event):
    """管理员在群里发“解散群组”进入待确认流程"""
    chat_id = event.chat_id
    user_id = event.sender_id
    
    group, group_name = await get_group_info(client, chat_id)
    logger.info(f"[解散] 解散群 [{event.chat_id:>14}] 群组名称：{group_name}")
    
    # 权限校验
    if not event.is_group or not await is_admin(user_id):
        logger.warning(f"用户 {user_id} 权限不足，无法发起解散请求")
        return
    
    # 检查机器人是否为创建者
    try:
        bot_permissions = await client.get_permissions(chat_id, 'me')
        if not bot_permissions.is_creator:
            logger.info(f"[检查] 机器人 [{chat_id:>14}] 无创建者权限，已拒绝解散请求")
            return await event.reply("❌ 机器人必须是群组创建者才能执行解散操作")
        logger.info(f"[检查] 机器人 [{chat_id:>14}] 权限成功，允许继续操作，等待管理确认解散")
    except Exception as e:
        logger.error(f"检查创建者权限失败 (群组ID:{chat_id}): {e}", exc_info=True)
        return await event.reply("❌ 检查权限时出错，请稍后重试")
    
    # 检查是否已有待确认请求
    if chat_id in pending_disband and pending_disband[chat_id] == user_id:
        logger.info(f"群组 {chat_id} 已有待确认的解散请求，通知用户")
        return await event.reply("ℹ️ 你之前已经发起了解散请求，请回复“确认解散”或“取消解散”。")
    
    # 记录待确认状态
    pending_disband[chat_id] = user_id
    
    # 发送确认提示
    await event.reply(
        f"⚠️ 你正在请求解散群组 {group_name}！此操作不可恢复。\n"
        "如果你确定要解散，请回复：确认解散\n"
        "如果想取消本次操作，请回复：取消解散"
    )

@client.on(events.NewMessage(pattern=r'^确认解散$', incoming=True))
async def disband_group_confirm(event):
    """管理员确认解散"""
    chat_id = event.chat_id
    user_id = event.sender_id
    
    group, group_name = await get_group_info(client, chat_id)
    logger.info(f"[确认] 已确认 [{event.chat_id:>14}] 收到解散群组请求：{group_name}")
    
    # 验证操作权限，传入 operation_type="disband"
    is_valid, error_msg = await verify_operation_permissions(event, user_id, chat_id, pending_disband, "disband")
    if not is_valid:
        return await event.reply(error_msg)
    
    try:
        # 执行解散操作
        await client(DeleteChannelRequest(channel=chat_id))
        await GroupJoinTimeManager.delete_join_time(chat_id)
        logger.info(f"[删除] 已删除 [{chat_id}] 群组的加入时间，并已在数据库更新完成")
        
        # 清除待确认状态
        pending_disband.pop(chat_id, None)
        
        # 通知管理员操作结果
        try:
            await client.send_message(user_id, f"✅ 群组 {group_name} 已被成功解散。")
            logger.info(f"[完成] 已完成 [{event.chat_id:>14}] {group_name} 已解散，私聊管理员确认")
        except:
            pass
    except Exception as e:
        pending_disband.pop(chat_id, None)
        await event.reply(f"❌ 解散群组失败：{e}")
        logger.error(f"解散群组 {group_name} 时出错: {e}")

@client.on(events.NewMessage(pattern=r'^取消解散$', incoming=True))
async def disband_group_cancel(event):
    """处理解散操作的取消"""
    await handle_operation_cancellation(
        event, 
        event.sender_id, 
        event.chat_id, 
        pending_disband, 
        "解散群组",
        "disband"  # 传入 operation_type="disband"
    )


# ---------------------------- 退群功能（双重确认） ----------------------------

# 全局临时缓存：记录哪些群正在等待确认退群
pending_leave = create_pending_store()

@client.on(events.NewMessage(pattern=r"^退群$", incoming=True))
async def leave_group_start(event):
    """管理员在群里发“退群”进入待确认流程"""
    user_id = event.sender_id
    chat_id = event.chat_id
    
    group, group_name = await get_group_info(client, chat_id)
    logger.info(f"[退群] 请求群 [{chat_id:>14}] 退群，群组名称：{group_name}")
    
    # 验证权限，传入 operation_type="leave"
    is_valid, error_msg = await verify_operation_permissions(event, user_id, chat_id, pending_leave, "leave")
    if not is_valid and "尚未检测到" not in error_msg:  # 排除未检测到请求的情况
        return await event.reply(error_msg)
    
    # 发送确认提示
    await event.reply(
        f"⚠️ 你正在请求让机器人退出群组 {group_name}！此操作不可恢复。\n"
        "如果你确定要退群，请回复：确认退群\n"
        "如果想取消本次操作，请回复：取消退群"
    )
    
    # 记录待确认状态
    pending_leave[chat_id] = user_id
    logger.info(f"[检查] 已记录 [{chat_id:>14}] 的退群请求，请等待管理员确认")

@client.on(events.NewMessage(pattern=r"^确认退群$", incoming=True))
async def leave_group_confirm(event):
    """管理员确认退群"""
    chat_id = event.chat_id
    user_id = event.sender_id
    
    group, group_name = await get_group_info(client, chat_id)
    logger.info(f"[确认] 已确认 [{event.chat_id:>14}] 收到确认退群请求：{group_name}")
    
    # 验证操作权限，传入 operation_type="leave"
    is_valid, error_msg = await verify_operation_permissions(event, user_id, chat_id, pending_leave, "leave")
    if not is_valid:
        return await event.reply(error_msg)
    
    try:
        # 发送退群消息
        farewell_message = "江湖路远，爱意永存💖"
        await event.reply(farewell_message)
        
        # 执行退群操作
        if isinstance(group, Channel):
            peer = InputPeerChannel(group.id, group.access_hash)
            await client(LeaveChannelRequest(peer))
        else:
            await client.delete_dialog(chat_id)
        
        # 更新数据库
        await GroupJoinTimeManager.delete_join_time(chat_id)
        logger.info(f"[删除] 已删除 [{event.chat_id:>14}] 群组的加入时间，并已在数据库更新完成")
        
        # 清除待确认状态
        pending_leave.pop(chat_id, None)
        
        # 通知管理员操作结果
        try:
            await client.send_message(user_id, f"✅ 机器人已成功退出群组 `{group_name}`")
            logger.info(f"[完成] 已完成 [{event.chat_id:>14}] 已退出 {group_name}，私聊管理员确认")
        except Exception as e:
            logger.warning(f"无法向管理员发送退群确认：{e}")
    except Exception as e:
        logger.error(f"退群失败：{e}")
        return await event.reply(f"❌ 退群失败：{e}")

@client.on(events.NewMessage(pattern=r"^取消退群$", incoming=True))
async def leave_group_cancel(event):
    """处理退群操作的取消"""
    await handle_operation_cancellation(
        event, 
        event.sender_id, 
        event.chat_id, 
        pending_leave, 
        "退出群组",
        "leave"  # 传入 operation_type="leave"
    )
    

# ---------------------------- 消息通知功能公共工具函数 ----------------------------
async def verify_group_and_permissions(event):
    """
    验证是否为群组消息、是否为历史消息以及管理员权限
    返回值: (是否验证通过, 错误消息/None)
    """
    # 验证是否为群组消息
    if not event.is_group:
        return (False, "❌ 请在群组中发送该指令")
    
    chat_id = event.chat_id
    message_time = int(event.date.timestamp())
    
    # 过滤历史消息
    if message_time < start_time:
        logger.debug(f"跳过历史消息（消息时间：{message_time}, 启动时间：{start_time}）")
        return (False, None)  # 不回复历史消息
    
    # 验证管理员权限
    if not await is_admin(event.sender_id):
        return (False, "❌ 你没有权限执行此操作")
    
    return (True, None)

async def get_existing_users(db, chat_id):
    """获取群组中已存在的通知用户列表"""
    async with db.execute("SELECT usernames FROM mentions WHERE group_id = ?", (chat_id,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row[0].strip():
            return []
        # 清洗数据：拆分、去空、去重
        return [u.strip() for u in row[0].split(',') if u.strip()]


# ---------------------------- 消息通知功能（添加通知用户） ----------------------------
@client.on(events.NewMessage(pattern=r"^消息通知\s+((?:@\w+\s*)+)$", incoming=True))
async def add_mentions(event):
    # 验证群组和权限
    is_valid, error_msg = await verify_group_and_permissions(event)
    if not is_valid:
        if error_msg:
            return await event.reply(error_msg)
        return  # 历史消息不回复

    chat_id = event.chat_id
    
    # 提取@用户（去除@符号和空格）
    input_usernames = [u.lstrip('@').strip() for u in event.pattern_match.group(1).split()]
    input_usernames = [u for u in input_usernames if u]  # 过滤空值
    if not input_usernames:
        return await event.reply("❌ 未识别到有效用户名，请使用@用户名格式")

    db = await DB.get_conn()
    already_added = []
    newly_added = []

    # 查询现有用户列表（使用公共函数）
    existing_users = await get_existing_users(db, chat_id)

    # 去重处理（区分已存在和新添加）
    for username in input_usernames:
        if username in existing_users:
            already_added.append(username)
        else:
            existing_users.append(username)
            newly_added.append(username)

    # 保存更新后的用户列表（用逗号拼接）
    if newly_added:
        updated_usernames = ','.join(existing_users)
        await db.execute("""
            INSERT OR REPLACE INTO mentions (group_id, usernames) 
            VALUES (?, ?)
        """, (chat_id, updated_usernames))
        await db.commit()

    # 构建响应消息
    response = []
    if already_added:
        response.append(f"⚠ 以下用户已在通知列表中：{', '.join(already_added)}")
    if newly_added:
        response.append(f"✅ 已添加新通知用户：{', '.join(newly_added)}")
    if not response:
        response.append("⚠ 未添加任何新用户（全部已存在）")

    await event.reply("\n".join(response))
    logger.info(f"管理员 {event.sender_id} 在群组 [{chat_id}] 添加通知用户：新增{len(newly_added)}位，重复{len(already_added)}位")


# ---------------------------- 消息通知功能（查看通知用户） ----------------------------
@client.on(events.NewMessage(pattern="查看通知", incoming=True))
async def view_mentions(event):
    # 验证群组和权限
    is_valid, error_msg = await verify_group_and_permissions(event)
    if not is_valid:
        if error_msg:
            return await event.reply(error_msg)
        return  # 历史消息不回复

    chat_id = event.chat_id
    db = await DB.get_conn()
    
    # 查询现有用户列表（使用公共函数）
    existing_users = await get_existing_users(db, chat_id)

    if not existing_users:
        return await event.reply("当前群组没有消息通知用户")

    # 拆分并格式化用户列表
    usernames = [f"@{u}" for u in existing_users]
    text = "📋 当前群组消息通知用户列表：\n" + "\n".join(usernames)
    await event.reply(text)


# ---------------------------- 消息通知功能（删除通知用户） ----------------------------
@client.on(events.NewMessage(pattern="删除通知"))
async def delete_mention(event):
    # 验证群组和权限
    is_valid, error_msg = await verify_group_and_permissions(event)
    if not is_valid:
        if error_msg:
            return await event.reply(error_msg)
        return  # 历史消息不回复

    chat_id = event.chat_id
    
    # 解析要删除的用户名（支持@用户名或引用消息）
    mentions = event.raw_text.strip().split()
    usernames = []
    if len(mentions) > 1:
        # 从指令中提取@用户名（如“删除通知 @user1 @user2”）
        usernames = [u.lstrip('@').strip() for u in mentions[1:] if u.lstrip('@').strip()]
    else:
        # 从引用消息中提取用户名
        reply = await event.get_reply_message()
        if not reply or not reply.sender or not reply.sender.username:
            return await event.reply("❌ 请使用“删除通知 @用户名”格式，或引用要删除的成员")
        usernames = [reply.sender.username.strip()]

    if not usernames:
        return await event.reply("❌ 未识别到有效用户名")

    db = await DB.get_conn()
    deleted_users = []
    not_found_users = []

    # 查询现有用户列表（使用公共函数）
    existing_users = await get_existing_users(db, chat_id)

    if not existing_users:
        return await event.reply("❌ 当前群组没有消息通知用户，无需删除")

    # 筛选要删除的用户
    for username in usernames:
        if username in existing_users:
            deleted_users.append(username)
            existing_users.remove(username)  # 从列表中移除
        else:
            not_found_users.append(username)

    # 更新数据库（若剩余用户为空则删除行，否则更新字符串）
    if deleted_users:
        if existing_users:
            updated_usernames = ','.join(existing_users)
            await db.execute("""
                UPDATE mentions 
                SET usernames = ? 
                WHERE group_id = ?
            """, (updated_usernames, chat_id))
        else:
            # 全部删除时，直接删掉这一行
            await db.execute("DELETE FROM mentions WHERE group_id = ?", (chat_id,))
        await db.commit()

    # 构建响应消息
    response = []
    if deleted_users:
        response.append(f"✅ 已删除通知用户：{', '.join(deleted_users)}")
    if not_found_users:
        response.append(f"⚠ 未找到以下用户：{', '.join(not_found_users)}")
    if not response:
        response.append("⚠ 未删除任何用户")

    await event.reply("\n".join(response))
    logger.info(f"管理员 {event.sender_id} 在群组 [{chat_id}] 删除通知用户：成功{len(deleted_users)}位，未找到{len(not_found_users)}位")





# —— 常量定义 —— #
# Telegram配置
MAX_CAPTION_LENGTH = 1024  # 最大标题长度

# Google API配置
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILES = {
    'pay': {
        'client_secret': 'credentials.json',
        'token': 'token.json'
    }
}


# 缓存配置
TASK_CACHE = {}  # 任务状态缓存：存储任务哈希及状态

# 连接池配置
GMAIL_SERVICE_POOL = {
    'connections': {},        # 存储实际连接
    'last_used': {},          # 记录最后使用时间
    'max_connections': 5,     # 最大连接数
    'timeout': 300            # 连接超时时间(秒)
}
FASTMAIL_CONN_POOL = {
    'connections': {},
    'last_used': {},
    'max_connections': 5,
    'timeout': 300
}

# 正则表达式
NAME_PATTERN = re.compile(r'^[\u4e00-\u9fa5a-zA-Z·\-\']+[·\-\']?[\u4e00-\u9fa5a-zA-Z]*$')  # 姓名验证

# —— 全局变量与锁 —— #
gmail_service_lock = asyncio.Lock()  # Gmail服务创建的线程安全锁


# —— 任务控制类 —— #
class TaskControl:
    """任务独立的控制类，存储每个任务的终止状态和匹配数量"""
    def __init__(self):
        self.terminate = False  # 控制当前任务终止
        self.matched_count = 0  # 记录当前任务的匹配数量

class GmailTaskState:
    """Gmail任务状态存储，避免全局变量冲突"""
    def __init__(self):
        self.terminate = False
        self.matched_count = 0


def resource_path(relative_path):
    """生成平台兼容的路径（自动处理斜杠问题）"""
    return os.path.abspath(os.path.join(os.getcwd(), relative_path))

def format_chinese_datetime(datetime_str: str) -> str:
    """公共时间格式化：将 yyyy-mm-dd HH:MM:SS 转为中文时间（带北京时间标注）"""
    if not datetime_str or '-' not in datetime_str:
        return datetime_str
    try:
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").strftime("%Y年%m月%d日 %H:%M:%S（北京时间）")
    except Exception:
        return datetime_str

def extract_sender_info(sender_email_str: str) -> tuple[str, str]:
    """公共发件人解析：从「名称 <邮箱>」格式中提取名称和纯邮箱地址"""
    sender_email_str = sender_email_str or '未知邮箱'
    if '<' in sender_email_str:
        return (
            sender_email_str.split('<')[0].strip(),
            sender_email_str.split('<')[-1].strip('>')
        )
    return (sender_email_str.strip(), sender_email_str.strip())

def get_script_directory():
    """获取当前脚本所在的目录"""
    return os.path.dirname(os.path.abspath(__file__))

def create_temp_dirs(prefixes: list) -> dict:
    """
    创建临时目录到脚本目录的temp文件夹中
    每个前缀生成一个唯一的子目录
    """
    # 获取脚本所在目录
    script_dir = get_script_directory()
    # 定义temp文件夹路径（脚本目录下的temp）
    base_temp_dir = os.path.join(script_dir, "temp")
    
    # 确保基础temp文件夹存在
    os.makedirs(base_temp_dir, exist_ok=True)
    
    dirs = {}
    for prefix in prefixes:
        # 生成唯一的目录名（前缀+随机字符串，避免冲突）
        unique_id = uuid.uuid4().hex[:8]  # 8位随机字符串
        temp_dir_name = f"{prefix}_{unique_id}"
        temp_dir_path = os.path.join(base_temp_dir, temp_dir_name)
        
        # 创建子目录
        os.makedirs(temp_dir_path, exist_ok=True)
        
        dirs[prefix] = {
            'path': temp_dir_path,
            'obj': None  # 不再需要TemporaryDirectory对象
        }
        # 删掉下面这行日志输出代码即可
        # logger.info(f"创建临时目录: {temp_dir_path}")
    return dirs

def cleanup_temp_dirs(dirs: dict) -> None:
    """清理临时目录（脚本目录下的temp子目录）"""
    cleaned = []
    for prefix, dir_info in dirs.items():
        dir_path = dir_info['path']
        if dir_path and os.path.exists(dir_path):
            try:
                # 递归删除目录及内容
                shutil.rmtree(dir_path)
                cleaned.append(os.path.basename(dir_path))
            except Exception as e:
                logger.warning(f"⚠️ 清理{prefix}临时目录失败: {e}")
    if cleaned:
        logger.info(f"✓ 已清理临时目录：{', '.join(cleaned)}")
    

def fullwidth_to_halfwidth(text):
    """将全角字符转换为半角字符"""
    return ''.join([unicodedata.normalize('NFKC', char) for char in text])

def fuzzy_match(target, text, threshold=0.6):
    """模糊匹配函数，使用简单的字符串相似性比较（不依赖外部库）"""
    if not target or not text:
        return False
        
    target = target.lower()
    text = text.lower()
    
    # 检查是否有直接包含关系
    if target in text or text in target:
        return True
        
    # 计算最长公共子串
    def longest_common_substring(s1, s2):
        m, n = len(s1), len(s2)
        dp = [[0]*(n+1) for _ in range(m+1)]
        max_length = 0
        for i in range(1, m+1):
            for j in range(1, n+1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                    max_length = max(max_length, dp[i][j])
                else:
                    dp[i][j] = 0
        return max_length
    
    lcs_length = longest_common_substring(target, text)
    max_length = max(len(target), len(text))
    return max_length > 0 and (lcs_length / max_length) >= threshold

def escape_special_chars(text):
    """处理Telegram中可能被误解的特殊字符"""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def is_valid_name(name):
    """验证姓名格式，支持汉字、英文、空格、连字符和点号"""
    if name.isdigit():
        return False
    pattern = r'^[a-zA-Z\u4e00-\u9fa5\s\-\.]{1,50}$'
    return re.fullmatch(pattern, name) is not None

def is_valid_count(count_str):
    """验证数量是否为有效的正整数"""
    if not count_str:
        return False
    return count_str.isdigit() and int(count_str) > 0

def is_other_bot_command(s):
    """判断是否为其他机器人的指令（纯字母、纯数字或字母数字混合）"""
    s = s.strip()
    return bool(re.fullmatch(r'^[a-zA-Z0-9]+$', s))


# —— 日志工具函数 —— #
def log_info(message, source=None):
    """标准化信息日志输出"""
    prefix = f"[{source}] " if source else ""
    logger.info(f"{prefix}{message}")

def log_error(message, source=None, exc_info=False):
    """标准化错误日志输出"""
    prefix = f"[{source}] " if source else ""
    logger.error(f"{prefix}⚠️ {message}", exc_info=exc_info)

def log_success(message, source=None):
    """标准化成功操作日志输出"""
    prefix = f"[{source}] " if source else ""
    logger.info(f"{prefix}✓ {message}")

def log_attachment_processing(filename, source, action="处理"):
    """标准化附件处理日志"""
    log_info(f"{action}附件：{os.path.basename(filename)}", source)

def log_email_skip(reason, msg_id, source):
    """标准化邮件跳过日志"""
    log_info(f"跳过邮件（ID：{msg_id}）：{reason}", source)


# —— PDF处理与回单生成 —— #
def parse_pdf_receipt_info(pdf_path: str) -> tuple:
    """
    公共PDF回单解析：从PDF第一页提取完整回单信息（核心函数）
    返回：(付款人, 付款账号, 付款类型, 收款人, 收款账号, 收款类型,
           小写金额, 大写金额, 支付时间, 凭证生成时间, 支付宝流水号)
    """
    # 先检查缓存，添加超时机制（24小时）
    cache_entry = _pdf_text_cache.get(pdf_path)
    if cache_entry and (time.time() - cache_entry['timestamp'] < 86400):
        return cache_entry['data']
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            raise Exception("PDF无有效页面")
        text = doc.load_page(0).get_text()
        doc.close()
        
        # 更新缓存，添加时间戳
        _pdf_text_cache[pdf_path] = {
            'data': text,
            'timestamp': time.time()
        }
    except Exception as e:
        logger.error(f"PDF处理失败: {e}")
        raise

    # 第一步：将所有全角字符转换为半角字符
    text = fullwidth_to_halfwidth(text)
    
    # 清理文本中可能存在的转义字符
    text = text.replace("\\", "")

    def find(pattern: str) -> str:
        """内部辅助：正则匹配提取内容，返回strip后的结果，无匹配则返回空字符串"""
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match and match.group(1):
            result = match.group(1).strip()
            return result.replace("\\", "")
        return ''

    # 付款方信息：严格匹配"付款方"模块内的字段
    payer = find(r'付款方[\s\S]*?账户名[:：]\s*([^\n]+)') or '未知'
    pacc = find(r'付款方[\s\S]*?账号[:：]\s*([^\n]+)') or '未知'
    payer_type_raw = find(r'付款方[\s\S]*?账户类型[:：]\s*([^\n]+)')
    payer_type = f"（{payer_type_raw}）" if payer_type_raw else ""

    # 收款方信息：严格匹配"收款方"模块内的字段
    payee = find(r'收款方[\s\S]*?账户名[:：]\s*([^\n]+)') or '未知'
    eacc = find(r'收款方[\s\S]*?账号[:：]\s*([^\n]+)') or '未知'
    payee_type_raw = find(r'收款方[\s\S]*?账户类型[:：]\s*([^\n]+)')
    payee_type = f"（{payee_type_raw}）" if payee_type_raw else ""

    # 金额信息提取
    amount = find(r'小写[:：]?\s*([0-9]+\.[0-9]{2})') or find(r'付款金额[\s\S]*?小写[:：]?\s*([0-9]+\.[0-9]{2})') or '未知'
    amount_in_words = find(r'大写[:：]?\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元[整|角分]?)') or find(r'付款金额[\s\S]*?大写[:：]?\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元[整|角分]?)') or '未知'

    # 时间信息提取
    pay_time = format_chinese_datetime(find(r'支付时间[:：]?\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})') or find(r'付款时间[:：]?\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})') or '未知')
    receipt_time = format_chinese_datetime(find(r'凭证生成时间[:：]?\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})') or find(r'回单生成时间[:：]?\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})') or '未知')

    # 支付宝流水号提取
    alipay_flow_no = find(r'支付宝流水号[:：]?\s*([^\n]+)') or find(r'交易流水号[:：]?\s*([^\n]+)') or '未知'

    result = (payer, pacc, payer_type, payee, eacc, payee_type, amount, amount_in_words, pay_time, receipt_time, alipay_flow_no)
    
    # 更新缓存，存储解析结果而非原始文本
    _pdf_text_cache[pdf_path] = {
        'data': result,
        'timestamp': time.time()
    }
    
    return result

def generate_receipt_caption(
    source: str,          # 来源邮箱标识
    payer: str,           # 付款人名称
    payer_type: str,      # 付款人类型
    payer_account: str,   # 付款人账号
    payee: str,           # 收款人名称
    payee_type: str,      # 收款人类型
    payee_account: str,   # 收款人账号
    amount: str,          # 小写金额
    amount_in_words: str, # 大写金额
    pay_time: str,        # 支付时间
    receipt_time: str,    # 回单生成时间
    alipay_flow_no: str,  # 支付宝流水号
    sender_name: str,     # 发件人名称
    sender_addr: str,     # 发件人邮箱
    send_time: str        # 邮件发送时间
) -> str:
    """公共回单文本生成函数：用代码格式保护账号，支持点击复制，统一时间格式"""
    # 强制保留账号原始格式
    def preserve_raw_account(account: str) -> str:
        if not account:
            return "未知账号"
        return account.replace("\\", "")

    # 转义函数：仅处理非账号字段
    def safe_escape(text, is_datetime=False):
        if not text:
            return ""
        text = text.replace("\\", "")
        must_escape = r'_[]()~`>#+=|{}!-'
        if is_datetime:
            must_escape = must_escape.replace('-', '')
        for char in must_escape:
            if char in text:
                text = text.replace(char, f'\{char}')
        return text

    # 时间格式转换：将YYYY-MM-DD转换为YYYY年MM月DD日
    def format_time_with_chinese(time_str):
        if not time_str:
            return ""
        date_part, _, time_part = time_str.partition(' ')
        if '-' in date_part:
            year, month, day = date_part.split('-')
            formatted_date = f"{year}年{month}月{day}日"
            return f"{formatted_date} {time_part}" if time_part else formatted_date
        return time_str

    # 处理账号
    raw_payer_account = preserve_raw_account(payer_account)
    raw_payee_account = preserve_raw_account(payee_account)
    
    # 处理发件人名：去除前后可能存在的双引号
    cleaned_sender_name = sender_name.strip('"') if sender_name else ""

    parts = [
        f"📧 【收件箱】：`{safe_escape(source.capitalize())}`",
        f"💳 【付款方】：`{safe_escape(payer)}`{safe_escape(payer_type)}，账号：`{raw_payer_account}`",
        f"🏦 【收款方】：`{safe_escape(payee)}`{safe_escape(payee_type)}，账号：`{raw_payee_account}`",
        f"💰 【交易金额】：`{safe_escape(amount)}` 元（大写：{safe_escape(amount_in_words)}），已完成支付。",
        f"⏱️ 【支付时间】：{safe_escape(pay_time, is_datetime=True)}",
        f"📅 【回单生成时间】：{safe_escape(format_time_with_chinese(receipt_time), is_datetime=True)}",
        f"🔢 【支付宝流水号】：{safe_escape(alipay_flow_no)}",
        f"📧 【发件邮箱详情】：{safe_escape(cleaned_sender_name)},邮箱:`{safe_escape(sender_addr)}`",
        f"⏰ 【邮件发送时间】：{safe_escape(format_time_with_chinese(send_time), is_datetime=True)}（北京时间）"
    ]
    
    caption = "\n".join(parts)
    return caption

def process_pdf_attachment(pdf_bytes: bytes, out_dir: str, source: str, original_filename: str) -> tuple[None|str, None|str, None|str]:
    """
    公共PDF附件处理：生成高清图片、保存PDF、提取文本（Gmail/FastMail 通用）
    返回：(图片路径, PDF路径, 文本内容)，失败则返回 (None, None, None)
    """
    try:
        # 确保输出目录存在
        os.makedirs(out_dir, exist_ok=True)
        
        # 将来源标识转换为大写形式（首字母大写）
        source = source.capitalize()
        
        # 使用原始文件名（去除扩展名）
        base_name = os.path.splitext(original_filename)[0]
        # 清理文件名中的非法字符
        base_name = re.sub(r'[\\/*?:"<>|]', '_', base_name)
        
        pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
        img_path = os.path.join(out_dir, f"{base_name}.png")

        # 检查文件是否已存在（避免重复处理）
        if os.path.exists(pdf_path) and os.path.exists(img_path):
            try:
                doc = fitz.open(pdf_path)
                pdf_text = doc.load_page(0).get_text()
                doc.close()
                _pdf_text_cache[f"{source}_{img_path}"] = {
                    'data': pdf_text,
                    'timestamp': time.time()
                }
                log_attachment_processing(pdf_path, source, "重用")
                return (img_path, pdf_path, pdf_text)
            except Exception as e:
                log_error(f"重用现有文件失败，将重新处理: {e}", source)

        # 保存PDF
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        log_attachment_processing(pdf_path, source, "下载")

        # 生成300DPI高清图片
        doc = fitz.open(pdf_path)
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(3.0, 3.0), dpi=300)
        pix.save(img_path)
        pdf_text = doc.load_page(0).get_text()
        doc.close()

        # 文本缓存
        _pdf_text_cache[f"{source}_{img_path}"] = {
            'data': pdf_text,
            'timestamp': time.time()
        }
        log_attachment_processing(img_path, source, "渲染")
        return (img_path, pdf_path, pdf_text)
    except Exception as e:
        log_error(f"PDF处理失败：{str(e)}", source, exc_info=True)
        return (None, None, None)


# —— Gmail 相关功能 —— #
# 凭证管理
async def load_credentials_from_files(credential_type: str) -> dict:
    config = CREDENTIALS_FILES.get(credential_type)
    if not config:
        if not await has_fastmail_credentials():
            logger.info(f"未配置凭证类型：{credential_type}")
        return None

    creds = {}
    # 加载 client_secret 文件
    if os.path.exists(config['client_secret']):
        with open(config['client_secret'], 'r') as f:
            creds['client_secret'] = json.load(f)
        os.remove(config['client_secret'])
        logger.info(f"加载并删除 {config['client_secret']}")
    else:
        if not await has_fastmail_credentials():
            logger.info(f"找不到 {config['client_secret']}")
        return None

    # 加载 token 文件（可不存在）
    if os.path.exists(config['token']):
        with open(config['token'], 'r') as f:
            creds['token'] = json.load(f)
        os.remove(config['token'])
        logger.info(f"加载并删除 {config['token']}")
    else:
        logger.info(f"找不到 {config['token']}，后续会创建")
        creds['token'] = {}

    return creds

async def save_google_credentials(credential_type: str, credentials: dict):
    cs = json.dumps(credentials['client_secret'])
    tk = json.dumps(credentials.get('token', {}))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO google_api_credentials(type, client_secret, token)
            VALUES (?, ?, ?)
            ON CONFLICT(type) DO UPDATE SET
              client_secret = excluded.client_secret,
              token         = excluded.token,
              updated_at    = CURRENT_TIMESTAMP
            """,
            (credential_type,)
        )
        await db.commit()
    logger.info(f"已保存 {credential_type} 凭证到数据库")

async def get_google_credentials(credential_type: str) -> dict:
    # 尝试从数据库读取
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT client_secret, token FROM google_api_credentials WHERE type = ?",
            (credential_type,)
        )
        row = await cur.fetchone()
    if row:
        return {
            'client_secret': json.loads(row[0]),
            'token': json.loads(row[1]) if row[1] else {}
        }

    # 表里没有，则从文件加载
    has_fastmail = await has_fastmail_credentials()
    if not has_fastmail:
        logger.info(f"{credential_type} 凭证表里无记录，尝试从文件加载")
    
    creds = await load_credentials_from_files(credential_type)
    if not creds:
        if not has_fastmail:
            logger.info(f"未能加载 {credential_type} 凭证")
        return None

    # 将文件加载的凭证存回数据库
    await save_google_credentials(credential_type, creds)
    return creds

async def delete_google_credentials(credential_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM google_api_credentials WHERE type = ?",
            (credential_type,)
        )
        await db.commit()
    # 从连接池移除
    if credential_type in GMAIL_SERVICE_POOL['connections']:
        del GMAIL_SERVICE_POOL['connections'][credential_type]
        del GMAIL_SERVICE_POOL['last_used'][credential_type]
    logger.info(f"已删除 {credential_type} 凭证")

# 服务初始化
async def initialize_credentials(credential_type: str, event=None):
    """初始化凭证流程，引导用户完成授权"""
    existing_creds = await get_google_credentials(credential_type)
    
    if not existing_creds or 'client_secret' not in existing_creds:
        if event:
            service_name = "代付" if credential_type == "pay" else ""
            await event.reply(
                f"❌ 系统尚未配置{service_name}业务的Google API客户端密钥\n\n"
                f"请联系管理员进行以下操作：\n"
                f"1 访问Google Cloud Console创建OAuth 2.0客户端ID\n"
                f"2 下载客户端密钥JSON文件\n"
                f"3 将文件命名为{CREDENTIALS_FILES[credential_type]['client_secret']}并放置在程序目录下\n"
                f"4 重启程序让系统加载新配置"
            )
        raise ValueError(f"未配置 {credential_type} 类型的 Google API 客户端密钥")
    
    # 已有客户端密钥，引导用户完成授权
    flow = InstalledAppFlow.from_client_config(
        existing_creds['client_secret'], SCOPES
    )
    
    # 使用 run_local_server() 自动弹出浏览器并获取授权
    creds = await asyncio.to_thread(flow.run_local_server, port=0)
    
    # 保存新的令牌到数据库
    token = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    # 更新数据库中的凭证
    updated_credentials = {
        'client_secret': existing_creds['client_secret'],
        'token': token
    }
    await save_google_credentials(credential_type, updated_credentials)
    logger.info(f"{credential_type} 凭证已更新并保存到数据库")
    
    return creds

async def get_gmail_service(credential_type: str, event=None, max_retries=3):
    """获取 Gmail 服务，优化并发处理"""
    retry_delay = 1  # 初始重试延迟（秒）
    
    async with gmail_service_lock:
        for attempt in range(max_retries):
            try:
                creds = None

                # 从数据库获取凭证
                credentials_data = await get_google_credentials(credential_type)
                
                if not credentials_data:
                    logger.info(f"未找到 {credential_type} 类型的凭证，开始初始化流程")
                    return await initialize_credentials(credential_type, event)
                    
                if 'token' in credentials_data:
                    token = credentials_data['token']
                    creds = Credentials(
                        token=token.get('token'),
                        refresh_token=token.get('refresh_token'),
                        token_uri=token.get('token_uri'),
                        client_id=token.get('client_id'),
                        client_secret=token.get('client_secret'),
                        scopes=SCOPES
                    )

                # 如无效则刷新或重新获取
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        logger.info(f"尝试刷新 {credential_type} Google API 访问令牌…")
                        creds.refresh(Request())
                    else:
                        logger.info(f"需要获取新的 {credential_type} Google API 凭证…")
                        creds = await initialize_credentials(credential_type, event)

                    # 保存更新后的凭证到数据库
                    if credentials_data:
                        credentials_data['token'] = {
                            'token': creds.token,
                            'refresh_token': creds.refresh_token,
                            'token_uri': creds.token_uri,
                            'client_id': creds.client_id,
                            'client_secret': creds.client_secret,
                            'scopes': creds.scopes
                        }
                    else:
                        credentials_data = {
                            'client_secret': (await get_google_credentials(credential_type))['client_secret'],
                            'token': {
                                'token': creds.token,
                                'refresh_token': creds.refresh_token,
                                'token_uri': creds.token_uri,
                                'client_id': creds.client_id,
                                'client_secret': creds.client_secret,
                                'scopes': creds.scopes
                            }
                        }
                    
                    await save_google_credentials(credential_type, credentials_data)
                    logger.info(f"{credential_type} 凭证已更新并保存到数据库")

                # 构建并返回服务
                service = build("gmail", "v1", credentials=creds)
                
                # 更新连接池和最后使用时间
                GMAIL_SERVICE_POOL['connections'][credential_type] = service
                GMAIL_SERVICE_POOL['last_used'][credential_type] = time.time()
                
                return service

            except RefreshError as e:
                logger.error(f"{credential_type} Google API 凭证刷新失败: {e}")
                await delete_google_credentials(credential_type)
                
                error_msg = f"❌ {credential_type} Google API 凭证已过期或被撤销，请重新授权。"
                if event:
                    await event.reply(error_msg)
                    
                if attempt < max_retries - 1:
                    logger.info(f"重试获取Gmail服务 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
                raise

            except HttpError as e:
                logger.error(f"构建 {credential_type} Gmail 服务失败: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"重试获取Gmail服务 ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise
        
        raise Exception(f"获取Gmail服务失败，已达到最大重试次数 {max_retries}")

# 邮件与附件处理
def process_attachment(service, msg, out_dir: str) -> str:
    """
    下载邮件里的第一份 PDF。
    - PDF：先保存到本地，再渲染高清 PNG，同时把 PDF 里的文字塞进 _pdf_text_cache
    返回：生成的图片的本地路径；如果啥都没有，就返回 None
    """
    for part in msg.get("payload", {}).get("parts", []):
        fn  = part.get("filename", "")
        aid = part.get("body", {}).get("attachmentId")

        # 处理 PDF
        if fn.lower().endswith(".pdf") and aid:
            try:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=aid
                ).execute()
                pdf_bytes = base64.urlsafe_b64decode(att["data"])
                
                img_path, _, _ = process_pdf_attachment(pdf_bytes, out_dir, source="gmail", original_filename=fn)
                if img_path:
                    _pdf_text_cache[msg["id"]] = {
                        'data': _pdf_text_cache.get(f"gmail_{img_path}", {}).get('data', ""),
                        'timestamp': time.time()
                    }
                    return img_path
            except Exception as e:
                logger.error(f"处理PDF附件失败: {e}")
            continue

    return None

def parse_payback_info(img_path: str):
    """Gmail回单解析：直接调用公共PDF解析函数"""
    pdf_path = img_path.rsplit('.', 1)[0] + '.pdf'
    try:
        return parse_pdf_receipt_info(pdf_path)
    except Exception as e:
        logger.warning(f"❗ 解析回单信息失败（来源：Gmail）: {e}")
        return ('', '', '', '', '', '', '', '', '未知', '未知', '未知')

# 回单获取
async def get_payback_items(service, name: str, max_results: int, out_dir: str):
    """查询 Gmail，返回回单信息列表"""
    task_state = GmailTaskState()
    os.makedirs(out_dir, exist_ok=True)
    items = []
    
    # 构建搜索条件
    q = f'from:service@mail.alipay.com has:attachment'
    if name:
        q += f' subject:"{name}"'
    
    resp = service.users().messages().list(userId='me', q=q, maxResults=max_results).execute()
    
    # 获取Gmail收件人地址
    profile = service.users().getProfile(userId='me').execute()
    recipient_email = profile.get('emailAddress', '未知邮箱')
    
    # 统计邮件总数
    total_messages = len(resp.get('messages', []))
    
    # 处理单封邮件
    async def process_message(ref):
        nonlocal items
        if task_state.terminate:
            return
            
        try:
            m = await asyncio.to_thread(
                service.users().messages().get, 
                userId='me', 
                id=ref['id']
            )
            
            raw_date = next((h['value']
                             for h in m.get('payload', {}).get('headers', [])
                             if h['name'] == 'Date'),
                            '未知时间')
            
            # 提取发件人邮箱
            sender_email = next((h['value']
                                for h in m.get('payload', {}).get('headers', [])
                                if h['name'] == 'From'),
                               '未知邮箱')
            
            # 处理附件
            img_path = await asyncio.to_thread(
                process_attachment, 
                service, m, out_dir
            )
            if not img_path:
                return
                
            # 解析回单信息
            parsed_info = await asyncio.to_thread(parse_payback_info, img_path)
            (
                payer, pacc, payer_type, payee, eacc, payee_type, 
                amount, amount_in_words, pay_time, receipt_time, alipay_flow_no
            ) = parsed_info
            
            items.append((
                img_path, raw_date, sender_email, payer, pacc, payer_type, payee, eacc, payee_type, 
                amount, amount_in_words, pay_time, receipt_time, alipay_flow_no, "gmail",
                recipient_email
            ))
            
            task_state.matched_count += 1
            if task_state.matched_count >= max_results:
                task_state.terminate = True
                
        except Exception as e:
            logger.error(f"处理邮件失败: {e}")
    
    # 控制并发数量
    semaphore = asyncio.Semaphore(5)
    
    async def bounded_process_message(ref):
        async with semaphore:
            await process_message(ref)
    
    # 并发处理所有邮件
    messages = resp.get('messages', [])
    await asyncio.gather(*[bounded_process_message(ref) for ref in messages])
    
    return items, total_messages

def get_payback_items_with_payee(
    service, payer_name, payee_name, max_results: int = 1000, 
    out_dir: str = "", required_email: str = "service@mail.alipay.com",
    task_control=None
):
    """按付款人搜索所有邮件，使用独立的任务控制实例"""
    if task_control is None:
        task_control = TaskControl()
        
    os.makedirs(out_dir, exist_ok=True)
    
    # 获取Gmail收件人地址
    profile = service.users().getProfile(userId='me').execute()
    recipient_email = profile.get('emailAddress', '未知邮箱')
    
    items = []
    next_page_token = None
    total_searched = 0
    processed_emails = 0
    found_enough = False
    total_messages = 0
    
    while True:
        if found_enough or task_control.terminate:
            break
            
        # 搜索条件
        query = f'from:{required_email} has:attachment'
        if payer_name:
            query += f' subject:"{payer_name}"'
            
        # 请求邮件
        request = service.users().messages().list(
            userId='me', q=query, maxResults=50, pageToken=next_page_token
        )
        resp = request.execute()
        messages = resp.get('messages', [])
        current_emails = len(messages)
        total_messages += current_emails
        
        if not messages:
            break
        
        # 处理当前页邮件
        for ref in messages:
            if found_enough or task_control.terminate:
                break
                
            total_searched += 1
            try:
                m = service.users().messages().get(userId='me', id=ref['id']).execute()
                processed_emails += 1
                
                # 验证发件人
                sender_email = next(
                    (h['value'] for h in m.get('payload', {}).get('headers', []) if h['name'] == 'From'), 
                    '未知邮箱'
                )
                actual_email = re.search(r'<([^>]+)>', sender_email).group(1) if re.search(r'<([^>]+)>', sender_email) else sender_email.strip()
                if actual_email != required_email:
                    logger.warning(f"跳过非官方邮箱邮件 ({processed_emails}): {sender_email}")
                    continue
                    
                # 处理附件
                try:
                    img_path = process_attachment(service, m, out_dir)
                    if not img_path:
                        logger.warning(f"无有效附件 ({processed_emails})")
                        continue
                except Exception as e:
                    logger.error(f"附件处理失败 ({processed_emails}): {e}")
                    continue
                    
                # 解析回单信息
                try:
                    (payer, pacc, payer_type, payee, eacc, payee_type, amount, amount_in_words, 
                     pay_time, receipt_time, alipay_flow_no) = parse_payback_info(img_path)
                except Exception as e:
                    logger.error(f"信息解析失败 ({processed_emails}): {e}")
                    continue
                    
                # 匹配验证
                payee_match = fuzzy_match(payee_name, payee) if payee_name else True
                payer_match = fuzzy_match(payer_name, payer) if payer_name else True
                match_result = "匹配" if payee_match and payer_match else "不匹配"
                
                # 日志输出
                target = payee_name if payee_name else payer_name
                if target:
                    logger.info(f"[Gmail] 解析结果：付款人：{payer}  收款人：{payee}  目标：{target}  结果：{match_result}")
                
                # 匹配成功时更新计数
                if payee_match and payer_match:
                    task_control.matched_count += 1
                    raw_date = next(
                        (h['value'] for h in m.get('payload', {}).get('headers', []) if h['name'] == 'Date'), 
                        '未知时间'
                    )
                    items.append((
                        img_path, raw_date, sender_email, payer, pacc, payer_type, payee, eacc, payee_type, 
                        amount, amount_in_words, pay_time, receipt_time, alipay_flow_no, "gmail", recipient_email
                    ))
                    
                    if task_control.matched_count >= max_results:
                        found_enough = True
                        task_control.terminate = True
                        break
            except Exception as e:
                logger.error(f"处理邮件失败: {e}")
                continue
        
        next_page_token = resp.get('nextPageToken')
        if not next_page_token:
            break
    
    return items, total_messages


# —— FastMail 相关功能 —— #
# 凭证管理
async def get_fastmail_credentials(credential_type: str = 'pay') -> dict:
    try:
        async with aiosqlite.connect("database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT user, app_password FROM fastmail_api_credentials 
                WHERE type = ? LIMIT 1
            """, (credential_type,))
            return await cursor.fetchone() or None
    except Exception as e:
        logger.error(f"获取凭证失败：{e}")
        raise

async def has_fastmail_credentials() -> bool:
    """检查是否存在有效的FastMail凭证"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT 1 FROM fastmail_api_credentials WHERE type = 'pay' LIMIT 1"
            )
            row = await cur.fetchone()
            return row is not None
    except Exception as e:
        logger.error(f"检查FastMail凭证时出错: {e}")
        return False

# 连接管理
async def connect_fastmail_imap(event=None) -> imaplib.IMAP4_SSL:
    """连接FastMail IMAP服务器，带重试机制"""
    max_retries = 3
    retry_delay = 1  # 初始重试延迟（秒）
    for attempt in range(max_retries):
        try:
            creds = await get_fastmail_credentials()
            if not creds:
                msg = "❌ 请先发送「设置FastMail代付凭证 邮箱 App密码」"
                if event:
                    await event.reply(msg)
                raise ValueError(msg)

            def _create_conn():
                conn = imaplib.IMAP4_SSL("imap.fastmail.com", 993)
                conn._encoding = 'utf-8'
                conn.login(creds["user"], creds["app_password"])
                conn.select("INBOX", readonly=True)
                return conn

            conn = await asyncio.to_thread(_create_conn)
            
            # 更新连接池和最后使用时间
            FASTMAIL_CONN_POOL['connections']['fastmail'] = conn
            FASTMAIL_CONN_POOL['last_used']['fastmail'] = time.time()
            
            return conn
        except Exception as e:
            msg = f"❌ 连接失败：{str(e)}"
            if event and attempt == max_retries - 1:
                await event.reply(msg)
            logger.error(f"{msg} (尝试 {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
    
    raise Exception(f"连接FastMail失败，已达到最大重试次数 {max_retries}")

# 邮件与附件处理
def parse_fastmail_payback_info(pdf_path: str):
    """FastMail回单解析：调用公共PDF解析函数"""
    try:
        return parse_pdf_receipt_info(pdf_path)
    except Exception as e:
        logger.warning(f"❗ 解析回单信息失败（来源：FastMail）: {e}")
        return ('', '', '', '', '', '', '', '', '未知', '未知', '未知')

def process_fastmail_attachment(msg_bytes: bytes, out_dir: str) -> tuple:
    """处理附件并返回图片路径、PDF路径和文本内容"""
    try:
        msg = BytesParser(policy=policy.default).parsebytes(msg_bytes)
    except Exception as e:
        logger.error(f"❌ 邮件解析失败：{str(e)}")
        return (None, None, None)

    # 优先处理PDF附件
    pdf_attachments = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue

        filename = part.get_filename()
        if not filename:
            continue
            
        # 处理文件名编码问题
        if isinstance(filename, bytes):
            decoded = False
            for encoding in ['utf-8', 'gbk', 'gb2312', 'iso-8859-1', 'big5']:
                try:
                    filename = filename.decode(encoding)
                    decoded = True
                    break
                except UnicodeDecodeError:
                    continue
            if not decoded:
                filename = filename.decode('utf-8', errors='replace')

        # 收集所有PDF附件
        if filename.lower().endswith(".pdf"):
            pdf_attachments.append((filename, part))
            logger.debug(f"发现PDF附件: {filename}")

    # 优先处理名称中包含"receipt"或"回单"的PDF
    target_attachment = None
    if pdf_attachments:
        for filename, part in pdf_attachments:
            if "receipt" in filename.lower() or "回单" in filename:
                target_attachment = (filename, part)
                break
        if not target_attachment:
            target_attachment = pdf_attachments[0]

        try:
            filename, part = target_attachment
            # 提取PDF字节流
            content_encoding = part.get("Content-Transfer-Encoding", "").lower()
            if content_encoding == "base64":
                pdf_bytes = base64.b64decode(part.get_payload(decode=False), validate=False)
            else:
                pdf_bytes = part.get_payload(decode=True)

            if not pdf_bytes:
                logger.warning("⚠️ PDF内容为空")
                return (None, None, None)

            # 调用公共PDF处理函数
            img_path, pdf_path, pdf_text = process_pdf_attachment(pdf_bytes, out_dir, source="fastmail", original_filename=filename)
            if img_path and pdf_path and pdf_text:
                return (img_path, pdf_path, pdf_text)

        except Exception as e:
            logger.error(f"⚠️ 处理PDF失败：{str(e)}")
            # 尝试下一个PDF
            for i in range(1, len(pdf_attachments)):
                try:
                    filename, part = pdf_attachments[i]
                    pdf_bytes = part.get_payload(decode=True)
                    img_path, pdf_path, pdf_text = process_pdf_attachment(pdf_bytes, out_dir, source="fastmail", original_filename=filename)
                    if img_path and pdf_path and pdf_text:
                        return (img_path, pdf_path, pdf_text)
                except Exception as e2:
                    logger.error(f"⚠️ 尝试处理第{i+1}个PDF失败：{str(e2)}")
                    continue

    logger.warning("⚠️ 未找到PDF附件")
    return (None, None, None)

# 回单获取
async def get_fastmail_pay_receipts(
    imap_conn: imaplib.IMAP4_SSL,
    payer_name: str,
    payee_name: str,
    max_results: int,
    out_dir: str,
    required_email: str = "service@mail.alipay.com",
    task_control=None
) -> list:
    """从FastMail获取符合条件的支付回单 - 使用独立任务控制"""
    if task_control is None:
        task_control = TaskControl()
        
    items = []
    os.makedirs(out_dir, exist_ok=True)
    max_results = min(max_results, 50)  # 限制最大结果数

    payer = payer_name.strip()
    payee = payee_name.strip()

    # 获取收件人邮箱地址
    creds = await get_fastmail_credentials()
    recipient_email = creds["user"] if creds else "未知邮箱"

    # 选择收件箱
    try:
        folder_utf7 = "INBOX".encode('utf-7').decode('utf-8')
        resp, _ = imap_conn.select(folder_utf7, readonly=True)
        if resp == "OK":
            total_messages = int(_[0]) if _ else 0
        else:
            logger.warning("无法选择INBOX文件夹，使用默认文件夹")
            resp, _ = imap_conn.select(readonly=True)
            total_messages = int(_[0]) if _ else 0
    except Exception as e:
        logger.error(f"文件夹选择失败: {str(e)}")
        return items, 0

    # 构建搜索条件
    search_criteria = []
    search_criteria.extend(['FROM', required_email])
    
    if payer:
        search_criteria.append('OR')
        search_criteria.extend([f'SUBJECT "{payer}"', f'BODY "{payer}"'])

    # 执行初始搜索
    def _sync_search():
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                imap_conn.noop()
                resp_code, msg_ids = imap_conn.search('UTF-8', *search_criteria)
                
                if resp_code != "OK":
                    error_msg = msg_ids.decode('utf-8', errors='ignore') if msg_ids else "未知错误"
                    logger.warning(f"搜索命令执行失败: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    
                    logger.info("尝试仅按发件人搜索")
                    resp_code, msg_ids = imap_conn.search('UTF-8', 'FROM', required_email)
                    if resp_code != "OK":
                        return []
                
                all_ids = msg_ids[0].split() if msg_ids and msg_ids[0] else []
                return all_ids
                
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                logger.error(f"搜索执行异常 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return []

    try:
        all_msg_ids = await asyncio.to_thread(_sync_search)
        if not all_msg_ids:
            return items, 0
            
        all_msg_ids.reverse()
        total_emails = len(all_msg_ids)

        page_size = 20
        processed_count = 0
        
        # 分页处理邮件
        for i in range(0, total_emails, page_size):
            if len(items) >= max_results or task_control.terminate:
                if task_control.terminate:
                    pass
                else:
                    logger.info(f"已找到{max_results}个匹配结果，停止处理")
                break
                
            page_ids = all_msg_ids[i:i+page_size]
            
            for msg_id in page_ids:
                if task_control.terminate:
                    break
                    
                processed_count += 1
                
                try:
                    if processed_count % 10 == 0:
                        await asyncio.to_thread(imap_conn.noop)
                    
                    def _fetch_mail():
                        try:
                            resp_code, data = imap_conn.fetch(msg_id, "(RFC822)")
                            return data[0][1] if resp_code == "OK" and data else None
                        except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                            logger.error(f"获取邮件内容失败: {str(e)}")
                            if 'fastmail' in FASTMAIL_CONN_POOL['connections']:
                                del FASTMAIL_CONN_POOL['connections']['fastmail']
                                del FASTMAIL_CONN_POOL['last_used']['fastmail']
                            return None

                    msg_bytes = await asyncio.to_thread(_fetch_mail)
                    if not msg_bytes:
                        continue

                    # 解析邮件
                    msg = BytesParser(policy=policy.default).parsebytes(msg_bytes)
                    sender_email = str(msg["from"]) if msg["from"] else "未知邮箱"
                    mail_date = msg["date"] or "1970-01-01"
                    
                    # 验证发件人
                    actual_email = re.search(r'<([^>]+)>', sender_email).group(1) if re.search(r'<([^>]+)>', sender_email) else sender_email.strip()
                    if actual_email != required_email:
                        continue
                    
                    # 处理附件
                    img_path, pdf_path, pdf_text = process_fastmail_attachment(msg_bytes, out_dir)
                    if not img_path or not pdf_path:
                        continue

                    # 解析PDF回单信息
                    parsed_data = parse_fastmail_payback_info(pdf_path)
                    if len(parsed_data) < 11:
                        continue

                    # 解析结果赋值
                    payer_parsed, pacc, payer_type, payee_parsed, eacc, payee_type, \
                    amount, amount_in_words, pay_time, receipt_time, alipay_flow_no = parsed_data

                    # 模糊匹配
                    parsed_payee_match = fuzzy_match(payee, payee_parsed) if payee else True
                    parsed_payer_match = fuzzy_match(payer, payer_parsed) if payer else True
                    
                    match_result = "匹配" if parsed_payee_match and parsed_payer_match else "不匹配"
                    logger.info(f"[Fastmail] 解析结果 : 付款人：{payer_parsed}  收款人：{payee_parsed}  目标：{payee}  结果：{match_result}")
                    
                    # 匹配成功
                    if parsed_payer_match and parsed_payee_match:
                        task_control.matched_count += 1
                        item = {
                            "img_path": img_path,
                            "raw_date": mail_date,
                            "sender_email": sender_email,
                            "parsed_data": parsed_data,
                            "email_type": "fastmail",
                            "recipient_email": recipient_email
                        }
                        items.append(item)
                        
                        task_control.terminate = True
                        
                        if len(items) >= max_results:
                            break

                except Exception as e:
                    logger.error(f"处理邮件ID {msg_id} 失败：{str(e)}")
                    continue
                
            if len(items) >= max_results or task_control.terminate:
                break

        return items, total_emails
    
    except Exception as e:
        logger.error(f"搜索流程异常：{str(e)}")
        if 'fastmail' in FASTMAIL_CONN_POOL['connections']:
            del FASTMAIL_CONN_POOL['connections']['fastmail']
            del FASTMAIL_CONN_POOL['last_used']['fastmail']
        return items, 0

async def get_fastmail_pay_receipts_with_payee(
    imap_conn: imaplib.IMAP4_SSL,
    payer_name: str,
    payee_name: str,
    max_results: int = 10,
    out_dir: str = "",
    required_email: str = "service@mail.alipay.com",
    task_control=None
):
    """按付款人搜索所有邮件，直到找到收款人匹配的回单或搜索完所有邮件（FastMail）"""
    os.makedirs(out_dir, exist_ok=True)
    
    # 调用主处理函数
    items, total_messages = await get_fastmail_pay_receipts(
        imap_conn, payer_name, payee_name, max_results, out_dir, required_email,
        task_control=task_control
    )
    
    # 格式化结果以匹配Gmail的返回格式
    formatted_items = []
    for item in items:
        parsed = item["parsed_data"]
        formatted = (
            item["img_path"], 
            item["raw_date"], 
            item["sender_email"], 
            parsed[0], parsed[1], parsed[2], parsed[3], parsed[4], parsed[5],
            parsed[6], parsed[7], parsed[8], parsed[9], parsed[10],
            item["email_type"], item["recipient_email"]
        )
        formatted_items.append(formatted)
    
    return formatted_items, total_messages


# —— 统一任务处理 —— #
DEFAULT_EMAIL_TYPE = "gmail"  # 默认使用Gmail，可选"fastmail"

async def check_available_credentials():
    """检查可用的邮箱凭证"""
    available = {
        "gmail": False,
        "fastmail": False,
        "gmail_account": "",
        "fastmail_account": ""
    }
    
    # 检查Gmail凭证
    try:
        gmail_creds = await get_google_credentials('pay')
        if gmail_creds and 'client_secret' in gmail_creds:
            available["gmail"] = True
            # 获取Gmail账号信息
            try:
                service = await get_gmail_service('pay')
                profile = service.users().getProfile(userId='me').execute()
                available["gmail_account"] = profile.get('emailAddress', '未知Gmail账号')
            except:
                available["gmail_account"] = '已配置Gmail账号'
    except:
        pass
        
    # 检查FastMail凭证
    try:
        fastmail_creds = await get_fastmail_credentials()
        if fastmail_creds:
            available["fastmail"] = True
            available["fastmail_account"] = fastmail_creds["user"]
    except:
        pass
        
    return available

def generate_task_hash(payer_name, payee_name, count, email_type=None):
    """基于关键参数生成任务唯一哈希值"""
    norm_payer = payer_name.strip() if payer_name else ""
    norm_payee = payee_name.strip() if payee_name else ""
    norm_email_type = email_type.strip().lower() if email_type else ""
    task_str = f"{norm_email_type}|{norm_payer}|{norm_payee}|{count}"
    return hashlib.md5(task_str.encode()).hexdigest()

async def clean_expired_cache():
    """清理过期缓存"""
    now = time.time()
    expired_hashes = [
        task_hash for task_hash, data in TASK_CACHE.items()
        if now - data["timestamp"] > CACHE_EXPIRE_SECONDS
    ]
    for task_hash in expired_hashes:
        del TASK_CACHE[task_hash]

async def periodic_cleanup_pdf_cache():
    """定期清理过期的PDF文本缓存"""
    while True:
        now = time.time()
        # 清理超过24小时的缓存项
        expired_keys = [
            key for key, entry in _pdf_text_cache.items()
            if now - entry['timestamp'] > 86400  # 24小时
        ]
        for key in expired_keys:
            del _pdf_text_cache[key]
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期的PDF缓存项")
        # 每小时执行一次清理
        await asyncio.sleep(3600)

async def periodic_cleanup_connection_pools():
    """定期清理连接池中的闲置连接"""
    while True:
        now = time.time()
        
        # 清理Gmail连接池
        gmail_expired = [
            key for key, last_used in GMAIL_SERVICE_POOL['last_used'].items()
            if now - last_used > GMAIL_SERVICE_POOL['timeout']
        ]
        for key in gmail_expired:
            try:
                # 关闭连接
                GMAIL_SERVICE_POOL['connections'][key].close()
            except Exception as e:
                logger.error(f"关闭Gmail连接 {key} 失败: {e}")
            del GMAIL_SERVICE_POOL['connections'][key]
            del GMAIL_SERVICE_POOL['last_used'][key]
        if gmail_expired:
            logger.info(f"清理了 {len(gmail_expired)} 个过期的Gmail连接")
        
        # 清理FastMail连接池
        fastmail_expired = [
            key for key, last_used in FASTMAIL_CONN_POOL['last_used'].items()
            if now - last_used > FASTMAIL_CONN_POOL['timeout']
        ]
        for key in fastmail_expired:
            try:
                # 关闭连接
                FASTMAIL_CONN_POOL['connections'][key].close()
            except Exception as e:
                logger.error(f"关闭FastMail连接 {key} 失败: {e}")
            del FASTMAIL_CONN_POOL['connections'][key]
            del FASTMAIL_CONN_POOL['last_used'][key]
        if fastmail_expired:
            logger.info(f"清理了 {len(fastmail_expired)} 个过期的FastMail连接")
        
        # 每30分钟执行一次清理
        await asyncio.sleep(1800)

async def fetch_combined_receipts(event, payer_name, payee_name, count, email_type=None):
    """根据可用凭证并发获取合并的回单结果（任务隔离版本）"""
    task_hash = generate_task_hash(payer_name, payee_name, count, email_type)
    
    # 创建任务控制实例
    task_control = TaskControl()
    
    # 检查任务状态
    async with cache_lock:
        await clean_expired_cache()
        
        if task_hash in TASK_CACHE:
            task_data = TASK_CACHE[task_hash]
            if task_data["status"] == "processing":
                return await event.reply("⚠️ 相同查询正在处理中，请稍候...")
            elif task_data["status"] == "completed":
                if task_data.get("has_result", False):
                    return await event.reply(f"ℹ️ 相同查询结果已获取，如需更新请{int(CACHE_EXPIRE_SECONDS)}秒后再试")
                else:
                    del TASK_CACHE[task_hash]
        
        TASK_CACHE[task_hash] = {
            "status": "processing",
            "timestamp": time.time(),
            "result": None,
            "has_result": False
        }
    
    try:
        available = await check_available_credentials()
        results = []
        temp_dirs = {}
        
        # 邮箱来源处理
        email_sources = []
        prefixes = []
        if email_type:
            if email_type.lower() == "gmail" and available["gmail"]:
                email_sources.append("Gmail")
                prefixes.append("gmail_combined")
            elif email_type.lower() == "fastmail" and available["fastmail"]:
                email_sources.append("Fastmail")
                prefixes.append("fastmail_combined")
            else:
                return await event.reply(f"❌ 未配置{email_type}的有效凭证")
        else:
            if available["gmail"]:
                email_sources.append("Gmail")
                prefixes.append("gmail_combined")
            if available["fastmail"]:
                email_sources.append("Fastmail")
                prefixes.append("fastmail_combined")
        
        source_text = " + ".join(email_sources)
        
        # 创建临时目录
        temp_dir_created = False
        if prefixes:
            temp_dirs = create_temp_dirs(prefixes)
            temp_dir_created = True
            log_success(f"创建临时目录，{source_text} 开始处理回单...")
            await asyncio.sleep(0.1)
        
        gmail_dir = temp_dirs.get("gmail_combined", {}).get('path') if available["gmail"] else None
        fastmail_dir = temp_dirs.get("fastmail_combined", {}).get('path') if available["fastmail"] else None
        
        # 解析邮件时间的辅助函数
        def parse_email_time(raw_time):
            if not raw_time:
                return datetime.min
            
            try:
                return parsedate_to_datetime(raw_time)
            except:
                pass
            
            time_formats = [
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
                "%m/%d/%Y %H:%M:%S"
            ]
            for fmt in time_formats:
                try:
                    return datetime.strptime(raw_time, fmt)
                except:
                    continue
            
            log_error(f"无法解析时间格式：{raw_time}，将按最早时间处理")
            return datetime.min
        
        # FastMail任务处理
        async def fetch_fastmail():
            fastmail_control = TaskControl()
            
            async def check_termination():
                while not fastmail_control.terminate:
                    if task_control.terminate:
                        fastmail_control.terminate = True
                    await asyncio.sleep(0.5)
            
            termination_task = asyncio.create_task(check_termination())
            
            try:
                conn = await connect_fastmail_imap(event)
                if not conn:
                    return []
                
                items, total_available = await get_fastmail_pay_receipts_with_payee(
                    conn, payer_name, payee_name, count, fastmail_dir,
                    required_email='service@mail.alipay.com',
                    task_control=fastmail_control
                )
                
                return items
            finally:
                fastmail_control.terminate = True
                termination_task.cancel()
                await asyncio.gather(termination_task, return_exceptions=True)
        
        # Gmail任务处理
        async def fetch_gmail():
            gmail_control = TaskControl()
            
            async def check_termination():
                while not gmail_control.terminate:
                    if task_control.terminate:
                        gmail_control.terminate = True
                    await asyncio.sleep(0.5)
            
            termination_task = asyncio.create_task(check_termination())
            
            try:
                svc = await get_gmail_service('pay', event)
                if not svc:
                    return []
                
                items, total_available = await asyncio.to_thread(
                    get_payback_items_with_payee, 
                    svc, payer_name, payee_name, count, gmail_dir,
                    required_email='service@mail.alipay.com',
                    task_control=gmail_control
                )
                
                return items
            finally:
                gmail_control.terminate = True
                termination_task.cancel()
                await asyncio.gather(termination_task, return_exceptions=True)
        
        # 执行任务并统一排序
        try:
            tasks = []
            if available["gmail"] and (not email_type or email_type.lower() == "gmail"):
                tasks.append(fetch_gmail())
            if available["fastmail"] and (not email_type or email_type.lower() == "fastmail"):
                tasks.append(fetch_fastmail())
            
            if not tasks:
                result = await event.reply("❌ 未配置任何邮箱凭证，请先配置Gmail或FastMail凭证")
                async with cache_lock:
                    TASK_CACHE[task_hash] = {
                        "status": "completed",
                        "timestamp": time.time(),
                        "result": result,
                        "has_result": False
                    }
                return result
            
            # 等待所有任务完成
            results_list = await asyncio.gather(*tasks)
            for items in results_list:
                if items:
                    results.extend(items)
            
            # 处理结果
            if not results:
                reply_msg = await event.reply(f"❌ 未找到付款人「{payer_name}」向收款人「{payee_name}」的回单")
                async with cache_lock:
                    TASK_CACHE[task_hash] = {
                        "status": "completed",
                        "timestamp": time.time(),
                        "result": reply_msg,
                        "has_result": False
                    }
                return reply_msg
            
            # 按时间排序并发送
            results.sort(key=lambda x: parse_email_time(x[1]), reverse=True)
            results = results[:count]
            sent_count = 0
            
            semaphore = asyncio.Semaphore(5)
            
            async def send_receipt(item):
                nonlocal sent_count
                try:
                    img_path, raw_date, sender_email, payer, pacc, payer_type, payee, eacc, payee_type, \
                    amount, amount_in_words, pay_time, receipt_time, alipay_flow_no, email_type, recipient_email = item

                    try:
                        send_time = parsedate_to_datetime(raw_date).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        send_time = raw_date

                    sender_name, sender_addr = extract_sender_info(sender_email)

                    caption = generate_receipt_caption(
                        source=email_type,
                        payer=escape_special_chars(payer),
                        payer_type=escape_special_chars(payer_type),
                        payer_account=escape_special_chars(pacc),
                        payee=escape_special_chars(payee),
                        payee_type=escape_special_chars(payee_type),
                        payee_account=eacc,
                        amount=escape_special_chars(amount),
                        amount_in_words=escape_special_chars(amount_in_words),
                        pay_time=escape_special_chars(pay_time),
                        receipt_time=escape_special_chars(receipt_time),
                        alipay_flow_no=escape_special_chars(alipay_flow_no),
                        sender_name=escape_special_chars(sender_name),
                        sender_addr=escape_special_chars(sender_addr),
                        send_time=escape_special_chars(send_time)
                    )

                    # 假设client是一个已初始化的Telegram客户端实例
                    await client.send_file(
                        event.chat_id,
                        img_path,
                        caption=caption,
                        reply_to=event.message.id,
                        force_document=(count > 1)
                    )
                    
                    sent_count += 1
                    logger.info(f"[{email_type.capitalize()}] 已发送回单: 收款人：{payee}   金额：{amount}")
                    
                    # 删除临时文件，添加异常处理
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                            pdf_path = img_path.rsplit('.', 1)[0] + '.pdf'
                            if os.path.exists(pdf_path):
                                os.remove(pdf_path)
                    except OSError as e:
                        logger.error(f"删除临时文件 {img_path} 失败: {e}")
                    
                except Exception as e:
                    log_error(f"发送回单失败: {e}", email_type)
            
            await asyncio.gather(*[send_receipt(item) for item in results])
            
            # 更新缓存
            async with cache_lock:
                TASK_CACHE[task_hash] = {
                    "status": "completed",
                    "timestamp": time.time(),
                    "result": None,
                    "has_result": len(results) > 0
                }
            
            return None
            
        except Exception as e:
            if task_control.terminate:
                log_info(f"已获取足够回单，停止处理")
            else:
                log_error(f"处理回单时发生异常: {e}", exc_info=True)
            async with cache_lock:
                TASK_CACHE[task_hash] = {
                    "status": "completed",
                    "timestamp": time.time(),
                    "result": None,
                    "has_result": False
                }
            return await event.reply("❌ 处理回单时发生错误")
        finally:
            if temp_dirs:
                cleanup_temp_dirs(temp_dirs)
    except Exception as e:
        async with cache_lock:
            if task_hash in TASK_CACHE:
                TASK_CACHE[task_hash] = {
                    "status": "completed",
                    "timestamp": time.time(),
                    "result": None,
                    "has_result": False
                }
        log_error(f"任务执行异常: {e}", exc_info=True)
        return await event.reply("❌ 处理请求时发生错误，请稍后重试")


# —— 通用请求处理 —— #
async def process_payback_request(event, name, count, credential_type):
    """处理回单请求的通用逻辑（Gmail）"""
    temp_dir = None
    try:
        # 获取Gmail服务
        svc = await get_gmail_service(credential_type, event)
        
        if not svc:
            raise ValueError(f"无法获取 {credential_type} 的Gmail服务")
            
        # 创建临时目录
        temp_dirs = create_temp_dirs([f"gmail_{credential_type}"])
        temp_dir_info = temp_dirs.get(f"gmail_{credential_type}")
        temp_dir = temp_dir_info['path'] if temp_dir_info else None
        
        if not temp_dir:
            raise ValueError("无法创建临时目录")

        items, _ = await asyncio.to_thread(get_payback_items, svc, name, count, temp_dir)

        if not items:
            await event.reply(f"❌ 未找到姓名「{name}」的回单邮件")
            return

        # 批量处理发送
        files_to_send = []
        for idx, (
            img_path, raw_date, sender_email, payer, pacc, payer_type, payee, eacc, payee_type, 
            amount, amount_in_words, pay_time, receipt_time, alipay_flow_no, email_type
        ) in enumerate(items, start=1):
            try:
                nice = parsedate_to_datetime(raw_date).strftime("%Y-%m-%d %H:%M:%S")
            except:
                nice = raw_date

            # 解析发件人信息
            sender_name, sender_addr = extract_sender_info(sender_email)

            # 生成回单文本
            caption = generate_receipt_caption(
                source=email_type,
                payer=escape_special_chars(payer),
                payer_type=escape_special_chars(payer_type),
                payer_account=escape_special_chars(pacc),
                payee=escape_special_chars(payee),
                payee_type=escape_special_chars(payee_type),
                payee_account=eacc,
                amount=escape_special_chars(amount),
                amount_in_words=escape_special_chars(amount_in_words),
                pay_time=escape_special_chars(pay_time),
                receipt_time=escape_special_chars(receipt_time),
                alipay_flow_no=escape_special_chars(alipay_flow_no),
                sender_name=escape_special_chars(sender_name),
                sender_addr=escape_special_chars(sender_addr),
                send_time=escape_special_chars(nice)
            )

            files_to_send.append((img_path, caption))

        # 并发发送
        semaphore = asyncio.Semaphore(5)
        
        async def send_file_task(img_path, caption):
            async with semaphore:
                try:
                    # 假设client是一个已初始化的Telegram客户端实例
                    await client.send_file(
                        event.chat_id,
                        img_path,
                        caption=caption,
                        reply_to=event.message.id,
                        force_document=(count > 1)
                    )
                    logger.info(f"[{email_type.capitalize()}] 已发送回单: 收款人：{payee}   金额：{amount}")

                    # 删除临时文件，添加异常处理
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                            pdf_path = img_path.rsplit('.', 1)[0] + '.pdf'
                            if os.path.exists(pdf_path):
                                os.remove(pdf_path)
                    except OSError as e:
                        logger.error(f"删除临时文件 {img_path} 失败: {e}")
                        
                except Exception as e:
                    logger.error(f"发送回单失败: {e}")
        
        await asyncio.gather(*[send_file_task(img, cap) for img, cap in files_to_send])

    except RefreshError as e:
        # 处理凭证过期
        logger.error(f"{credential_type} Google API 凭证刷新失败: {e}")
        await delete_google_credentials(credential_type)
        if credential_type in GMAIL_SERVICE_POOL['connections']:
            del GMAIL_SERVICE_POOL['connections'][credential_type]
            del GMAIL_SERVICE_POOL['last_used'][credential_type]

        error_msg = (
            f"❌ 代付回单查询失败：Google API凭证已过期或被撤销\n\n"
            f"当前凭证已被删除，无法继续使用。\n\n"
            f"请联系管理员重新授权：\n"
            f"1. 管理员需要在 Google Cloud Console 重新配置OAuth 2.0客户端凭证\n"
            f"2. 将新的凭证上传并重启机器人\n"
            f"3. 授权完成后，您可以再次尝试查询代付回单"
        )
        await event.reply(error_msg)
    
    except ValueError as e:
        logger.info(f"处理回单请求时发生值错误: {e}")
        error_msg = f"❌ 代付回单查询失败：{str(e)}"
        await event.reply(error_msg)
    
    except Exception as e:
        error_msg = f"❌ 代付回单查询失败：发生未知错误\n\n错误详情：{str(e)}"
        await event.reply(error_msg)
        logger.info(f"处理代付回单请求时发生未知错误: {e}")
    
    finally:
        # 清理临时目录
        if temp_dirs:
            cleanup_temp_dirs(temp_dirs)

async def process_payback_with_payee_request(event, payer_name, payee_name, count):
    """处理带收款人指定的代付回单请求"""
    await fetch_combined_receipts(event, payer_name, payee_name, count)

async def process_fastmail_pay_request(event, payer_name, payee_name, count):
    """处理FastMail代付回单请求"""
    await fetch_combined_receipts(event, payer_name, payee_name, count)


# —— 命令处理与事件响应 —— #
from telethon import events, TelegramClient

# 设置FastMail凭证命令
@client.on(events.NewMessage(pattern=r'^设置FastMail代付凭证\s+(\S+)\s+(\S+)$', incoming=True))
async def set_fastmail_credentials(event):
    """处理设置FastMail代付凭证的指令：设置FastMail代付凭证 邮箱地址 App专用密码"""
    # 验证管理员权限
    user_id = event.sender_id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        is_admin = await cursor.fetchone() is not None
    
    if not is_admin:
        return await event.reply("❌ 权限不足，仅管理员可设置FastMail凭证")
    
    # 提取参数
    email = event.pattern_match.group(1)
    app_password = event.pattern_match.group(2)
    
    # 验证邮箱格式
    if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
        return await event.reply("❌ 邮箱格式错误，请检查后重新输入")
    
    try:
        # 保存到数据库
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO fastmail_api_credentials 
                (type, user, app_password, updated_at) 
                VALUES ('pay', ?, ?, CURRENT_TIMESTAMP)
            """, (email, app_password))
            await db.commit()
        
        # 重置连接池
        if 'fastmail' in FASTMAIL_CONN_POOL['connections']:
            try:
                FASTMAIL_CONN_POOL['connections']['fastmail'].close()
            except:
                pass
            del FASTMAIL_CONN_POOL['connections']['fastmail']
            del FASTMAIL_CONN_POOL['last_used']['fastmail']
        
        logger.info(f"✅ FastMail代付凭证已更新：{email}")
        await event.reply(f"✅ FastMail代付凭证设置成功\n邮箱：{email}")
    
    except Exception as e:
        logger.error(f"❌ 设置FastMail凭证失败：{str(e)}")
        await event.reply(f"❌ 设置失败：{str(e)}")

# 代付回单命令（按匹配精度排序）

async def _process_pay_receipt(event, email_type, payer_name, payee_name, count):
    """公共处理函数：统一处理参数验证、日志记录和核心函数调用"""
    # 检测是否包含其他机器人命令
    if is_other_bot_command(payer_name) or (payee_name and is_other_bot_command(payee_name)):
        raise events.StopPropagation
    
    # 验证姓名格式
    if not is_valid_name(payer_name) or (payee_name and not is_valid_name(payee_name)):
        return await event.reply("❌ 姓名格式错误，支持汉字、英文和常见连接符，且不能为纯数字")
    
    # 记录日志（保持原有格式）
    log_parts = [f"★ 代付回单"]
    if email_type:
        log_parts.append(f"（{email_type}）")
    log_parts.append(f" 付款人：{payer_name}")
    log_parts.append(f" 收款人：{payee_name if payee_name else '未指定'}")
    log_parts.append(f" 数量：{count}")
    logger.info(''.join(log_parts))
    
    # 调用核心函数（根据是否有email_type传递不同参数）
    if email_type:
        await fetch_combined_receipts(event, payer_name, payee_name, count, email_type)
    else:
        await fetch_combined_receipts(event, payer_name, payee_name, count)
    
    raise events.StopPropagation


# 处理完整指定的代付回单命令（使用re.compile设置忽略大小写）
@client.on(events.NewMessage(
    pattern=re.compile(r'^代付回单\s+(gmail|fastmail)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+(\d+)\s*$', re.IGNORECASE),
    incoming=True
))
async def fetch_email_pay_full_specified(event):
    """处理完整指定的代付回单命令：代付回单 [邮箱类型] [付款人] [收款人] [数量]"""
    email_type = event.pattern_match.group(1)  # 保持原始大小写
    payer_name = event.pattern_match.group(2).strip()
    payee_name = event.pattern_match.group(3).strip()
    count = int(event.pattern_match.group(4))
    await _process_pay_receipt(event, email_type, payer_name, payee_name, count)


# 处理带邮箱类型、付款人和收款人的命令（默认数量1）
@client.on(events.NewMessage(
    pattern=re.compile(r'^代付回单\s+(gmail|fastmail)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s*$', re.IGNORECASE),
    incoming=True
))
async def fetch_email_pay_without_count(event):
    """处理带邮箱类型、付款人和收款人的命令（默认数量1）"""
    email_type = event.pattern_match.group(1)  # 保持原始大小写
    payer_name = event.pattern_match.group(2).strip()
    payee_name = event.pattern_match.group(3).strip()
    count = 1  # 默认数量
    await _process_pay_receipt(event, email_type, payer_name, payee_name, count)


# 处理带邮箱类型和付款人的命令
@client.on(events.NewMessage(
    pattern=re.compile(r'^代付回单\s+(gmail|fastmail)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)(?:\s+(\d+))?\s*$', re.IGNORECASE),
    incoming=True
))
async def fetch_email_pay_only_payer(event):
    """处理带邮箱类型和付款人的命令：代付回单 [邮箱类型] [付款人] [数量]"""
    email_type = event.pattern_match.group(1)  # 保持原始大小写
    payer_name = event.pattern_match.group(2).strip()
    count_str = event.pattern_match.group(3)
    count = int(count_str) if count_str and is_valid_count(count_str) else 1
    await _process_pay_receipt(event, email_type, payer_name, "", count)

@client.on(events.NewMessage(pattern=r'^代付回单\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+(\d+)\s*$', incoming=True))
async def fetch_email_pay_with_payee_and_count(event):
    """处理带付款人、收款人和数量的代付回单命令：代付回单 [付款人] [收款人] [数量]"""
    payer_name = event.pattern_match.group(1).strip()
    payee_name = event.pattern_match.group(2).strip()
    count = int(event.pattern_match.group(3))
    await _process_pay_receipt(event, None, payer_name, payee_name, count)


@client.on(events.NewMessage(pattern=r'^代付回单\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s*$', incoming=True))
async def fetch_email_pay_with_payee(event):
    """处理带付款人和收款人的代付回单命令（默认数量1）"""
    payer_name = event.pattern_match.group(1).strip()
    payee_name = event.pattern_match.group(2).strip()
    count = 1  # 默认数量
    await _process_pay_receipt(event, None, payer_name, payee_name, count)


@client.on(events.NewMessage(pattern=r'^代付回单\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s+(\d+)\s*$', incoming=True))
async def fetch_email_pay_payer_and_count(event):
    """处理带付款人和数量的代付回单命令：代付回单 [付款人] [数量]"""
    payer_name = event.pattern_match.group(1).strip()
    count = int(event.pattern_match.group(2))
    await _process_pay_receipt(event, None, payer_name, "", count)


@client.on(events.NewMessage(pattern=r'^代付回单\s+([^\d\s][\w\s\u4e00-\u9fa5\-\.]*?)\s*$', incoming=True))
async def fetch_email_pay_only_payer_basic(event):
    """处理仅带付款人的基础代付回单命令（默认数量1）"""
    payer_name = event.pattern_match.group(1).strip()
    count = 1  # 默认数量
    await _process_pay_receipt(event, None, payer_name, "", count)

# 启动定期清理任务
async def start_background_tasks():
    asyncio.create_task(periodic_cleanup_pdf_cache())
    asyncio.create_task(periodic_cleanup_connection_pools())


# —— 定时任务 —— #
async def cleanup_stale_connections():
    """定期清理连接池中的过期连接，每30分钟执行一次"""
    # 添加启动日志，明确任务开始
    logger.info("✅ 连接池清理任务已启动，将每30分钟检查并清理过期连接")
    
    while True:
        current_time = time.time()
        
        # 清理Gmail连接池
        # 使用列表复制避免迭代中修改字典引发的异常
        for cred_type in list(GMAIL_SERVICE_POOL['connections'].keys()):
            # 计算连接闲置时间
            idle_time = current_time - GMAIL_SERVICE_POOL['last_used'].get(cred_type, 0)
            
            # 当闲置时间超过超时阈值时清理
            if idle_time > GMAIL_SERVICE_POOL['timeout']:
                try:
                    # 移除连接池和最后使用时间记录
                    del GMAIL_SERVICE_POOL['connections'][cred_type]
                    del GMAIL_SERVICE_POOL['last_used'][cred_type]
                    logger.info(f"[Gmail] 清理过期的Gmail连接 (闲置时间: {idle_time:.1f}秒)")
                except Exception as e:
                    logger.warning(f"清理Gmail连接 {cred_type} 失败: {str(e)}")
        
        # 清理FastMail连接池
        for conn_key in list(FASTMAIL_CONN_POOL['connections'].keys()):
            idle_time = current_time - FASTMAIL_CONN_POOL['last_used'].get(conn_key, 0)
            
            if idle_time > FASTMAIL_CONN_POOL['timeout']:
                try:
                    # 先关闭连接再移除记录
                    conn = FASTMAIL_CONN_POOL['connections'][conn_key]
                    conn.close()
                    
                    del FASTMAIL_CONN_POOL['connections'][conn_key]
                    del FASTMAIL_CONN_POOL['last_used'][conn_key]
                    logger.info(f"[Fastmail] 清理过期的FastMail连接 (闲置时间: {idle_time:.1f}秒)")
                except Exception as e:
                    logger.warning(f"清理FastMail连接 {conn_key} 失败: {str(e)}")

        # 每30分钟检查一次（1800秒）
        await asyncio.sleep(1800)



# ========= Gmail 验证器部分 start =========

DELETE_DELAY = 15         # 统一延迟秒数

# ------------------------------------------------------------------
# 辅助：无权限时友好提示（仅私聊回复，群聊静默）
async def _no_perm(event):
    if event.is_private:
        warn = await event.reply("⚠️ 仅限管理员使用")
        asyncio.create_task(_auto_del(event, warn.id))   # 15 秒后删提示
    # 群聊静默

# ------------------------------------------------------------------
# 通用：把 cmd + reply 在 15 秒后一起删除
async def _auto_del(event, *msg_ids):
    await asyncio.sleep(DELETE_DELAY)
    await event.client.delete_messages(event.chat_id, (event.id, *msg_ids))

# ------------------------------------------------------------------
# ——— 添加密钥（彻底兜底版） ——————————————————————
@client.on(events.NewMessage(pattern=r"^添加密钥\s+(.+?)\s+(.+)$", incoming=True))
async def handle_add_secret(event):
    # 0) 权限
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    # 1) 把两段内容拆出来
    name, secret = map(str.strip, event.pattern_match.groups())
    name = name.lower()

    # 2) 如果 name 或 secret 为空，直接提示
    if not name or not secret:
        rsp = await event.respond("❌ 参数不足，用法：`增加密钥 账号标识 Base32密钥`")
        return asyncio.create_task(_auto_del(event, rsp.id))

    # 3) 基础字符检查：允许大小写 A-Z 与 2-7，不足 16 位时报错
    if not re.fullmatch(r"[A-Z2-7]{16,}", secret, flags=re.I):
        rsp = await event.respond("❌ 密钥格式错误：只能包含 A-Z 与 2-7，且长度 ≥16")
        return asyncio.create_task(_auto_del(event, rsp.id))

    # 4) 深度校验：pyotp 能否解析
    try:
        _ = pyotp.TOTP(secret).now()
    except Exception as e:
        rsp = await event.respond(f"❌ 密钥无法解析（{e.__class__.__name__}）")
        return asyncio.create_task(_auto_del(event, rsp.id))

    # 5) 入库
    ok = await GASecretDAO.add_secret(name, secret)
    if ok:
        logger.info(f"Admin {event.sender_id} 增加密钥 {name}")

    rsp = await event.respond("✅ 已增加" if ok else "⚠️ 名称已存在，先删再增")
    asyncio.create_task(_auto_del(event, rsp.id))


# ——— 更名密钥 ——————————————————————————
@client.on(events.NewMessage(pattern=r"^更名密钥\s+(\w+)\s+(\w+)$", incoming=True))
async def handle_rename_secret(event):
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    old_name, new_name = event.pattern_match.groups()
    ok, msg = await GASecretDAO.rename_secret(old_name, new_name)
    if ok:
        logger.info(f"Admin {event.sender_id} 重命名 {old_name} → {new_name}")
    reply = await event.reply(msg)
    asyncio.create_task(_auto_del(event, reply.id))

# ——— 删除密钥 ——————————————————————————
@client.on(events.NewMessage(pattern=r"^删除密钥\s+(\w+)$", incoming=True))
async def handle_del_secret(event):
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    name = event.pattern_match.group(1).lower()
    ok = await GASecretDAO.delete_secret(name)
    if ok:
        logger.info(f"Admin {event.sender_id} 删除密钥 {name}")
    reply = await event.reply("🗑️ 已删除" if ok else "❌ 未找到该密钥")
    asyncio.create_task(_auto_del(event, reply.id))

# ——— 列出密钥（动态倒计时 + 15 秒后撤回） ——————————————
@client.on(events.NewMessage(pattern=r"^列出密钥$", incoming=True))
async def handle_list_secret(event):
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    entries = await GASecretDAO.list_all()
    if not entries:
        reply = await event.reply("（空）尚未保存任何密钥")
        asyncio.create_task(_auto_del(event, reply.id))
        return
    entries.sort(key=lambda x: (len(x[0]), x[0]))

    def render(now:int) -> str:
        lines = []
        for idx, (name, secret) in enumerate(entries, 1):
            totp   = pyotp.TOTP(secret)
            code   = totp.now()
            remain = totp.interval - (now % totp.interval)
            lines.append(f"{idx}. `{name}` → `{code}`（{remain}s）")
        return "\n".join(lines)

    reply = await event.reply(render(int(time.time())), parse_mode="md")

    async def updater():
        try:
            start_time = time.time()
            for _ in range(DELETE_DELAY):
                elapsed = int(time.time() - start_time)
                # 仅在第5秒和第10秒刷新
                if elapsed in (5, 10):
                    await asyncio.sleep(1)
                    await event.client.edit_message(
                        event.chat_id, reply.id,
                        render(int(time.time())), parse_mode="md")
                else:
                    await asyncio.sleep(1)  # 其他时间正常等待，但不刷新
        finally:
            await event.client.delete_messages(event.chat_id, (event.id, reply.id))

    asyncio.create_task(updater())
    
    
    
# ——— 查看密钥 ——————————————————————————
@client.on(events.NewMessage(pattern=r"^查看密钥\s+(\w+)$", incoming=True))
async def handle_view_secret(event):
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    name = event.pattern_match.group(1).lower()
    secret = await GASecretDAO.get_secret(name)
    if secret:
        logger.info(f"Admin {event.sender_id} 查看密钥 {name}")
    reply = await event.reply(secret or "❌ 未找到该密钥")
    asyncio.create_task(_auto_del(event, reply.id))

# ——— 取验证码 ——————————————————————————
@client.on(events.NewMessage(pattern=r"^取验证码\s+(\w+)$", incoming=True))
async def handle_get_code(event):
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    name = event.pattern_match.group(1).lower()
    secret = await GASecretDAO.get_secret(name)
    if not secret:
        reply = await event.reply("❌ 未找到该密钥")
        asyncio.create_task(_auto_del(event, reply.id))
        return
    code = pyotp.TOTP(secret).now()
    logger.info(f"Admin {event.sender_id} 取验证码 {name}: {code}")
    reply = await event.respond(f"{name} 当前验证码：`{code}`", parse_mode="md")
    asyncio.create_task(_auto_del(event, reply.id))

# ========= Gmail 验证器部分 end =========




# ========== Google Auth 二维码解析 (multi + enhance) ==========

# ---- 辅助：判断消息是否含图片（放在装饰器之前） ----
def _is_image(evt: events.NewMessage.Event) -> bool:
    if evt.photo:
        return True
    doc = evt.document
    if doc and getattr(doc, "mime_type", "").startswith("image/"):
        return True
    if getattr(evt.media, "photo", None):
        return True
    if doc and any(isinstance(a, DocumentAttributeImageSize) for a in doc.attributes):
        return True
    return False

# === 轻量 protobuf 解码工具（解析账号迁移码） ===
_TAG_BITS, _WT_LENGTH = 3, 2
def _read_varint(buf, idx):
    v = s = 0
    while True:
        b = buf[idx]; idx += 1
        v |= (b & 0x7F) << s
        if not b & 0x80:
            break
        s += 7
    return v, idx
def _iter_fields(buf):
    i = 0
    while i < len(buf):
        key, i = _read_varint(buf, i)
        fn, wt = key >> _TAG_BITS, key & ((1 << _TAG_BITS) - 1)
        if wt == _WT_LENGTH:
            ln, i = _read_varint(buf, i)
            yield fn, buf[i:i+ln]
            i += ln
        elif wt == 0:
            _, i = _read_varint(buf, i)
        elif wt == 1:
            i += 8
        elif wt == 5:
            i += 4
        else:
            break
def _parse_param(raw):
    n = s = None
    for fn, d in _iter_fields(raw):
        if fn == 1:
            s = base64.b32encode(d).decode().rstrip("=")
        elif fn == 2:
            n = re.sub(r"\s+", "", d.decode()).lower()
    return (n, s) if n and s else None
def _decode_migration(b64):
    try:
        raw = base64.urlsafe_b64decode(b64 + "===")
    except Exception:
        return []
    return [p for fn, d in _iter_fields(raw) if fn == 1 for p in [_parse_param(d)] if p]

# === 主解析函数 ===
async def extract_secret_from_qr(path:str)->Optional[List[Tuple[str,str]]]:
    img = cv2.imread(path)
    if img is None:
        logger.warning(f"读取图片失败 {path}")
        return None
    det = cv2.QRCodeDetector()
    def dec(m): _, info, _, _ = det.detectAndDecodeMulti(m); return [d for d in info if d]

    payloads = dec(img)
    if not payloads:
        h, w = img.shape[:2]
        sc = 2 if max(h, w) < 1000 else 1.4
        big = cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
        gry = cv2.equalizeHist(cv2.cvtColor(big, cv2.COLOR_BGR2GRAY))
        payloads = dec(gry)

    res, seen = [], set()
    for d in payloads:
        if d.startswith("otpauth://"):
            u = urllib.parse.urlparse(d)
            sec = urllib.parse.parse_qs(u.query).get("secret", [None])[0]
            if sec and re.fullmatch(r"[A-Z2-7]{16,}", sec):
                label = urllib.parse.unquote(u.path.lstrip("/"))
                name  = re.sub(r"\s+", "", (label.split(":")[-1] or label)).lower()
                if name not in seen:
                    res.append((name, sec)); seen.add(name)
        elif d.startswith("otpauth-migration://"):
            b64 = urllib.parse.parse_qs(urllib.parse.urlparse(d).query).get("data", [None])[0]
            if b64:
                for n, s in _decode_migration(b64):
                    if n not in seen:
                        res.append((n, s)); seen.add(n)
    return res or None

# === 收图 → 解析 → 写库（管理员私聊） ===
@client.on(events.NewMessage(incoming=True, func=_is_image))
async def handle_qr_photo(event: events.NewMessage.Event):
    # 仅管理员私聊
    if not event.is_private:
        return
    if not await is_admin(event.sender_id):
        return await _no_perm(event)

    tmp_path = None
    try:
        # ① 下载图片
        tmp_path = await event.download_media()
        # 移除了日志输出

        # ② 解析二维码
        pairs = await extract_secret_from_qr(tmp_path)
        if not pairs:
            # 移除了日志输出
            return  # 直接返回，不删除消息、不回复、不缓存

        # ③ 仅当识别到二维码时删除原始消息
        await event.delete()
        # 移除了日志输出

        # ④ 写库（去重）
        existing_names = set(await GASecretDAO.list_names())
        added, skipped, tasks = [], [], []
        for name, secret in pairs:
            if name in existing_names:
                skipped.append(name)
            else:
                tasks.append(GASecretDAO.add_secret(name, secret))
                added.append(name)

        results = await asyncio.gather(*tasks)
        final_added   = [n for n, ok in zip(added, results) if ok]
        final_skipped = skipped + [n for n, ok in zip(added, results) if not ok]

        # ⑤ 回复结果
        lines = []
        if final_added:
            lines.append("✅ 已导入：" + ", ".join(final_added))
        if final_skipped:
            lines.append("⚠️ 已存在：" + ", ".join(final_skipped))
        reply = await event.respond("\n".join(lines))
        # 移除了日志输出

        # ⑥ 15 秒后删除回复消息
        asyncio.create_task(_auto_del(event, reply.id))

    except Exception as e:
        logger.error(f"[QR] 处理图片时出错: {e}", exc_info=True)
    finally:
        # ⑦ 无论是否识别到二维码，都清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            # 移除了日志输出



# 删除机器人信息
@client.on(events.NewMessage)
async def handler(event):
    # 获取当前机器人信息
    me = await client.get_me()

    # 检查消息是否是对机器人的消息的引用
    if event.is_reply and event.reply_to_msg_id:
        # 获取被引用的消息
        replied_message = await event.get_reply_message()
        
        # 确保被引用的消息不为空
        if replied_message:
            # 如果引用的是机器人发送的消息
            if replied_message.sender_id == me.id:
                # 如果用户的消息内容是“删除”
                if event.text.lower() == "删除":
                    # 权限校验：只有管理员可以删除消息
                    if not await is_admin(event.sender_id):
                        return await _no_perm(event)  # 非管理员返回权限不足消息

                    try:
                        # 获取群组信息
                        chat_id = event.chat_id

                        # 删除机器人发送的消息
                        await replied_message.delete()

                        # 日志记录：删除操作成功，不显示群组名称
                        logger.info(f"[删除] 在群组 [{chat_id:>14}] 进行删除了机器人的消息，用户：{event.sender_id}")
                    except MessageDeleteForbiddenError:
                        # 日志记录：删除权限不足，不显示群组名称
                        logger.error(f"[错误] 在群组 [{event.chat_id:>14}] 用户 {event.sender_id} 无法删除消息，可能权限不足")
    
    
    

                    
                
# ✅ 三方辅助机器人 - Part 13：启动欢迎语 + 彩色日志 + 初次管理员提示
init(autoreset=True)

# 修改窗口标题
if os.name == 'nt':  # Windows系统
    ctypes.windll.kernel32.SetConsoleTitleW("三方辅助机器人")
else:  # Linux系统
    sys.stdout.write("\x1b]2;三方辅助机器人\x07")


# ─────────── ASCII 艺术启动提示 ───────────
async def startup_banner():
    # Wave-Bot Banner
    banner_lines = [
        "══════════════  T G  W A V E  B O T  ══════════════",
        "≈≈≈≈≈≈  Ready to Surf Messages !  ≈≈≈≈≈≈",
    ]
    for line in banner_lines:
        logger.info(line)

    logger.info("三方辅助机器人 已启动 ")
    logger.info("连接 Telegram 网络 ...")
    logger.info("账户缓存完成  session.session")
    logger.info("数据库初始化完成 ✓ database.db")
    logger.info(f"启用多线程模式 (线程数: {MAX_WORKERS})")
    logger.info("启动成功！系统已全速运行！")
    logger.info("=================================================")



async def check_admin_tip():
    db = await DB.get_conn()
    async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
        count = (await cursor.fetchone())[0]
    if count == 0:
        logger.warning("⚠ 当前无管理员账号！请私聊机器人并发送“设置管理”命令，以设置第一位管理员。")



async def load_payback_groups():
    global payback_groups
    payback_groups.clear()
    db = await DB.get_conn()
    async with db.execute(
        "SELECT chat_id FROM group_config WHERE group_type = '代付'"
    ) as cursor:
        rows = await cursor.fetchall()
    for (gid,) in rows:
        payback_groups.add(gid)


async def clean_payback_cache():
    """
    定时清理 recent_payback_requests 中过期的 “(chat_id, order_id) => 时间戳” 条目，
    避免与那些存放字符串 order_id 的条目混淆混淆导致类型错误。
    """
    while True:
        await asyncio.sleep(60)
        now = time.time()

        to_remove = []
        for key, val in recent_payback_requests.items():
            # 只对 (chat_id, order_id) 这种 val 应该是数值时间戳的键值对执行过期判断
            if isinstance(key, tuple) and len(key) == 2 and isinstance(val, (int, float)):
                if now - val > PAYBACK_DEDUPE_INTERVAL:
                    to_remove.append(key)

        for key in to_remove:
            recent_payback_requests.pop(key, None)

async def verify_bot_user_id():
    """验证 BOT_USER_ID 是否已初始化，并返回机器人信息"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        logger.warning("⚠️ 警告：机器人 ID 未初始化")
        return None
    else:
        try:
            # 获取机器人用户名和昵称
            bot_entity = await client.get_entity(BOT_USER_ID)
            bot_username = bot_entity.username or "None"
            bot_name = bot_entity.first_name or ""
            if hasattr(bot_entity, 'last_name') and bot_entity.last_name:
                bot_name += f" {bot_entity.last_name}"
            return {
                "id": BOT_USER_ID,
                "username": bot_username,
                "name": bot_name
            }
        except Exception as e:
            logger.warning(f"获取机器人信息失败: {e}")
            return {
                "id": BOT_USER_ID,
                "username": "None",
                "name": "未知"
            }

async def main():
    # 存储所有创建的任务，便于退出时清理
    tasks = []
    
    try:
        # 1. 显示启动横幅
        await startup_banner()

        # 2. 提示是否已有管理员
        await check_admin_tip()

        # 3. 连接并登录 Telegram
        ok = await connect_client()
        if not ok:
            logger.critical("Telegram 连接失败，脚本退出")
            return

        # 4. 验证机器人ID并获取信息
        bot_info = await verify_bot_user_id()
        if bot_info:
            logger.info(f"✅ 验证通过：机器人 ID:{bot_info['id']} - {bot_info['name']} (@{bot_info['username']})")
        else:
            logger.info(f"✅ 验证通过：机器人 ID:{BOT_USER_ID}")

        # 5. 机器人准备就绪提示
        logger.info("✅ 当前机器人已准备就绪，开始监听处理消息…")

        # 6. 加载群组数据
        await load_payback_groups()
        await load_group_data_on_startup()  # 合并加载加入时间和实体
        
        # 7. 启动各种定时任务并保存任务引用
        # 添加连接池清理任务
        task_cleanup_connections = asyncio.create_task(cleanup_stale_connections())
        tasks.append(task_cleanup_connections)
        
        # 原有任务：清理代付缓存
        task_clean_payback = asyncio.create_task(clean_payback_cache())
        tasks.append(task_clean_payback)
        
        # 8. 启动订单号缓存清理任务
        task_clean_orders = asyncio.create_task(GroupJoinTimeManager.cleanup_expired_orders())
        tasks.append(task_clean_orders)
        logger.info("✅ 单号缓存定时清理已启动（60秒清理一次过期记录）")
        
        # 9. 启动其他定时清理任务并获取等待时间
        seconds_until_midnight = await start_scheduled_tasks()
        logger.info(f"✅ 定时清理已启动，数据清理将在 {seconds_until_midnight/3600:.2f} 小时后执行")

        # 10. 无限循环，等待并处理新消息
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"主程序运行出错: {str(e)}", exc_info=True)
    finally:
        # 取消所有后台任务
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"任务 {task.get_name()} 已成功取消")
        logger.info("所有任务已清理，程序退出")
    


# 确保全局变量 BOT_USER_ID 已在脚本其他位置定义（与 verify_bot_user_id 函数对应）
async def daily_reset_forward_counts(initial_seconds_until_midnight):
    """每日凌晨0点清理，确保每天仅执行一次"""
    # 首次清理前的等待（从启动到次日凌晨）
    logger.debug(f"首次清理将在 {initial_seconds_until_midnight:.0f} 秒后执行")
    await asyncio.sleep(initial_seconds_until_midnight)
    
    # 记录最后一次清理的日期（用于去重）
    last_cleaned_date = None
    tz = timezone(timedelta(hours=8))  # 固定时区
    
    while True:
        try:
            now = datetime.now(tz)
            current_date = now.date()  # 获取当前日期（仅年月日）
            
            # 核心校验：如果今天已经清理过，直接跳过
            if last_cleaned_date == current_date:
                # 计算到第二天0点的等待时间
                tomorrow = now + timedelta(days=1)
                midnight = datetime(
                    year=tomorrow.year,
                    month=tomorrow.month,
                    day=tomorrow.day,
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=tz
                )
                next_wait = (midnight - now).total_seconds()
                logger.debug(f"今日已执行清理，将在 {next_wait:.0f} 秒后再次检查")
                await asyncio.sleep(next_wait)
                continue

            # 执行清理逻辑（原有代码保持不变）
            bot_info = await verify_bot_user_id()
            if not bot_info or "id" not in bot_info:
                logger.error("❌ 无法获取有效机器人ID，跳过群组加入时间、群组实体清理")
                db = await DB.get_conn()
                await db.execute("DELETE FROM reminder_forward_log")
                await db.execute("DELETE FROM stopped_reminders")
                await db.commit()
                logger.info("✅ 已完成部分清理（因机器人ID无效，未清理群组加入时间、群组实体）：转发计数数据 + 停止催单记录")
            else:
                current_bot_id = bot_info["id"]
                logger.info("✅ 开始执行每日定时清理...")
                
                # 第二步：检查并更新分组表中的机器人ID（原有逻辑保留）
                db = await DB.get_conn()
                
                # 2.1 检查group_config中是否存在机器人ID字段
                async with db.execute("PRAGMA table_info(group_config)") as cursor:
                    columns = [row[1] for row in await cursor.fetchall()]
                
                if "bot_user_id" not in columns:
                    await db.execute("ALTER TABLE group_config ADD COLUMN bot_user_id INTEGER")
                    logger.info("✅ 为分组表添加更新机器人ID")
                
                # 2.2 查询当前分组表中存储的机器人ID
                async with db.execute("SELECT DISTINCT bot_user_id FROM group_config WHERE bot_user_id IS NOT NULL") as cursor:
                    stored_bot_ids = [row[0] for row in await cursor.fetchall()]
                
                # 2.3 判断是否需要更新机器人ID
                id_updated = False
                if stored_bot_ids and stored_bot_ids[0] != current_bot_id:
                    update_count = await db.execute(
                        "UPDATE group_config SET bot_user_id = ?", 
                        (current_bot_id,)
                    )
                    await db.commit()
                    logger.info(f"✅ 检测到机器人ID变更，已将分组表中{update_count.rowcount}条记录的机器人ID更新为当前ID")
                    id_updated = True
                elif not stored_bot_ids:
                    init_count = await db.execute(
                        "UPDATE group_config SET bot_user_id = ? WHERE bot_user_id IS NULL", 
                        (current_bot_id,)
                    )
                    await db.commit()
                    logger.info(f"✅ 初始化分组表机器人ID为当前登录ID，共更新{init_count.rowcount}条记录")

                # 第三步：执行全量清理（原有逻辑保留）
                # 1. 原有两张表清理
                await db.execute("DELETE FROM reminder_forward_log")
                await db.execute("DELETE FROM stopped_reminders")
                
                # 2. 群组加入时间清理
                delete_group_join_sql = """
                    DELETE FROM group_join_times
                    WHERE 
                        bot_user_id != ? 
                        OR chat_id NOT IN (SELECT DISTINCT chat_id FROM group_config)
                """
                delete_join_result = await db.execute(delete_group_join_sql, (current_bot_id,))
                deleted_join_rows = delete_join_result.rowcount
                
                # 3. 群组实体表清理
                delete_entity_sql = """
                    DELETE FROM group_entities
                    WHERE chat_id NOT IN (SELECT DISTINCT chat_id FROM group_config)
                """
                delete_entity_result = await db.execute(delete_entity_sql)
                deleted_entity_rows = delete_entity_result.rowcount
                
                await db.commit()

                # 第四步：完整性校验（原有逻辑保留）
                if id_updated:
                    logger.info("🔍 开始执行ID变更后的完整性校验...")
                    
                    # 校验1：清理无效分组
                    async with db.execute("""
                        SELECT COUNT(*) FROM group_config 
                        WHERE bot_user_id != ? OR bot_user_id IS NULL
                    """, (current_bot_id,)) as cursor:
                        invalid_groups = (await cursor.fetchone())[0]
                    if invalid_groups > 0:
                        logger.warning(f"⚠️ 发现{invalid_groups}个未正确关联到当前机器人的分组")
                        fix_result = await db.execute("""
                            DELETE FROM group_config 
                            WHERE bot_user_id != ? OR bot_user_id IS NULL
                        """, (current_bot_id,))
                        await db.commit()
                        logger.info(f"✅ 已清理{fix_result.rowcount}个无效分组")

                    # 校验2：清理无效实体
                    async with db.execute("""
                        SELECT COUNT(*) FROM group_entities 
                        WHERE chat_id NOT IN (SELECT DISTINCT chat_id FROM group_config)
                    """) as cursor:
                        invalid_entities = (await cursor.fetchone())[0]
                    if invalid_entities > 0:
                        logger.warning(f"⚠️ 发现{invalid_entities}个未关联到有效分组的实体")
                        fix_entity_result = await db.execute(delete_entity_sql)
                        await db.commit()
                        logger.info(f"✅ 二次清理{fix_entity_result.rowcount}个无效实体")
                
                # 输出清理日志
                logger.info("✅ 已完成每日定时清理：转发计数数据 + 停止催单记录")
                logger.info(f"✅ 已完成清理加入时间：删除{deleted_join_rows}条非当前机器人/未分组记录")
                logger.info(f"✅ 已完成清理群组实体：删除{deleted_entity_rows}条未分组记录")
            
            # 更新最后清理日期为当前日期
            last_cleaned_date = current_date
            
            # 计算到第二天0点的等待时间（确保24小时后再执行）
            tomorrow = now + timedelta(days=1)
            midnight = datetime(
                year=tomorrow.year,
                month=tomorrow.month,
                day=tomorrow.day,
                hour=0,
                minute=0,
                second=0,
                tzinfo=tz
            )
            next_seconds_until_midnight = (midnight - now).total_seconds()
            if next_seconds_until_midnight < 0:
                next_seconds_until_midnight = 86400  # 异常时重置为24小时
            
            logger.debug(f"每日清理完成，等待 {next_seconds_until_midnight:.0f} 秒后执行下次清理")
            await asyncio.sleep(next_seconds_until_midnight)
                
        except Exception as e:
            logger.error("定时清理任务出错（含群组加入时间、群组实体清理）", exc_info=True)
            # 出错后等待1小时重试，并重计算下次等待时间
            await asyncio.sleep(3600)
            now = datetime.now(tz)
            tomorrow = now + timedelta(days=1)
            midnight = datetime(
                year=tomorrow.year,
                month=tomorrow.month,
                day=tomorrow.day,
                hour=0,
                minute=0,
                second=0,
                tzinfo=tz
            )
            next_seconds_until_midnight = (midnight - now).total_seconds()
            if next_seconds_until_midnight < 0:
                next_seconds_until_midnight = 86400


async def start_scheduled_tasks():
    """启动所有定时任务，返回初始清理等待时间（到次日凌晨）"""
    # 计算到次日凌晨0点的等待时间（供首次清理后使用）
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    tomorrow = now + timedelta(days=1)
    midnight = datetime(
        year=tomorrow.year,
        month=tomorrow.month,
        day=tomorrow.day,
        hour=0,
        minute=0,
        second=0,
        tzinfo=tz
    )
    seconds_until_midnight = (midnight - now).total_seconds()
    if seconds_until_midnight < 0:
        seconds_until_midnight = 86400  # 处理时间异常
    
    # 启动定时任务（会立即执行首次全量清理）
    asyncio.create_task(daily_reset_forward_counts(seconds_until_midnight))
    return seconds_until_midnight  # 返回等待时间（到次日凌晨）


# 合并：加载群组加入时间和实体数据（保持不变）
async def load_group_data_on_startup():
    """
    启动时加载群组数据：
    1. 加载群组加入时间
    2. 加载群组实体
    并合并输出日志
    """
    # 初始化统计变量
    join_times_count = 0
    entities_count = 0
    
    try:
        db = await DB.get_conn()
        
        # 1. 加载群组加入时间
        global group_join_times
        try:
            async with db.execute(
                "SELECT chat_id, join_time FROM group_join_times WHERE bot_user_id = ?",
                (BOT_USER_ID,)
            ) as cursor:
                rows = await cursor.fetchall()
                group_join_times = {row[0]: row[1] for row in rows}
                join_times_count = len(group_join_times)
        except Exception as e:
            logger.warning(f"加载群组加入时间时出错: {e}，将使用空字典")
            group_join_times = {}
        
        # 2. 加载群组实体
        global global_group_entities
        try:
            async with db.execute("SELECT chat_id, entity_data FROM group_entities") as cursor:
                async for row in cursor:
                    chat_id, entity_data = row
                    try:
                        entity = pickle.loads(entity_data)
                        global_group_entities[chat_id] = entity
                        entities_count += 1
                    except Exception as e:
                        logger.warning(f"跳过无效实体 [群组ID:{chat_id}]: {e}")
        except Exception as e:
            logger.warning(f"加载群组实体时出错: {e}，将使用空字典")
            global_group_entities = {}
        
        # 合并输出日志
        logger.info(f"✅ 已加载 {join_times_count} 个群组的加入时间，{entities_count} 个群组实体")
        
    except Exception as e:
        logger.error(f"加载群组数据失败: {e}")
        # 出错时确保全局变量初始化
        group_join_times = {}
        global_group_entities = {}
        
        
# ────────────────────────────
# 入口函数（保持不变）
# ────────────────────────────
if __name__ == "__main__":
    # Windows CMD 不支持 ANSI 颜色，可在此关闭彩色日志
    if os.name == "nt" and not os.getenv("ANSICON"):
        pass    # 若你前面有彩色日志相关逻辑，可在此禁用

    try:
        # 初始化数据库（同步调用）
        asyncio.run(init_all_tables())
        logger.info("Google API 凭证表初始化完成")
        
        # 运行异步主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序已终止。")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
