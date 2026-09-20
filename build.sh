#!/bin/bash
# Build script for AIC8800 WiFi driver DKMS deb package
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="${SCRIPT_DIR}/aic8800fdrvpackage"
CONTROL="${PKG_DIR}/DEBIAN/control"

# read version from DEBIAN/control
VERSION=$(grep '^Version:' "$CONTROL" | awk '{print $2}')
PKG_NAME=$(grep '^Package:' "$CONTROL" | awk '{print $2}')
OUTPUT="${SCRIPT_DIR}/${PKG_NAME}_${VERSION}_dkms_all.deb"

echo "==> Package: ${PKG_NAME} ${VERSION}"
echo "==> Output:  ${OUTPUT}"
echo ""

# pre-flight checks
if [ ! -d "${PKG_DIR}/DEBIAN" ]; then
    echo "ERROR: DEBIAN/ directory not found in ${PKG_DIR}"
    exit 1
fi
if [ ! -f "${PKG_DIR}/AIC8800/drivers/aic8800/dkms.conf" ]; then
    echo "ERROR: dkms.conf not found"
    exit 1
fi

# make scripts executable
chmod 755 "${PKG_DIR}/DEBIAN/postinst" \
          "${PKG_DIR}/DEBIAN/prerm" \
          "${PKG_DIR}/DEBIAN/postrm" \
          "${PKG_DIR}/DEBIAN/preinst"

# remove old build artifacts
rm -f "${SCRIPT_DIR}/${PKG_NAME}_"*"_dkms_all.deb"
rm -f "${SCRIPT_DIR}/${PKG_NAME}_"*"all.deb"

# build
echo "==> Building..."
dpkg-deb --build "$PKG_DIR" "$OUTPUT"

# verify
echo ""
echo "==> Verifying package..."
dpkg-deb -I "$OUTPUT"
echo ""
echo "==> Package contents (top-level):"
dpkg-deb -c "$OUTPUT" 2>/dev/null | head -20
echo "   ..."

echo ""
echo "==> Done. Package built: ${OUTPUT}"
ls -lh "$OUTPUT"
