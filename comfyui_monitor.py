#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ComfyUI服务监控和自动重启脚本
"""

import requests
import time
import subprocess
import psutil
import os
from pathlib import Path
from typing import Optional

class ComfyUIMonitor:
    """ComfyUI服务监控器"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.comfyui_process = None
    
    def check_service_status(self) -> bool:
        """检查ComfyUI服务状态"""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_system_resources(self) -> dict:
        """获取系统资源使用情况"""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'available_memory_gb': memory.available / (1024**3)
            }
        except Exception as e:
            print(f"⚠️ 无法获取系统资源信息: {e}")
            return {}
    
    def restart_comfyui(self) -> bool:
        """重启ComfyUI服务"""
        try:
            print("🔧 尝试重启ComfyUI服务...")
            
            # 1. 首先尝试停止现有进程
            self.stop_comfyui()
            
            # 2. 等待一段时间确保进程完全停止
            time.sleep(5)
            
            # 3. 启动新的ComfyUI进程
            # 假设ComfyUI安装在F:\ComfyUI_windows_portable
            comfyui_path = Path("F:/ComfyUI_windows_portable/ComfyUI_windows_portable.exe")
            
            if not comfyui_path.exists():
                print(f"❌ 找不到ComfyUI可执行文件: {comfyui_path}")
                # 尝试其他可能的路径
                possible_paths = [
                    "F:/ComfyUI_windows_portable/ComfyUI_windows_portable.exe",
                    "C:/ComfyUI_windows_portable/ComfyUI_windows_portable.exe",
                    "D:/ComfyUI_windows_portable/ComfyUI_windows_portable.exe",
                    "./ComfyUI_windows_portable.exe"
                ]
                
                for path in possible_paths:
                    path_obj = Path(path)
                    if path_obj.exists():
                        comfyui_path = path_obj
                        print(f"✅ 找到ComfyUI可执行文件: {comfyui_path}")
                        break
            
            if comfyui_path.exists():
                # 启动ComfyUI进程
                print(f"🚀 启动ComfyUI: {comfyui_path}")
                self.comfyui_process = subprocess.Popen([str(comfyui_path)], 
                                                       cwd=comfyui_path.parent)
                print("⏳ 等待ComfyUI服务启动...")
                
                # 等待服务启动
                for i in range(30):  # 最多等待5分钟
                    time.sleep(10)
                    if self.check_service_status():
                        print("✅ ComfyUI服务重启成功")
                        return True
                    print(f"   等待中... ({i+1}/30)")
                
                print("❌ ComfyUI服务启动超时")
                return False
            else:
                print("❌ 无法找到ComfyUI可执行文件，请手动启动")
                return False
                
        except Exception as e:
            print(f"❌ 重启ComfyUI服务失败: {e}")
            return False
    
    def stop_comfyui(self):
        """停止ComfyUI进程"""
        try:
            # 查找并终止ComfyUI相关进程
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'comfyui' in proc.info['name'].lower():
                        print(f"🛑 终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.terminate()
                        proc.wait(timeout=10)  # 等待进程终止
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
            
            # 如果有记录的进程，也尝试终止
            if self.comfyui_process:
                try:
                    self.comfyui_process.terminate()
                    self.comfyui_process.wait(timeout=10)
                    print("🛑 ComfyUI进程已终止")
                except:
                    pass
                    
        except Exception as e:
            print(f"⚠️ 停止ComfyUI进程时出错: {e}")
    
    def monitor_and_maintain(self, check_interval: int = 30):
        """持续监控和维护ComfyUI服务"""
        print("🔍 开始监控ComfyUI服务...")
        print(f"   检查间隔: {check_interval}秒")
        
        while True:
            try:
                # 检查服务状态
                if self.check_service_status():
                    print("✅ ComfyUI服务运行正常")
                    
                    # 检查系统资源
                    resources = self.get_system_resources()
                    if resources:
                        print(f"📊 系统资源: CPU {resources['cpu_percent']:.1f}%, "
                              f"内存 {resources['memory_percent']:.1f}%, "
                              f"可用内存 {resources['available_memory_gb']:.2f}GB")
                        
                        # 如果内存使用率过高，建议重启
                        if resources['memory_percent'] > 90:
                            print("⚠️ 内存使用率过高，建议重启ComfyUI服务")
                            # 可以选择自动重启或提示用户
                            # self.restart_comfyui()
                else:
                    print("❌ ComfyUI服务未响应")
                    # 尝试重启服务
                    if self.restart_comfyui():
                        print("✅ 服务重启成功")
                    else:
                        print("❌ 服务重启失败，请手动处理")
                
                # 等待下次检查
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 监控已停止")
                break
            except Exception as e:
                print(f"⚠️ 监控过程中出错: {e}")
                time.sleep(check_interval)

def main():
    """主函数"""
    print("=== ComfyUI服务监控工具 ===")
    
    # 创建监控器实例
    monitor = ComfyUIMonitor()
    
    # 检查当前服务状态
    print("🔍 检查ComfyUI服务状态...")
    if monitor.check_service_status():
        print("✅ ComfyUI服务正在运行")
    else:
        print("❌ ComfyUI服务未运行")
        # 询问是否要启动服务
        response = input("是否要启动ComfyUI服务？(y/n): ")
        if response.lower() in ['y', 'yes']:
            if monitor.restart_comfyui():
                print("✅ ComfyUI服务启动成功")
            else:
                print("❌ ComfyUI服务启动失败")
    
    # 询问是否要持续监控
    response = input("是否要持续监控ComfyUI服务？(y/n): ")
    if response.lower() in ['y', 'yes']:
        monitor.monitor_and_maintain()

if __name__ == "__main__":
    main()