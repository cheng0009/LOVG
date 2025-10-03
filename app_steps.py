import streamlit as st
import json
import time
import os
from pathlib import Path
from config import Config
from typing import List, Dict


def render_step_4_video_generation(services, status):
    """步骤4: 视频生成"""
    st.markdown('<h2 class="step-header">步骤4: 视频生成</h2>', unsafe_allow_html=True)
    
    # 检查必要数据
    if 'storyboard_images' not in st.session_state.results:
        st.error("未找到分镜图！")
        return
    
    images = st.session_state.results['storyboard_images']
    prompts = st.session_state.results.get('video_prompts_list', [])
    
    if not images:
        st.error("没有分镜图！")
        return
    
    # 视频参数设置
    with st.expander("🔧 视频参数设置", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            duration = st.slider("每段时长(秒)", 3, 15, 5)
            fps = st.selectbox("帧率", [12, 18, 24, 30], index=1)
        with col2:
            quality = st.selectbox("质量", ["低", "中", "高"], index=1)
            seed = st.number_input("随机种子", value=42, min_value=0, max_value=999999)
        with col3:
            motion_intensity = st.slider("运动强度", 1, 10, 5)
            camera_movement = st.selectbox("镜头运动", ["固定", "轻微", "中等", "强烈"])
    
    video_params = {
        'duration': duration,
        'fps': fps,
        'quality': quality,
        'seed': seed,
        'motion_intensity': motion_intensity,
        'camera_movement': camera_movement
    }
    
    # 显示视频参数
    with st.expander("📊 当前视频参数", expanded=False):
        st.json(video_params)
    
    # 为每个分镜图生成视频
    st.subheader("🎥 视频片段生成")
    
    # 获取当前视频片段状态
    if 'video_clips' not in st.session_state.results:
        st.session_state.results['video_clips'] = [None] * len(images)
    
    videos = st.session_state.results['video_clips']
    
    # 显示每个分镜图和对应的视频控件
    for i in range(len(images)):
        if i < len(images) and images[i] and Path(images[i]).exists():
            st.markdown(f"### 分镜图 {i+1}")
            
            # 显示分镜图和视频提示词
            col1, col2 = st.columns(2)
            with col1:
                st.image(images[i], caption=f"分镜图 {i+1}", use_column_width=True)
            with col2:
                # 如果没有视频提示词，使用默认提示词
                if i >= len(prompts):
                    default_prompt = f"根据图片内容生成动态视频，包含适当的运动效果和镜头移动"
                else:
                    default_prompt = prompts[i] if prompts[i] else f"根据图片内容生成动态视频，包含适当的运动效果和镜头移动"
                
                video_prompt = st.text_area(
                    f"视频提示词 {i+1}",
                    value=default_prompt,
                    key=f"inline_video_prompt_{i}",
                    height=80,
                    help="描述这个场景中的动作、运动效果、镜头移动等"
                )
                
                # 视频生成按钮
                if i < len(videos) and videos[i] and Path(videos[i]).exists():
                    # 已有视频，显示重新生成按钮
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button(f"🔄 重新生成视频", key=f"regen_video_{i}", use_container_width=True):
                            with st.spinner(f"重新生成视频片段 {i+1}..."):
                                try:
                                    # 删除当前视频文件
                                    old_video_path = videos[i]
                                    if old_video_path and Path(old_video_path).exists():
                                        try:
                                            Path(old_video_path).unlink()
                                            print(f"🗑️ 删除旧视频: {old_video_path}")
                                        except:
                                            pass
                                    
                                    # 清理相关缓存文件
                                    try:
                                        from config import Config
                                        import time
                                        current_time = time.time()
                                        video_clips_dir = Config.VIDEO_CLIPS_DIR
                                        if video_clips_dir.exists():
                                            for old_file in video_clips_dir.glob(f"*_{i+1:03d}_*.mp4"):
                                                try:
                                                    old_file.unlink()
                                                    print(f"🗑️ 清理片段{i+1}缓存: {old_file}")
                                                except:
                                                    pass
                                    except Exception as e:
                                        print(f"清理缓存异常: {e}")
                                    
                                    video_prompt = st.session_state.results['video_prompts_list'][i]
                                    video_params = st.session_state.results.get('video_params', {})
                                    new_videos = services['comfyui'].generate_videos([images[i]], [video_prompt], video_params)
                                    if new_videos and new_videos[0]:
                                        # 验证新生成的文件
                                        video_path = new_videos[0]
                                        if Path(video_path).exists():
                                            file_mtime = Path(video_path).stat().st_mtime
                                            current_time = time.time()
                                            
                                            if current_time - file_mtime < 600:  # 10分钟内生成
                                                st.session_state.results['video_clips'][i] = video_path
                                                st.success(f"视频片段 {i+1} 重新生成成功！")
                                                st.rerun()
                                            else:
                                                st.error(f"重新生成的视频太旧，可能是缓存问题")
                                        else:
                                            st.error(f"重新生成的视频文件不存在")
                                    else:
                                        st.error(f"重新生成失败")
                                except Exception as e:
                                    st.error(f"重新生成失败: {str(e)}")
                    with btn_col2:
                        if st.button(f"❌ 删除视频", key=f"delete_video_{i}", use_container_width=True):
                            st.session_state.results['video_clips'][i] = None
                            st.rerun()
                else:
                    # 没有视频，显示生成按钮
                    if st.button(f"▶️ 生成视频片段 {i+1}", key=f"gen_single_video_{i}", use_container_width=True, type="primary"):
                        with st.spinner(f"生成视频片段 {i+1}..."):
                            try:
                                # 清理可能存在的旧缓存
                                try:
                                    from config import Config
                                    import time
                                    current_time = time.time()
                                    video_clips_dir = Config.VIDEO_CLIPS_DIR
                                    if video_clips_dir.exists():
                                        for old_file in video_clips_dir.glob(f"*_{i+1:03d}_*.mp4"):
                                            if current_time - old_file.stat().st_mtime > 60:  # 1分钟前的文件
                                                try:
                                                    old_file.unlink()
                                                    print(f"🗑️ 清理片段{i+1}的旧文件: {old_file}")
                                                except:
                                                    pass
                                except Exception as e:
                                    print(f"清理单个片段缓存异常: {e}")
                                
                                video_prompt = st.session_state.results['video_prompts_list'][i]
                                video_params = st.session_state.results.get('video_params', {})
                                new_videos = services['comfyui'].generate_videos([images[i]], [video_prompt], video_params)
                                if new_videos and new_videos[0]:
                                    # 确保video_clips列表足够长
                                    if 'video_clips' not in st.session_state.results:
                                        st.session_state.results['video_clips'] = [None] * len(images)
                                    elif len(st.session_state.results['video_clips']) <= i:
                                        st.session_state.results['video_clips'].extend([None] * (i + 1 - len(st.session_state.results['video_clips'])))
                                    
                                    # 验证生成的视频文件
                                    video_path = new_videos[0]
                                    if Path(video_path).exists():
                                        file_mtime = Path(video_path).stat().st_mtime
                                        current_time = time.time()
                                        
                                        # 确保是刚生成的文件（10分钟内）
                                        if current_time - file_mtime < 600:
                                            st.session_state.results['video_clips'][i] = video_path
                                            st.success(f"视频片段 {i+1} 生成成功！")
                                            st.rerun()
                                        else:
                                            st.error(f"生成的视频文件太旧，可能是历史缓存，请重试")
                                    else:
                                        st.error(f"视频文件不存在: {video_path}")
                                else:
                                    st.error(f"视频生成失败，请检查ComfyUI服务")
                            except Exception as e:
                                st.error(f"生成失败: {str(e)}")
                
                st.markdown("---")
                
                # 视频预览区域
                st.markdown("**🎬 视频预览**")
                if i < len(videos) and videos[i] and Path(videos[i]).exists():
                    video_path = Path(videos[i])
                    file_size = video_path.stat().st_size
                    file_mtime = video_path.stat().st_mtime
                    
                    # 显示文件信息和时间戳
                    import time
                    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_mtime))
                    st.caption(f"文件: {video_path.name} ({file_size/1024/1024:.2f} MB)")
                    st.caption(f"生成时间: {time_str}")
                    
                    # 检查文件是否为最近生成（10分钟内）
                    current_time = time.time()
                    is_recent = (current_time - file_mtime) < 600
                    
                    if not is_recent:
                        st.warning(f"⚠️ 此文件生成于 {(current_time - file_mtime)/60:.1f} 分钟前，可能是历史缓存")
                        if st.button(f"🔄 刷新片段 {i+1}", key=f"refresh_video_{i}"):
                            # 删除可能的缓存文件并重新生成
                            try:
                                video_path.unlink()
                                st.session_state.results['video_clips'][i] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"删除缓存失败: {e}")
                    
                    # 使用CSS类控制视频尺寸
                    st.markdown('<div class="media-container">', unsafe_allow_html=True)
                    # Streamlit版本兼容性处理：尝试传递key参数，如果不支持则使用默认方式
                    video_key = f"video_{i}_{int(file_mtime * 1000)}"
                    try:
                        # 尝试使用key参数（新版本Streamlit可能支持）
                        st.video(videos[i], key=video_key)
                    except TypeError:
                        # 如果不支持key参数，则直接使用视频路径
                        st.video(videos[i])
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 显示文件状态
                    if file_size < 1024:  # 小于1KB可能有问题
                        st.error("❌ 视频文件太小，可能生成失败")
                    elif is_recent:
                        st.success(f"✅ 视频文件正常且为最新生成 ({file_size/1024/1024:.2f} MB)")
                    else:
                        st.info(f"ℹ️ 视频文件存在但较旧 ({file_size/1024/1024:.2f} MB)")
                elif i < len(videos) and videos[i]:
                    # 文件路径存在但文件不存在
                    st.error(f"❌ 视频文件不存在: {videos[i]}")
                    if st.button(f"🔄 重新生成片段 {i+1}", key=f"regen_missing_{i}"):
                        st.session_state.results['video_clips'][i] = None
                        st.rerun()
                else:
                    st.info("视频未生成")
            
            st.markdown("---")  # 分隔线
        
        # 检查是否所有视频都已生成
        valid_videos = [v for v in videos if v and Path(v).exists()]
        if len(valid_videos) == len(images):
            st.success("✅ 所有视频片段已生成完成！")
            if st.button("🎵 确认视频片段，继续音频合成", type="primary", use_container_width=True):
                st.session_state.step = 5
                st.rerun()
        else:
            st.warning(f"⚠️ 还有 {len(images) - len(valid_videos)} 个视频片段未生成")
        
        # 调试信息面板
        with st.expander("🔍 调试信息", expanded=False):
            st.markdown("**视频生成状态检查**")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("总数", len(images))
                st.metric("成功", len(valid_videos))
            with col2:
                st.metric("失败", len(images) - len(valid_videos))
                st.metric("成功率", f"{len(valid_videos)/len(images)*100:.1f}%" if images else "0%")
            
            # 显示每个视频的详细状态
            st.markdown("**各视频片段状态**")
            for i, video_path in enumerate(videos):
                if video_path and Path(video_path).exists():
                    file_size = Path(video_path).stat().st_size / (1024*1024)
                    st.write(f"✅ 片段 {i+1}: {Path(video_path).name} ({file_size:.2f} MB)")
                elif video_path:
                    st.write(f"❌ 片段 {i+1}: 文件不存在 - {video_path}")
                else:
                    st.write(f"⚪ 片段 {i+1}: 未生成")


def render_step_5_audio_generation(services, status):
    """步骤5: 音频生成"""
    st.markdown('<h2 class="step-header">步骤5: 音频生成</h2>', unsafe_allow_html=True)
    
    # 检查音频脚本
    if 'scripts' not in st.session_state.results:
        st.error("未找到音频脚本！")
        return
    
    audio_script = st.session_state.results['scripts'].get('audio_script', '')
    
    # 显示音频脚本
    st.subheader("🎙️ 配音脚本")
    audio_text = st.text_area(
        "配音内容",
        value=audio_script,
        height=200,
        help="可以编辑配音内容"
    )
    
    # TTS设置
    with st.expander("🔧 TTS设置", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            voice_type = st.selectbox("语音类型", ["默认", "男声", "女声", "童声"])
            speech_speed = st.slider("语速", 0.5, 2.0, 1.0, 0.1)
        with col2:
            audio_format = st.selectbox("音频格式", ["wav", "mp3"])
            volume = st.slider("音量", 0.1, 2.0, 1.0, 0.1)
    
    # 参考音频上传（默认必须上传）
    with st.expander("🎤 参考音频上传（必须上传）", expanded=True):
        st.markdown("""**重要提示**: 系统现在默认使用增强版TTS服务，必须上传参考音频文件来克隆声音特征。
        请上传一个清晰的语音文件作为声音参考。""")
        
        uploaded_audio = st.file_uploader(
            "选择参考音频文件（必须上传）",
            type=['wav', 'mp3', 'flac', 'ogg'],
            help="支持 WAV, MP3, FLAC, OGG 格式的音频文件"
        )
        
        if uploaded_audio:
            st.success(f"✅ 已选择参考音频: {uploaded_audio.name}")
            
            # 播放上传的音频预览
            st.audio(uploaded_audio, format=uploaded_audio.type)
            
            # 保存上传的音频文件
            try:
                import time
                timestamp = int(time.time())
                reference_filename = f"reference_audio_{timestamp}.wav"
                reference_path = Config.AUDIO_DIR / "references" / reference_filename
                reference_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(reference_path, "wb") as f:
                    f.write(uploaded_audio.getbuffer())
                
                st.session_state.results['reference_audio'] = str(reference_path)
                st.info(f"参考音频已保存: {reference_filename}")
                
            except Exception as e:
                st.error(f"保存参考音频失败: {str(e)}")
        else:
            if 'reference_audio' not in st.session_state.results:
                st.error("❌ 必须上传参考音频文件！系统默认使用增强版TTS服务，需要参考音频来生成高质量配音。")
    
    # 生成音频
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎵 生成配音", type="primary"):
            if audio_text.strip():
                # 检查是否有参考音频（现在是必须的）
                if 'reference_audio' not in st.session_state.results:
                    st.error("❌ 必须上传参考音频文件！系统默认使用增强版TTS服务，需要参考音频来生成高质量配音。")
                else:
                    with st.spinner("正在生成配音（使用增强版TTS服务）..."):
                        try:
                            # 使用增强版TTS服务生成配音和精确时间戳字幕
                            reference_audio = st.session_state.results.get('reference_audio')
                            result = services['tts'].text_to_speech_with_precise_timestamps(
                                audio_text, 
                                "narration",
                                reference_audio=reference_audio
                            )
                            
                            audio_path = result.get('audio_file')
                            subtitle_path = result.get('subtitle_file')
                            
                            if audio_path:
                                # 验证生成的文件确实不同于参考音频
                                reference_audio_path = st.session_state.results.get('reference_audio')
                                if reference_audio_path and Path(reference_audio_path).exists():
                                    try:
                                        new_size = Path(audio_path).stat().st_size
                                        ref_size = Path(reference_audio_path).stat().st_size
                                        
                                        if abs(new_size - ref_size) < max(1024, min(new_size, ref_size) * 0.1):  # 更精确的对比
                                            st.error("❌ 生成的文件与参考音频相似，TTS可能未正常工作")
                                            st.warning("请检查ComfyUI TTS工作流配置")
                                        else:
                                            st.session_state.results['audio_file'] = audio_path
                                            # 保存字幕文件路径
                                            if subtitle_path:
                                                st.session_state.results['subtitle_file'] = subtitle_path
                                            st.success("✅ 配音生成成功！（使用增强版TTS服务）")
                                            st.rerun()
                                    except Exception as e:
                                        st.warning(f"文件验证异常: {e}")
                                        st.session_state.results['audio_file'] = audio_path
                                        # 保存字幕文件路径
                                        if subtitle_path:
                                            st.session_state.results['subtitle_file'] = subtitle_path
                                        st.success("配音生成成功！（使用增强版TTS服务）")
                                        st.rerun()
                                else:
                                    st.session_state.results['audio_file'] = audio_path
                                    # 保存字幕文件路径
                                    if subtitle_path:
                                        st.session_state.results['subtitle_file'] = subtitle_path
                                    st.success("配音生成成功！（使用增强版TTS服务）")
                                    st.rerun()
                            else:
                                st.error("❌ 配音生成失败，请检查增强版TTS服务")
                        except Exception as e:
                            st.error(f"生成失败: {str(e)}")
            else:
                st.warning("请输入配音内容")

    # 显示生成的音频
    if 'audio_file' in st.session_state.results:
        audio_path = st.session_state.results['audio_file']
        if Path(audio_path).exists():
            st.subheader("🎧 生成的配音")
            
            # 验证这不是参考音频文件
            is_reference_audio = False
            reference_audio_path = st.session_state.results.get('reference_audio')
            
            if reference_audio_path and Path(reference_audio_path).exists():
                # 检查文件路径和大小，确保这不是参考音频
                try:
                    audio_size = Path(audio_path).stat().st_size
                    ref_size = Path(reference_audio_path).stat().st_size
                    
                    # 如果文件路径相同或大小非常相似，可能是参考音频
                    if (audio_path == reference_audio_path or 
                        (abs(audio_size - ref_size) < max(1024, min(audio_size, ref_size) * 0.1))):  # 1KB或文件大小10%误差
                        is_reference_audio = True
                        st.error("❌ 检测到当前显示的是参考音频，而不是生成的配音！")
                        st.warning("请重新生成配音或检查TTS服务状态。")
                    else:
                        # 显示文件信息以便用户验证
                        import time
                        audio_mtime = Path(audio_path).stat().st_mtime
                        time_str = time.strftime('%H:%M:%S', time.localtime(audio_mtime))
                        
                        st.success(f"✅ 配音文件: {Path(audio_path).name}")
                        st.caption(f"生成时间: {time_str} | 文件大小: {audio_size/1024/1024:.2f}MB")
                        
                        # 对比显示
                        with st.expander("📊 文件对比信息", expanded=False):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write("**🎵 生成的配音**")
                                st.write(f"文件: {Path(audio_path).name}")
                                st.write(f"大小: {audio_size/1024/1024:.2f}MB")
                                st.write(f"路径: {audio_path}")
                            with col2:
                                st.write("**🎤 参考音频**")
                                st.write(f"文件: {Path(reference_audio_path).name}")
                                st.write(f"大小: {ref_size/1024/1024:.2f}MB")
                                st.write(f"路径: {reference_audio_path}")
                except Exception as e:
                    st.warning(f"文件验证失败: {e}")
            else:
                # 没有参考音频或参考音频不存在
                st.success(f"✅ 配音文件: {Path(audio_path).name}")
            
            # 只有在确认不是参考音频时才播放
            if not is_reference_audio:
                st.audio(audio_path)
            else:
                st.info("🔄 请重新生成配音以获取正确的配音文件")
            
            # 音频控制
            if st.button("🔄 重新生成配音"):
                # 检查是否有参考音频
                if 'reference_audio' not in st.session_state.results:
                    st.error("❌ 必须上传参考音频文件！系统默认使用增强版TTS服务，需要参考音频来生成高质量配音。")
                else:
                    with st.spinner("重新生成配音（使用增强版TTS服务）..."):
                        try:
                            # 生成唯一的输出文件名，避免覆盖问题
                            import time
                            timestamp = int(time.time())
                            unique_filename = f"narration_regen_{timestamp}"
                            
                            reference_audio = st.session_state.results.get('reference_audio')
                            result = services['tts'].text_to_speech_with_precise_timestamps(
                                audio_text, 
                                unique_filename,
                                reference_audio=reference_audio
                            )
                            
                            audio_path = result.get('audio_file')
                            subtitle_path = result.get('subtitle_file')
                            
                            if audio_path:
                                # 验证新生成的文件确实不同于参考音频
                                if reference_audio_path and Path(reference_audio_path).exists():
                                    try:
                                        new_size = Path(audio_path).stat().st_size
                                        ref_size = Path(reference_audio_path).stat().st_size
                                        
                                        if abs(new_size - ref_size) < max(1024, min(new_size, ref_size) * 0.1):  # 更精确的对比
                                            st.error("❌ 重新生成的文件与参考音频相似，TTS可能未正常工作")
                                            st.warning("请检查ComfyUI TTS工作流配置或参考音频设置")
                                        else:
                                            st.session_state.results['audio_file'] = audio_path
                                            # 保存字幕文件路径
                                            if subtitle_path:
                                                st.session_state.results['subtitle_file'] = subtitle_path
                                            st.success("✅ 配音重新生成成功！（使用增强版TTS服务）")
                                            st.rerun()
                                    except Exception as e:
                                        st.warning(f"文件验证异常: {e}")
                                        st.session_state.results['audio_file'] = audio_path
                                        # 保存字幕文件路径
                                        if subtitle_path:
                                            st.session_state.results['subtitle_file'] = subtitle_path
                                        st.success("配音重新生成成功！（使用增强版TTS服务）")
                                        st.rerun()
                                else:
                                    st.session_state.results['audio_file'] = audio_path
                                    # 保存字幕文件路径
                                    if subtitle_path:
                                        st.session_state.results['subtitle_file'] = subtitle_path
                                    st.success("配音重新生成成功！（使用增强版TTS服务）")
                                    st.rerun()
                            else:
                                st.error("重新生成失败，请检查TTS服务")
                        except Exception as e:
                            st.error(f"重新生成失败: {str(e)}")
        else:
            st.error(f"音频文件不存在: {audio_path}")




def render_step_6_final_composition(services, status):
    """步骤6: 最终合成"""
    st.markdown('<h2 class="step-header">步骤6: 视频合成</h2>', unsafe_allow_html=True)
    
    # 检查必要数据
    if 'video_clips' not in st.session_state.results:
        st.error("未找到视频片段！")
        return
    
    video_clips = st.session_state.results['video_clips']
    valid_videos = [v for v in video_clips if v and Path(v).exists()]
    
    if not valid_videos:
        st.error("没有有效的视频片段！")
        return
    
    # 合成设置
    st.subheader("⚙️ 合成设置")
    
    col1, col2 = st.columns(2)
    with col1:
        final_video_name = st.text_input("视频文件名", value=f"video_{int(time.time())}")
        add_cover = st.checkbox("添加封面", value=True)
    
    with col2:
        add_subtitles = st.checkbox("添加字幕", value=False)
        
        # 字幕选项
        if add_subtitles:
            # 检查是否有音频文件和配音脚本
            has_audio_script = 'scripts' in st.session_state.results and st.session_state.results['scripts'].get('audio_script')
            
            if has_audio_script:
                subtitle_source = st.radio(
                    "字幕来源",
                    ["自动生成", "手动输入"],
                    help="自动生成将使用配音脚本生成字幕"
                )
                
                if subtitle_source == "手动输入":
                    subtitle_text = st.text_area("字幕内容", height=100)
                else:
                    # 显示将使用的配音脚本作为字幕
                    audio_script = st.session_state.results['scripts']['audio_script']
                    st.text_area("将使用的字幕内容（预览）", value=audio_script, height=100, disabled=True)
                    subtitle_text = audio_script
            else:
                st.warning("⚠️ 未找到配音脚本，请手动输入字幕内容")
                subtitle_text = st.text_area("字幕内容", height=100)
            
            # 字幕样式显示
            current_subtitle_style = st.session_state.results.get('subtitle_style')
            if not current_subtitle_style:
                # 尝试从文件加载
                try:
                    from config import Config
                    import json
                    style_file = Config.BASE_DIR / "subtitle_style.json"
                    if style_file.exists():
                        with open(style_file, 'r', encoding='utf-8') as f:
                            current_subtitle_style = json.load(f)
                        # 将列表转换回元组（对于颜色值）
                        for key in ['text_color', 'outline_color', 'bg_color']:
                            if key in current_subtitle_style and isinstance(current_subtitle_style[key], list):
                                current_subtitle_style[key] = tuple(current_subtitle_style[key])
                    else:
                        current_subtitle_style = Config.SUBTITLE_STYLE['opencv'].copy()
                except:
                    from config import Config
                    current_subtitle_style = Config.SUBTITLE_STYLE['opencv'].copy()
            
            if current_subtitle_style:
                with st.expander("🎨 字幕样式预览", expanded=False):
                    # 检查是否使用了智能预设
                    use_smart_preset = st.session_state.get('use_smart_preset', False)
                    
                    if use_smart_preset and 'video_clips' in st.session_state.results:
                        # 显示智能适配信息
                        st.info("🤖 检测到启用了智能预设，将根据视频尺寸自动优化字幕样式")
                        
                        # 获取第一个视频片段的尺寸信息
                        video_clips = st.session_state.results.get('video_clips', [])
                        if video_clips and video_clips[0] and Path(video_clips[0]).exists():
                            try:
                                from services.video_service import VideoService
                                video_service = VideoService()
                                video_info = video_service.get_video_info(video_clips[0])
                                
                                if video_info:
                                    width = video_info['width']
                                    height = video_info['height']
                                    
                                    # 使用智能服务检测最优样式
                                    from services.smart_subtitle_style_service import SmartSubtitleStyleService
                                    smart_service = SmartSubtitleStyleService()
                                    
                                    # 预览智能样式
                                    preview_result = smart_service.preview_style_for_resolution(width, height)
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.metric("视频分辨率", f"{width}x{height}")
                                        st.metric("检测格式", preview_result['detected_format'])
                                    with col2:
                                        st.metric("宽高比", f"{preview_result['aspect_ratio']}:1")
                                        st.metric("字号大小", preview_result['font_size_preview'])
                                    
                                    # 获取优化后的样式
                                    optimized_style = smart_service.get_smart_subtitle_style(width, height)
                                    if '_detection_info' in optimized_style:
                                        del optimized_style['_detection_info']
                                    
                                    # 更新当前样式
                                    current_subtitle_style = optimized_style
                                    st.session_state.results['subtitle_style'] = optimized_style
                                    
                                    st.success("✅ 已根据视频尺寸自动优化字幕样式")
                                    
                            except Exception as e:
                                st.warning(f"智能适配失败，使用手动设置: {e}")
                        else:
                            st.warning("未找到视频片段，无法进行智能适配")
                    
                    st.markdown("💡 **当前字幕样式设置**（在步骤1中可修改）")
                    
                    # 显示当前样式配置
                    st.json(current_subtitle_style)
            
            # 保存字幕样式
            if st.button("💾 保存字幕样式"):
                try:
                    from config import Config
                    import json
                    style_file = Config.BASE_DIR / "subtitle_style.json"
                    
                    # 将元组转换为列表以便JSON序列化
                    style_to_save = current_subtitle_style.copy()
                    for key in ['text_color', 'outline_color', 'bg_color']:
                        if key in style_to_save and isinstance(style_to_save[key], tuple):
                            style_to_save[key] = list(style_to_save[key])
                    
                    with open(style_file, 'w', encoding='utf-8') as f:
                        json.dump(style_to_save, f, ensure_ascii=False, indent=2)
                    
                    # 保存到session_state
                    st.session_state.results['subtitle_style'] = current_subtitle_style
                    st.success("✅ 字幕样式已保存")
                except Exception as e:
                    st.error(f"保存字幕样式失败: {e}")
    
    # 封面设置
    with st.expander("🖼️ 封面设置", expanded=False):
        cover_title = st.text_input("封面标题", value=st.session_state.results.get('topic', ''))
        cover_template = st.file_uploader("封面模板（可选）", type=['png', 'jpg', 'jpeg'])
    
    # 开始合成
    st.markdown("---")
    if st.button("🎬 开始合成最终视频", type="primary", use_container_width=True):
        with st.spinner("正在合成视频..."):
            try:
                current_video = None
                
                # 1. 合并视频片段
                if len(valid_videos) == 1:
                    # 只有一个视频片段，直接使用
                    current_video = valid_videos[0]
                    print(f"ℹ️ 只有一个视频片段，直接使用: {current_video}")
                else:
                    # 多个视频片段，需要合并
                    print(f"ℹ️ 合并 {len(valid_videos)} 个视频片段")
                    merged_video = services['video'].merge_video_clips(valid_videos, f"{final_video_name}_merged")
                    if merged_video and Path(merged_video).exists():
                        current_video = merged_video
                        print(f"✅ 视频片段合并成功: {merged_video}")
                    else:
                        st.error("❌ 视频片段合并失败")
                        return
                
                # 2. 添加音频
                if 'audio_file' in st.session_state.results:
                    audio_file = st.session_state.results['audio_file']
                    if Path(audio_file).exists():
                        # 计算封面时长（如果添加封面）
                        cover_duration = 3.0 if add_cover else 0.0
                        
                        print(f"🎵 添加音频到视频...")
                        print(f"  音频文件: {audio_file}")
                        print(f"  封面时长: {cover_duration}s")
                        
                        audio_video = services['video'].add_audio(
                            current_video,
                            audio_file,
                            f"{final_video_name}_with_audio",
                            cover_duration=cover_duration  # 传递封面时长
                        )
                        
                        if audio_video and Path(audio_video).exists():
                            current_video = audio_video
                            st.success("✅ 音频添加成功！")
                            print(f"✅ 音频视频生成成功: {audio_video}")
                        else:
                            st.warning("⚠️ 音频添加失败，继续其他步骤")
                            print("❌ 音频视频生成失败")
                    else:
                        st.warning("⚠️ 音频文件不存在，跳过音频添加")
                
                # 3. 添加字幕
                if add_subtitles and subtitle_text:
                    print("🎨 开始添加字幕...")
                    
                    # 获取用户设置的字幕样式（优先级：session_state > 文件 > 默认）
                    subtitle_style = None
                    
                    # 1. 首先尝试从session_state获取
                    if 'subtitle_style' in st.session_state.results:
                        subtitle_style = st.session_state.results['subtitle_style']
                        print(f"✅ 从session_state加载字幕样式: {subtitle_style}")
                    
                    # 2. 如果session_state没有，尝试从文件加载
                    if not subtitle_style:
                        try:
                            from config import Config
                            import json
                            style_file = Config.BASE_DIR / "subtitle_style.json"
                            if style_file.exists():
                                with open(style_file, 'r', encoding='utf-8') as f:
                                    subtitle_style = json.load(f)
                                # 将列表转换回元组（对于颜色值）
                                for key in ['text_color', 'outline_color', 'bg_color']:
                                    if key in subtitle_style and isinstance(subtitle_style[key], list):
                                        subtitle_style[key] = tuple(subtitle_style[key])
                                print(f"✅ 从文件加载字幕样式: {subtitle_style}")
                                # 保存到session_state避免重复加载
                                st.session_state.results['subtitle_style'] = subtitle_style
                            else:
                                print("⚠️ 字幕样式文件不存在，使用默认样式")
                        except Exception as e:
                            print(f"❌ 加载字幕样式文件失败: {e}")
                    
                    # 3. 最后使用默认样式
                    if not subtitle_style:
                        subtitle_style = Config.SUBTITLE_STYLE['opencv'].copy()
                        print("⚠️ 使用默认字幕样式")
                    
                    # 确保样式不为空且包含必要字段
                    if not subtitle_style or not isinstance(subtitle_style, dict):
                        subtitle_style = Config.SUBTITLE_STYLE['opencv'].copy()
                        print("⚠️ 样式无效，强制使用默认样式")
                    
                    try:
                        # 检查是否已经存在精确时间戳的SRT文件（优先使用）
                        precise_subtitle_file = None
                        audio_delay = 0.0  # 音频延迟时间
                        if 'audio_file' in st.session_state.results:
                            # 根据音频文件名查找对应的SRT文件
                            audio_file_path = Path(st.session_state.results['audio_file'])
                            srt_file_path = audio_file_path.with_suffix('.srt')
                            if srt_file_path.exists():
                                precise_subtitle_file = str(srt_file_path)
                                print(f"✅ 找到精确时间戳字幕文件: {precise_subtitle_file}")
                            
                            # 检查是否有封面，如果有则音频需要延迟3秒开始
                            if add_cover:
                                audio_delay = 3.0
                                print(f"ℹ️ 检测到封面，音频将延迟 {audio_delay} 秒开始")
                        
                        if precise_subtitle_file:
                            # 使用精确时间戳的SRT文件
                            print("💬 使用精确时间戳字幕文件...")
                            subtitle_video = services['video'].add_subtitles_from_srt(
                                current_video,
                                precise_subtitle_file,
                                f"{final_video_name}_with_subtitles"
                            )
                        else:
                            # 获取视频时长
                            video_info = services['video'].get_video_info(current_video)
                            video_duration = video_info['duration'] if video_info else 30.0
                            
                            # 创建字幕数据 - 使用正确的文本分割和时间分配
                            if add_subtitles and subtitle_text:
                                # 使用现有的文本分割函数来正确处理字幕
                                subtitles = _generate_subtitles_from_text(subtitle_text)
                                print(f"📝 生成了 {len(subtitles)} 条字幕")
                                
                                # 如果有音频延迟，需要调整字幕时间
                                if audio_delay > 0:
                                    print(f"ℹ️ 调整字幕时间以匹配音频延迟 ({audio_delay} 秒)")
                                    for subtitle in subtitles:
                                        subtitle['start'] += audio_delay
                                
                                for i, sub in enumerate(subtitles):
                                    print(f"  字幕 {i+1}: {sub['text'][:30]}... (开始: {sub['start']:.2f}s, 时长: {sub['duration']:.2f}s)")
                            else:
                                # 如果没有字幕文本，创建一个默认的字幕（保持原有逻辑）
                                subtitles = [
                                    {
                                        'text': subtitle_text,
                                        'start': audio_delay,  # 考虑音频延迟
                                        'duration': video_duration
                                    }
                                ]
                            
                            print(f"📝 字幕内容: {subtitle_text[:50]}...")
                            print(f"⏱️ 视频时长: {video_duration:.2f}秒")
                            print(f"🎨 应用样式: {subtitle_style}")
                            
                            # 添加字幕（样式必定传递）
                            subtitle_video = services['video'].add_subtitles(
                                current_video,
                                subtitles,
                                f"{final_video_name}_with_subtitles",
                                style_config=subtitle_style
                            )
                        
                        if subtitle_video and Path(subtitle_video).exists():
                            current_video = subtitle_video
                            st.success(f"✅ 字幕添加成功！样式：字号{subtitle_style.get('font_scale', '默认')}")
                            print(f"✅ 字幕视频生成成功: {subtitle_video}")
                        else:
                            st.warning("⚠️ 字幕添加失败，继续其他步骤")
                            print("❌ 字幕视频生成失败")
                            
                    except Exception as subtitle_error:
                        print(f"❌ 字幕添加异常: {subtitle_error}")
                        import traceback
                        traceback.print_exc()
                        st.warning("⚠️ 字幕添加失败，继续生成无字幕视频")
                
                # 4. 添加封面
                if add_cover and cover_title:
                    cover_template_path = None
                    if cover_template:
                        # 保存上传的封面模板
                        cover_template_path = f"temp_cover_template.{cover_template.name.split('.')[-1]}"
                        with open(cover_template_path, "wb") as f:
                            f.write(cover_template.getbuffer())
                    
                    current_video = services['video'].create_video_with_cover(
                        current_video,
                        cover_template_path,
                        cover_title,
                        final_video_name
                    )
                
                if current_video:
                    st.session_state.results['final_video'] = current_video
                    st.success("🎉 视频合成完成！")
                    
                    # 显示合成统计
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("原始片段", f"{len(video_clips)}个")
                    with col2:
                        st.metric("有效片段", f"{len(valid_videos)}个")
                    with col3:
                        video_info = services['video'].get_video_info(current_video)
                        if video_info:
                            st.metric("总时长", f"{video_info['duration']:.1f}秒")
                    
                    st.rerun()
                else:
                    st.error("❌ 视频合成失败")
                    
            except Exception as e:
                st.error(f"合成过程出错: {str(e)}")
                import traceback
                st.error("详细错误信息：")
                st.code(traceback.format_exc())
                
                # 显示调试信息
                with st.expander("🔍 调试信息", expanded=False):
                    st.write("视频片段状态：")
                    for i, video in enumerate(video_clips):
                        if video and Path(video).exists():
                            file_size = Path(video).stat().st_size / 1024 / 1024  # MB
                            st.write(f"  ✅ 片段 {i+1}: {Path(video).name} ({file_size:.1f}MB)")
                        else:
                            st.write(f"  ❌ 片段 {i+1}: 文件不存在")
                    
                    if 'audio_file' in st.session_state.results:
                        audio_file = st.session_state.results['audio_file']
                        if Path(audio_file).exists():
                            file_size = Path(audio_file).stat().st_size / 1024 / 1024
                            st.write(f"  ✅ 音频文件: {Path(audio_file).name} ({file_size:.1f}MB)")
                        else:
                            st.write(f"  ❌ 音频文件不存在: {audio_file}")
    
    with col2:
        if st.button("⬅️ 返回上一步"):
            st.session_state.step = 5
            st.rerun()
    
    # 显示最终视频
    if 'final_video' in st.session_state.results:
        final_video_path = st.session_state.results['final_video']
        if Path(final_video_path).exists():
            st.subheader("🎊 最终视频")
            st.video(final_video_path)
            
            # 视频信息
            video_info = services['video'].get_video_info(final_video_path)
            if video_info:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("时长", f"{video_info['duration']:.1f}秒")
                with col2:
                    st.metric("分辨率", f"{video_info['width']}x{video_info['height']}")
                with col3:
                    st.metric("帧率", f"{video_info['fps']:.1f}fps")
            
            # 下载按钮
            with open(final_video_path, "rb") as file:
                st.download_button(
                    label="📥 下载视频",
                    data=file.read(),
                    file_name=f"{final_video_name}.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
            
            # 重新开始
            if st.button("🔄 制作新视频", use_container_width=True):
                st.session_state.results = {}
                st.session_state.step = 1
                st.success("已重置，可以开始制作新视频！")
                st.rerun()
        else:
            st.error(f"视频文件不存在: {final_video_path}")

def _generate_subtitles_from_text(text: str) -> List[Dict]:
    """
    根据文本生成字幕数据，包含时间信息
    """
    try:
        # 将文本分割成句子
        sentences = _split_text_into_sentences(text)
        
        # 估算总时长（假设平均每秒2.5个单词）
        total_words = len(text.split())
        total_duration = total_words / 2.5
        
        # 计算每个句子的时长
        sentence_durations = _calculate_sentence_durations(sentences, total_duration)
        
        # 生成字幕数据
        subtitles = []
        current_time = 0.0
        
        for i, (sentence, duration) in enumerate(zip(sentences, sentence_durations)):
            subtitle = {
                'text': sentence.strip(),
                'start': current_time,
                'duration': duration
            }
            subtitles.append(subtitle)
            current_time += duration
        
        return subtitles
        
    except Exception as e:
        print(f"生成字幕数据失败: {str(e)}")
        # 回退到简单分割
        return [{'text': text, 'start': 0, 'duration': 10}]

def _split_text_into_sentences(text: str) -> List[str]:
    """
    将文本分割成句子
    """
    import re
    
    # 使用标点符号分割句子
    sentences = re.split(r'[。！？.!?]+', text)
    
    # 过滤空句子并去除首尾空格
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # 如果没有找到标点符号，按长度分割
    if len(sentences) <= 1 and len(text) > 50:
        # 按大约30个字符分割
        sentences = [text[i:i+30] for i in range(0, len(text), 30)]
    
    # 如果还是没有分割，返回原文本
    if not sentences:
        sentences = [text]
    
    return sentences

def _calculate_sentence_durations(sentences: List[str], total_duration: float) -> List[float]:
    """
    根据句子长度分配时长
    """
    if not sentences:
        return []
    
    # 计算每个句子的字符数
    sentence_lengths = [len(sentence) for sentence in sentences]
    total_length = sum(sentence_lengths)
    
    if total_length == 0:
        # 如果总长度为0，平均分配时长
        duration_per_sentence = total_duration / len(sentences) if len(sentences) > 0 else 3.0
        return [duration_per_sentence] * len(sentences)
    
    # 按照字符数比例分配时长
    durations = []
    for length in sentence_lengths:
        duration = (length / total_length) * total_duration
        # 确保每个句子至少有2秒的显示时间，以确保可读性
        duration = max(duration, 2.0)
        durations.append(duration)
    
    # 调整总时长以匹配预期，但不要过度压缩
    current_total = sum(durations)
    if current_total > 0 and current_total > total_duration:
        # 只有当当前总时长超过预期时才进行调整
        scale_factor = total_duration / current_total
        # 但确保缩放因子不会使任何句子的时长低于1.5秒
        scaled_durations = [max(d * scale_factor, 1.5) for d in durations]
        durations = scaled_durations
    
    return durations