"""
任务日志管理工具
"""

import os
import logging
from datetime import datetime
from typing import Optional
import re


class TaskLogger:
    """任务日志管理器"""
    
    def __init__(self, log_dir: str = "task_logs"):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录路径
        """
        self.log_dir = log_dir
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _sanitize_filename(self, task_name: str) -> str:
        """
        清理任务名称，生成安全的文件名
        
        Args:
            task_name: 任务名称
            
        Returns:
            清理后的文件名
        """
        # 移除或替换不安全的字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', task_name)
        # 限制文件名长度
        if len(filename) > 100:
            filename = filename[:100]
        # 确保不以点开头或结尾
        filename = filename.strip('. ')
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = 'unknown_task'
        return filename
    
    def _find_recent_log_file(self, task_name: str) -> Optional[dict]:
        """
        查找任务最近的日志文件
        
        Args:
            task_name: 任务名称
            
        Returns:
            最近日志文件的信息字典，包含path和date
        """
        try:
            filename_prefix = self._sanitize_filename(task_name)
            recent_file = None
            recent_date = None
            
            for filename in os.listdir(self.log_dir):
                if filename.startswith(filename_prefix + '_') and filename.endswith('.log'):
                    # 提取日期部分
                    date_part = filename[len(filename_prefix)+1:-4]  # 去掉前缀和.log后缀
                    
                    try:
                        # 验证日期格式
                        datetime.strptime(date_part, '%Y-%m-%d')
                        
                        if recent_date is None or date_part > recent_date:
                            recent_date = date_part
                            recent_file = os.path.join(self.log_dir, filename)
                    except ValueError:
                        # 日期格式不正确，跳过
                        continue
            
            if recent_file:
                return {
                    'path': recent_file,
                    'date': recent_date
                }
            
            return None
            
        except Exception as e:
            print(f"查找最近日志文件失败: {e}")
            return None
    
    def get_log_file_path(self, task_name: str, date: str = None) -> str:
        """
        获取任务日志文件路径
        
        Args:
            task_name: 任务名称
            date: 日期字符串，如果不提供则使用今天的日期
            
        Returns:
            日志文件路径
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        filename = self._sanitize_filename(task_name)
        return os.path.join(self.log_dir, f"{filename}_{date}.log")
    
    def create_logger(self, task_name: str, task_id: int) -> logging.Logger:
        """
        为任务创建日志记录器
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            
        Returns:
            配置好的日志记录器
        """
        logger_name = f"task_{task_id}"
        logger = logging.getLogger(logger_name)
        
        # 如果已经配置过，直接返回
        if logger.handlers:
            return logger
        
        logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        log_file = self.get_log_file_path(task_name)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # 写入任务开始标记
        logger.info(f"=== 任务开始 - {task_name} (ID: {task_id}) ===")
        
        return logger
    
    def log_task_start(self, task_name: str, task_id: int, parameters: dict = None):
        """
        记录任务开始
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            parameters: 任务参数
        """
        logger = self.create_logger(task_name, task_id)
        logger.info(f"任务启动成功")
        
        if parameters:
            logger.info("任务参数:")
            for key, value in parameters.items():
                logger.info(f"  {key}: {value}")
    
    def log_task_end(self, task_name: str, task_id: int, status: str = "completed"):
        """
        记录任务结束
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            status: 结束状态
        """
        logger_name = f"task_{task_id}"
        logger = logging.getLogger(logger_name)
        
        if logger.handlers:
            logger.info(f"=== 任务结束 - 状态: {status} ===")
            
            # 关闭所有处理器
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
    
    def log_trade_action(self, task_name: str, task_id: int, action: str, 
                        symbol: str, quantity: float, price: float = None, 
                        result: str = "success", error_msg: str = None):
        """
        记录交易动作
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            action: 交易动作（buy/sell）
            symbol: 交易对
            quantity: 数量
            price: 价格
            result: 结果（success/error）
            error_msg: 错误信息
        """
        logger_name = f"task_{task_id}"
        logger = logging.getLogger(logger_name)
        
        if result == "success":
            price_info = f" @ {price}" if price else ""
            logger.info(f"交易成功 - {action.upper()} {quantity} {symbol}{price_info}")
        else:
            logger.error(f"交易失败 - {action.upper()} {quantity} {symbol} - {error_msg}")
    
    def log_round_complete(self, task_name: str, task_id: int, round_num: int, 
                          total_rounds: int, success_count: int, fail_count: int):
        """
        记录轮次完成
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            round_num: 当前轮次
            total_rounds: 总轮次
            success_count: 成功次数
            fail_count: 失败次数
        """
        logger_name = f"task_{task_id}"
        logger = logging.getLogger(logger_name)
        
        logger.info(f"轮次 {round_num}/{total_rounds} 完成 - 成功: {success_count}, 失败: {fail_count}")
    
    def read_task_logs(self, task_name: str, max_lines: int = 1000) -> str:
        """
        读取任务日志内容
        
        Args:
            task_name: 任务名称
            max_lines: 最大行数
            
        Returns:
            日志内容
        """
        # 首先尝试读取今天的日志文件
        today_log_file = self.get_log_file_path(task_name)
        
        log_file_to_read = None
        file_date = None
        
        if os.path.exists(today_log_file):
            log_file_to_read = today_log_file
            file_date = datetime.now().strftime('%Y-%m-%d')
        else:
            # 如果今天的日志文件不存在，查找最近的日志文件
            recent_file = self._find_recent_log_file(task_name)
            if recent_file:
                log_file_to_read = recent_file['path']
                file_date = recent_file['date']
        
        if not log_file_to_read:
            return f"""任务 "{task_name}" 尚未生成日志文件。

可能的原因：
1. 任务从未启动过
2. 任务正在启动中，日志文件尚未创建
3. 日志文件被意外删除

建议操作：
- 启动任务以生成日志
- 刷新页面重试
- 检查任务状态是否正常"""
        
        try:
            with open(log_file_to_read, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 如果文件为空
            if not lines:
                return f"""任务 "{task_name}" 的日志文件为空。

可能的原因：
1. 任务刚刚启动，尚未写入日志
2. 日志已被清空
3. 任务启动失败

请等待片刻后刷新，或检查任务运行状态。"""
            
            # 如果行数超过限制，只返回最后的行数
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
                content = f"... (显示最后 {max_lines} 行)\n" + "".join(lines)
            else:
                content = "".join(lines)
            
            # 如果不是今天的日志，添加日期标识
            if file_date != datetime.now().strftime('%Y-%m-%d'):
                content = f"=== 历史日志 ({file_date}) ===\n\n" + content
                
            return content
            
        except Exception as e:
            return f"读取日志文件失败: {str(e)}\n\n请检查文件权限或联系管理员。"
    
    def clear_task_logs(self, task_name: str) -> bool:
        """
        清空任务日志（清空今天的日志文件）
        
        Args:
            task_name: 任务名称
            
        Returns:
            是否成功
        """
        log_file = self.get_log_file_path(task_name)
        
        try:
            if os.path.exists(log_file):
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("")
                return True
            return False
        except Exception as e:
            print(f"清空日志文件失败: {e}")
            return False
    
    def get_log_file_size(self, task_name: str) -> int:
        """
        获取日志文件大小（今天的日志文件）
        
        Args:
            task_name: 任务名称
            
        Returns:
            文件大小（字节）
        """
        log_file = self.get_log_file_path(task_name)
        
        try:
            if os.path.exists(log_file):
                return os.path.getsize(log_file)
            return 0
        except Exception:
            return 0
    
    def list_all_log_files(self) -> list:
        """
        列出所有日志文件
        
        Returns:
            日志文件列表
        """
        try:
            files = []
            for filename in os.listdir(self.log_dir):
                if filename.endswith('.log'):
                    filepath = os.path.join(self.log_dir, filename)
                    size = os.path.getsize(filepath)
                    modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    # 解析文件名，提取任务名和日期
                    name_without_ext = filename[:-4]  # 移除.log后缀
                    
                    # 尝试解析新格式的文件名 (任务名_日期)
                    if '_' in name_without_ext:
                        parts = name_without_ext.rsplit('_', 1)  # 从右边分割一次
                        if len(parts) == 2:
                            task_name, date_part = parts
                            try:
                                # 验证日期格式
                                datetime.strptime(date_part, '%Y-%m-%d')
                                display_name = f"{task_name} ({date_part})"
                            except ValueError:
                                # 日期格式不正确，使用原文件名
                                display_name = name_without_ext
                        else:
                            display_name = name_without_ext
                    else:
                        # 旧格式的文件名
                        display_name = name_without_ext
                    
                    files.append({
                        'name': display_name,
                        'filename': filename,
                        'size': size,
                        'modified': modified
                    })
            
            return sorted(files, key=lambda x: x['modified'], reverse=True)
            
        except Exception as e:
            print(f"列出日志文件失败: {e}")
            return []


# 全局日志管理器实例
task_logger = TaskLogger()