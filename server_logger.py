import threading
import datetime
import os
import sys
import re
import time
import queue
import atexit

from enum import IntEnum
from collections import namedtuple
from colorama import init

# 初始化colorama
init()


class LogLevel(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2
    DEBUG = 3


class ServerLogger:
    _instance = None
    _lock = threading.Lock()
    _console_lock = threading.Lock() # 消息同步锁，保证原子性
    
    # 定义日志配置结构
    LogConfig = namedtuple('LogConfig', ['color', 'name'], defaults=('\033[0m', 'UNKNOWN'))
    LOG_CONFIGS = (
        LogConfig("\033[37m", "INFO"),  # 灰色
        LogConfig("\033[33m", "WARNING"),  # 黄色
        LogConfig("\033[31m", "ERROR"),  # 红色
        LogConfig("\033[34m", "DEBUG")  # 蓝色
    )
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_logger()
                    atexit.register(cls._instance._safe_shutdown)  # 注册退出处理函数
        return cls._instance
    
    def __del__(self):
        self._safe_shutdown()
    
    def _init_logger(self):
        """初始化日志系统"""
        # 确保logs目录存在
        os.makedirs('logs', exist_ok=True)
        
        # 初始化日志文件
        self.current_base_date = datetime.date.today().strftime("%Y-%m-%d")
        max_index = self._find_max_index(self.current_base_date)
        filename = os.path.join('logs', f"{self.current_base_date}-{max_index + 1}.log")
        self.log_file = open(filename, "a", buffering=1, encoding="utf-8")
        
        # 初始化队列和后台线程
        self._log_queue = queue.Queue(maxsize=1024)
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_logs,
            name="LogWorker",
            daemon=True  # 必须为true，防止死锁
        )
        self._worker_thread.start()
    
    def _safe_shutdown(self):
        """安全关闭日志系统"""
        if not hasattr(self, "_running") or not self._running:
            return
        
        # 设置标签防止继续插入
        self._running = False
        
        # 发送终止信号通知工作线程退出
        self._log_queue.put(None)
        
        # 等待队列处理完成
        self._log_queue.join()

        # 等待线程终止
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)  # 设置超时时间，超时直接忽略
        
        # 关闭文件
        if hasattr(self, "log_file"):
            self.log_file.close()
    
    @staticmethod
    def _find_max_index(base_date: str) -> int:
        """查找当前日期的最大文件索引"""
        pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.log$")
        max_index = 0
        
        try:
            for filename in os.listdir('logs'):
                match = pattern.match(filename)
                if match:
                    file_date, index_str = match.groups()
                    if file_date == base_date:
                        max_index = max(max_index, int(index_str))
        except FileNotFoundError:
            pass  # 如果logs目录不存在，直接返回0
        
        return max_index
    
    def _process_logs(self):
        """后台日志处理线程"""
        while True:
            # 无限等待
            item = self._log_queue.get(block=True)
            if item is None:  # 收到终止信号
                self._log_queue.task_done()
                break
            
            self._write_log(item)
            self._log_queue.task_done()
    
    def _rotate_log_file(self, new_date):
        """切换日志文件到新日期"""
        try:
            max_index = self._find_max_index(new_date)
            filename = os.path.join('logs', f"{new_date}-{max_index + 1}.log")
            tmp_log_file = open(filename, "a", buffering=1, encoding="utf-8")
        except Exception as e:
            sys.stderr.writer(f"日志文件切换失败: {str(e)}，新日期应为：[{new_date}]")
            return#直接返回
        #执行切换
        if hasattr(self, 'log_file') and self.log_file:
            self.log_file.close()
        self.log_file = tmp_log_file
        self.current_base_date = new_date
    
    def _write_log(self, item):
        """写入和输出日志"""
        # 检查是否需要切换日志文件
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        if current_date != self.current_base_date:
            self._rotate_log_file(current_date)
        try:
            # 文件写入
            log_line = item
            self.log_file.write(log_line)
            self.log_file.flush()
            os.fsync(self.log_file.fileno())
        except Exception as e:
            print(f"日志写入失败：{str(e)}")
    
    def _log(self, level: LogLevel, message: str):
        if not self._running:  # 防止停止过程插入消息
            return
        #同步锁
        with self._console_lock:
            timestamp = datetime.datetime.now()
            thread = threading.current_thread()
            thread_info = thread.name if thread.name else f"Thread-{thread.ident}"
            time_str = timestamp.strftime("%H:%M:%S")
            config = self.LOG_CONFIGS[level]
            log_line = f"[{time_str}] [{thread_info}/{config.name}]: {message}\n"
            
            # 控制台输出
            sys.stdout.write(f"{config.color}{log_line}\033[0m")
            #插入到写入队列
            self._log_queue.put(log_line)
    
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
    #先测试不同颜色输出
    print("颜色测试")
    
    
    # 定义所有字体颜色的ANSI转义码（30-37, 90-97）
    colors = [
        '\033[30m', '\033[31m', '\033[32m', '\033[33m', '\033[34m', '\033[35m', '\033[36m', '\033[37m',
        '\033[90m', '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[97m'
    ]
    
    # 生成带颜色的"Test"字符串（每个颜色后自动重置）
    color_tests = [f"{color}Test\033[0m" for color in colors]
    
    # 每8个为一组输出
    for i in range(0, len(color_tests), 8):
        print(' '.join(color_tests[i:i + 8]))
    
    print("多线程测试")
    
    logger = ServerLogger()
    
    def worker(fun):
        for _ in range(5):
            time.sleep(0.01)
            fun("线程消息")
    
    threads = [
        threading.Thread(target=worker, args=(logger.debug,), name="TaskExecutor0"),
        threading.Thread(target=worker, args=(logger.info,), name="TaskExecutor1"),
        threading.Thread(target=worker, args=(logger.warning,)),
        threading.Thread(target=worker, args=(logger.error,))
    ]
    
    for t in threads:
        t.start()
    
    # 主线程日志
    for _ in range(5):
        logger.info("主线程消息")
        time.sleep(0.01)
    
    # 不等待线程直接退出（测试关闭逻辑）
    print("主线程执行完成，即将退出...")