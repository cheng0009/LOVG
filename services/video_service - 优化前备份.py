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

class VideoService:
    def __init__(self):
        pass
    
    def check_connection(self) -> bool:
        """检查视频服务状态（本地服务，检查依赖库）"""
        try:
            # 检查必要的依赖库是否可用
            import moviepy
            from PIL import Image
            import cv2
            import numpy as np
            return True
        except ImportError:
            return False
    
    def merge_video_clips(self, video_paths: List[str], output_filename: str) -> Optional[str]:
        """合并视频片段 - 优化内存使用"""
        try:
            # 过滤掉无效的视频路径
            valid_paths = [path for path in video_paths if path and Path(path).exists()]
            
            if not valid_paths:
                print("没有有效的视频文件进行合并")
                return None
            
            print(f"ℹ️ 开始合并 {len(valid_paths)} 个视频片段")
            
            # 分批处理以降低内存使用
            batch_size = 2  # 每次只处理2个视频
            if len(valid_paths) <= batch_size:
                # 视频数量较少，直接处理
                return self._merge_videos_direct(valid_paths, output_filename)
            else:
                # 视频数量较多，分批处理
                return self._merge_videos_batched(valid_paths, output_filename, batch_size)
            
        except Exception as e:
            print(f"合并视频失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _merge_videos_direct(self, video_paths: List[str], output_filename: str) -> Optional[str]:
        """直接合并视频片段"""
        # 加载视频片段
        clips = []
        target_size = None  # 使用第一个视频的分辨率作为目标分辨率
        target_fps = None   # 使用第一个视频的帧率作为目标帧率
        
        for i, path in enumerate(video_paths):
            try:
                print(f"ℹ️ 加载视频片段 {i+1}/{len(video_paths)}: {Path(path).name}")
                clip = VideoFileClip(path)
                
                print(f"  原始参数: {clip.size[0]}x{clip.size[1]} @ {clip.fps}fps, 时长: {clip.duration:.2f}s")
                
                # 使用第一个视频的分辨率和帧率作为目标
                if target_size is None:
                    target_size = clip.size
                    target_fps = clip.fps  # 保持原始帧率
                    print(f"ℹ️ 使用原始参数作为目标: {target_size[0]}x{target_size[1]} @ {target_fps}fps")
                
                # 统一分辨率（如果不一致才调整）
                if clip.size != target_size:
                    print(f"  ⚠️ 调整分辨率: {clip.size} -> {target_size}")
                    clip = clip.resize(target_size)
                
                # 统一帧率（如果不一致才调整）
                if hasattr(clip, 'fps') and abs(clip.fps - target_fps) > 0.1:
                    print(f"  ⚠️ 调整帧率: {clip.fps} -> {target_fps}")
                    clip = clip.set_fps(target_fps)
                else:
                    print(f"  ✅ 帧率已匹配: {clip.fps}fps")
                
                # 确保视频没有损坏
                if clip.duration > 0:
                    clips.append(clip)
                    print(f"  ✅ 成功加载视频片段 {i+1}，处理后时长: {clip.duration:.2f}s")
                else:
                    print(f"  ❌ 视频片段 {i+1} 时长为0，跳过")
                    clip.close()
                
            except Exception as e:
                print(f"  ❌ 加载视频文件失败 {path}: {str(e)}")
                continue
        
        if not clips:
            print("没有可用的视频片段")
            return None
        
        print(f"ℹ️ 开始合并 {len(clips)} 个视频片段")
        
        # 合并视频
        final_video = concatenate_videoclips(clips, method="compose")
        
        # 输出路径
        output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"ℹ️ 导出视频到: {output_path}")
        
        # 导出视频（使用原始帧率，避免强制转换）
        print(f"ℹ️ 开始导出视频，预计时长: {sum(c.duration for c in clips):.2f}s，帧率: {target_fps}fps")
        
        final_video.write_videofile(
            str(output_path),
            fps=target_fps,
            audio_codec='aac',
            codec='libx264',
            bitrate='5000k',      # 降低码率以减少内存使用
            preset='fast',        # 使用快速预设减少内存占用
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            ffmpeg_params=[
                '-pix_fmt', 'yuv420p',
                '-crf', '23',         # 适中的质量参数
                '-movflags', '+faststart',  # 优化文件结构
                '-avoid_negative_ts', 'make_zero'  # 避免时间戳问题
            ]
        )
        
        # 清理内存
        final_video.close()
        for clip in clips:
            clip.close()
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        print(f"✅ 视频合并成功: {output_path}")
        return str(output_path)
    
    def _merge_videos_batched(self, video_paths: List[str], output_filename: str, batch_size: int = 2) -> Optional[str]:
        """分批合并视频片段以降低内存使用"""
        print(f"ℹ️ 开始分批合并 {len(video_paths)} 个视频片段 (批大小: {batch_size})")
        
        batch_count = 0
        intermediate_videos = []
        
        # 按批次处理视频
        for i in range(0, len(video_paths), batch_size):
            batch_paths = video_paths[i:i + batch_size]
            batch_count += 1
            
            print(f"ℹ️ 处理第 {batch_count} 批视频 ({len(batch_paths)} 个片段)")
            
            # 为中间文件生成唯一名称
            intermediate_name = f"{output_filename}_batch_{batch_count}"
            intermediate_path = self._merge_videos_direct(batch_paths, intermediate_name)
            
            if intermediate_path and Path(intermediate_path).exists():
                intermediate_videos.append(intermediate_path)
                print(f"✅ 第 {batch_count} 批处理完成: {intermediate_path}")
            else:
                print(f"❌ 第 {batch_count} 批处理失败")
            
            # 强制垃圾回收以释放内存
            import gc
            gc.collect()
            import time
            time.sleep(1)  # 短暂等待以确保资源释放
        
        # 合并中间视频
        if len(intermediate_videos) == 1:
            # 只有一个中间视频，直接重命名
            final_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            import shutil
            shutil.move(intermediate_videos[0], final_path)
            print(f"✅ 视频合并完成: {final_path}")
            return str(final_path)
        else:
            # 多个中间视频，再次合并
            print(f"ℹ️ 合并 {len(intermediate_videos)} 个中间视频")
            return self._merge_videos_direct(intermediate_videos, output_filename)
    
    def add_audio(self, video_path: str, audio_path: str, output_filename: str, cover_duration: float = 0) -> Optional[str]:
        """添加音频到视频，支持封面延迟"""
        try:
            if not Path(video_path).exists():
                print(f"视频文件不存在: {video_path}")
                return None
                
            if not Path(audio_path).exists():
                print(f"音频文件不存在: {audio_path}")
                return None
            
            # 加载视频和音频
            video = VideoFileClip(video_path)
            audio = AudioFileClip(audio_path)
            
            print(f"ℹ️ 视频时长: {video.duration:.2f}s, 音频时长: {audio.duration:.2f}s")
            if cover_duration > 0:
                print(f"ℹ️ 封面时长: {cover_duration:.2f}s, 音频将延迟 {cover_duration:.2f}s 开始")
            
            # 计算音频应该对应的视频时长（去除封面部分）
            video_content_duration = video.duration - cover_duration
            
            # 调整音频长度与视频内容部分匹配
            if abs(audio.duration - video_content_duration) > 0.1:
                if audio.duration > video_content_duration:
                    print(f"  ⚠️ 音频较长，裁剪到 {video_content_duration:.2f}s")
                    audio = audio.subclip(0, video_content_duration)
                elif audio.duration < video_content_duration and audio.duration > 0:
                    print(f"  ⚠️ 音频较短，延伸到 {video_content_duration:.2f}s")
                    # 使用正确的循环方法
                    try:
                        # MoviePy的新版本使用audio_loop方法
                        audio = audio.audio_loop(duration=video_content_duration)
                    except AttributeError:
                        # 如果没有audio_loop方法，使用旧方法
                        try:
                            # 循环音频直到匹配视频内容长度
                            loop_count = int(video_content_duration / audio.duration) + 1
                            from moviepy.audio.AudioClip import CompositeAudioClip
                            # 创建循环音频片段
                            audio_clips = []
                            current_time = 0
                            while current_time < video_content_duration:
                                clip_duration = min(audio.duration, video_content_duration - current_time)
                                audio_clips.append(audio.subclip(0, clip_duration).set_start(current_time))
                                current_time += clip_duration
                            audio = CompositeAudioClip(audio_clips)
                        except Exception as e:
                            print(f"  ⚠️ 音频循环失败: {e}")
                            # 如果循环失败，使用原始音频
                            pass
            else:
                print(f"  ✅ 音频和视频内容时长匹配")
            
            # 如果有封面，将音频延迟开始
            if cover_duration > 0:
                from moviepy.audio.AudioClip import AudioClip
                # 创建静音部分（封面部分）
                silence = AudioClip(lambda t: [0, 0], duration=cover_duration, fps=44100)
                # 合并静音和实际音频
                from moviepy.audio.AudioClip import CompositeAudioClip
                audio = CompositeAudioClip([silence, audio.set_start(cover_duration)])
                print(f"  ✅ 音频已延迟 {cover_duration:.2f}s，总时长: {audio.duration:.2f}s")
            
            # 设置音频
            final_video = video.set_audio(audio)
            
            # 输出路径
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            
            # 导出视频（使用原始帧率）
            final_video.write_videofile(
                str(output_path),
                fps=video.fps,  # 使用原始视频的帧率
                audio_codec='aac',
                codec='libx264'
            )
            
            # 清理内存
            final_video.close()
            video.close()
            audio.close()
            
            return str(output_path)
            
        except Exception as e:
            print(f"添加音频失败: {str(e)}")
            return None
    
    def add_subtitles_from_srt(self, video_path: str, srt_path: str, output_filename: str) -> Optional[str]:
        """从 SRT 文件添加字幕到视频"""
        try:
            if not Path(video_path).exists():
                print(f"视频文件不存在: {video_path}")
                return None
            
            if not Path(srt_path).exists():
                print(f"字幕文件不存在: {srt_path}")
                return None
            
            # 解析SRT文件
            subtitles = self._parse_srt_file(srt_path)
            
            if not subtitles:
                print("无法解析字幕文件")
                return None
            
            # 使用解析出的字幕数据添加字幕
            return self.add_subtitles(video_path, subtitles, output_filename)
            
        except Exception as e:
            print(f"从 SRT 文件添加字幕失败: {str(e)}")
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
    
    def add_subtitles(self, video_path: str, subtitles: List[Dict], output_filename: str, style_config: Dict = None) -> Optional[str]:
        """添加字幕到视频（使用OpenCV方法避免ImageMagick依赖）。支持自定义样式配置"""
        try:
            # 检查输入参数
            if not video_path or not Path(video_path).exists():
                print(f"❌ 视频文件不存在: {video_path}")
                return None
            
            if not subtitles:
                print("❌ 没有字幕内容")
                return video_path  # 返回原视频
            
            print(f"ℹ️ 开始添加字幕到视频: {Path(video_path).name}")
            print(f"🎨 接收到的样式配置: {style_config}")
            
            # 确保有样式配置
            if style_config is None:
                print("⚠️ 未接收到样式配置，使用默认样式")
                style_config = Config.SUBTITLE_STYLE['opencv'].copy()
            else:
                print(f"✅ 使用自定义样式配置: {style_config}")
            
            # 使用OpenCV和ffmpeg方法添加字幕
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建字幕文件（ASS格式，支持中文）
            ass_content = self._create_ass_subtitle(subtitles, style_config)
            ass_file = Config.TEMP_DIR / f"{output_filename}_subtitles.ass"
            
            with open(ass_file, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            print(f"ℹ️ 创建字幕文件: {ass_file}")
            print(f"ℹ️ 字幕文件将保留用于检查")
            
            # 使用ffmpeg添加字幕
            import subprocess
            import os
            
            # 修复路径问题，使用绝对路径和正确的转义
            ass_file_path = str(ass_file.absolute())
            video_path_abs = str(Path(video_path).absolute())
            output_path_abs = str(Path(output_path).absolute())
            
            # 确保路径存在
            if not ass_file.exists():
                print(f"❌ 字幕文件不存在: {ass_file_path}")
                raise Exception("Subtitle file not found")
            
            print(f"📁 字幕文件路径: {ass_file_path}")
            print(f"📁 输入视频路径: {video_path_abs}")
            print(f"📁 输出视频路径: {output_path_abs}")
            
            # 使用更安全的FFmpeg命令格式，避免路径问题
            try:
                # 方法1：使用单引号格式
                subtitle_filter = f"subtitles='{ass_file_path.replace(chr(92), '/')}'"
                
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', video_path_abs,
                    '-vf', subtitle_filter,
                    '-c:a', 'copy',
                    '-c:v', 'libx264',
                    '-crf', '18',
                    '-y',
                    output_path_abs
                ]
                
                print(f"🔧 尝试FFmpeg命令(方法1): ffmpeg -i ... -vf {subtitle_filter} ... ")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0:
                    print(f"✅ FFmpeg字幕添加成功: {output_path}")
                    # 注意：不再删除字幕文件，保留用于检查
                    # ass_file.unlink(missing_ok=True)
                    return str(output_path)
                else:
                    print(f"⚠️ FFmpeg方法1失败: {result.stderr[:200]}...")
                    
            except Exception as e:
                print(f"⚠️ FFmpeg方法1异常: {str(e)[:100]}...")
            
            # 方法2：尝试使用短路径
            try:
                # 将字幕文件复制到一个简单的路径
                simple_ass_file = Config.TEMP_DIR / "subtitle.ass"
                import shutil
                shutil.copy2(ass_file, simple_ass_file)
                
                subtitle_filter = f"subtitles=subtitle.ass"
                
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-i', video_path_abs,
                    '-vf', subtitle_filter,
                    '-c:a', 'copy',
                    '-c:v', 'libx264', 
                    '-crf', '18',
                    '-y',
                    output_path_abs
                ]
                
                print(f"🔧 尝试FFmpeg命令(方法2): ffmpeg -i ... -vf {subtitle_filter} ...")
                
                # 在temp目录中执行命令
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, 
                                      cwd=str(Config.TEMP_DIR), timeout=120)
                
                if result.returncode == 0:
                    print(f"✅ FFmpeg字幕添加成功(方法2): {output_path}")
                    # 注意：不再删除字幕文件，保留用于检查
                    # ass_file.unlink(missing_ok=True)
                    # simple_ass_file.unlink(missing_ok=True)
                    return str(output_path)
                else:
                    print(f"⚠️ FFmpeg方法2也失败: {result.stderr[:200]}...")
                    
            except Exception as e:
                print(f"⚠️ FFmpeg方法2异常: {str(e)[:100]}...")
            
            print(f"⚠️ FFmpeg所有尝试都失败，使用OpenCV降级方案")
            print(f"🎨 传递给OpenCV的样式配置: {style_config}")
            result = self._add_subtitles_with_opencv(video_path, subtitles, output_filename, style_config)
            # 注意：保留字幕文件用于检查
            return result
            
        except Exception as e:
            print(f"添加字幕失败: {str(e)}")
            print(f"🎨 出错时的样式配置: {style_config}")
            # 如果所有方法都失败，返回原视频
            return video_path
    
    def _create_ass_subtitle(self, subtitles: List[Dict], style_config: Dict = None) -> str:
        """创建ASS格式字幕文件内容。支持自定义样式配置"""
        # 默认ASS样式配置
        default_ass_style = {
            'fontname': 'SimHei',        # 字体名称（默认黑体）
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
        }
        
        # 如果有OpenCV样式配置，转换为ASS格式
        if style_config:
            print(f"ℹ️ 收到OpenCV样式配置，转换为ASS格式: {style_config}")
            
            # 智能调整字号（与OpenCV方法保持一致）
            original_font_scale = style_config.get('font_scale', 2.0)
            
            # 字号转换（OpenCV font_scale -> ASS fontsize）
            # 基准映射：font_scale 2.0 对应 fontsize 48
            adjusted_fontsize = int(original_font_scale * 24)
            # 限制在合理范围内
            adjusted_fontsize = max(20, min(120, adjusted_fontsize))
            
            default_ass_style['fontsize'] = adjusted_fontsize
            print(f"📊 ASS字号转换: font_scale {original_font_scale:.2f} -> fontsize {adjusted_fontsize}")
            
            # 文字颜色转换（BGR -> ASS颜色格式）
            if 'text_color' in style_config:
                bgr = style_config['text_color']
                # ASS颜色格式: &H00BBGGRR
                default_ass_style['primary_color'] = f"&H00{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"
            
            # 描边颜色转换
            if 'outline_color' in style_config:
                bgr = style_config['outline_color']
                default_ass_style['outline_color'] = f"&H00{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"
            
            # 背景颜色转换（考虑透明度）
            if 'bg_color' in style_config and 'bg_alpha' in style_config:
                bgr = style_config['bg_color']
                alpha = style_config['bg_alpha']
                # ASS透明度: 00=不透明, FF=透明
                alpha_hex = int((1 - alpha) * 255)
                default_ass_style['back_color'] = f"&H{alpha_hex:02X}{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"
            
            # 描边宽度转换
            if 'outline_thickness' in style_config:
                default_ass_style['outline'] = style_config['outline_thickness']
            
            # 底部边距转换
            if 'bottom_margin' in style_config:
                default_ass_style['margin_v'] = style_config['bottom_margin'] // 5  # 缩放比例
            
            # 字体粗细转换（thickness > 3 则加粗）
            if 'thickness' in style_config:
                default_ass_style['bold'] = 1 if style_config['thickness'] > 3 else 0
            
            print(f"ℹ️ 转换后的ASS样式: {default_ass_style}")
        
        # 构建ASS样式字符串
        style_line = f"Style: Default,{default_ass_style['fontname']},{default_ass_style['fontsize']},{default_ass_style['primary_color']},{default_ass_style['secondary_color']},{default_ass_style['outline_color']},{default_ass_style['back_color']},{default_ass_style['bold']},0,0,0,100,100,0,0,1,{default_ass_style['outline']},{default_ass_style['shadow']},{default_ass_style['alignment']},10,10,{default_ass_style['margin_v']},1"
        
        ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        events = []
        for subtitle in subtitles:
            text = subtitle.get('text', '')
            start_time = subtitle.get('start', 0)
            duration = subtitle.get('duration', 3)
            end_time = start_time + duration
            
            # 转换为 ASS 时间格式 (H:MM:SS.cc)
            start_ass = self._seconds_to_ass_time(start_time)
            end_ass = self._seconds_to_ass_time(end_time)
            
            # 清理文本（移除特殊字符）
            clean_text = text.replace('\n', '\\N').replace('{', '\\{').replace('}', '\\}')
            
            event = f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{clean_text}"
            events.append(event)
        
        return ass_header + '\n'.join(events)
    
    def _seconds_to_ass_time(self, seconds: float) -> str:
        """将秒数转换为ASS时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centiseconds = int((secs % 1) * 100)
        secs = int(secs)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"
    
    def _add_subtitles_with_opencv(self, video_path: str, subtitles: List[Dict], output_filename: str, style_config: Dict = None) -> Optional[str]:
        """使用OpenCV直接在视频帧上添加字幕（备用方法）。支持自定义样式配置"""
        try:
            # 检查输入参数
            if not video_path or not Path(video_path).exists():
                print(f"❌ 视频文件不存在: {video_path}")
                return None
                
            print("ℹ️ 使用OpenCV方法添加字幕...")
            
            import cv2
            import numpy as np
            from moviepy.editor import VideoFileClip
            
            # 默认样式配置
            default_style = {
                'font_scale': 2.0,           # 字号大小
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
            
            # 合并用户自定义样式
            if style_config:
                print(f"ℹ️ 收到自定义样式配置: {style_config}")
                
                # 智能调整字号大小（基于视频分辨率和宽高比）
                video_clip = VideoFileClip(video_path)
                video_width = video_clip.size[0]
                video_height = video_clip.size[1]
                video_clip.close()  # 立即释放
                
                # 计算宽高比
                aspect_ratio = video_width / video_height if video_height > 0 else 1.0
                
                # 根据视频分辨率和宽高比调整字号倍数
                original_font_scale = style_config.get('font_scale', 2.0)
                
                # 根据宽高比调整基础字号
                if aspect_ratio > 1.8:  # 横屏视频（16:9等）
                    base_scale = 1.8  # 横屏使用较小的字号
                elif aspect_ratio < 0.8:  # 竖屏视频
                    base_scale = 2.5  # 竖屏使用较大的字号
                else:  # 接近正方形
                    base_scale = 2.2
                
                # 根据分辨率调整字号
                if video_height <= 480:  # SD视频
                    adjusted_font_scale = base_scale * 0.6
                elif video_height <= 720:  # HD视频
                    adjusted_font_scale = base_scale * 0.8
                elif video_height <= 1080:  # Full HD
                    adjusted_font_scale = base_scale * 1.0
                elif video_height <= 1440:  # 2K
                    adjusted_font_scale = base_scale * 1.2
                else:  # 4K及以上
                    adjusted_font_scale = base_scale * 1.5
                
                # 确保字号不会过小或过大
                adjusted_font_scale = max(0.8, min(4.0, adjusted_font_scale))
                
                if adjusted_font_scale != original_font_scale:
                    print(f"📊 根据视频分辨率({video_width}x{video_height})和宽高比({aspect_ratio:.2f})调整字号: {original_font_scale:.2f} -> {adjusted_font_scale:.2f}")
                    style_config['font_scale'] = adjusted_font_scale
                else:
                    print(f"✅ 字号大小适合当前分辨率: {adjusted_font_scale:.2f}")
                
                default_style.update(style_config)
                print(f"ℹ️ 合并后的样式: {default_style}")
            else:
                print("⚠️ 未收到自定义样式，使用默认样式")
            
            # 加载视频
            clip = VideoFileClip(video_path)
            
            def add_subtitle_to_frame(get_frame, t):
                frame = get_frame(t)
                
                # 查找当前时间的字幕
                current_subtitle = None
                for subtitle in subtitles:
                    start = subtitle.get('start', 0)
                    duration = subtitle.get('duration', 3)
                    if start <= t < start + duration:
                        current_subtitle = subtitle.get('text', '')
                        break
                
                if current_subtitle:
                    # 使用OpenCV添加文字（增强可见性）
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # 使用配置的文字参数
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = default_style['font_scale']
                    text_color = default_style['text_color']
                    outline_color = default_style['outline_color']
                    bg_color = default_style['bg_color']
                    thickness = default_style['thickness']
                    outline_thickness = default_style['outline_thickness']
                    bg_padding = default_style['bg_padding']
                    line_height = default_style['line_height']
                    bottom_margin = default_style['bottom_margin']
                    
                    # 处理多行文本
                    lines = current_subtitle.split('\n')
                    
                    # 计算整体文本区域的高度
                    total_height = len(lines) * line_height
                    start_y = frame.shape[0] - total_height - bottom_margin
                    
                    for i, line in enumerate(lines):
                        if line.strip():  # 跳过空行
                            # 获取文字尺寸
                            (text_width, text_height), _ = cv2.getTextSize(line, font, font_scale, thickness)
                            
                            # 居中位置
                            x = (frame.shape[1] - text_width) // 2
                            y = start_y + (i * line_height)
                            
                            # 添加背景矩形增强对比度
                            if default_style['bg_alpha'] > 0:
                                # 创建背景矩形
                                bg_start_x = max(0, x - bg_padding)
                                bg_start_y = max(0, y - text_height - bg_padding)
                                bg_end_x = min(frame_bgr.shape[1], x + text_width + bg_padding)
                                bg_end_y = min(frame_bgr.shape[0], y + bg_padding)
                                
                                # 直接在原图上绘制半透明背景
                                overlay = frame_bgr.copy()
                                cv2.rectangle(overlay, 
                                            (bg_start_x, bg_start_y), 
                                            (bg_end_x, bg_end_y), 
                                            bg_color, -1)
                                
                                # 正确的透明度混合：bg_alpha是背景的不透明度
                                cv2.addWeighted(overlay, default_style['bg_alpha'], 
                                              frame_bgr, 1 - default_style['bg_alpha'], 
                                              0, frame_bgr)
                                
                                print(f"🎨 添加背景: 颜色{bg_color}, 透明度{default_style['bg_alpha']}, 区域({bg_start_x},{bg_start_y})-({bg_end_x},{bg_end_y})")
                            
                            # 添加描边效果
                            for offset in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
                                cv2.putText(frame_bgr, line, (x + offset[0], y + offset[1]), 
                                          font, font_scale, outline_color, thickness + outline_thickness)
                            
                            # 添加主文字
                            cv2.putText(frame_bgr, line, (x, y), font, font_scale, text_color, thickness)
                    
                    frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                
                return frame
            
            # 应用字幕到视频
            final_clip = clip.fl(lambda get_frame, t: add_subtitle_to_frame(get_frame, t))
            
            # 输出路径
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            
            # 导出视频
            final_clip.write_videofile(
                str(output_path),
                fps=clip.fps,
                audio_codec='aac',
                codec='libx264',
                preset='fast'  # 使用快速预设减少内存占用
            )
            
            # 清理内存
            final_clip.close()
            clip.close()
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            return str(output_path)
            
        except Exception as e:
            print(f"❌ OpenCV字幕添加失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return video_path
    
    def create_video_with_cover(self, video_path: str, cover_template_path: str, 
                               title: str, output_filename: str) -> Optional[str]:
        """为视频添加封面（返回封面时长信息）"""
        try:
            # 检查输入参数
            if not video_path or not Path(video_path).exists():
                print(f"❌ 视频文件不存在: {video_path}")
                return None
            
            # 获取原始视频的分辨率信息
            video = VideoFileClip(video_path)
            video_size = video.size  # (width, height)
            video_fps = video.fps
            
            print(f"ℹ️ 原始视频参数: {video_size[0]}x{video_size[1]} @ {video_fps}fps")
            
            # 创建与视频分辨率匹配的封面图片
            cover_path = self.create_cover_image(cover_template_path, title, "temp_cover", target_size=video_size)
            
            if not cover_path:
                video.close()
                return video_path  # 如果封面创建失败，返回原视频
            
            # 加载封面
            cover_duration = 3.0  # 封面显示3秒
            cover = ImageClip(cover_path).set_duration(cover_duration)
            
            # 确保封面分辨率与视频一致
            if cover.size != video_size:
                print(f"⚠️ 调整封面分辨率: {cover.size} -> {video_size}")
                cover = cover.resize(video_size)
            
            print(f"ℹ️ 封面时长: {cover_duration}s, 视频时长: {video.duration}s")
            print(f"ℹ️ 封面分辨率: {cover.size}, 视频分辨率: {video.size}")
            
            # 合并封面和视频
            final_video = concatenate_videoclips([cover, video])
            
            # 输出路径
            output_path = Config.FINAL_VIDEO_DIR / f"{output_filename}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            
            # 导出视频（使用原始视频的帧率和分辨率）
            print(f"ℹ️ 导出参数: {video_size[0]}x{video_size[1]} @ {video_fps}fps")
            
            final_video.write_videofile(
                str(output_path),
                fps=video_fps,  # 使用原始视频的帧率
                audio_codec='aac',
                codec='libx264',
                preset='fast'  # 使用快速预设减少内存占用
            )
            
            # 清理内存
            final_video.close()
            video.close()
            cover.close()
            
            # 删除临时封面文件
            Path(cover_path).unlink(missing_ok=True)
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            print(f"✅ 封面视频创建成功，总时长: {cover_duration + video.duration:.2f}s")
            return str(output_path)
            
        except Exception as e:
            print(f"添加封面失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return video_path
    
    def create_cover_image(self, template_path: str, title: str, output_filename: str, target_size: tuple = None) -> Optional[str]:
        """创建视频封面图片（支持指定目标分辨率）"""
        try:
            # 如果有模板文件，使用模板
            if template_path and Path(template_path).exists():
                img = Image.open(template_path)
                # 如果指定了目标尺寸，调整模板尺寸
                if target_size:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                    print(f"ℹ️ 调整模板尺寸到: {target_size[0]}x{target_size[1]}")
            else:
                # 创建默认封面，使用目标尺寸或默认尺寸
                if target_size:
                    cover_size = target_size
                    print(f"ℹ️ 使用目标分辨率创建封面: {cover_size[0]}x{cover_size[1]}")
                else:
                    cover_size = (1920, 1080)
                    print(f"⚠️ 使用默认分辨率创建封面: {cover_size[0]}x{cover_size[1]}")
                
                img = Image.new('RGB', cover_size, color='#2C3E50')
            
            # 添加标题文字
            draw = ImageDraw.Draw(img)
            
            # 尝试使用支持中文的字体
            try:
                # Windows系统常见的中文字体
                font_paths = [
                    "C:/Windows/Fonts/simhei.ttf",      # 黑体
                    "C:/Windows/Fonts/simsun.ttc",      # 宋体
                    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
                    "C:/Windows/Fonts/simkai.ttf",      # 楷体
                    "C:/Windows/Fonts/simfang.ttf",     # 仿宋
                    "/System/Library/Fonts/PingFang.ttc",  # macOS中文字体
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux字体
                ]
                
                font = None
                font_size = 80
                
                for font_path in font_paths:
                    if Path(font_path).exists():
                        try:
                            font = ImageFont.truetype(font_path, font_size)
                            print(f"✅ 使用字体: {font_path}")
                            break
                        except Exception as e:
                            print(f"⚠️ 字体加载失败 {font_path}: {e}")
                            continue
                
                if font is None:
                    # 如果没有找到合适的字体，使用默认字体
                    font = ImageFont.load_default()
                    print("⚠️ 使用默认字体，可能不支持中文")
                    
            except Exception as e:
                print(f"字体加载异常: {e}")
                font = ImageFont.load_default()
            
            # 计算文字位置（居中）
            # 使用textbbox方法获取文字边界框
            try:
                bbox = draw.textbbox((0, 0), title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except:
                # 如果textbbox不可用，使用textsize（已弃用但兼容）
                try:
                    text_width, text_height = draw.textsize(title, font=font)
                except:
                    # 如果都不可用，使用估算值
                    text_width = len(title) * font_size // 2
                    text_height = font_size
            
            x = (img.width - text_width) // 2
            y = (img.height - text_height) // 2
            
            # 绘制文字（带阴影效果）
            shadow_offset = 3
            draw.text((x + shadow_offset, y + shadow_offset), title, fill='black', font=font)
            draw.text((x, y), title, fill='white', font=font)
            
            # 保存封面
            output_path = Config.TEMP_DIR / f"{output_filename}.png"
            img.save(output_path)
            
            print(f"✅ 封面图片创建成功: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"创建封面图片失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_video_info(self, video_path: str) -> Optional[Dict]:
        """获取视频信息"""
        try:
            if not Path(video_path).exists():
                return None
            
            clip = VideoFileClip(video_path)
            info = {
                'duration': clip.duration,
                'fps': clip.fps,
                'size': clip.size,
                'width': clip.w,
                'height': clip.h
            }
            clip.close()
            
            return info
            
        except Exception as e:
            print(f"获取视频信息失败: {str(e)}")
            return None
    
    def create_video_preview(self, video_path: str, num_frames: int = 9) -> Optional[str]:
        """创建视频预览图（多帧拼接）"""
        try:
            if not Path(video_path).exists():
                return None
            
            clip = VideoFileClip(video_path)
            duration = clip.duration
            
            # 计算取帧的时间点
            time_points = [i * duration / (num_frames + 1) for i in range(1, num_frames + 1)]
            
            # 提取帧
            frames = []
            for t in time_points:
                frame = clip.get_frame(t)
                frames.append(frame)
            
            clip.close()
            
            # 创建预览图（3x3网格）
            rows = int(np.sqrt(num_frames))
            cols = (num_frames + rows - 1) // rows
            
            frame_height, frame_width = frames[0].shape[:2]
            preview_width = frame_width * cols
            preview_height = frame_height * rows
            
            preview = np.zeros((preview_height, preview_width, 3), dtype=np.uint8)
            
            for i, frame in enumerate(frames):
                row = i // cols
                col = i % cols
                y1 = row * frame_height
                y2 = y1 + frame_height
                x1 = col * frame_width
                x2 = x1 + frame_width
                preview[y1:y2, x1:x2] = frame
            
            # 保存预览图
            output_path = Config.TEMP_DIR / f"preview_{Path(video_path).stem}.jpg"
            cv2.imwrite(str(output_path), cv2.cvtColor(preview, cv2.COLOR_RGB2BGR))
            
            return str(output_path)
            
        except Exception as e:
            print(f"创建视频预览失败: {str(e)}")
            return None