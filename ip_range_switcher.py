"""
IP Range Switcher – Windows  (v2.0)
-----------------------------------
• Pick any adapter (PowerShell Get‑NetAdapter).
• Store unlimited static‑IP profiles in ip_profiles.json.
• One‑click apply or revert to DHCP.
• NEW: Proper Add/Edit dialog (single form), no more name‑only prompt.
• Pure std‑lib; PyInstaller‑friendly.
"""

import json, os, subprocess, sys, tkinter as tk
from tkinter import ttk, messagebox

PROFILE_FILE = 'ip_profiles.json'


# ---------- Helper wrappers ----------
def powershell(cmd: str) -> str:
    """Run arbitrary PowerShell and return stdout."""
    cp = subprocess.run(['powershell', '-NoLogo', '-Command', cmd],
                        capture_output=True, text=True)
    return cp.stdout.strip()


def list_adapters():
    """Return ALL physical adapters (Up or Down, non‑loopback)."""
    ps = ("Get-NetAdapter | "
          "Where {$_.HardwareInterface -eq $true -and "
          "$_.InterfaceDescription -notmatch 'Loopback'} | "
          "Select -ExpandProperty Name")
    return [l for l in powershell(ps).splitlines() if l]


def apply_profile(adapter: str, p: dict):
    cmds = [
        ['netsh', 'interface', 'ip', 'set', 'address',
         f'name={adapter}', 'static', p['ip'], p['mask'], p['gw'], '1'],
        ['netsh', 'interface', 'ip', 'set', 'dns',
         f'name={adapter}', 'static', p['dns1'], 'primary']
    ]
    if p['dns2']:
        cmds.append(['netsh', 'interface', 'ip', 'add', 'dns',
                     f'name={adapter}', p['dns2'], 'index=2'])
    for c in cmds:
        subprocess.run(c, capture_output=True)


def set_dhcp(adapter: str):
    subprocess.run(['netsh', 'interface', 'ip', 'set',
                    'address', f'name={adapter}', 'dhcp'], capture_output=True)
    subprocess.run(['netsh', 'interface', 'ip', 'set',
                    'dns', f'name={adapter}', 'dhcp'], capture_output=True)


def load_profiles():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE) as f:
            return json.load(f)
    return {}


def save_profiles(p):
    with open(PROFILE_FILE, 'w') as f:
        json.dump(p, f, indent=2)


# ---------- Profile editor window ----------
class ProfileEditor(tk.Toplevel):
    def __init__(self, master, name='', data=None, callback=None):
        super().__init__(master)
        self.title('Profile editor')
        self.resizable(False, False)
        self.callback = callback
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # defaults
        data = data or {'ip': '', 'mask': '255.255.255.0',
                        'gw': '', 'dns1': '', 'dns2': ''}

        ttk.Label(self, text='Profile name:').grid(row=0, column=0, sticky='e')
        self.e_name = ttk.Entry(self, width=25)
        self.e_name.grid(row=0, column=1, padx=5, pady=3)
        self.e_name.insert(0, name)

        fields = ('ip', 'mask', 'gw', 'dns1', 'dns2')
        self.entries = {}
        for r, fld in enumerate(fields, start=1):
            ttk.Label(self, text=f'{fld.upper()}:').grid(
                row=r, column=0, sticky='e')
            e = ttk.Entry(self, width=25)
            e.grid(row=r, column=1, padx=5, pady=3)
            e.insert(0, data.get(fld, ''))
            self.entries[fld] = e

        ttk.Button(self, text='Save', command=self._save).grid(
            row=6, column=0, pady=6)
        ttk.Button(self, text='Cancel', command=self.destroy).grid(
            row=6, column=1, pady=6)

    def _save(self):
        name = self.e_name.get().strip()
        if not name:
            messagebox.showerror('Error', 'Profile needs a name.')
            return
        newdata = {fld: e.get().strip() for fld, e in self.entries.items()}
        if self.callback:
            self.callback(name, newdata)
        self.destroy()


# ---------- Main GUI ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('IP Range Switcher (v2.0)')
        self.resizable(False, False)

        self.profiles = load_profiles()
        self._build_ui()
        self._refresh_adapters()
        self._refresh_profiles()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.grid()

        ttk.Label(frm, text='Adapter:').grid(row=0, column=0, sticky='e')
        self.cmb_adp = ttk.Combobox(frm, width=30, state='readonly')
        self.cmb_adp.grid(row=0, column=1, sticky='w')
        ttk.Button(frm, text='Refresh', command=self._refresh_adapters).grid(
            row=0, column=2, padx=4)

        ttk.Label(frm, text='Profiles:').grid(row=1, column=0, sticky='ne',
                                              pady=(10, 0))
        self.lst = tk.Listbox(frm, height=7, width=30)
        self.lst.grid(row=1, column=1, rowspan=4, sticky='w', pady=(10, 0))

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(row=1, column=2, rowspan=4, sticky='n', pady=(10, 0))
        ttk.Button(btnfrm, text='Add', width=10,
                   command=self._add).grid(pady=2)
        ttk.Button(btnfrm, text='Edit', width=10,
                   command=self._edit).grid(pady=2)
        ttk.Button(btnfrm, text='Delete', width=10,
                   command=self._delete).grid(pady=2)

        ttk.Button(frm, text='Apply profile', width=20,
                   command=self._apply).grid(row=6, column=0, columnspan=2,
                                             pady=8)
        ttk.Button(frm, text='Back to DHCP', width=15,
                   command=self._dhcp).grid(row=6, column=2, pady=8)

    # ---------- List refresh ----------
    def _refresh_adapters(self):
        lst = list_adapters()
        self.cmb_adp['values'] = lst
        if lst:
            self.cmb_adp.current(0)

    def _refresh_profiles(self):
        self.lst.delete(0, 'end')
        for name in self.profiles:
            self.lst.insert('end', name)

    # ---------- CRUD ----------
    def _add(self):
        ProfileEditor(self, callback=self._save_profile)

    def _edit(self):
        sel = self.lst.curselection()
        if not sel:
            return
        name = self.lst.get(sel)
        ProfileEditor(self, name, self.profiles[name],
                      callback=self._save_profile)

    def _save_profile(self, name, data):
        self.profiles[name] = data
        save_profiles(self.profiles)
        self._refresh_profiles()

    def _delete(self):
        sel = self.lst.curselection()
        if not sel:
            return
        name = self.lst.get(sel)
        if messagebox.askyesno('Delete', f'Delete profile “{name}”?'):
            del self.profiles[name]
            save_profiles(self.profiles)
            self._refresh_profiles()

    # ---------- Actions ----------
    def _apply(self):
        sel = self.lst.curselection()
        if not sel:
            return
        name = self.lst.get(sel)
        adapter = self.cmb_adp.get()
        apply_profile(adapter, self.profiles[name])
        messagebox.showinfo('Done', f'Applied “{name}” to {adapter}')

    def _dhcp(self):
        adapter = self.cmb_adp.get()
        set_dhcp(adapter)
        messagebox.showinfo('DHCP', f'{adapter} now set to DHCP')


# ---------- Main ----------
if __name__ == '__main__':
    if not sys.platform.startswith('win'):
        messagebox.showerror('Error', 'Windows only.')
        sys.exit(1)
    App().mainloop()
