#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能字幕样式服务
根据视频的宽高比自动匹配合适的字幕样式预设
"""

from typing import Dict, Optional, Tuple
from pathlib import Path
import json
from config import Config

class SmartSubtitleStyleService:
    """智能字幕样式服务"""
    
    def __init__(self):
        self.presets = Config.SMART_SUBTITLE_PRESETS
    
    def get_video_aspect_ratio(self, width: int, height: int) -> float:
        """计算视频宽高比"""
        if height == 0:
            return 1.0
        return width / height
    
    def detect_video_format(self, aspect_ratio: float) -> str:
        """根据宽高比检测视频格式类型"""
        for format_type, preset in self.presets.items():
            min_ratio, max_ratio = preset['aspect_ratio_range']
            if min_ratio <= aspect_ratio <= max_ratio:
                return format_type
        
        # 默认返回最接近的格式
        if aspect_ratio < 0.8:
            return 'portrait'
        elif aspect_ratio > 2.1:
            return 'ultrawide'
        elif aspect_ratio < 1.3:
            return 'square'
        else:
            return 'landscape'
    
    def get_smart_subtitle_style(self, width: int, height: int, 
                                custom_adjustments: Dict = None) -> Dict:
        """
        根据视频尺寸智能获取字幕样式
        
        Args:
            width: 视频宽度
            height: 视频高度
            custom_adjustments: 用户自定义调整参数
            
        Returns:
            Dict: 优化后的字幕样式配置
        """
        # 计算宽高比
        aspect_ratio = self.get_video_aspect_ratio(width, height)
        
        # 检测视频格式
        format_type = self.detect_video_format(aspect_ratio)
        
        # 获取预设样式
        preset = self.presets[format_type]
        base_style = preset['style'].copy()
        
        # 根据实际分辨率进行微调
        scale_factor = self._calculate_scale_factor(width, height, format_type)
        base_style = self._apply_scale_adjustments(base_style, scale_factor)
        
        # 应用用户自定义调整
        if custom_adjustments:
            base_style.update(custom_adjustments)
        
        # 添加检测信息
        base_style['_detection_info'] = {
            'format_type': format_type,
            'format_name': preset['name'],
            'description': preset['description'],
            'aspect_ratio': round(aspect_ratio, 2),
            'resolution': f"{width}x{height}",
            'scale_factor': round(scale_factor, 2)
        }
        
        return base_style
    
    def _calculate_scale_factor(self, width: int, height: int, format_type: str) -> float:
        """根据分辨率计算缩放因子"""
        # 定义参考分辨率
        reference_resolutions = {
            'portrait': (720, 1280),    # 9:16
            'landscape': (1920, 1080),  # 16:9
            'square': (1080, 1080),     # 1:1
            'ultrawide': (2560, 1080)   # 21:9
        }
        
        ref_width, ref_height = reference_resolutions.get(format_type, (1920, 1080))
        
        # 计算相对于参考分辨率的缩放因子
        width_scale = width / ref_width
        height_scale = height / ref_height
        
        # 使用较小的缩放因子，避免字幕过大
        scale_factor = min(width_scale, height_scale)
        
        # 限制缩放范围，避免极端情况
        return max(0.5, min(2.0, scale_factor))
    
    def _apply_scale_adjustments(self, style: Dict, scale_factor: float) -> Dict:
        """根据缩放因子调整样式参数"""
        # 需要缩放的参数列表
        scalable_params = [
            'font_scale', 'thickness', 'outline_thickness', 
            'bg_padding', 'line_height', 'bottom_margin'
        ]
        
        adjusted_style = style.copy()
        
        for param in scalable_params:
            if param in adjusted_style:
                original_value = adjusted_style[param]
                adjusted_value = original_value * scale_factor
                
                # 应用最小值限制，确保可读性
                if param == 'font_scale':
                    adjusted_value = max(1.0, adjusted_value)
                elif param in ['thickness', 'outline_thickness']:
                    adjusted_value = max(1, int(adjusted_value))
                elif param in ['bg_padding', 'line_height', 'bottom_margin']:
                    adjusted_value = max(5, int(adjusted_value))
                
                adjusted_style[param] = adjusted_value
        
        return adjusted_style
    
    def get_all_presets(self) -> Dict:
        """获取所有预设样式"""
        return {
            format_type: {
                'name': preset['name'],
                'description': preset['description'],
                'style': preset['style']
            }
            for format_type, preset in self.presets.items()
        }
    
    def preview_style_for_resolution(self, width: int, height: int) -> Dict:
        """预览指定分辨率的样式效果"""
        style = self.get_smart_subtitle_style(width, height)
        
        return {
            'detected_format': style['_detection_info']['format_name'],
            'aspect_ratio': style['_detection_info']['aspect_ratio'],
            'scale_factor': style['_detection_info']['scale_factor'],
            'font_size_preview': f"{style['font_scale']:.1f}倍",
            'position_preview': f"底部边距{style['bottom_margin']}px",
            'style_preview': {
                'font_scale': style['font_scale'],
                'text_color': style['text_color'],
                'bg_alpha': style['bg_alpha'],
                'bottom_margin': style['bottom_margin']
            }
        }
    
    def save_custom_preset(self, name: str, style: Dict, 
                          aspect_ratio_range: Tuple[float, float],
                          description: str = "") -> bool:
        """保存用户自定义预设"""
        try:
            custom_presets_file = Config.BASE_DIR / "custom_subtitle_presets.json"
            
            # 加载现有自定义预设
            if custom_presets_file.exists():
                with open(custom_presets_file, 'r', encoding='utf-8') as f:
                    custom_presets = json.load(f)
            else:
                custom_presets = {}
            
            # 添加新预设
            custom_presets[name] = {
                'name': name,
                'description': description,
                'aspect_ratio_range': aspect_ratio_range,
                'style': style
            }
            
            # 保存到文件
            with open(custom_presets_file, 'w', encoding='utf-8') as f:
                json.dump(custom_presets, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"保存自定义预设失败: {e}")
            return False
    
    def load_custom_presets(self) -> Dict:
        """加载用户自定义预设"""
        try:
            custom_presets_file = Config.BASE_DIR / "custom_subtitle_presets.json"
            if custom_presets_file.exists():
                with open(custom_presets_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载自定义预设失败: {e}")
            return {}