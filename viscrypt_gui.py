import os
import threading
import time
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
UPLOADS = os.path.join(OUTPUT_DIR, 'uploads')
SHARES = os.path.join(OUTPUT_DIR, 'shares')
RECON = os.path.join(OUTPUT_DIR, 'recon')

for p in (OUTPUT_DIR, UPLOADS, SHARES, RECON):
    os.makedirs(p, exist_ok=True)

try:
    from viscrypt import generate_multiple_shares, reconstruct, send_shares_over_network, start_receiver
except Exception as e:
    print('Failed to import viscrypt functions:', e)
    raise


class VEITAGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('VEITA — GUI')
        # Start with a more compact default size and set a sensible minimum
        self.geometry('860x520')
        self.minsize(700, 480)
        # center window on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        ww = self.winfo_width(); wh = self.winfo_height()
        x = max(0, (sw - ww) // 2); y = max(0, (sh - wh) // 2)
        self.geometry(f'+{x}+{y}')

        self.receivers = {}
        # status variable (create early so builders can update it)
        self.status_var = tk.StringVar(value='Ready')
        # vars used by reconstruct helpers (prevent AttributeError if used)
        self.recon_files_var = tk.StringVar()
        self.recon_out_var = tk.StringVar(value=os.path.join(RECON, 'reconstruction.png'))

        # Menu
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label='Exit', command=self.quit)
        menubar.add_cascade(label='File', menu=filem)
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label='About', command=lambda: webbrowser.open('https://github.com/iryandae/VEITA/tree/main?tab=readme-ov-file#gui-version'))
        menubar.add_cascade(label='Help', menu=helpm)
        self.config(menu=menubar)

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=8, pady=6)

        self.tab_generate = ttk.Frame(nb, padding=10)
        self.tab_send = ttk.Frame(nb, padding=10)
        self.tab_receiver = ttk.Frame(nb, padding=10)
        self.tab_log = ttk.Frame(nb, padding=10)

        nb.add(self.tab_send, text='Send')
        nb.add(self.tab_receiver, text='Receive')
        nb.add(self.tab_log, text='Log')

        self._build_send()
        self._build_receiver()
        self._build_log()

        # Status bar
        status = ttk.Label(self, textvariable=self.status_var, relief='sunken', anchor='w')
        status.pack(fill='x', side='bottom')

        # periodic UI updates
        self.after(1000, self._periodic)

    def _build_send(self):
        f = self.tab_send
        # Generation frame (top)
        ttk.Label(f, text='Input image:').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.gen_input_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.gen_input_var, width=60).grid(row=0, column=1, padx=4, pady=4, sticky='ew')
        ttk.Button(f, text='Browse', command=self._browse_gen_input).grid(row=0, column=2, padx=4, pady=4, sticky='ew')

        ttk.Label(f, text='Number of shares:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.gen_n_var = tk.IntVar(value=2)
        ttk.Entry(f, textvariable=self.gen_n_var, width=10).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        ttk.Button(f, text='Generate', command=self._generate).grid(row=1, column=2, sticky='ew', padx=4, pady=4)

        # Separator / spacer
        sep = ttk.Separator(f, orient='horizontal')
        sep.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(8, 8))

        # Targets and port above list
        ttk.Label(f, text='Targets:').grid(row=3, column=0, sticky='w', padx=4, pady=4)
        self.send_targets_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.send_targets_var, width=60).grid(row=3, column=1, padx=4, pady=4, sticky='ew')
        self.send_port_label = ttk.Label(f, text='Start port:')
        self.send_port_label.grid(row=4, column=0, sticky='w', padx=4, pady=4)
        self.send_port_var = tk.StringVar(value='8000')
        self.send_port_entry = ttk.Entry(f, textvariable=self.send_port_var, width=14)
        self.send_port_entry.grid(row=4, column=1, sticky='ew', padx=4, pady=4)
        self.send_use_start_port = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f,
            text='Auto-assign ports',
            variable=self.send_use_start_port,
            command=self._toggle_send_start_port
        ).grid(row=4, column=2, sticky='w', padx=4, pady=4)

        # Files list area
        ttk.Label(f, text='Available shares:').grid(row=5, column=0, sticky='w', padx=4, pady=4)
        self.files_listbox = tk.Listbox(f, selectmode='extended', height=12)
        self.files_listbox.grid(row=6, column=0, columnspan=3, sticky='nsew', padx=4, pady=4)
        # scrollbar
        sb = ttk.Scrollbar(f, orient='vertical', command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=sb.set)
        sb.grid(row=6, column=3, sticky='ns')

        # Controls under list
        ttk.Button(f, text='Refresh', command=self._refresh_file_list).grid(row=7, column=0, sticky='w', padx=4, pady=4)
        ttk.Button(f, text='Send Selected', command=self._send_selected).grid(row=7, column=2, sticky='e', padx=4, pady=4)

        f.columnconfigure(1, weight=1)
        self._refresh_file_list()

    def _build_receiver(self):
        f = self.tab_receiver
        # Destination row at top
        ttk.Label(f, text='Save folder:').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.rc_dest = tk.StringVar(value=RECON)
        ttk.Entry(f, textvariable=self.rc_dest, width=50).grid(row=0, column=1, columnspan=4, padx=4, pady=4, sticky='ew')
        ttk.Button(f, text='Browse', command=self._browse_rc_dest).grid(row=0, column=5, padx=4, pady=4, sticky='w')

        # Host / Port / Scramble row (mirrors Send tab alignment)
        ttk.Label(f, text='Host:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.rc_host = tk.StringVar(value='0.0.0.0')
        ttk.Entry(f, textvariable=self.rc_host, width=18).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        self.rc_port_label = ttk.Label(f, text='Port:')
        self.rc_port_label.grid(row=2, column=1, sticky='w', padx=4, pady=4)
        self.rc_port = tk.StringVar(value='8000')
        self.rc_port_entry = ttk.Entry(f, textvariable=self.rc_port, width=12)
        self.rc_port_entry.grid(row=2, column=2, sticky='w', padx=2, pady=4)

        self.rc_use_scramble = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text='Scramble Ports', variable=self.rc_use_scramble, command=self._toggle_scramble).grid(row=2, column=0, sticky='w', padx=4, pady=4)

        # Max files row
        self.rc_use_max = tk.BooleanVar(value=False)
        self.rc_max = tk.StringVar(value='')
        ttk.Checkbutton(f, text='Limit max files', variable=self.rc_use_max, command=self._toggle_max).grid(row=4, column=0, sticky='w', padx=4, pady=4)
        lbl_max = ttk.Label(f, text='Max files:')
        ent_max = ttk.Entry(f, textvariable=self.rc_max, width=10)
        lbl_max.grid(row=4, column=1, sticky='w', padx=4, pady=4)
        ent_max.grid(row=4, column=2, sticky='w', padx=2, pady=4)
        self._max_widgets = [lbl_max, ent_max]

        # Reconstruct row
        self.rc_use_recon_after = tk.BooleanVar(value=False)
        self.rc_recon_after = tk.StringVar(value='')
        ttk.Checkbutton(f, text='Auto reconstruct', variable=self.rc_use_recon_after, command=self._toggle_recon).grid(row=5, column=0, sticky='w', padx=4, pady=4)
        lbl_recon = ttk.Label(f, text='After N files:')
        ent_recon = ttk.Entry(f, textvariable=self.rc_recon_after, width=10)
        lbl_recon.grid(row=5, column=1, sticky='w', padx=4, pady=4)
        ent_recon.grid(row=5, column=2, sticky='w', padx=2, pady=4)
        self._recon_widgets = [lbl_recon, ent_recon]

        sep = ttk.Separator(f, orient='horizontal')
        sep.grid(row=6, column=0, columnspan=6, sticky='ew', pady=(8, 8))

        # Receiver list area (distinct from Send list)
        ttk.Label(f, text='Receivers:').grid(row=7, column=0, sticky='w', padx=4, pady=4)
        self.receivers_listbox = tk.Listbox(f, selectmode='extended', height=11)
        self.receivers_listbox.grid(row=8, column=0, columnspan=6, sticky='nsew', padx=4, pady=4)
        rsb = ttk.Scrollbar(f, orient='vertical', command=self.receivers_listbox.yview)
        self.receivers_listbox.configure(yscrollcommand=rsb.set)
        rsb.grid(row=8, column=6, sticky='ns')

        ttk.Button(f, text='Start Receiver', command=self._start_receiver).grid(row=9, column=5, sticky='e', padx=4, pady=4)
        ttk.Button(f, text='Stop', command=self._stop_selected_receiver).grid(row=9, column=0, sticky='w', padx=4, pady=4)

        for c in range(1, 5):
            f.columnconfigure(c, weight=1)

        # hide optional rows initially
        self._toggle_scramble()
        self._toggle_max()
        self._toggle_recon()

    def _build_log(self):
        f = self.tab_log
        # Make the log read-only by default; enable briefly when appending
        self.log_text = tk.Text(f, wrap='word', state='disabled')
        # add a scrollbar
        sb = ttk.Scrollbar(f, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(fill='both', expand=True, side='left')
        sb.pack(fill='y', side='right')

    # helpers
    def _log(self, msg):
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        # temporarily enable the widget to insert text, then disable again
        try:
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'[{ts}] {msg}\n')
            self.log_text.see('end')
        finally:
            self.log_text.configure(state='disabled')

    def _set_status(self, text):
        self.status_var.set(text)

    def _browse_gen_input(self):
        p = filedialog.askopenfilename(title='Select input image')
        if p:
            self.gen_input_var.set(p)

    def _browse_recon_files(self):
        p = filedialog.askopenfilenames(title='Select share files')
        if p:
            self.recon_files_var.set(';;'.join(p))

    def _browse_rc_dest(self):
        p = filedialog.askdirectory(title='Select destination directory')
        if p:
            self.rc_dest.set(p)

    def _generate(self):
        inp = self.gen_input_var.get()
        n = self.gen_n_var.get()
        if not inp or not os.path.exists(inp):
            messagebox.showerror('Error', 'Input image not selected or missing')
            return
        prefix = os.path.join(SHARES, os.path.splitext(os.path.basename(inp))[0])
        def _work():
            self._set_status('Generating shares...')
            self._log(f'Generating {n} shares for {inp}...')
            files = generate_multiple_shares(inp, prefix, int(n))
            if files:
                self._log('Saved shares: ' + ', '.join(files))
            else:
                self._log('Generation failed (see console)')
            self._refresh_file_list()
            self._set_status('Ready')
        threading.Thread(target=_work, daemon=True).start()

    def _reconstruct(self):
        raw = self.recon_files_var.get()
        if not raw:
            messagebox.showerror('Error', 'No share files specified')
            return
        parts = [p for p in raw.split(';;') if p]
        outp = self.recon_out_var.get()
        if not outp:
            messagebox.showerror('Error', 'No output path specified')
            return
        def _work():
            self._set_status('Reconstructing...')
            self._log('Reconstructing...')
            reconstruct(parts, outp)
            self._log(f'Reconstruction saved to {outp}')
            self._refresh_file_list()
            self._set_status('Ready')
        threading.Thread(target=_work, daemon=True).start()

    def _refresh_file_list(self):
        self.files_listbox.delete(0, 'end')
        for root, _, files in os.walk(OUTPUT_DIR):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, OUTPUT_DIR).replace('\\', '/')
                self.files_listbox.insert('end', rel)
        self._set_status(f'Files refreshed ({self.files_listbox.size()} items)')

    def _send_selected(self):
        sel = [self.files_listbox.get(i) for i in self.files_listbox.curselection()]
        if not sel:
            messagebox.showinfo('Send', 'No files selected')
            return
        targets = self.send_targets_var.get()
        start_port_raw = self.send_port_var.get().strip()
        target_items = [t.strip() for t in re.split(r"[;,]", targets) if t.strip()]
        if not target_items:
            messagebox.showerror('Error', 'No targets specified')
            return

        final_targets = []
        missing_hosts = []
        with_ports = []
        for t in target_items:
            if ':' in t:
                host, p = t.rsplit(':', 1)
                host = host.strip()
                p = p.strip()
                if not host or not p:
                    messagebox.showerror('Error', f'Invalid target entry: {t}')
                    return
                try:
                    with_ports.append((host, int(p)))
                except Exception:
                    messagebox.showerror('Error', f'Port must be a number in target: {t}')
                    return
            else:
                missing_hosts.append(t)

        auto_mode = self.send_use_start_port.get()
        manual_ports = []
        if auto_mode:
            try:
                base_port = int(start_port_raw)
            except Exception:
                messagebox.showerror('Error', 'Start port must be a number')
                return
            if base_port <= 0:
                messagebox.showerror('Error', 'Start port must be greater than 0')
                return
        else:
            # parse manual ports list (comma/semicolon separated)
            if not start_port_raw:
                messagebox.showerror('Error', 'Provide port(s) when auto-assign is off')
                return
            for p in re.split(r"[;,]", start_port_raw):
                if not p.strip():
                    continue
                try:
                    manual_ports.append(int(p.strip()))
                except Exception:
                    messagebox.showerror('Error', f'Ports must be numbers (got "{p}")')
                    return
            if len(manual_ports) < len(missing_hosts):
                messagebox.showerror('Error', 'Not enough ports for hosts without explicit ports')
                return

        # build final targets preserving order
        auto_idx = 0
        manual_idx = 0
        for t in target_items:
            if ':' in t:
                host, p = t.rsplit(':', 1)
                final_targets.append((host.strip(), int(p.strip())))
            else:
                if auto_mode:
                    assigned = base_port + auto_idx
                    auto_idx += 1
                else:
                    assigned = manual_ports[manual_idx]
                    manual_idx += 1
                final_targets.append((t, assigned))

        targets_for_send = [f"{h}:{p}" for h, p in final_targets]
        start_port = final_targets[0][1] if final_targets else 8000
        paths = [os.path.join(OUTPUT_DIR, s) for s in sel]
        def _work():
            self._set_status('Sending...')
            mode_desc = 'auto' if auto_mode else 'manual ports'
            self._log(f'Sending {len(paths)} files to {targets_for_send} ({mode_desc})')
            results = send_shares_over_network(paths, targets_for_send, default_port=int(start_port))
            self._log('Send results: ' + str(results))
            self._set_status('Ready')
        threading.Thread(target=_work, daemon=True).start()

    def _toggle_send_start_port(self):
        if self.send_use_start_port.get():
            self.send_port_label.configure(text='Start port:')
            self.send_port_entry.state(['!disabled'])
            # restore default if empty or non-positive
            try:
                val = int(self.send_port_var.get())
            except Exception:
                val = 0
            if val <= 0:
                self.send_port_var.set('8000')
        else:
            # manual ports list mode
            self.send_port_label.configure(text='Port(s):')
            self.send_port_entry.state(['!disabled'])

    def _start_receiver(self):
        host = self.rc_host.get()
        # ensure numeric values are converted
        scramble_n = 0
        port_list = []
        if self.rc_use_scramble.get():
            try:
                scramble_n = int(self.rc_port.get())
            except Exception:
                messagebox.showerror('Error', 'Scramble ports must be a number')
                return
            if scramble_n <= 0:
                messagebox.showerror('Error', 'Scramble ports must be greater than 0')
                return
        else:
            raw_ports = [p.strip() for p in re.split(r"[;,]", self.rc_port.get() or '') if p.strip()]
            if not raw_ports:
                messagebox.showerror('Error', 'Port must be provided')
                return
            try:
                port_list = [int(p) for p in raw_ports]
            except Exception:
                messagebox.showerror('Error', 'All ports must be numbers')
                return
            if any(p <= 0 for p in port_list):
                messagebox.showerror('Error', 'Ports must be greater than 0')
                return
        dest = self.rc_dest.get()
        max_files = int(self.rc_max.get()) if (self.rc_use_max.get() and self.rc_max.get()) else None
        recon_after = int(self.rc_recon_after.get()) if (self.rc_use_recon_after.get() and self.rc_recon_after.get()) else None
        os.makedirs(dest, exist_ok=True)
        rid = uuid.uuid4().hex[:8]
        shared_state = {
            'lock': threading.Lock(),
            'count': 0,
            'max_files': max_files,
            'reconstruct_after': recon_after,
            'reconstructed': False,
            'reconstruct_out': 'reconstruction.png',
            'ports': [],
            'stop': False
        }

        def _run_single(port_value):
            try:
                self._log(f'Starting receiver {rid} on {host}:{port_value} saving to {dest}')
                self._set_status(f'Receiver {rid} running')
                start_receiver(host, port_value, dest, shared_state.get('max_files'), reconstruct_after=shared_state.get('reconstruct_after'), reconstruct_out=shared_state.get('reconstruct_out'), shared_state=shared_state)
                self._log(f'Receiver {rid} exited ({port_value})')
            except Exception as e:
                self._log(f'Receiver {rid} error on {port_value}: {e}')
            finally:
                self._set_status('Ready')

        def _run_scramble(n):
            threads = []
            self._log(f'Starting {n} receivers on random ports (host {host}) saving to {dest}')
            self._set_status(f'Receivers {rid} running')
            for _ in range(n):
                t = threading.Thread(
                    target=start_receiver,
                    args=(host, 0, dest),
                    kwargs={
                        'shared_state': shared_state,
                        'max_files': shared_state.get('max_files'),
                        'reconstruct_after': shared_state.get('reconstruct_after'),
                        'reconstruct_out': shared_state.get('reconstruct_out'),
                    },
                    daemon=True
                )
                t.start()
                threads.append(t)

            # small wait to collect assigned ports
            start_wait = time.time()
            while time.time() - start_wait < 2.0:
                with shared_state['lock']:
                    if len(shared_state.get('ports', [])) >= n:
                        break
                time.sleep(0.05)
            self._log(f'Scramble receivers started on ports: {shared_state.get("ports", [])}')
            # don't join here; threads tracked in receivers dict
            return threads

        threads = None
        if scramble_n and scramble_n > 0:
            threads = _run_scramble(scramble_n)
            port_display = 'random'
        else:
            threads = []
            for p in port_list:
                t = threading.Thread(target=_run_single, args=(p,), daemon=True)
                t.start()
                threads.append(t)
            port_display = ','.join(str(p) for p in port_list)

        self.receivers[rid] = {'threads': threads, 'state': shared_state, 'host': host, 'port': port_display, 'dest': dest}
        self._list_receivers()

    def _toggle_scramble(self):
        if self.rc_use_scramble.get():
            # reuse the same input as "number of ports" when scrambling
            self.rc_port_label.configure(text='Ports (N):')
            # default to 0 when switching into scramble mode
            if self.rc_port.get() == '8000':
                self.rc_port.set('0')
            self.rc_port_entry.state(['!disabled'])
        else:
            self.rc_port_label.configure(text='Port(s):')
            try:
                v = int(self.rc_port.get())
            except Exception:
                v = 0
            if v <= 0:
                self.rc_port.set('8000')
            self.rc_port_entry.state(['!disabled'])

    def _toggle_max(self):
        if self.rc_use_max.get():
            for w in self._max_widgets:
                w.grid()
        else:
            for w in self._max_widgets:
                w.grid_remove()
            self.rc_max.set('')

    def _toggle_recon(self):
        if self.rc_use_recon_after.get():
            for w in self._recon_widgets:
                w.grid()
        else:
            for w in self._recon_widgets:
                w.grid_remove()
            self.rc_recon_after.set('')

    def _list_receivers(self):
        # Keep current selection stable across refreshes
        selected_ids = set()
        try:
            for idx in self.receivers_listbox.curselection():
                item = self.receivers_listbox.get(idx)
                selected_ids.add(item.split('|', 1)[0])
        except Exception:
            selected_ids = set()

        self.receivers_listbox.delete(0, 'end')
        for rid, info in list(self.receivers.items()):
            count = info['state'].get('count', 0)
            ports = info['state'].get('ports') or info.get('port')
            if isinstance(ports, list):
                port_display = ','.join(str(p) for p in ports)
            else:
                port_display = str(ports)
            text = f"{rid}: {info['host']}:{port_display} -> {info['dest']} (count={count})"
            self.receivers_listbox.insert('end', rid + '|' + text)

        # restore selection if the items still exist
        if selected_ids:
            for i in range(self.receivers_listbox.size()):
                rid = self.receivers_listbox.get(i).split('|', 1)[0]
                if rid in selected_ids:
                    self.receivers_listbox.selection_set(i)

    def _periodic(self):
        # update receiver counts periodically
        self._list_receivers()
        self.after(1000, self._periodic)

    def _stop_selected_receiver(self):
        sel = self.receivers_listbox.curselection()
        if not sel:
            messagebox.showinfo('Stop', 'No receiver selected')
            return
        item = self.receivers_listbox.get(sel[0])
        rid = item.split('|', 1)[0]
        rec = self.receivers.get(rid)
        if not rec:
            messagebox.showerror('Error', 'Receiver not found')
            return
        rec['state']['stop'] = True
        self._log(f'Signalled stop to receiver {rid}')


def main():
    app = VEITAGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
