import os
import threading
import time
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

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
        helpm.add_command(label='About', command=lambda: webbrowser.open('https://github.com/iryandae/VEITA/tree/main'))
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
        nb.add(self.tab_receiver, text='Receiver')
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
        ttk.Button(f, text='Browse', command=self._browse_gen_input).grid(row=0, column=2, padx=4, pady=4)

        ttk.Label(f, text='Number of shares:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.gen_n_var = tk.IntVar(value=2)
        ttk.Entry(f, textvariable=self.gen_n_var, width=10).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        ttk.Button(f, text='Generate', command=self._generate).grid(row=1, column=2, sticky='w', padx=4, pady=8)

        # Separator / spacer
        sep = ttk.Separator(f, orient='horizontal')
        sep.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(8, 8))

        # Files list area
        ttk.Label(f, text='Available shares:').grid(row=3, column=0, sticky='w', padx=4, pady=4)
        self.files_listbox = tk.Listbox(f, selectmode='extended', height=12)
        self.files_listbox.grid(row=4, column=0, columnspan=3, sticky='nsew', padx=4, pady=4)
        # scrollbar
        sb = ttk.Scrollbar(f, orient='vertical', command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=sb.set)
        sb.grid(row=4, column=3, sticky='ns')

        # Refresh / Send controls
        ttk.Button(f, text='Refresh', command=self._refresh_file_list).grid(row=5, column=0, sticky='w', padx=4, pady=4)
        ttk.Label(f, text='Targets:').grid(row=6, column=0, sticky='w', padx=4, pady=4)
        self.send_targets_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.send_targets_var, width=60).grid(row=6, column=1, padx=4, pady=4, sticky='ew')
        ttk.Label(f, text='Start port:').grid(row=7, column=0, sticky='w', padx=4, pady=4)
        self.send_port_var = tk.IntVar(value=8000)
        ttk.Entry(f, textvariable=self.send_port_var, width=10).grid(row=7, column=1, sticky='w', padx=4, pady=4)
        ttk.Button(f, text='Send Selected', command=self._send_selected).grid(row=7, column=2, sticky='w', padx=4, pady=8)

        f.columnconfigure(1, weight=1)
        self._refresh_file_list()

    def _build_receiver(self):
        f = self.tab_receiver
        ttk.Label(f, text='Host:').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.rc_host = tk.StringVar(value='0.0.0.0')
        ttk.Entry(f, textvariable=self.rc_host, width=20).grid(row=0, column=1, sticky='w', padx=4, pady=4)

        ttk.Label(f, text='Port:').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.rc_port = tk.IntVar(value=8000)
        ttk.Entry(f, textvariable=self.rc_port, width=10).grid(row=1, column=1, sticky='w', padx=4, pady=4)

        ttk.Label(f, text='Dest dir:').grid(row=2, column=0, sticky='w', padx=4, pady=4)
        self.rc_dest = tk.StringVar(value=RECON)
        ttk.Entry(f, textvariable=self.rc_dest, width=60).grid(row=2, column=1, padx=4, pady=4, sticky='ew')
        ttk.Button(f, text='Browse', command=self._browse_rc_dest).grid(row=2, column=2, padx=4, pady=4)

        ttk.Label(f, text='Max files:').grid(row=3, column=0, sticky='w', padx=4, pady=4)
        self.rc_max = tk.StringVar(value='')
        ttk.Entry(f, textvariable=self.rc_max, width=10).grid(row=3, column=1, sticky='w', padx=4, pady=4)

        ttk.Label(f, text='Reconstruct after:').grid(row=4, column=0, sticky='w', padx=4, pady=4)
        self.rc_recon_after = tk.StringVar(value='')
        ttk.Entry(f, textvariable=self.rc_recon_after, width=10).grid(row=4, column=1, sticky='w', padx=4, pady=4)

        ttk.Button(f, text='Start Receiver', command=self._start_receiver).grid(row=5, column=1, sticky='w', padx=4, pady=8)
        ttk.Button(f, text='List Receivers', command=self._list_receivers).grid(row=5, column=2, sticky='w', padx=4, pady=8)

        self.receivers_listbox = tk.Listbox(f, height=6)
        self.receivers_listbox.grid(row=6, column=0, columnspan=2, sticky='nsew', padx=4, pady=4)
        rsb = ttk.Scrollbar(f, orient='vertical', command=self.receivers_listbox.yview)
        self.receivers_listbox.configure(yscrollcommand=rsb.set)
        rsb.grid(row=6, column=2, sticky='ns')
        ttk.Button(f, text='Stop', command=self._stop_selected_receiver).grid(row=7, column=1, sticky='w', padx=4, pady=6)
        f.columnconfigure(1, weight=1)

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
        start_port = self.send_port_var.get()
        paths = [os.path.join(OUTPUT_DIR, s) for s in sel]
        def _work():
            self._set_status('Sending...')
            self._log(f'Sending {len(paths)} files to {targets} (start port {start_port})')
            results = send_shares_over_network(paths, targets, default_port=int(start_port))
            self._log('Send results: ' + str(results))
            self._set_status('Ready')
        threading.Thread(target=_work, daemon=True).start()

    def _start_receiver(self):
        host = self.rc_host.get()
        # ensure numeric values are converted
        try:
            port = int(self.rc_port.get())
        except Exception:
            messagebox.showerror('Error', 'Port must be a number')
            return
        dest = self.rc_dest.get()
        max_files = int(self.rc_max.get()) if self.rc_max.get() else None
        recon_after = int(self.rc_recon_after.get()) if self.rc_recon_after.get() else None
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

        def _run():
            try:
                self._log(f'Starting receiver {rid} on {host}:{port} saving to {dest}')
                self._set_status(f'Receiver {rid} running')
                start_receiver(host, port, dest, shared_state.get('max_files'), reconstruct_after=shared_state.get('reconstruct_after'), reconstruct_out=shared_state.get('reconstruct_out'), shared_state=shared_state)
                self._log(f'Receiver {rid} exited')
            except Exception as e:
                self._log(f'Receiver {rid} error: {e}')
            finally:
                self._set_status('Ready')

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self.receivers[rid] = {'thread': t, 'state': shared_state, 'host': host, 'port': port, 'dest': dest}
        self._list_receivers()

    def _list_receivers(self):
        self.receivers_listbox.delete(0, 'end')
        for rid, info in list(self.receivers.items()):
            count = info['state'].get('count', 0)
            text = f"{rid}: {info['host']}:{info['port']} -> {info['dest']} (count={count})"
            self.receivers_listbox.insert('end', rid + '|' + text)

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
