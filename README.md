# aic8800-linux-driver

## 介绍

本项目是 [TL-XDN6000H免驱版 V1.0 Linux系统驱动程序20250118](https://resource.tp-link.com.cn/pc/docCenter/showDoc?productId=3217&type=DRIVER&id=1737698106348416) 驱动的改版，用于在某些 Linux 设备上能够成功安装驱动。

## 动机

设备描述：
- 操作系统：Ubuntu 22.04
- 内核版本：6.5.0-18-generic

按照文档要求安装好 `build-essential`、`make`、`gcc-12` 等软件包后，使用 `sudo dpkg -i aic8800fdrvpackage.deb` 直接安装该网址处下载的驱动时，每次编译至 `rwnx_*` 相关文件时，设备 CPU 风扇高速运行发出响声后系统重启，无法正常安装。

## Debug

根据搜索结果，猜测失败原因是，编译到 `rwnx_*` 相关的大文件时负载持续升高，温度触发保护致使系统重启。但通过安装时限制编译核心数和使用 `cpulimit` 限制系统资源无法解决，遂对 `aic8800fdrvpackage.deb` 进行解包：

```shell
dpkg-deb -R aic8800fdrvpackage.deb aic8800fdrvpackage
```

分析源码，Makefile 里用了 `-j$(shell nproc)`，全核满载编译可能会导致过热触发硬件保护重启。

## 改动

1. 两个 Makefile 的并行数限制到 `-j4`：
	- AIC8800/drivers/aic8800/Makefile:60
	- AIC8800/drivers/aic8800/aic8800_fdrv/Makefile:330
2. postinst 脚本增加了保护措施：
	- 编译前等待 10 秒让 CPU 冷却
	- 用 `nice -n 19` 降低编译进程优先级

## 使用方式

从 [releases](https://github.com/jiahylan/aic8800-linux-driver/releases/tag/modified) 中下载打包好的安装包，或自己根据命令进行安装包打包，之后运行安装命令即可：

```shell
sudo dpkg -i aic8800fdrvpackage.deb
```
