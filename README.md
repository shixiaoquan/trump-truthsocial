# Trump Truth Social

定时抓取 Truth Social 上 Trump 发布内容的镜像网站。

## 功能

- 每30分钟自动抓取 Trump 的最新帖子
- 中文翻译（Google Translate）默认显示
- 支持切换显示原文/译文
- 图片和视频媒体展示
- 响应式深色主题设计

## 技术栈

- 前端：纯 HTML/CSS/JavaScript
- 抓取：Python + cloudscraper
- 部署：GitHub Pages
- 自动化：GitHub Actions

## 部署

1. Fork 本仓库
2. 在 Settings > Pages 中启用 GitHub Pages（Source: main branch）
3. 等待 GitHub Actions 完成首次抓取
4. 访问 `https://<username>.github.io/trump-truthsocial/`
