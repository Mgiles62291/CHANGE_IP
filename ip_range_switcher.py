"""
IP Range Switcher – Windows (v1.2)
-----------------------------------
 * Pick any network adapter (PowerShell Get‑NetAdapter).
 * Store unlimited static‑IP profiles in `ip_profiles.json`.
 * One‑click apply or revert to DHCP.
 * NEW: Profile editor is a **single form** (no more 5 pop‑ups).
 * Pure standard library; PyInstaller‑friendly.
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
    """Run a PowerShell one‑liner and capture stdout."""
    res = subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True)
    return res.stdout.strip()


# ---------------------------------------------------------------------------
# Adapter enumeration & network changes
# ---------------------------------------------------------------------------

def list_adapters():
    """Return every *physical* adapter name (even if disconnected)."""
    ps = (
        "Get-NetAdapter | Where { $_.HardwareInterface -eq $true -and $_.InterfaceDescription -notmatch 'Loopback' } "
        "| Select -ExpandProperty Name")
    return [l.strip() for l in powershell(ps).splitlines() if l.strip()]


def _run_netsh(args):
    subprocess.run(['netsh'] + args, capture_output=True, text=True)


def apply_profile(adapter: str, p: dict):
    if not adapter or not p:
        return
    _run_netsh(['interface', 'ip', 'set', 'address', f'name={adapter}', 'static', p['ip'], p['mask'], p['gw'], '1'])
    _run_netsh(['interface', 'ip', 'set', 'dns', f'name={adapter}', 'static', p['dns1'], 'primary'])
    if p.get('dns2'):
        _run_netsh(['interface', 'ip', 'add', 'dns', f'name={adapter}', p['dns2'], 'index=2'])


def set_dhcp(adapter: str):
    _run_netsh(['interface', 'ip', 'set', 'address', f'name={adapter}', 'dhcp'])
    _run_netsh(['interface', 'ip', 'set', 'dns', f'name={adapter}', 'dhcp'])


# ---------------------------------------------------------------------------
# Custom dialog for adding/editing a profile (single window)
# ---------------------------------------------------------------------------

class ProfileDialog(simpledialog.Dialog):
    def __init__(self, parent, title, defaults=None):
        self.defaults = defaults or {}
        super().__init__(parent, title)

    def body(self, master):
        fields = [
            ('IP address', 'ip'),
            ('Subnet mask', 'mask'),
            ('Gateway', 'gw'),
            ('Primary DNS', 'dns1'),
            ('Secondary DNS (optional)', 'dns2'),
        ]
        self.entries = {}
        for r, (label, key) in enumerate(fields):
            ttk.Label(master, text=label+':').grid(row=r, column=0, sticky='e')
            e = ttk.Entry(master, width=25)
            e.grid(row=r, column=1, padx=5, pady=2)
            e.insert(0, self.defaults.get(key, ''))
            self.entries[key] = e
        return self.entries['ip']  # initial focus

    def validate(self):
        ip = self.entries['ip'].get().strip()
        mask = self.entries['mask'].get().strip()
        gw = self.entries['gw'].get().strip()
        if not ip or not mask or not gw:
            messagebox.showerror('Error', 'IP, Mask, and Gateway are required.')
            return False
        return True

    def apply(self):
        self.result = {k: e.get().strip() for k, e in self.entries.items()}


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
        for t, fn in [('Add', self._add), ('Edit', self._edit), ('Delete', self._delete)]:
            ttk.Button(btnfrm, text=t, width=10, command=fn).grid(pady=2)

        ttk.Button(frm, text='Apply Profile', command=self._apply).grid(column=0, row=6, columnspan=2, sticky='we', pady=10)
        ttk.Button(frm, text='Back to DHCP', command=self._dhcp).grid(column=2, row=6, pady=10)

        self._refresh_profiles()

    # ---------- helpers ----------
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
    def _add(self):
        name = simpledialog.askstring('New Profile', 'Profile name:')
        if not name:
            return
        dlg = ProfileDialog(self, f'Profile: {name}')
        if dlg.result:
            self.profiles[name] = dlg.result
            save_profiles(self.profiles)
            self._refresh_profiles()

    def _edit(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        name = self.profile_lst.get(sel)
        dlg = ProfileDialog(self, f'Edit: {name}', self.profiles[name])
        if dlg.result:
            self.profiles[name] = dlg.result
            save_profiles(self.profiles)

    def _delete(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        name = self.profile_lst.get(sel)
        if messagebox.askyesno('Delete', f'Delete profile “{name}”?'):
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
        print('This tool runs on Windows only.')
        sys.exit(1)
    if shutil.which('powershell') is None:
        messagebox.showerror('Error', 'PowerShell is required but not found.')
        sys.exit(1)

    App().mainloop()
