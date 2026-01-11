# Bright Data 代理配置指南

本文档介绍了如何在 AsterDEX 多钱包管理系统中配置和使用 Bright Data 代理服务。

## 概述

Bright Data 是一个强大的代理服务提供商，提供住宅代理、数据中心代理、移动代理等多种类型的代理IP。相比之前的 Decodo 代理，Bright Data 通常具有更低的延迟和更高的稳定性。

## 配置步骤

### 1. 环境变量配置

在 `.env` 文件中添加以下配置（使用您的实际账户信息）：

```env
# Bright Data 配置
BRIGHTDATA_ENABLED=true
BRIGHTDATA_CUSTOMER=brd-customer-hl_5e1f2ce5-zone-aster  # 您的实际客户名
BRIGHTDATA_PASSWORD=jlfm7ayb6puo  # 您的实际密码
BRIGHTDATA_HOST=brd.superproxy.io
BRIGHTDATA_PORT=33335  # 您的实际端口号
BRIGHTDATA_ZONE=aster
BRIGHTDATA_SESSION_DURATION=60
```

### 2. 系统配置

通过管理员面板或直接在数据库中设置系统配置：

- `brightdata_enabled`: 设为 `true` 启用 Bright Data 代理


### 3. 代理类型

Bright Data 支持以下代理类型：

- `residential` (住宅代理) - 推荐用于生产环境
- `datacenter` (数据中心代理) - 速度更快，成本较低
- `mobile` (移动代理) - 模拟移动设备IP
- `isp` (ISP代理) - 通过ISP提供的IP

## 实现细节

### 代理选择逻辑

系统按照以下优先级选择代理：

1. **Bright Data** (最高优先级) - 如果启用
2. **全局代理** (最低优先级) - 开发环境用

### 会话管理

- 每个任务获得独立的代理会话
- 会话ID基于任务ID生成，格式为 `task{task_id:04d}`
- 会话在任务完成后自动释放

## 优势

- **低延迟**: Bright Data 通常比其他代理服务延迟更低
- **高稳定性**: 更少的连接超时和错误
- **丰富IP池**: 大量高质量IP资源
- **地理位置控制**: 支持指定国家、地区、城市
- **并发能力强**: 支持大量并发连接

## 故障排除

### 常见问题

1. **代理连接失败**:
   - 检查用户名和密码是否正确
   - 确认客户名格式是否正确 (应为 `customer-xxx` 格式)
   - 检查端口是否正确 (通常是 22225)

2. **IP地理位置不符**:
   - Bright Data 使用智能路由，可能不完全按照指定地区
   - 如需精确地理位置，可在用户名中添加区域参数

3. **性能问题**:
   - 尝试切换到不同类型的代理 (数据中心 vs 住宅)
   - 联系 Bright Data 支持以优化配置

## 安全注意事项

- 将 Bright Data 凭证存储在安全的位置
- 定期更换密码
- 监控代理使用情况，防止滥用
- 在生产环境中禁用不必要的代理类型

## 测试

使用以下命令测试 Bright Data 代理连接：

```bash
python utils/tests/proxy_connection_test.py
```

或直接运行 Bright Data 管理器测试：

```bash
python utils/bright_data_manager.py
```