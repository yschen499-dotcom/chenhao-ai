# AI Resume Portfolio

一个基于静态 HTML / CSS / JavaScript 的单页简历作品集，适合把传统 PDF 简历升级成更有展示感的网页版本。

## 线上访问与二维码

- GitHub Pages 目标地址：`https://yschen499-dotcom.github.io/test_dingdingtest_dingding/`
- 仓库启用 GitHub Pages 后，工作流会自动把当前静态站发布到这个地址
- 二维码图片：`assets/resume-qr.png`

## 文件结构

- `index.html`：页面结构与内容
- `styles.css`：视觉样式与响应式布局
- `script.js`：滚动动效、导航高亮、关键词轮播
- `.github/workflows/deploy-pages.yml`：自动部署到 GitHub Pages

## 本地预览

直接用浏览器打开 `index.html` 即可，或者在仓库根目录执行：

```bash
python3 -m http.server 8000
```

然后访问 `http://localhost:8000`

## 后续可继续升级

- 增加 GitHub / 项目仓库链接
- 补充嵌入式课程设计、实验作品或比赛经历
- 增加中英双语切换
- 增加 PDF 下载按钮或二维码入口