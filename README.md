# AI WeChat Digest

一个小型 Python 应用：定期抓取计算机和 AI 相关 RSS/Atom 内容，挑选一条未发送过的知识或新闻，通过企业微信/微信群机器人 webhook 发送，并用 SQLite 避免重复发送。

## 1. 配置

```bash
cd ~/ai-wechat-digest
cp config.example.json config.json
```

在企业微信里添加「群机器人」，复制 webhook 地址，填到 `config.json` 的 `wecom_bot_webhook`，或用环境变量：

```bash
export WECOM_BOT_WEBHOOK='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...'
```

为了把链接里的正文提取出来、翻译成中文并整合成通俗解释，还需要配置 Kimi/Moonshot API Key：

```bash
export MOONSHOT_API_KEY='sk-...'
```

也可以把 key 写进 `config.json` 的 `llm_api_key`。如果使用 launchd 后台定时运行，推荐写进 `config.json`，因为 launchd 不会自动继承你当前终端里 export 的环境变量。

如果没有配置 Kimi API Key，应用仍会发送内容，但只发送内置中文知识，避免把英文 RSS 摘要直接发到群里。

国内 Kimi 开放平台通常使用：

```json
"llm_base_url": "https://api.moonshot.cn/v1"
```

如果你的 key 来自国际站，改成：

```json
"llm_base_url": "https://api.moonshot.ai/v1"
```

个人微信没有稳定官方的自动发消息 API。这个应用默认使用企业微信/微信群机器人 webhook，是最稳的微信系接入方式。

## 2. 试运行

```bash
python3 app.py --dry-run
```

确认内容没问题后发送一次：

```bash
python3 app.py
```

已发送记录保存在 `sent.sqlite3`，之后不会重复发送同一条链接/标题。

## 3. 定时运行

macOS 推荐用 `launchd`。先把 `launchd/com.ai-wechat-digest.plist.example` 复制成正式 plist，并把 `WECOM_BOT_WEBHOOK` 改成你的 webhook：

```bash
cp launchd/com.ai-wechat-digest.plist.example ~/Library/LaunchAgents/com.ai-wechat-digest.plist
launchctl load ~/Library/LaunchAgents/com.ai-wechat-digest.plist
```

默认每 1 小时运行一次。修改 plist 里的 `StartInterval` 可以调整频率，单位是秒。

查看日志：

```bash
tail -f ~/ai-wechat-digest/digest.log
tail -f ~/ai-wechat-digest/digest.err.log
```

停止定时任务：

```bash
launchctl unload ~/Library/LaunchAgents/com.ai-wechat-digest.plist
```
