"""
IP Range Switcher – Windows (v1.1)
-----------------------------------
 * Pick any active network adapter (uses PowerShell Get‑NetAdapter).
 * Store unlimited static‑IP profiles in `ip_profiles.json`.
 * One‑click apply or revert to DHCP.
 * No external packages; PyInstaller‑friendly.
"""

import json, os, subprocess, sys, shutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

PROFILE_FILE = 'ip_profiles.json'

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def load_profiles():
    if not os.path.exists(PROFILE_FILE):
        return {}
    with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_profiles(profiles):
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, indent=2)


def powershell(cmd: str) -> str:
    """Run a PowerShell one‑liner and return stdout text (empty string on error)."""
    result = subprocess.run(
        ['powershell', '-NoProfile', '-Command', cmd],
        capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Adapter enumeration & network changes
# ---------------------------------------------------------------------------

def list_adapters():
    """Return a list of UP adapters' friendly names (no virtual/loopback)."""
    ps = (
        "Get-NetAdapter | Where {$_.Status -eq 'Up' -and $_.HardwareInterface -eq $true} "
        "| Select -ExpandProperty Name")
    out = powershell(ps)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines if lines else ["(no active adapter found)"]


def _run_netsh(args):
    """Helper that wraps subprocess for netsh commands."""
    subprocess.run(['netsh'] + args, capture_output=True, text=True)


def apply_profile(adapter: str, p: dict):
    if not adapter or '(no active' in adapter or not p:
        return
    _run_netsh(['interface', 'ip', 'set', 'address', f'name={adapter}', 'static',
                p['ip'], p['mask'], p['gw'], '1'])
    _run_netsh(['interface', 'ip', 'set', 'dns', f'name={adapter}', 'static', p['dns1'], 'primary'])
    if p.get('dns2'):
        _run_netsh(['interface', 'ip', 'add', 'dns', f'name={adapter}', p['dns2'], 'index=2'])


def set_dhcp(adapter: str):
    if not adapter or '(no active' in adapter:
        return
    _run_netsh(['interface', 'ip', 'set', 'address', f'name={adapter}', 'dhcp'])
    _run_netsh(['interface', 'ip', 'set', 'dns', f'name={adapter}', 'dhcp'])


# ---------------------------------------------------------------------------
# Tk GUI
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('IP Range Switcher')
        self.resizable(False, False)
        self.profiles = load_profiles()
        self._build_ui()
        self._refresh_adapters()

    # ---------- UI builders ----------
    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.grid()

        ttk.Label(frm, text='Network adapter:').grid(column=0, row=0, sticky='w')
        self.adapter_cmb = ttk.Combobox(frm, state='readonly', width=35)
        self.adapter_cmb.grid(column=1, row=0, sticky='w')
        ttk.Button(frm, text='Refresh', command=self._refresh_adapters).grid(column=2, row=0)

        ttk.Label(frm, text='Profiles:').grid(column=0, row=1, sticky='nw', pady=(10, 0))
        self.profile_lst = tk.Listbox(frm, height=6, width=35)
        self.profile_lst.grid(column=1, row=1, rowspan=4, sticky='w', pady=(10, 0))

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(column=2, row=1, rowspan=4, sticky='n')
        for txt, cmd in [('Add', self._add), ('Edit', self._edit), ('Delete', self._delete)]:
            ttk.Button(btnfrm, text=txt, width=10, command=cmd).grid(pady=2)

        ttk.Button(frm, text='Apply Profile', command=self._apply).grid(column=0, row=6, columnspan=2, sticky='we', pady=10)
        ttk.Button(frm, text='Back to DHCP', command=self._dhcp).grid(column=2, row=6, pady=10)

        self._refresh_profiles()

    # ---------- Refresh helpers ----------
    def _refresh_adapters(self):
        vals = list_adapters()
        self.adapter_cmb['values'] = vals
        if vals:
            self.adapter_cmb.current(0)
        else:
            self.adapter_cmb.set('(no adapter)')

    def _refresh_profiles(self):
        self.profile_lst.delete(0, 'end')
        for name in self.profiles:
            self.profile_lst.insert('end', name)

    # ---------- CRUD ----------
    def _prompt_profile(self, defaults):
        ask = simpledialog.askstring
        out = {}
        out['ip'] = ask('IP', 'Static IP address:', initialvalue=defaults.get('ip', ''))
        out['mask'] = ask('Mask', 'Subnet mask:', initialvalue=defaults.get('mask', '255.255.255.0'))
        out['gw'] = ask('Gateway', 'Gateway:', initialvalue=defaults.get('gw', ''))
        out['dns1'] = ask('DNS1', 'Primary DNS:', initialvalue=defaults.get('dns1', ''))
        out['dns2'] = ask('DNS2', 'Secondary DNS (optional):', initialvalue=defaults.get('dns2', ''))
        return out

    def _add(self):
        name = simpledialog.askstring('Add Profile', 'Profile name:')
        if not name:
            return
        self.profiles[name] = self._prompt_profile({})
        save_profiles(self.profiles)
        self._refresh_profiles()

    def _edit(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        name = self.profile_lst.get(sel)
        self.profiles[name] = self._prompt_profile(self.profiles[name])
        save_profiles(self.profiles)

    def _delete(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        name = self.profile_lst.get(sel)
        if messagebox.askyesno('Delete', f'Delete profile "{name}"?'):
            self.profiles.pop(name, None)
            save_profiles(self.profiles)
            self._refresh_profiles()

    # ---------- Actions ----------
    def _apply(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        adapter = self.adapter_cmb.get()
        profile_name = self.profile_lst.get(sel)
        apply_profile(adapter, self.profiles[profile_name])
        messagebox.showinfo('Done', f'Applied “{profile_name}” to {adapter}.')

    def _dhcp(self):
        adapter = self.adapter_cmb.get()
        set_dhcp(adapter)
        messagebox.showinfo('DHCP', f'{adapter} now set to DHCP.')


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    if not sys.platform.startswith('win'):
        print('This utility works on Windows only.')
        sys.exit(1)
    if shutil.which('powershell') is None:
        messagebox.showerror('Error', 'PowerShell is required but not found.')
        sys.exit(1)

    App().mainloop()
