import json, os, subprocess, sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

PROFILE_FILE = 'ip_profiles.json'


def load_profiles():
    if not os.path.exists(PROFILE_FILE):
        return {}
    with open(PROFILE_FILE, 'r') as f:
        return json.load(f)


def save_profiles(profiles):
    with open(PROFILE_FILE, 'w') as f:
        json.dump(profiles, f, indent=2)


def list_adapters():
    """Return friendly names of all IPv4-capable adapters."""
    result = subprocess.run(
        ['netsh', 'interface', 'ipv4', 'show', 'interfaces'],
        capture_output=True, text=True
    )
    adapters = []
    for line in result.stdout.splitlines():
        if 'Connected' in line or 'Disconnected' in line:
            parts = line.split()
            if len(parts) >= 5:
                adapters.append(' '.join(parts[4:]))
    return adapters


def apply_profile(adapter, profile):
    if not adapter or not profile:
        return
    ip, mask, gw = profile['ip'], profile['mask'], profile['gw']
    dns1, dns2 = profile['dns1'], profile['dns2']

    cmds = [
        ['netsh', 'interface', 'ip', 'set', 'address',
         f'name={adapter}', 'static', ip, mask, gw, '1'],
        ['netsh', 'interface', 'ip', 'set', 'dns',
         f'name={adapter}', 'static', dns1, 'primary']
    ]
    if dns2:
        cmds.append(['netsh', 'interface', 'ip', 'add', 'dns',
                     f'name={adapter}', dns2, 'index=2'])
    for cmd in cmds:
        subprocess.run(cmd, capture_output=True)


def set_dhcp(adapter):
    subprocess.run(['netsh', 'interface', 'ip', 'set',
                    'address', f'name={adapter}', 'dhcp'], capture_output=True)
    subprocess.run(['netsh', 'interface', 'ip', 'set',
                    'dns', f'name={adapter}', 'dhcp'], capture_output=True)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('IP Range Switcher')
        self.resizable(False, False)
        self.profiles = load_profiles()
        self._build_ui()
        self._refresh_adapters()

    # ---------- UI ----------
    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.grid()

        ttk.Label(frm, text='Network adapter:').grid(
            column=0, row=0, sticky='w')
        self.adapter_cmb = ttk.Combobox(frm, state='readonly', width=30)
        self.adapter_cmb.grid(column=1, row=0, sticky='w')
        ttk.Button(frm, text='Refresh',
                   command=self._refresh_adapters).grid(column=2, row=0)

        ttk.Label(frm, text='Profiles:').grid(
            column=0, row=1, sticky='nw', pady=(10, 0))
        self.profile_lst = tk.Listbox(frm, height=6, width=30)
        self.profile_lst.grid(column=1, row=1, rowspan=4,
                              sticky='w', pady=(10, 0))

        btnfrm = ttk.Frame(frm)
        btnfrm.grid(column=2, row=1, rowspan=4, sticky='n')
        ttk.Button(btnfrm, text='Add', width=10,
                   command=self._add).grid(pady=2)
        ttk.Button(btnfrm, text='Edit', width=10,
                   command=self._edit).grid(pady=2)
        ttk.Button(btnfrm, text='Delete', width=10,
                   command=self._delete).grid(pady=2)

        ttk.Button(frm, text='Apply Profile',
                   command=self._apply).grid(column=0, row=6,
                                             columnspan=2, sticky='we', pady=10)
        ttk.Button(frm, text='Back to DHCP',
                   command=self._dhcp).grid(column=2, row=6, pady=10)

        self._refresh_profiles()

    # ---------- Helpers ----------
    def _refresh_adapters(self):
        self.adapter_cmb['values'] = list_adapters()
        if self.adapter_cmb['values']:
            self.adapter_cmb.current(0)

    def _refresh_profiles(self):
        self.profile_lst.delete(0, 'end')
        for name in self.profiles:
            self.profile_lst.insert('end', name)

    # ---------- Profile CRUD ----------
    def _add(self):
        name = simpledialog.askstring('Profile name', 'Name this profile:')
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
        if messagebox.askyesno('Delete', f'Delete profile {name}?'):
            del self.profiles[name]
            save_profiles(self.profiles)
            self._refresh_profiles()

    def _prompt_profile(self, defaults):
        ask = simpledialog.askstring
        new = {}
        new['ip'] = ask('IP address', 'Static IP:',
                        initialvalue=defaults.get('ip', ''))
        new['mask'] = ask('Subnet mask', 'Mask (e.g. 255.255.255.0):',
                          initialvalue=defaults.get('mask', '255.255.255.0'))
        new['gw'] = ask('Gateway', 'Gateway IP:',
                        initialvalue=defaults.get('gw', ''))
        new['dns1'] = ask('DNS 1', 'Primary DNS:',
                          initialvalue=defaults.get('dns1', ''))
        new['dns2'] = ask('DNS 2', 'Secondary DNS (optional):',
                          initialvalue=defaults.get('dns2', ''))
        return new

    # ---------- Actions ----------
    def _apply(self):
        sel = self.profile_lst.curselection()
        if not sel:
            return
        name = self.profile_lst.get(sel)
        adapter = self.adapter_cmb.get()
        apply_profile(adapter, self.profiles[name])
        messagebox.showinfo('Done', f'Applied profile “{name}”.')

    def _dhcp(self):
        adapter = self.adapter_cmb.get()
        set_dhcp(adapter)
        messagebox.showinfo('DHCP', 'Adapter now uses DHCP.')

# ---------- Main ----------
if __name__ == '__main__':
    if not sys.platform.startswith('win'):
        messagebox.showerror('Error', 'This tool only works on Windows.')
        sys.exit(1)
    App().mainloop()
