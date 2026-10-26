# 长龙航网助手 · macOS 版

这是 [eureka-wu/clairline](https://github.com/eureka-wu/clairline) 的 macOS 移植分支。
原版只支持 Windows（注册表改代理 + `certutil` 装根证书 + WebView2 桌面壳），
本分支把它改造成**在 macOS 上用浏览器直接访问**的版本。

## 快速开始

```bash
git clone https://github.com/beelzebubxbh/clairline.git
cd clairline
./refresh-token.sh    # 首次：抓取一次微信小程序登录态
./run.sh              # 启动 → 浏览器打开 http://127.0.0.1:3000
```

`run.sh` 首次会自动构建前端（需要 Node.js），之后秒开。

## 依赖

| 组件 | 要求 | 安装 |
|---|---|---|
| Python | 3.9+（纯标准库，无第三方包） | 系统自带即可 |
| Node.js | 仅构建前端时需要 | `brew install node` |
| mitmproxy | 仅刷新登录态时需要 | `brew install mitmproxy` |

## 与原版的差异

### 1. 移除了整套 Windows 系统级操作

原版为了拿登录态，会改注册表把系统代理指向本机、用 `certutil` 把 mitmproxy 根证书
装进 Windows 信任区、退出时再改回来。这套东西在 macOS 上全部作废。

本版把凭据获取降级为**按需的一次性操作**（`refresh-token.sh`），
日常使用完全不碰系统代理和证书。

### 2. 修掉了 403 的真实原因

原版代码注释说「长龙 WAF 靠 `Accept-Encoding` 识别合法请求」—— 这句话是对的。
实测：同一套请求头，**去掉 `Accept-Encoding` 立刻 403，加上就 200**。
容易被误判成「TLS 指纹被拦」而去上 curl 子进程或 TLS 伪装库，其实不需要。

`backend/seccard_client.py` 里现在会强制补齐这个头，并把 `br` 降级为 `gzip`
（标准库没有 brotli）。

### 3. 取消了「跨自然日强制作废凭据」

原版逻辑：只要凭据不是今天抓的，就清空。但 Token 的实际寿命由服务端决定，
强制作废会把明明还能用的凭据丢掉。

本版改为：**一直用到服务端报错为止**，报错时抛出 `AuthExpired`，提示重新抓取。

### 4. 关闭了「打开页面自动全网普查」

原版 `App.vue` 在 `onMounted` 里发现本地有票航线少于 50 条，就自动启动
397 条航线的全量普查。实测这一次会在 **48 秒内打对方 397 次接口（约 8 次/秒）**。

本版两处改动：

- 前端：删除自动触发，改为手动点击「全网普查」；
- 后端：`auto_patrol.py` 的全量模式不再走 4 线程 + 0.25 秒微延迟，
  改为**全局共享限速器 1.1 秒/条**（397 条约需 7 分钟）。

### 5. 数据与凭据都放用户目录

```
~/.clairline/credentials.json   # 登录态，600 权限
~/.clairline/data/changlong.db  # SQLite
```

仓库目录保持干净，`git status` 不会有脏文件。

## 登录态（Token）到底是什么

抓包实测结论：

- 接口地址统一是 `POST https://www.loongair.cn/webhandler.ashx`，
  body 为 `paras={"AppID":"ClientService","MethodName":"...","Parameters":"..."}`；
- `NESign` 请求头的值是字符串 `"[object Null]"` —— 小程序自身的签名逻辑是坏的，
  **等于没有签名**，任意参数重放都不会被拒；
- `Authorization` 是 base64 编码的 UUID（`SESSION` 同值），不是 JWT，不带过期时间。

所以：**只要拿到一次 Token，就能在纯命令行环境一直用**，直到服务端让它失效。

## 接口能力边界（实测）

| 接口 | 用途 | 限制 |
|---|---|---|
| `getSecCardRedeemedCalendar` | 放票日历 | 返回 396 天（原版前端只展示 61 天） |
| `secCardSearchFlights` | 查具体班次余票 | **仅限提前 3～30 天**，超出报 `ErrorCode:1` |
| `sales_user_userDetailInfo` | 会员档案 | — |

日历状态值语义（实测反推）：

| 值 | 含义 |
|---|---|
| `1` | 有 1 个可兑航班 |
| `0` | 可预约但无票 |
| `-1` / `-2` | 不可兑 / 未放票 |
| `-3` | 超出预约窗口 |

## 免责声明

沿用上游：仅供个人学习研究与行程规划参考，非长龙航空官方产品。
本项目通过复用小程序私有接口获取数据，高频请求可能触发风控影响账号，
请自行评估风险，勿用于商业用途。