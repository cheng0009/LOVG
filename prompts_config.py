#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词配置文件
用户可以根据需要自定义各种提示词模板
"""

import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime

class PromptsConfig:
    """提示词配置类"""
    
    # ====================================
    # 脚本生成提示词模板
    # ====================================
    
    SCRIPT_GENERATION_PROMPT = """
请为主题"{topic}"生成一个完整的短视频内容，包含以下部分：

1. 视频拍摄脚本：包含场景描述、镜头运动、拍摄角度等详细信息
2. 配音脚本：清晰的旁白内容，语言生动有趣
3. 分镜图绘制提示词：每个场景的详细视觉描述，适合AI绘图生成
4. 图生视频提示词：描述画面中的动作、运动效果

要求：
- 视频总长度控制在{duration}秒
- 分镜图数量：{scene_count}张
- 每个分镜对应{scene_duration}秒的视频内容
- 风格要求：{style}
- 语言：{language}

请严格按照以下JSON格式返回，不要添加任何其他文字、标记或解释：
{{
    "video_script": "详细的视频拍摄脚本",
    "audio_script": "完整的配音脚本文本",
    "storyboard_prompts": ["分镜图1的绘制提示词", "分镜图2的绘制提示词", "分镜图3的绘制提示词"],
    "video_prompts": ["视频1的动作提示词", "视频2的动作提示词", "视频3的动作提示词"],
    "estimated_duration": {duration},
    "scene_count": {scene_count}
}}

重要要求：
1. 必须返回完整的有效JSON格式
2. 不要使用markdown代码块包装
3. 不要添加任何注释或说明文字
4. 确保所有引号正确匹配
5. 数组元素数量必须等于scene_count参数
6. 所有字符串值都必须用双引号包围
"""

    # ====================================
    # 图像生成优化提示词模板
    # ====================================
    
    IMAGE_OPTIMIZATION_SYSTEM_PROMPT = """你是一个专业的AI绘图提示词优化专家。
你的任务是将用户的中文描述转换为更详细、更适合AI绘图的英文提示词。

优化要求：
1. 使用专业的摄影和艺术术语
2. 包含具体的视觉细节描述
3. 添加适当的风格和质量标签
4. 确保提示词结构清晰、逻辑性强
5. 长度控制在200个英文单词以内

格式要求：
- 主体描述 + 环境背景 + 风格标签 + 质量标签
- 使用逗号分隔不同元素
- 避免使用复杂句式

示例格式：
[主体], [动作/姿态], [环境/背景], [光照], [风格], [质量标签]
"""

    IMAGE_OPTIMIZATION_USER_PROMPT = "请将以下中文描述优化为AI绘图提示词：{original_prompt}"

    # ====================================
    # 视频生成优化提示词模板
    # ====================================
    
    VIDEO_OPTIMIZATION_SYSTEM_PROMPT = """你是一个专业的AI视频生成提示词优化专家。
你的任务是将用户的描述转换为更详细的视频动作和运动描述提示词。

优化要求：
1. 明确描述画面中的运动和动作
2. 包含镜头运动描述（推拉摇移等）
3. 描述时间变化和动态效果
4. 确保动作自然流畅
5. 长度控制在150个英文单词以内

运动类型包括：
- 对象运动：人物动作、物体移动
- 镜头运动：zoom in/out, pan left/right, tilt up/down, dolly, tracking
- 环境变化：光影变化、天气变化、时间变化
- 特效：粒子效果、过渡效果

示例格式：
[主体动作], [镜头运动], [环境变化], [时间节奏], [视觉效果]
"""

    VIDEO_OPTIMIZATION_USER_PROMPT = "请将以下描述优化为视频生成提示词：{original_prompt}"

    # ====================================
    # 风格化提示词模板
    # ====================================
    
    STYLE_TEMPLATES = {
        "现代简约": {
            "image_suffix": "modern minimalist style, clean composition, simple geometry, white background, soft lighting, professional photography",
            "video_suffix": "smooth camera movement, gentle transitions, modern aesthetic, clean visuals"
        },
        "科技感": {
            "image_suffix": "futuristic, high-tech, digital art, neon lights, metallic surfaces, sci-fi aesthetic, 4k digital art",
            "video_suffix": "dynamic camera movement, digital effects, glowing elements, tech atmosphere"
        },
        "温馨": {
            "image_suffix": "warm lighting, cozy atmosphere, soft colors, comfortable setting, natural light, lifestyle photography",
            "video_suffix": "gentle camera movement, warm atmosphere, natural transitions, comfortable pace"
        },
        "商务": {
            "image_suffix": "professional, business environment, corporate style, formal lighting, office setting, commercial photography",
            "video_suffix": "steady camera work, professional presentation, business atmosphere, confident movement"
        },
        "艺术": {
            "image_suffix": "artistic, creative composition, painterly style, dramatic lighting, fine art, expressive, masterpiece",
            "video_suffix": "creative camera angles, artistic movement, expressive visuals, dramatic effects"
        }
    }

    # ====================================
    # 质量标签
    # ====================================
    
    QUALITY_TAGS = {
        "图像": "high quality, detailed, sharp focus, professional, 8k resolution, award winning",
        "视频": "high quality video, smooth motion, professional cinematography, 4k, detailed"
    }

    # ====================================
    # 默认参数
    # ====================================
    
    DEFAULT_SETTINGS = {
        "duration": 60,      # 默认视频时长（秒）
        "scene_count": 5,    # 默认分镜数量
        "style": "现代简约",   # 默认风格
        "language": "中文"    # 默认语言
    }

    # ====================================
    # 提示词生成方法
    # ====================================
    
    @classmethod
    def get_script_generation_prompt(cls, topic, settings=None):
        """生成脚本生成提示词"""
        if settings is None:
            settings = cls.DEFAULT_SETTINGS.copy()
        
        # 计算每个场景的时长
        scene_duration = settings['duration'] // settings['scene_count']
        
        return cls.SCRIPT_GENERATION_PROMPT.format(
            topic=topic,
            duration=settings.get('duration', 60),
            scene_count=settings.get('scene_count', 5),
            scene_duration=scene_duration,
            style=settings.get('style', '现代简约'),
            language=settings.get('language', '中文')
        )
    
    @classmethod
    def get_image_optimization_prompts(cls, original_prompt):
        """获取图像优化提示词"""
        return {
            'system': cls.IMAGE_OPTIMIZATION_SYSTEM_PROMPT,
            'user': cls.IMAGE_OPTIMIZATION_USER_PROMPT.format(original_prompt=original_prompt)
        }
    
    @classmethod
    def get_video_optimization_prompts(cls, original_prompt):
        """获取视频优化提示词"""
        return {
            'system': cls.VIDEO_OPTIMIZATION_SYSTEM_PROMPT,
            'user': cls.VIDEO_OPTIMIZATION_USER_PROMPT.format(original_prompt=original_prompt)
        }
    
    @classmethod
    def apply_style_to_prompt(cls, prompt, style, prompt_type="image"):
        """为提示词应用风格"""
        if style in cls.STYLE_TEMPLATES:
            style_config = cls.STYLE_TEMPLATES[style]
            if prompt_type == "image":
                suffix = style_config.get("image_suffix", "")
            else:
                suffix = style_config.get("video_suffix", "")
            
            if suffix:
                return f"{prompt}, {suffix}"
        
        return prompt
    
    @classmethod
    def add_quality_tags(cls, prompt, prompt_type="图像"):
        """添加质量标签"""
        quality_tags = cls.QUALITY_TAGS.get(prompt_type, "")
        if quality_tags:
            return f"{prompt}, {quality_tags}"
        return prompt

    # ====================================
    # 用户自定义配置支持
    # ====================================
    
    @classmethod
    def load_user_config(cls, config_file=None):
        """加载用户自定义配置"""
        if config_file and os.path.exists(config_file):
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # 更新配置
                for key, value in user_config.items():
                    if hasattr(cls, key):
                        setattr(cls, key, value)
                        
                print(f"✅ 已加载用户配置: {config_file}")
            except Exception as e:
                print(f"⚠️ 加载用户配置失败: {e}")
    
    @classmethod
    def save_user_config(cls, config_file="user_prompts_config.json"):
        """保存用户自定义配置"""
        try:
            import json
            
            config_data = {
                "SCRIPT_GENERATION_PROMPT": cls.SCRIPT_GENERATION_PROMPT,
                "IMAGE_OPTIMIZATION_SYSTEM_PROMPT": cls.IMAGE_OPTIMIZATION_SYSTEM_PROMPT,
                "VIDEO_OPTIMIZATION_SYSTEM_PROMPT": cls.VIDEO_OPTIMIZATION_SYSTEM_PROMPT,
                "STYLE_TEMPLATES": cls.STYLE_TEMPLATES,
                "QUALITY_TAGS": cls.QUALITY_TAGS,
                "DEFAULT_SETTINGS": cls.DEFAULT_SETTINGS
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 配置已保存到: {config_file}")
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")


# 导入检查
if __name__ == "__main__":
    import os
    
    # 演示用法
    print("🔧 提示词配置演示")
    print("=" * 50)
    
    # 生成脚本提示词
    settings = {"duration": 90, "scene_count": 6, "style": "科技感", "language": "中文"}
    script_prompt = PromptsConfig.get_script_generation_prompt("人工智能的发展", settings)
    print("📝 脚本生成提示词:")
    print(script_prompt[:200] + "...")
    
    # 图像优化提示词
    image_prompts = PromptsConfig.get_image_optimization_prompts("一个未来城市的场景")
    print(f"\n🎨 图像优化系统提示词: {image_prompts['system'][:100]}...")
    
    # 应用风格
    styled_prompt = PromptsConfig.apply_style_to_prompt("beautiful landscape", "艺术", "image")
    print(f"\n🎭 应用风格后: {styled_prompt}")
    
    # 保存配置示例
    # PromptsConfig.save_user_config("example_config.json")


# ====================================
# Streamlit 界面渲染函数
# ====================================

def render_prompts_config():
    """渲染提示词配置界面"""
    st.markdown('<h2 class="step-header">🔧 提示词模板编辑</h2>', unsafe_allow_html=True)
    
    st.info("""
    📝 **功能说明**：
    - 📝 编辑脚本生成提示词模板
    - 🎨 编辑图像优化系统提示词
    - 🎥 编辑视频优化系统提示词
    - 💾 保存修改并立即生效
    """)
    
    # 创建选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📝 脚本生成", "🎨 图像优化", "🎥 视频优化", "💾 配置管理"])
    
    with tab1:
        st.subheader("📝 脚本生成提示词模板")
        st.markdown("""
        **用途**：用于生成视频脚本、配音脚本和分镜图提示词
        
        **可用变量**：
        - `{topic}`: 视频主题
        - `{duration}`: 视频时长
        - `{scene_count}`: 分镜数量
        - `{scene_duration}`: 每个场景时长
        - `{style}`: 视频风格
        - `{language}`: 语言
        """)
        
        # 编辑区域
        new_script_prompt = st.text_area(
            "编辑脚本生成提示词",
            value=PromptsConfig.SCRIPT_GENERATION_PROMPT,
            height=400,
            help="请保留花括号中的变量名称，如 {topic}, {duration} 等"
        )
        
        if st.button("💾 保存脚本生成模板", type="primary"):
            PromptsConfig.SCRIPT_GENERATION_PROMPT = new_script_prompt
            st.success("✅ 脚本生成模板已保存！")
            st.rerun()
    
    with tab2:
        st.subheader("🎨 图像优化系统提示词")
        st.markdown("""
        **用途**：用于AI绘图的系统提示词，指导如何优化中文描述为英文提示词
        
        **功能**：
        - 使用专业摄影术语
        - 添加视觉细节描述
        - 包含风格和质量标签
        """)
        
        new_image_prompt = st.text_area(
            "编辑图像优化系统提示词",
            value=PromptsConfig.IMAGE_OPTIMIZATION_SYSTEM_PROMPT,
            height=300
        )
        
        if st.button("💾 保存图像优化模板", type="primary"):
            PromptsConfig.IMAGE_OPTIMIZATION_SYSTEM_PROMPT = new_image_prompt
            st.success("✅ 图像优化模板已保存！")
            st.rerun()
    
    with tab3:
        st.subheader("🎥 视频优化系统提示词")
        st.markdown("""
        **用途**：用于视频生成的系统提示词，指导如何描述动作和运动效果
        
        **包含**：
        - 对象运动描述
        - 镜头运动指导
        - 环境变化效果
        - 时间节奏控制
        """)
        
        new_video_prompt = st.text_area(
            "编辑视频优化系统提示词",
            value=PromptsConfig.VIDEO_OPTIMIZATION_SYSTEM_PROMPT,
            height=300
        )
        
        if st.button("💾 保存视频优化模板", type="primary"):
            PromptsConfig.VIDEO_OPTIMIZATION_SYSTEM_PROMPT = new_video_prompt
            st.success("✅ 视频优化模板已保存！")
            st.rerun()
    
    with tab4:
        st.subheader("💾 配置文件管理")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📤 导出配置")
            if st.button("💾 导出当前配置", use_container_width=True):
                try:
                    config_data = {
                        "SCRIPT_GENERATION_PROMPT": PromptsConfig.SCRIPT_GENERATION_PROMPT,
                        "IMAGE_OPTIMIZATION_SYSTEM_PROMPT": PromptsConfig.IMAGE_OPTIMIZATION_SYSTEM_PROMPT,
                        "VIDEO_OPTIMIZATION_SYSTEM_PROMPT": PromptsConfig.VIDEO_OPTIMIZATION_SYSTEM_PROMPT,
                        "STYLE_TEMPLATES": PromptsConfig.STYLE_TEMPLATES,
                        "QUALITY_TAGS": PromptsConfig.QUALITY_TAGS,
                        "DEFAULT_SETTINGS": PromptsConfig.DEFAULT_SETTINGS
                    }
                    
                    config_json = json.dumps(config_data, ensure_ascii=False, indent=2)
                    
                    st.download_button(
                        label="💾 下载配置文件",
                        data=config_json,
                        file_name=f"prompts_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                    
                    st.success("✅ 配置已准备好，点击下载按钮保存！")
                except Exception as e:
                    st.error(f"❌ 导出失败: {str(e)}")
        
        with col2:
            st.markdown("### 📥 导入配置")
            uploaded_file = st.file_uploader(
                "选择配置文件",
                type=['json'],
                help="上传JSON格式的提示词配置文件"
            )
            
            if uploaded_file is not None:
                try:
                    config_data = json.load(uploaded_file)
                    
                    # 显示配置预览
                    st.markdown("**配置预览**")
                    config_keys = list(config_data.keys())
                    st.write(f"包含 {len(config_keys)} 个配置项: {', '.join(config_keys)}")
                    
                    if st.button("🚀 应用配置", type="primary", use_container_width=True):
                        # 应用配置
                        for key, value in config_data.items():
                            if hasattr(PromptsConfig, key):
                                setattr(PromptsConfig, key, value)
                        
                        st.success("✅ 配置已成功应用！")
                        st.rerun()
                        
                except json.JSONDecodeError:
                    st.error("❌ 无效的JSON文件格式")
                except Exception as e:
                    st.error(f"❌ 导入失败: {str(e)}")
        
        # 重置配置
        st.markdown("---")
        st.markdown("### 🔄 重置配置")
        if st.button("⚠️ 重置为默认配置", use_container_width=True):
            if st.button("确认重置（不可恢复）", type="secondary"):
                # 这里应该重新加载默认配置
                st.warning("重置功能待实现")
    
    # 返回主页按钮
    st.markdown("---")
    if st.button("⬅️ 返回主页", use_container_width=True):
        st.session_state.show_prompts_config = False
        st.rerun()