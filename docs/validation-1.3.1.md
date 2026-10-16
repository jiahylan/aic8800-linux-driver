# 1.3.1 验证记录

日期：2026-10-17。远端项目：`hylan@192.168.31.59:/home/hylan/aic8800-linux-driver`。

## 问题与改动

旧包虽为 Deb 1.3.0，但内部 DKMS 仍为 1.2.0，未设置两个模块的 BUILT_MODULE_LOCATION。编译成功后 DKMS 在构建根目录找不到子目录内的 .ko，返回错误码 7，导致 postinst / dpkg / APT 连续失败。1.3.1 配置了产物路径，并在构建时同步版本。

新增 install.sh 和单文件自解压 .run。依赖下载在进入 dpkg 前完成判断，由一次 APT 安装事务处理通用依赖、当前内核头文件、GCC 和本地 Deb，避免嵌套 APT 锁及旧包半配置状态。保留标准 Deb。头文件存在且依赖已装好时不要求更新索引。

6.8 构建发现原源码还存在 timer_container_of 和 cfg80211 参数判断错误。通过兼容宏及 compat_flags.sh 按实际目标头文件检测无线事件和信道切换接口，兼容发行版 API 回移。没有更改 PHY、调制解调或 DSP 算法。

## 已执行

- `./build.sh`：成功生成 root 所有权的标准 Deb、自解压 .run 及 SHA256SUMS；源代码目录未混入编译产物，旧包保留。
- `python3 tests/test_packaging.py`：13 项回归检查通过。APT/DKMS 的系统写入使用命令替身，覆盖匹配头文件下载、GCC 选择、同一 APT 事务替换旧包、已有依赖离线路径、网络失败、无匹配头文件、Clang 明确拒绝、APT 安装失败、DKMS 失败保留旧注册、升级动作、包版本/所有权/产物目录、自解压和 API 回移检测。
- ShellCheck 0.9.0：build.sh、install.sh、四个维护脚本及 compat_flags.sh 通过。
- x86_64，Ubuntu 22.04 系列 `6.8.0-138-generic` 头文件、GCC 12：两个模块编译成功。此前失败的 cfg80211/timer 接口均已修复。
- x86_64，Ubuntu 24.04.4，`7.0.0-31-generic`、GCC 13：使用发行版 DKMS 3.0.11-1ubuntu13 在临时树中 add/build 成功，两个模块均被正确找到、strip 并保存为 .ko.zst。
- 同一环境 `7.0.0-38-generic`、GCC 13：隔离 DKMS build 成功，两个模块产物齐全。
- 厂商 wifi_test、bt_test 从源码在临时目录编译通过。
- APT dry-run 成功解析：新增 dkms，并将旧版 aic8800fdrvpackage 1.2.0 升级为 1.3.1，不删除其他软件包。
- 从 Ubuntu 软件源真实下载 linux-headers-7.0.0-31-generic 并解包，成功读取 include/config/auto.conf 中的 CONFIG_GCC_VERSION=130300 和 gcc-13 编译器信息。

真实编译命令示例（在源码副本中执行，禁止把编译产物加入 Git）：

```bash
make -C /tmp/aic8800-build-6.8 -j4 KVER=6.8.0-138-generic CC=gcc-12
```

远端隔离 DKMS 运行文件由 `apt-get download dkms` 取得并解包到 `/tmp/aic8800-dkms-validation/runtime`，未安装进宿主系统。使用独立 `--dkmstree` / `--sourcetree`，及空的 `--config` 禁用测试签名流程；实际 Kbuild 仍使用完整的目标内核头文件。实际安装时会使用系统正常的 DKMS 签名流程。

远端构建日志在 `/tmp/aic8800-dkms-validation/dkms-31.log`、`dkms-38.log` 和对应临时 DKMS 树；本地 6.8 构建日志在 `/tmp/aic8800-build-6.8/make.log`。这些目录仅供本次检查，不是发布依赖。

## 未执行与后续

- 未在目标宿主执行新驱动的 dpkg 安装、模块卸载/加载、重启或硬件收发，保留其现有无线连接。
- 环境不允许非特权 user namespace，未能用隔离容器进行一次全新系统安装；实际包管理器状态转换仍需在可回滚的干净系统上验证。
- 未验证 Secure Boot 的密钥生成、签名与 MOK 注册；未覆盖 Debian 实机、其他架构及未列出的内核。编译成功不等于全部硬件和系统组合都兼容。
- 若未来内核更换 GCC，需确保对应 gcc-N 和头文件一并安装；可重新运行 .run 自动补齐。
- 旧版包自身的 prerm 会卸载模块，无法靠新版本的 prerm 改写旧脚本已执行的行为；首次从 1.2.0/1.3.0 迁移时应准备其他联网方式。后续新版本升级不主动卸载已加载模块。

接口参考：[Linux Kbuild 外部模块](https://docs.kernel.org/kbuild/modules.html)、[DKMS 配置说明](https://github.com/dell/dkms/blob/main/dkms.8.in)、[Debian DKMS 打包](https://wiki.debian.org/DkmsPackaging)。
