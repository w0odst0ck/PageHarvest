"""日志模块：同时输出到控制台和文件"""

import sys
import os
from datetime import datetime


class Logger:
    """统一日志器"""

    LEVELS = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}

    def __init__(self, level: str = "INFO", log_file: str = None):
        self.level = self.LEVELS.get(level.upper(), 1)
        self.log_file = log_file
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def _log(self, level: str, platform: str, message: str):
        if self.LEVELS.get(level, 0) < self.level:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{platform}] [{level}] {message}"
        print(line, file=sys.stderr)
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + '\n')

    def debug(self, platform: str, msg: str): self._log("DEBUG", platform, msg)
    def info(self, platform: str, msg: str): self._log("INFO", platform, msg)
    def warning(self, platform: str, msg: str): self._log("WARNING", platform, msg)
    def error(self, platform: str, msg: str): self._log("ERROR", platform, msg)


# 全局单例
_logger = None


def get_logger(level: str = "INFO", log_file: str = None):
    global _logger
    if _logger is None:
        _logger = Logger(level, log_file)
    return _logger
