"""
进程管理工具
"""

import os
import sys
import subprocess
import psutil
from typing import Optional


class ProcessManager:
    """进程管理器"""
    
    @staticmethod
    def start_task_process(task_id: int) -> Optional[int]:
        """启动任务进程"""
        try:
            # 构建进程启动命令
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'task_runner.py')
            cmd = [sys.executable, script_path, str(task_id)]
            
            # 根据操作系统设置进程启动参数
            popen_kwargs = {
                'cwd': os.path.dirname(os.path.dirname(__file__))
            }
            
            # Windows特定参数
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # Linux/Unix 系统 - 创建新的进程组以便独立运行
                popen_kwargs['preexec_fn'] = os.setsid
            
            # 启动进程，不重定向输出，让日志直接写入文件
            process = subprocess.Popen(cmd, **popen_kwargs)
            
            return process.pid
        except Exception as e:
            print(f"启动任务进程失败: {e}")
            return None
    
    @staticmethod
    def stop_task_process(process_id: int) -> bool:
        """停止任务进程"""
        try:
            if not process_id:
                return False
                
            process = psutil.Process(process_id)
            
            if process.is_running():
                # 优雅停止 - 先发送 TERM 信号
                process.terminate()
                
                # 等待进程结束
                try:
                    process.wait(timeout=5)
                    return True
                except psutil.TimeoutExpired:
                    # 强制终止 - 发送 KILL 信号
                    try:
                        process.kill()
                        process.wait(timeout=3)
                        return True
                    except psutil.TimeoutExpired:
                        # 尝试终止进程组（处理子进程）
                        try:
                            if sys.platform == 'win32':
                                # Windows: 终止整个进程树
                                for child in process.children(recursive=True):
                                    child.kill()
                                process.kill()
                            else:
                                # Linux: 终止进程组
                                os.killpg(process.pid, 9)
                        except Exception:
                            pass
                        return False
            else:
                return True
                
        except psutil.NoSuchProcess:
            return True  # 进程不存在也算停止成功
        except Exception as e:
            print(f"停止进程失败: {e}")
            return False
    
    @staticmethod
    def is_process_running(process_id: int) -> bool:
        """检查进程是否运行中"""
        try:
            if process_id:
                process = psutil.Process(process_id)
                return process.is_running()
        except psutil.NoSuchProcess:
            pass
        return False
    
    @staticmethod
    def get_process_info(process_id: int) -> Optional[dict]:
        """获取进程信息"""
        try:
            if process_id:
                process = psutil.Process(process_id)
                if process.is_running():
                    return {
                        'pid': process.pid,
                        'name': process.name(),
                        'status': process.status(),
                        'cpu_percent': process.cpu_percent(),
                        'memory_info': process.memory_info(),
                        'create_time': process.create_time()
                    }
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"获取进程信息失败: {e}")
        return None