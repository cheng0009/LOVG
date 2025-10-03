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
        services = {
            'llm': LLMService(),
            'comfyui': ComfyUIService(),
            'tts': TTSService(),
            'video': VideoService()
        }
        return services
    except Exception as e:
        st.error(f"服务初始化失败: {e}")
        return {}

@st.cache_data(ttl=60)
def check_service_status(services):
    """检查服务状态"""
    status = {}
    if 'llm' in services:
        status['llm'] = services['llm'].check_connection()
    else:
        status['llm'] = False
        
    if 'comfyui' in services:
        status['comfyui'] = services['comfyui'].check_connection()
    else:
        status['comfyui'] = False
        
    if 'tts' in services:
        status['tts'] = services['tts'].check_connection()
    else:
        status['tts'] = False
        
    if 'video' in services:
        status['video'] = services['video'].check_connection()
    else:
        status['video'] = False
        
    return status

# 一键生成功能
def start_one_click_generation(topic, services, status, settings):
    """一键生成完整视频"""
    if not all([status['llm'], status['comfyui']]):
        st.error("缺少必要服务，无法进行一键生成")
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
            videos = services['comfyui'].generate_videos(images, video_prompts)
            st.session_state.results['video_clips'] = videos
            
            progress_bar.progress(75)
            status_text.text("✅ 视频片段生成完成")
            
            # 步骤 4: 生成配音
            status_text.text("🎵 步骤 4/6: 正在生成配音...")
            progress_bar.progress(85)
            
            audio_script = st.session_state.results['scripts'].get('audio_script', '')
            if status['tts'] and audio_script:
                audio_file = services['tts'].generate_audio(audio_script)
                st.session_state.results['audio_file'] = audio_file
            
            progress_bar.progress(90)
            status_text.text("✅ 配音生成完成")
            
            # 步骤 5: 合成最终视频
            status_text.text("🎆 步骤 5/6: 正在合成最终视频...")
            progress_bar.progress(95)
            
            if status['video']:
                final_video = services['video'].merge_video_clips(videos)
                if 'audio_file' in st.session_state.results:
                    final_video = services['video'].add_audio(final_video, st.session_state.results['audio_file'])
                st.session_state.results['final_video'] = final_video
            
            progress_bar.progress(100)
            status_text.text("🎉 视频生成完成！")
            
            # 跳转到结果展示页面
            st.session_state.step = 7
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"生成过程中发生错误: {str(e)}")

# 初始化会话状态
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'show_prompts_config' not in st.session_state:
    st.session_state.show_prompts_config = False

# 初始化服务和状态
services = initialize_services()
status = check_service_status(services)

# 主标题
st.markdown('<h1 class="main-header">🎬 AI视频生成器</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666;">从文字主题到完整视频的一站式生成工具</p>', unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.title("控制面板")
    
    # 服务状态
    st.markdown("### 服务状态")
    status_col1, status_col2 = st.columns(2)
    
    with status_col1:
        st.write("🤖 LLM:", "✅" if status.get('llm', False) else "❌")
        st.write("🎨 ComfyUI:", "✅" if status.get('comfyui', False) else "❌")
    
    with status_col2:
        st.write("🔊 TTS:", "✅" if status.get('tts', False) else "❌")
        st.write("🎬 Video:", "✅" if status.get('video', False) else "❌")
    
    st.markdown("---")
    st.markdown("### 生成步骤")
    
    steps = [
        "1. 输入主题",
        "2. 脚本生成", 
        "3. 分镜图生成",
        "4. 视频片段生成",
        "5. 音频生成",
        "6. 视频合成",
        "7. 生成结果"
    ]
    
    for i, step_name in enumerate(steps, 1):
        if st.button(step_name, key=f"step_{i}", use_container_width=True):
            st.session_state.step = i
            st.rerun()
    
    st.markdown("---")
    
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
                st.text_area("视频拍摄脚本", value=scripts.get('video_script', ''), height=300, disabled=True)
            
            with col2:
                st.subheader("🎙️ 配音脚本")
                st.text_area("配音旁白脚本", value=scripts.get('audio_script', ''), height=300, disabled=True)
            
            # 分镜图提示词
            st.subheader("🖼️ 分镜图提示词")
            prompts = scripts.get('storyboard_prompts', [])
            if isinstance(prompts, str):
                try:
                    prompts = json.loads(prompts)
                except:
                    prompts = [prompts]
            
            for i, prompt in enumerate(prompts):
                st.text_input(f"分镜图 {i+1}", value=prompt, disabled=True)
            
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
        st.write("分镜图生成功能")
        
        # 显示生成按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎨 生成分镜图", type="primary"):
                st.session_state.step = 4
                st.rerun()
        with col2:
            if st.button("⬅️ 返回上一步"):
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