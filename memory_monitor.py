#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存监控工具
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_system_resources():
    """检查系统资源使用情况"""
    try:
        import psutil
        
        print("📊 系统资源使用情况监控")
        print("=" * 40)
        
        # 获取CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 获取内存信息
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        available_memory_gb = memory.available / (1024**3)
        total_memory_gb = memory.total / (1024**3)
        
        # 获取磁盘信息
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        available_disk_gb = disk.free / (1024**3)
        
        print(f"💻 CPU使用率: {cpu_percent:.1f}%")
        print(f"💾 内存使用率: {memory_percent:.1f}% ({available_memory_gb:.2f}GB / {total_memory_gb:.2f}GB)")
        print(f"🗄️  磁盘使用率: {disk_percent:.1f}% ({available_disk_gb:.2f}GB 可用)")
        
        # 检查是否需要警告
        if memory_percent > 85:
            print("⚠️  内存使用率较高，建议关闭其他程序")
        if disk_percent > 90:
            print("⚠️  磁盘空间不足，建议清理磁盘")
            
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'available_memory_gb': available_memory_gb,
            'disk_percent': disk_percent,
            'available_disk_gb': available_disk_gb
        }
        
    except ImportError:
        print("❌ 未安装psutil库，无法监控系统资源")
        print("💡 安装命令: pip install psutil")
        return None
    except Exception as e:
        print(f"❌ 监控系统资源时出错: {e}")
        return None

def monitor_resources_continuously(duration=60, interval=5):
    """持续监控系统资源"""
    print(f"🔍 开始持续监控系统资源 ({duration}秒)")
    print(f"⏱️  监控间隔: {interval}秒")
    print("按 Ctrl+C 停止监控")
    print("-" * 40)
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            check_system_resources()
            print("-" * 40)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n🛑 监控已停止")

def check_comfyui_resources():
    """检查ComfyUI相关的资源使用情况"""
    try:
        import psutil
        import os
        
        print("🔍 ComfyUI资源使用情况")
        print("=" * 40)
        
        # 查找ComfyUI进程
        comfyui_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                if 'python' in proc.info['name'].lower() and 'comfyui' in ''.join(proc.cmdline()).lower():
                    comfyui_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if comfyui_processes:
            for proc in comfyui_processes:
                try:
                    memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                    cpu_percent = proc.info['cpu_percent']
                    print(f"进程 PID {proc.info['pid']}:")
                    print(f"  CPU使用率: {cpu_percent:.1f}%")
                    print(f"  内存使用: {memory_mb:.1f} MB")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            print("⚠️ 未找到运行中的ComfyUI进程")
            
    except ImportError:
        print("❌ 未安装psutil库，无法监控ComfyUI资源")
    except Exception as e:
        print(f"❌ 监控ComfyUI资源时出错: {e}")

if __name__ == "__main__":
    print("🧠 AI视频生成器内存监控工具")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "continuous":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            monitor_resources_continuously(duration, interval)
        elif sys.argv[1] == "comfyui":
            check_comfyui_resources()
    else:
        print("使用方法:")
        print("  python memory_monitor.py           # 检查当前系统资源")
        print("  python memory_monitor.py continuous [duration] [interval]  # 持续监控")
        print("  python memory_monitor.py comfyui   # 检查ComfyUI资源使用")
        print()
        
        # 默认检查一次系统资源
        check_system_resources()
        print()
        check_comfyui_resources()