#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词编辑器 - 用户可视化编辑提示词配置
"""

import streamlit as st
import json
import os
from prompts_config import PromptsConfig

def main():
    """主界面"""
    st.set_page_config(
        page_title="提示词配置编辑器",
        page_icon="✏️",
        layout="wide"
    )
    
    st.title("✏️ 提示词配置编辑器")
    st.markdown("---")
    
    # 侧边栏
    with st.sidebar:
        st.header("配置管理")
        
        # 加载配置
        uploaded_file = st.file_uploader("上传配置文件", type=['json'])
        if uploaded_file:
            try:
                config_data = json.load(uploaded_file)
                st.success("配置文件加载成功！")
                # 这里可以加载配置到PromptsConfig
            except Exception as e:
                st.error(f"加载失败: {e}")
        
        st.markdown("---")
        
        # 保存配置
        if st.button("💾 保存当前配置"):
            PromptsConfig.save_user_config("user_prompts_config.json")
            st.success("配置已保存！")
        
        # 重置配置
        if st.button("🔄 重置为默认"):
            st.warning("功能开发中...")
    
    # 主内容区
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 脚本生成", "🎨 图像优化", "🎥 视频优化", "🎭 风格配置", "⚙️ 默认设置"
    ])
    
    with tab1:
        edit_script_generation_prompt()
    
    with tab2:
        edit_image_optimization_prompts()
    
    with tab3:
        edit_video_optimization_prompts()
    
    with tab4:
        edit_style_templates()
    
    with tab5:
        edit_default_settings()

def edit_script_generation_prompt():
    """编辑脚本生成提示词"""
    st.subheader("📝 脚本生成提示词模板")
    st.markdown("这个模板用于生成视频脚本、配音文本和各种提示词")
    
    # 显示当前模板
    current_prompt = st.text_area(
        "当前模板",
        value=PromptsConfig.SCRIPT_GENERATION_PROMPT,
        height=400,
        help="支持的变量: {topic}, {duration}, {scene_count}, {scene_duration}, {style}, {language}"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 保存修改", type="primary"):
            PromptsConfig.SCRIPT_GENERATION_PROMPT = current_prompt
            st.success("脚本生成模板已更新！")
    
    with col2:
        if st.button("🧪 测试模板"):
            test_settings = {
                'duration': 60,
                'scene_count': 5,
                'style': '现代简约',
                'language': '中文'
            }
            test_prompt = PromptsConfig.get_script_generation_prompt("测试主题", test_settings)
            st.text_area("测试结果", value=test_prompt, height=200)

def edit_image_optimization_prompts():
    """编辑图像优化提示词"""
    st.subheader("🎨 图像优化提示词模板")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**系统提示词**")
        system_prompt = st.text_area(
            "系统提示词",
            value=PromptsConfig.IMAGE_OPTIMIZATION_SYSTEM_PROMPT,
            height=300,
            key="img_system"
        )
    
    with col2:
        st.markdown("**用户提示词**")
        user_prompt = st.text_area(
            "用户提示词模板",
            value=PromptsConfig.IMAGE_OPTIMIZATION_USER_PROMPT,
            height=300,
            key="img_user",
            help="支持变量: {original_prompt}"
        )
    
    if st.button("💾 保存图像优化模板"):
        PromptsConfig.IMAGE_OPTIMIZATION_SYSTEM_PROMPT = system_prompt
        PromptsConfig.IMAGE_OPTIMIZATION_USER_PROMPT = user_prompt
        st.success("图像优化模板已更新！")

def edit_video_optimization_prompts():
    """编辑视频优化提示词"""
    st.subheader("🎥 视频优化提示词模板")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**系统提示词**")
        system_prompt = st.text_area(
            "系统提示词",
            value=PromptsConfig.VIDEO_OPTIMIZATION_SYSTEM_PROMPT,
            height=300,
            key="video_system"
        )
    
    with col2:
        st.markdown("**用户提示词**")
        user_prompt = st.text_area(
            "用户提示词模板",
            value=PromptsConfig.VIDEO_OPTIMIZATION_USER_PROMPT,
            height=300,
            key="video_user",
            help="支持变量: {original_prompt}"
        )
    
    if st.button("💾 保存视频优化模板"):
        PromptsConfig.VIDEO_OPTIMIZATION_SYSTEM_PROMPT = system_prompt
        PromptsConfig.VIDEO_OPTIMIZATION_USER_PROMPT = user_prompt
        st.success("视频优化模板已更新！")

def edit_style_templates():
    """编辑风格模板"""
    st.subheader("🎭 风格模板配置")
    
    # 显示现有风格
    st.markdown("### 现有风格")
    for style_name, style_config in PromptsConfig.STYLE_TEMPLATES.items():
        with st.expander(f"🎨 {style_name}"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_image_suffix = st.text_area(
                    "图像风格后缀",
                    value=style_config.get("image_suffix", ""),
                    key=f"img_suffix_{style_name}",
                    height=100
                )
            
            with col2:
                new_video_suffix = st.text_area(
                    "视频风格后缀",
                    value=style_config.get("video_suffix", ""),
                    key=f"video_suffix_{style_name}",
                    height=100
                )
            
            col3, col4 = st.columns(2)
            with col3:
                if st.button(f"💾 保存 {style_name}", key=f"save_{style_name}"):
                    PromptsConfig.STYLE_TEMPLATES[style_name] = {
                        "image_suffix": new_image_suffix,
                        "video_suffix": new_video_suffix
                    }
                    st.success(f"风格 {style_name} 已更新！")
            
            with col4:
                if st.button(f"🗑️ 删除 {style_name}", key=f"delete_{style_name}"):
                    if len(PromptsConfig.STYLE_TEMPLATES) > 1:
                        del PromptsConfig.STYLE_TEMPLATES[style_name]
                        st.success(f"风格 {style_name} 已删除！")
                        st.rerun()
                    else:
                        st.error("至少要保留一个风格！")
    
    # 添加新风格
    st.markdown("### 添加新风格")
    with st.expander("➕ 添加新风格"):
        new_style_name = st.text_input("风格名称")
        col1, col2 = st.columns(2)
        
        with col1:
            new_style_image = st.text_area("图像风格后缀", height=100, key="new_image")
        
        with col2:
            new_style_video = st.text_area("视频风格后缀", height=100, key="new_video")
        
        if st.button("➕ 添加风格"):
            if new_style_name and new_style_name not in PromptsConfig.STYLE_TEMPLATES:
                PromptsConfig.STYLE_TEMPLATES[new_style_name] = {
                    "image_suffix": new_style_image,
                    "video_suffix": new_style_video
                }
                st.success(f"风格 {new_style_name} 已添加！")
                st.rerun()
            else:
                st.error("风格名称不能为空或已存在！")

def edit_default_settings():
    """编辑默认设置"""
    st.subheader("⚙️ 默认设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        duration = st.number_input(
            "默认视频时长（秒）",
            min_value=10,
            max_value=300,
            value=PromptsConfig.DEFAULT_SETTINGS.get('duration', 60)
        )
        
        scene_count = st.number_input(
            "默认分镜数量",
            min_value=2,
            max_value=10,
            value=PromptsConfig.DEFAULT_SETTINGS.get('scene_count', 5)
        )
    
    with col2:
        style = st.selectbox(
            "默认风格",
            options=list(PromptsConfig.STYLE_TEMPLATES.keys()),
            index=list(PromptsConfig.STYLE_TEMPLATES.keys()).index(
                PromptsConfig.DEFAULT_SETTINGS.get('style', '现代简约')
            ) if PromptsConfig.DEFAULT_SETTINGS.get('style', '现代简约') in PromptsConfig.STYLE_TEMPLATES else 0
        )
        
        language = st.selectbox(
            "默认语言",
            options=['中文', '英文'],
            index=0 if PromptsConfig.DEFAULT_SETTINGS.get('language', '中文') == '中文' else 1
        )
    
    if st.button("💾 保存默认设置"):
        PromptsConfig.DEFAULT_SETTINGS = {
            'duration': duration,
            'scene_count': scene_count,
            'style': style,
            'language': language
        }
        st.success("默认设置已更新！")
    
    # 质量标签配置
    st.markdown("### 质量标签配置")
    col1, col2 = st.columns(2)
    
    with col1:
        image_quality = st.text_area(
            "图像质量标签",
            value=PromptsConfig.QUALITY_TAGS.get('图像', ''),
            height=100
        )
    
    with col2:
        video_quality = st.text_area(
            "视频质量标签",
            value=PromptsConfig.QUALITY_TAGS.get('视频', ''),
            height=100
        )
    
    if st.button("💾 保存质量标签"):
        PromptsConfig.QUALITY_TAGS['图像'] = image_quality
        PromptsConfig.QUALITY_TAGS['视频'] = video_quality
        st.success("质量标签已更新！")

if __name__ == "__main__":
    main()