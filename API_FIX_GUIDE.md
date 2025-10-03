"""
AI视频生成器 - API密钥配置指南

## 问题: 401 认证错误

### 解决方案1: 更新环境变量（推荐）
1. 获取有效的DeepSeek API密钥:
   - 访问 https://platform.deepseek.com/
   - 注册并获取API密钥

2. 设置环境变量:
   PowerShell:
   $env:OPENAI_API_KEY="your_valid_deepseek_api_key"
   
   或永久设置:
   [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "your_valid_deepseek_api_key", "User")

### 解决方案2: 直接修改配置文件
编辑 config.py 文件:
OPENAI_API_KEY = "your_valid_deepseek_api_key"

### 解决方案3: 使用其他API提供商
如果您有其他API密钥，可以修改:
- config.py 中的 OPENAI_BASE_URL
- services/llm_service.py 中的模型名称

### 支持的API提供商:
1. DeepSeek: https://api.deepseek.com (模型: deepseek-chat)
2. OpenAI: https://api.openai.com (模型: gpt-4, gpt-3.5-turbo)
3. 其他兼容OpenAI格式的API

### 测试API连接:
运行 test_llm_fix.py 来验证修复效果
"""