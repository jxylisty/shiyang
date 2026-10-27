# 打包成手机 APP（Android）

> 实测环境：2026-10-27，Windows 10 + HBuilderX 5.26 + 前端 Vue3/Vite。
> 本文记录的是**实际跑通的步骤**，以及踩过的坑；未验证的 iOS 打包不在范围内。

## 结论先说

平台是「Vue3 前端 + FastAPI 后端」的纯 Web 架构，打包成 APP 的方式是
**把前端产物内置进 5+App 壳工程**（不是 wap2app、不是 WebView 指向远程地址）：

- 界面、字体、图标全部打进 APK，**秒开、不依赖任何服务器**
- 只有数据请求走网络，指向部署好的后端
- 后端不用改架构，一行代码都不用动

## 一、架构与产物

```
shiyang/                     ← 原项目（不参与打包，只提供构建输入）
  frontend/                  ← Vue 源码；vite --mode app 产出 dist-app/
  scripts/build_app.py       ← 构建 + 装配脚本（本次新增）
shiyang-app5/                ← HBuilderX 5+App 壳工程（在项目目录外，避免污染仓库）
  manifest.json              ← 应用名/包名/图标/签名证书/启动页
  index.html assets/ img/    ← build_app.py 覆盖灌入（这里是资源根，不是 www/）
  unpackage/release/apk/     ← 云打包产物（APK）落在这里
shiyang-app/certs/           ← Android 签名证书 keystore（勿提交到公开仓库）
```

## 二、构建 APK 的完整流程

### 1. 启动后端（手机要能访问）

后端默认只监听 `127.0.0.1`，手机访问不到。用联调脚本一条命令搞定（会打印手机该用的地址 + 尝试放行防火墙）：

```bash
cd shiyang
python -X utf8 scripts/start_backend_lan.py
```

它做的事情：

- 监听 `0.0.0.0:8100`（局域网可达）
- 枚举本机 IPv4 并按「常用程度」排序，Tailscale / Hyper-V 虚拟网卡会被标注「别用」
- 添加防火墙入站规则 `Shiyang Backend 8100`（需管理员权限，失败会提示）

手动等价写法：

```bash
cd backend
SHIYANG_HOST=0.0.0.0 python -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

**选哪个 IP 很重要**：要选手机所在 WiFi 对应的那一个（通常是 `WLAN` 网卡）。
`172.x` 开头的多半是 Hyper-V 虚拟网卡，`192.168.137.1` 是本机开的热点网关
（只有手机连本机热点时才通），`100.x` 是 Tailscale，手机一般连不上。

**WLAN 若是「公用网络」，Windows 会拦截入站**，改成「专用」：
设置 → 网络和 Internet → WLAN → 当前网络 → 网络配置文件类型 → 专用。

### 2. 构建前端并装配到壳工程

```bash
cd shiyang
python -X utf8 scripts/build_app.py --api "http://<你的局域网IP>:8100/api/v1"
```

脚本做三件事：

1. `vite build --mode app` —— base 改相对路径 `./`、路由改 hash 模式（file:// 下 history 会 404）
2. 把 82 张中文文件名的药材图改名为 `m01.jpg`…`m82.jpg`（**云打包禁止中文文件名**），并把「中文名→ASCII 名」映射注入前端
3. 产物**覆盖到 `shiyang-app5/` 项目根目录**（5+App 的资源根就是项目根，不是 `www/`）

脚本会记住上次的 API 地址，下次直接运行不带参数即可。
**换网络环境（IP 变了）时必须重跑一次**，否则 APP 会连不上后端。

装配完可以自查一句（应输出含 `<div id="app">`，不是空模板）：

```bash
grep -c 'id="app"' shiyang-app5/index.html
```

### 3. 云打包

HBuilderX 图形界面：打开 `shiyang-app5` 项目 → 发行 → 原生App-云打包 → 选 Android、自有证书。

命令行等价（证书口令与 manifest 中一致，`shiyang2026`）：

```bash
"D:/HBuilderX/HBuilderX/cli.exe" pack \
  --project "C:/Users/zzx05/Desktop/大床课题/shiyang-app5" \
  --platform android \
  --android.packagename edu.njucm.shiyang \
  --android.androidpacktype 0 \
  --android.certalias shiyang \
  --android.certfile ".../certs/shiyang.keystore" \
  --android.certpassword shiyang2026 \
  --android.storepassword shiyang2026 \
  --ignoreWarnings true
```

排队期间可用 `cli.exe logcat pack` 看进度，产物在
`shiyang-app5/unpackage/release/apk/`。

## 三、踩过的坑（都是实测）

1. **wap2app 类型打不了包**。它的 APPID 是 `__W2A__<IP>` 这种按域名/地址本地生成的标识，
   云端不认，报「非当前账号所有」。改用 5+App（app-plus）类型，APPID 是 `H519137D3` 这种正规格式。
2. **5+App 的资源根是项目根目录，不是 `www/`**。曾把产物铺进 `www/`，打包一路成功，
   但 app 启动的是项目根那个 469 字节的空模板 `index.html` —— 装上去白屏，云端不报任何错。
   `scripts/build_app.py` 因此直接覆盖项目根，装配后务必确认根 `index.html` 里有 `<div id="app">`。
3. **5+App 云打包禁止中文文件名**。`public/img/materials/` 下 82 张 `乌梅.jpg` 直接导致打包失败，
   报 `App打包时，项目中文件名不能含有中文或全角字符`。解决方式见 `build_app.py`。
4. **app 内是 file:// 环境**，所有 `/api/v1`、`/img/xxx` 这类绝对路径全部失效，
   必须用 `import.meta.env.BASE_URL`（web 为 `/`、app 为 `./`）拼路径，且路由必须用 hash 模式。
5. **HBuilderX CLI 的 `user info` 会骗人**。它读本地缓存，显示已登录但 `pack` 报 `user not login`，
   需要用户在图形界面重新登录一次；另外装插件（amazon-corretto / launcher / app-safe-pack）后
   HBuilderX 可能自动退出，要重新 `cli open`。
6. **签名证书不能丢**。APK 更新必须用同一个 keystore，否则手机上报签名冲突、无法覆盖安装。
   `shiyang-app/certs/shiyang.keystore` + 口令 `shiyang2026`，请离线备份，**不要提交到公开仓库**。

## 四、当前状态与限制

- APK 只保证能装能跑；**答辩/演示前务必真机验证**（本机无连接手机，未做真机验收）。
- 后端跑在谁的电脑上，APP 就连谁；换网段要重新构建。正式使用应把后端部署到有固定域名/公网 IP
  的服务器，然后只需重跑一次 `build_app.py --api https://你的域名/api/v1`。
- APP 内没有做隐私协议弹窗、权限说明等上架必需项（云打包时会有 warning 提示），
  校内演示/内测安装无影响，**上架应用市场前需要补齐**。
- iOS 需要 Mac + 苹果开发者账号（￥688/年），当前未做。

## 五、验证记录

| 项目 | 结果 |
|---|---|
| web 版构建 `npx vite build` | 通过，产物行为不变（绝对路径/中文图名/相对 API） |
| app 版构建 `--mode app` | 通过，无中文文件名、无绝对路径残留 |
| 后端可导入 + 端点规模 | 49 路径 / 53 端点 |
| 云打包（第 1 次） | 成功，但产物内是项目自带空模板 index.html（真机会白屏）→ 定位到资源根问题 |
| 云打包（第 2 次） | 成功，产物体积 13.1 MB；已核对包内 `www/index.html` 含 `id="app"`、资源为相对路径、无中文文件名 |
| APK 结构与签名 | zip 校验通过（858 条目）、含 AndroidManifest、`META-INF/CERT.RSA` 签名存在 |
| 联调脚本 | `start_backend_lan.py` 语法与 `--help` 通过；**未在真机上跑通端到端**（本机无连接设备） |
