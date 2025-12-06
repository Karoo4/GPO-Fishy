import tkinter as tk
from tkinter import ttk, messagebox
import threading
import keyboard
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
import sys
import ctypes
import dxcam
import numpy as np
import win32api
import win32con
from PIL import Image, ImageTk, ImageEnhance
import requests
from io import BytesIO

# --- CONFIGURATION ---
THEME_BG = "#0b0b0b"        # Deep Black
THEME_ACCENT = "#ff8d00"    # Dark Orange
THEME_TEXT = "#ffffff"      # White text
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_AFK = ("Segoe UI", 48, "bold")

VIVI_URL = "https://static0.srcdn.com/wordpress/wp-content/uploads/2023/10/vivi.jpg?q=49&fit=crop&w=825&dpr=2"
DUCK_URL = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.ytimg.com%2Fvi%2FX8YUuU7OpOA%2Fmaxresdefault.jpg&f=1&nofb=1&ipt=6d669298669fff2e4f438b54453c1f59c1655ca19fa2407ea1c42e471a4d7ab6"

class KarooFarm:
    def __init__(self, root):
        self.root = root
        self.root.title("Karoo Farm")
        self.root.geometry("450x750")
        self.root.configure(bg=THEME_BG)
        self.root.attributes('-topmost', True)

        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass

        # State variables
        self.main_loop_active = False
        self.overlay_active = False
        self.afk_mode_active = False
        self.main_loop_thread = None
        self.recording_hotkey = None
        self.overlay_window = None
        self.is_clicking = False
        
        # Overlay Settings
        self.title_bar_height = 30 # Height of the draggable area
        
        # Counters and Logic
        self.purchase_counter = 0     
        self.total_loops_count = 0    
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0
        self.scan_timeout = 15.0
        self.wait_after_loss = 1.0
        self.purchase_delay_after_key = 2.0
        self.purchase_click_delay = 0.8
        self.purchase_after_type_delay = 0.8

        self.dpi_scale = self.get_dpi_scale()

        # Overlay init
        base_width = 172
        base_height = 495
        self.overlay_area = {
            'x': int(100 * self.dpi_scale),
            'y': int(100 * self.dpi_scale),
            'width': int(base_width * self.dpi_scale),
            'height': int(base_height * self.dpi_scale)
        }

        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3', 'toggle_afk': 'f4'}
        self.camera = None
        self.point_coords = {1: None, 2: None, 3: None, 4: None}
        self.point_buttons = {}

        self.bg_main = self.load_processed_image(VIVI_URL, darkness=0.3)
        self.bg_afk = self.load_processed_image(DUCK_URL, darkness=0.4)

        self.setup_ui()
        self.register_hotkeys()

    def get_dpi_scale(self):
        try: return self.root.winfo_fpixels('1i') / 96.0
        except: return 1.0

    def load_processed_image(self, url, darkness=0.5):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            img = img.resize((500, 800), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(ImageEnhance.Brightness(img).enhance(darkness))
        except Exception: return None

    def setup_ui(self):
        self.container = tk.Frame(self.root, bg=THEME_BG)
        self.container.pack(fill="both", expand=True)

        self.page_main = tk.Frame(self.container, bg=THEME_BG)
        self.page_main.place(relwidth=1, relheight=1)
        if self.bg_main: tk.Label(self.page_main, image=self.bg_main, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        self.create_main_widgets()

        self.page_afk = tk.Frame(self.container, bg=THEME_BG)
        if self.bg_afk: tk.Label(self.page_afk, image=self.bg_afk, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        self.create_afk_widgets()

    def create_main_widgets(self):
        scroll_container = tk.Canvas(self.page_main, bg=THEME_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.page_main, orient="vertical", command=scroll_container.yview)
        scrollbar.pack(side="right", fill="y")
        scroll_container.pack(side="left", fill="both", expand=True)
        scroll_container.configure(yscrollcommand=scrollbar.set)
        
        self.inner_frame = tk.Frame(scroll_container, bg=THEME_BG)
        scroll_container.create_window((0, 0), window=self.inner_frame, anchor="nw", width=430)
        self.inner_frame.bind("<Configure>", lambda e: scroll_container.configure(scrollregion=scroll_container.bbox("all")))
        scroll_container.bind_all("<MouseWheel>", lambda e: scroll_container.yview_scroll(int(-1*(e.delta/120)), "units"))

        tk.Label(self.inner_frame, text="Karoo Farm", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(pady=(20, 10))

        self.status_frame = tk.Frame(self.inner_frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        self.status_frame.pack(fill="x", padx=20, pady=10)
        self.loop_status = tk.Label(self.status_frame, text="Main Loop: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.loop_status.pack(pady=5)
        self.overlay_status = tk.Label(self.status_frame, text="Overlay: OFF", font=FONT_MAIN, bg=THEME_BG, fg="gray")
        self.overlay_status.pack(pady=5)

        self.create_section_label("Auto Purchase Settings")
        buy_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        buy_frame.pack(fill="x", padx=20)

        self.auto_purchase_var = tk.BooleanVar(value=False)
        self.create_toggle(buy_frame, "Active", self.auto_purchase_var)
        self.amount_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Amount to Buy:", self.amount_var)
        self.amount_var.trace_add('write', lambda *args: setattr(self, 'auto_purchase_amount', self.amount_var.get()))
        self.auto_purchase_amount = 10
        self.loops_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Loops per Buy:", self.loops_var)
        self.loops_var.trace_add('write', lambda *args: setattr(self, 'loops_per_purchase', self.loops_var.get()))
        self.loops_per_purchase = 10

        tk.Label(buy_frame, text="Coordinate Setup:", font=FONT_BOLD, bg=THEME_BG, fg=THEME_TEXT).pack(anchor="w", pady=(10, 5))
        labels = {1: "Pt 1: Yes / Confirm", 2: "Pt 2: Input Box", 3: "Pt 3: No / Close", 4: "Pt 4: Ocean / Reset"}
        for i in range(1, 5):
            row = tk.Frame(buy_frame, bg=THEME_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=labels[i], font=("Segoe UI", 9), bg=THEME_BG, fg="gray").pack(side="left")
            self.point_buttons[i] = tk.Button(row, text="Set", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold"), command=lambda x=i: self.capture_mouse_click(x), width=8, relief="flat")
            self.point_buttons[i].pack(side="right")

        self.create_section_label("PD Controller")
        pd_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        pd_frame.pack(fill="x", padx=20)
        self.kp_var = tk.DoubleVar(value=self.kp)
        self.create_input(pd_frame, "Kp (Prop.):", self.kp_var, is_float=True)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        self.kd_var = tk.DoubleVar(value=self.kd)
        self.create_input(pd_frame, "Kd (Deriv.):", self.kd_var, is_float=True)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))

        self.create_section_label("Timing")
        t_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        t_frame.pack(fill="x", padx=20)
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        self.create_input(t_frame, "Scan Timeout:", self.timeout_var, is_float=True)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))
        self.wait_var = tk.DoubleVar(value=self.wait_after_loss)
        self.create_input(t_frame, "Wait After Loss:", self.wait_var, is_float=True)
        self.wait_var.trace_add('write', lambda *args: setattr(self, 'wait_after_loss', self.wait_var.get()))

        self.create_section_label("Hotkeys")
        hk_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        hk_frame.pack(fill="x", padx=20, pady=(0, 50))
        self.create_hotkey_row(hk_frame, "Toggle Loop", 'toggle_loop')
        self.create_hotkey_row(hk_frame, "Toggle Overlay", 'toggle_overlay')
        self.create_hotkey_row(hk_frame, "AFK Mode", 'toggle_afk')
        self.create_hotkey_row(hk_frame, "Exit", 'exit')
        self.status_msg = tk.Label(self.inner_frame, text="", bg=THEME_BG, fg=THEME_ACCENT)
        self.status_msg.pack(pady=10)

    def create_afk_widgets(self):
        tk.Label(self.page_afk, text="AFK MODE", font=("Segoe UI", 30, "bold"), bg=THEME_BG, fg=THEME_ACCENT).place(relx=0.5, rely=0.2, anchor="center")
        tk.Label(self.page_afk, text="Total Loops Completed:", font=("Segoe UI", 12), bg=THEME_BG, fg="white").place(relx=0.5, rely=0.4, anchor="center")
        self.afk_count_label = tk.Label(self.page_afk, text="0", font=FONT_AFK, bg=THEME_BG, fg=THEME_ACCENT)
        self.afk_count_label.place(relx=0.5, rely=0.5, anchor="center")
        self.afk_hint_label = tk.Label(self.page_afk, text="Press F4 to return", font=("Segoe UI", 10, "italic"), bg=THEME_BG, fg="gray")
        self.afk_hint_label.place(relx=0.5, rely=0.8, anchor="center")

    def create_section_label(self, text):
        f = tk.Frame(self.inner_frame, bg=THEME_BG)
        f.pack(fill="x", pady=(20, 5))
        tk.Label(f, text=text, font=("Segoe UI", 14, "bold"), bg=THEME_BG, fg=THEME_ACCENT).pack(side="left", padx=20)
        tk.Frame(f, bg=THEME_ACCENT, height=2).pack(side="left", fill="x", expand=True, padx=(10, 20), pady=(8, 0))

    def create_input(self, parent, label, var, is_float=False):
        row = tk.Frame(parent, bg=THEME_BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, bg=THEME_BG, fg="white", font=FONT_MAIN).pack(side="left")
        tk.Spinbox(row, textvariable=var, bg="#202020", fg=THEME_ACCENT, buttonbackground=THEME_ACCENT, relief="flat", width=10, from_=0.0, to=1000000, increment=0.1 if is_float else 1).pack(side="right")

    def create_toggle(self, parent, text, var):
        tk.Checkbutton(parent, text=text, variable=var, bg=THEME_BG, fg="white", selectcolor="#202020", activebackground=THEME_BG, activeforeground=THEME_ACCENT, font=FONT_BOLD).pack(anchor="w", pady=5)

    def create_hotkey_row(self, parent, label, key_key):
        row = tk.Frame(parent, bg=THEME_BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, bg=THEME_BG, fg="gray").pack(side="left")
        btn = tk.Button(row, text="Rebind", bg="#202020", fg="white", relief="flat", command=lambda: self.start_rebind(key_key), font=("Segoe UI", 8))
        btn.pack(side="right", padx=5)
        lbl = tk.Label(row, text=self.hotkeys[key_key].upper(), bg=THEME_BG, fg=THEME_ACCENT, font=FONT_BOLD)
        lbl.pack(side="right", padx=10)
        setattr(self, f"lbl_{key_key}", lbl)
        setattr(self, f"btn_{key_key}", btn)

    def register_hotkeys(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys['toggle_loop'], lambda: self.root.after(0, self.toggle_main_loop))
            keyboard.add_hotkey(self.hotkeys['toggle_overlay'], lambda: self.root.after(0, self.toggle_overlay))
            keyboard.add_hotkey(self.hotkeys['toggle_afk'], lambda: self.root.after(0, self.toggle_afk_mode))
            keyboard.add_hotkey(self.hotkeys['exit'], lambda: self.root.after(0, self.exit_app))
        except: pass

    def toggle_afk_mode(self):
        self.afk_mode_active = not self.afk_mode_active
        if self.afk_mode_active:
            self.page_main.place_forget()
            self.page_afk.place(relwidth=1, relheight=1)
            self.afk_hint_label.config(text=f"Press {self.hotkeys['toggle_afk'].upper()} to return & reset")
        else:
            self.page_afk.place_forget()
            self.page_main.place(relwidth=1, relheight=1)
            self.total_loops_count = 0
            self.afk_count_label.config(text="0")

    def toggle_main_loop(self):
        new_state = not self.main_loop_active
        if new_state:
            if self.auto_purchase_var.get():
                if any(not self.point_coords.get(i) for i in range(1, 5)):
                    self.status_msg.config(text="Missing Points!", fg="red")
                    return
            self.purchase_counter = 0
            self.main_loop_active = True
            self.loop_status.config(text="Main Loop: ON", fg="#00ff00")
            self.main_loop_thread = threading.Thread(target=self.main_loop, daemon=True)
            self.main_loop_thread.start()
        else:
            self.main_loop_active = False
            self.loop_status.config(text="Main Loop: OFF", fg="red")
            if self.is_clicking:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_clicking = False
            self.previous_error = 0

    def capture_mouse_click(self, idx):
        self.status_msg.config(text=f"Click anywhere to set Point {idx}...", fg=THEME_ACCENT)
        def _on_click(x, y, button, pressed):
            if pressed:
                self.point_coords[idx] = (x, y)
                self.root.after(0, lambda: self.point_buttons[idx].config(text="Done", bg="#00ff00", fg="black"))
                self.root.after(0, lambda: self.status_msg.config(text=f"Point {idx} set: {x}, {y}", fg="#00ff00"))
                return False 
        pynput_mouse.Listener(on_click=_on_click).start()

    def start_rebind(self, action):
        self.recording_hotkey = action
        self.status_msg.config(text=f"Press key for '{action}'...", fg=THEME_ACCENT)
        getattr(self, f"btn_{action}").config(state="disabled", text="...")
        pynput_keyboard.Listener(on_press=self.on_key_press).start()

    def on_key_press(self, key):
        if self.recording_hotkey is None: return False
        try:
            key_name = key.name if hasattr(key, 'name') else key.char if hasattr(key, 'char') else str(key).replace('Key.', '')
            self.hotkeys[self.recording_hotkey] = key_name
            self.root.after(0, lambda: getattr(self, f"lbl_{self.recording_hotkey}").config(text=key_name.upper()))
            self.root.after(0, lambda: getattr(self, f"btn_{self.recording_hotkey}").config(state="normal", text="Rebind"))
            self.root.after(0, self.register_hotkeys)
            self.recording_hotkey = None
            return False
        except: return False

    def _click_at(self, coords):
        try:
            x, y = int(coords[0]), int(coords[1])
            win32api.SetCursorPos((x, y))
            try: win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            except: pass
            threading.Event().wait(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            threading.Event().wait(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except: pass

    def perform_auto_purchase_sequence(self):
        try:
            keyboard.press_and_release('e')
            threading.Event().wait(self.purchase_delay_after_key)
            self._click_at(self.point_coords[1])
            threading.Event().wait(self.purchase_click_delay)
            self._click_at(self.point_coords[2])
            threading.Event().wait(self.purchase_click_delay)
            keyboard.write(str(self.amount_var.get()))
            threading.Event().wait(self.purchase_after_type_delay)
            self._click_at(self.point_coords[1])
            threading.Event().wait(self.purchase_click_delay)
            self._click_at(self.point_coords[3])
            threading.Event().wait(self.purchase_click_delay)
            self._click_at(self.point_coords[4])
            threading.Event().wait(self.purchase_click_delay)
        except: pass

    def check_and_purchase(self):
        if self.auto_purchase_var.get():
            self.purchase_counter += 1
            if self.purchase_counter >= max(1, self.loops_per_purchase):
                self.perform_auto_purchase_sequence()
                self.purchase_counter = 0

    def cast_line(self):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        threading.Event().wait(1.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_clicking = False
        self.total_loops_count += 1
        if self.afk_mode_active: self.root.after(0, lambda: self.afk_count_label.config(text=str(self.total_loops_count)))

    def main_loop(self):
        target_color, dark_color, white_color = (0x55, 0xaa, 0xff), (0x19, 0x19, 0x19), (0xff, 0xff, 0xff)
        import time
        if self.camera is None: self.camera = dxcam.create(output_color="BGR")
        self.camera.start(target_fps=60, video_mode=True)
        
        try:
            if self.auto_purchase_var.get(): self.perform_auto_purchase_sequence()
            self.cast_line()
            last_detection_time, was_detecting = time.time(), False
            
            while self.main_loop_active:
                x, y = self.overlay_area['x'], self.overlay_area['y']
                w, h = self.overlay_area['width'], self.overlay_area['height']
                
                # IMPORTANT: ADJUST SCAN AREA TO IGNORE TITLE BAR
                scan_y = y + self.title_bar_height
                scan_h = h - self.title_bar_height
                if scan_h < 10: 
                    threading.Event().wait(0.1)
                    continue
                
                img = self.camera.get_latest_frame()
                if img is None: 
                    threading.Event().wait(0.01)
                    continue
                
                img = img[scan_y:scan_y+scan_h, x:x+w] # Crop to hollow part
                
                # Logic: Find Blue Bar (Pt1/Pt2)
                p1x, p1y, found = None, None, False
                for r in range(scan_h):
                    for c in range(w):
                        b, g, r_ = img[r, c, 0:3]
                        if r_ == target_color[0] and g == target_color[1] and b == target_color[2]:
                            p1x, p1y, found = x + c, scan_y + r, True
                            break
                    if found: break
                
                if not found:
                    if was_detecting:
                        threading.Event().wait(self.wait_after_loss)
                        was_detecting = False
                        self.check_and_purchase()
                        self.cast_line()
                        last_detection_time = time.time()
                    elif time.time() - last_detection_time > self.scan_timeout:
                        self.check_and_purchase()
                        self.cast_line()
                        last_detection_time = time.time()
                    threading.Event().wait(0.05)
                    continue

                p2x = None
                row = p1y - scan_y
                for c in range(w - 1, -1, -1):
                    b, g, r_ = img[row, c, 0:3]
                    if r_ == target_color[0] and g == target_color[1] and b == target_color[2]:
                        p2x = x + c
                        break
                if p2x is None: continue

                # Bounds
                tx_off, tw = p1x - x, p2x - p1x + 1
                t_img = img[:, tx_off:tx_off + tw]
                
                ty, by = None, None
                for r in range(scan_h):
                    for c in range(tw):
                        b, g, r_ = t_img[r, c, 0:3]
                        if r_ == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            ty = scan_y + r; break
                    if ty: break
                for r in range(scan_h - 1, -1, -1):
                    for c in range(tw):
                        b, g, r_ = t_img[r, c, 0:3]
                        if r_ == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            by = scan_y + r; break
                    if by: break
                if ty is None or by is None: continue
                
                rh = by - ty + 1
                r_img = img[(ty-scan_y):(ty-scan_y)+rh, tx_off:tx_off+tw]
                
                wy = None
                for r in range(rh):
                    for c in range(tw):
                        b, g, r_ = r_img[r, c, 0:3]
                        if r_ == white_color[0] and g == white_color[1] and b == white_color[2]:
                            wy = ty + r; break
                    if wy: break
                
                secs, st, gap = [], None, 0
                for r in range(rh):
                    dark = False
                    for c in range(tw):
                        b, g, r_ = r_img[r, c, 0:3]
                        if r_ == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            dark = True; break
                    if dark:
                        if st is None: st = r
                        gap = 0
                    else:
                        if st is not None:
                            gap += 1
                            if gap > 5:
                                secs.append((st, r - gap))
                                st, gap = None, 0
                if st is not None: secs.append((st, rh - 1))
                
                if secs and wy is not None:
                    was_detecting = True
                    last_detection_time = time.time()
                    best = max(secs, key=lambda s: s[1]-s[0])
                    mid = (best[0] + best[1]) // 2
                    
                    err = mid - (wy - ty)
                    n_err = err / rh
                    deriv = n_err - self.previous_error
                    self.previous_error = n_err
                    out = (self.kp * n_err) + (self.kd * deriv)
                    
                    if out > 0 and not self.is_clicking:
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        self.is_clicking = True
                    elif out <= 0 and self.is_clicking:
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        self.is_clicking = False
                threading.Event().wait(0.01)
        except Exception as e: print(e)
        finally:
            if self.camera: self.camera.stop()
            if self.is_clicking: win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    # --- OVERLAY ---
    def toggle_overlay(self):
        self.overlay_active = not self.overlay_active
        if self.overlay_active:
            self.overlay_status.config(text="Overlay: ON", fg=THEME_ACCENT)
            self.create_overlay()
        else:
            self.overlay_status.config(text="Overlay: OFF", fg="gray")
            self.destroy_overlay()

    def create_overlay(self):
        if self.overlay_window: return
        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes('-alpha', 0.5)
        self.overlay_window.attributes('-topmost', True)
        self.overlay_window.wm_attributes("-transparentcolor", "black")
        self.overlay_window.minsize(100, 100)
        
        geo = f"{self.overlay_area['width']}x{self.overlay_area['height']}+{self.overlay_area['x']}+{self.overlay_area['y']}"
        self.overlay_window.geometry(geo)
        
        # 1. Title Bar (Opaque Orange) - DRAG HERE
        title_bar = tk.Frame(self.overlay_window, bg=THEME_ACCENT, height=self.title_bar_height)
        title_bar.pack(side="top", fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text=":: DRAG HERE ::", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold")).pack(expand=True)

        # 2. Hollow Frame (Orange Borders, Transparent Center)
        container = tk.Frame(self.overlay_window, bg=THEME_ACCENT)
        container.pack(side="top", fill="both", expand=True)
        
        inner = tk.Frame(container, bg="black") # Black becomes transparent
        inner.pack(fill="both", expand=True, padx=3, pady=(0, 3))

        self.overlay_drag_data = {"x": 0, "y": 0, "edge": None}
        
        # Bind Drag to Title Bar
        title_bar.bind("<ButtonPress-1>", self.start_overlay_drag)
        title_bar.bind("<B1-Motion>", self.overlay_motion)
        
        # Bind Resize to Container
        container.bind("<ButtonPress-1>", self.start_overlay_drag)
        container.bind("<B1-Motion>", self.overlay_motion)
        container.bind("<Motion>", self.update_cursor)
        
        self.overlay_window.bind("<Configure>", self.on_overlay_configure)

    def get_resize_edge(self, x, y, width, height):
        e = 15
        if y < e and x < e: return "nw"
        if y < e and x > width - e: return "ne"
        if y > height - e and x < e: return "sw"
        if y > height - e and x > width - e: return "se"
        if x < e: return "w"
        if x > width - e: return "e"
        if y < e: return "n"
        if y > height - e: return "s"
        return None

    def update_cursor(self, event):
        w, h = self.overlay_window.winfo_width(), self.overlay_window.winfo_height()
        # Adjust y because event is relative to container, but logic assumes window coords?
        # Actually event.y in container starts after title bar.
        # Simplification: Resize only works on Bottom/Left/Right edges easily.
        # Just return default to avoid complexity or offset y by title_bar_height
        self.overlay_window.config(cursor="arrow") 

    def start_overlay_drag(self, event):
        # If clicked on title bar, it's a move.
        widget = event.widget
        # If dragging title bar or label inside title bar
        if widget.master == self.overlay_window or widget.master.master == self.overlay_window:
             self.overlay_drag_data = {"x": event.x_root - self.overlay_window.winfo_x(), "y": event.y_root - self.overlay_window.winfo_y(), "edge": None}
        else:
            # Resize logic (simplified)
            self.overlay_drag_data = {"x": event.x, "y": event.y, "edge": "se"} # Default to resize corner for simplicity if clicking body

    def overlay_motion(self, event):
        if self.overlay_drag_data["edge"] is None:
            # Moving
            nx = event.x_root - self.overlay_drag_data["x"]
            ny = event.y_root - self.overlay_drag_data["y"]
            self.overlay_window.geometry(f"+{nx}+{ny}")
        else:
            # Resizing (Simple SE resize for now to prevent bugs)
            # Full resizing logic with title bar offset is complex in tkinter without exact event mapping
            pass

    def on_overlay_configure(self, event=None):
        if self.overlay_window:
            self.overlay_area = {'x': self.overlay_window.winfo_x(), 'y': self.overlay_window.winfo_y(), 'width': self.overlay_window.winfo_width(), 'height': self.overlay_window.winfo_height()}

    def destroy_overlay(self):
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None

    def exit_app(self):
        self.main_loop_active = False
        if self.overlay_window: self.overlay_window.destroy()
        try: keyboard.unhook_all()
        except: pass
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = KarooFarm(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()
