import psutil
import time
import gc
from typing import Dict, Optional
import threading
from config import Config
import requests

class ResourceOptimizer:
    """资源优化器，用于监控和优化系统资源使用"""
    
    def __init__(self, comfyui_host: str = "127.0.0.1", comfyui_port: int = 8188):
        self.monitoring = False
        self.monitor_thread = None
        self.comfyui_host = comfyui_host
        self.comfyui_port = comfyui_port
        self.comfyui_base_url = f"http://{comfyui_host}:{comfyui_port}"
        self.comfyui_monitoring = False
        self.thresholds = {
            'memory_percent_warning': 85,  # 内存使用率警告阈值
            'memory_percent_critical': 95,  # 内存使用率危险阈值
            'cpu_percent_warning': 80,      # CPU使用率警告阈值
            'cpu_percent_critical': 95      # CPU使用率危险阈值
        }
    
    def start_monitoring(self):
        """开始资源监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("✅ 资源监控已启动")
    
    def stop_monitoring(self):
        """停止资源监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("🛑 资源监控已停止")
    
    def start_comfyui_monitoring(self):
        """开始ComfyUI服务监控"""
        self.comfyui_monitoring = True
        print("✅ ComfyUI服务监控已启动")
    
    def stop_comfyui_monitoring(self):
        """停止ComfyUI服务监控"""
        self.comfyui_monitoring = False
        print("🛑 ComfyUI服务监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._check_and_optimize()
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                print(f"⚠️ 资源监控异常: {e}")
                time.sleep(10)  # 出错时等待更长时间
    
    def _check_and_optimize(self):
        """检查资源使用情况并优化"""
        if not self._is_psutil_available():
            return
        
        try:
            # 获取系统资源信息
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = memory.percent
            
            # 检查是否需要优化
            if memory_percent > self.thresholds['memory_percent_warning']:
                self._optimize_memory(memory_percent)
            
            if cpu_percent > self.thresholds['cpu_percent_warning']:
                self._optimize_cpu(cpu_percent)
            
            # 检查ComfyUI服务状态（如果启用监控）
            if self.comfyui_monitoring:
                self._check_comfyui_status()
                
        except Exception as e:
            print(f"⚠️ 资源检查异常: {e}")
    
    def _check_comfyui_status(self):
        """检查ComfyUI服务状态"""
        try:
            response = requests.get(f"{self.comfyui_base_url}/system_stats", timeout=3)
            if response.status_code != 200:
                print("⚠️ ComfyUI服务响应异常")
        except requests.exceptions.ConnectionError:
            print("❌ ComfyUI服务连接失败")
            # 可以在这里添加自动重启逻辑
        except Exception as e:
            print(f"⚠️ ComfyUI服务检查异常: {e}")
    
    def _optimize_memory(self, memory_percent: float):
        """优化内存使用"""
        print(f"⚠️ 内存使用率过高: {memory_percent:.1f}%")
        
        # 触发垃圾回收
        collected = gc.collect()
        print(f"🗑️ 垃圾回收完成，回收对象数: {collected}")
        
        # 如果内存使用率仍然很高，执行更激进的优化
        if memory_percent > self.thresholds['memory_percent_critical']:
            print("🚨 内存使用率极高，执行紧急优化...")
            
            # 清理临时文件
            self._cleanup_temp_files()
            
            # 强制垃圾回收
            gc.collect()
            time.sleep(1)
            gc.collect()
            
            # 检查优化后的情况
            if self._is_psutil_available():
                new_memory = psutil.virtual_memory()
                print(f"  优化后内存使用率: {new_memory.percent:.1f}%")
    
    def _optimize_cpu(self, cpu_percent: float):
        """优化CPU使用"""
        print(f"⚠️ CPU使用率过高: {cpu_percent:.1f}%")
        
        # 如果CPU使用率极高，建议暂停一些操作
        if cpu_percent > self.thresholds['cpu_percent_critical']:
            print("🚨 CPU使用率极高，建议减少并发操作")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            import os
            temp_dirs = [Config.TEMP_DIR, Config.VIDEO_CLIPS_DIR, Config.AUDIO_DIR]
            
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    # 删除超过1小时的临时文件
                    current_time = time.time()
                    for file_path in temp_dir.iterdir():
                        if file_path.is_file():
                            try:
                                file_age = current_time - file_path.stat().st_mtime
                                if file_age > 3600:  # 1小时
                                    file_path.unlink()
                                    print(f"🗑️ 清理临时文件: {file_path}")
                            except Exception as e:
                                print(f"⚠️ 清理文件失败 {file_path}: {e}")
        except Exception as e:
            print(f"⚠️ 清理临时文件异常: {e}")
    
    def _is_psutil_available(self) -> bool:
        """检查psutil是否可用"""
        return psutil is not None
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        if not self._is_psutil_available():
            return {"error": "psutil不可用"}
        
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "status": "normal" if memory.percent < 85 and cpu_percent < 80 else "warning"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def force_cleanup(self):
        """强制清理资源"""
        print("🔧 执行强制资源清理...")
        
        # 垃圾回收
        collected = gc.collect()
        print(f"🗑️ 垃圾回收完成，回收对象数: {collected}")
        
        # 清理临时文件
        self._cleanup_temp_files()
        
        # 再次垃圾回收
        gc.collect()
        
        # 显示清理后的状态
        status = self.get_system_status()
        if "error" not in status:
            print(f"📊 清理后系统状态: CPU {status['cpu_percent']:.1f}%, 内存 {status['memory_percent']:.1f}%")

# 全局资源优化器实例
resource_optimizer = ResourceOptimizer()

# 在模块加载时启动监控
resource_optimizer.start_monitoring()