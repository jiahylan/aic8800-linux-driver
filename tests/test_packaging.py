#!/usr/bin/env python3
"""Packaging regressions. APT/DKMS mutations are mocked; no root is required."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEB = ROOT / 'dist/aic8800fdrvpackage_1.3.1_dkms_all.deb'
RUN = ROOT / 'dist/aic8800-installer-1.3.1.run'
REAL_DPKG_DEB = shutil.which('dpkg-deb')
MOCK = r'''#!/usr/bin/python3
import json, os, pathlib, shutil, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as f:
    f.write(json.dumps([name] + args) + '\n')
if name == 'id':
    print(0)
elif name == 'uname':
    print('Linux' if args == ['-s'] else os.environ['TEST_KERNEL'])
elif name == 'dpkg-query':
    if args[-1] not in os.environ.get('TEST_MISSING', '').split(','):
        print('installed')
    else:
        sys.exit(1)
elif name == 'apt-get':
    if args[0] == 'update':
        sys.exit(int(os.environ.get('TEST_UPDATE_EXIT', 0)))
    if args[0] == 'download':
        if os.environ.get('TEST_NO_HEADERS'):
            sys.exit(100)
        shutil.copy(os.environ['TEST_HEADER_DEB'], pathlib.Path.cwd() / 'headers.deb')
    if args[0] == 'install':
        sys.exit(int(os.environ.get('TEST_INSTALL_EXIT', 0)))
elif name == 'dkms':
    if args[0] == 'status':
        if '-v' not in args:
            print('aic8800/1.2.0: added')
        elif os.environ.get('TEST_REGISTERED'):
            print('aic8800/1.3.1: added')
    elif args[0] == 'build':
        sys.exit(int(os.environ.get('TEST_BUILD_EXIT', 0)))
elif name == 'make':
    directory = pathlib.Path(args[args.index('-C') + 1])
    for tool in ('wifi_test', 'bt_test'):
        (directory / tool).write_text('#!/bin/sh\nexit 0\n')
'''


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aic8800-test-')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.bin = self.work / 'bin'
        self.bin.mkdir()
        self.log = self.work / 'calls.jsonl'
        self.env = dict(os.environ, TEST_LOG=str(self.log),
                        TEST_KERNEL='0.0.0-aic8800-test',
                        PATH=str(self.bin) + ':' + os.environ['PATH'])
        for cmd in ('id', 'uname', 'dpkg-query', 'apt-get', 'dkms', 'make', 'udevadm'):
            path = self.bin / cmd
            path.write_text(MOCK)
            path.chmod(0o755)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def header(self, config=None):
        pkg = self.work / 'header-package'
        (pkg / 'DEBIAN').mkdir(parents=True)
        (pkg / 'DEBIAN/control').write_text(
            'Package: linux-headers-test\nVersion: 1\nArchitecture: all\n'
            'Maintainer: Test <test@example.com>\nDescription: Fixture\n')
        target = pkg / 'usr/src/linux-headers-0.0.0-aic8800-test/include/config'
        target.mkdir(parents=True)
        (target / 'auto.conf').write_text(config or
            'CONFIG_CC_VERSION_TEXT="x86_64-linux-gnu-gcc-13 (Ubuntu) 13.3.0"\n'
            'CONFIG_GCC_VERSION=130300\n')
        out = self.work / 'headers.deb'
        subprocess.run([REAL_DPKG_DEB, '--root-owner-group', '--build', str(pkg), str(out)],
                       check=True, stdout=subprocess.DEVNULL)
        self.env['TEST_HEADER_DEB'] = str(out)

    def install(self, *args):
        return subprocess.run(['bash', str(ROOT / 'install.sh'), *args, str(DEB)],
                              env=self.env, text=True, capture_output=True)

    def test_download_headers_compiler_and_replace_in_one_transaction(self):
        self.header()
        self.env['TEST_MISSING'] = 'dkms,gcc-13'
        result = self.install('--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(len([c for c in calls if c[:2] == ['apt-get', 'update']]), 1)
        self.assertIn(['apt-get', 'download', 'linux-headers-0.0.0-aic8800-test'], calls)
        installs = [c for c in calls if c[:2] == ['apt-get', 'install']]
        self.assertEqual(len(installs), 1)
        for arg in ('-y', 'gcc-13', 'dkms', 'linux-headers-0.0.0-aic8800-test', str(DEB)):
            self.assertIn(arg, installs[0])

    def test_installed_dependencies_do_not_require_index_update(self):
        configs = list(Path('/lib/modules').glob('*/build/include/config/auto.conf'))
        if not configs:
            self.skipTest('No prepared host headers available')
        self.env['TEST_KERNEL'] = configs[0].parents[3].name
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(c[:2] == ['apt-get', 'update'] for c in self.calls()))
        self.assertFalse(any(c[:2] == ['apt-get', 'download'] for c in self.calls()))

    def test_unavailable_matching_headers_stop_before_install(self):
        self.env['TEST_NO_HEADERS'] = '1'
        result = self.install('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No matching headers', result.stderr)
        self.assertFalse(any(c[:2] == ['apt-get', 'install'] for c in self.calls()))

    def test_network_failure_stops_before_install(self):
        self.env['TEST_MISSING'] = 'dkms'
        self.env['TEST_UPDATE_EXIT'] = '100'
        result = self.install('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot refresh APT indexes', result.stderr)
        self.assertFalse(any(c[:2] == ['apt-get', 'install'] for c in self.calls()))

    def test_clang_kernel_is_explicitly_rejected(self):
        self.header('CONFIG_CC_IS_CLANG=y\nCONFIG_GCC_VERSION=0\n')
        result = self.install('--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Clang-built kernels', result.stderr)
        self.assertFalse(any(c[:2] == ['apt-get', 'install'] for c in self.calls()))

    def test_apt_install_failure_is_not_reported_as_success(self):
        self.header()
        self.env['TEST_INSTALL_EXIT'] = '100'
        result = self.install('--yes')
        self.assertEqual(result.returncode, 100)
        self.assertNotIn('Installation complete.', result.stdout)

    def maintainer_script(self, script, action):
        fs = self.work / 'fs'
        src = fs / 'AIC8800'
        (src / 'drivers/aic8800').mkdir(parents=True, exist_ok=True)
        (src / 'drivers/aic8800/dkms.conf').write_text('fixture\n')
        (src / 'fw/aic8800DC').mkdir(parents=True, exist_ok=True)
        (src / 'fw/aic8800DC/firmware.bin').write_bytes(b'firmware')
        (src / 'aicrf_test').mkdir(exist_ok=True)
        (src / 'aic.rules').write_text('# fixture\n')
        config = fs / 'lib/modules/0.0.0-aic8800-test/build/include/config'
        config.mkdir(parents=True, exist_ok=True)
        (config / 'auto.conf').touch()
        (fs / 'usr/sbin').mkdir(parents=True, exist_ok=True)
        text = (ROOT / 'aic8800fdrvpackage/DEBIAN' / script).read_text()
        for prefix in ('/usr/src', '/AIC8800', '/lib/modules', '/lib/firmware',
                       '/etc/udev', '/usr/sbin', '/var/lib/dkms'):
            text = text.replace(prefix, str(fs) + prefix)
        # Keep every side effect in this sandbox, with APT/DKMS/make as recorders.
        lines = text.splitlines()
        lines = ['export PATH="' + str(self.bin) + ':' + os.environ['PATH'] + '"'
                 if line.startswith('export PATH=') else line for line in lines]
        path = self.work / script
        path.write_text('\n'.join(lines) + '\n')
        return subprocess.run(['bash', str(path), action], env=self.env,
                              text=True, capture_output=True)

    def test_replacement_is_built_before_retiring_old_registration(self):
        result = self.maintainer_script('postinst', 'configure')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [c for c in self.calls() if c[0] == 'dkms']
        actions = [c[1] for c in calls]
        self.assertLess(actions.index('build'), actions.index('remove'))
        self.assertLess(actions.index('remove'), actions.index('install'))
        self.assertTrue((self.work / 'fs/usr/sbin/wifi_test').exists())
        self.assertTrue((self.work / 'fs/lib/firmware/aic8800DC/firmware.bin').exists())
        self.assertFalse(any(c[0] in ('apt-get', 'rmmod', 'modprobe') for c in self.calls()))

    def test_failed_build_preserves_old_registration(self):
        self.env['TEST_BUILD_EXIT'] = '10'
        result = self.maintainer_script('postinst', 'configure')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('make.log', result.stderr)
        actions = [c[1] for c in self.calls() if c[0] == 'dkms']
        self.assertNotIn('remove', actions)
        self.assertNotIn('install', actions)

    def test_upgrade_prerm_keeps_registration(self):
        result = self.maintainer_script('prerm', 'upgrade')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_postinst_abort_upgrade_does_not_reconfigure(self):
        result = self.maintainer_script('postinst', 'abort-upgrade')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_api_backports_are_detected_from_header_declarations(self):
        probe = (ROOT / 'aic8800fdrvpackage/AIC8800/drivers/aic8800/'
                 'aic8800_fdrv/compat_flags.sh')
        header = self.work / 'cfg80211.h'
        # Ubuntu 6.8: puncturing arguments, but no receive-frame link_id.
        header.write_text(
            'bool cfg80211_rx_spurious_frame(struct net_device *dev,\n'
            '    const u8 *addr, gfp_t gfp);\n'
            'bool cfg80211_rx_unexpected_4addr_frame(struct net_device *dev,\n'
            '    const u8 *addr, gfp_t gfp);\n'
            'void cfg80211_cac_event(struct net_device *dev,\n'
            '    const struct cfg80211_chan_def *chandef,\n'
            '    enum nl80211_radar_event event, gfp_t gfp);\n'
            'void cfg80211_ch_switch_notify(struct net_device *dev,\n'
            '    struct cfg80211_chan_def *chandef, unsigned int link_id,\n'
            '    u16 punct_bitmap);\n'
            'void cfg80211_ch_switch_started_notify(struct net_device *dev,\n'
            '    struct cfg80211_chan_def *chandef, unsigned int link_id,\n'
            '    u8 count, bool quiet, u16 punct_bitmap);\n')
        result = subprocess.run(['sh', str(probe), str(header)], check=True,
                                text=True, capture_output=True)
        self.assertIn('-DAIC_CFG80211_CH_SWITCH_PUNCT', result.stdout)
        self.assertIn('-DAIC_CFG80211_CH_SWITCH_STARTED_LINK_ID', result.stdout)
        self.assertNotIn('-DAIC_CFG80211_SPURIOUS_LINK_ID', result.stdout)
        self.assertNotIn('-DAIC_CFG80211_4ADDR_LINK_ID', result.stdout)
        self.assertNotIn('-DAIC_CFG80211_CAC_LINK_ID', result.stdout)
        # Newer kernel: receive-frame link_id, no punct_bitmap.
        header.write_text(header.read_text().replace('const u8 *addr, gfp_t gfp',
            'const u8 *addr, int link_id, gfp_t gfp').replace(
                'enum nl80211_radar_event event, gfp_t gfp',
                'enum nl80211_radar_event event, gfp_t gfp, unsigned int link_id').replace(
                ',\n    u16 punct_bitmap', '').replace(', u16 punct_bitmap', ''))
        result = subprocess.run(['sh', str(probe), str(header)], check=True,
                                text=True, capture_output=True)
        self.assertIn('-DAIC_CFG80211_SPURIOUS_LINK_ID', result.stdout)
        self.assertIn('-DAIC_CFG80211_4ADDR_LINK_ID', result.stdout)
        self.assertIn('-DAIC_CFG80211_CAC_LINK_ID', result.stdout)
        self.assertNotIn('-DAIC_CFG80211_CH_SWITCH_PUNCT', result.stdout)
        self.assertNotIn('-DAIC_CFG80211_CH_SWITCH_STARTED_PUNCT', result.stdout)

    def test_run_bundle_extracts_without_installing(self):
        target = self.work / 'extracted bundle'
        result = subprocess.run(['bash', str(RUN), '--extract', str(target)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / DEB.name).read_bytes(), DEB.read_bytes())
        self.assertTrue((target / 'install.sh').exists())
        self.assertTrue((target / 'docs/validation-1.3.1.md').exists())
        self.assertTrue((target / 'CHANGELOG.md').exists())
        self.assertEqual(self.calls(), [])

    def test_package_versions_locations_ownership_and_no_build_products(self):
        control = self.work / 'control'
        subprocess.run([REAL_DPKG_DEB, '-e', str(DEB), str(control)], check=True)
        for name in ('postinst', 'prerm'):
            self.assertIn('PACKAGE_VERSION="1.3.1"', (control / name).read_text())
        archive = subprocess.run([REAL_DPKG_DEB, '--fsys-tarfile', str(DEB)],
                                 check=True, capture_output=True).stdout
        import io
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            for member in tf:
                self.assertEqual((member.uid, member.gid), (0, 0))
                self.assertFalse(member.name.endswith(('.ko', '.o', '.cmd')))
            config = tf.extractfile('./AIC8800/drivers/aic8800/dkms.conf').read().decode()
        self.assertIn('PACKAGE_VERSION="1.3.1"', config)
        self.assertIn('BUILT_MODULE_LOCATION[0]="aic_load_fw/"', config)
        self.assertIn('BUILT_MODULE_LOCATION[1]="aic8800_fdrv/"', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
