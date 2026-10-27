#!/usr/bin/env python3
"""T-Pot VM deployer: tools, form checks, self-installing disc, VM definitions, the whole run with fakes.
Run: python3 test_tpot_vm.py"""
import importlib.util, os, sys, json, tempfile, io, time, hashlib, subprocess, threading
HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ['NM_WIFI_TEST'] = '1'
os.environ['LOCALAPPDATA'] = TMP
spec = importlib.util.spec_from_file_location("stm_under_test", os.path.join(HERE, "speedtest_monitor.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod._NM_HONEYPOT_OFF = False        # the dormant honeypot code is tested with the switch ON
fails = []
def check(c, m):
    print(('  ok   ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

# ── hypervisors ──
env = {'ProgramFiles(x86)': 'C:\\Program Files (x86)', 'ProgramFiles': 'C:\\Program Files'}
have = {'C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe', 'C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe'}
t = mod._nm_vm_find_tools(env, lambda p: p in have)
check([x['kind'] for x in t] == ['vmware', 'virtualbox'] and t[0]['name'] == 'VMware Workstation', 'finds Workstation and VirtualBox: %s' % [x['name'] for x in t])
check(mod._nm_vm_find_tools(env, lambda p: False) == [] or os.name != 'nt', 'nothing installed -> empty list')
tools = t

# ── the form ──
host = {'ram_mb': 32768, 'cpus': 16, 'free_gb': 500}
good = {'hypervisor': 'vmware', 'dir': os.path.join(TMP, 'vm1'), 'ram_mb': 12288, 'cpus': 4, 'disk_gb': 128, 'tz': 'Europe/London', 'kb': 'gb',
        'os_user': 'tpotadmin', 'os_pw': 'a-long-vm-password', 'web_user': 'tpotweb', 'web_pw': 'portal.pw-1234', 'consent': True}
c, err = mod._nm_vm_validate(good, host, tools)
check(c is not None and c['tool']['kind'] == 'vmware', 'good form accepted: %s' % err)
def bad(**kw):
    r = dict(good); r.update(kw); return mod._nm_vm_validate(r, host, tools)[1]
check('Install one' in mod._nm_vm_validate(good, host, [])[1], 'no hypervisor gives install advice')
check('at least 8 GB' in bad(ram_mb=4096) or 'at least 8 GB' in bad(ram_mb=6000), 'under 8 GB refused')
check('less than 4 GB' in bad(ram_mb=32000), 'memory that starves Windows refused')
check('VM user name' in bad(os_user='root') and 'VM user name' in bad(os_user='Bad User'), 'root / odd user names refused')
check('portal password' in bad(web_pw='short') and 'portal password' in bad(web_pw='has space 1234') and 'portal password' in bad(web_pw="it's-quoted-1"), 'portal password limited to safe characters')
check('different password' in bad(web_pw='a-long-vm-password'), 'same password for both refused')
check('at least 8' in bad(os_pw='short'), 'short VM password refused')
check('time zone' in bad(tz='../../etc'), 'time zone injection refused')
os.makedirs(os.path.join(TMP, 'full')); open(os.path.join(TMP, 'full', 'x'), 'w').write('x')
check('not empty' in bad(dir=os.path.join(TMP, 'full')), 'non-empty folder refused')
check('Only 20 GB' in mod._nm_vm_validate(good, dict(host, free_gb=20), tools)[1], 'low disk refused')

# ── password hash matches openssl ──
for pw, salt in (('Hello world!', 'saltstring'), ('pässword', 'abcdefghijklmnop')):
    ref = subprocess.run(['openssl', 'passwd', '-6', '-salt', salt, pw], capture_output=True, text=True).stdout.strip()
    if ref: check(mod._nm_sha512_crypt(pw, salt) == ref, 'SHA-512 crypt equals openssl for %r' % pw)

# ── the answer file ──
cc = dict(c); cc['_sh_name'] = 'README.html'
pre = mod._nm_vm_preseed(cc)
check('a-long-vm-password' not in pre and 'passwd/user-password-crypted password $6$' in pre, 'VM password is only in the file as a hash')
check('passwd/root-login boolean false' in pre and 'tasksel tasksel/first multiselect ssh-server' in pre, 'root locked, SSH only (no mail server on port 25)')
late = [l for l in pre.splitlines() if l.startswith('d-i preseed/late_command')]
check(len(late) == 1 and 'WEB_PW=portal.pw-1234' in late[0] and 'chmod 600 /target/root/.tpot-deploy' in late[0] and 'cp /cdrom/README.html' in late[0], 'late command writes the root-only portal login and installs the first-boot script')
check(all('\n' not in l for l in late) and len(pre.encode()) < 5000, 'answer file fits README.txt (%d bytes)' % len(pre.encode()))
check(len(mod._NM_VM_FIRSTBOOT.encode()) < 8000 and 'install.sh -s -t h' in mod._NM_VM_FIRSTBOOT and 'shred -u /root/.tpot-deploy' in mod._NM_VM_FIRSTBOOT, 'first-boot script fits README.html and installs T-Pot unattended')
cfg = mod._nm_vm_boot_cfg('README.txt').decode()
check('timeout 1' in cfg and 'auto=true' in cfg and 'file=/cdrom/README.txt' in cfg and len(cfg) < 157, 'boot menu skipped, goes straight to the unattended install (%d bytes)' % len(cfg))

# ── the disc image: needs pycdlib to build a test image ──
try:
    import pycdlib
except Exception:
    pycdlib = None
if pycdlib:
    def mk(path):
        iso = pycdlib.PyCdlib(); iso.new(interchange_level=3, rock_ridge='1.09', joliet=3, vol_ident='TEST')
        def add(isop, data, rr, jol):
            iso.add_fp(io.BytesIO(data), len(data), isop, rr_name=rr, joliet_path=jol)
        iso.add_directory('/ISOLINUX', rr_name='isolinux', joliet_path='/isolinux')
        iso.add_directory('/INSTALLAMD', rr_name='install.amd', joliet_path='/install.amd')
        add('/ISOLINUX/ISOLINUX.CFG;1', b'# D-I config version 2.0\n' + b'x' * 130, 'isolinux.cfg', '/isolinux/isolinux.cfg')
        add('/ISOLINUX/TXT.CFG;1', b'label install\n', 'txt.cfg', '/isolinux/txt.cfg')
        add('/INSTALLAMD/VMLINUZ;1', b'KERNEL' * 100, 'vmlinuz', '/install.amd/vmlinuz')
        add('/README.TXT;1', b'readme' * 900, 'README.txt', '/README.txt')
        add('/README.HTM;1', b'<html>' + b'y' * 8800, 'README.html', '/README.html')
        iso.write(path); iso.close()
    src = os.path.join(TMP, 'src.iso'); dst = os.path.join(TMP, 'dst.iso'); mk(src)
    before = open(src, 'rb').read()
    with open(src, 'rb') as f: e0 = mod._nm_iso_entries(f)
    check(e0['/README.TXT']['rr'] == 'README.txt' and e0['/README.HTM']['rr'] == 'README.html', 'Rock Ridge names read: %s' % e0['/README.HTM']['rr'])
    mod._nm_vm_prepare_iso(src, dst, c)
    after = open(dst, 'rb').read()
    with open(dst, 'rb') as f: e1 = mod._nm_iso_entries(f)
    check(len(before) == len(after) and {k: (v['lba'], v['size']) for k, v in e0.items()} == {k: (v['lba'], v['size']) for k, v in e1.items()}, 'image size and every file position/size unchanged')
    iso = pycdlib.PyCdlib(); iso.open(dst)
    def rd(p):
        o = io.BytesIO(); iso.get_file_from_iso_fp(o, iso_path=p); return o.getvalue()
    check(b'file=/cdrom/README.txt' in rd('/ISOLINUX/ISOLINUX.CFG;1') and b'timeout 1' in rd('/ISOLINUX/ISOLINUX.CFG;1'), 'boot config replaced')
    pr = rd('/README.TXT;1').decode()
    check('d-i passwd/username string tpotadmin' in pr and pr.rstrip('\n').endswith('d-i finish-install/reboot_in_progress note'), 'answer file in place, blank-line padding only')
    check(rd('/README.HTM;1').startswith(b'#!/bin/bash') and rd('/INSTALLAMD/VMLINUZ;1') == b'KERNEL' * 100 and rd('/ISOLINUX/TXT.CFG;1') == b'label install\n', 'script in place and untouched files byte-identical')
    iso.close()
    try:
        mod._nm_iso_patch_same_size(dst, {'/ISOLINUX/ISOLINUX.CFG': b'z' * 5000}); check(False, 'too-long text must be refused')
    except ValueError as ex:
        check('do not fit' in str(ex), 'text longer than the file is refused')
    try:
        mod._nm_iso_patch_same_size(dst, {'/NOPE.TXT': b'z'}); check(False, 'missing file must be refused')
    except ValueError:
        check(True, 'missing file refused')
else:
    print('  skip disc-image tests (pycdlib not installed here)')

# ── VM definitions ──
mac = mod._nm_vm_mac('vmware')
check(mac.startswith('00:50:56:') and int(mac.split(':')[3], 16) < 0x40, 'VMware MAC inside its static range: %s' % mac)
check(mod._nm_vm_mac('virtualbox').startswith('08:00:27:'), 'VirtualBox MAC prefix')
vmx = mod._nm_vm_vmx(c, 'D:\\vm\\tpot-install.iso', mac)
check('ethernet0.virtualDev = "e1000"' in vmx and 'pciBridge4.virtualDev = "pcieRootPort"' in vmx and 'bios.bootOrder = "hdd,cdrom"' in vmx and 'memsize = "12288"' in vmx, 'vmx has the settings that fixed the PCIe slot crash')
check('isolation.tools.copy.disable = "TRUE"' in vmx and 'connectionType = "bridged"' in vmx and 'sata0:1.fileName = "D:\\\\vm\\\\tpot-install.iso"' in vmx, 'copy/paste off, bridged, disc path escaped')
p = mod._nm_vm_vmware_plan(c, 'D:\\vm\\tpot.vmx', 'D:\\vm\\tpot.vmdk', 'x.iso', mac)
check(p['create_disk'][:5] == ['C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmware-vdiskmanager.exe', '-c', '-s', '128GB', '-a'] and p['start'][-1] == 'gui', 'VMware disk and start commands')
cvb = dict(c); cvb['tool'] = tools[1]
q = mod._nm_vm_vbox_plan(cvb, 'tpot', 'x.iso', '08:00:27:aa:bb:cc', 'Intel(R) Ethernet')
flat = [' '.join(x) for x in q['create']]
check(any('--nic1 bridged --bridgeadapter1 Intel(R) Ethernet' in x or '--bridgeadapter1' in x for x in flat) and any('--macaddress1 080027AABBCC' in x for x in flat) and any('--boot1 disk --boot2 dvd' in x for x in flat), 'VirtualBox: bridged, fixed MAC, disk then DVD')
check(any('createmedium disk' in x and '131072' in x for x in flat) and q['start'][-1] == 'gui', 'VirtualBox: 128 GB disk, GUI start')
bridge_out = 'Name: VMware Network Adapter VMnet1\nStatus: Up\n\nName: Realtek PCIe GbE Family Controller\nStatus: Up\n\nName: Wi-Fi\nStatus: Down\n'
check(mod._nm_vbox_bridge_adapter(lambda _x: (0, bridge_out)) == 'Realtek PCIe GbE Family Controller', 'VirtualBox bridge adapter: first physical one that is up')

# ── a whole run with fakes ──
def make_job(stop_after=None, vm_alive=True, tpot_after=2, remote_ok=True, cancel_at=None):
    base = os.path.join(TMP, 'run%d' % int(time.time() * 1000))
    cl = dict(c); cl['dir'] = base
    calls = []; hold = {}; probes = {'n': 0}
    def run(args, cwd=None, timeout=15):
        calls.append(list(args))
        if len(args) > 3 and args[-1] == 'list' or (len(args) > 1 and args[1:3] == ['-T', 'ws'] and 'list' in args):
            return (0, 'Total running VMs: 1\n' + hold['j'].vmx + '\n') if vm_alive else (0, 'Total running VMs: 0\n')
        return 0, ''
    def lookup(): return {'name': 'debian-13.7.0-amd64-netinst.iso', 'sha256': 'a' * 64, 'url': 'https://example/x.iso', 'size': 800 * 1048576}
    def download(url, dest, sha, prog, cancel):
        prog(100 * 1048576, 800 * 1048576); open(dest, 'wb').write(b'iso'); return 3
    prepared = []
    def prepare(src, dst, cc):
        open(dst, 'wb').write(b'patched'); prepared.append(sorted(k for k in cc if k in ('os_pw', 'web_pw')))
    def sweep(): return {hold['j'].mac.lower(): '192.168.1.99'}
    def probe(ip, port, timeout=2.0):
        if port == 22: return True
        probes['n'] += 1
        return probes['n'] > tpot_after
    rs = []
    def remote_set(ip, user, pw):
        rs.append((ip, user, pw)); return {'ok': True, 'message': 'Connected to T-Pot at %s.' % ip} if remote_ok else {'ok': False, 'error': 'wrong login'}
    sp = []
    d = {'run': run, 'lookup': lookup, 'download': download, 'prepare': prepare, 'sweep': sweep, 'probe': probe, 'remote_set': remote_set,
         'sleep': lambda s: None, 'host': lambda p: {'ram_mb': 32768, 'cpus': 16, 'free_gb': 500}, 'spawn': lambda a: sp.append(a)}
    j = mod._NMVmDeploy(cl, deps=d, stop_after=stop_after); hold['j'] = j
    j.JOB_CALLS = calls; j.JOB_RS = rs; j.JOB_SP = sp; j.JOB_PREP = prepared
    return j

j = make_job(); j.start(); j.thread.join(20)
st = j.status()
check(st['state'] == 'done' and st['step'] == len(mod._NM_VM_STEPS) and st['ip'] == '192.168.1.99', 'full run reaches done: %s step %s' % (st['state'], st['step']))
check(j.JOB_RS == [('192.168.1.99', 'tpotweb', 'portal.pw-1234')], 'NetSentinel connected with the typed portal login')
check('portal.pw' not in json.dumps(st) and 'a-long-vm' not in json.dumps(st) and 'os_pw' not in j.c and 'web_pw' not in j.c and j.web_pw_kept == '', 'status carries no secrets and the passwords are dropped afterwards')
check(os.path.exists(os.path.join(j.c['dir'], 'tpot', 'tpot.vmx')) and not os.path.exists(os.path.join(j.c['dir'], 'tpot-install.iso')), 'vmx written, discs deleted at the end')
check(any(a[-1] == 'gui' and 'start' in a for a in j.JOB_SP) and any('disconnectNamedDevice' in ' '.join(x) for x in j.JOB_CALLS), 'VM started with a window, install disc disconnected')
check('Reserve 192.168.1.99' in j.msg and j.mac.upper() in j.msg, 'tells the person to reserve the address for the MAC')

j = make_job(stop_after='debian'); j.start(); j.thread.join(20)
check(j.state == 'done' and j.step == 4 and not j.JOB_RS, 'stop_after debian stops before T-Pot (test hook)')

j = make_job(vm_alive=False); j.start(); j.thread.join(20)
check(j.state == 'error' and 'did not start' in j.error, 'VM that never starts is reported: %s' % j.error)

j = make_job(remote_ok=False); j.CONNECT_TIMEOUT_S = 0; j.start(); j.thread.join(20)
check(j.state == 'error' and 'could not log in' in j.error, 'login that never works is reported')

j = make_job(); j.cancel.set(); j.start(); j.thread.join(20)
check(j.state == 'cancelled', 'cancel stops the run')

# ── API ──
r = mod._nm_vm_api({'action': 'check'}, local=False)
check(not r['ok'], 'API refuses other devices')
_r = mod._nm_vm_api(dict(good, action='start', consent=False), local=True, deps={'tools': tools, 'host': lambda p: host})
check('agree to the downloads' in str(_r.get('error')), 'start needs the consent box: %s' % _r)
r = mod._nm_vm_api({'action': 'check'}, local=True, deps={'tools': tools, 'host': lambda p: host, 'lookup': lambda: {'name': 'debian-13.7.0-amd64-netinst.iso', 'sha256': 'b' * 64, 'url': 'u', 'size': 7}})
check(r['ok'] and r['iso']['name'].startswith('debian-13') and 'sha256' not in r['iso'] and r['defaults']['ram_mb'] >= 8192 and r['tools'][0]['kind'] == 'vmware', 'check lists tools, defaults and the installer to be downloaded')
l = mod._nm_vm_iso_lookup(fetch=lambda u: ('%s  debian-13.6.0-amd64-netinst.iso\n%s  debian-13.7.0-amd64-netinst.iso\n%s  debian-13.7.0-amd64-DVD-1.iso\n' % ('1' * 64, '2' * 64, '3' * 64)), head=lambda u: 777)
check(l['name'] == 'debian-13.7.0-amd64-netinst.iso' and l['sha256'] == '2' * 64 and l['size'] == 777, 'newest netinst picked from the checksum list')
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); sys.exit(1 if fails else 0)
