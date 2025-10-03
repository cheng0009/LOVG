import requests
import json
import requests
from typing import List, Dict
from config import Config
from prompts_config import PromptsConfig

class LLMService:
    def __init__(self):
        self.api_key = Config.OPENAI_API_KEY
        self.base_url = Config.OPENAI_BASE_URL
        self.model = Config.OPENAI_MODEL
    
    def check_connection(self) -> bool:
        """检查LLM服务连接状态"""
        if not self.api_key or not self.base_url:
            return False
        
        try:
            # 发送一个简单的测试请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 5
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False
        
    def _clean_and_parse_json(self, content: str) -> Dict:
        """增强版JSON清理和解析逻辑"""
        import re
        
        # 策略列表：按优先级尝试不同的清理方法
        strategies = [
            self._extract_json_from_markdown,
            self._extract_json_from_code_blocks,
            self._clean_basic_json,
            self._extract_json_with_regex,
            self._fix_common_json_errors
        ]
        
        for strategy in strategies:
            try:
                cleaned = strategy(content)
                if cleaned:
                    data = json.loads(cleaned)
                    # 验证必要字段
                    if self._validate_script_data(data):
                        return data
            except (json.JSONDecodeError, Exception):
                continue
        
        return None
    
    def _extract_json_from_markdown(self, content: str) -> str:
        """从 markdown 代码块中提取 JSON"""
        if '```json' in content:
            parts = content.split('```json')
            if len(parts) > 1:
                json_part = parts[1].split('```')[0]
                return json_part.strip()
        return None
    
    def _extract_json_from_code_blocks(self, content: str) -> str:
        """从普通代码块中提取 JSON"""
        if '```' in content:
            parts = content.split('```')
            if len(parts) >= 3:
                # 获取第一个代码块
                code_block = parts[1].strip()
                # 去除可能的语言标识
                if code_block.startswith('json\n'):
                    code_block = code_block[5:]
                elif '\n' in code_block and code_block.split('\n')[0].strip() in ['json', 'JSON']:
                    code_block = '\n'.join(code_block.split('\n')[1:])
                return code_block.strip()
        return None
    
    def _clean_basic_json(self, content: str) -> str:
        """基本 JSON 清理"""
        # 寻找第一个 { 和最后一个 }
        start = content.find('{')
        end = content.rfind('}') + 1
        
        if start >= 0 and end > start:
            return content[start:end].strip()
        return None
    
    def _extract_json_with_regex(self, content: str) -> str:
        """使用正则表达式提取 JSON"""
        import re
        # 匹配从 { 开始到 } 结束的JSON结构
        pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                # 尝试解析每个匹配
                json.loads(match)
                return match
            except:
                continue
        return None
    
    def _fix_common_json_errors(self, content: str) -> str:
        """修复常见的 JSON 错误"""
        import re
        
        # 先获取基本 JSON 结构
        cleaned = self._clean_basic_json(content)
        if not cleaned:
            return None
        
        # 修复常见问题
        fixes = [
            # 移除末尾逗号
            (r',\s*}', '}'),
            (r',\s*]', ']'),
            # 修复单引号
            (r"'([^']*)'\s*:", r'"\1":'),
            # 移除注释
            (r'//.*?\n', '\n'),
            (r'/\*.*?\*/', ''),
            # 修复省略号
            (r'"\.\.\.",?', ''),
        ]
        
        for pattern, replacement in fixes:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL)
        
        return cleaned.strip()
    
    def _validate_script_data(self, data: Dict) -> bool:
        """验证脚本数据的必要字段"""
        required_fields = ['video_script', 'audio_script', 'storyboard_prompts', 'video_prompts']
        return isinstance(data, dict) and all(field in data for field in required_fields)

    def generate_scripts(self, topic: str, settings: Dict = None) -> Dict:
        """生成视频脚本和配音脚本"""
        # 使用配置文件中的提示词模板
        prompt = PromptsConfig.get_script_generation_prompt(topic, settings)
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 尝试解析JSON - 增强版解析逻辑
                try:
                    # 多种策略清理和解析JSON
                    cleaned_content = self._clean_and_parse_json(content)
                    if cleaned_content:
                        return {
                            'success': True,
                            'data': cleaned_content
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'JSON解析失败',
                            'raw_content': content
                        }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'JSON解析异常: {str(e)}',
                        'raw_content': content
                    }
            else:
                return {
                    'success': False,
                    'error': f'API请求失败: {response.status_code}',
                    'details': response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': '请求超时，请检查网络连接'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'网络请求错误: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'未知错误: {str(e)}'
            }
    
    def optimize_prompt(self, original_prompt: str, prompt_type: str = "image") -> str:
        """优化提示词"""
        # 使用配置文件中的提示词模板
        if prompt_type == "image":
            prompts = PromptsConfig.get_image_optimization_prompts(original_prompt)
            system_prompt = prompts['system']
            user_prompt = prompts['user']
        else:
            prompts = PromptsConfig.get_video_optimization_prompts(original_prompt)
            system_prompt = prompts['system']
            user_prompt = prompts['user']
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                return original_prompt
                
        except Exception:
            return original_prompt
    
    def translate_to_english(self, chinese_text: str) -> str:
        """将中文文本翻译成英文"""
        if not chinese_text.strip():
            return chinese_text
            
        # 构造翻译提示词
        system_prompt = "你是一个专业的翻译员，请将用户提供的中文文本准确翻译成英文，保持原意不变。"
        user_prompt = f"请将以下中文翻译成英文：\n\n{chinese_text}"
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                translated_text = result['choices'][0]['message']['content'].strip()
                # 移除可能的引号
                if translated_text.startswith('"') and translated_text.endswith('"'):
                    translated_text = translated_text[1:-1]
                return translated_text
            else:
                print(f"翻译API调用失败: {response.status_code}")
                return chinese_text  # 翻译失败时返回原文
                
        except Exception as e:
            print(f"翻译失败: {str(e)}")
            return chinese_text  # 异常时返回原文