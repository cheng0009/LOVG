import os
from pathlib import Path

class Config:
    # API配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
    
    # ComfyUI配置
    COMFYUI_HOST = "127.0.0.1"
    COMFYUI_PORT = 8188
    COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"
    
    # TTS配置
    TTS_HOST = "127.0.0.1"
    TTS_PORT = 5000
    
    # 项目路径
    BASE_DIR = Path(__file__).parent
    WORKFLOWS_DIR = BASE_DIR / "workflows"
    
    # 输出目录
    OUTPUT_DIR = BASE_DIR / "outputs"
    TEMP_DIR = BASE_DIR / "temp"
    STORYBOARD_DIR = BASE_DIR / "outputs" / "storyboards"
    VIDEO_CLIPS_DIR = BASE_DIR / "outputs" / "video_clips"
    AUDIO_DIR = BASE_DIR / "outputs" / "audio"
    FINAL_VIDEO_DIR = BASE_DIR / "outputs" / "final_videos"
    
    # 工作流文件路径
    IMAGE_WORKFLOW = WORKFLOWS_DIR / "双节棍nunchaku-flux.1-schnell文生图工作流api.json"
    VIDEO_WORKFLOW = WORKFLOWS_DIR / "▶Wan2.2-AllInOne图生视频流.json"
    TTS_WORKFLOW = WORKFLOWS_DIR / "Index-TTSV20-单人情感对话.json"
    
    # 创建所有必要的目录
    @classmethod
    def create_directories(cls):
        for dir_path in [cls.OUTPUT_DIR, cls.TEMP_DIR, cls.STORYBOARD_DIR, 
                        cls.VIDEO_CLIPS_DIR, cls.AUDIO_DIR, cls.FINAL_VIDEO_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    # 视频生成参数
    DEFAULT_VIDEO_DURATION = 5  # 秒
    DEFAULT_VIDEO_FPS = 30
    DEFAULT_VIDEO_QUALITY = "medium"
    
    # 支持的文件格式
    SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']
    SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.flac', '.aac']
    
    # 字幕样式配置
    SUBTITLE_STYLE = {
        # ASS字幕样式（FFmpeg使用）
        'ass': {
            'fontname': 'SimHei',        # 字体名称（黑体，支持中文）
            'fontsize': 48,              # 字号大小
            'primary_color': '&H00FFFFFF',   # 主色（白色）
            'secondary_color': '&H000000FF', # 次色（红色）
            'outline_color': '&H00000000',   # 描边颜色（黑色）
            'back_color': '&H80000000',      # 背景色（半透明黑色）
            'bold': 1,                   # 是否加粗（1=是，0=否）
            'outline': 3,                # 描边宽度
            'shadow': 0,                 # 阴影效果
            'alignment': 2,              # 对齐方式（2=底部居中）
            'margin_v': 10               # 底部边距
        },
        # OpenCV字幕样式（降级方案使用）
        'opencv': {
            'font_scale': 1.8,           # 字号大小（调整为更适合横屏的默认值）
            'text_color': (255, 255, 255),   # 文字颜色（白色）BGR格式
            'outline_color': (0, 0, 0),     # 描边颜色（黑色）
            'bg_color': (0, 0, 0),           # 背景颜色（黑色）
            'thickness': 3,              # 字体粗细
            'outline_thickness': 2,      # 描边粗细
            'bg_padding': 10,            # 背景内边距
            'line_height': 60,           # 行高
            'bottom_margin': 50,         # 底部边距
            'bg_alpha': 0.7              # 背景透明度（0.0-1.0）
        }
    }
    
    # 智能字幕样式预设（根据视频宽高比自动匹配）
    SMART_SUBTITLE_PRESETS = {
        # 竖屏视频 (9:16, 9:18等)
        'portrait': {
            'name': '竖屏优化',
            'description': '适合短视频、社交媒体等竖屏内容',
            'aspect_ratio_range': (0.0, 0.8),  # 宽高比范围
            'style': {
                'font_scale': 2.5,                    # 较大字号，便于手机观看
                'text_color': (255, 255, 255),       # 白色文字
                'outline_color': (0, 0, 0),          # 黑色描边
                'bg_color': (0, 0, 0),               # 黑色背景
                'thickness': 4,                      # 较粗文字
                'outline_thickness': 3,              # 较粗描边
                'bg_padding': 20,                    # 较大背景边距
                'line_height': 80,                   # 较大行高
                'bottom_margin': 120,                # 底部留更多空间
                'bg_alpha': 0.8                      # 较强背景，提升可读性
            }
        },
        # 横屏视频 (16:9等)
        'landscape': {
            'name': '横屏经典',
            'description': '适合电影、电视剧等横屏内容',
            'aspect_ratio_range': (1.3, 2.5),  # 宽高比范围
            'style': {
                'font_scale': 1.8,                    # 适中的字号（比之前更小）
                'text_color': (255, 255, 255),       # 白色文字
                'outline_color': (0, 0, 0),          # 黑色描边
                'bg_color': (0, 0, 0),               # 黑色背景
                'thickness': 3,                      # 标准文字粗细
                'outline_thickness': 2,              # 标准描边
                'bg_padding': 15,                    # 标准背景边距
                'line_height': 60,                   # 标准行高
                'bottom_margin': 60,                 # 标准底部边距
                'bg_alpha': 0.75                     # 标准背景透明度
            }
        },
        # 方形视频 (1:1)
        'square': {
            'name': '方形时尚',
            'description': '适合Instagram等方形内容',
            'aspect_ratio_range': (0.8, 1.3),  # 宽高比范围
            'style': {
                'font_scale': 2.2,                    # 中等字号
                'text_color': (255, 255, 255),       # 白色文字
                'outline_color': (50, 50, 50),       # 深灰描边，更柔和
                'bg_color': (20, 20, 20),            # 深灰背景，更现代
                'thickness': 3,                      # 标准粗细
                'outline_thickness': 2,              # 标准描边
                'bg_padding': 18,                    # 适中边距
                'line_height': 70,                   # 适中行高
                'bottom_margin': 80,                 # 适中底部边距
                'bg_alpha': 0.8                      # 较强背景
            }
        },
        # 超宽屏 (21:9等)
        'ultrawide': {
            'name': '超宽屏影院',
            'description': '适合电影、游戏等超宽屏内容',
            'aspect_ratio_range': (2.1, 3.0),  # 宽高比范围
            'style': {
                'font_scale': 1.6,                    # 较小字号，不占太多空间
                'text_color': (240, 240, 240),       # 稍微偏灰的白色
                'outline_color': (0, 0, 0),          # 黑色描边
                'bg_color': (0, 0, 0),               # 黑色背景
                'thickness': 2,                      # 较细文字
                'outline_thickness': 1,              # 较细描边
                'bg_padding': 12,                    # 较小边距
                'line_height': 50,                   # 较小行高
                'bottom_margin': 40,                 # 较小底部边距
                'bg_alpha': 0.7                      # 较淡背景
            }
        }
    }

# 初始化目录
Config.create_directories()