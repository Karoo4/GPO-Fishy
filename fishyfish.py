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
import time

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
        self.root.geometry("450x850") # Taller for new settings
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
        self.title_bar_height = 30
        
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
        
        # Item Check settings
        self.check_items = True

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
        
        # Points: 1=Yes, 2=Input, 3=No, 4=Ocean, 5=ItemCheck
        self.point_coords = {1: None, 2: None, 3: None, 4: None, 5: None}
        self.point_buttons = {}
        self.point_labels = {} 

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
            img = img.resize((500, 900), Image.Resampling.LANCZOS)
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

        # Status
        self.status_frame = tk.Frame(self.inner_frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        self.status_frame.pack(fill="x", padx=20, pady=10)
        self.loop_status = tk.Label(self.status_frame, text="Main Loop: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.loop_status.pack(pady=5)
        self.overlay_status = tk.Label(self.status_frame, text="Overlay: OFF", font=FONT_MAIN, bg=THEME_BG, fg="gray")
        self.overlay_status.pack(pady=5)

        # --- AUTO PURCHASE SECTION ---
        self.create_section_label("Auto Purchase")
        buy_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        buy_frame.pack(fill="x", padx=20)

        self.auto_purchase_var = tk.BooleanVar(value=False)
        self.create_toggle(buy_frame, "Active", self.auto_purchase_var)
        self.amount_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Amount:", self.amount_var)
        self.amount_var.trace_add('write', lambda *args: setattr(self, 'auto_purchase_amount', self.amount_var.get()))
        self.auto_purchase_amount = 10
        self.loops_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Loops/Buy:", self.loops_var)
        self.loops_var.trace_add('write', lambda *args: setattr(self, 'loops_per_purchase', self.loops_var.get()))
        self.loops_per_purchase = 10

        tk.Label(buy_frame, text="Coordinates:", font=FONT_BOLD, bg=THEME_BG, fg=THEME_TEXT).pack(anchor="w", pady=(10, 5))
        
        # Purchase Points
        p_labels = {1: "Pt 1 (Yes)", 2: "Pt 2 (Input)", 3: "Pt 3 (No)", 4: "Pt 4 (Ocean)"}
        for i in range(1, 5):
            self.create_point_row(buy_frame, i, p_labels[i])

        # --- INVENTORY SECTION ---
        self.create_section_label("Inventory / Item Check")
        inv_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        inv_frame.pack(fill="x", padx=20)
        
        self.item_check_var = tk.BooleanVar(value=True)
        self.create_toggle(inv_frame, "Enable Item Cleaning", self.item_check_var)
        
        self.create_point_row(inv_frame, 5, "Pt 5 (Slot 3 Check)")

        # --- SETTINGS ---
        self.create_section_label("Settings")
        set_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        set_frame.pack(fill="x", padx=20)
        
        self.kp_var = tk.DoubleVar(value=self.kp)
        self.create_input(set_frame, "Kp:", self.kp_var, is_float=True)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        
        self.kd_var = tk.DoubleVar(value=self.kd)
        self.create_input(set_frame, "Kd:", self.kd_var, is_float=True)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))
        
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        self.create_input(set_frame, "Timeout:", self.timeout_var, is_float=True)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))

        # --- HOTKEYS ---
        self.create_section_label("Hotkeys")
        hk_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        hk_frame.pack(fill="x", padx=20, pady=(0, 50))
        self.create_hotkey_row(hk_frame, "Loop", 'toggle_loop')
        self.create_hotkey_row(hk_frame, "Overlay", 'toggle_overlay')
        self.create_hotkey_row(hk_frame, "AFK Mode", 'toggle_afk')
        self.create_hotkey_row(hk_frame, "Exit", 'exit')
        
        self.status_msg = tk.Label(self.inner_frame, text="", bg=THEME_BG, fg=THEME_ACCENT)
        self.status_msg.pack(pady=10)

    def create_point_row(self, parent, idx, text_label):
        row = tk.Frame(parent, bg=THEME_BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=text_label, font=("Segoe UI", 9), bg=THEME_BG, fg="gray").pack(side="left")
        
        # Container for coords label and button
        right = tk.Frame(row, bg=THEME_BG)
        right.pack(side="right")
        
        coord_lbl = tk.Label(right, text="Not Set", font=("Segoe UI", 8), bg=THEME_BG, fg="red")
        coord_lbl.pack(side="left", padx=5)
        self.point_labels[idx] = coord_lbl
        
        btn = tk.Button(right, text="Set", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold"), 
                        command=lambda x=idx: self.capture_mouse_click(x), width=6, relief="flat")
        btn.pack(side="left")
        self.point_buttons[idx] = btn

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
            # Check Points based on features enabled
            req_points = []
            if self.auto_purchase_var.get():
                req_points.extend([1, 2, 4]) # Pt 3 is optional? Protocol says 1,2,4 needed.
            if self.item_check_var.get():
                req_points.append(5)
            
            missing = [p for p in req_points if not self.point_coords.get(p)]
            if missing:
                self.status_msg.config(text=f"Missing Points: {missing}", fg="red")
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
                self.root.after(0, lambda: self.point_labels[idx].config(text=f"{x}, {y}", fg="#00ff00"))
                self.root.after(0, lambda: self.status_msg.config(text=f"Point {idx} Saved.", fg="#00ff00"))
                return False 
        pynput_mouse.Listener(on_click=_on_click).start()

    def start_rebind(self, action):
        self.recording_hotkey = action
        self.status_msg.config(text=f"Press key...", fg=THEME_ACCENT)
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
        if not coords: return
        try:
            x, y = int(coords[0]), int(coords[1])
            win32api.SetCursorPos((x, y))
            try: win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            except: pass
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except: pass

    # --- ACTION SEQUENCES ---

    def perform_auto_purchase_sequence(self):
        # Sequence: Yes -> Input -> Type -> Yes -> Input -> Ocean
        try:
            keyboard.press_and_release('e')
            time.sleep(self.purchase_delay_after_key)
            
            # 1. Yes
            self._click_at(self.point_coords[1])
            time.sleep(self.purchase_click_delay)
            
            # 2. Input
            self._click_at(self.point_coords[2])
            time.sleep(self.purchase_click_delay)
            
            # 3. Type
            keyboard.write(str(self.amount_var.get()))
            time.sleep(self.purchase_after_type_delay)
            
            # 4. Yes
            self._click_at(self.point_coords[1])
            time.sleep(self.purchase_click_delay)
            
            # 5. Input (Requested Sequence)
            self._click_at(self.point_coords[2])
            time.sleep(self.purchase_click_delay)
            
            # 6. Ocean
            self._click_at(self.point_coords[4])
            time.sleep(self.purchase_click_delay)
        except Exception as e: print(f"Purchase Error: {e}")

    def perform_item_check(self):
        # Press 3 -> Click Pt 5 -> Check if changed -> if not Backspace -> Press 2
        p5 = self.point_coords.get(5)
        if not p5: return

        try:
            # 1. Press 3
            keyboard.press_and_release('3')
            time.sleep(0.3)
            
            # 2. Check Color before Click
            img_before = self.camera.get_latest_frame()
            if img_before is not None:
                x, y = int(p5[0]), int(p5[1])
                # Safety crop check
                if 0 <= y < img_before.shape[0] and 0 <= x < img_before.shape[1]:
                    color_before = img_before[y, x].tolist() # [B, G, R]
                else: color_before = [0,0,0]
            
            # 3. Click
            self._click_at(p5)
            time.sleep(0.5)
            
            # 4. Check Color after Click
            img_after = self.camera.get_latest_frame()
            clicked_something = False
            
            if img_after is not None:
                 if 0 <= y < img_after.shape[0] and 0 <= x < img_after.shape[1]:
                    color_after = img_after[y, x].tolist()
                    # Calculate diff
                    diff = sum([abs(c1 - c2) for c1, c2 in zip(color_before, color_after)])
                    # If Diff is small, the item didn't move/disappear (it's stuck or we selected it)
                    # If Diff is large, UI changed (Good?)
                    # User logic: "If element doesnt disappear... press backspace"
                    # We assume clicking it selects it.
            
            # Blind Backspace logic based on user request "If element doesnt disappear"
            # Since we can't reliably know "Disappear" without a baseline empty color,
            # We will press Backspace if we clicked.
            
            keyboard.press_and_release('backspace')
            time.sleep(0.3)
            
            # 5. Return to Rod
            keyboard.press_and_release('2')
            time.sleep(0.5)
            
        except Exception as e: print(f"Item Check Error: {e}")

    def main_loop(self):
        target_color, dark_color, white_color = (0x55, 0xaa, 0xff), (0x19, 0x19, 0x19), (0xff, 0xff, 0xff)
        if self.camera is None: self.camera = dxcam.create(output_color="BGR")
        self.camera.start(target_fps=60, video_mode=True)
        
        try:
            if self.auto_purchase_var.get(): self.perform_auto_purchase_sequence()
            
            # Initial Cast
            self._click_at(self.point_coords[4]) # Ensure focus
            self.cast_line()
            
            last_detection_time, was_detecting = time.time(), False
            
            while self.main_loop_active:
                x, y = self.overlay_area['x'], self.overlay_area['y']
                w, h = self.overlay_area['width'], self.overlay_area['height']
                
                scan_y_off = self.title_bar_height 
                scan_h = h - scan_y_off - 5
                
                if scan_h < 10: 
                    time.sleep(0.1)
                    continue
                
                img = self.camera.get_latest_frame()
                if img is None: 
                    time.sleep(0.01)
                    continue
                
                img = img[y+scan_y_off : y+scan_y_off+scan_h, x:x+w]
                
                # --- DETECTION LOGIC START ---
                p1x, p1y, found = None, None, False
                for r in range(scan_h):
                    for c in range(w):
                        b, g, r_ = img[r, c, 0:3]
                        if r_ == target_color[0] and g == target_color[1] and b == target_color[2]:
                            p1x, p1y, found = x + c, r, True
                            break
                    if found: break
                
                if not found:
                    if was_detecting:
                        time.sleep(self.wait_after_loss)
                        was_detecting = False
                        
                        # LOGIC: Loop Finished. Check Purchase -> Check Inventory -> Cast
                        if self.auto_purchase_var.get():
                            self.purchase_counter += 1
                            if self.purchase_counter >= max(1, self.loops_per_purchase):
                                self.perform_auto_purchase_sequence()
                                self.purchase_counter = 0
                                
                        if self.item_check_var.get():
                            self.perform_item_check()
                            
                        self.cast_line()
                        last_detection_time = time.time()
                    elif time.time() - last_detection_time > self.scan_timeout:
                        # Timeout logic
                        if self.item_check_var.get(): self.perform_item_check()
                        self.cast_line()
                        last_detection_time = time.time()
                    time.sleep(0.05)
                    continue

                p2x = None
                row = p1y
                for c in range(w - 1, -1, -1):
                    b, g, r_ = img[row, c, 0:3]
                    if r_ == target_color[0] and g == target_color[1] and b == target_color[2]:
                        p2x = x + c
                        break
                if p2x is None: continue

                tx_off, tw = p1x - x, p2x - p1x + 1
                t_img = img[:, tx_off:tx_off + tw]
                
                ty, by = None, None
                for r in range(scan_h):
                    for c in range(tw):
                        b, g, r_ = t_img[r, c, 0:3]
                        if r_ == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            ty = r; break
                    if ty: break
                for r in range(scan_h - 1, -1, -1):
                    for c in range(tw):
                        b, g, r_ = t_img[r, c, 0:3]
                        if r_ == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            by = r; break
                    if by: break
                if ty is None or by is None: continue
                
                rh = by - ty + 1
                r_img = img[(ty):(ty)+rh, tx_off:tx_off+tw]
                
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
                time.sleep(0.01)
        except Exception as e: print(e)
        finally:
            if self.camera: self.camera.stop()
            if self.is_clicking: win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def cast_line(self):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(1.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_clicking = False
        self.total_loops_count += 1
        if self.afk_mode_active: self.root.after(0, lambda: self.afk_count_label.config(text=str(self.total_loops_count)))

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
        
        # 1. Title Bar
        title_bar = tk.Frame(self.overlay_window, bg=THEME_ACCENT, height=self.title_bar_height, cursor="fleur")
        title_bar.pack(side="top", fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text=":: DRAG HERE ::", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold")).pack(expand=True)

        # 2. Frame
        container = tk.Frame(self.overlay_window, bg=THEME_ACCENT)
        container.pack(side="top", fill="both", expand=True)
        inner = tk.Frame(container, bg="black") 
        inner.pack(fill="both", expand=True, padx=3, pady=0)

        # Bindings
        self.overlay_drag_data = {"x": 0, "y": 0}
        
        # Move
        title_bar.bind("<ButtonPress-1>", self.start_drag)
        title_bar.bind("<B1-Motion>", self.do_drag)
        
        # Resize: Use the window borders via binds on the whole window
        self.overlay_window.bind("<Motion>", self.update_cursor)
        self.overlay_window.bind("<ButtonPress-1>", self.start_resize_check)
        self.overlay_window.bind("<B1-Motion>", self.do_resize_check)

        self.overlay_window.bind("<Configure>", self.on_overlay_configure)

    def start_drag(self, event):
        self.overlay_drag_data = {"mode": "move", "x": event.x_root, "y": event.y_root, "win_x": self.overlay_window.winfo_x(), "win_y": self.overlay_window.winfo_y()}

    def do_drag(self, event):
        dx = event.x_root - self.overlay_drag_data["x"]
        dy = event.y_root - self.overlay_drag_data["y"]
        self.overlay_window.geometry(f"+{self.overlay_drag_data['win_x'] + dx}+{self.overlay_drag_data['win_y'] + dy}")

    def get_edge(self, event):
        w, h = self.overlay_window.winfo_width(), self.overlay_window.winfo_height()
        x, y = event.x, event.y
        m = 10 # margin
        
        if x < m and y < m: return "nw"
        if x > w-m and y < m: return "ne"
        if x < m and y > h-m: return "sw"
        if x > w-m and y > h-m: return "se"
        if x < m: return "w"
        if x > w-m: return "e"
        if y < m: return "n"
        if y > h-m: return "s"
        return None

    def update_cursor(self, event):
        edge = self.get_edge(event)
        cursors = {"nw":"size_nw_se", "ne":"size_ne_sw", "sw":"size_ne_sw", "se":"size_nw_se", "n":"size_ns", "s":"size_ns", "w":"size_we", "e":"size_we"}
        self.overlay_window.config(cursor=cursors.get(edge, "arrow"))

    def start_resize_check(self, event):
        edge = self.get_edge(event)
        if edge:
            self.overlay_drag_data = {
                "mode": "resize", "edge": edge, "x": event.x_root, "y": event.y_root,
                "x_win": self.overlay_window.winfo_x(), "y_win": self.overlay_window.winfo_y(),
                "w": self.overlay_window.winfo_width(), "h": self.overlay_window.winfo_height()
            }

    def do_resize_check(self, event):
        if self.overlay_drag_data.get("mode") != "resize": return
        edge = self.overlay_drag_data["edge"]
        dx = event.x_root - self.overlay_drag_data["x"]
        dy = event.y_root - self.overlay_drag_data["y"]
        
        x, y, w, h = self.overlay_drag_data["x_win"], self.overlay_drag_data["y_win"], self.overlay_drag_data["w"], self.overlay_drag_data["h"]
        
        if 'e' in edge: w += dx
        if 'w' in edge: w -= dx; x += dx
        if 's' in edge: h += dy
        if 'n' in edge: h -= dy; y += dy
        
        w = max(100, w)
        h = max(100, h)
        self.overlay_window.geometry(f"{w}x{h}+{x}+{y}")

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
