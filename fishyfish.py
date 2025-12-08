import tkinter as tk
from tkinter import ttk, messagebox
import threading
import keyboard
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
import sys
import ctypes
import dxcam
import win32api
import win32con
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageDraw
import requests
from io import BytesIO
import time
import json
import os
from datetime import datetime
import numpy as np

# --- 1. FORCE ADMIN ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- CONFIGURATION ---
THEME_BG = "#0b0b0b"
THEME_ACCENT = "#ff8d00" # Orange
THEME_CARD = "#1a1a1a"   # Dark Grey
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_AFK = ("Segoe UI", 48, "bold")

# IMAGE URLS
VIVI_URL = "https://static0.srcdn.com/wordpress/wp-content/uploads/2023/10/vivi.jpg?q=49&fit=crop&w=825&dpr=2"
DUCK_URL = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.ytimg.com%2Fvi%2FX8YUuU7OpOA%2Fmaxresdefault.jpg&f=1&nofb=1&ipt=6d669298669fff2e4f438b54453c1f59c1655ca19fa2407ea1c42e471a4d7ab6"
TITLE_LOGO_URL = "https://image2url.com/images/1765149562249-ff56b103-b5ea-4402-a896-0ed38202b804.png"
PROFILE_ICON_URL = "https://i.pinimg.com/736x/f1/bb/3d/f1bb3d7b7b2fe3dbf46915f380043be9.jpg"

STATS_FILE = "karoo_stats.json"
CONFIG_FILE = "karoo_config.json"

class KarooFish:
    def __init__(self, root):
        self.root = root
        self.root.title("Karoo Fish")
        self.root.geometry("460x950")
        self.root.configure(bg=THEME_BG)
        self.root.attributes('-topmost', True)

        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass

        # --- STATE ---
        self.fishing_active = False
        self.reroll_active = False
        self.overlay_active = False
        self.afk_mode_active = False
        
        self.overlay_window = None
        self.is_clicking = False
        self.is_performing_action = False 
        self.last_cast_time = 0.0
        self.last_user_activity = time.time()
        
        # --- CONFIG VARS ---
        self.resize_threshold = 10
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
        self.border_size = 5      
        
        self.purchase_counter = 0     
        self.session_loops = 0        
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0
        self.scan_timeout = 15.0
        self.wait_after_loss = 1.0
        
        self.purchase_delay_after_key = 2.0   
        self.purchase_click_delay = 0.8       
        self.purchase_after_type_delay = 0.8
        self.clean_step_delay = 1.0           
        
        self.dpi_scale = self.get_dpi_scale()
        self.overlay_area = {
            'x': 100, 'y': 100, 
            'width': int(180 * self.dpi_scale), 
            'height': int(500 * self.dpi_scale)
        }

        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3', 'toggle_afk': 'f4'}
        
        # Initialize Camera
        try:
            self.camera = dxcam.create(output_color="BGR")
        except Exception as e:
            print(f"Camera Init Error: {e}")
            self.camera = None

        self.point_coords = {1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None}
        self.point_labels = {} 

        self.stats = self.load_stats()

        self.bg_main = self.load_processed_image(VIVI_URL, 0.3)
        self.bg_afk = self.load_processed_image(DUCK_URL, 0.4)
        self.img_title = self.load_title_image(TITLE_LOGO_URL)
        self.img_profile = self.load_circular_icon(PROFILE_ICON_URL)

        self.setup_ui()
        self.register_hotkeys()
        
        # LOAD CONFIG (Points & Settings)
        self.load_config()

        # Auto AFK Monitor
        self.root.bind_all("<Any-KeyPress>", self.reset_afk_timer)
        self.root.bind_all("<Any-ButtonPress>", self.reset_afk_timer)
        self.root.bind_all("<Motion>", self.reset_afk_timer)
        self.check_auto_afk()

    # --- DATA & PERSISTENCE ---
    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                
            # Load Points
            saved_points = data.get("points", {})
            for k, v in saved_points.items():
                idx = int(k)
                self.point_coords[idx] = tuple(v)
                # Update Labels if they exist
                if idx in self.point_labels:
                    self.point_labels[idx].config(text=f"{v[0]},{v[1]}", fg="#00ff00")

            # Load Variables
            if "auto_purchase" in data: self.auto_purchase_var.set(data["auto_purchase"])
            if "amount" in data: self.amount_var.set(data["amount"])
            if "loops" in data: self.loops_var.set(data["loops"])
            if "item_check" in data: self.item_check_var.set(data["item_check"])
            if "auto_bait" in data: self.auto_bait_var.set(data["auto_bait"])
            if "auto_afk" in data: self.auto_afk_var.set(data["auto_afk"])
            if "afk_seconds" in data: self.auto_afk_seconds_var.set(data["afk_seconds"])
            if "kp" in data: self.kp_var.set(data["kp"])
            if "kd" in data: self.kd_var.set(data["kd"])
            if "timeout" in data: self.timeout_var.set(data["timeout"])

            print("Configuration Loaded.")
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        try:
            data = {
                "points": self.point_coords,
                "auto_purchase": self.auto_purchase_var.get(),
                "amount": self.amount_var.get(),
                "loops": self.loops_var.get(),
                "item_check": self.item_check_var.get(),
                "auto_bait": self.auto_bait_var.get(),
                "auto_afk": self.auto_afk_var.get(),
                "afk_seconds": self.auto_afk_seconds_var.get(),
                "kp": self.kp_var.get(),
                "kd": self.kd_var.get(),
                "timeout": self.timeout_var.get()
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.status_msg.config(text="Configuration Saved!", fg="#00ff00")
        except Exception as e:
            self.status_msg.config(text="Save Failed", fg="red")
            print(f"Save error: {e}")

    def reset_defaults(self):
        # Clear Points
        self.point_coords = {1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None, 8: None}
        for idx, lbl in self.point_labels.items():
            lbl.config(text="Not Set", fg="red")
        
        # Reset Vars
        self.auto_purchase_var.set(False)
        self.amount_var.set(10)
        self.loops_var.set(10)
        self.item_check_var.set(True)
        self.auto_bait_var.set(False)
        self.auto_afk_var.set(True)
        self.auto_afk_seconds_var.set(60)
        self.kp_var.set(0.1)
        self.kd_var.set(0.5)
        self.timeout_var.set(15.0)
        
        self.status_msg.config(text="Restored Defaults", fg=THEME_ACCENT)
        self.save_config()

    # --- HELPERS ---
    def get_dpi_scale(self):
        try: return self.root.winfo_fpixels('1i') / 96.0
        except: return 1.0

    def load_processed_image(self, url, darkness=0.5):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            img = img.resize((500, 950), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(ImageEnhance.Brightness(img).enhance(darkness))
        except: return None

    def load_title_image(self, url):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            w, h = img.size
            aspect = h / w
            new_w = 300
            new_h = int(new_w * aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except: return None

    def load_circular_icon(self, url):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            size = (100, 100)
            img = ImageOps.fit(img, size, centering=(0.5, 0.5))
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            img.putalpha(mask)
            draw_img = ImageDraw.Draw(img)
            draw_img.ellipse((0, 0, 99, 99), outline=THEME_ACCENT, width=4)
            return ImageTk.PhotoImage(img)
        except: return None

    def load_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
            except: pass
        return {"total_caught": 0, "history": []}

    def save_stats(self):
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=4)

    def record_session(self):
        if self.session_loops > 0:
            self.stats["total_caught"] += self.session_loops
            entry = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "count": self.session_loops}
            self.stats["history"].insert(0, entry)
            self.stats["history"] = self.stats["history"][:50]
            self.save_stats()
            self.session_loops = 0
            self.refresh_profile_ui()

    def delete_selected_session(self):
        selection = self.hist_list.curselection()
        if not selection: return
        index = selection[0]
        if 0 <= index < len(self.stats['history']):
            del self.stats['history'][index]
            self.save_stats()
            self.refresh_profile_ui()

    # --- UI SETUP ---
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook", background=THEME_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#202020", foreground="white", padding=[10, 5], font=FONT_BOLD, borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", THEME_ACCENT)], foreground=[("selected", "black")])

        self.container = tk.Frame(self.root, bg=THEME_BG)
        self.container.pack(fill="both", expand=True)

        self.page_main = tk.Frame(self.container, bg=THEME_BG)
        self.page_main.place(relwidth=1, relheight=1)
        if self.bg_main: tk.Label(self.page_main, image=self.bg_main, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        
        self.create_main_widgets()

        self.page_afk = tk.Frame(self.container, bg=THEME_BG)
        if self.bg_afk: tk.Label(self.page_afk, image=self.bg_afk, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        self.create_afk_widgets()

        self.page_profile = tk.Frame(self.container, bg=THEME_BG)
        self.create_profile_widgets()

    def create_main_widgets(self):
        header_frame = tk.Frame(self.page_main, bg=THEME_BG)
        header_frame.pack(fill="x", pady=(10, 0))
        
        if self.img_title:
            tk.Label(header_frame, image=self.img_title, bg=THEME_BG).pack(pady=5)
        else:
            tk.Label(header_frame, text="Karoo Fish", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(pady=5)

        tk.Button(header_frame, text="View Profile & Stats", bg=THEME_CARD, fg="white", font=FONT_BOLD, relief="flat", 
                  command=self.show_profile).pack(pady=5)

        self.notebook = ttk.Notebook(self.page_main)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_fishing = tk.Frame(self.notebook, bg=THEME_BG)
        self.notebook.add(self.tab_fishing, text="Fishing Bot")
        self.create_fishing_tab(self.tab_fishing)

        self.tab_reroll = tk.Frame(self.notebook, bg=THEME_BG)
        self.notebook.add(self.tab_reroll, text="Race Reroll")
        self.create_reroll_tab(self.tab_reroll)

    def create_fishing_tab(self, parent):
        canvas = tk.Canvas(parent, bg=THEME_BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=sb.set)
        
        frame = tk.Frame(canvas, bg=THEME_BG)
        canvas.create_window((0, 0), window=frame, anchor="nw", width=420)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        st = tk.Frame(frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        st.pack(fill="x", padx=10, pady=10)
        self.fishing_status_lbl = tk.Label(st, text="Fishing: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.fishing_status_lbl.pack(pady=5)
        self.overlay_status = tk.Label(st, text="Overlay: OFF", font=FONT_MAIN, bg=THEME_BG, fg="gray")
        self.overlay_status.pack(pady=5)

        self.create_section(frame, "Auto Purchase")
        self.auto_purchase_var = tk.BooleanVar(value=False)
        self.create_toggle(frame, "Active", self.auto_purchase_var)
        self.amount_var = tk.IntVar(value=10)
        self.create_input(frame, "Amount:", self.amount_var)
        self.loops_var = tk.IntVar(value=10)
        self.create_input(frame, "Loops/Buy:", self.loops_var)

        tk.Label(frame, text="Coordinates:", font=FONT_BOLD, bg=THEME_BG, fg="white").pack(anchor="w", padx=20, pady=(10, 5))
        plabs = {1: "Pt 1 (Yes)", 2: "Pt 2 (Input)", 3: "Pt 3 (No)", 4: "Pt 4 (Ocean)"}
        for i in range(1, 5): self.create_point_row(frame, i, plabs[i])

        self.create_section(frame, "Auto Store Fruit")
        self.item_check_var = tk.BooleanVar(value=True)
        self.create_toggle(frame, "Enable Auto Store", self.item_check_var)
        self.create_point_row(frame, 5, "Pt 5 (Store Button)")
        self.create_point_row(frame, 7, "Pt 7 (Slot 3 Check)")

        self.create_section(frame, "Auto Bait")
        self.auto_bait_var = tk.BooleanVar(value=False)
        self.create_toggle(frame, "Enable Auto Bait", self.auto_bait_var)
        self.create_point_row(frame, 6, "Pt 6 (Bait Location)")

        self.create_section(frame, "Settings")
        self.auto_afk_var = tk.BooleanVar(value=True)
        self.create_toggle(frame, "Auto AFK Mode", self.auto_afk_var)
        self.auto_afk_seconds_var = tk.IntVar(value=60)
        self.create_input(frame, "Idle (s):", self.auto_afk_seconds_var)
        
        self.kp_var = tk.DoubleVar(value=self.kp)
        self.create_input(frame, "Kp:", self.kp_var, True)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        self.kd_var = tk.DoubleVar(value=self.kd)
        self.create_input(frame, "Kd:", self.kd_var, True)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        self.create_input(frame, "Timeout:", self.timeout_var, True)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))

        self.create_section(frame, "Hotkeys")
        for k, label in [('toggle_loop', 'Loop'), ('toggle_overlay', 'Overlay'), ('toggle_afk', 'AFK'), ('exit', 'Exit')]:
            self.create_hotkey_row(frame, label, k)
            
        # --- SAVE / RESTORE SECTION ---
        self.create_section(frame, "Configuration")
        btn_row = tk.Frame(frame, bg=THEME_BG)
        btn_row.pack(fill="x", padx=20, pady=5)
        
        tk.Button(btn_row, text="Save Settings", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 9, "bold"), 
                  command=self.save_config, width=15, relief="flat").pack(side="left", padx=(0, 10))
                  
        tk.Button(btn_row, text="Reset Defaults", bg="#202020", fg="white", font=("Segoe UI", 9), 
                  command=self.reset_defaults, width=15, relief="flat").pack(side="left")

        self.status_msg = tk.Label(frame, text="", bg=THEME_BG, fg=THEME_ACCENT)
        self.status_msg.pack(pady=20)

    def create_reroll_tab(self, parent):
        frame = tk.Frame(parent, bg=THEME_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        st = tk.Frame(frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        st.pack(fill="x", pady=10)
        self.reroll_status_lbl = tk.Label(st, text="Reroll: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.reroll_status_lbl.pack(pady=10)

        tk.Label(frame, text="Auto Race Reroll", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(anchor="w", pady=(10, 5))
        tk.Label(frame, text="This mode checks for the GOLD button color (#b37a00).\nIt runs independently from fishing.", 
                 bg=THEME_BG, fg="gray", justify="left").pack(anchor="w", pady=5)

        self.create_section(frame, "Configuration")
        self.create_point_row(frame, 8, "Pt 8 (Reroll Button)")
        
        tk.Label(frame, text="\nHow to use:", font=FONT_BOLD, bg=THEME_BG, fg="white").pack(anchor="w")
        tk.Label(frame, text="1. Set Pt 8 on the center of the 'Reroll' button.\n2. Switch to this tab.\n3. Press F1 to Start/Stop.", 
                 bg=THEME_BG, fg="white", justify="left").pack(anchor="w", pady=5)

    def create_afk_widgets(self):
        center_frame = tk.Frame(self.page_afk, bg=THEME_BG) 
        tk.Label(self.page_afk, text="AFK MODE", font=("Segoe UI", 36, "bold"), bg=THEME_BG, fg=THEME_ACCENT).place(relx=0.5, rely=0.15, anchor="center")
        tk.Label(self.page_afk, text="Current Session:", font=("Segoe UI", 14), bg=THEME_BG, fg="white").place(relx=0.5, rely=0.35, anchor="center")
        self.afk_session_label = tk.Label(self.page_afk, text="0", font=("Segoe UI", 60, "bold"), bg=THEME_BG, fg=THEME_ACCENT)
        self.afk_session_label.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(self.page_afk, text="All Time Total:", font=("Segoe UI", 12), bg=THEME_BG, fg="gray").place(relx=0.5, rely=0.6, anchor="center")
        self.afk_total_label = tk.Label(self.page_afk, text=f"{self.stats['total_caught']}", font=("Segoe UI", 24, "bold"), bg=THEME_BG, fg="white")
        self.afk_total_label.place(relx=0.5, rely=0.65, anchor="center")
        self.afk_hint_label = tk.Label(self.page_afk, text="Press F4 to return", font=("Segoe UI", 10, "italic"), bg=THEME_BG, fg="gray")
        self.afk_hint_label.place(relx=0.5, rely=0.85, anchor="center")

    def create_profile_widgets(self):
        tk.Label(self.page_profile, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        tk.Button(self.page_profile, text="← Back", bg=THEME_BG, fg="white", relief="flat", font=FONT_BOLD, command=self.show_main).pack(anchor="nw", padx=20, pady=20)
        
        header = tk.Frame(self.page_profile, bg=THEME_CARD, height=150)
        header.pack(fill="x", padx=20, pady=10)
        header.pack_propagate(False)
        
        if self.img_profile:
            tk.Label(header, image=self.img_profile, bg=THEME_CARD).pack(side="left", padx=20)
        else:
            tk.Label(header, text="IMG", bg=THEME_CARD, fg="white", width=10, height=5).pack(side="left", padx=20)
            
        info_frame = tk.Frame(header, bg=THEME_CARD)
        info_frame.pack(side="left", fill="y", pady=20)
        tk.Label(info_frame, text="Fisher", font=("Segoe UI", 24, "bold"), bg=THEME_CARD, fg="white").pack(anchor="w")
        tk.Label(info_frame, text="The One And Only Karoo", font=("Segoe UI", 10, "italic"), bg=THEME_CARD, fg=THEME_ACCENT).pack(anchor="w")

        stats_frame = tk.Frame(self.page_profile, bg=THEME_BG)
        stats_frame.pack(fill="x", padx=20, pady=10)
        s_card = tk.Frame(stats_frame, bg=THEME_CARD, pady=15)
        s_card.pack(fill="x")
        tk.Label(s_card, text="TOTAL CAUGHT", font=("Segoe UI", 10, "bold"), bg=THEME_CARD, fg="gray").pack()
        self.profile_total_label = tk.Label(s_card, text=str(self.stats['total_caught']), font=("Segoe UI", 36, "bold"), bg=THEME_CARD, fg=THEME_ACCENT)
        self.profile_total_label.pack()
        
        tk.Label(self.page_profile, text="Recent Sessions", font=FONT_BOLD, bg=THEME_BG, fg="white").pack(anchor="w", padx=20, pady=(20, 5))
        hist_frame = tk.Frame(self.page_profile, bg=THEME_CARD)
        hist_frame.pack(fill="both", expand=True, padx=20, pady=0)
        
        self.hist_list = tk.Listbox(hist_frame, bg=THEME_CARD, fg="white", font=("Consolas", 10), borderwidth=0, highlightthickness=0, selectbackground=THEME_ACCENT)
        sb = ttk.Scrollbar(hist_frame, orient="vertical", command=self.hist_list.yview)
        self.hist_list.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        sb.pack(side="right", fill="y")
        self.hist_list.config(yscrollcommand=sb.set)

        btn_frame = tk.Frame(self.page_profile, bg=THEME_BG)
        btn_frame.pack(fill="x", padx=20, pady=(5, 20))
        tk.Button(btn_frame, text="Delete Selected", bg=THEME_CARD, fg="white", font=("Segoe UI", 9), relief="flat", command=self.delete_selected_session).pack(side="right")
        self.refresh_profile_ui()

    def refresh_profile_ui(self):
        self.profile_total_label.config(text=str(self.stats['total_caught']))
        self.afk_total_label.config(text=str(self.stats['total_caught'] + self.session_loops))
        self.hist_list.delete(0, tk.END)
        for entry in self.stats['history']:
            d = entry['date']
            c = str(entry['count'])
            spacer = "." * (40 - len(d) - len(c))
            self.hist_list.insert(tk.END, f"{d} {spacer} +{c}")

    def show_profile(self):
        self.refresh_profile_ui()
        self.page_main.place_forget()
        self.page_afk.place_forget()
        self.page_profile.place(relwidth=1, relheight=1)

    def show_main(self):
        self.page_profile.place_forget()
        self.page_afk.place_forget()
        self.page_main.place(relwidth=1, relheight=1)

    # --- UI HELPERS ---
    def create_section(self, p, txt):
        f = tk.Frame(p, bg=THEME_BG)
        f.pack(fill="x", pady=(20, 5), padx=20)
        tk.Label(f, text=txt, font=("Segoe UI", 14, "bold"), bg=THEME_BG, fg=THEME_ACCENT).pack(side="left")
        tk.Frame(f, bg=THEME_ACCENT, height=2).pack(side="left", fill="x", expand=True, padx=(10, 0))

    def create_input(self, p, lbl, var, is_float=False):
        f = tk.Frame(p, bg=THEME_BG)
        f.pack(fill="x", pady=2, padx=20)
        tk.Label(f, text=lbl, bg=THEME_BG, fg="white").pack(side="left")
        tk.Spinbox(f, textvariable=var, bg="#202020", fg=THEME_ACCENT, relief="flat", width=10, from_=0, to=999999, increment=0.1 if is_float else 1).pack(side="right")

    def create_toggle(self, p, txt, var):
        tk.Checkbutton(p, text=txt, variable=var, bg=THEME_BG, fg="white", selectcolor="#202020", activebackground=THEME_BG, activeforeground=THEME_ACCENT, font=FONT_BOLD).pack(anchor="w", padx=20, pady=2)

    def create_point_row(self, p, idx, txt):
        f = tk.Frame(p, bg=THEME_BG)
        f.pack(fill="x", pady=2, padx=20)
        tk.Label(f, text=txt, bg=THEME_BG, fg="gray").pack(side="left")
        r = tk.Frame(f, bg=THEME_BG)
        r.pack(side="right")
        l = tk.Label(r, text="Not Set", font=("Segoe UI", 8), bg=THEME_BG, fg="red")
        l.pack(side="left", padx=5)
        self.point_labels[idx] = l
        tk.Button(r, text="Set", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold"), command=lambda: self.capture_pt(idx), width=6, relief="flat").pack(side="left")

    def create_hotkey_row(self, p, lbl, key):
        f = tk.Frame(p, bg=THEME_BG)
        f.pack(fill="x", pady=2, padx=20)
        tk.Label(f, text=lbl, bg=THEME_BG, fg="gray").pack(side="left")
        b = tk.Button(f, text="Rebind", bg="#202020", fg="white", relief="flat", command=lambda: self.rebind(key), font=("Segoe UI", 8))
        b.pack(side="right", padx=5)
        l = tk.Label(f, text=self.hotkeys[key].upper(), bg=THEME_BG, fg=THEME_ACCENT, font=FONT_BOLD)
        l.pack(side="right", padx=10)
        setattr(self, f"lbl_{key}", l); setattr(self, f"btn_{key}", b)

    # --- INPUT LOGIC ---
    def reset_afk_timer(self, event=None):
        self.last_user_activity = time.time()

    def check_auto_afk(self):
        # Check AFK only if Fishing Bot is active
        if self.auto_afk_var.get() and self.fishing_active and not self.afk_mode_active:
            idle_time = time.time() - self.last_user_activity
            if idle_time > self.auto_afk_seconds_var.get():
                self.toggle_afk()
        self.root.after(1000, self.check_auto_afk)

    def register_hotkeys(self):
        try:
            keyboard.unhook_all()
            for k, f in [('toggle_loop', self.toggle_loop), ('toggle_overlay', self.toggle_overlay), ('toggle_afk', self.toggle_afk), ('exit', self.exit_app)]:
                keyboard.add_hotkey(self.hotkeys[k], lambda f=f: self.root.after(0, f))
        except: pass

    def toggle_afk(self):
        self.afk_mode_active = not self.afk_mode_active
        if self.afk_mode_active:
            self.page_main.place_forget()
            self.page_profile.place_forget()
            self.page_afk.place(relwidth=1, relheight=1)
            self.afk_hint_label.config(text=f"Press {self.hotkeys['toggle_afk'].upper()} to return")
        else:
            self.page_afk.place_forget()
            self.page_profile.place_forget()
            self.page_main.place(relwidth=1, relheight=1)
            self.last_user_activity = time.time()

    def toggle_loop(self):
        # Determine current tab
        current_tab = self.notebook.index(self.notebook.select())
        
        if current_tab == 0: # Fishing Tab
            self.toggle_fishing()
        elif current_tab == 1: # Reroll Tab
            self.toggle_reroll()

    def toggle_fishing(self):
        if self.reroll_active: return # Cannot run both
        self.fishing_active = not self.fishing_active
        if self.fishing_active:
            req = []
            if self.auto_purchase_var.get(): req.extend([1,2,3,4]) 
            if self.item_check_var.get(): req.extend([5,7])
            if self.auto_bait_var.get(): req.append(6)
            
            if any(not self.point_coords.get(p) for p in req):
                self.fishing_active = False
                self.status_msg.config(text="Missing Fishing Points!", fg="red")
                return
            
            self.purchase_counter = 0
            self.session_loops = 0 
            self.afk_session_label.config(text="0")
            self.last_user_activity = time.time() 
            self.fishing_status_lbl.config(text="Fishing: ON", fg="#00ff00")
            if self.overlay_window: self.overlay_window.withdraw()
            threading.Thread(target=self.run_fishing_loop, daemon=True).start()
        else:
            self.fishing_status_lbl.config(text="Fishing: OFF", fg="red")
            self.is_clicking = False
            self.is_performing_action = False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.record_session()
            if self.overlay_window: self.overlay_window.deiconify()

    def toggle_reroll(self):
        if self.fishing_active: return
        self.reroll_active = not self.reroll_active
        if self.reroll_active:
            if not self.point_coords.get(8):
                self.reroll_active = False
                self.status_msg.config(text="Missing Pt 8 for Reroll!", fg="red")
                return
            self.reroll_status_lbl.config(text="Reroll: ON", fg="#00ff00")
            threading.Thread(target=self.run_reroll_loop, daemon=True).start()
        else:
            self.reroll_status_lbl.config(text="Reroll: OFF", fg="red")

    def capture_pt(self, idx):
        self.status_msg.config(text=f"Click for Pt {idx}...", fg=THEME_ACCENT)
        def on_click(x, y, button, pressed):
            if pressed:
                self.point_coords[idx] = (x, y)
                self.root.after(0, lambda: self.point_labels[idx].config(text=f"{x},{y}", fg="#00ff00"))
                self.root.after(0, lambda: self.status_msg.config(text=f"Pt {idx} Saved", fg="#00ff00"))
                return False
        pynput_mouse.Listener(on_click=on_click).start()

    def rebind(self, key):
        self.status_msg.config(text="Press key...", fg=THEME_ACCENT)
        getattr(self, f"btn_{key}").config(state="disabled")
        def on_press(k):
            kn = k.name if hasattr(k, 'name') else str(k).replace('Key.', '')
            self.hotkeys[key] = kn
            self.root.after(0, lambda: getattr(self, f"lbl_{key}").config(text=kn.upper()))
            self.root.after(0, lambda: getattr(self, f"btn_{key}").config(state="normal"))
            self.root.after(0, self.register_hotkeys)
            return False
        pynput_keyboard.Listener(on_press=on_press).start()

    # --- MOUSE ACTIONS ---
    def move_to(self, pt):
        if not pt: return
        try:
            x, y = int(pt[0]), int(pt[1])
            win32api.SetCursorPos((x, y))
            time.sleep(0.02)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
            time.sleep(0.05)
        except Exception: pass

    def click(self, pt, debug_name="Target", hold_time=0.1):
        if not pt: return
        try:
            x, y = int(pt[0]), int(pt[1])
            print(f"Clicking: {debug_name} at {x},{y}")
            win32api.SetCursorPos((x, y))
            time.sleep(0.02)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(hold_time) 
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05)
        except Exception as e: print(f"Click Error on {debug_name}: {e}")

    # --- ACTIONS (FISHING) ---
    def perform_auto_purchase_sequence(self):
        try:
            self.is_performing_action = True 
            if not all([self.point_coords[1], self.point_coords[2], self.point_coords[4]]): return
            
            # 1. Standard Buy Sequence
            keyboard.press_and_release('e')
            time.sleep(self.purchase_delay_after_key)
            self.click(self.point_coords[1], "Pt 1 (Yes)")
            time.sleep(self.purchase_click_delay)
            self.click(self.point_coords[2], "Pt 2 (Input)")
            time.sleep(self.purchase_click_delay)
            keyboard.write(str(self.amount_var.get()))
            time.sleep(self.purchase_after_type_delay)
            self.click(self.point_coords[1], "Pt 1 (Confirm)")
            time.sleep(self.purchase_click_delay)
            self.click(self.point_coords[2], "Pt 2 (Safety)")
            time.sleep(self.purchase_click_delay)
            self.move_to(self.point_coords[4])
            time.sleep(self.purchase_click_delay)

            # 2. Check Pt 3 for "No" (Red)
            if self.point_coords[3]:
                frame = None
                if self.camera and self.camera.is_capturing:
                     frame = self.camera.get_latest_frame()
                else:
                    if not self.camera: self.camera = dxcam.create(output_color="BGR")
                    frame = self.camera.grab()

                if frame is not None:
                    p3 = self.point_coords[3]
                    cx, cy = int(p3[0]), int(p3[1])
                    if cy < frame.shape[0] and cx < frame.shape[1]:
                        b, g, r = frame[cy, cx]
                        if r > 200 and g < 50 and b < 50:
                            print("Red detected at Pt 3 (Menu stuck). Forcing close.")
                            self.click(p3, "Pt 3 (Force Close)")
                            time.sleep(0.5)
                            self.click(self.point_coords[2], "Pt 2 (Post-Close Safety)")
                            time.sleep(0.5)
                            self.move_to(self.point_coords[4])

        except Exception as e:
            print(f"Auto Purchase Error: {e}")
        finally: 
            self.is_performing_action = False

    def perform_store_fruit(self):
        p5, p7 = self.point_coords.get(5), self.point_coords.get(7)
        if not p5 or not p7: return

        def is_white_icon_visible():
            img = self.camera.get_latest_frame()
            if img is None: return False
            cx, cy = int(p7[0]), int(p7[1])
            if cy >= img.shape[0] or cx >= img.shape[1]: return False
            b, g, r = img[cy, cx]
            return (r > 200 and g > 200 and b > 200)

        try:
            self.is_performing_action = True 
            keyboard.press_and_release('2')
            time.sleep(0.5)
            keyboard.press_and_release('3')
            time.sleep(self.clean_step_delay)
            if is_white_icon_visible():
                for i in range(3):
                    self.click(p5, f"Store Click {i+1}")
                    time.sleep(0.8)
                    if not is_white_icon_visible(): break
                if is_white_icon_visible():
                    keyboard.press_and_release('backspace')
                    time.sleep(1.0)
            keyboard.press_and_release('2')
            time.sleep(0.5)
            self.move_to(self.point_coords[4])
            time.sleep(0.2)
        except Exception: 
            keyboard.press_and_release('2')
        finally:
            self.is_performing_action = False

    def perform_bait_select(self):
        if not self.auto_bait_var.get(): return
        p6 = self.point_coords.get(6)
        if not p6: return
        try:
            self.is_performing_action = True 
            self.click(p6, "Pt 6 (Bait Select)")
            time.sleep(0.5) 
            self.move_to(self.point_coords[4])
            time.sleep(0.2)
        except Exception: pass
        finally: self.is_performing_action = False

    def cast(self):
        if self.is_performing_action: return 
        self.click(self.point_coords[4], "Cast (Long)", hold_time=1.0)
        self.is_clicking = False
        self.session_loops += 1
        self.last_cast_time = time.time()
        if self.afk_mode_active:
             self.root.after(0, lambda: self.afk_session_label.config(text=str(self.session_loops)))
             current_total = self.stats['total_caught'] + self.session_loops
             self.root.after(0, lambda: self.afk_total_label.config(text=str(current_total)))
        self.previous_error = 0
        time.sleep(0.5)

    # --- LOOPS ---
    def run_fishing_loop(self):
        print("Fishing Loop Started")
        target_color = (0x55, 0xaa, 0xff) 
        dark_color = (0x19, 0x19, 0x19)
        white_color = (0xff, 0xff, 0xff)

        if self.camera is None: 
            try: self.camera = dxcam.create(output_color="BGR")
            except: pass

        if self.camera and not self.camera.is_capturing:
            self.camera.start(target_fps=60, video_mode=True)

        try:
            if self.auto_purchase_var.get(): self.perform_auto_purchase_sequence()
            self.cast()
            last_detection_time = time.time()
            was_detecting = False

            while self.fishing_active:
                if self.is_performing_action:
                    time.sleep(0.1)
                    continue

                img_full = self.camera.get_latest_frame()
                
                # Black screen fix
                if img_full is None:
                    time.sleep(0.01)
                    continue
                
                if np.sum(img_full) == 0:
                    print("Black screen detected! Restarting camera...")
                    self.camera.stop()
                    time.sleep(0.5)
                    self.camera.start(target_fps=60, video_mode=True)
                    time.sleep(0.5)
                    continue

                x, y = self.overlay_area['x'], self.overlay_area['y']
                width, height = self.overlay_area['width'], self.overlay_area['height']
                
                if y + height > img_full.shape[0] or x + width > img_full.shape[1]:
                    img = img_full 
                else:
                    img = img_full[y:y+height, x:x+width]

                point1_x = None
                point1_y = None
                found_first = False
                for row_idx in range(height):
                    for col_idx in range(width):
                        b, g, r = img[row_idx, col_idx, 0:3]
                        if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                            point1_x = x + col_idx
                            point1_y = y + row_idx
                            found_first = True
                            break
                    if found_first: break

                if not found_first:
                    current_time = time.time()
                    if was_detecting:
                        print("Lost detection (Game Over).")
                        time.sleep(self.wait_after_loss)
                        was_detecting = False
                        self.is_clicking = False
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        
                        if self.auto_purchase_var.get():
                            self.purchase_counter += 1
                            if self.purchase_counter >= self.loops_var.get():
                                self.perform_auto_purchase_sequence()
                                self.purchase_counter = 0
                        
                        if self.item_check_var.get(): self.perform_store_fruit()
                        if self.auto_bait_var.get(): self.perform_bait_select()
                        self.cast()
                        last_detection_time = time.time()
                    elif current_time - last_detection_time > self.scan_timeout:
                        print("Timeout. Recasting...")
                        if self.item_check_var.get(): self.perform_store_fruit()
                        if self.auto_bait_var.get(): self.perform_bait_select()
                        self.cast()
                        last_detection_time = time.time()
                    time.sleep(0.1)
                    continue

                point2_x = None
                row_idx = point1_y - y
                for col_idx in range(width - 1, -1, -1):
                    b, g, r = img[row_idx, col_idx, 0:3]
                    if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                        point2_x = x + col_idx
                        break
                
                if point2_x is None:
                    time.sleep(0.01)
                    continue

                temp_area_width = point2_x - point1_x + 1
                temp_x_offset = point1_x - x
                temp_img = img[:, temp_x_offset:temp_x_offset + temp_area_width]

                top_y = None
                for r_idx in range(height):
                    found_dark = False
                    for c_idx in range(temp_area_width):
                        b, g, r = temp_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            top_y = y + r_idx
                            found_dark = True
                            break
                    if found_dark: break
                
                bottom_y = None
                for r_idx in range(height - 1, -1, -1):
                    found_dark = False
                    for c_idx in range(temp_area_width):
                        b, g, r = temp_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            bottom_y = y + r_idx
                            found_dark = True
                            break
                    if found_dark: break

                if top_y is None or bottom_y is None:
                    time.sleep(0.1)
                    continue

                real_height = bottom_y - top_y + 1
                real_img = img[top_y-y:top_y-y+real_height, temp_x_offset:temp_x_offset+temp_area_width]
                
                white_top_y = None
                for r_idx in range(real_height):
                    for c_idx in range(temp_area_width):
                        b, g, r = real_img[r_idx, c_idx, 0:3]
                        if r == white_color[0] and g == white_color[1] and b == white_color[2]:
                            white_top_y = top_y + r_idx
                            break
                    if white_top_y is not None: break

                if white_top_y is None: continue

                dark_sections = []
                current_section_start = None
                gap_counter = 0
                max_gap = (real_height * 0.2) if white_top_y else 3

                for r_idx in range(real_height):
                    has_dark = False
                    for c_idx in range(temp_area_width):
                        b, g, r = real_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            has_dark = True
                            break
                    
                    if has_dark:
                        gap_counter = 0
                        if current_section_start is None:
                            current_section_start = top_y + r_idx
                    else:
                        if current_section_start is not None:
                            gap_counter += 1
                            if gap_counter > max_gap:
                                section_end = top_y + r_idx - gap_counter
                                dark_sections.append({
                                    'middle': (current_section_start + section_end) // 2,
                                    'size': section_end - current_section_start
                                })
                                current_section_start = None
                                gap_counter = 0
                
                if current_section_start is not None:
                    section_end = top_y + real_height - 1 - gap_counter
                    dark_sections.append({
                        'middle': (current_section_start + section_end) // 2,
                        'size': section_end - current_section_start
                    })

                if dark_sections and white_top_y is not None:
                    was_detecting = True
                    last_detection_time = time.time()
                    
                    largest_section = max(dark_sections, key=lambda s: s['size'])
                    raw_error = largest_section['middle'] - white_top_y
                    normalized_error = raw_error / real_height if real_height > 0 else raw_error
                    derivative = normalized_error - self.previous_error
                    self.previous_error = normalized_error
                    
                    pd_output = (self.kp_var.get() * normalized_error) + (self.kd_var.get() * derivative)
                    
                    time_since_cast = time.time() - self.last_cast_time
                    if pd_output > 0:
                        if time_since_cast > 3.0: 
                            if not self.is_clicking:
                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                self.is_clicking = True
                    else:
                        if self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self.is_clicking = False
                time.sleep(0.01)

        except Exception as e:
            print(f"Error in fishing loop: {e}")
        finally:
            self.camera.stop()
            if self.is_clicking:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_clicking = False
            self.save_config() # Auto-save on stop

    def run_reroll_loop(self):
        print("Reroll Loop Started")
        
        if self.camera is None: 
            try: self.camera = dxcam.create(output_color="BGR")
            except: pass
        if self.camera and not self.camera.is_capturing: 
            self.camera.start(target_fps=30, video_mode=True)
        
        try:
            p8 = self.point_coords.get(8)
            cx, cy = int(p8[0]), int(p8[1])
            
            while self.reroll_active:
                img = self.camera.get_latest_frame()
                if img is None: 
                    time.sleep(0.01)
                    continue
                
                # Black screen check
                if np.sum(img) == 0:
                    self.camera.stop()
                    time.sleep(0.5)
                    self.camera.start(target_fps=30, video_mode=True)
                    continue
                
                if cy < img.shape[0] and cx < img.shape[1]:
                    b, g, r = img[cy, cx]
                    # Check for Gold #b37a00 (R:179, G:122, B:0) +/- 35
                    if (abs(r - 179) < 35) and (abs(g - 122) < 35) and (abs(b - 0) < 35):
                        print("Reroll Button Detected. Clicking.")
                        self.click(p8, "Reroll")
                        time.sleep(0.2)
                
                time.sleep(0.1)
        except Exception as e:
            print(f"Error in reroll loop: {e}")
        finally:
            self.camera.stop()
            self.save_config()

    def save_geo(self, e=None):
        if self.overlay_window:
            self.overlay_area = {'x': self.overlay_window.winfo_x(), 'y': self.overlay_window.winfo_y(), 
                                 'width': self.overlay_window.winfo_width(), 'height': self.overlay_window.winfo_height()}

    def destroy_overlay(self):
        if self.overlay_window: self.overlay_window.destroy(); self.overlay_window = None

    def exit_app(self):
        self.save_config()
        self.fishing_active = False
        self.reroll_active = False
        self.record_session()
        self.destroy_overlay()
        try: keyboard.unhook_all()
        except: pass
        if self.camera: 
            try: self.camera.stop()
            except: pass
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = KarooFish(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()
