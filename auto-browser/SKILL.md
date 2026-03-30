---
name: auto-browser
description: agent-browser + VNC 协同。自动化 + 人工接管共享同一 Chrome/CDP 会话。
---

# auto-browser

这个 skill 面向 **agent 内部执行**。下面的命令是给 agent 的，不是让用户手动在终端里运行。

## 固定变量

```bash
VRD=~/.nanobot/workspace/skills/auto-browser/scripts/vrd.py
STATE=$HOME/.openclaw/vrd-data/state.json
```

## 核心原则

- 所有浏览器操作用 `agent-browser` 完成，不要截图分析
- 只有验证码、扫码、风控拦截才启动 VNC 让用户接管
- 始终用 `--session vrd --cdp 9222`，不要开新浏览器实例
- 复用现有会话，不要反复 start/stop

## 启动流程（严格按顺序）

### 1. 检查状态

```bash
python3 $VRD status
```

- 正常运行 → 直接跳到"操作页面"
- 未运行 → 执行第 2 步
- `chrome: down` 但其他正常 → 执行健康恢复（见下方故障处理）

### 2. 启动全栈

```bash
KASM_BIND=0.0.0.0 python3 $VRD start >/tmp/vrd-start.log 2>&1
```

### 3. 读取公网链接和 token

```bash
python3 -c "import json; d=json.load(open('$STATE')); print('URL:', d.get('PUBLIC_URL','')); print('TOKEN:', d.get('SWITCH_TOKEN',''))"
```

拿到 URL 之前不要给用户发消息。TOKEN 在调用控制面 API 时使用。

## 操作页面（agent-browser）

```bash
# 核心循环：snapshot → 操作 → snapshot 验证
agent-browser --cdp 9222 --session vrd snapshot
agent-browser --cdp 9222 --session vrd open <url>
agent-browser --cdp 9222 --session vrd click <ref>
agent-browser --cdp 9222 --session vrd fill <ref> <text>
agent-browser --cdp 9222 --session vrd wait --load networkidle
agent-browser --cdp 9222 --session vrd tab new <url>
agent-browser --cdp 9222 --session vrd upload <ref> <files>
agent-browser --cdp 9222 --session vrd get text <ref>
agent-browser --cdp 9222 --session vrd get url
agent-browser --cdp 9222 --session vrd screenshot [path]  # 仅给用户看，不用来分析
```

## 人工接管（扫码/验证码/确认）

需要用户手动操作时，agent 应自己完成引导、轮询和恢复；用户只需要在远程浏览器里完成扫码、验证码或确认动作：

```bash
# 1. 读取 token
TOKEN=$(python3 -c "import json; print(json.load(open('$STATE')).get('SWITCH_TOKEN',''))")

# 2. 设置引导提示
curl -s -X POST "http://127.0.0.1:6090/guide?token=$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"请扫码登录，完成后点击底部「已完成」","kind":"action"}'

# 3. 把 PUBLIC_URL 发给用户，等用户操作完成
curl -s "http://127.0.0.1:6090/continue/poll?token=$TOKEN&after=0&timeout=30"

# 4. 清引导、继续
curl -s -X DELETE "http://127.0.0.1:6090/guide?token=$TOKEN"
agent-browser --cdp 9222 --session vrd snapshot
```

识别为"人工完成"的信号：

- 用户点了 VNC 页面的"已完成，继续"
- 用户在对话里说"已完成""好了""可以继续"等

收到信号后直接 `snapshot` 校验，不要让用户描述页面。

## 安全闸门（高风险操作前确认）

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('$STATE')).get('SWITCH_TOKEN',''))")
# 发起确认
curl -s -X POST "http://127.0.0.1:6090/gate?token=$TOKEN" -d '{"prompt":"确认提交？"}'
# 轮询结果（approved: null=等待 / true=确认 / false=取消）
curl -s "http://127.0.0.1:6090/gate?token=$TOKEN"
# 清理
curl -s -X DELETE "http://127.0.0.1:6090/gate?token=$TOKEN"
```

## 设备切换

```bash
python3 $VRD switch mobile
# 可选：desktop / mobile / iphone-safari / tablet / wechat-h5 / android-chrome
```

切换后 `agent-browser --cdp 9222 --session vrd snapshot` 再继续。

## 收尾

判断后续**不再需要浏览器**时立即停止：

```bash
python3 $VRD stop
```

保留浏览器的场景：还要继续操作网页、读取页面结果、等用户再次接管。

## 导出登录态

当用户已经在当前 VRD 浏览器里完成登录，需要把会话交给其他工具复用时，agent 应在内部导出当前会话：

```bash
python3 $VRD export-session linkedin /path/to/linkedin.session.json
```

导出文件是一个包装后的 `storage_state` JSON，可直接交给 `social-data-crawler` 的 `--cookies` 参数使用。

推荐协同方式：

1. agent 调起 `auto-browser`
2. agent 打开目标登录页并等待用户完成人工接管
3. agent 在收到“已完成”信号后执行 `export-session`
4. agent 把导出的会话文件继续交给下游 skill 使用

## 其他工具

```bash
# 截图
python3 $VRD screenshot [label]

# 剪贴板注入
python3 $VRD clipboard set "验证码123456"

# 健康检查（自动恢复 x11vnc 和 Chrome）
TOKEN=$(python3 -c "import json; print(json.load(open('$STATE')).get('SWITCH_TOKEN',''))")
curl -s "http://127.0.0.1:6090/health?token=$TOKEN"
```

## 故障处理

| 问题 | 解法 |
| ------ | ------ |
| `chrome: down` | 调用健康检查自动恢复：`curl -s "http://127.0.0.1:6090/health?token=$TOKEN"`；或手动重启：`curl -s -X POST "http://127.0.0.1:6090/switch?token=$TOKEN" -H "Content-Type: application/json" -d '{"mode":"desktop"}'` |
| `agent-browser: command not found` | `python3 $VRD check` 会自动安装并 symlink 到 PATH |
| VRD 整体未运行 | 执行启动流程第 2 步 |
| Cloudflare tunnel 拿不到 URL | 检查网络后 `python3 $VRD stop && KASM_BIND=0.0.0.0 python3 $VRD start` 重启 |
| `SingletonLock` 错误 | 复用已有 9222 会话，不要再开新 Chrome |

## AI 执行约束

- **不把命令贴给用户**，只汇报进度和需要用户做的动作
- **不截图分析**，所有页面理解通过 `snapshot` 完成
- 用户完成接管后直接 `snapshot`，不要求用户描述页面
- 不再需要浏览器时立即 `stop`
- 始终用 `--session vrd --cdp 9222`
- 导出登录态后由 agent 继续消费会话文件，不要求用户再执行任何 CLI 命令
