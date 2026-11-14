# 🏸 羽毛球实时比分

实时追踪 BWF 世界巡回赛等羽毛球赛事的进行中比赛、轮次与逐局比分。

## 功能

- **实时比分**：进行中比赛的大比分 + 逐局小分，当前局红色高亮
- **轮次显示**：自动识别半决赛 / 决赛等轮次（中文显示）
- **三态标签**：🔴 进行中 / ⏰ 未开始（含开赛时间）/ ✅ 已结束
- **自动刷新**：前端每 15 秒拉取，后端每 20 秒重新抓取，标签页标题实时显示进行中场数
- **移动端适配**：卡片式界面，手机浏览器体验友好

## 技术方案

Flashscore 无公开比分接口，本项目：

1. **Playwright 无头浏览器**渲染 Flashscore 羽毛球首页，从 WebSocket 推送后的 DOM 中解析全部比赛（进行中/未开始/已结束）
2. **requests** 抓取比赛详情页静态 HTML（`og:description`）补充轮次信息（带缓存）
3. **Flask** 聚合输出 `/api/live` JSON 接口 + 前端单页

## 本地运行

```bash
# 1. 安装依赖
pip install flask playwright requests
playwright install chromium

# 2. 启动（Chrome/Chromium 路径自动探测，也可用环境变量 CHROME_PATH 指定）
python app.py

# 3. 打开
http://127.0.0.1:8000
```

> 注意：本地运行需要你的网络能访问 `flashscore.com`。

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `PORT` | 8000 | 服务端口 |
| `CHROME_PATH` | 自动探测 | Chrome/Chromium 可执行文件路径 |

## 项目结构

```
badminton-live/
├── app.py              # 后端：抓取 + Flask API
└── static/
    └── index.html      # 前端：比分看板（移动端优先）
```

## 免责声明

数据来源于 Flashscore 公开页面，仅供个人学习与观赛参考。
