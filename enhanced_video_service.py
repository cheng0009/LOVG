from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, 
    concatenate_videoclips, ImageClip
)
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict
from config import Config
import json
import subprocess

class EnhancedVideoService:
    def __init__(self):
        pass
    
    def add_subtitles_with_precise_timing(self, video_path: str, subtitle_path: str, 
                                        output_filename: str) -> Optional[str]:
        """
        使用精确时间戳字幕文件添加字幕到视频
        """
        try:
            if not Path(video_path).exists():
                print(f"❌ 视频文件不存在: {video_path}")
                return None
            
            if not Path(subtitle_path).exists():
                print(f"❌ 字幕文件不存在: {subtitle_path}")
                return None
            
            print(f"ℹ️ 开始添加精确时间戳字幕到视频: {Path(video_path).name}")
            
            # 使用FFmpeg直接添加字幕（最佳方案）
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用FFmpeg的subtitles滤镜添加字幕
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"subtitles='{subtitle_path}'",
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-crf', '18',
                '-y',
                str(output_path)
            ]
            
            print(f"🔧 执行FFmpeg命令: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print(f"✅ 精确时间戳字幕添加成功: {output_path}")
                return str(output_path)
            else:
                print(f"⚠️ FFmpeg添加字幕失败: {result.stderr[:200]}...")
                # 回退到OpenCV方法
                return self._add_subtitles_with_opencv_from_srt(video_path, subtitle_path, output_filename)
                
        except Exception as e:
            print(f"添加精确时间戳字幕失败: {str(e)}")
            return None
    
    def _add_subtitles_with_opencv_from_srt(self, video_path: str, srt_path: str, 
                                          output_filename: str) -> Optional[str]:
        """
        使用OpenCV从SRT文件添加字幕（FFmpeg失败时的回退方案）
        """
        try:
            # 解析SRT文件
            subtitles = self._parse_srt_file(srt_path)
            
            if not subtitles:
                print("❌ 无法解析SRT字幕文件")
                return None
            
            # 使用OpenCV方法添加字幕
            return self._add_subtitles_with_opencv(video_path, subtitles, output_filename)
            
        except Exception as e:
            print(f"使用OpenCV添加SRT字幕失败: {str(e)}")
            return None
    
    def _parse_srt_file(self, srt_path: str) -> List[Dict]:
        """解析 SRT 字幕文件"""
        subtitles = []
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 分割字幕条目
            entries = content.split('\n\n')
            
            for entry in entries:
                lines = entry.strip().split('\n')
                if len(lines) >= 3:
                    # 第一行是序号，第二行是时间，后面是文本
                    time_line = lines[1]
                    text_lines = lines[2:]
                    text = '\n'.join(text_lines)
                    
                    # 解析时间
                    time_parts = time_line.split(' --> ')
                    if len(time_parts) == 2:
                        start_time = self._srt_time_to_seconds(time_parts[0])
                        end_time = self._srt_time_to_seconds(time_parts[1])
                        duration = end_time - start_time
                        
                        subtitles.append({
                            'text': text,
                            'start': start_time,
                            'duration': duration
                        })
            
            return subtitles
            
        except Exception as e:
            print(f"解析 SRT 文件失败: {str(e)}")
            return []
    
    def _srt_time_to_seconds(self, srt_time: str) -> float:
        """将 SRT 时间格式转换为秒数"""
        try:
            # 格式: HH:MM:SS,mmm
            time_part, ms_part = srt_time.split(',')
            h, m, s = map(int, time_part.split(':'))
            ms = int(ms_part)
            
            total_seconds = h * 3600 + m * 60 + s + ms / 1000.0
            return total_seconds
            
        except Exception as e:
            print(f"时间格式转换失败: {str(e)}")
            return 0.0
    
    def _add_subtitles_with_opencv(self, video_path: str, subtitles: List[Dict], 
                                 output_filename: str) -> Optional[str]:
        """
        使用OpenCV添加字幕到视频
        """
        try:
            # 加载视频
            clip = VideoFileClip(video_path)
            
            # 定义添加字幕的函数
            def add_subtitle_to_frame(get_frame, t):
                frame = get_frame(t)
                
                # 查找当前时间应该显示的字幕
                current_subtitle = None
                for subtitle in subtitles:
                    if subtitle['start'] <= t <= (subtitle['start'] + subtitle['duration']):
                        current_subtitle = subtitle
                        break
                
                if current_subtitle:
                    # 使用OpenCV添加字幕
                    frame = self._add_text_to_frame_cv2(
                        frame, current_subtitle['text'])
                
                return frame
            
            # 应用字幕到视频
            final_clip = clip.fl(lambda get_frame, t: add_subtitle_to_frame(get_frame, t))
            
            # 输出路径
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 导出视频
            final_clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            
            # 清理资源
            final_clip.close()
            clip.close()
            
            print(f"✅ OpenCV字幕添加成功: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"OpenCV添加字幕失败: {str(e)}")
            return None
    
    def _add_text_to_frame_cv2(self, frame: np.ndarray, text: str) -> np.ndarray:
        """
        使用OpenCV在视频帧上添加文字
        """
        try:
            # 转换颜色空间 (MoviePy使用RGB, OpenCV使用BGR)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # 获取帧尺寸
            height, width = frame_bgr.shape[:2]
            
            # 设置字体和尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 2.0
            thickness = 3
            text_color = (255, 255, 255)  # 白色文字 (BGR)
            outline_color = (0, 0, 0)     # 黑色描边
            
            # 计算文字尺寸
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            
            # 计算文字位置（底部居中）
            text_x = (width - text_size[0]) // 2
            text_y = height - 50
            
            # 添加黑色描边
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx != 0 or dy != 0:
                        cv2.putText(frame_bgr, text, (text_x + dx, text_y + dy), 
                                  font, font_scale, outline_color, thickness)
            
            # 添加白色文字
            cv2.putText(frame_bgr, text, (text_x, text_y), 
                       font, font_scale, text_color, thickness)
            
            # 转换回RGB颜色空间
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            return frame_rgb
            
        except Exception as e:
            print(f"添加文字到帧失败: {str(e)}")
            return frame  # 返回原始帧

# 测试代码
if __name__ == "__main__":
    print("Enhanced Video Service - 字幕处理模块")
    print("此模块提供精确时间戳字幕添加功能")