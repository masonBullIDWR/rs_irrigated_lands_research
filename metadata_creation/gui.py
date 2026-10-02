#%%
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import *
from tkinter import scrolledtext
from pathlib import Path
from sys import executable
from ruamel.yaml import YAML
 
parent_dir = Path.cwd().absolute()
config_file = [i for i in parent_dir.parent.glob('**/*.yml')][0]
yaml = YAML()
yaml.preserve_quotes = (True)
with open(config_file) as f:
    config = yaml.load(f)
 
config_fields = ['year', 'scale', 'area', 'training_data', 'mode', 'aoi']
 
root = tk.Tk()
root.geometry('500x250')
root.title('Update Metadata')
frame = Frame(root)
frame.grid(sticky='nsew')
 
items = {}
for row, key in enumerate(config_fields):
    Label(frame, text=key).grid(row=row, column=0, sticky='w', pady=4, padx=(0, 10))
    entry = Entry(frame, width=45)
    entry.insert(0, str(config[key]))
    entry.grid(row=row, column=1, pady=4)
    items[key] = entry
 
var = tk.IntVar()
Checkbutton(frame, text='Open ArcPro on completion?', name='checkbox', variable=var).grid(
    row=row + 1, column=0, sticky='w', pady=10, padx=(0, 10))
 
 
def convert_like(original, text):
    """Convert the entry text back to the same type as the original value,
    so ints stay ints, floats stay floats, and quoted strings stay quoted."""
    text = text.strip()
    if isinstance(original, bool):
        return text.lower() in ('true', '1', 'yes')
    if isinstance(original, int):
        return int(text)
    if isinstance(original, float):
        return float(text)
    if isinstance(original, str) and type(original) is not str:
        return type(original)(text)
    return text
 
 
def run_gui():
    # 1. Save the entry values to the config file
    for key, entry in items.items():
        config[key] = convert_like(config[key], entry.get())
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
 
    varg = 'True' if var.get() else 'False'
 
    # 2. Build the live log window
    run_button.config(state='disabled')
    log_win = Toplevel(root)
    log_win.title('Metadata Updates')
    log_win.geometry('700x400')
    log = scrolledtext.ScrolledText(log_win, state='disabled', wrap='word')
    log.pack(fill='both', expand=True, padx=5, pady=5)
    close_btn = Button(log_win, text='Close', state='disabled', command=log_win.destroy)
    close_btn.pack(pady=(0, 8))
    log_win.protocol('WM_DELETE_WINDOW', lambda: None)  # can't close while running
 
    def append(text):
        log.config(state='normal')
        log.insert(END, text)
        log.see(END)
        log.config(state='disabled')
 
    # 3. Run the script in a background thread, pushing each line to a queue
    q = queue.Queue()
 
    def worker():
        proc = subprocess.Popen(
            [executable, '-u', str(Path.cwd() / 'metadata_updating.py'), varg],  # -u = unbuffered
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # errors show up in the log too
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        for line in proc.stdout:
            q.put(line)
        proc.wait()
        q.put(('done', proc.returncode))
 
    threading.Thread(target=worker, daemon=True).start()
 
    # 4. Poll the queue from the Tk main thread and update the log
    def poll():
        try:
            while True:
                item = q.get_nowait()
                if isinstance(item, tuple):
                    append(f'\n--- Finished (exit code {item[1]}) ---\n')
                    close_btn.config(state='normal')
                    log_win.protocol('WM_DELETE_WINDOW', log_win.destroy)
                    run_button.config(state='normal')
                    return
                append(item)
        except queue.Empty:
            pass
        root.after(100, poll)
 
    poll()
 
 
run_button = Button(frame, text='Run', command=run_gui)
run_button.grid(row=len(config_fields), column=0, columnspan=2, pady=(12, 0))
root.mainloop()