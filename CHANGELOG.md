# Changelog

## 1.3.1 — 2026-10-17

- 修复 DKMS 未声明产物子目录的问题：原来编译成功后仍以错误码 7 退出。
- 同步 Deb、DKMS 和维护脚本版本；构建时以 DEBIAN/control 为版本来源。
- 新增单文件 .run 安装包及 install.sh，通过 APT 自动取得当前内核头文件、对应 GCC 和通用依赖；一个安装事务覆盖旧的半配置包。
- 不在 dpkg 脚本中调用 APT，不强制依赖 Ubuntu 专有 linux-headers-generic 元包。
- 构建替代版本后再清理旧 DKMS 注册；升级脚本不卸载已加载的模块，维护脚本按 dpkg action 分支执行。
- 根据目标头文件识别 cfg80211 事件/信道切换 API，修复 Ubuntu 6.8 回移接口及 timer_container_of 兼容问题。
- 修复兼容宏重复定义、空内核版本变量警告、递归 make 的 jobserver 传递；限制编译并行度为四。
- 在临时打包目录清除编译产物、统一文件所有权，保留旧发布文件，生成 SHA256SUMS。
- 诊断工具在宿主机编译并使用 install 写入 /usr/sbin，移除维护脚本对 sudo 的隐式依赖。

详见 [验证记录](docs/validation-1.3.1.md)。未进行实际硬件收发或系统安装测试时，不将源码编译成功视为所有设备兼容的证明。
