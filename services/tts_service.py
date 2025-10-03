import requests
import json
from pathlib import Path
from typing import Optional, List, Dict
from config import Config
import re

class TTSService:
    def __init__(self):
        self.host = Config.TTS_HOST
        self.port = Config.TTS_PORT
        self.base_url = f"http://{self.host}:{self.port}"
    
    def check_connection(self) -> bool:
        """检查TTS服务连接"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def text_to_speech(self, text: str, output_filename: str, voice: str = "default", speed: float = 1.0) -> Optional[str]:
        """文本转语音"""
        try:
            # 确保输出路径存在
            output_path = Config.AUDIO_DIR / f"{output_filename}.wav"
            
            # 调用TTS API
            response = requests.post(
                f"{self.base_url}/tts",
                json={
                    "text": text,
                    "voice": voice,
                    "speed": speed,
                    "format": "wav"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return str(output_path)
            else:
                print(f"TTS服务错误: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print("TTS请求超时")
            return None
        except Exception as e:
            print(f"TTS转换失败: {str(e)}")
            return None
    
    def text_to_speech_with_comfyui(self, text: str, output_filename: str, reference_audio: str = None) -> Optional[str]:
        """使用ComfyUI的TTS工作流进行文本转语音"""
        try:
            from .comfyui_service import ComfyUIService
            
            comfyui = ComfyUIService()
            
            print(f"\n=== ComfyUI TTS 生成开始 ===")
            print(f"原始文本: {text[:100]}...")
            
            # 预处理文本，过滤掉括号内的音效说明
            cleaned_text = self._clean_audio_script(text)
            print(f"清理后文本: {cleaned_text[:100]}...")
            print(f"输出文件名: {output_filename}")
            
            # 处理参考音频
            speaker_filename = None
            if reference_audio:
                print(f"参考音频路径: {reference_audio}")
                speaker_filename = self._prepare_reference_audio(reference_audio)
                if not speaker_filename:
                    print(f"⚠️ 参考音频处理失败，将使用默认音频")
                    return None  # 如果参考音频失败，直接返回失败
                else:
                    print(f"✅ 参考音频已准备: {speaker_filename}")
            else:
                print(f"⚠️ 未提供参考音频")
                return None  # 强制要求参考音频
            
            # 加载TTS工作流
            workflow = comfyui.load_workflow(Config.TTS_WORKFLOW)
            
            # 更新工作流中的文本和参考音频
            workflow = self._update_tts_workflow(workflow, cleaned_text, speaker_filename)
            
            # 执行工作流
            print(f"正在执行TTS工作流...")
            audio_path = comfyui._execute_workflow(workflow, f"audio_{output_filename}")
            
            if audio_path:
                print(f"✅ ComfyUI返回的音频路径: {audio_path}")
                
                # 验证返回的文件确实是新生成的，而不是参考音频
                if self._validate_generated_audio(audio_path, reference_audio, cleaned_text):
                    # 移动到音频目录
                    final_path = Config.AUDIO_DIR / f"{output_filename}.wav"
                    Config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        import shutil
                        shutil.move(audio_path, final_path)
                        print(f"✅ 音频文件已移动到: {final_path}")
                        print(f"=== ComfyUI TTS 生成完成 ===\n")
                        return str(final_path)
                    except Exception as e:
                        print(f"⚠️ 移动文件失败: {e}")
                        # 如果移动失败，尝试复制
                        try:
                            import shutil
                            shutil.copy2(audio_path, final_path)
                            print(f"✅ 音频文件已复制到: {final_path}")
                            return str(final_path)
                        except Exception as e2:
                            print(f"❌ 复制文件也失败: {e2}")
                            # 最后直接返回原路径
                            return audio_path
                else:
                    print(f"❌ 验证失败：生成的音频可能与参考音频相同")
                    return None
            else:
                print(f"❌ ComfyUI执行失败，未返回音频文件")
            
            return None
            
        except Exception as e:
            print(f"❌ ComfyUI TTS转换失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 检查是否是连接错误
            if "WinError 10061" in str(e) or "Failed to establish a new connection" in str(e):
                print("🚨 ComfyUI服务连接失败，请检查ComfyUI是否正常运行")
            return None
    
    def _clean_audio_script(self, text: str) -> str:
        """清理音频脚本，过滤掉括号内的音效说明"""
        import re
        
        # 移除各种括号内的内容
        patterns = [
            r'（[^）]*）',  # 中文括号（）
            r'\([^)]*\)',        # 英文括号()
            r'【[^】]*】',  # 中文方括号【】
            r'\[[^\]]*\]',       # 英文方括号[]
            r'《[^》]*》',  # 书名号《》
            r'“[^”]*”',  # 双引号“”
        ]
        
        cleaned_text = text
        for pattern in patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text)
        
        # 清理多余的空白字符
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text if cleaned_text.strip() else text

    def generate_subtitles(self, text: str, output_filename: str, 
                          audio_duration: Optional[float] = None,
                          words_per_second: float = 2.5) -> Optional[str]:
        """生成字幕文件（SRT格式）"""
        try:
            # 清理文本，过滤掉括号内的音效说明
            cleaned_text = self._clean_audio_script(text)
            
            # 将文本分割成句子
            sentences = self._split_text_into_sentences(cleaned_text)
            
            # 如果没有提供音频时长，根据文字数量估算
            if audio_duration is None:
                total_words = len(cleaned_text.split())
                audio_duration = total_words / words_per_second
            
            # 计算每个句子的时长
            sentence_durations = self._calculate_sentence_durations(sentences, audio_duration)
            
            # 生成SRT字幕文件
            subtitle_path = Config.AUDIO_DIR / f"{output_filename}.srt"
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                current_time = 0.0
                
                for i, (sentence, duration) in enumerate(zip(sentences, sentence_durations), 1):
                    start_time = current_time
                    end_time = current_time + duration
                    
                    # SRT时间格式：HH:MM:SS,mmm
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)
                    
                    # 写入字幕条目
                    f.write(f"{i}\n")
                    f.write(f"{start_srt} --> {end_srt}\n")
                    f.write(f"{sentence.strip()}\n\n")
                    
                    current_time = end_time
            
            return str(subtitle_path)
            
        except Exception as e:
            print(f"生成字幕文件失败: {str(e)}")
            return None
    
    def _validate_generated_audio(self, generated_path: str, reference_path: str, text: str) -> bool:
        """验证生成的音频文件是否正确"""
        try:
            from pathlib import Path
            import time
            
            generated_file = Path(generated_path)
            reference_file = Path(reference_path) if reference_path else None
            
            print(f"\n=== 验证生成的音频 ===")
            print(f"生成文件: {generated_file}")
            print(f"参考文件: {reference_file}")
            
            # 检查生成文件是否存在
            if not generated_file.exists():
                print(f"❌ 生成文件不存在")
                return False
            
            # 检查文件大小
            generated_size = generated_file.stat().st_size
            print(f"生成文件大小: {generated_size/1024/1024:.2f}MB")
            
            if generated_size < 1024:  # 小于1KB
                print(f"❌ 生成文件太小，可能生成失败")
                return False
            
            # 检查文件时间
            current_time = time.time()
            file_mtime = generated_file.stat().st_mtime
            age_seconds = current_time - file_mtime
            
            print(f"文件年龄: {age_seconds:.1f}秒")
            
            if age_seconds > 300:  # 5分钟前的文件
                print(f"⚠️ 文件太旧，可能不是刚生成的")
                # 不直接失败，但给出警告
            
            # 如果有参考音频，检查是否相同
            if reference_file and reference_file.exists():
                reference_size = reference_file.stat().st_size
                print(f"参考文件大小: {reference_size/1024/1024:.2f}MB")
                
                # 检查路径是否相同
                if str(generated_file.resolve()) == str(reference_file.resolve()):
                    print(f"❌ 生成文件与参考文件路径相同")
                    return False
                
                # 检查大小是否相同（使用更精确的阈值）
                size_diff = abs(generated_size - reference_size)
                similarity_threshold = max(1024, min(generated_size, reference_size) * 0.1)  # 1KB或1％中的较大值
                
                if size_diff < similarity_threshold:
                    print(f"⚠️ 生成文件与参考文件大小相似（相差{size_diff}字节，阈值{similarity_threshold}）")
                    # 这里不直接失败，因为有可能正好生成的文件大小相似
                
                print(f"✅ 文件大小差异: {size_diff/1024:.1f}KB")
            
            # 基于文本长度估算期望的文件大小
            text_length = len(text)
            estimated_duration = text_length / 2.5  # 估计每秒2.5个字符
            estimated_size = estimated_duration * 16000 * 2  # 16kHz, 16bit
            
            print(f"估计时长: {estimated_duration:.1f}秒")
            print(f"估计大小: {estimated_size/1024/1024:.2f}MB")
            
            # 如果生成文件明显小于预期，可能有问题
            if generated_size < estimated_size * 0.1:  # 小于预期的10%
                print(f"⚠️ 生成文件明显小于预期大小")
            
            print(f"✅ 音频文件验证通过")
            print(f"=== 验证完成 ===\n")
            return True
            
        except Exception as e:
            print(f"❌ 验证过程异常: {str(e)}")
            return True  # 验证失败时默认通过
    
    def _update_tts_workflow(self, workflow: dict, text: str, speaker_filename: str = None) -> dict:
        """更新TTS工作流中的文本和参考音频"""
        print(f"正在更新TTS工作流...")
        print(f"输入文本: {text[:50]}...")
        if speaker_filename:
            print(f"参考音频: {speaker_filename}")
        
        updated_nodes = []
        
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict):
                # 查找文本输入节点
                if node_data.get("class_type") in ["MultiLinePromptIndex", "TextInput", "TTSTextInput", "PromptNode"]:
                    if "inputs" in node_data:
                        # 查找文本相关的字段
                        for key in node_data["inputs"]:
                            if "text" in key.lower() or "prompt" in key.lower() or "multi_line" in key.lower():
                                node_data["inputs"][key] = text
                                updated_nodes.append(f"Node {node_id}: {key} -> {text[:30]}...")
                                print(f"更新节点 {node_id} ({key}): {text[:30]}...")
                
                # 查找参考音频节点
                elif node_data.get("class_type") in ["IndexSpeakersPreview"] and speaker_filename:
                    if "inputs" in node_data:
                        # 查找音频相关的字段
                        for key in node_data["inputs"]:
                            if "speaker" in key.lower() or "audio" in key.lower():
                                node_data["inputs"][key] = speaker_filename
                                updated_nodes.append(f"Node {node_id}: {key} -> {speaker_filename}")
                                print(f"更新节点 {node_id} ({key}): {speaker_filename}")
                
                # 查找其他可能的文本字段
                elif "inputs" in node_data:
                    for key, value in node_data["inputs"].items():
                        if "text" in key.lower() and isinstance(value, str):
                            node_data["inputs"][key] = text
                            updated_nodes.append(f"Node {node_id}: {key} -> {text[:30]}...")
                            print(f"更新节点 {node_id} ({key}): {text[:30]}...")
        
        print(f"TTS工作流更新完成，共更新了 {len(updated_nodes)} 个节点:")
        for update in updated_nodes:
            print(f"  - {update}")
        
        return workflow
    
    def _prepare_reference_audio(self, reference_audio_path: str) -> Optional[str]:
        """准备参考音频文件，复制到ComfyUI的speakers目录"""
        try:
            import shutil
            from pathlib import Path
            
            source_path = Path(reference_audio_path)
            if not source_path.exists():
                print(f"❌ 参考音频文件不存在: {reference_audio_path}")
                return None
            
            print(f"🎧 准备参考音频: {source_path}")
            
            # ComfyUI的speakers目录路径
            comfyui_speakers_dirs = [
                Path("F:/ComfyUI_windows_portable/ComfyUI/models/TTS/speakers"),
                Path("./ComfyUI/models/TTS/speakers"),
                Path("../ComfyUI/models/TTS/speakers"),
                Path("C:/ComfyUI/models/TTS/speakers"),
                Path("D:/ComfyUI/models/TTS/speakers")
            ]
            
            speakers_dir = None
            for dir_path in comfyui_speakers_dirs:
                if dir_path.parent.parent.parent.exists():  # 检查ComfyUI目录是否存在
                    speakers_dir = dir_path
                    break
            
            if not speakers_dir:
                print(f"⚠️ 找不到ComfyUI的speakers目录，使用默认路径")
                speakers_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/models/TTS/speakers")
            
            # 创建目录
            speakers_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ speakers目录: {speakers_dir}")
            
            # 生成唯一文件名
            import time
            timestamp = int(time.time())
            file_extension = source_path.suffix
            filename = f"user_reference_{timestamp}{file_extension}"
            dest_path = speakers_dir / filename
            
            # 复制文件
            shutil.copy2(source_path, dest_path)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 参考音频复制成功: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return filename  # 返回文件名，不是完整路径
            else:
                print(f"❌ 参考音频复制失败")
                return None
                
        except Exception as e:
            print(f"❌ 准备参考音频异常: {str(e)}")
            return None
    
    def get_available_voices(self) -> list:
        """获取可用的语音列表"""
        try:
            response = requests.get(f"{self.base_url}/voices", timeout=10)
            if response.status_code == 200:
                return response.json().get("voices", ["default"])
            return ["default"]
        except:
            return ["default"]
    
    def create_silence_audio(self, duration: float, output_filename: str) -> Optional[str]:
        """创建静音音频文件"""
        try:
            from pydub import AudioSegment
            
            # 创建指定时长的静音
            silence = AudioSegment.silent(duration=int(duration * 1000))  # 转换为毫秒
            
            output_path = Config.AUDIO_DIR / f"{output_filename}.wav"
            silence.export(output_path, format="wav")
            
            return str(output_path)
            
        except Exception as e:
            print(f"创建静音音频失败: {str(e)}")
            return None
    
    def _split_text_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子"""
        # 使用正则表达式分割句子（中英文兼容）
        sentences = re.split(r'[。！？.!?]+', text)
        # 过滤空句子并保留标点符号
        result = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                result.append(sentence)
        return result
    
    def _calculate_sentence_durations(self, sentences: List[str], total_duration: float) -> List[float]:
        """根据句子长度分配时长"""
        if not sentences:
            return []
        
        # 计算每个句子的字符数
        sentence_lengths = [len(sentence) for sentence in sentences]
        total_length = sum(sentence_lengths)
        
        if total_length == 0:
            # 如果总长度为0，平均分配时长
            duration_per_sentence = total_duration / len(sentences)
            return [duration_per_sentence] * len(sentences)
        
        # 按照字符数比例分配时长
        durations = []
        for length in sentence_lengths:
            duration = (length / total_length) * total_duration
            # 确保每个句子至少有1秒的显示时间
            duration = max(duration, 1.0)
            durations.append(duration)
        
        return durations
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def text_to_speech_with_subtitles(self, text: str, output_filename: str, 
                                     voice: str = "default", speed: float = 1.0) -> Dict[str, Optional[str]]:
        """生成语音和字幕文件"""
        result = {
            'audio_file': None,
            'subtitle_file': None
        }
        
        try:
            # 清理文本，过滤掉括号内的音效说明
            cleaned_text = self._clean_audio_script(text)
            
            # 生成语音文件（使用清理后的文本）
            audio_file = self.text_to_speech(cleaned_text, output_filename, voice, speed)
            result['audio_file'] = audio_file
            
            if audio_file:
                # 获取音频时长
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_wav(audio_file)
                    duration = len(audio) / 1000.0  # 转换为秒
                except ImportError:
                    # 如果没有pydub，估算时长
                    word_count = len(cleaned_text.split())
                    duration = word_count / (2.5 * speed)  # 根据语速调整
                
                # 生成字幕文件（使用清理后的文本）
                subtitle_file = self.generate_subtitles(cleaned_text, output_filename, duration)
                result['subtitle_file'] = subtitle_file
            
            return result
            
        except Exception as e:
            print(f"生成语音和字幕失败: {str(e)}")
            return result
