# AI Resume Portfolio

一个基于静态 HTML / CSS / JavaScript 的单页简历作品集，适合把传统 PDF 简历升级成更有展示感的网页版本。

## 线上访问与二维码

- GitHub Pages 目标地址：`https://yschen499-dotcom.github.io/chenhao-ai/`
- 仓库启用 GitHub Pages 后，工作流会自动把当前静态站发布到这个地址
- 二维码图片：`assets/chenhao-ai-portfolio-qr.png`
- 分享封面图：`assets/chenhao-ai-portfolio-cover.png`
- PDF 简历文件：`assets/chenhao-ai-portfolio-resume.pdf`
- 证件照占位文件：`assets/profile-photo.png`（后续可直接替换成原始证件照）

## 文件结构

- `index.html`：页面结构与内容
- `styles.css`：视觉样式与响应式布局
- `script.js`：滚动动效、导航高亮、关键词轮播
- `resume-pdf.html`：A4 排版的 PDF 简历页面
- `resume-pdf.css`：PDF 简历样式
- `.github/workflows/deploy-pages.yml`：自动部署到 GitHub Pages

## 本地预览

直接用浏览器打开 `index.html` 即可，或者在仓库根目录执行：

```bash
python3 -m http.server 8000
```

然后访问 `http://localhost:8000`

## 重新生成 PDF

仓库根目录执行：

```bash
google-chrome --headless --disable-gpu --no-sandbox --allow-file-access-from-files --print-to-pdf="assets/chenhao-ai-portfolio-resume.pdf" "file:///workspace/resume-pdf.html"
```

## 后续可继续升级

- 增加 GitHub / 项目仓库链接
- 补充嵌入式课程设计、实验作品或比赛经历
- 增加中英双语切换
- 增加 PDF 下载按钮或二维码入口