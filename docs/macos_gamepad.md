# macOS 手柄输入

Host 优先启动随 Python 包附带的原生 GameController 模块，无需打开 Chrome 页面。
F310 使用 D 模式。当前本机已验证 Apple Development 签名模块可读取输入。

首次构建或修改 Swift 后，在仓库根目录运行：

```sh
bash scripts/setup_gc_bridge.sh
```

构建需要 Xcode 命令行工具和本机可用的代码签名证书；可用
`CODE_SIGN_IDENTITY` 指定证书。生成物在
`host/src/deepsight_host/native/DeepSightGamepad.app`，由 Host 自动启动、退出时关闭。
无需安装到 `/usr/local/bin`，也不需要管理员权限。

原生模块在后台接收输入，持续报告连接状态。拔出手柄、进程退出、超过一秒没有
新状态时 Host 会停止绞盘/平台输入并锁定。重新插入后仍保持锁定，需要重新按 Start。

Python wheel 的 package-data 包含此辅助 app；必须先构建再打 wheel。
如后续用 PyInstaller 制作完整上位机 app，同样应收集
`deepsight_host/native` 整个目录（含 Info.plist、可执行文件和签名目录），
并按发行目标重新签名。当前没有制作完整的可分发上位机安装包。

Windows/Linux 仍使用 pygame；macOS 原生模块缺失或启动失败时保留旧的回退路径。
