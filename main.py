"""
AI视频生成器 - 完整版本
集成LLM、ComfyUI、TTS等服务，提供完整的AI视频生成功能
"""

import streamlit as st
import json
import time
import os
from pathlib import Path

# 导入服务模块
try:
    from services.llm_service import LLMService
    from services.comfyui_service import ComfyUIService  
    from services.tts_service import TTSService
    # 导入增强版TTS服务
    from enhanced_tts_service import EnhancedTTSService
    from services.video_service import VideoService
    from app_steps import render_step_4_video_generation, render_step_5_audio_generation, render_step_6_final_composition
    from prompts_config import render_prompts_config
    from config import Config
except ImportError as e:
    st.error(f"导入服务模块失败: {e}")
    st.stop()

# 页面配置
st.set_page_config(
    page_title="AI视频生成器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
.main-header {
    text-align: center;
    color: #1f4e79;
    margin-bottom: 30px;
}
.step-header {
    color: #2e7d32;
    border-bottom: 2px solid #2e7d32;
    padding-bottom: 10px;
}
.status-success {
    color: #4caf50;
    font-weight: bold;
}
.status-error {
    color: #f44336;
    font-weight: bold;
}
.status-warning {
    color: #ff9800;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# 初始化服务
@st.cache_resource
def initialize_services():
    """初始化所有服务"""
    try:
        # 导入优化的视频服务
        try:
            from services.optimized_video_service import OptimizedVideoService
            video_service = OptimizedVideoService()
            print("✅ 使用优化的视频服务")
        except Exception as e:
            print(f"⚠️ 无法加载优化的视频服务，使用默认视频服务: {e}")
            from services.video_service import VideoService
            video_service = VideoService()
        
        # 导入优化的ComfyUI服务
        try:
            from services.optimized_comfyui_service import OptimizedComfyUIService
            comfyui_service = OptimizedComfyUIService()
            print("✅ 使用优化的ComfyUI服务")
        except Exception as e:
            print(f"⚠️ 无法加载优化的ComfyUI服务，使用默认ComfyUI服务: {e}")
            from services.comfyui_service import ComfyUIService
            comfyui_service = ComfyUIService()
        
        # 默认使用增强版TTS服务
        services = {
            'llm': LLMService(),
            'comfyui': comfyui_service,
            'tts': EnhancedTTSService(),  # 默认使用增强版TTS服务
            'video': video_service
        }
        return services
    except Exception as e:
        st.error(f"服务初始化失败: {e}")
        return {}

@st.cache_data(ttl=30)  # 缩短缓存时间
def check_service_status(_services):
    """检查服务状态"""
    status = {}
    
    # 检查LLM服务 - 先检查配置，再检查连接
    if 'llm' in _services and _services['llm']:
        # 首先检查配置是否存在
        if hasattr(_services['llm'], 'api_key') and _services['llm'].api_key:
            # 配置存在，再检查连接（允许连接失败但配置正确）
            try:
                status['llm'] = _services['llm'].check_connection()
            except Exception:
                # 连接检查失败，但配置正确，仍然认为可用
                status['llm'] = True
        else:
            status['llm'] = False
    else:
        status['llm'] = False
        
    # 检查其他服务
    if 'comfyui' in _services and _services['comfyui']:
        try:
            status['comfyui'] = _services['comfyui'].check_connection()
        except Exception:
            status['comfyui'] = False
    else:
        status['comfyui'] = False
        
    if 'tts' in _services and _services['tts']:
        try:
            status['tts'] = _services['tts'].check_connection()
        except Exception:
            status['tts'] = False
    else:
        status['tts'] = False
        
    if 'video' in _services and _services['video']:
        try:
            status['video'] = _services['video'].check_connection()
        except Exception:
            status['video'] = False
    else:
        status['video'] = False
        
    return status

# 一键生成功能
def start_one_click_generation(topic, services, status, settings):
    """一键生成完整视频"""
    if not all([status['llm'], status['comfyui']]):
        st.error("缺少必要服务，无法进行一键生成")
        if not status['llm']:
            st.info("💡 LLM服务不可用，请检查API密钥配置")
        if not status['comfyui']:
            st.info("💡 ComfyUI服务不可用，请确保ComfyUI已启动并运行在 http://127.0.0.1:8188")
        return
        
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 步骤 1: 生成脚本
            status_text.text("📝 步骤 1/6: 正在生成脚本...")
            progress_bar.progress(10)
            
            result = services['llm'].generate_scripts(topic, settings)
            if not result['success']:
                st.error(f"脚本生成失败: {result['error']}")
                return
                
            st.session_state.results['topic'] = topic
            st.session_state.results['scripts'] = result['data']
            st.session_state.results['storyboard_prompts_list'] = result['data'].get('storyboard_prompts', [])
            
            progress_bar.progress(20)
            status_text.text("✅ 脚本生成完成")
            
            # 步骤 2: 生成分镜图
            status_text.text("🎨 步骤 2/6: 正在生成分镜图...")
            progress_bar.progress(35)
            
            prompts = st.session_state.results['storyboard_prompts_list']
            images = services['comfyui'].generate_images(prompts)
            st.session_state.results['storyboard_images'] = images
            
            progress_bar.progress(50)
            status_text.text("✅ 分镜图生成完成")
            
            # 步骤 3: 生成视频片段
            status_text.text("🎥 步骤 3/6: 正在生成视频片段...")
            progress_bar.progress(60)
            
            video_prompts = [f"video prompt for {i+1}" for i in range(len(images))]
            # 使用默认视频参数
            video_params = {'duration': 5, 'fps': 18, 'quality': '中'}
            
            # 显示视频生成参数
            with st.expander("📊 视频生成参数", expanded=False):
                st.json(video_params)
            
            # 生成视频片段
            videos = services['comfyui'].generate_videos(images, video_prompts, video_params)
            st.session_state.results['video_clips'] = videos
            
            # 检查视频生成结果
            valid_videos = [v for v in videos if v and Path(v).exists()]
            if len(valid_videos) == 0:
                st.warning("⚠️ 所有视频生成失败，可能原因：")
                st.info("1. ComfyUI内存不足 - 尝试重启ComfyUI服务")
                st.info("2. 视频生成超时 - 系统已自动增加超时时间")
                st.info("3. 模型文件缺失 - 检查ComfyUI模型目录")
                st.info("4. 系统资源不足 - 关闭其他程序释放内存")
                
                # 提供重试选项
                if st.button("🔄 重新生成视频片段"):
                    st.session_state.step = 4
                    st.rerun()
            
            progress_bar.progress(75)
            status_text.text("✅ 视频片段生成完成")
            
            # 步骤 4: 生成配音
            status_text.text("🎵 步骤 4/6: 正在生成配音...")
            progress_bar.progress(85)
            
            audio_script = st.session_state.results['scripts'].get('audio_script', '')
            
            # 检查是否有预设的参考音频
            reference_audio = st.session_state.results.get('one_click_reference_audio')
            
            if audio_script:
                if reference_audio:
                    # 有参考音频，使用ComfyUI生成配音
                    status_text.text("🎵 使用参考音频生成配音...")
                    audio_file = services['tts'].text_to_speech_with_comfyui(
                        audio_script, 
                        "auto_narration_with_ref",
                        reference_audio=reference_audio
                    )
                    if audio_file:
                        st.session_state.results['audio_file'] = audio_file
                        status_text.text("✅ 配音生成完成（使用参考音频）")
                    else:
                        status_text.text("⚠️ 配音生成失败，将跳过音频")
                else:
                    # 没有参考音频，跳过配音步骤
                    status_text.text("⚠️ 未设置参考音频，跳过配音步骤")
                    st.warning("💡 提示：您可以在高级设置中上传参考音频文件来启用配音功能")
            else:
                status_text.text("⚠️ 没有配音脚本，跳过配音步骤")
            
            progress_bar.progress(90)
            status_text.text("✅ 配音生成完成")
            
            # 步骤 5: 合成最终视频
            status_text.text("🎆 步骤 5/6: 正在合成最终视频...")
            progress_bar.progress(95)
            
            # 过滤有效的视频文件
            valid_videos = [v for v in videos if v and Path(v).exists()]
            
            if valid_videos and status['video']:
                # 生成时间戳文件名
                import time
                timestamp = int(time.time())
                final_video_name = f"auto_video_{timestamp}"
                
                # 使用优化的视频合并服务
                if hasattr(services['video'], 'merge_video_clips_batch'):
                    # 使用批处理合并（优化版本）
                    merged_video = services['video'].merge_video_clips_batch(valid_videos, f"{final_video_name}_merged")
                else:
                    # 使用默认合并
                    merged_video = services['video'].merge_video_clips(valid_videos, f"{final_video_name}_merged")
                
                if merged_video:
                    # 检查是否有音频文件
                    if 'audio_file' in st.session_state.results:
                        # 添加音频
                        final_video = services['video'].add_audio(
                            merged_video, 
                            st.session_state.results['audio_file'], 
                            final_video_name
                        )
                        if final_video:
                            st.session_state.results['final_video'] = final_video
                            status_text.text("✅ 视频合成完成（包含音频）")
                        else:
                            # 添加音频失败，使用无音频版本
                            st.session_state.results['final_video'] = merged_video
                            status_text.text("⚠️ 添加音频失败，使用无音频版本")
                    else:
                        # 没有音频，直接使用合并后的视频
                        st.session_state.results['final_video'] = merged_video
                        status_text.text("✅ 视频合成完成（无音频）")
                else:
                    status_text.text("❌ 视频合成失败")
            else:
                status_text.text("❌ 没有有效的视频文件或视频服务未就绪")
            
            progress_bar.progress(100)
            
            # 检查生成结果
            if 'final_video' in st.session_state.results:
                if 'audio_file' in st.session_state.results:
                    status_text.text("🎉 视频生成完成！（包含配音）")
                else:
                    status_text.text("🎉 视频生成完成！（无配音）")
                    st.info("💡 提示：您可以在步骤5中手动添加配音")
            else:
                status_text.text("⚠️ 视频生成部分完成，请检查结果")
            
            # 跳转到结果展示页面
            st.session_state.step = 7
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"生成过程中发生错误: {str(e)}")
            st.info("💡 解决建议：")
            st.info("1. 检查ComfyUI是否正常运行")
            st.info("2. 重启ComfyUI服务释放内存")
            st.info("3. 检查系统资源使用情况")
            st.info("4. 查看控制台详细错误信息")

# 初始化会话状态
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'show_prompts_config' not in st.session_state:
    st.session_state.show_prompts_config = False

# 初始化服务和状态
services = initialize_services()

# 添加刷新按钮来清除缓存
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = 0

# 检查服务状态，在缓存key中包含刷新计数器
status = check_service_status(services)

# 主标题
st.markdown('<h1 class="main-header">🎬 AI视频一键生成系统</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666;">从文字主题到完整视频的一站式生成工具</p>', unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.title("控制面板")
    
    # 服务状态
    st.markdown("### 服务状态")
    
    # LLM服务状态 - 详细显示
    if status.get('llm', False):
        st.success("✅ LLM服务: 正常")
        if 'llm' in services and hasattr(services['llm'], 'api_key'):
            st.caption(f"🔑 API: {services['llm'].api_key[:20]}...")
            st.caption(f"🌐 模型: {services['llm'].model}")
    else:
        st.error("❌ LLM服务: 异常")
        if 'llm' in services:
            if not hasattr(services['llm'], 'api_key') or not services['llm'].api_key:
                st.caption("⚠️ 原因: API Key 未设置")
            else:
                st.caption("⚠️ 原因: 连接检查失败（但配置正确）")
        else:
            st.caption("⚠️ 原因: 服务初始化失败")
    
    # 其他服务状态简化显示
    status_col1, status_col2 = st.columns(2)
    
    with status_col1:
        st.write("🎨 ComfyUI:", "✅" if status.get('comfyui', False) else "❌")
        st.write("🔊 TTS:", "✅" if status.get('tts', False) else "✅")
    
    with status_col2:
        st.write("🎬 Video:", "✅" if status.get('video', False) else "❌")
    
    # 刷新按钮
    if st.button("🔄 刷新状态", use_container_width=True):
        st.session_state.force_refresh += 1
        st.cache_data.clear()  # 清除所有缓存数据
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 快速跳转")
    
    # 检查各步骤的数据完整性
    step_status = {
        1: True,  # 总是可用
        2: 'scripts' in st.session_state.results,
        3: 'scripts' in st.session_state.results,
        4: 'storyboard_images' in st.session_state.results,
        5: 'video_clips' in st.session_state.results,
        6: 'audio_file' in st.session_state.results,
        7: 'final_video' in st.session_state.results
    }
    
    steps = [
        (1, "📝 输入主题"),
        (2, "📋 脚本编辑"), 
        (3, "🎨 分镜生成"),
        (4, "🎬 视频片段"),
        (5, "🎵 音频生成"),
        (6, "🎞️ 视频合成"),
        (7, "🎉 最终结果")
    ]
    
    current_step = st.session_state.get('step', 1)
    
    for step_num, step_name in steps:
        # 判断按钮类型和可用性
        if step_num == current_step:
            button_type = "primary"
            disabled = False
        elif step_status.get(step_num, False):
            button_type = "secondary"
            disabled = False
        else:
            button_type = "secondary"  # 改为None为secondary
            disabled = True
        
        # 显示步骤状态图标
        if step_status.get(step_num, False):
            status_icon = "✅" if step_num < current_step else "📍" if step_num == current_step else "⏳"
        else:
            status_icon = "🔒"
        
        button_label = f"{status_icon} {step_name}"
        
        if st.button(button_label, key=f"step_{step_num}", use_container_width=True, 
                    type=button_type, disabled=disabled):
            st.session_state.step = step_num
            st.rerun()
    
    st.markdown("---")
    
    # 数据缓存管理
    st.markdown("### 数据管理")
    
    # 显示当前缓存的数据
    if st.session_state.results:
        with st.expander("💾 已缓存数据", expanded=False):
            cached_items = []
            if 'topic' in st.session_state.results:
                cached_items.append("📝 主题")
            if 'scripts' in st.session_state.results:
                cached_items.append("📋 脚本")
            if 'storyboard_images' in st.session_state.results:
                cached_items.append(f"🎨 分镜图 ({len(st.session_state.results['storyboard_images'])})")
            if 'video_clips' in st.session_state.results:
                valid_videos = [v for v in st.session_state.results['video_clips'] if v and Path(v).exists()]
                cached_items.append(f"🎬 视频片段 ({len(valid_videos)})")
            if 'audio_file' in st.session_state.results:
                cached_items.append("🎵 音频")
            if 'final_video' in st.session_state.results:
                cached_items.append("🎞️ 最终视频")
            
            for item in cached_items:
                st.write(f"• {item}")
    
    # 保存/加载缓存
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存缓存", use_container_width=True):
            try:
                import json
                cache_data = {
                    'step': st.session_state.step,
                    'results': {}
                }
                
                # 只保存路径信息，不保存文件内容
                for key, value in st.session_state.results.items():
                    if key in ['topic', 'settings', 'scripts']:
                        cache_data['results'][key] = value
                    elif key in ['storyboard_images', 'video_clips']:
                        if isinstance(value, list):
                            cache_data['results'][key] = [str(v) if v else None for v in value]
                    elif key in ['audio_file', 'final_video']:
                        cache_data['results'][key] = str(value) if value else None
                
                cache_file = Config.BASE_DIR / "session_cache.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                st.success("缓存保存成功！")
            except Exception as e:
                st.error(f"保存失败: {str(e)}")
    
    with col2:
        if st.button("📂 加载缓存", use_container_width=True):
            try:
                import json
                cache_file = Config.BASE_DIR / "session_cache.json"
                
                if cache_file.exists():
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    # 恢复状态
                    st.session_state.step = cache_data.get('step', 1)
                    st.session_state.results = {}
                    
                    # 验证文件是否仍然存在
                    for key, value in cache_data.get('results', {}).items():
                        if key in ['topic', 'settings', 'scripts']:
                            st.session_state.results[key] = value
                        elif key in ['storyboard_images', 'video_clips']:
                            if isinstance(value, list):
                                valid_files = []
                                for v in value:
                                    if v and Path(v).exists():
                                        valid_files.append(v)
                                    else:
                                        valid_files.append(None)
                                st.session_state.results[key] = valid_files
                        elif key in ['audio_file', 'final_video']:
                            if value and Path(value).exists():
                                st.session_state.results[key] = value
                    
                    st.success("缓存加载成功！")
                    st.rerun()
                else:
                    st.warning("未找到缓存文件")
            except Exception as e:
                st.error(f"加载失败: {str(e)}")
    
    st.markdown("---")
    
    # 其他操作
    # 提示词配置入口
    if st.button("🔧 编辑提示词模板", use_container_width=True):
        st.session_state.show_prompts_config = not st.session_state.get('show_prompts_config', False)
        st.rerun()
    
    if st.button("🔄 重新开始", use_container_width=True):
        st.session_state.results = {}
        st.session_state.step = 1
        st.session_state.show_prompts_config = False
        st.rerun()
    
    if st.button("🗑️ 清空数据", use_container_width=True):
        st.session_state.clear()
        st.success("数据已清空")
        st.rerun()

# 主内容区域
if st.session_state.get('show_prompts_config', False):
    render_prompts_config()
else:
    # 原有的步骤显示逻辑
    if st.session_state.step == 1:
        st.markdown('<h2 class="step-header">步骤1: 输入主题</h2>', unsafe_allow_html=True)
        
        # 主题输入
        topic = st.text_area(
            "请输入视频主题",
            placeholder="例如：人工智能的发展历程、环保的重要性、健康生活方式...",
            height=120,
            help="描述你想要制作的视频内容主题，越详细越好"
        )
        
        # 高级设置
        with st.expander("⚙️ 高级设置", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                video_duration = st.slider("目标视频时长(秒)", 30, 180, 60)
                scene_count = st.slider("分镜图数量", 3, 8, 5)
            
            with col2:
                video_style = st.selectbox("视频风格", ["现代简约", "科技感", "温馨", "商务", "艺术"])
                language = st.selectbox("配音语言", ["中文", "英文"])
        
        # 参考音频设置（用于一键生成）
        with st.expander("🎤 参考音频设置（可选）", expanded=False):
            st.markdown("""**提示**: 如果要使用一键生成功能并包含配音，请先上传参考音频文件。
            如果不上传，一键生成将跳过配音步骤，您可以稍后在手动模式下添加配音。""")
            
            uploaded_reference_audio = st.file_uploader(
                "选择参考音频文件（用于一键生成）",
                type=['wav', 'mp3', 'flac', 'ogg'],
                help="支持 WAV, MP3, FLAC, OGG 格式的音频文件",
                key="one_click_reference_audio"
            )
            
            if uploaded_reference_audio:
                st.success(f"✅ 已选择参考音频: {uploaded_reference_audio.name}")
                
                # 播放上传的音频预览
                st.audio(uploaded_reference_audio, format=uploaded_reference_audio.type)
                
                # 保存上传的音频文件
                try:
                    import time
                    timestamp = int(time.time())
                    reference_filename = f"reference_audio_oneclcik_{timestamp}.wav"
                    reference_path = Config.AUDIO_DIR / "references" / reference_filename
                    reference_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(reference_path, "wb") as f:
                        f.write(uploaded_reference_audio.getbuffer())
                    
                    st.session_state.results['one_click_reference_audio'] = str(reference_path)
                    st.info(f"参考音频已保存，一键生成时将使用此音频进行配音")
                    
                except Exception as e:
                    st.error(f"保存参考音频失败: {str(e)}")
            else:
                st.info("💡 未上传参考音频时，一键生成将跳过配音步骤")
        
        # 字幕样式设置
        with st.expander("🎨 字幕样式设置（可选）", expanded=False):
            st.markdown("""💡 **提示**: 在这里设置的字幕样式将作为默认样式保存，
            下次生成视频时自动使用这些设置。""")
            
            # 智能预设功能
            st.markdown("##### 🤖 智能预设")
            st.markdown("🎆 **新功能**: 根据视频宽高比自动匹配最优字幕样式！")
            
            # 智能预设选择
            col1, col2 = st.columns([2, 1])
            
            with col1:
                use_smart_preset = st.checkbox(
                    "🤖 启用智能预设", 
                    value=st.session_state.get('use_smart_preset', False),
                    help="根据视频尺寸自动选择最优字幕样式"
                )
                st.session_state.use_smart_preset = use_smart_preset
                
                if use_smart_preset:
                    # 预设选择和预览
                    preset_options = {
                        "竖屏优化 (9:16)": "portrait",
                        "横屏经典 (16:9)": "landscape", 
                        "方形时尚 (1:1)": "square",
                        "超宽屏影院 (21:9)": "ultrawide"
                    }
                    
                    selected_preset = st.selectbox(
                        "选择预设样式",
                        options=list(preset_options.keys()),
                        index=0,
                        help="选择与您视频格式匹配的预设样式"
                    )
                    
                    preset_type = preset_options[selected_preset]
                    
                    # 显示预设介绍
                    from services.smart_subtitle_style_service import SmartSubtitleStyleService
                    smart_service = SmartSubtitleStyleService()
                    preset_info = smart_service.presets[preset_type]
                    
                    st.info(f"📝 **{preset_info['name']}**: {preset_info['description']}")
                    
                    # 视频尺寸输入用于预览
                    col_w, col_h = st.columns(2)
                    with col_w:
                        preview_width = st.number_input(
                            "视频宽度（预览）", 
                            min_value=320, max_value=4096, 
                            value=1920 if preset_type == 'landscape' else 720,
                            step=16
                        )
                    with col_h:
                        preview_height = st.number_input(
                            "视频高度（预览）", 
                            min_value=240, max_value=4096, 
                            value=1080 if preset_type == 'landscape' else 1280,
                            step=16
                        )
                    
                    # 预览智能样式
                    if st.button("🔍 预览智能样式", use_container_width=True):
                        preview_result = smart_service.preview_style_for_resolution(preview_width, preview_height)
                        
                        st.success(f"🎯 检测结果: {preview_result['detected_format']}")
                        
                        col_prev1, col_prev2 = st.columns(2)
                        with col_prev1:
                            st.metric("宽高比", f"{preview_result['aspect_ratio']}:1")
                            st.metric("缩放因子", f"{preview_result['scale_factor']}x")
                        with col_prev2:
                            st.metric("字号大小", preview_result['font_size_preview'])
                            st.metric("底部位置", preview_result['position_preview'])
                        
                        # 应用智能样式
                        smart_style = smart_service.get_smart_subtitle_style(preview_width, preview_height)
                        # 移除检测信息
                        if '_detection_info' in smart_style:
                            del smart_style['_detection_info']
                        
                        st.session_state.subtitle_style = smart_style
                        st.session_state.results['subtitle_style'] = smart_style
                        
                        # 保存到文件
                        try:
                            serializable_config = {}
                            for key, value in smart_style.items():
                                if isinstance(value, tuple):
                                    serializable_config[key] = list(value)
                                else:
                                    serializable_config[key] = value
                            
                            style_file = Config.BASE_DIR / "subtitle_style.json"
                            with open(style_file, 'w', encoding='utf-8') as f:
                                json.dump(serializable_config, f, ensure_ascii=False, indent=2)
                            
                            st.success("✅ 智能样式已应用并保存！")
                        except Exception as e:
                            st.error(f"保存样式失败: {e}")
                    
                    st.markdown("---")
                    
                    # 显示当前预设的样式参数
                    st.markdown("🔍 **预设样式参数详情**")
                    preset_style = preset_info['style']
                    col_p1, col_p2 = st.columns(2)
                    
                    with col_p1:
                        st.write(f"🔤 **字体设置**")
                        st.write(f"  • 字号: {preset_style['font_scale']}倍")
                        st.write(f"  • 粗细: {preset_style['thickness']}")
                        st.write(f"  • 描边: {preset_style['outline_thickness']}")
                        st.write(f"  • 行高: {preset_style['line_height']}px")
                    
                    with col_p2:
                        st.write(f"🌈 **颜色和位置**")
                        st.write(f"  • 文字: BGR{preset_style['text_color']}")
                        st.write(f"  • 描边: BGR{preset_style['outline_color']}")
                        st.write(f"  • 背景透明度: {preset_style['bg_alpha']}")
                        st.write(f"  • 底部边距: {preset_style['bottom_margin']}px")
            
            with col2:
                if use_smart_preset:
                    st.markdown("📊 **智能预设优势**")
                    st.markdown("""
                    • 🎯 自动匹配最优样式
                    • 📱 适配不同屏幕比例
                    • 🔍 智能缩放调节
                    • ✨ 专业设计预设
                    """)
                else:
                    st.markdown("🎨 **手动设置**")
                    st.markdown("""
                    • 🔧 精细调节参数
                    • 🌈 自定义颜色
                    • 💯 完全控制
                    • 💾 保存个性设置
                    """)
            
            # 如果未启用智能预设，显示手动设置界面
            if not use_smart_preset:
                st.markdown("---")
                st.markdown("##### 🔧 手动设置")
                
                # 加载保存的字幕样式设置
                def load_subtitle_style():
                    """加载保存的字幕样式设置"""
                    try:
                        style_file = Config.BASE_DIR / "subtitle_style.json"
                        if style_file.exists():
                            with open(style_file, 'r', encoding='utf-8') as f:
                                loaded_config = json.load(f)
                            
                            # 将列表转换回元组（对于颜色值）
                            for key in ['text_color', 'outline_color', 'bg_color']:
                                if key in loaded_config and isinstance(loaded_config[key], list):
                                    loaded_config[key] = tuple(loaded_config[key])
                            
                            return loaded_config
                        else:
                            # 返回默认样式
                            return Config.SUBTITLE_STYLE['opencv'].copy()
                    except Exception as e:
                        st.error(f"加载字幕样式失败: {e}")
                        return Config.SUBTITLE_STYLE['opencv'].copy()
                
                def save_subtitle_style(style_config):
                    """保存字幕样式设置"""
                    try:
                        # 为了稳定序列化，将元组转换为列表
                        serializable_config = {}
                        for key, value in style_config.items():
                            if isinstance(value, tuple):
                                serializable_config[key] = list(value)
                            else:
                                serializable_config[key] = value
                        
                        style_file = Config.BASE_DIR / "subtitle_style.json"
                        with open(style_file, 'w', encoding='utf-8') as f:
                            json.dump(serializable_config, f, ensure_ascii=False, indent=2)
                        return True
                    except Exception as e:
                        st.error(f"保存字幕样式失败: {e}")
                        return False
                
                # 初始化字幕样式设置
                if 'subtitle_style' not in st.session_state:
                    st.session_state.subtitle_style = load_subtitle_style()
                
                current_style = st.session_state.subtitle_style
                
                # 字体设置
                st.markdown("###### 🔤 字体设置")
                col1, col2 = st.columns(2)
                
                with col1:
                    font_scale = st.slider(
                        "字号大小", 
                        min_value=1.0, max_value=5.0, 
                        value=float(current_style.get('font_scale', 2.0)), 
                        step=0.1,
                        key="subtitle_font_scale"
                    )
                    
                    thickness = st.slider(
                        "字体粗细", 
                        min_value=1, max_value=8, 
                        value=int(current_style.get('thickness', 3)),
                        key="subtitle_thickness"
                    )
                
                with col2:
                    outline_thickness = st.slider(
                        "描边粗细", 
                        min_value=0, max_value=6, 
                        value=int(current_style.get('outline_thickness', 2)),
                        key="subtitle_outline_thickness"
                    )
                    
                    line_height = st.slider(
                        "行高", 
                        min_value=40, max_value=120, 
                        value=int(current_style.get('line_height', 60)),
                        key="subtitle_line_height"
                    )
                
                # 颜色设置
                st.markdown("###### 🌈 颜色设置")
                
                # 颜色选择器
                color_options = {
                    "白色": (255, 255, 255),
                    "黑色": (0, 0, 0),
                    "红色": (0, 0, 255),
                    "绿色": (0, 255, 0),
                    "蓝色": (255, 0, 0),
                    "黄色": (0, 255, 255),
                    "紫色": (255, 0, 255),
                    "青色": (255, 255, 0)
                }
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 文字颜色
                    current_text_color = current_style.get('text_color', (255, 255, 255))
                    text_color_name = next((name for name, color in color_options.items() if color == tuple(current_text_color)), "自定义")
                    
                    text_color_choice = st.selectbox(
                        "文字颜色",
                        options=list(color_options.keys()) + ["自定义"],
                        index=list(color_options.keys()).index(text_color_name) if text_color_name != "自定义" else len(color_options),
                        key="subtitle_text_color_choice"
                    )
                    
                    if text_color_choice == "自定义":
                        text_color = st.color_picker(
                            "自定义文字颜色", 
                            value="#FFFFFF",
                            key="subtitle_text_color_custom"
                        )
                        # 转换为BGR格式
                        hex_color = text_color.lstrip('#')
                        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                        text_color_bgr = (b, g, r)
                    else:
                        text_color_bgr = color_options[text_color_choice]
                
                with col2:
                    # 描边颜色
                    current_outline_color = current_style.get('outline_color', (0, 0, 0))
                    outline_color_name = next((name for name, color in color_options.items() if color == tuple(current_outline_color)), "自定义")
                    
                    outline_color_choice = st.selectbox(
                        "描边颜色",
                        options=list(color_options.keys()) + ["自定义"],
                        index=list(color_options.keys()).index(outline_color_name) if outline_color_name != "自定义" else len(color_options),
                        key="subtitle_outline_color_choice"
                    )
                    
                    if outline_color_choice == "自定义":
                        outline_color = st.color_picker(
                            "自定义描边颜色", 
                            value="#000000",
                            key="subtitle_outline_color_custom"
                        )
                        # 转换为BGR格式
                        hex_color = outline_color.lstrip('#')
                        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                        outline_color_bgr = (b, g, r)
                    else:
                        outline_color_bgr = color_options[outline_color_choice]
                
                # 背景设置
                st.markdown("###### 📋 背景设置")
                col1, col2 = st.columns(2)
                
                with col1:
                    bg_alpha = st.slider(
                        "背景透明度", 
                        min_value=0.0, max_value=1.0, 
                        value=float(current_style.get('bg_alpha', 0.7)), 
                        step=0.1,
                        help="0.0=完全透明（无背景），1.0=完全不透明",
                        key="subtitle_bg_alpha"
                    )
                    
                    bg_padding = st.slider(
                        "背景内边距", 
                        min_value=5, max_value=25, 
                        value=int(current_style.get('bg_padding', 10)),
                        key="subtitle_bg_padding"
                    )
                
                with col2:
                    # 背景颜色
                    current_bg_color = current_style.get('bg_color', (0, 0, 0))
                    bg_color_name = next((name for name, color in color_options.items() if color == tuple(current_bg_color)), "自定义")
                    
                    bg_color_choice = st.selectbox(
                        "背景颜色",
                        options=list(color_options.keys()) + ["自定义"],
                        index=list(color_options.keys()).index(bg_color_name) if bg_color_name != "自定义" else len(color_options),
                        key="subtitle_bg_color_choice"
                    )
                    
                    if bg_color_choice == "自定义":
                        bg_color = st.color_picker(
                            "自定义背景颜色", 
                            value="#000000",
                            key="subtitle_bg_color_custom"
                        )
                        # 转换为BGR格式
                        hex_color = bg_color.lstrip('#')
                        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                        bg_color_bgr = (b, g, r)
                    else:
                        bg_color_bgr = color_options[bg_color_choice]
                    
                    bottom_margin = st.slider(
                        "底部边距", 
                        min_value=20, max_value=120, 
                        value=int(current_style.get('bottom_margin', 50)),
                        key="subtitle_bottom_margin"
                    )
                
                # 样式预览
                st.markdown("###### 👀 样式预览")
                
                # 创建当前样式配置
                current_style_config = {
                    'font_scale': font_scale,
                    'text_color': text_color_bgr,
                    'outline_color': outline_color_bgr,
                    'bg_color': bg_color_bgr,
                    'thickness': thickness,
                    'outline_thickness': outline_thickness,
                    'bg_padding': bg_padding,
                    'line_height': line_height,
                    'bottom_margin': bottom_margin,
                    'bg_alpha': bg_alpha
                }
                
                # 显示样式信息
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"🔤 字号: {font_scale}, 粗细: {thickness}")
                    st.write(f"🌈 文字: {text_color_choice}, 描边: {outline_color_choice}")
                with col2:
                    st.write(f"📋 背景: {bg_color_choice}, 透明度: {bg_alpha}")
                    st.write(f"📌 边距: 内{bg_padding}px, 底{bottom_margin}px")
                
                # 操作按钮
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("💾 保存样式", use_container_width=True):
                        st.session_state.subtitle_style = current_style_config
                        if save_subtitle_style(current_style_config):
                            st.success("✅ 字幕样式已保存！")
                            # 保存到session_state供视频生成使用
                            st.session_state.results['subtitle_style'] = current_style_config
                        else:
                            st.error("❌ 保存失败")
                
                with col2:
                    if st.button("🔄 重置默认", use_container_width=True):
                        st.session_state.subtitle_style = Config.SUBTITLE_STYLE['opencv'].copy()
                        st.success("✅ 已重置为默认样式")
                        st.rerun()
                
                with col3:
                    if st.button("🎨 测试样式", use_container_width=True):
                        st.info("💡 测试样式功能将在视频合成步骤中可用")
            
            # 将智能预设和手动设置的公共部分放在最后
            # 智能推荐提示
            if not use_smart_preset:
                st.markdown("---")
                st.markdown("🤖 **推荐**: 尝试智能预设功能，自动匹配最优字幕样式！")
        
        # 操作按钮
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📝 生成脚本", type="primary", use_container_width=True):
                if not topic.strip():
                    st.error("请先输入视频主题")
                elif not status['llm']:
                    st.error("LLM服务未配置，请设置OPENAI_API_KEY")
                else:
                    with st.spinner("正在生成脚本，这可能需要几分钟..."):
                        # 保存用户设置
                        st.session_state.results['topic'] = topic
                        st.session_state.results['settings'] = {
                            'duration': video_duration,
                            'scene_count': scene_count,
                            'style': video_style,
                            'language': language
                        }
                        
                        # 调用LLM生成脚本
                        result = services['llm'].generate_scripts(topic, {
                            'duration': video_duration,
                            'scene_count': scene_count,
                            'style': video_style,
                            'language': language
                        })
                        
                        if result['success']:
                            st.session_state.results['scripts'] = result['data']
                            st.success("脚本生成成功！")
                            st.session_state.step = 2
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"脚本生成失败: {result['error']}")
                            if 'raw_content' in result:
                                st.text_area("原始返回内容", value=result['raw_content'], height=200)
        
        with col2:
            if st.button("🚀 一键生成完整视频", use_container_width=True):
                if not topic.strip():
                    st.error("请先输入视频主题")
                elif not all([status['comfyui'], status['llm']]):
                    st.error("服务未就绪，请检查ComfyUI和LLM服务状态")
                else:
                    # 开始一键生成流程
                    start_one_click_generation(topic, services, status, {
                        'duration': video_duration,
                        'scene_count': scene_count,
                        'style': video_style,
                        'language': language
                    })

    elif st.session_state.step == 2:
        st.markdown('<h2 class="step-header">步骤2: 脚本生成结果</h2>', unsafe_allow_html=True)
        
        if 'scripts' in st.session_state.results:
            scripts = st.session_state.results['scripts']
            
            # 显示脚本
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📝 视频脚本")
                st.text_area("视频拍摄脚本", value=scripts.get('video_script', ''), height=300, key="video_script_edit")
            
            with col2:
                st.subheader("🎙️ 配音脚本")
                st.text_area("配音旁白脚本", value=scripts.get('audio_script', ''), height=300, key="audio_script_edit")
            
            # 分镜图提示词
            st.subheader("🖼️ 分镜图提示词")
            st.info("💡 支持中文输入，系统将自动翻译成英文发送给绘图模型")
            prompts = scripts.get('storyboard_prompts', [])
            if isinstance(prompts, str):
                try:
                    prompts = json.loads(prompts)
                except:
                    prompts = [prompts]
            
            for i, prompt in enumerate(prompts):
                st.text_input(f"分镜图 {i+1}", value=prompt, key=f"prompt_edit_{i}")
            
            # 保存修改按钮
            if st.button("💾 保存修改", type="secondary", use_container_width=True):
                # 从 Streamlit 组件中获取用户编辑的内容
                video_script = st.session_state.get('video_script_edit', scripts.get('video_script', ''))
                audio_script = st.session_state.get('audio_script_edit', scripts.get('audio_script', ''))
                
                # 收集所有编辑后的分镜图提示词
                edited_prompts = []
                for i in range(len(prompts)):
                    edited_prompt = st.session_state.get(f'prompt_edit_{i}', prompts[i])
                    edited_prompts.append(edited_prompt)
                
                # 更新session_state中的脚本数据
                st.session_state.results['scripts']['video_script'] = video_script
                st.session_state.results['scripts']['audio_script'] = audio_script
                st.session_state.results['scripts']['storyboard_prompts'] = edited_prompts
                st.success("脚本修改已保存！")
                time.sleep(1)
                st.rerun()
            
            # 操作按钮
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 重新生成", type="secondary"):
                    st.session_state.step = 1
                    st.rerun()
            
            with col2:
                if st.button("✅ 确认并继续", type="primary"):
                    st.session_state.step = 3
                    st.rerun()
            
            with col3:
                if st.button("⬅️ 返回上一步"):
                    st.session_state.step = 1
                    st.rerun()
        else:
            st.error("未找到脚本数据，请返回第一步重新生成")

    elif st.session_state.step == 3:
        st.markdown('<h2 class="step-header">步骤3: 分镜图生成</h2>', unsafe_allow_html=True)
        
        if 'scripts' not in st.session_state.results:
            st.error("未找到脚本数据，请返回步骤2")
            if st.button("⬅️ 返回步骤2"):
                st.session_state.step = 2
                st.rerun()
        else:
            scripts = st.session_state.results['scripts']
            prompts = scripts.get('storyboard_prompts', [])
            
            if isinstance(prompts, str):
                try:
                    prompts = json.loads(prompts)
                except:
                    prompts = [prompts]
            
            # 显示分镜图提示词
            st.subheader("🎨 将要生成的分镜图")
            st.info("💡 提示词支持中文输入，系统将自动翻译成英文发送给绘图模型")
            for i, prompt in enumerate(prompts):
                st.text_area(f"分镜图 {i+1} 提示词", value=prompt, height=80, disabled=True)
            
            # 检查是否已经生成了分镜图
            if 'storyboard_images' in st.session_state.results:
                # 显示已生成的分镜图
                st.subheader("🖼️ 已生成的分镜图")
                
                storyboard_images = st.session_state.results['storyboard_images']
                
                # 使用列布局展示分镜图
                cols = st.columns(min(3, len(storyboard_images)))  # 最多3列
                
                for i, image_path in enumerate(storyboard_images):
                    with cols[i % len(cols)]:
                        if Path(image_path).exists():
                            # 为了避免Streamlit缓存问题，使用带时间戳的容器
                            import time
                            cache_buster = int(time.time() * 1000)  # 毫秒级时间戳
                            
                            # 在容器中显示图片，给容器唯一key
                            with st.container(key=f"img_container_{i}_{cache_buster}"):
                                st.image(image_path, caption=f"分镜图 {i+1}", use_container_width=True)
                            
                            # 根据项目规范，为每个分镜图提供控制按钮
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button(f"🔄 重新生成", key=f"regen_img_{i}"):
                                    # 重新生成单个分镜图
                                    with st.spinner(f"正在重新生成分镜图 {i+1}..."):
                                        # 使用单张图片生成方法
                                        new_image_path = services['comfyui'].generate_single_image(
                                            prompts[i], 
                                            f"storyboard_regen_{i+1:03d}"
                                        )
                                        if new_image_path:
                                            st.session_state.results['storyboard_images'][i] = new_image_path
                                            st.success(f"分镜图 {i+1} 重新生成成功！")
                                            st.rerun()
                            with col_b:
                                if st.button(f"📝 编辑提示词", key=f"edit_prompt_{i}"):
                                    # 设置编辑状态
                                    st.session_state[f'editing_prompt_{i}'] = True
                                    st.rerun()
                            
                            # 如果处于编辑状态，显示编辑框
                            if st.session_state.get(f'editing_prompt_{i}', False):
                                new_prompt = st.text_area(f"编辑分镜图 {i+1} 提示词", value=prompts[i], key=f"new_prompt_{i}")
                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.button("保存", key=f"save_prompt_{i}"):
                                        # 保存新提示词并重新生成
                                        st.session_state.results['scripts']['storyboard_prompts'][i] = new_prompt
                                        st.session_state[f'editing_prompt_{i}'] = False
                                        with st.spinner(f"正在使用新提示词生成分镜图 {i+1}..."):
                                            # 使用单张图片生成方法，指定文件名
                                            new_image_path = services['comfyui'].generate_single_image(
                                                new_prompt, 
                                                f"storyboard_edit_{i+1:03d}"
                                            )
                                            if new_image_path:
                                                st.session_state.results['storyboard_images'][i] = new_image_path
                                                st.success(f"分镜图 {i+1} 更新成功！")
                                                st.rerun()
                                with col_cancel:
                                    if st.button("取消", key=f"cancel_prompt_{i}"):
                                        st.session_state[f'editing_prompt_{i}'] = False
                                        st.rerun()
                        else:
                            st.error(f"分镜图 {i+1} 文件不存在: {image_path}")
                
                # 操作按钮
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔄 重新生成所有", type="secondary"):
                        # 重新生成所有分镜图
                        if status['comfyui']:
                            with st.spinner("正在重新生成所有分镜图..."):
                                storyboard_images = services['comfyui'].generate_images(prompts)
                                st.session_state.results['storyboard_images'] = storyboard_images
                                st.success("所有分镜图重新生成成功！")
                                st.rerun()
                        else:
                            st.error("ComfyUI服务未就绪")
                
                with col2:
                    if st.button("✅ 确认并继续", type="primary"):
                        st.session_state.step = 4
                        st.rerun()
                
                with col3:
                    if st.button("⬅️ 返回上一步"):
                        st.session_state.step = 2
                        st.rerun()
            
            else:
                # 尚未生成分镜图
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🎨 生成分镜图", type="primary", use_container_width=True):
                        if not prompts:
                            st.error("未找到分镜图提示词")
                        elif not status['comfyui']:
                            st.error("ComfyUI服务未就绪，请检查服务状态")
                        else:
                            with st.spinner(f"正在生成 {len(prompts)} 张分镜图，请稍等..."):
                                # 调用ComfyUI服务生成分镜图
                                storyboard_images = services['comfyui'].generate_images(prompts)
                                
                                if storyboard_images:
                                    st.session_state.results['storyboard_images'] = storyboard_images
                                    st.success(f"成功生成 {len(storyboard_images)} 张分镜图！")
                                    st.rerun()
                                else:
                                    st.error("分镜图生成失败，请检查ComfyUI服务")
                
                with col2:
                    if st.button("⬅️ 返回上一步", use_container_width=True):
                        st.session_state.step = 2
                        st.rerun()

    elif st.session_state.step == 4:
        render_step_4_video_generation(services, status)

    elif st.session_state.step == 5:
        render_step_5_audio_generation(services, status)

    elif st.session_state.step == 6:
        render_step_6_final_composition(services, status)

    elif st.session_state.step == 7:
        # 一键生成结果展示页面
        st.markdown('<h2 class="step-header">🎉 生成结果</h2>', unsafe_allow_html=True)
        
        # 显示生成的内容
        if 'topic' in st.session_state.results:
            st.subheader(f"🎥 主题: {st.session_state.results['topic']}")
        
        # 显示最终视频
        if 'final_video' in st.session_state.results:
            final_video_path = st.session_state.results['final_video']
            if final_video_path and Path(final_video_path).exists():
                st.subheader("🎆 最终视频")
                st.video(final_video_path)
                
                # 下载按钮
                try:
                    with open(final_video_path, "rb") as file:
                        st.download_button(
                            label="📥 下载视频",
                            data=file.read(),
                            file_name=f"ai_video_{int(time.time())}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"下载准备失败: {str(e)}")
        
        # 操作按钮
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 制作新视频", use_container_width=True):
                st.session_state.results = {}
                st.session_state.step = 1
                st.success("已重置，可以开始制作新视频！")
                st.rerun()
        
        with col2:
            if st.button("⚙️ 进入手动模式", use_container_width=True):
                st.session_state.step = 2
                st.info("已切换到手动模式，可以精细调整每个步骤")
                st.rerun()