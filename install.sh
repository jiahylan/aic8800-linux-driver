#!/bin/bash
# APT must run outside dpkg maintainer scripts (which already hold its lock).
set -euo pipefail
export PATH="${PATH}:/usr/sbin:/sbin"
fail() { echo "ERROR: $*" >&2; exit 1; }
usage() { echo "Usage: bash $0 [--yes] [driver.deb]"; }
assume_yes=()
package=""
for arg in "$@"; do
    case "$arg" in
        -y|--yes) assume_yes=(-y) ;;
        -h|--help) usage; exit 0 ;;
        -*) usage >&2; exit 2 ;;
        *) [[ -z "$package" ]] || fail "Only one package can be installed."; package="$arg" ;;
    esac
done
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ -z "$package" ]]; then
    shopt -s nullglob
    packages=("$script_dir"/aic8800fdrvpackage_*_dkms_all.deb)
    [[ ${#packages[@]} == 1 ]] || fail "Specify one .deb file, or use the self-contained .run installer."
    package=${packages[0]}
fi
[[ -f "$package" ]] || fail "Package not found: $package"
package=$(readlink -f -- "$package")
[[ $(uname -s) == Linux ]] || fail "This installer requires Linux."
for tool in apt-get dpkg dpkg-deb dpkg-query; do
    command -v "$tool" >/dev/null || fail "Debian/Ubuntu with APT is required (missing $tool)."
done
[[ $(dpkg-deb -f "$package" Package) == aic8800fdrvpackage ]] || fail "Unexpected package."
if [[ $(id -u) != 0 ]]; then
    command -v sudo >/dev/null || fail "Run this installer as root."
    exec sudo -- bash "$0" "${assume_yes[@]}" "$package"
fi
kernel=$(uname -r)
headers="linux-headers-$kernel"
dependencies=(build-essential dkms kmod udev eject ca-certificates)
refreshed=no
refresh_indexes() {
    if [[ "$refreshed" == no ]]; then
        apt-get update || fail "Cannot refresh APT indexes. Check Internet access and software sources."
        refreshed=yes
    fi
}
installed() { [[ $(dpkg-query -W -f='${db:Status-Status}' "$1" 2>/dev/null) == 'installed' ]]; }
for dep in "${dependencies[@]}"; do
    if ! installed "$dep"; then refresh_indexes; break; fi
done
workdir=$(mktemp -d)
trap 'rm -rf -- "$workdir"' EXIT
config="/lib/modules/$kernel/build/include/config/auto.conf"
if [[ ! -f "$config" ]]; then
    refresh_indexes
    # Inspect the exact target header package before installing anything. This
    # also gives a clear error for kernels removed from the configured mirrors.
    if ! (cd "$workdir" && apt-get download "$headers"); then
        fail "No matching headers for $kernel. Enable its repository, or boot a kernel with available headers."
    fi
    header_debs=("$workdir"/*.deb)
    dpkg-deb -x "${header_debs[0]}" "$workdir/headers"
    config="$workdir/headers/usr/src/linux-headers-$kernel/include/config/auto.conf"
    [[ -f "$config" ]] || fail "Downloaded headers lack include/config/auto.conf; install prepared headers for $kernel."
    dependencies+=("$headers")
fi
# Kernel builds may require a newer GCC than the distribution's default GCC.
compiler_text=$(sed -n 's/^CONFIG_CC_VERSION_TEXT=//p' "$config")
if grep -q '^CONFIG_CC_IS_CLANG=y' "$config"; then
    fail "This package currently supports GCC-built kernels. Clang-built kernels need a separately configured LLVM toolchain."
fi
compiler_major=$(printf '%s\n' "$compiler_text" | sed -nE 's/.*gcc-([0-9]+).*/\1/p')
if [[ -z "$compiler_major" ]]; then
    gcc_version=$(sed -n 's/^CONFIG_GCC_VERSION=//p' "$config")
    if [[ "$gcc_version" =~ ^[0-9]+$ ]] && (( gcc_version > 0 )); then
        compiler_major=$((gcc_version / 10000))
    fi
fi
if [[ -n "$compiler_major" ]]; then
    dependencies+=("gcc-$compiler_major")
    if ! installed "gcc-$compiler_major"; then refresh_indexes; fi
fi
# One transaction replaces an old half-configured package before configuration;
# installing dependencies in an earlier transaction could rerun its broken postinst.
echo "Installing AIC8800 for $kernel; APT will download missing dependencies."
apt-get install "${assume_yes[@]}" --no-install-recommends "${dependencies[@]}" "$package"
echo "Installation complete. Reboot or reconnect the USB adapter to use the new driver."
if command -v mokutil >/dev/null && mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
    echo "Secure Boot is enabled: enroll the DKMS signing key through MOK on reboot if it is not trusted yet."
fi
