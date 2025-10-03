import requests
try:
    import websocket
except ImportError:
    print("Warning: websocket-client not installed. Some features may not work.")
    websocket = None
import json
import uuid
import time
import threading
from typing import List, Dict, Optional
from pathlib import Path
import base64
from config import Config
import gc

# 尝试导入psutil，如果失败则设置为None
try:
    import psutil
except ImportError:
    psutil = None
    print("Warning: psutil not installed. System resource monitoring will be disabled.")


class ComfyUIService:
    def __init__(self):
        self.host = Config.COMFYUI_HOST
        self.port = Config.COMFYUI_PORT

        self.base_url = Config.COMFYUI_URL
        self.client_id = str(uuid.uuid4())
        
    def _check_system_resources(self):
        """检查系统资源使用情况并优化"""
        # 如果psutil不可用，跳过资源检查
        if psutil is None:
            print("⚠️ 系统资源监控不可用 (缺少psutil模块)")
            return None
            
        try:
            # 获取内存信息
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            available_memory_gb = memory.available / (1024**3)
            
            # 获取CPU信息
            cpu_percent = psutil.cpu_percent(interval=1)
            
            print(f"📊 系统资源使用情况:")
            print(f"  CPU使用率: {cpu_percent:.1f}%")
            print(f"  内存使用率: {memory_percent:.1f}%")
            print(f"  可用内存: {available_memory_gb:.2f}GB")
            
            # 如果内存使用率过高，触发垃圾回收
            if memory_percent > 85:  # 降低阈值到85%
                print("⚠️ 内存使用率较高，触发垃圾回收...")
                gc.collect()
                time.sleep(2)  # 等待回收完成
                
                # 重新检查内存
                memory = psutil.virtual_memory()
                print(f"  回收后内存使用率: {memory.percent:.1f}%")
                
            # 如果内存使用率过高，给出警告
            if memory_percent > 90:
                print("🚨 内存使用率过高，建议重启ComfyUI服务!")
                
                # 尝试优化：强制释放更多资源
                if memory_percent > 95:
                    print("⚠️ 内存使用率极高，执行紧急优化措施...")
                    # 清理Python垃圾
                    gc.collect()
                    gc.collect()  # 双重垃圾回收
                    
                    # 清理系统缓存（如果可能）
                    try:
                        import os
                        if hasattr(os, 'system') and os.name == 'nt':  # Windows
                            # Windows清理内存命令
                            os.system('echo 1 > nul')  # 空操作，但可能触发一些清理
                    except:
                        pass
                    
                    # 使用增强的资源优化器
                    try:
                        from .resource_optimizer import resource_optimizer
                        resource_optimizer.force_cleanup()
                    except ImportError:
                        print("⚠️ 资源优化器不可用")
                
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'available_memory_gb': available_memory_gb
            }
        except Exception as e:
            print(f"⚠️ 无法获取系统资源信息: {e}")
            return None
    
    def check_connection(self) -> bool:
        """检查ComfyUI服务连接"""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if response.status_code == 200:
                # 尝试获取ComfyUI的系统信息
                try:
                    stats = response.json()
                    print(f"ComfyUI系统信息: {stats}")
                except:
                    pass
                
                # 尝试获取ComfyUI的输入目录信息
                try:
                    info_response = requests.get(f"{self.base_url}/object_info", timeout=5)
                    if info_response.status_code == 200:
                        object_info = info_response.json()
                        # 查找LoadImage节点的信息
                        if "LoadImage" in object_info:
                            load_image_info = object_info["LoadImage"]
                            print(f"LoadImage节点信息: {load_image_info}")
                except Exception as e:
                    print(f"获取对象信息失败: {str(e)}")
                
                return True
            return False
        except Exception as e:
            print(f"ComfyUI连接检查失败: {str(e)}")
            # 如果连接失败，尝试重启服务或等待恢复
            return False

    def load_workflow(self, workflow_path: Path) -> Dict:
        """加载工作流文件"""
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            # 检查是否是ComfyUI项目文件格式（包含'nodes'字段）
            if 'nodes' in workflow_data:
                print(f"检测到ComfyUI项目文件格式，转换为标准工作流格式")
                return self._convert_project_to_workflow(workflow_data)
            else:
                # 已经是标准工作流格式
                return workflow_data
                
        except Exception as e:
            raise Exception(f"加载工作流失败: {str(e)}")
    
    def _convert_project_to_workflow(self, project_data: Dict) -> Dict:
        """将ComfyUI项目文件转换为标准工作流格式"""
        workflow = {}
        
        nodes = project_data.get('nodes', [])
        
        for node in nodes:
            node_id = str(node.get('id', ''))
            if not node_id:
                continue
                
            # 获取节点类型
            node_type = node.get('type', '')
            if not node_type:
                continue
            
            # 获取输入参数
            inputs = {}
            
            # 从 widgets_values获取值
            widget_values = node.get('widgets_values', [])
            node_inputs = node.get('inputs', [])
            
            # 根据节点类型设置默认参数
            if node_type == "LoadImage":
                if len(widget_values) > 0:
                    inputs["image"] = widget_values[0]
            elif node_type == "CLIPTextEncode":
                if len(widget_values) > 0:
                    inputs["text"] = widget_values[0]
            elif node_type == "CheckpointLoaderSimple":
                if len(widget_values) > 0:
                    inputs["ckpt_name"] = widget_values[0]
            elif node_type == "VAELoader":
                if len(widget_values) > 0:
                    inputs["vae_name"] = widget_values[0]
            elif node_type == "CLIPVisionLoader":
                if len(widget_values) > 0:
                    inputs["clip_name"] = widget_values[0]
            elif node_type == "KSampler":
                if len(widget_values) >= 6:
                    inputs.update({
                        "seed": widget_values[0],
                        "control_after_generate": widget_values[1],
                        "steps": widget_values[2],
                        "cfg": widget_values[3],
                        "sampler_name": widget_values[4],
                        "scheduler": widget_values[5],
                        "denoise": widget_values[6] if len(widget_values) > 6 else 1.0
                    })
            elif node_type == "WanImageToVideo":
                if len(widget_values) >= 4:
                    inputs.update({
                        "width": widget_values[0],
                        "height": widget_values[1],
                        "length": widget_values[2],
                        "batch_size": widget_values[3]
                    })
            elif node_type == "VHS_VideoCombine":
                if len(widget_values) > 0 and isinstance(widget_values[0], dict):
                    video_params = widget_values[0]
                    inputs.update({
                        "frame_rate": video_params.get("frame_rate", 18),
                        "loop_count": video_params.get("loop_count", 0),
                        "filename_prefix": video_params.get("filename_prefix", "video"),
                        "format": video_params.get("format", "video/h264-mp4"),
                        "save_output": video_params.get("save_output", True)
                    })
            
            # 处理连接关系
            for input_def in node_inputs:
                input_name = input_def.get('name', '')
                input_link = input_def.get('link')
                if input_link is not None:
                    # 查找链接的源节点
                    source_info = self._find_link_source(project_data.get('links', []), input_link)
                    if source_info:
                        inputs[input_name] = source_info
            
            workflow[node_id] = {
                "class_type": node_type,
                "inputs": inputs
            }
            
            # 添加标题信息
            if 'title' in node:
                workflow[node_id]["_meta"] = {"title": node['title']}
        
        return workflow
    
    def _find_link_source(self, links: list, link_id: int) -> list:
        """查找链接的源节点"""
        for link in links:
            if len(link) >= 3 and link[0] == link_id:
                # link 格式: [link_id, source_node_id, source_slot, target_node_id, target_slot, type]
                return [str(link[1]), link[2]]  # [source_node_id, source_slot]
        return None
    
    def _create_placeholder_image(self, image_path: Path, text: str):
        """创建占位符图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 创建一个简单的占位符图片
            width, height = 512, 512
            image = Image.new('RGB', (width, height), color='lightgray')
            draw = ImageDraw.Draw(image)
            
            # 尝试使用默认字体
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                font = ImageFont.load_default()
            
            # 计算文本位置
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            # 绘制文本
            draw.text((x, y), text, fill='black', font=font)
            
            # 确保目录存在
            image_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存图片
            image.save(image_path, 'JPEG')
            print(f"✅ 创建占位符图片: {image_path}")
            
        except ImportError:
            print(f"⚠️ PIL库未安装，使用简单占位符")
            self._create_simple_placeholder(image_path, text)
        except Exception as e:
            print(f"⚠️ 创建占位符图片失败: {str(e)}")
            self._create_simple_placeholder(image_path, text)
    
    def _create_simple_placeholder(self, image_path: Path, text: str):
        """创建简单的文本占位符文件"""
        try:
            # 确保目录存在
            image_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建一个简单的文本文件作为占位符
            placeholder_text = f"占位符图片: {text}\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 修改扩展名为.txt
            txt_path = image_path.with_suffix('.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(placeholder_text)
            
            print(f"✅ 创建简单占位符: {txt_path}")
            
        except Exception as e:
            print(f"❌ 创建占位符失败: {str(e)}")

    def generate_single_image(self, prompt: str, filename: str = None, max_retries: int = 3) -> Optional[str]:
        """生成单张图片 - 带重试机制，专用于编辑提示词重新生成"""
        if not filename:
            import time
            timestamp = int(time.time() * 1000)
            filename = f"single_{timestamp:03d}"
        
        print(f"🎨 生成单张图片...")
        print(f"📁 使用工作流: {Config.IMAGE_WORKFLOW}")
        print(f"📝 提示词: {prompt}")
        print(f"🔄 最大重试次数: {max_retries}")
        
        last_error = None
        
        # 重试机制
        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    print(f"🔄 第{retry}次重试 (共{max_retries}次)...")
                    import time
                    time.sleep(2 * retry)  # 逐渐增加等待时间
                
                # 检查ComfyUI连接状态
                if not self.check_connection():
                    raise Exception("ComfyUI服务连接失败，请检查服务是否正常运行")
                
                # 加载图像生成工作流
                print(f"📥 加载工作流: {Config.IMAGE_WORKFLOW}")
                workflow = self.load_workflow(Config.IMAGE_WORKFLOW)
                
                # 修改工作流中的提示词
                print(f"✏️ 更新提示词...")
                workflow = self._update_image_workflow(workflow, prompt)
                
                # 执行工作流
                print(f"⚙️ 执行工作流...")
                image_path = self._execute_workflow(workflow, filename)
                
                if image_path and Path(image_path).exists():
                    # 验证生成的图片
                    file_size = Path(image_path).stat().st_size
                    if file_size > 1024:  # 大于1KB
                        print(f"✅ 单张图片生成成功: {Path(image_path).name}")
                        print(f"📊 文件大小: {file_size/1024:.1f}KB")
                        return image_path
                    else:
                        raise Exception(f"生成的图片文件太小({file_size}字节)，可能生成失败")
                else:
                    raise Exception("工作流执行未返回有效结果或文件不存在")
                    
            except Exception as e:
                last_error = str(e)
                error_detail = f"单张图片生成失败 (尝试{retry+1}/{max_retries+1}): {last_error}"
                print(f"❌ {error_detail}")
                
                # 如果不是最后一次尝试，显示重试信息
                if retry < max_retries:
                    print(f"🔄 准备重试...")
                    # 详细的错误诊断
                    self._diagnose_single_image_error(last_error)
                else:
                    print(f"💥 已达到最大重试次数，放弃生成")
        
        # 如果所有重试都失败了
        detailed_error = f"""单张图片生成完全失败！

🔍 错误详情:
• 提示词: {prompt}
• 最后错误: {last_error}
• 重试次数: {max_retries}

💡 可能的解决方案:
1. 检查ComfyUI服务是否正常运行
2. 确认工作流文件是否存在且有效
3. 检查GPU内存是否充足
4. 尝试简化提示词内容
5. 重启ComfyUI服务

❌ 无法生成有效图片，请根据以上建议排查问题。"""
        
        print(f"\n{'='*60}")
        print(detailed_error)
        print(f"{'='*60}\n")
        
        # 抛出详细的异常信息
        raise Exception(detailed_error)

    def generate_images(self, prompts: List[str], max_retries: int = 3) -> List[str]:
        """生成分镜图片 - 带重试机制，失败时提供详细错误信息"""
        image_paths = []
        
        print(f"🎨 开始生成 {len(prompts)} 张分镜图...")
        print(f"📁 使用工作流: {Config.IMAGE_WORKFLOW}")
        print(f"🔄 最大重试次数: {max_retries}")
        
        for i, prompt in enumerate(prompts):
            print(f"\n=== 生成第{i+1}张分镜图 ===")
            print(f"📝 提示词: {prompt}")
            
            success = False
            last_error = None
            
            # 重试机制
            for retry in range(max_retries + 1):
                try:
                    if retry > 0:
                        print(f"🔄 第{retry}次重试 (共{max_retries}次)...")
                        import time
                        time.sleep(2 * retry)  # 逐渐增加等待时间
                    
                    # 检查ComfyUI连接状态
                    if not self.check_connection():
                        raise Exception("ComfyUI服务连接失败，请检查服务是否正常运行")
                    
                    # 加载图像生成工作流
                    print(f"📥 加载工作流: {Config.IMAGE_WORKFLOW}")
                    workflow = self.load_workflow(Config.IMAGE_WORKFLOW)
                    
                    # 修改工作流中的提示词
                    print(f"✏️ 更新提示词...")
                    workflow = self._update_image_workflow(workflow, prompt)
                    
                    # 执行工作流
                    print(f"⚙️ 执行工作流...")
                    image_path = self._execute_workflow(workflow, f"storyboard_{i+1:03d}")
                    
                    if image_path and Path(image_path).exists():
                        # 验证生成的图片
                        file_size = Path(image_path).stat().st_size
                        if file_size > 1024:  # 大于1KB
                            image_paths.append(image_path)
                            print(f"✅ 第{i+1}张分镜图生成成功: {Path(image_path).name}")
                            print(f"📊 文件大小: {file_size/1024:.1f}KB")
                            success = True
                            break
                        else:
                            raise Exception(f"生成的图片文件太小({file_size}字节)，可能生成失败")
                    else:
                        raise Exception("工作流执行未返回有效结果或文件不存在")
                        
                except Exception as e:
                    last_error = str(e)
                    error_detail = f"第{i+1}张分镜图生成失败 (尝试{retry+1}/{max_retries+1}): {last_error}"
                    print(f"❌ {error_detail}")
                    
                    # 如果不是最后一次尝试，显示重试信息
                    if retry < max_retries:
                        print(f"🔄 准备重试...")
                        # 详细的错误诊断
                        self._diagnose_generation_error(last_error, i+1)
                    else:
                        print(f"💥 已达到最大重试次数，放弃生成第{i+1}张分镜图")
            
            # 如果所有重试都失败了
            if not success:
                detailed_error = f"""第{i+1}张分镜图生成完全失败！

🔍 错误详情:
• 提示词: {prompt}
• 最后错误: {last_error}
• 重试次数: {max_retries}

💡 可能的解决方案:
1. 检查ComfyUI服务是否正常运行
2. 确认工作流文件是否存在且有效
3. 检查GPU内存是否充足
4. 尝试简化提示词内容
5. 重启ComfyUI服务

❌ 由于无法生成有效的分镜图，流程将终止。"""
                
                print(f"\n{'='*60}")
                print(detailed_error)
                print(f"{'='*60}\n")
                
                # 抛出详细的异常信息
                raise Exception(detailed_error)
        
        print(f"\n🎉 所有分镜图生成完成! 共{len(image_paths)}张")
        return image_paths
    
    def _diagnose_single_image_error(self, error_msg: str):
        """诊断单张图片生成错误并提供建议"""
        print(f"\n🔍 单张图片错误诊断:")
        
        error_lower = error_msg.lower()
        
        if "connection" in error_lower or "timeout" in error_lower:
            print("🌐 网络连接问题:")
            print("  • ComfyUI服务可能未运行或不可达")
            print("  • 建议: 检查ComfyUI是否在127.0.0.1:8188运行")
            
        elif "memory" in error_lower or "out of memory" in error_lower:
            print("💾 内存不足问题:")
            print("  • GPU显存可能不足")
            print("  • 建议: 关闭其他占用GPU的程序，或降低图片分辨率")
            
        elif "workflow" in error_lower or "node" in error_lower:
            print("⚙️ 工作流问题:")
            print("  • 工作流文件可能损坏或节点缺失")
            print("  • 建议: 检查ComfyUI插件是否完整安装")
            
        elif "file" in error_lower:
            print("📁 文件系统问题:")
            print("  • 可能是权限问题或磁盘空间不足")
            print("  • 建议: 检查输出目录权限和磁盘空间")
            
        else:
            print("❓ 未知错误:")
            print(f"  • 原始错误: {error_msg[:200]}")
            print("  • 建议: 检查ComfyUI控制台输出获取更多信息")
        
        print("⏱️ 等待2秒后重试...")
    
    def _diagnose_generation_error(self, error_msg: str, image_index: int):
        """诊断图片生成错误并提供建议"""
        print(f"\n🔍 错误诊断 (第{image_index}张分镜图):")
        
        error_lower = error_msg.lower()
        
        if "connection" in error_lower or "timeout" in error_lower:
            print("🌐 网络连接问题:")
            print("  • ComfyUI服务可能未运行或不可达")
            print("  • 建议: 检查ComfyUI是否在127.0.0.1:8188运行")
            
        elif "memory" in error_lower or "out of memory" in error_lower:
            print("💾 内存不足问题:")
            print("  • GPU显存可能不足")
            print("  • 建议: 关闭其他占用GPU的程序，或降低图片分辨率")
            
        elif "workflow" in error_lower or "node" in error_lower:
            print("⚙️ 工作流问题:")
            print("  • 工作流文件可能损坏或节点缺失")
            print("  • 建议: 检查ComfyUI插件是否完整安装")
            
        elif "file" in error_lower:
            print("📁 文件系统问题:")
            print("  • 可能是权限问题或磁盘空间不足")
            print("  • 建议: 检查输出目录权限和磁盘空间")
            
        else:
            print("❓ 未知错误:")
            print(f"  • 原始错误: {error_msg[:200]}")
            print("  • 建议: 检查ComfyUI控制台输出获取更多信息")
        
        print("⏱️ 等待2秒后重试...")
    
    def _queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交工作流到队列"""
        try:
            prompt_data = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            
            print(f"\n=== 提交工作流到ComfyUI ===")
            print(f"Client ID: {self.client_id}")
            print(f"URL: {self.base_url}/prompt")
            print(f"工作流节点数量: {len(workflow)}")
            
            # 显示工作流的前几个节点信息
            for i, (node_id, node_data) in enumerate(list(workflow.items())[:3]):
                print(f"Node {node_id}: {node_data.get('class_type', 'Unknown')}")
                if 'inputs' in node_data:
                    for key, value in list(node_data['inputs'].items())[:3]:
                        if isinstance(value, str) and len(value) > 50:
                            print(f"  {key}: {value[:50]}...")
                        else:
                            print(f"  {key}: {value}")
            
            response = requests.post(
                f"{self.base_url}/prompt",
                json=prompt_data,
                timeout=30
            )
            
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                prompt_id = result.get("prompt_id")
                print(f"Prompt ID: {prompt_id}")
                print(f"=========================\n")
                return prompt_id
            else:
                print(f"错误响应: {response.text}")
                
                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"无法解析错误响应")
                
                print(f"=========================\n")
                return None
                
        except Exception as e:
            print(f"提交工作流异常: {str(e)}")
            # 检查是否是连接错误，如果是则尝试重启服务
            if "WinError 10061" in str(e) or "Failed to establish a new connection" in str(e):
                print("🚨 ComfyUI服务连接失败，尝试检查服务状态...")
                self._attempt_service_recovery()
            print(f"=========================\n")
            return None
    
    def _attempt_service_recovery(self):
        """尝试恢复ComfyUI服务"""
        try:
            print("🔧 尝试恢复ComfyUI服务...")
            
            # 1. 等待一段时间让服务可能自行恢复
            print("⏳ 等待服务可能的自动恢复...")
            import time
            time.sleep(10)
            
            # 2. 检查服务是否恢复
            if self.check_connection():
                print("✅ ComfyUI服务已恢复")
                return True
            
            # 3. 如果服务仍未恢复，建议用户手动重启
            print("⚠️ ComfyUI服务仍未恢复，请手动重启ComfyUI服务:")
            print("   1. 关闭当前ComfyUI进程")
            print("   2. 重新启动ComfyUI")
            print("   3. 等待服务完全启动后再继续")
            
            # 4. 尝试更长时间的等待
            print("⏳ 继续等待服务恢复...")
            for i in range(12):  # 等待2分钟
                time.sleep(10)
                if self.check_connection():
                    print("✅ ComfyUI服务已恢复")
                    return True
                print(f"   等待中... ({i+1}/12)")
            
            print("❌ ComfyUI服务长时间未恢复，请检查服务状态")
            return False
            
        except Exception as e:
            print(f"服务恢复尝试失败: {str(e)}")
            return False
    
    def _wait_for_completion(self, prompt_id: str, timeout: int = 900) -> Optional[Dict]:
        """等待工作流完成 - 增加超时时间到15分钟"""
        start_time = time.time()
        
        # 增加初始等待时间，让ComfyUI有时间开始处理
        time.sleep(2)
        
        while time.time() - start_time < timeout:
            try:
                # 检查队列状态
                response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
                
                if response.status_code == 200:
                    history = response.json()
                    
                    if prompt_id in history:
                        # 任务完成
                        outputs = history[prompt_id].get("outputs", {})
                        return outputs
                else:
                    print(f"错误响应: {response.text}")
                    return None
                
            except Exception as e:
                print(f"检查队列状态异常: {str(e)}")
                return None
    
    def _save_output(self, output_images: Dict, filename: str) -> Optional[str]:
        """保存输出文件"""
        try:
            import base64
            
            print(f"\n=== 保存输出文件 ===")
            print(f"文件名: {filename}")
            print(f"输出图片数量: {len(output_images)}")
            
            if len(output_images) == 0:
                print(f"✗ 未找到任何输出图片")
                return None
            
            # 选择第一个输出图片
            output_image = output_images[0]
            image_data = output_image[0]
            image_format = output_image[1]
            image_name = output_image[2]
            
            print(f"选择图片: {image_name}")
            print(f"图片格式: {image_format}")
            
            # 生成目标路径
            dest_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 解码base64数据并保存文件
            with open(dest_path, "wb") as output_file:
                output_file.write(base64.b64decode(image_data))
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功保存视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return str(dest_path)
            else:
                print(f"✗ 文件保存失败或文件为空")
                return None
                
        except Exception as e:
            print(f"保存输出文件异常: {str(e)}")
            return None
    
    def _get_comfyui_output_files(self) -> Dict[str, float]:
        """获取ComfyUI output目录中的所有文件及其修改时间"""
        try:
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                return {}
            
            files_info = {}
            # 获取所有视频文件
            for ext in ['*.mp4', '*.avi', '*.mov', '*.mkv']:
                for file_path in comfyui_output_dir.glob(ext):
                    files_info[str(file_path)] = file_path.stat().st_mtime
            
            return files_info
        except Exception as e:
            print(f"获取文件列表失败: {str(e)}")
            return {}
    
    def _execute_workflow_with_file_tracking(self, workflow: Dict, filename: str, files_before: Dict[str, float]) -> Optional[str]:
        """执行ComfyUI工作流并跟踪新生成的文件"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 首先尝试通过API保存
                api_result = self._save_output(output_images, filename)
                if api_result:
                    return api_result
            
            # API失败，使用文件跟踪方式
            print(f"⚠️ API保存失败，使用文件跟踪方式...")
            return self._find_new_video_file(files_before, filename)
            
        except Exception as e:
            print(f"执行工作流异常: {str(e)}")
            # 如果有异常，也尝试文件跟踪
            return self._find_new_video_file(files_before, filename)
    
    def _find_new_video_file(self, files_before: Dict[str, float], filename: str) -> Optional[str]:
        """查找新生成的视频文件"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            files_after = self._get_comfyui_output_files()
            
            # 找出新增的文件
            new_files = []
            for file_path, mtime in files_after.items():
                if file_path not in files_before:
                    # 全新文件
                    new_files.append((file_path, mtime, 'new'))
                elif mtime > files_before[file_path]:
                    # 修改过的文件
                    new_files.append((file_path, mtime, 'modified'))
            
            if not new_files:
                print(f"✗ 未找到新生成的视频文件")
                return None
            
            print(f"找到 {len(new_files)} 个新/修改的文件:")
            for file_path, mtime, status in new_files:
                file_obj = Path(file_path)
                size = file_obj.stat().st_size / 1024 / 1024
                print(f"  {file_obj.name} ({size:.2f}MB, {status})")
            
            # 选择最新的文件（按修改时间）
            latest_file = max(new_files, key=lambda x: x[1])
            latest_path = Path(latest_file[0])
            
            # 检查文件大小
            file_size = latest_path.stat().st_size
            if file_size < 100 * 1024:  # 小于100KB
                print(f"⚠️ 最新文件太小 ({file_size/1024:.1f}KB)，可能生成失败")
                # 尝试找更大的文件
                valid_files = [(f, m, s) for f, m, s in new_files if Path(f).stat().st_size > 100 * 1024]
                if valid_files:
                    # 选择最新的有效文件
                    latest_file = max(valid_files, key=lambda x: x[1])
                    latest_path = Path(latest_file[0])
                    print(f"使用最新的有效文件: {latest_path.name}")
            
            print(f"选择文件: {latest_path}")
            
            # 复制到项目目录
            return self._copy_video_file(latest_path, filename)
            
        except Exception as e:
            print(f"查找新文件异常: {str(e)}")
            return None
    
    def _copy_video_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制视频文件到项目目录"""
        try:
            import shutil
            
            # 目标路径
            dest_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制视频文件异常: {str(e)}")
            return None
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
    
    def _find_latest_generated_image(self, filename: str) -> Optional[str]:
        """从 ComfyUI 输出目录查找最新生成的图片"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                print(f"✗ ComfyUI output目录不存在: {comfyui_output_dir}")
                return None
            
            print(f"\n=== 查找最新生成的图片 ===")
            print(f"搜索目录: {comfyui_output_dir}")
            
            # 查找所有图片文件
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.webp']:
                found_files = list(comfyui_output_dir.glob(ext))
                image_files.extend(found_files)
                if found_files:
                    print(f"找到 {len(found_files)} 个 {ext} 文件")
            
            if not image_files:
                print(f"✗ 未找到任何图片文件")
                return None
            
            print(f"总共找到 {len(image_files)} 个图片文件")
            
            # 按修改时间排序，选择最新的
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 选择最新的有效图片（大于50KB）
            for image_file in image_files[:5]:  # 只检查最新的5个文件
                file_size = image_file.stat().st_size
                file_time = time.ctime(image_file.stat().st_mtime)
                print(f"检查文件: {image_file.name} ({file_size/1024:.1f}KB, {file_time})")
                
                if file_size > 50 * 1024:  # 大于50KB
                    print(f"✅ 选择最新的有效图片: {image_file.name}")
                    
                    # 复制到项目目录
                    return self._copy_image_file(image_file, filename)
            
            print(f"✗ 未找到有效的图片文件（大于50KB）")
            return None
            
        except Exception as e:
            print(f"查找最新图片异常: {str(e)}")
            return None
    
    def _copy_image_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制图片文件到项目目录"""
        try:
            import shutil
            
            print(f"\n=== 复制图片文件 ===")
            print(f"源文件: {source_path}")
            print(f"源文件大小: {source_path.stat().st_size/1024/1024:.2f}MB")
            
            # 目标路径 - 使用原始扩展名
            dest_path = Config.STORYBOARD_DIR / f"{filename}{source_path.suffix}"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            print(f"开始复制文件...")
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制图片: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                print(f"=========================\n")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制图片文件异常: {str(e)}")
            return None

    def _execute_workflow(self, workflow: Dict, filename: str) -> Optional[str]:
        """执行ComfyUI工作流"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 保存输出文件
                saved_path = self._save_output(output_images, filename)
                if saved_path:
                    return saved_path
                else:
                    print(f"⚠️ API保存失败，尝试从输出目录查找...")
                    # 根据filename判断是音频还是图片
                    if filename.startswith('audio_'):
                        # 音频文件，查找最新生成的音频
                        return self._find_latest_generated_audio(filename)
                    else:
                        # 图片文件，查找最新生成的图片
                        return self._find_latest_generated_image(filename)
            
            return None
            
        except Exception as e:
            print(f"执行工作流失败: {str(e)}")
            return None
    
    def _queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交工作流到队列"""
        try:
            prompt_data = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            
            print(f"\n=== 提交工作流到ComfyUI ===")
            print(f"Client ID: {self.client_id}")
            print(f"URL: {self.base_url}/prompt")
            print(f"工作流节点数量: {len(workflow)}")
            
            # 显示工作流的前几个节点信息
            for i, (node_id, node_data) in enumerate(list(workflow.items())[:3]):
                print(f"Node {node_id}: {node_data.get('class_type', 'Unknown')}")
                if 'inputs' in node_data:
                    for key, value in list(node_data['inputs'].items())[:3]:
                        if isinstance(value, str) and len(value) > 50:
                            print(f"  {key}: {value[:50]}...")
                        else:
                            print(f"  {key}: {value}")
            
            response = requests.post(
                f"{self.base_url}/prompt",
                json=prompt_data,
                timeout=30
            )
            
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                prompt_id = result.get("prompt_id")
                print(f"Prompt ID: {prompt_id}")
                print(f"=========================\n")
                return prompt_id
            else:
                print(f"错误响应: {response.text}")
                
                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"无法解析错误响应")
                
                print(f"=========================\n")
                return None
                
        except Exception as e:
            print(f"提交工作流异常: {str(e)}")
            print(f"=========================\n")
            return None
    
    def _wait_for_completion(self, prompt_id: str, timeout: int = 900) -> Optional[Dict]:
        """等待工作流完成 - 增加超时时间到15分钟"""
        start_time = time.time()
        
        # 增加初始等待时间，让ComfyUI有时间开始处理
        time.sleep(2)
        
        while time.time() - start_time < timeout:
            try:
                # 检查队列状态
                response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
                
                if response.status_code == 200:
                    history = response.json()
                    
                    if prompt_id in history:
                        # 任务完成
                        outputs = history[prompt_id].get("outputs", {})
                        return outputs
                else:
                    print(f"错误响应: {response.text}")
                    return None
                
            except Exception as e:
                print(f"检查队列状态异常: {str(e)}")
                return None
    
    def _execute_workflow_simple(self, workflow: Dict, video_filename: str, timestamp: int) -> Optional[str]:
        """简化的工作流执行，按文件名+时间戳查找视频"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 首先尝试通过API保存
                api_result = self._save_output(output_images, video_filename)
                if api_result:
                    return api_result
            
            # API失败，按时间戳查找最新文件
            print(f"⚠️ API保存失败，按时间戳查找最新视频文件...")
            return self._find_video_by_timestamp(video_filename, timestamp)
            
        except Exception as e:
            print(f"执行工作流异常: {str(e)}")
            # 如果有异常，也尝试按时间戳查找
            return self._find_video_by_timestamp(video_filename, timestamp)
    
    def _find_video_by_timestamp(self, video_filename: str, timestamp: int) -> Optional[str]:
        """按时间戳查找最新生成的视频文件，确保每次都生成唯一的新文件"""
        try:
            import time
            # 等待ComfyUI完成文件写入 - 增加等待时间
            print("⏳ 等待ComfyUI完成文件写入...")
            time.sleep(5)  # 增加等待时间确保文件完全写入
            
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                print(f"✗ ComfyUI output目录不存在: {comfyui_output_dir}")
                return None
            
            print(f"\n=== 查找视频文件 (时间戳: {timestamp}) ===")
            print(f"搜索目录: {comfyui_output_dir}")
            print(f"视频文件名: {video_filename}")
            
            # 清理项目目录中的历史文件，防止混淆
            self._clean_old_video_files(video_filename)
            
            # 查找所有视频文件
            video_files = []
            for ext in ['*.mp4', '*.avi', '*.mov', '*.mkv']:
                found_files = list(comfyui_output_dir.glob(ext))
                video_files.extend(found_files)
                if found_files:
                    print(f"找到 {len(found_files)} 个 {ext} 文件")
            
            if not video_files:
                print(f"✗ 未找到任何视频文件")
                # 显示目录中的文件以便调试
                all_files = list(comfyui_output_dir.glob('*.*'))
                print(f"目录中的所有文件: {[f.name for f in all_files[:10]]}")
                return None
            
            print(f"总共找到 {len(video_files)} 个视频文件")
            
            # 查找在时间戳之后生成的文件（转换为秒）
            timestamp_seconds = timestamp / 1000.0
            
            # 添加更严格的时间范围筛选，避免选择历史文件
            # 扩大时间窗口以适应可能的系统时间差异
            min_timestamp = timestamp_seconds - 30  # 允许最多30秒的时间偏差
            max_timestamp = timestamp_seconds + 300  # 允许最多5分钟的时间偏差
            
            recent_files = []
            
            for video_file in video_files:
                try:
                    file_mtime = video_file.stat().st_mtime
                    file_size = video_file.stat().st_size
                    file_time_readable = time.ctime(file_mtime)
                    
                    print(f"检查文件: {video_file.name} ({file_size/1024/1024:.2f}MB, {file_time_readable})")
                    
                    # 严格的时间范围筛选：必须在合理的时间窗口内生成
                    if (file_mtime >= min_timestamp and 
                        file_mtime <= max_timestamp and 
                        file_size > 100 * 1024):
                        recent_files.append((video_file, file_mtime, file_size))
                        print(f"✅ 符合条件的候选文件: {video_file.name} ({file_size/1024/1024:.2f}MB)")
                    elif file_mtime < min_timestamp:
                        print(f"❌ 文件太旧，忽略: {video_file.name}")
                    elif file_mtime > max_timestamp:
                        print(f"❌ 文件太新，忽略: {video_file.name}")
                    elif file_size <= 100 * 1024:
                        print(f"❌ 文件太小，忽略: {video_file.name}")
                except Exception as e:
                    print(f"检查文件 {video_file.name} 时出错: {e}")
                    continue
            
            if not recent_files:
                print(f"⚠️ 无法找到在时间窗口内生成的有效视频文件")
                try:
                    print(f"时间戳范围: {time.ctime(min_timestamp)} ~ {time.ctime(max_timestamp)}")
                except Exception as e:
                    print(f"时间戳格式化错误: {e}")
                
                # 最后的备用方案：选择最新的大文件（但要确保不是太旧的）
                current_time = time.time()
                recent_enough_files = []
                for f in video_files:
                    try:
                        file_stat = f.stat()
                        if (file_stat.st_size > 100 * 1024 and 
                            file_stat.st_mtime > current_time - 600):  # 10分钟内
                            recent_enough_files.append((f, file_stat.st_mtime, file_stat.st_size))
                    except Exception as e:
                        print(f"检查文件 {f.name} 时出错: {e}")
                        continue
                
                if recent_enough_files:
                    recent_files = [max(recent_enough_files, key=lambda x: x[1])]
                    print(f"备用方案：使用10分钟内最新的文件: {recent_files[0][0].name}")
                else:
                    print(f"✗ 没有找到任何近期的有效视频文件")
                    return None
            
            # 选择最新的文件
            latest_file = max(recent_files, key=lambda x: x[1])[0]
            print(f"最终选择文件: {latest_file}")
            print(f"文件大小: {latest_file.stat().st_size/1024/1024:.2f}MB")
            print(f"文件扩展名: {latest_file.suffix}")
            
            # 确保选择的是视频文件
            if latest_file.suffix.lower() not in ['.mp4', '.avi', '.mov', '.mkv']:
                print(f"⚠️ 警告：选择的文件不是标准视频格式: {latest_file.suffix}")
                print(f"但继续处理，可能是ComfyUI的特殊格式")
            
            # 复制到项目目录并验证
            result = self._copy_video_file_simple(latest_file, video_filename)
            
            if result:
                print(f"✅ 视频文件成功生成: {result}")
            else:
                print(f"❌ 视频文件复制失败")
            
            return result
            
        except Exception as e:
            print(f"按时间戳查找文件异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _clean_old_video_files(self, video_filename: str):
        """清理项目目录中可能存在的旧视频文件，防止缓存混淆"""
        try:
            # 清理可能存在的同名文件
            old_file = Config.VIDEO_CLIPS_DIR / f"{video_filename}.mp4"
            if old_file.exists():
                old_file.unlink()
                print(f"🗑️ 清理旧文件: {old_file}")
            
            # 清理带有相似名称的文件（防止时间戳重复）
            base_name = video_filename.split('_')[0] if '_' in video_filename else video_filename
            for old_file in Config.VIDEO_CLIPS_DIR.glob(f"{base_name}_*.mp4"):
                if old_file.name != f"{video_filename}.mp4":
                    try:
                        # 检查文件是否太新（5分钟内），如果是则不删除
                        import time
                        if time.time() - old_file.stat().st_mtime > 300:  # 5分钟
                            old_file.unlink()
                            print(f"🗑️ 清理历史文件: {old_file}")
                        else:
                            print(f"⏳ 保留最近文件: {old_file}")
                    except Exception as e:
                        print(f"⚠️ 清理文件失败: {old_file} - {e}")
                        
        except Exception as e:
            print(f"⚠️ 清理旧文件异常: {str(e)}")
    
    def _copy_video_file_simple(self, source_path: Path, video_filename: str) -> Optional[str]:
        """简化的视频文件复制"""
        try:
            import shutil
            
            print(f"\n=== 复制视频文件 ===")
            print(f"源文件: {source_path}")
            print(f"源文件扩展名: {source_path.suffix}")
            print(f"源文件大小: {source_path.stat().st_size/1024/1024:.2f}MB")
            print(f"目标文件名: {video_filename}")
            
            # 验证源文件是视频文件
            if source_path.suffix.lower() not in ['.mp4', '.avi', '.mov', '.mkv']:
                print(f"⚠️ 警告：源文件不是视频格式: {source_path.suffix}")
                print(f"但继续复制，可能是ComfyUI的输出文件命名问题")
            
            # 目标路径 - 确保使用.mp4扩展名
            dest_path = Config.VIDEO_CLIPS_DIR / f"{video_filename}.mp4"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            print(f"开始复制文件...")
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                print(f"文件扩展名: {dest_path.suffix}")
                print(f"=========================\n")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                print(f"=========================\n")
                return None
                
        except Exception as e:
            print(f"复制视频文件异常: {str(e)}")
            print(f"=========================\n")
            return None
        """获取ComfyUI output目录中的所有文件及其修改时间"""
        try:
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                return {}
            
            files_info = {}
            # 获取所有视频文件
            for ext in ['*.mp4', '*.avi', '*.mov', '*.mkv']:
                for file_path in comfyui_output_dir.glob(ext):
                    files_info[str(file_path)] = file_path.stat().st_mtime
            
            return files_info
        except Exception as e:
            print(f"获取文件列表失败: {str(e)}")
            return {}
    
    def _execute_workflow_with_file_tracking(self, workflow: Dict, filename: str, files_before: Dict[str, float]) -> Optional[str]:
        """执行ComfyUI工作流并跟踪新生成的文件"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 首先尝试通过API保存
                api_result = self._save_output(output_images, filename)
                if api_result:
                    return api_result
            
            # API失败，使用文件跟踪方式
            print(f"⚠️ API保存失败，使用文件跟踪方式...")
            return self._find_new_video_file(files_before, filename)
            
        except Exception as e:
            print(f"执行工作流异常: {str(e)}")
            # 如果有异常，也尝试文件跟踪
            return self._find_new_video_file(files_before, filename)
    
    def _find_new_video_file(self, files_before: Dict[str, float], filename: str) -> Optional[str]:
        """查找新生成的视频文件"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            files_after = self._get_comfyui_output_files()
            
            # 找出新增的文件
            new_files = []
            for file_path, mtime in files_after.items():
                if file_path not in files_before:
                    # 全新文件
                    new_files.append((file_path, mtime, 'new'))
                elif mtime > files_before[file_path]:
                    # 修改过的文件
                    new_files.append((file_path, mtime, 'modified'))
            
            if not new_files:
                print(f"✗ 未找到新生成的视频文件")
                return None
            
            print(f"找到 {len(new_files)} 个新/修改的文件:")
            for file_path, mtime, status in new_files:
                file_obj = Path(file_path)
                size = file_obj.stat().st_size / 1024 / 1024
                print(f"  {file_obj.name} ({size:.2f}MB, {status})")
            
            # 选择最新的文件（按修改时间）
            latest_file = max(new_files, key=lambda x: x[1])
            latest_path = Path(latest_file[0])
            
            # 检查文件大小
            file_size = latest_path.stat().st_size
            if file_size < 100 * 1024:  # 小于100KB
                print(f"⚠️ 最新文件太小 ({file_size/1024:.1f}KB)，可能生成失败")
                # 尝试找更大的文件
                valid_files = [(f, m, s) for f, m, s in new_files if Path(f).stat().st_size > 100 * 1024]
                if valid_files:
                    # 选择最新的有效文件
                    latest_file = max(valid_files, key=lambda x: x[1])
                    latest_path = Path(latest_file[0])
                    print(f"使用最新的有效文件: {latest_path.name}")
            
            print(f"选择文件: {latest_path}")
            
            # 复制到项目目录
            return self._copy_video_file(latest_path, filename)
            
        except Exception as e:
            print(f"查找新文件异常: {str(e)}")
            return None
    
    def _copy_video_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制视频文件到项目目录"""
        try:
            import shutil
            
            # 目标路径
            dest_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制视频文件异常: {str(e)}")
            return None
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
    
    def _find_latest_generated_image(self, filename: str) -> Optional[str]:
        """从 ComfyUI 输出目录查找最新生成的图片"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                print(f"✗ ComfyUI output目录不存在: {comfyui_output_dir}")
                return None
            
            print(f"\n=== 查找最新生成的图片 ===")
            print(f"搜索目录: {comfyui_output_dir}")
            
            # 查找所有图片文件
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.webp']:
                found_files = list(comfyui_output_dir.glob(ext))
                image_files.extend(found_files)
                if found_files:
                    print(f"找到 {len(found_files)} 个 {ext} 文件")
            
            if not image_files:
                print(f"✗ 未找到任何图片文件")
                return None
            
            print(f"总共找到 {len(image_files)} 个图片文件")
            
            # 按修改时间排序，选择最新的
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 选择最新的有效图片（大于50KB）
            for image_file in image_files[:5]:  # 只检查最新的5个文件
                file_size = image_file.stat().st_size
                file_time = time.ctime(image_file.stat().st_mtime)
                print(f"检查文件: {image_file.name} ({file_size/1024:.1f}KB, {file_time})")
                
                if file_size > 50 * 1024:  # 大于50KB
                    print(f"✅ 选择最新的有效图片: {image_file.name}")
                    
                    # 复制到项目目录
                    return self._copy_image_file(image_file, filename)
            
            print(f"✗ 未找到有效的图片文件（大于50KB）")
            return None
            
        except Exception as e:
            print(f"查找最新图片异常: {str(e)}")
            return None
    
    def _copy_image_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制图片文件到项目目录"""
        try:
            import shutil
            
            print(f"\n=== 复制图片文件 ===")
            print(f"源文件: {source_path}")
            print(f"源文件大小: {source_path.stat().st_size/1024/1024:.2f}MB")
            
            # 目标路径 - 使用原始扩展名
            dest_path = Config.STORYBOARD_DIR / f"{filename}{source_path.suffix}"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            print(f"开始复制文件...")
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制图片: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                print(f"=========================\n")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制图片文件异常: {str(e)}")
            return None

    def _execute_workflow(self, workflow: Dict, filename: str) -> Optional[str]:
        """执行ComfyUI工作流"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 保存输出文件
                saved_path = self._save_output(output_images, filename)
                if saved_path:
                    return saved_path
                else:
                    print(f"⚠️ API保存失败，尝试从输出目录查找...")
                    # 根据filename判断是音频还是图片
                    if filename.startswith('audio_'):
                        # 音频文件，查找最新生成的音频
                        return self._find_latest_generated_audio(filename)
                    else:
                        # 图片文件，查找最新生成的图片
                        return self._find_latest_generated_image(filename)
            
            return None
            
        except Exception as e:
            print(f"执行工作流失败: {str(e)}")
            return None
    
    def _queue_prompt(self, workflow: Dict) -> Optional[str]:
        """提交工作流到队列"""
        try:
            prompt_data = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            
            print(f"\n=== 提交工作流到ComfyUI ===")
            print(f"Client ID: {self.client_id}")
            print(f"URL: {self.base_url}/prompt")
            print(f"工作流节点数量: {len(workflow)}")
            
            # 显示工作流的前几个节点信息
            for i, (node_id, node_data) in enumerate(list(workflow.items())[:3]):
                print(f"Node {node_id}: {node_data.get('class_type', 'Unknown')}")
                if 'inputs' in node_data:
                    for key, value in list(node_data['inputs'].items())[:3]:
                        if isinstance(value, str) and len(value) > 50:
                            print(f"  {key}: {value[:50]}...")
                        else:
                            print(f"  {key}: {value}")
            
            response = requests.post(
                f"{self.base_url}/prompt",
                json=prompt_data,
                timeout=30
            )
            
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                prompt_id = result.get("prompt_id")
                print(f"Prompt ID: {prompt_id}")
                print(f"=========================\n")
                return prompt_id
            else:
                print(f"错误响应: {response.text}")
                
                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    print(f"错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"无法解析错误响应")
                
                print(f"=========================\n")
                return None
                
        except Exception as e:
            print(f"提交工作流异常: {str(e)}")
            print(f"=========================\n")
            return None
    
    def _wait_for_completion(self, prompt_id: str, timeout: int = 900) -> Optional[Dict]:
        """等待工作流完成 - 增加超时时间到15分钟"""
        start_time = time.time()
        
        # 增加初始等待时间，让ComfyUI有时间开始处理
        time.sleep(2)
        
        while time.time() - start_time < timeout:
            try:
                # 检查队列状态
                response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
                
                if response.status_code == 200:
                    history = response.json()
                    
                    if prompt_id in history:
                        # 任务完成
                        outputs = history[prompt_id].get("outputs", {})
                        return outputs
                else:
                    print(f"错误响应: {response.text}")
                    return None
                
            except Exception as e:
                print(f"检查队列状态异常: {str(e)}")
                return None
    
    def _save_output(self, output_images: Dict, filename: str) -> Optional[str]:
        """保存输出文件"""
        try:
            import base64
            
            print(f"\n=== 保存输出文件 ===")
            print(f"文件名: {filename}")
            print(f"输出图片数量: {len(output_images)}")
            
            if len(output_images) == 0:
                print(f"✗ 未找到任何输出图片")
                return None
            
            # 选择第一个输出图片
            output_image = output_images[0]
            image_data = output_image[0]
            image_format = output_image[1]
            image_name = output_image[2]
            
            print(f"选择图片: {image_name}")
            print(f"图片格式: {image_format}")
            
            # 生成目标路径
            dest_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 解码base64数据并保存文件
            with open(dest_path, "wb") as output_file:
                output_file.write(base64.b64decode(image_data))
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功保存视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return str(dest_path)
            else:
                print(f"✗ 文件保存失败或文件为空")
                return None
                
        except Exception as e:
            print(f"保存输出文件异常: {str(e)}")
            return None
    
    def _get_comfyui_output_files(self) -> Dict[str, float]:
        """获取ComfyUI output目录中的所有文件及其修改时间"""
        try:
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                return {}
            
            files_info = {}
            # 获取所有视频文件
            for ext in ['*.mp4', '*.avi', '*.mov', '*.mkv']:
                for file_path in comfyui_output_dir.glob(ext):
                    files_info[str(file_path)] = file_path.stat().st_mtime
            
            return files_info
        except Exception as e:
            print(f"获取文件列表失败: {str(e)}")
            return {}
    
    def _execute_workflow_with_file_tracking(self, workflow: Dict, filename: str, files_before: Dict[str, float]) -> Optional[str]:
        """执行ComfyUI工作流并跟踪新生成的文件"""
        try:
            # 队列提示
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return None
            
            # 等待完成
            output_images = self._wait_for_completion(prompt_id)
            
            if output_images:
                # 首先尝试通过API保存
                api_result = self._save_output(output_images, filename)
                if api_result:
                    return api_result
            
            # API失败，使用文件跟踪方式
            print(f"⚠️ API保存失败，使用文件跟踪方式...")
            return self._find_new_video_file(files_before, filename)
            
        except Exception as e:
            print(f"执行工作流异常: {str(e)}")
            # 如果有异常，也尝试文件跟踪
            return self._find_new_video_file(files_before, filename)
    
    def _find_new_video_file(self, files_before: Dict[str, float], filename: str) -> Optional[str]:
        """查找新生成的视频文件"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            files_after = self._get_comfyui_output_files()
            
            # 找出新增的文件
            new_files = []
            for file_path, mtime in files_after.items():
                if file_path not in files_before:
                    # 全新文件
                    new_files.append((file_path, mtime, 'new'))
                elif mtime > files_before[file_path]:
                    # 修改过的文件
                    new_files.append((file_path, mtime, 'modified'))
            
            if not new_files:
                print(f"✗ 未找到新生成的视频文件")
                return None
            
            print(f"找到 {len(new_files)} 个新/修改的文件:")
            for file_path, mtime, status in new_files:
                file_obj = Path(file_path)
                size = file_obj.stat().st_size / 1024 / 1024
                print(f"  {file_obj.name} ({size:.2f}MB, {status})")
            
            # 选择最新的文件（按修改时间）
            latest_file = max(new_files, key=lambda x: x[1])
            latest_path = Path(latest_file[0])
            
            # 检查文件大小
            file_size = latest_path.stat().st_size
            if file_size < 100 * 1024:  # 小于100KB
                print(f"⚠️ 最新文件太小 ({file_size/1024:.1f}KB)，可能生成失败")
                # 尝试找更大的文件
                valid_files = [(f, m, s) for f, m, s in new_files if Path(f).stat().st_size > 100 * 1024]
                if valid_files:
                    # 选择最新的有效文件
                    latest_file = max(valid_files, key=lambda x: x[1])
                    latest_path = Path(latest_file[0])
                    print(f"使用最新的有效文件: {latest_path.name}")
            
            print(f"选择文件: {latest_path}")
            
            # 复制到项目目录
            return self._copy_video_file(latest_path, filename)
            
        except Exception as e:
            print(f"查找新文件异常: {str(e)}")
            return None
    
    def _copy_video_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制视频文件到项目目录"""
        try:
            import shutil
            
            # 目标路径
            dest_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            
            # 确保目录存在
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制视频: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制视频文件异常: {str(e)}")
            return None
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
        """将图片编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except Exception as e:
            print(f"图片编码失败: {str(e)}")
            return ""
    
    def _find_latest_generated_image(self, filename: str) -> Optional[str]:
        """从 ComfyUI 输出目录查找最新生成的图片"""
        try:
            import time
            # 等待一下让ComfyUI完成文件写入
            time.sleep(2)
            
            comfyui_output_dir = Path("F:/ComfyUI_windows_portable/ComfyUI/output")
            if not comfyui_output_dir.exists():
                print(f"✗ ComfyUI output目录不存在: {comfyui_output_dir}")
                return None
            
            print(f"\n=== 查找最新生成的图片 ===")
            print(f"搜索目录: {comfyui_output_dir}")
            
            # 查找所有图片文件
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.webp']:
                found_files = list(comfyui_output_dir.glob(ext))
                image_files.extend(found_files)
                if found_files:
                    print(f"找到 {len(found_files)} 个 {ext} 文件")
            
            if not image_files:
                print(f"✗ 未找到任何图片文件")
                return None
            
            print(f"总共找到 {len(image_files)} 个图片文件")
            
            # 按修改时间排序，选择最新的
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 选择最新的有效图片（大于50KB）
            for image_file in image_files[:5]:  # 只检查最新的5个文件
                file_size = image_file.stat().st_size
                file_time = time.ctime(image_file.stat().st_mtime)
                print(f"检查文件: {image_file.name} ({file_size/1024:.1f}KB, {file_time})")
                
                if file_size > 50 * 1024:  # 大于50KB
                    print(f"✅ 选择最新的有效图片: {image_file.name}")
                    
                    # 复制到项目目录
                    return self._copy_image_file(image_file, filename)
            
            print(f"✗ 未找到有效的图片文件（大于50KB）")
            return None
            
        except Exception as e:
            print(f"查找最新图片异常: {str(e)}")
            return None
    
    def _copy_image_file(self, source_path: Path, filename: str) -> Optional[str]:
        """复制图片文件到项目目录"""
        try:
            import shutil
            
            print(f"\n=== 复制图片文件 ===")
            print(f"源文件: {source_path}")
            print(f"源文件大小: {source_path.stat().st_size/1024/1024:.2f}MB")
            
            # 目标路径 - 使用原始扩展名
            dest_path = Config.STORYBOARD_DIR / f"{filename}{source_path.suffix}"
            print(f"目标路径: {dest_path}")
            
            # 确保目录存在
            Config.STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            print(f"开始复制文件...")
            shutil.copy2(source_path, dest_path)
            
            # 等待一下确保复制完成
            import time
            time.sleep(0.5)
            
            # 验证文件
            if dest_path.exists() and dest_path.stat().st_size > 0:
                file_size = dest_path.stat().st_size
                print(f"✅ 成功复制图片: {dest_path}")
                print(f"文件大小: {file_size/1024/1024:.2f}MB")
                print(f"=========================\n")
                return str(dest_path)
            else:
                print(f"✗ 文件复制失败或文件为空")
                return None
                
        except Exception as e:
            print(f"复制图片文件异常: {str(e)}")
            return None

    def generate_videos(self, image_paths: List[str], video_prompts: List[str], video_params: Dict = None) -> List[str]:
        """将图片转换为视频片段 - 使用分批处理避免内存溢出"""
        video_paths = []
        
        print(f"开始生成 {len(image_paths)} 个视频片段...")
        if video_params:
            print(f"视频参数: {video_params}")
        
        # 检查输入参数
        if len(image_paths) != len(video_prompts):
            print(f"⚠️ 警告：图片数量({len(image_paths)})与提示词数量({len(video_prompts)})不匹配")
            min_count = min(len(image_paths), len(video_prompts))
            image_paths = image_paths[:min_count]
            video_prompts = video_prompts[:min_count]
            print(f"自动裁剪到 {min_count} 个")
        
        success_count = 0
        
        # 使用更小的分批处理，每批只处理1个视频以避免内存问题
        batch_size = 1
        max_retries = 3
        
        # 检查ComfyUI服务状态
        if not self.check_connection():
            print("❌ ComfyUI服务未运行，请先启动ComfyUI服务")
            # 尝试恢复服务
            if not self._attempt_service_recovery():
                # 填充结果列表为None
                return [None] * len(image_paths)
        
        # 分批处理所有视频
        for batch_start in range(0, len(image_paths), batch_size):
            batch_end = min(batch_start + batch_size, len(image_paths))
            batch_images = image_paths[batch_start:batch_end]
            batch_prompts = video_prompts[batch_start:batch_end]
            
            print(f"\n=== 处理批次 {batch_start//batch_size + 1}/{(len(image_paths)-1)//batch_size + 1} ===")
            
            # 处理当前批次
            for i, (image_path, prompt) in enumerate(zip(batch_images, batch_prompts)):
                try:
                    print(f"\n--- 处理批次内第{i+1}个视频 ---")
                    print(f"源图片: {image_path}")
                    print(f"视频提示词: {prompt}")
                    
                    # 检查系统资源
                    self._check_system_resources()
                    
                    # 检查图片文件是否存在
                    if not image_path or not Path(image_path).exists():
                        print(f"❌ 图片文件不存在，跳过: {image_path}")
                        video_paths.append(None)
                        continue
                    
                    # 生成唯一的视频文件名：图片名 + 精确时间戳
                    image_name = Path(image_path).stem  # 不带扩展名的文件名
                    import time as time_module  # 避免变量名冲突
                    # 使用更精确的时间戳加随机数确保唯一性
                    timestamp = int(time_module.time() * 1000000)  # 微秒级时间戳
                    import uuid
                    unique_id = str(uuid.uuid4())[:8]  # 8位随机字符
                    video_filename = f"{image_name}_{timestamp}_{unique_id}"
                    
                    print(f"生成唯一视频文件名: {video_filename}")
                    print(f"时间戳: {timestamp}, UUID前缀: {unique_id}")
                    
                    # 重试机制
                    video_path = None
                    last_error = None
                    
                    for retry in range(max_retries):
                        try:
                            # 检查ComfyUI服务状态
                            if not self.check_connection():
                                print("❌ ComfyUI服务连接失败")
                                if not self._attempt_service_recovery():
                                    last_error = "ComfyUI服务无法连接"
                                    break
                            
                            if retry > 0:
                                print(f"🔄 第{retry}次重试 (共{max_retries-1}次)...")
                                # 重试前等待更长时间
                                wait_time = 15 * retry  # 递增等待时间
                                print(f"⏳ 等待 {wait_time} 秒后重试...")
                                time_module.sleep(wait_time)
                            
                            # 加载视频生成工作流
                            workflow = self.load_workflow(Config.VIDEO_WORKFLOW)
                            
                            # 修改工作流，传递视频参数
                            workflow = self._update_video_workflow(workflow, image_path, prompt, video_params)
                            
                            # 执行工作流
                            video_path = self._execute_workflow_simple(workflow, video_filename, timestamp)
                            
                            if video_path and Path(video_path).exists():
                                # 检查文件大小
                                file_size = Path(video_path).stat().st_size
                                print(f"文件大小: {file_size / (1024*1024):.2f} MB")
                                
                                if file_size >= 1024:  # 大于1KB才认为成功
                                    break  # 成功，跳出重试循环
                                else:
                                    print(f"⚠️ 警告：视频文件太小，可能生成失败")
                                    last_error = "视频文件太小"
                            else:
                                last_error = "视频文件未生成"
                                
                        except Exception as e:
                            last_error = str(e)
                            print(f"❌ 生成视频片段异常 (尝试{retry+1}/{max_retries}): {str(e)}")
                            if retry < max_retries - 1:  # 不是最后一次尝试
                                print("等待ComfyUI服务恢复...")
                                # 重试前等待更长时间
                                wait_time = 20 * (retry + 1)  # 递增等待时间
                                print(f"⏳ 等待 {wait_time} 秒后重试...")
                                time_module.sleep(wait_time)
                    
                    if video_path and Path(video_path).exists():
                        video_paths.append(video_path)
                        success_count += 1
                        print(f"✅ 视频片段生成成功: {video_path}")
                    else:
                        print(f"❌ 视频片段生成失败: {last_error}")
                        video_paths.append(None)
                        
                except Exception as e:
                    print(f"❌ 处理视频片段异常: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    video_paths.append(None)
                
                # 每处理一个视频后等待一段时间，让ComfyUI释放资源
                if i < len(batch_images) - 1:  # 不是批次内最后一个视频
                    print("⏳ 等待ComfyUI释放资源...")
                    time_module.sleep(5)
                    
                    # 强制垃圾回收
                    gc.collect()
            
            # 批次间等待，让ComfyUI充分释放资源
            if batch_end < len(image_paths):
                print("⏳ 批次间等待，让ComfyUI充分释放资源...")
                wait_time = 10 + (batch_start//batch_size) * 5  # 递增等待时间
                time_module.sleep(wait_time)
                
                # 强制垃圾回收
                gc.collect()
                
                # 检查系统资源
                self._check_system_resources()
                
                # 额外的ComfyUI服务健康检查
                if not self.check_connection():
                    print("⚠️ ComfyUI服务连接断开，尝试重新连接...")
                    if not self._attempt_service_recovery():
                        print("❌ 无法重新连接到ComfyUI服务，终止视频生成")
                        # 将剩余未处理的视频路径填充为None
                        remaining_count = len(image_paths) - len(video_paths)
                        video_paths.extend([None] * remaining_count)
                        break
        
        print(f"\n=== 视频生成总结 ===")
        print(f"成功生成: {success_count}/{len(image_paths)} 个视频片段")
        
        if success_count == 0:
            print(f"❌ 所有视频生成失败！")
        elif success_count < len(image_paths):
            print(f"⚠️ 部分成功：{len(image_paths) - success_count}个视频生成失败")
        else:
            print(f"🎉 所有视频生成成功！")
        
        return video_paths

    def _wait_for_completion(self, prompt_id: str, timeout: int = 900) -> Optional[Dict]:
        """等待工作流完成 - 增加超时时间到15分钟"""
        start_time = time.time()
        
        # 增加初始等待时间，让ComfyUI有时间开始处理
        time.sleep(2)
        
        while time.time() - start_time < timeout:
            try:
                # 检查队列状态
                response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
                
                if response.status_code == 200:
                    history = response.json()
                    
                    if prompt_id in history:
                        # 任务完成
                        outputs = history[prompt_id].get("outputs", {})
                        return outputs
                
                # 逐渐增加等待时间，避免频繁请求
                elapsed = time.time() - start_time
                if elapsed < 60:
                    time.sleep(3)  # 前1分钟每3秒检查一次
                elif elapsed < 300:
                    time.sleep(5)  # 1-5分钟每5秒检查一次
                else:
                    time.sleep(10)  # 5分钟后每10秒检查一次
                
            except Exception as e:
                print(f"检查状态异常: {str(e)}")
                time.sleep(5)
        
        print(f"工作流执行超时 ({timeout}秒)")
        return None

    def _save_output(self, outputs: Dict, filename: str) -> Optional[str]:
        """保存输出文件"""
        try:
            print(f"\n=== 保存ComfyUI输出 ===")
            print(f"文件名: {filename}")
            print(f"输出节点: {list(outputs.keys())}")
            
            # 显示输出详情
            video_combine_node = None  # 视频合并节点（通常是节点13）
            
            for node_id, node_output in outputs.items():
                print(f"Node {node_id}: {list(node_output.keys())}")
                
                # 检查节点13（VHS_VideoCombine）的输出
                if node_id == "13":
                    video_combine_node = (node_id, node_output)
                    print(f"  🎬 发现视频合并节点 (Node 13)")
                    
                    if "gifs" in node_output:
                        print(f"  GIF数量: {len(node_output['gifs'])}")
                        for i, gif_info in enumerate(node_output['gifs']):
                            print(f"    GIF {i+1}: {gif_info}")
                    
                    if "videos" in node_output:
                        print(f"  视频数量: {len(node_output['videos'])}")
                        for i, video_info in enumerate(node_output['videos']):
                            print(f"    视频 {i+1}: {video_info}")
                
                elif "videos" in node_output:
                    print(f"  视频数量: {len(node_output['videos'])}")
                    for i, video_info in enumerate(node_output['videos']):
                        print(f"    视频 {i+1}: {video_info}")
                elif "gifs" in node_output:
                    print(f"  GIF数量: {len(node_output['gifs'])}")
                    for i, gif_info in enumerate(node_output['gifs']):
                        print(f"    GIF {i+1}: {gif_info}")
                elif "images" in node_output:
                    print(f"  图片数量: {len(node_output['images'])}")
                elif "audio" in node_output:
                    print(f"  🎧 音频节点 (Node {node_id})")
                    print(f"  音频数量: {len(node_output['audio'])}")
                    for i, audio_info in enumerate(node_output['audio']):
                        print(f"    音频 {i+1}: {audio_info}")
            
            # 优先处理SaveAudioMP3节点（Node 2）的音频输出
            save_audio_node = None
            preview_audio_nodes = []
            
            for node_id, node_output in outputs.items():
                if "audio" in node_output:
                    if node_id == "2":  # SaveAudioMP3节点
                        save_audio_node = (node_id, node_output)
                        print(f"🎧 发现SaveAudioMP3节点 (Node {node_id})")
                    else:
                        preview_audio_nodes.append((node_id, node_output))
                        print(f"🎧 发现其他音频节点 (Node {node_id})")
            
            # 优先处理SaveAudioMP3节点的输出（这是真正的TTS生成音频）
            if save_audio_node:
                node_id, node_output = save_audio_node
                print(f"🎧 优先处理SaveAudioMP3 Node {node_id}的audio输出...")
                for audio_info in node_output["audio"]:
                    print(f"  音频文件: {audio_info['filename']} (subfolder: {audio_info.get('subfolder', 'None')})")
                    result = self._download_and_save_audio(audio_info, filename)
                    if result:
                        print(f"✅ SaveAudioMP3节点音频处理成功: {result}")
                        return result
            
            # 如果SaveAudioMP3节点失败，才处理其他音频节点
            for node_id, node_output in preview_audio_nodes:
                print(f"🎧 备用方案：处理Node {node_id}的audio输出...")
                for audio_info in node_output["audio"]:
                    print(f"  音频文件: {audio_info['filename']} (subfolder: {audio_info.get('subfolder', 'None')})")
                    if audio_info.get('type') == 'temp':
                        print(f"  ⚠️ 跳过临时文件，可能是参考音频: {audio_info['filename']}")
                        continue
                    result = self._download_and_save_audio(audio_info, filename)
                    if result:
                        return result
            if video_combine_node:
                node_id, node_output = video_combine_node
                
                # 先检查是否有标准的videos输出
                if "videos" in node_output:
                    print(f"🎬 处理Node 13的videos输出...")
                    for video_info in node_output["videos"]:
                        result = self._download_and_save_video(video_info, filename)
                        if result:
                            return result
                
                # 如果没有videos，检查gifs（VHS_VideoCombine可能输出gif格式）
                elif "gifs" in node_output:
                    print(f"🎬 处理Node 13的gifs输出（可能是视频文件）...")
                    for gif_info in node_output["gifs"]:
                        # 检查文件名的扩展名
                        filename_lower = gif_info["filename"].lower()
                        if filename_lower.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                            print(f"✅ 检测到视频格式: {gif_info['filename']}")
                            result = self._download_and_save_video(gif_info, filename, is_video=True)
                        else:
                            print(f"⚠️ 检测到GIF格式: {gif_info['filename']}")
                            result = self._download_and_convert_gif(gif_info, filename)
                        
                        if result:
                            return result
            
            # 处理其他节点的视频输出
            for node_id, node_output in outputs.items():
                if node_id != "13" and "videos" in node_output:
                    print(f"🎬 处理Node {node_id}的videos输出...")
                    for video_info in node_output["videos"]:
                        result = self._download_and_save_video(video_info, filename)
                        if result:
                            return result
            
            print(f"❌ 无法通过API下载任何文件")
            return None
            
        except Exception as e:
            print(f"保存文件异常: {str(e)}")
            return None
    
    def _download_and_save_video(self, video_info: Dict, filename: str, is_video: bool = True) -> Optional[str]:
        """下载并保存视频文件"""
        try:
            video_url = f"{self.base_url}/view"
            params = {
                "filename": video_info["filename"],
                "subfolder": video_info.get("subfolder", ""),
                "type": video_info.get("type", "output")
            }
            
            print(f"尝试下载{'视频' if is_video else 'GIF'}: {video_info['filename']}")
            response = requests.get(video_url, params=params, timeout=30)
            
            if response.status_code == 200:
                # 直接保存为MP4格式
                save_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
                Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
                
                with open(save_path, "wb") as f:
                    f.write(response.content)
                
                # 验证文件
                if save_path.exists() and save_path.stat().st_size > 0:
                    file_size = save_path.stat().st_size
                    print(f"✅ {'视频' if is_video else 'GIF'}下载成功: {save_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    return str(save_path)
                else:
                    print(f"✗ 下载的文件为空或不存在")
            else:
                print(f"✗ 下载失败: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"下载文件异常: {str(e)}")
            return None
    
    def _download_and_convert_gif(self, gif_info: Dict, filename: str) -> Optional[str]:
        """下载GIF并转换为MP4"""
        try:
            gif_url = f"{self.base_url}/view"
            params = {
                "filename": gif_info["filename"],
                "subfolder": gif_info.get("subfolder", ""),
                "type": gif_info.get("type", "output")
            }
            
            print(f"尝试下载GIF: {gif_info['filename']}")
            response = requests.get(gif_url, params=params, timeout=30)
            
            if response.status_code == 200:
                # 先保存GIF文件
                temp_gif_path = Config.TEMP_DIR / f"temp_{filename}.gif"
                Config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
                
                with open(temp_gif_path, "wb") as f:
                    f.write(response.content)
                
                print(f"✅ GIF下载成功: {temp_gif_path}")
                
                # 尝试转换为MP4
                return self._convert_gif_to_mp4(temp_gif_path, filename)
            else:
                print(f"✗ GIF下载失败: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"下载GIF异常: {str(e)}")
            return None
    
    def _download_and_save_audio(self, audio_info: Dict, filename: str) -> Optional[str]:
        """下载并保存音频文件"""
        try:
            audio_url = f"{self.base_url}/view"
            params = {
                "filename": audio_info["filename"],
                "subfolder": audio_info.get("subfolder", ""),
                "type": audio_info.get("type", "output")
            }
            
            print(f"尝试下载音频: {audio_info['filename']}")
            response = requests.get(audio_url, params=params, timeout=30)
            
            if response.status_code == 200:
                # 保存为音频文件
                save_path = Config.AUDIO_DIR / f"{filename}.wav"
                Config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
                
                with open(save_path, "wb") as f:
                    f.write(response.content)
                
                # 验证文件
                if save_path.exists() and save_path.stat().st_size > 0:
                    file_size = save_path.stat().st_size
                    print(f"✅ 音频下载成功: {save_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    return str(save_path)
                else:
                    print(f"✗ 下载的文件为空或不存在")
            else:
                print(f"✗ 下载失败: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"下载音频异常: {str(e)}")
            return None
    
    def _convert_gif_to_mp4(self, gif_path: Path, filename: str) -> Optional[str]:
        """将GIF转换为MP4视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将GIF转换为MP4...")
            print(f"源文件: {gif_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg转换GIF为MP4
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-i', str(gif_path),  # 输入GIF文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                '-crf', '19',  # 质量参数
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ GIF转MP4成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时GIF文件
                    try:
                        gif_path.unlink()
                        print(f"✅ 清理临时GIF文件: {gif_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
                
                # 如果FFmpeg失败，尝试直接重命名GIF为MP4（作为备用方案）
                print(f"⚠️ 尝试备用方案：直接重命名GIF为MP4...")
                try:
                    import shutil
                    shutil.copy2(gif_path, output_path)
                    if output_path.exists():
                        print(f"✅ 备用方案成功: {output_path}")
                        return str(output_path)
                except Exception as e:
                    print(f"✗ 备用方案也失败: {str(e)}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg，尝试备用方案...")
            # 备用方案：直接复制文件
            try:
                import shutil
                output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
                shutil.copy2(gif_path, output_path)
                if output_path.exists():
                    print(f"✅ 备用方案复制成功: {output_path}")
                    return str(output_path)
            except Exception as e:
                print(f"✗ 备用方案复制失败: {str(e)}")
            return None
        except Exception as e:
            print(f"转GIF为MP4异常: {str(e)}")
            return None
    
    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None

    def _convert_image_to_video(self, image_path: Path, filename: str) -> Optional[str]:
        """将静态图片转换为视频"""
        try:
            import subprocess
            
            output_path = Config.VIDEO_CLIPS_DIR / f"{filename}.mp4"
            Config.VIDEO_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
            
            print(f"尝试使用FFmpeg将图片转换为视频...")
            print(f"源文件: {image_path}")
            print(f"目标文件: {output_path}")
            
            # 使用FFmpeg将静态图片转换为视频
            cmd = [
                'ffmpeg', '-y',  # -y 覆盖输出文件
                '-loop', '1',  # 循环播放图片
                '-i', str(image_path),  # 输入图片文件
                '-c:v', 'libx264',  # 使用H.264编码
                '-t', '5',  # 视频时长5秒
                '-pix_fmt', 'yuv420p',  # 像素格式
                '-r', '18',  # 帧率
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_size = output_path.stat().st_size
                    print(f"✅ 图片转视频成功: {output_path}")
                    print(f"文件大小: {file_size/1024/1024:.2f}MB")
                    
                    # 清理临时图片文件
                    try:
                        image_path.unlink()
                        print(f"✅ 清理临时图片文件: {image_path}")
                    except Exception as e:
                        print(f"⚠️ 清理临时文件失败: {str(e)}")
                    
                    return str(output_path)
                else:
                    print(f"✗ 转换后的文件为空或不存在")
            else:
                print(f"✗ FFmpeg转换失败")
                print(f"错误信息: {result.stderr}")
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"✗ FFmpeg转换超时")
            return None
        except FileNotFoundError:
            print(f"✗ 找不到FFmpeg")
            return None
        except Exception as e:
            print(f"图片转视频异常: {str(e)}")
            return None