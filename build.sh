#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
PKG_DIR="$SCRIPT_DIR/aic8800fdrvpackage"
CONTROL="$PKG_DIR/DEBIAN/control"
VERSION=$(sed -n 's/^Version: //p' "$CONTROL")
PKG_NAME=$(sed -n 's/^Package: //p' "$CONTROL")
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid version" >&2; exit 1; }
DIST="$SCRIPT_DIR/dist"
mkdir -p "$DIST"
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
cp -a "$PKG_DIR/." "$stage/package/"
# DEBIAN/control is the single version source, avoiding stale DKMS/script versions.
for f in DEBIAN/postinst DEBIAN/prerm AIC8800/drivers/aic8800/dkms.conf; do
    sed -i "s/^PACKAGE_VERSION=.*/PACKAGE_VERSION=\"$VERSION\"/" "$stage/package/$f"
done
chmod 755 "$stage/package/DEBIAN/"{preinst,postinst,prerm,postrm}
for f in "$stage/package/DEBIAN/"{preinst,postinst,prerm,postrm}; do bash -n "$f"; done
bash -n "$SCRIPT_DIR/install.sh"
# Never ship local compiler output; leave the source checkout and old releases intact.
find "$stage/package/AIC8800" -type f \( -name '*.o' -o -name '*.ko' \
    -o -name '*.cmd' -o -name '*.mod' -o -name '*.mod.c' \
    -o -name Module.symvers -o -name modules.order -o -name wifi_test \
    -o -name bt_test \) -delete
DEB="${PKG_NAME}_${VERSION}_dkms_all.deb"
dpkg-deb --root-owner-group --build "$stage/package" "$DIST/$DEB"
cp "$SCRIPT_DIR/install.sh" "$stage/install.sh"
cp "$SCRIPT_DIR/README.md" "$stage/README.md"
cp "$SCRIPT_DIR/CHANGELOG.md" "$stage/CHANGELOG.md"
cp -a "$SCRIPT_DIR/docs" "$stage/docs"
cp "$DIST/$DEB" "$stage/$DEB"
RUN="aic8800-installer-${VERSION}.run"
cat > "$DIST/$RUN" <<'HEADER'
#!/bin/bash
set -euo pipefail
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo "Usage: bash $0 [--yes] [--extract DIRECTORY]"
    echo "Installs AIC8800 with APT dependencies, or extracts the bundle without installation."
    exit 0
fi
payload_line=$(awk '/^__AIC8800_PAYLOAD__$/ { print NR + 1; exit }' "$0")
if [[ ${1:-} == --extract ]]; then
    [[ $# == 2 ]] || { echo "Usage: --extract DIRECTORY" >&2; exit 2; }
    mkdir -p -- "$2"
    tail -n +"$payload_line" "$0" | tar -xz -C "$2"
    exit 0
fi
workdir=$(mktemp -d)
trap 'rm -rf -- "$workdir"' EXIT
tail -n +"$payload_line" "$0" | tar -xz -C "$workdir"
bash "$workdir/install.sh" "$@"
exit 0
__AIC8800_PAYLOAD__
HEADER
tar -czf "$stage/payload.tar.gz" -C "$stage" install.sh README.md CHANGELOG.md docs "$DEB"
cat "$stage/payload.tar.gz" >> "$DIST/$RUN"
chmod 755 "$DIST/$RUN"
(cd "$DIST" && sha256sum "$DEB" "$RUN" > SHA256SUMS)
echo "Built: $DIST/$DEB"
echo "Built: $DIST/$RUN"
dpkg-deb -I "$DIST/$DEB"
