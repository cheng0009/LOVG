@echo off
echo 正在启动AI视频生成器...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查是否存在虚拟环境
REMif not exist "venv\" (
REM    echo 创建虚拟环境...
REM    python -m venv venv
REM )

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
REM echo 安装依赖包...
REM pip install -r requirements.txt

REM 检查ComfyUI服务
echo 检查ComfyUI服务连接...
curl -s http://127.0.0.1:8188/system_stats >nul 2>&1
if errorlevel 1 (
    echo 警告: ComfyUI服务未运行 (127.0.0.1:8188)
    echo 请确保ComfyUI服务已启动
    echo.
)

REM 启动Streamlit应用
echo 启动AI视频生成器...
echo 浏览器将自动打开: http://localhost:8501
echo.
streamlit run main.py

pause