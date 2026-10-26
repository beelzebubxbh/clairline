# 长龙航线 · 智能大盘与航网规划助手

[![GitHub Repo](https://img.shields.io/badge/GitHub-eureka--wu%2Fclairline-blue?logo=github)](https://github.com/eureka-wu/clairline)
[![Vue 3](https://img.shields.io/badge/Frontend-Vue%203%20%2B%20Vite-42b883?logo=vuedotjs)](https://vuejs.org/)
[![Python 3](https://img.shields.io/badge/Backend-Python%203%20%2B%20SQLite3-3776ab?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%2F%20Web-0078d4?logo=windows)](https://github.com/eureka-wu/clairline)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> 一款专为长龙航空旅客与常旅客打造的**纯本地、高颜值、现代化全景航网探索与智能兑换决策平台**。  
> 实时全景可视化中国航线网、近 60 天长龙官方放票动态日历、高铁周边延伸接驳漫游、余票持久化与自动化后台巡检。  
> **官方开源仓库**：[https://github.com/eureka-wu/clairline](https://github.com/eureka-wu/clairline)

---

## 🛡️ 纯本地开源理念 (100% Local & Privacy-First)

本项目遵循**纯本地单机运行**与**隐私绝对隔离**原则：
1. **零第三方云端上报**：所有航网数据、放票日历、查验流水、巡检配置以及个人凭据 **100% 保存在用户本机**，无任何外部遥测或第三方数据回传；
2. **端到端完全开源可审计**：前后端所有源代码公开透明在 [GitHub 仓库](https://github.com/eureka-wu/clairline)，绝无后门，安全可靠；
3. **敏感凭据物理隔离**：个人账号 Token、查票记录与 SQLite 数据库已配置严格的 Git 忽略策略，绝不随代码提交；新用户冷启动自动植入官方直飞航线种子，开箱立用；
4. **系统代理安全闭环**：嗅探仅针对长龙官方域名，结束后全自动关闭恢复 Windows 系统代理，绝不干扰外部网络与 IDE。

---

## 📸 界面预览

### 🗺️ 航网地图探索（全屏沉浸大屏）
以指定城市（如杭州、广州）为出发地的全屏航网：绿线为近 7 天有票 / 20+ 天充裕可兑，灰线为紧俏散票；悬停航线即显示可兑出行日天数，支持滚轮缩放与平移漫游。

![航网地图探索](frontend/src/assets/map-view.png)

### ✈️ 航线探索（列表大盘）
吸顶筛选栏 + 航线卡片：展示首末班时刻跨度、60 天日期胶囊，已查验日期以绿色微标回显余票（如 `余13 · 08:56查`），点击日期就地弹出班次明细气泡。

![航线探索列表](frontend/src/assets/table-view.png)

---

## 🌟 核心特性与架构亮点

- ⚡ **全自动无感嗅探凭据 (彻底告别 Fiddler 与 .bat)**：
  - 网页右上角点击「同步长龙登录」，在电脑微信打开长龙航空小程序，嗅探器自动开启 Windows 代理并精准截获认证凭证；
  - **毫秒级智能识别**：自动向长龙接口拉取真实会员姓名（如已实名乘云会员）、畅飞卡授权 ID，原子化落库，抓取完成瞬间直接呈现在界面上；
  - 捕获完成即自动平稳关闭系统代理恢复直连，用后即焚、零手动配置。
- ✈️ **全网直飞航线大盘 (1280px 居中 · 吸顶筛选)**：
  - 收录 71 座通航城市、397 条长龙直飞航线与 490 个定期航班基础拓扑；
  - **筛选栏 Sticky 粘性吸顶**：长列表滚动时出发地/目的地/排序工具栏紧贴顶部，随时随地切换筛选；
- 🗺️ **原生轻量矢量 SVG 动态航网大屏**：
  - **两档纯净色阶**：绿线（充裕）vs 灰线（紧俏），单一显色不重叠，自带近期可兑航线流动光效粒子动画；
  - **一键全屏沉浸大屏**：支持城市聚焦筛选下拉搜索，点击航线右侧抽屉弹窗自适应滑出，带一键“恢复全貌”；
- ⏱️ **SQLite 在库持久化与智能保活微气泡**：
  - 本地 SQLite WAL 高性能模式存储，任何日期点击查验后，各班次剩余张数、时刻、机型永久落库到本地 `seat_queries` 表；
  - 再次点击 **0 毫秒直接从数据库弹窗**，零网络请求、零风控；气泡内点击刷新列表平滑抗塌缩；
- 🛡️ **智能排班跨度提炼**：单班航线提炼 `首选单班 · 06:30 ➔ 15:20`，多班航线智能汇总 `全天共 4 班 · 首班 06:50 ~ 末班 21:50`；
- 🕒 **自动化巡检守护进程**：支持自定义 30 条核心热门航线后台慢速拟人轮巡、全网每日定时普查与实时百分比动态进度条。

---

## 🚀 运行方式（三种使用姿势）

### 方式一：Windows 桌面客户端 (小白推荐 · 双击即用)

> **零环境依赖！无需安装 Python、Node.js，绿色单文件免安装！**

- **系统支持**：**Windows 10 / Windows 11 (64位)**
- **运行环境**：依赖系统内置的 **Microsoft Edge WebView2** 渲染内核（Win 11 与绝大多数 Win 10 系统已默认内置，无需手动安装）；
- **使用方法**：
  1. 前往 GitHub 仓库 Releases 下载最新绿色版 **`长龙航空畅飞助手.exe`**：  
     👉 [https://github.com/eureka-wu/clairline/releases](https://github.com/eureka-wu/clairline/releases)
  2. 下载后直接双击即可启动，无需安装过程，不写入注册表；
  3. 绿色便携，所有在库查验缓存和个人配置自动保存在当前同级目录，随删即卸载。

---

### 方式二：纯 Python 本地服务 (免 Node.js · 浏览器访问)

> **只需 Python 3.8+，前端静态产物已固化分发！**

```bash
# 1. 克隆开源仓库
git clone https://github.com/eureka-wu/clairline.git
cd clairline

# 2. 直接启动后端一体化服务
python backend/server.py
```
终端将提示服务在 `http://127.0.0.1:3000` 监听，打开浏览器访问即可享受完整功能。

---

### 方式三：开发者模式 (极速协同热更新)

> **适合进行功能开发、UI 调优与前后端联调！**

双击项目根目录下的 **`dev.bat`**（或在终端运行 `python dev_runner.py`）：
- 单终端并发托管 Python 后端 (端口 `3000`) 与 Vite 前端开发服务器 (端口 `8173`)；
- 前端支持毫秒级 HMR 热更新，后端 Python 代码修改自动毫秒级热重载；
- 浏览器访问 `http://localhost:8173`。

---

## 📦 自行打包 Exe (开发者可选)

如果你对源码进行了二次开发，想要自行打包 Windows 单文件客户端：

```bash
# 1. 编译最新前端静态资源
cd frontend
npm install
npm run build
cd ..

# 2. 安装桌面壳与打包依赖
python -m pip install pywebview PyInstaller

# 3. 执行一键封包脚本
python build_exe.py
```
打包成功后，单文件程序将生成在 `dist/长龙航空畅飞助手.exe`。

---

## 📁 目录结构

```text
clairline/
├── app_desktop.py            # 基于 Edge WebView2 的轻量桌面客户端入口
├── build_exe.py              # PyInstaller 一键封包绿色 Exe 脚本
├── dev_runner.py             # 开发者单终端前后端并发与自动热重载调度器
├── dev.bat                   # Windows 极速一键启动脚本
├── backend/                  # Python 后端服务与 SQLite3 数据库引擎
│   ├── data/                 # 本地数据存储目录 (除种子外已严格配置 .gitignore)
│   │   ├── routes_seed.json  # 全网 490 个航班直飞航网种子 (开箱免配置初始化)
│   │   ├── changlong.db      # 本地私有 SQLite 数据库 (自动建表，不上传)
│   │   └── credentials.json  # 本地抓取凭据 (不上传)
│   ├── db.py                 # SQLite3 WAL 模式连接池、CRUD 与种子注入层
│   ├── loongair_client.py    # 长龙官方核心接口客户端 (身份与畅飞卡授权)
│   ├── capture_addon.py      # mitmproxy 自动化凭证嗅探核心
│   ├── capture_manager.py    # 嗅探生命周期管理与守护线程
│   ├── proxy_util.py         # 纯原生 Windows 系统代理安全重置工具
│   ├── auto_patrol.py        # 自动化巡检守护进程 (Top 30 慢速拟人 / 全网普查)
│   ├── seccard_client.py     # 官方查票与日历接口穿透客户端
│   ├── scheduler.py          # 定时调度核心模块
│   └── server.py             # 前后端一体化 HTTP 托管服务 (端口 3000)
├── frontend/                 # Vue 3 + Vite 单页应用工程
│   ├── dist/                 # 固化生产编译产物 (供 Python 直接高并发分发)
│   ├── src/
│   │   ├── api/              # API 接口通信模块 (auth.js, flights.js, patrol.js)
│   │   ├── assets/           # 统一设计系统 main.css 与航网地图预览截图
│   │   ├── components/       # 业务组件
│   │   │   ├── AppHeader.vue         # 顶部导航、GitHub 链接与身份胶囊
│   │   │   ├── AuthModal.vue         # 纯 SVG 矢量引导、无 Emoji 认证同步弹窗
│   │   │   ├── RouteFilterBar.vue    # 出发/目的地级联、互换、排序 (Sticky 吸顶)
│   │   │   ├── RouteCard.vue         # 航线卡片 (时刻跨度、日期胶囊、纯粹接驳按钮)
│   │   │   ├── SeatPopover.vue       # 就地轻量微气泡 (抗塌缩平稳蒙层、智能悬停保活)
│   │   │   ├── RouteDetailDrawer.vue # 60天日期流、落地周边游与高铁接驳
│   │   │   ├── PatrolModal.vue       # 30条巡检配置、定时普查、实时进度条
│   │   │   └── FlightMap.vue         # 原生矢量 SVG 航网漫游、两档纯净色阶与一键全屏
│   │   ├── data/             # 元数据与纯矢量 SVG 图标集 (icons.js, city-meta.js)
│   │   ├── App.vue           # 根组件
│   │   └── main.js           # Vue 入口脚本
│   ├── index.html            # Vite 现代 HTML 入口
│   ├── package.json          # 前端依赖配置
│   └── vite.config.js        # Vite 构建与开发代理配置
├── .gitignore                # 严格的隐私凭据、本地数据库与构建忽略规则
└── README.md                 # 项目完整文档
```

---

## ⚠️ 免责声明 (Disclaimer)

1. **学习研究用途**：本项目为个人开源项目，仅供个人技术研究、前端现代化工程探索与航旅行程规划参考，非长龙航空官方出品；
2. **官方权威性**：项目中展示的航班、时刻、机位及兑换规则均以长龙航空官方渠道最新发布为准；
3. **合规使用声明**：请严格遵守相关法律法规，严禁将本项目用于任何商业牟利、恶意高频扫描或破坏民航系统正常运行秩序的行为。
