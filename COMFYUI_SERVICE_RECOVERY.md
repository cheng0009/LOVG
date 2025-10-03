# ComfyUI服务自动恢复和监控方案

## 问题分析
ComfyUI服务在处理AI视频生成任务时频繁自动退出，主要原因包括：
1. 系统资源不足（内存、CPU）
2. 服务连接中断（WinError 10061）
3. 变量名冲突导致的运行时错误

## 解决方案

### 1. 连接错误处理和自动恢复
在 [services/comfyui_service.py](file://d:/AI_VEdio/services/comfyui_service.py) 中实现了：

#### 错误检测
```python
# 检测连接错误
if "WinError 10061" in str(e) or "Failed to establish a new connection" in str(e):
    print("🚨 ComfyUI服务连接失败，尝试检查服务状态...")
    self._attempt_service_recovery()
```

#### 自动恢复机制
```python
def _attempt_service_recovery(self):
    """尝试恢复ComfyUI服务"""
    # 1. 等待服务可能的自动恢复
    time.sleep(10)
    
    # 2. 检查服务是否恢复
    if self.check_connection():
        return True
    
    # 3. 建议用户手动重启并继续等待
    print("⚠️ ComfyUI服务仍未恢复，请手动重启ComfyUI服务")
    
    # 4. 继续等待服务恢复（最长2分钟）
    for i in range(12):
        time.sleep(10)
        if self.check_connection():
            return True
```

### 2. 变量名冲突修复
修复了 `_copy_image_to_comfyui` 方法中的变量名冲突问题：

```python
# 修复前 - 错误的变量名使用
import time
timestamp = int(time.time() * 1000)  # 这里会覆盖time模块

# 修复后 - 使用别名避免冲突
import time as time_module
timestamp = int(time_module.time() * 1000)
```

### 3. ComfyUI监控器
创建了独立的 [comfyui_monitor.py](file://d:/AI_VEdio/comfyui_monitor.py) 脚本，提供：

#### 服务状态检查
```python
def check_service_status(self) -> bool:
    """检查ComfyUI服务状态"""
    try:
        response = requests.get(f"{self.base_url}/system_stats", timeout=5)
        return response.status_code == 200
    except:
        return False
```

#### 自动重启功能
```python
def restart_comfyui(self) -> bool:
    """重启ComfyUI服务"""
    # 1. 停止现有进程
    self.stop_comfyui()
    
    # 2. 等待进程完全停止
    time.sleep(5)
    
    # 3. 启动新的ComfyUI进程
    comfyui_path = Path("F:/ComfyUI_windows_portable/ComfyUI_windows_portable.exe")
    self.comfyui_process = subprocess.Popen([str(comfyui_path)], 
                                           cwd=comfyui_path.parent)
    
    # 4. 等待服务启动（最长5分钟）
    for i in range(30):
        time.sleep(10)
        if self.check_service_status():
            return True
```

### 4. 资源优化器增强
在 [services/resource_optimizer.py](file://d:/AI_VEdio/services/resource_optimizer.py) 中添加了ComfyUI服务监控：

#### ComfyUI状态监控
```python
def _check_comfyui_status(self):
    """检查ComfyUI服务状态"""
    try:
        response = requests.get(f"{self.comfyui_base_url}/system_stats", timeout=3)
        if response.status_code != 200:
            print("⚠️ ComfyUI服务响应异常")
    except requests.exceptions.ConnectionError:
        print("❌ ComfyUI服务连接失败")
    except Exception as e:
        print(f"⚠️ ComfyUI服务检查异常: {e}")
```

## 使用方法

### 1. 自动集成
ComfyUI服务现在具备自动恢复能力，在检测到连接错误时会：
1. 等待服务可能的自动恢复
2. 检查服务状态
3. 建议用户手动重启
4. 继续等待服务恢复

### 2. 独立监控工具
运行独立监控脚本：
```bash
python comfyui_monitor.py
```

功能包括：
- 实时监控ComfyUI服务状态
- 系统资源使用情况检查
- 自动重启服务功能
- 持续监控模式

### 3. 资源优化器
资源优化器在后台持续运行：
```python
# 启动ComfyUI服务监控
resource_optimizer.start_comfyui_monitoring()

# 停止ComfyUI服务监控
resource_optimizer.stop_comfyui_monitoring()
```

## 最佳实践建议

### 预防措施
1. **系统资源管理**：
   - 确保系统有足够内存（推荐16GB以上）
   - 关闭不必要的后台程序
   - 定期清理系统垃圾文件

2. **ComfyUI配置优化**：
   - 使用便携版ComfyUI减少系统依赖
   - 定期更新模型文件
   - 避免同时运行多个AI服务

### 故障处理
1. **连接错误处理**：
   - 等待自动恢复（通常10-30秒）
   - 如果自动恢复失败，手动重启ComfyUI
   - 检查防火墙设置确保端口畅通

2. **内存不足处理**：
   - 执行强制资源清理
   - 减少并发处理任务
   - 增加虚拟内存设置

### 监控建议
1. **启用持续监控**：
   ```bash
   python comfyui_monitor.py
   ```
   
2. **定期检查资源使用**：
   - 内存使用率应保持在85%以下
   - CPU使用率应保持在80%以下

3. **日志分析**：
   - 定期查看错误日志
   - 分析资源使用峰值
   - 优化处理批次大小

## 测试验证

### 连接恢复测试
1. 手动停止ComfyUI服务
2. 观察自动恢复机制
3. 验证服务重新连接

### 资源优化测试
1. 运行批量视频生成任务
2. 监控内存使用情况
3. 验证自动清理功能

### 变量冲突修复验证
1. 运行包含时间戳处理的任务
2. 确认无变量名冲突错误
3. 验证文件名生成正确性

## 未来优化方向

1. **智能调度**：根据系统负载动态调整批处理大小
2. **GPU监控**：扩展监控范围到GPU内存使用
3. **分布式处理**：支持多机器分布式视频生成
4. **预测性维护**：基于历史数据预测服务故障
5. **自动扩容**：云环境下自动增加计算资源