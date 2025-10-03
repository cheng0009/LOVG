#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版AI视频生成系统启动脚本
"""

import sys
import subprocess
import time
from pathlib import Path

def check_and_install_dependencies():
    """检查并安装依赖"""
    print("🔍 检查依赖包...")
    
    required_packages = [
        'streamlit>=1.28.0',
        'requests>=2.31.0', 
        'pillow>=10.0.0',
        'opencv-python>=4.8.0',
        'moviepy>=1.0.3',
        'pydub>=0.25.1',
        'openai>=1.0.0',
        'websocket-client>=1.6.0',
        'numpy>=1.24.0',
        'psutil>=5.9.0'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        package_name = package.split('>=')[0].split('==')[0].split('>')[0].split('<')[0]
        try:
            __import__(package_name)
            print(f"✅ {package_name} 已安装")
        except ImportError:
            print(f"❌ {package_name} 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📥 安装缺失的依赖包...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'
            ])
            
            for package in missing_packages:
                print(f"  安装 {package}...")
                # 使用国内镜像源加速安装
                try:
                    subprocess.check_call([
                        sys.executable, '-m', 'pip', 'install', package,
                        '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple/'
                    ])
                except subprocess.CalledProcessError:
                    # 如果镜像源失败，尝试默认源
                    subprocess.check_call([
                        sys.executable, '-m', 'pip', 'install', package
                    ])
            
            print("✅ 所有依赖包安装完成")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ 依赖包安装失败: {e}")
            return False
    else:
        print("✅ 所有依赖包已安装")
        return True

def start_comfyui_service():
    """启动ComfyUI服务的说明"""
    print("\n🚀 启动ComfyUI服务")
    print("=" * 50)
    print("请确保您已经:")
    print("1. 下载并安装了ComfyUI")
    print("2. 启动了ComfyUI服务 (默认端口: 8188)")
    print("3. 确认ComfyUI在 http://127.0.0.1:8188 可访问")
    print("\n💡 启动命令示例:")
    print("   cd F:/ComfyUI_windows_portable/ComfyUI")
    print("   python main.py")
    print("\n⏳ 等待ComfyUI服务启动...")

def start_ai_video_system():
    """启动AI视频生成系统"""
    print("\n🎬 启动AI视频生成系统")
    print("=" * 50)
    
    try:
        # 启动Streamlit应用
        main_script = Path(__file__).parent / "main.py"
        if not main_script.exists():
            print(f"❌ 主程序文件不存在: {main_script}")
            return False
        
        print(f"📄 启动主程序: {main_script}")
        subprocess.Popen([
            sys.executable, '-m', 'streamlit', 'run', str(main_script),
            '--server.port', '8501',
            '--server.address', '127.0.0.1'
        ])
        
        print("✅ AI视频生成系统已启动!")
        print("🌐 访问地址: http://127.0.0.1:8501")
        return True
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

def main():
    """主函数"""
    print("🌟 AI视频生成系统优化版启动器")
    print("=" * 50)
    
    # 检查Python版本
    print(f"🐍 Python版本: {sys.version}")
    if sys.version_info < (3, 8):
        print("⚠️  建议使用Python 3.8或更高版本")
    
    # 检查并安装依赖
    if not check_and_install_dependencies():
        print("❌ 依赖检查失败，无法继续启动")
        return
    
    # 启动ComfyUI服务说明
    start_comfyui_service()
    
    # 等待用户确认ComfyUI已启动
    input("\n✅ 确认ComfyUI服务已启动后，按回车键继续...")
    
    # 启动AI视频生成系统
    if start_ai_video_system():
        print("\n🎉 系统启动完成!")
        print("请在浏览器中打开 http://127.0.0.1:8501 使用AI视频生成系统")
        print("\n💡 使用提示:")
        print("  - 系统已优化内存使用，支持大批量视频处理")
        print("  - 视频生成过程有重试机制，提高成功率")
        print("  - 支持分批处理，避免ComfyUI内存溢出")
    else:
        print("\n❌ 系统启动失败")

if __name__ == "__main__":
    main()