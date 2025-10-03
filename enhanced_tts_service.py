import requests
import json
from pathlib import Path
from typing import Optional, List, Dict
from config import Config
import re
import time

class EnhancedTTSService:
    def __init__(self):
        self.host = Config.TTS_HOST
        self.port = Config.TTS_PORT
        self.base_url = f"http://{self.host}:{self.port}"
    
    def text_to_speech_with_precise_timestamps(self, text: str, output_filename: str, 
                                             reference_audio: str = None) -> Dict[str, Optional[str]]:
        """
        使用ComfyUI的TTS工作流生成语音和精确时间戳的字幕
        """
        result = {
            'audio_file': None,
            'subtitle_file': None,
            'timestamps': []  # 精确的时间戳信息
        }
        
        try:
            from .comfyui_service import ComfyUIService
            
            comfyui = ComfyUIService()
            
            print(f"\n=== Enhanced ComfyUI TTS 生成开始 ===")
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
                    return result
                else:
                    print(f"✅ 参考音频已准备: {speaker_filename}")
            else:
                print(f"⚠️ 未提供参考音频")
                return result
            
            # 加载TTS工作流
            workflow = comfyui.load_workflow(Config.TTS_WORKFLOW)
            
            # 更新工作流中的文本和参考音频
            workflow = self._update_tts_workflow(workflow, cleaned_text, speaker_filename)
            
            # 执行工作流并获取精确时间戳
            audio_result = self._execute_tts_workflow_with_timestamps(comfyui, workflow, output_filename)
            
            if audio_result and audio_result.get('audio_file'):
                result['audio_file'] = audio_result['audio_file']
                result['timestamps'] = audio_result.get('timestamps', [])
                
                # 生成基于精确时间戳的字幕文件
                if result['timestamps']:
                    subtitle_file = self._generate_subtitles_from_timestamps(
                        result['timestamps'], output_filename)
                    result['subtitle_file'] = subtitle_file
                    print(f"✅ 基于精确时间戳生成字幕文件: {subtitle_file}")
                else:
                    # 如果没有时间戳信息，回退到基于音频时长的估算
                    print(f"⚠️ 未获取到精确时间戳，使用音频时长估算...")
                    try:
                        from pydub import AudioSegment
                        audio = AudioSegment.from_wav(result['audio_file'])
                        duration = len(audio) / 1000.0  # 转换为秒
                        subtitle_file = self._generate_subtitles_from_duration(
                            cleaned_text, output_filename, duration)
                        result['subtitle_file'] = subtitle_file
                    except Exception as e:
                        print(f"⚠️ 生成估算字幕失败: {str(e)}")
            
            print(f"=== Enhanced ComfyUI TTS 生成完成 ===\n")
            return result
            
        except Exception as e:
            print(f"❌ Enhanced ComfyUI TTS转换失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return result
    
    def _execute_tts_workflow_with_timestamps(self, comfyui_service, workflow: dict, 
                                            output_filename: str) -> Optional[Dict]:
        """
        执行TTS工作流并尝试获取精确时间戳
        """
        try:
            # 队列提示
            prompt_id = comfyui_service._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成并获取输出信息
            outputs = comfyui_service._wait_for_completion(prompt_id)
            
            if outputs:
                # 保存音频文件
                audio_file = comfyui_service._save_output(outputs, f"audio_{output_filename}")
                
                if audio_file:
                    # 尝试从IndexTTS2Run节点获取时间戳信息
                    timestamps = self._extract_timestamps_from_outputs(outputs)
                    return {
                        'audio_file': audio_file,
                        'timestamps': timestamps
                    }
            
            return None
            
        except Exception as e:
            print(f"执行TTS工作流获取时间戳失败: {str(e)}")
            return None
    
    def _extract_timestamps_from_outputs(self, outputs: Dict) -> List[Dict]:
        """
        从TTS工作流输出中提取时间戳信息
        """
        timestamps = []
        
        try:
            # 查找IndexTTS2Run节点的输出
            for node_id, node_output in outputs.items():
                if "class_type" in node_output and node_output["class_type"] == "IndexTTS2Run":
                    # 检查是否有时间戳相关信息
                    if "timestamps" in node_output:
                        timestamps_data = node_output["timestamps"]
                        # 解析时间戳数据
                        if isinstance(timestamps_data, list):
                            timestamps = timestamps_data
                        elif isinstance(timestamps_data, dict):
                            # 如果是字典格式，转换为列表
                            for key, value in timestamps_data.items():
                                if isinstance(value, dict) and "start" in value and "end" in value:
                                    timestamps.append({
                                        "text": key,
                                        "start": value["start"],
                                        "end": value["end"]
                                    })
                    # 检查是否有其他可能包含时间戳信息的字段
                    elif "metadata" in node_output:
                        metadata = node_output["metadata"]
                        if isinstance(metadata, dict) and "sentence_timings" in metadata:
                            sentence_timings = metadata["sentence_timings"]
                            if isinstance(sentence_timings, list):
                                timestamps = sentence_timings
                    
            # 如果没有找到时间戳，尝试从音频文件分析
            if not timestamps:
                print("⚠️ 未从TTS节点获取到时间戳，尝试从音频分析...")
                # 这里可以添加语音识别来获取时间戳，但暂时跳过以避免依赖
                
        except Exception as e:
            print(f"提取时间戳信息失败: {str(e)}")
        
        return timestamps
    
    def _generate_subtitles_from_timestamps(self, timestamps: List[Dict], 
                                          output_filename: str) -> Optional[str]:
        """
        基于精确时间戳生成SRT字幕文件
        """
        try:
            if not timestamps:
                return None
            
            subtitle_path = Config.AUDIO_DIR / f"{output_filename}.srt"
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                for i, timestamp in enumerate(timestamps, 1):
                    text = timestamp.get('text', '')
                    # 清理字幕文本，移除括号内的音效说明，保持与音频一致
                    cleaned_text = self._clean_audio_script(text)
                    start_time = timestamp.get('start', 0.0)
                    end_time = timestamp.get('end', start_time + 1.0)
                    
                    # SRT时间格式：HH:MM:SS,mmm
                    start_srt = self._seconds_to_srt_time(start_time)
                    end_srt = self._seconds_to_srt_time(end_time)
                    
                    # 写入字幕条目
                    f.write(f"{i}\n")
                    f.write(f"{start_srt} --> {end_srt}\n")
                    f.write(f"{cleaned_text.strip()}\n\n")
            
            return str(subtitle_path)
            
        except Exception as e:
            print(f"基于时间戳生成字幕失败: {str(e)}")
            return None
    
    def _generate_subtitles_from_duration(self, text: str, output_filename: str, 
                                        audio_duration: float) -> Optional[str]:
        """
        基于音频时长估算生成字幕文件（回退方案）
        """
        try:
            # 清理文本，过滤掉括号内的音效说明
            cleaned_text = self._clean_audio_script(text)
            
            # 将文本分割成句子
            sentences = self._split_text_into_sentences(cleaned_text)
            
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
            print(f"基于时长估算生成字幕失败: {str(e)}")
            return None
    
    def _clean_audio_script(self, text: str) -> str:
        """清理音频脚本，过滤掉括号内的音效说明"""
        import re
        
        print(f"\n=== 清理音频脚本 ===")
        print(f"原始文本: {text}")
        
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
        removed_parts = []
        
        for pattern in patterns:
            matches = re.findall(pattern, cleaned_text)
            if matches:
                removed_parts.extend(matches)
                cleaned_text = re.sub(pattern, '', cleaned_text)
        
        # 清理多余的空白字符
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        print(f"移除的内容: {removed_parts}")
        print(f"清理后文本: {cleaned_text}")
        print(f"=== 清理完成 ===\n")
        
        return cleaned_text if cleaned_text.strip() else text
    
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
                if dir_path.parent.parent.parent.exists():
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
                return filename
            else:
                print(f"❌ 参考音频复制失败")
                return None
                
        except Exception as e:
            print(f"❌ 准备参考音频异常: {str(e)}")
            return None
    
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