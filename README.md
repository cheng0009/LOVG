# 🎬 AI视频生成器

一个基于AI的完整视频生成系统，从文字主题到最终视频成品的一站式解决方案。

<img width="3696" height="1791" alt="image" src="https://github.com/user-attachments/assets/428bf101-301d-4abf-9996-60936b32f732" />

<img width="3742" height="1816" alt="image" src="https://github.com/user-attachments/assets/5bece8bd-c176-4a63-8324-3c5f337ebb83" />

<img width="3721" height="1739" alt="image" src="https://github.com/user-attachments/assets/421259d9-c60f-45c2-8ab4-eee1d4950498" />


## 🚀 快速开始

### 演示版本（推荐首次体验）
```bash
# 直接运行演示版本，无需任何依赖
streamlit run simple_demo.py
```

### 完整版本
```bash
# Windows用户
start.bat

# 手动启动
pip install -r requirements.txt
streamlit run main.py
```

### 优化版本（解决内存问题）
```bash
# 安装额外依赖并启动优化版本
python start_optimized.py
```

## 🎯 项目特色

- 🎬 **一键生成**：输入主题，自动生成完整视频
- 📝 **智能脚本**：AI自动生成视频脚本和配音稿
- 🖼️ **分镜图生成**：基于ComfyUI的高质量图像生成
- 🎥 **视频制作**：图片转视频，支持动画效果
- 🎵 **音频合成**：TTS语音合成和音频混合（默认使用增强版TTS服务）
- 📊 **可视化控制**：每步可预览、编辑和重新生成
- ✏️ **精细控制**：每个分镜图和视频片段都可单独编辑重生成
- 💾 **内存优化**：分批处理大量视频，避免内存溢出
- 🔁 **重试机制**：自动重试失败的视频生成任务
- 📈 **资源监控**：实时监控系统资源使用情况
- 🛠️ **错误修复**：解决第6步音视频合并、字幕添加等常见问题
- 🎯 **精确字幕同步**：默认使用增强版TTS服务生成精确时间戳字幕

## 🏗️ 系统架构

```text
AI视频生成器
├── 用户输入主题
├── LLM生成脚本和提示词
├── ComfyUI生成分镜图
├── ComfyUI图转视频
├── TTS生成配音（增强版TTS服务）
└── 视频合成输出
```

## 📁 项目结构

```text
AI_VEdio/
├── main.py                 # 主应用（完整版）
├── simple_demo.py          # 演示版本
├── start_optimized.py      # 优化版启动脚本
├── app_steps.py            # 应用步骤模块
├── config.py               # 配置文件
├── requirements.txt        # 依赖包列表
├── start.bat              # Windows启动脚本
├── enhanced_tts_service.py # 增强版TTS服务
├── workflows/             # ComfyUI工作流文件
│   ├── ▶Flux kontext dev_参考图备份.json
│   ├── ▶Wan2.2-AllInOne图生视频流.json
│   └── Index-TTSV20-单人情感对话.json
├── services/              # 服务模块
│   ├── llm_service.py     # LLM服务
│   ├── comfyui_service.py # ComfyUI服务
│   ├── tts_service.py     # TTS服务
│   └── video_service.py   # 视频处理服务
└── outputs/               # 输出目录
    ├── storyboards/       # 分镜图
    ├── video_clips/       # 视频片段
    ├── audio/            # 音频文件
    └── final_videos/     # 最终视频
```

## 🧪 功能演示

### 分镜图和视频片段可视化展示
- 分镜图直接在页面上展示（而不是链接）
- 视频片段直接在页面上播放展示
- 每个元素都有独立的控制按钮

### 精细化控制功能
- 每个分镜图都有：重新生成、删除、编辑提示词按钮
- 每个视频片段都有：重新生成、删除、编辑动作提示词按钮
- 支持单独重新生成任意分镜图或视频片段
- 实时编辑提示词并立即重新生成

### 一键生成功能
- 输入主题后一键自动完成整个流程
- 实时进度条显示生成状态
- 自动跳转到结果展示页面

## ⚙️ 配置要求

### 环境依赖
- Python 3.8+
- ComfyUI服务（运行在127.0.0.1:8188端口）
- OpenAI API密钥（或兼容的API服务）
- TTS服务（可选，可用ComfyUI替代）

### Python依赖包
```txt
streamlit>=1.28.0
requests>=2.31.0
pillow>=10.0.0
opencv-python>=4.8.0
moviepy>=1.0.3
pydub>=0.25.1
openai>=1.0.0
websocket-client>=1.6.0
numpy>=1.24.0
psutil>=5.9.0
```

## 📖 使用指南

### 1. 启动服务
1. 启动ComfyUI服务并确保运行在 `127.0.0.1:8188` 端口
2. 配置OpenAI API密钥（在 `config.py` 中设置）
3. （可选）启动TTS服务

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 运行应用
```bash
# 运行完整版本
streamlit run main.py

# 或运行演示版本（无需外部依赖）
streamlit run simple_demo.py
```

### 4. 使用流程
1. 在浏览器中打开应用（通常是 http://localhost:8501）
2. 输入视频主题
3. 选择生成模式：
   - 点击"生成脚本"进入逐步模式
   - 点击"一键生成完整视频"体验自动化流程
4. 在每个步骤中预览和调整生成内容

### 5. 定制二开服务
1. 联系wechat：zhiweizhiyuan（备注：github）
2. 关注公众号：老成教你玩互联网，获取更多AI黑科技软件！
   
## ❓ 常见问题

### Q: ComfyUI连接失败
A: 请确保ComfyUI服务已启动并运行在127.0.0.1:8188端口

### Q: 生成的图片质量不好
A: 可以在界面中编辑提示词，或者调整ComfyUI工作流参数

### Q: 视频生成很慢
A: 这是正常的，视频生成需要大量计算资源，建议使用GPU加速

### Q: API调用失败
A: 请检查网络连接和API密钥配置

### Q: ComfyUI在批量生成视频时自动退出
A: 这是由于内存不足导致的。系统已实现以下优化：
   - 分批处理机制（每次只处理1个视频）
   - 智能内存管理（定期垃圾回收）
   - 增强的错误处理和重试机制
   - 系统资源监控
   - 更长的超时设置

### Q: 第6步音视频合并、字幕添加失败
A: 系统已修复以下问题：
   - 音频循环方法兼容性问题
   - 字幕添加路径为空的问题
   - 封面添加文件不存在的问题
   - 提供多重降级方案确保功能可用

### Q: 为什么必须上传参考音频？
A: 系统默认使用增强版TTS服务，需要参考音频来克隆声音特征，生成高质量且与参考音频音色一致的配音。

### Q: 字幕与音频不同步怎么办？
A: 系统默认使用增强版TTS服务生成精确时间戳字幕，确保字幕与音频完全同步。如果仍有问题，请检查参考音频质量和ComfyUI TTS工作流配置。

## 🛠️ 开发指南

### 添加新的服务
1. 在 `services/` 目录创建新的服务文件
2. 继承基础服务类，实现必要方法
3. 在 `main.py` 中注册新服务

### 自定义工作流
1. 在ComfyUI中设计新的工作流
2. 导出工作流JSON文件到 `workflows/` 目录
3. 在相应的服务文件中添加工作流处理逻辑

### 扩展功能
1. 在 `app_steps.py` 中添加新的步骤函数
2. 在主应用中注册新的步骤
3. 更新UI界面和状态管理逻辑

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📅 更新日志

### v1.3.0
- 默认使用增强版TTS服务
- 强制要求上传参考音频以确保配音质量
- 实现精确时间戳字幕生成功能
- 优化音频处理和字幕同步逻辑

### v1.2.0
- 修复第6步音视频合并、字幕添加、封面添加等问题
- 增强错误处理和降级方案
- 优化音频循环和字幕添加逻辑

### v1.1.0
- 实现内存优化和批处理机制
- 解决ComfyUI批量视频生成时自动退出的问题
- 增强错误处理和重试机制
- 添加系统资源监控功能

### v1.0.0
- 初始版本发布
- 支持完整的视频生成流程
- Web界面交互
- ComfyUI集成
