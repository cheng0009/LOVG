#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI视频生成器 - 开发启动脚本
用于开发环境快速启动应用
"""

import subprocess
import sys
import os
import shutil

def find_python_executable():
    """查找可用的Python可执行文件"""
    # 优先使用当前Python解释器
    current_python = sys.executable
    if current_python and os.path.exists(current_python):
        return current_python
    
    # 尝试从环境变量中查找
    python_candidates = [
        'python',
        'python3',
        'python.exe',
        'python3.exe'
    ]
    
    for candidate in python_candidates:
        python_path = shutil.which(candidate)
        if python_path:
            return python_path
    
    # 如果都找不到，返回默认值
    return 'python'

def check_streamlit_installation(python_exe):
    """检查Streamlit是否安装"""
    try:
        result = subprocess.run(
            [python_exe, '-c', 'import streamlit; print(streamlit.__version__)'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Streamlit已安装，版本: {version}")
            return True
        else:
            print(f"❌ Streamlit未安装或版本不兼容")
            return False
    except Exception as e:
        print(f"❌ 检查Streamlit安装状态失败: {e}")
        return False

def main():
    """开发环境启动脚本"""
    print("🚀 启动AI视频生成器开发环境...")
    
    # 确保在正确的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"📁 工作目录: {script_dir}")
    
    # 检查main.py是否存在
    if not os.path.exists('main.py'):
        print("❌ 错误：找不到main.py文件")
        sys.exit(1)
    
    # 查找Python可执行文件
    python_exe = find_python_executable()
    print(f"🐍 使用Python: {python_exe}")
    
    # 检查Streamlit安装
    if not check_streamlit_installation(python_exe):
        print("❌ 请先安装Streamlit: pip install streamlit")
        sys.exit(1)
    
    # 启动Streamlit应用
    try:
        print("📝 正在启动 streamlit run main.py...")
        subprocess.run([python_exe, '-m', 'streamlit', 'run', 'main.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ 应用已停止")

if __name__ == "__main__":
    main()