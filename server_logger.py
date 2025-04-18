import threading
import datetime
import os
import sys
import re
import time
from enum import IntEnum
from collections import namedtuple
from colorama import init

#初始化colorama
init()


class LogLevel(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2
    DEBUG = 3


class ServerLogger:
    _instance = None
    _lock = threading.Lock()
    _log_lock = threading.Lock()

    # 定义日志配置结构
    LogConfig = namedtuple('LogConfig', ['color', 'name'], defaults=('\033[0m', 'UNKNOWN'))
    LOG_CONFIGS = (
        LogConfig("\033[97m", "INFO"),  # 白色
        LogConfig("\033[93m", "WARNING"),  # 黄色
        LogConfig("\033[91m", "ERROR"),  # 红色
        LogConfig("\033[94m", "DEBUG")  # 蓝色
    )

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_logger()
        return cls._instance

    def __del__(self):
        if hasattr(self, "log_file"):
            self.log_file.close()

    def _init_logger(self):
        """初始化日志文件"""
        base_date = datetime.date.today().strftime("%Y-%m-%d")
        max_index = self._find_max_index(base_date)
        filename = f"{base_date}-{max_index + 1}.log"
        self.log_file = open(filename, "a", buffering=1, encoding="utf-8")

    @staticmethod
    def _find_max_index(base_date: str) -> int:
        """查找当前日期的最大文件索引"""
        pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.log$")
        max_index = 0
        for filename in os.listdir():
            match = pattern.match(filename)
            if match:
                file_date, index_str = match.groups()
                if file_date == base_date:
                    max_index = max(max_index, int(index_str))
        return max_index

    def _log(self, level: LogLevel, message: str):
        """核心日志方法"""
        with self._log_lock:
            # 构建日志内容
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            thread = threading.current_thread()
            thread_info = thread.name if thread.name else f"Thread-{thread.ident}"

            # 获取配置信息
            config = self.LOG_CONFIGS[level]

            log_line = (
                f"[{time_str}] "
                f"[{thread_info}/{config.name}]: "
                f"{message}\n"
            )

            # 控制台输出
            sys.stdout.write(f"{config.color}{log_line}\033[0m")

            # 文件写入
            self.log_file.write(log_line)
            self.log_file.flush()
            os.fsync(self.log_file.fileno())

    # 日志级别方法
    def info(self, message: str):
        self._log(LogLevel.INFO, message)

    def warning(self, message: str):
        self._log(LogLevel.WARNING, message)

    def error(self, message: str):
        self._log(LogLevel.ERROR, message)

    def debug(self, message: str):
        self._log(LogLevel.DEBUG, message)

# 示例用法
if __name__ == "__main__":
    logger = ServerLogger()

    def worker(fun):
        fun("Worker thread message")

    threads = (
        threading.Thread(target=worker, args=(logger.debug,), name="TaskExecutor0"),
        threading.Thread(target=worker, args=(logger.info,), name="TaskExecutor1"),
        threading.Thread(target=worker, args=(logger.warning,)),
        threading.Thread(target=worker, args=(logger.error,))
    )
    for i in threads:
        i.start()

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    time.sleep(3)