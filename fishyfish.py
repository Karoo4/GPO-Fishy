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
THEME_TEXT = "#ffffff"      # White text for readability on dark
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

        # Make GUI always on top
        self.root.attributes('-topmost', True)

        # Make app DPI aware
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        # State variables
        self.main_loop_active = False
        self.overlay_active = False
        self.afk_mode_active = False
        self.main_loop_thread = None
        self.recording_hotkey = None
        self.overlay_window = None
        self.real_area = None
        self.is_clicking = False
        
        # Counters
        self.purchase_counter = 0     # For auto-buy logic
        self.total_loops_count = 0    # For AFK stats
        
        # PD controller defaults
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0

        # Timing defaults
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

        # Hotkeys
        self.hotkeys = {
            'toggle_loop': 'f1',
            'toggle_overlay': 'f2',
            'exit': 'f3',
            'toggle_afk': 'f4'
        }

        # Initialize Camera
        self.camera = None

        # Points
        self.point_coords = {1: None, 2: None, 3: None, 4: None}
        self.point_buttons = {}

        # Load Images
        self.bg_main = self.load_processed_image(VIVI_URL, darkness=0.3)
        self.bg_afk = self.load_processed_image(DUCK_URL, darkness=0.4)

        # Setup UI Pages
        self.setup_ui()
        
        # Register Hotkeys
        self.register_hotkeys()

    def get_dpi_scale(self):
        try:
            dpi = self.root.winfo_fpixels('1i')
            return dpi / 96.0
        except:
            return 1.0

    def load_processed_image(self, url, darkness=0.5):
        """Downloads, resizes to fit window (rough), and darkens image."""
        try:
            response = requests.get(url, timeout=5)
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            
            # Resize logic (Cover)
            target_w, target_h = 500, 800 # Slightly larger than window
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # Darken
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(darkness) # Lower is darker
            
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Failed to load image: {e}")
            return None

    def setup_ui(self):
        # --- CONTAINER ---
        self.container = tk.Frame(self.root, bg=THEME_BG)
        self.container.pack(fill="both", expand=True)

        # --- MAIN PAGE ---
        self.page_main = tk.Frame(self.container, bg=THEME_BG)
        self.page_main.place(relwidth=1, relheight=1)

        # Background Image for Main
        if self.bg_main:
            bg_label = tk.Label(self.page_main, image=self.bg_main, bg=THEME_BG)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.create_main_widgets()

        # --- AFK PAGE ---
        self.page_afk = tk.Frame(self.container, bg=THEME_BG)
        # Don't pack/place yet

        # Background Image for AFK
        if self.bg_afk:
            bg_afk_label = tk.Label(self.page_afk, image=self.bg_afk, bg=THEME_BG)
            bg_afk_label.place(x=0, y=0, relwidth=1, relheight=1)
            
        self.create_afk_widgets()

    def create_main_widgets(self):
        # Use a canvas for scrolling overlaying the background
        # Note: Transparent scrolling frames are hard in Tkinter. 
        # We will use a standard frame centered for "Cards" feel.
        
        scroll_container = tk.Canvas(self.page_main, bg=THEME_BG, highlightthickness=0)
        # Remove white background of canvas to try and show image (Tkinter canvas can't be transparent easily)
        # Instead, we will pack the widgets directly or use a dark semi-transparent stipple? 
        # For simplicity and stability with the image background, we'll pack a central column frame that is semi-transparent black?
        # Tkinter doesn't do transparency well. We will use black backgrounds for widgets.

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.page_main, orient="vertical", command=scroll_container.yview)
        scrollbar.pack(side="right", fill="y")
        
        scroll_container.pack(side="left", fill="both", expand=True)
        scroll_container.configure(yscrollcommand=scrollbar.set)

        # The internal frame
        self.inner_frame = tk.Frame(scroll_container, bg=THEME_BG)
        scroll_container.create_window((0, 0), window=self.inner_frame, anchor="nw", width=430) # Fixed width adjust

        def on_frame_configure(event):
            scroll_container.configure(scrollregion=scroll_container.bbox("all"))
        self.inner_frame.bind("<Configure>", on_frame_configure)
        
        # Mousewheel
        def on_mousewheel(event):
            scroll_container.yview_scroll(int(-1*(event.delta/120)), "units")
        scroll_container.bind_all("<MouseWheel>", on_mousewheel)

        # --- WIDGET CONTENT ---
        
        # Title
        tk.Label(self.inner_frame, text="Karoo Farm", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(pady=(20, 10))

        # Status
        self.status_frame = tk.Frame(self.inner_frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        self.status_frame.pack(fill="x", padx=20, pady=10)
        
        self.loop_status = tk.Label(self.status_frame, text="Main Loop: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.loop_status.pack(pady=5)
        self.overlay_status = tk.Label(self.status_frame, text="Overlay: OFF", font=FONT_MAIN, bg=THEME_BG, fg="gray")
        self.overlay_status.pack(pady=5)

        # --- AUTO BUY SECTION ---
        self.create_section_label("Auto Purchase Settings")
        
        buy_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        buy_frame.pack(fill="x", padx=20)

        # Active Checkbox
        self.auto_purchase_var = tk.BooleanVar(value=False)
        self.create_toggle(buy_frame, "Active", self.auto_purchase_var)

        # Amount
        self.amount_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Amount to Buy:", self.amount_var)
        self.amount_var.trace_add('write', lambda *args: setattr(self, 'auto_purchase_amount', self.amount_var.get()))
        self.auto_purchase_amount = 10

        # Loops
        self.loops_var = tk.IntVar(value=10)
        self.create_input(buy_frame, "Loops per Buy:", self.loops_var)
        self.loops_var.trace_add('write', lambda *args: setattr(self, 'loops_per_purchase', self.loops_var.get()))
        self.loops_per_purchase = 10

        # Points
        tk.Label(buy_frame, text="Coordinate Setup:", font=FONT_BOLD, bg=THEME_BG, fg=THEME_TEXT).pack(anchor="w", pady=(10, 5))
        
        pt_frame = tk.Frame(buy_frame, bg=THEME_BG)
        pt_frame.pack(fill="x")
        
        labels = {
            1: "Pt 1: Yes / Confirm",
            2: "Pt 2: Input Box",
            3: "Pt 3: No / Close",
            4: "Pt 4: Ocean / Reset"
        }

        for i in range(1, 5):
            row = tk.Frame(pt_frame, bg=THEME_BG)
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text=labels[i], font=("Segoe UI", 9), bg=THEME_BG, fg="gray")
            lbl.pack(side="left")
            
            btn = tk.Button(row, text="Set", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 8, "bold"),
                            activebackground="white", activeforeground=THEME_ACCENT,
                            command=lambda x=i: self.capture_mouse_click(x), width=8, relief="flat")
            btn.pack(side="right")
            self.point_buttons[i] = btn

        # --- PD CONTROLLER ---
        self.create_section_label("PD Controller")
        pd_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        pd_frame.pack(fill="x", padx=20)

        self.kp_var = tk.DoubleVar(value=self.kp)
        self.create_input(pd_frame, "Kp (Proportional):", self.kp_var, is_float=True)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))

        self.kd_var = tk.DoubleVar(value=self.kd)
        self.create_input(pd_frame, "Kd (Derivative):", self.kd_var, is_float=True)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))

        # --- TIMING ---
        self.create_section_label("Timing")
        t_frame = tk.Frame(self.inner_frame, bg=THEME_BG)
        t_frame.pack(fill="x", padx=20)
        
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        self.create_input(t_frame, "Scan Timeout (s):", self.timeout_var, is_float=True)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))

        self.wait_var = tk.DoubleVar(value=self.wait_after_loss)
        self.create_input(t_frame, "Wait After Loss (s):", self.wait_var, is_float=True)
        self.wait_var.trace_add('write', lambda *args: setattr(self, 'wait_after_loss', self.wait_var.get()))

        # --- HOTKEYS ---
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
        # Center content
        center_frame = tk.Frame(self.page_afk, bg=THEME_BG) # Opaque background for text clarity? No let's try transparent-ish feel
        # Actually tk frames aren't transparent. We will rely on the bg image being dark.
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Transparent hack: We can't actually do it easily. 
        # We will just place labels directly on page_afk
        
        tk.Label(self.page_afk, text="AFK MODE", font=("Segoe UI", 30, "bold"), bg=THEME_BG, fg=THEME_ACCENT).place(relx=0.5, rely=0.2, anchor="center")
        
        tk.Label(self.page_afk, text="Total Loops Completed:", font=("Segoe UI", 12), bg=THEME_BG, fg="white").place(relx=0.5, rely=0.4, anchor="center")
        
        self.afk_count_label = tk.Label(self.page_afk, text="0", font=FONT_AFK, bg=THEME_BG, fg=THEME_ACCENT)
        self.afk_count_label.place(relx=0.5, rely=0.5, anchor="center")
        
        self.afk_hint_label = tk.Label(self.page_afk, text="Press F4 to return", font=("Segoe UI", 10, "italic"), bg=THEME_BG, fg="gray")
        self.afk_hint_label.place(relx=0.5, rely=0.8, anchor="center")

    # --- UI HELPER FUNCTIONS ---
    def create_section_label(self, text):
        f = tk.Frame(self.inner_frame, bg=THEME_BG)
        f.pack(fill="x", pady=(20, 5))
        tk.Label(f, text=text, font=("Segoe UI", 14, "bold"), bg=THEME_BG, fg=THEME_ACCENT).pack(side="left", padx=20)
        tk.Frame(f, bg=THEME_ACCENT, height=2).pack(side="left", fill="x", expand=True, padx=(10, 20), pady=(8, 0))

    def create_input(self, parent, label_text, variable, is_float=False):
        row = tk.Frame(parent, bg=THEME_BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label_text, bg=THEME_BG, fg="white", font=FONT_MAIN).pack(side="left")
        
        # Style the spinbox
        sb = tk.Spinbox(row, textvariable=variable, bg="#202020", fg=THEME_ACCENT, 
                        buttonbackground=THEME_ACCENT, relief="flat", width=10,
                        from_=0.0 if is_float else 0, to=1000000, 
                        increment=0.1 if is_float else 1)
        sb.pack(side="right")

    def create_toggle(self, parent, text, var):
        # Custom looking checkbox using Checkbutton
        cb = tk.Checkbutton(parent, text=text, variable=var, bg=THEME_BG, fg="white",
                            selectcolor="#202020", activebackground=THEME_BG, activeforeground=THEME_ACCENT,
                            font=FONT_BOLD)
        cb.pack(anchor="w", pady=5)

    def create_hotkey_row(self, parent, label, key_key):
        row = tk.Frame(parent, bg=THEME_BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, bg=THEME_BG, fg="gray").pack(side="left")
        
        btn = tk.Button(row, text="Rebind", bg="#202020", fg="white", relief="flat",
                        command=lambda: self.start_rebind(key_key), font=("Segoe UI", 8))
        btn.pack(side="right", padx=5)
        
        lbl = tk.Label(row, text=self.hotkeys[key_key].upper(), bg=THEME_BG, fg=THEME_ACCENT, font=FONT_BOLD)
        lbl.pack(side="right", padx=10)
        
        # Store reference to update later
        setattr(self, f"lbl_{key_key}", lbl)
        setattr(self, f"btn_{key_key}", btn)

    # --- CORE LOGIC ---

    def register_hotkeys(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys['toggle_loop'], self.toggle_main_loop)
            keyboard.add_hotkey(self.hotkeys['toggle_overlay'], self.toggle_overlay)
            keyboard.add_hotkey(self.hotkeys['exit'], self.exit_app)
            keyboard.add_hotkey(self.hotkeys['toggle_afk'], self.toggle_afk_mode)
        except Exception as e:
            print(f"Error registering hotkeys: {e}")

    def toggle_afk_mode(self):
        self.afk_mode_active = not self.afk_mode_active
        
        if self.afk_mode_active:
            # Switch to AFK page
            self.page_main.place_forget()
            self.page_afk.place(relwidth=1, relheight=1)
            # Update hint
            hk = self.hotkeys['toggle_afk'].upper()
            self.afk_hint_label.config(text=f"Press {hk} to return & reset")
        else:
            # Switch back to Main
            self.page_afk.place_forget()
            self.page_main.place(relwidth=1, relheight=1)
            # Reset counter
            self.total_loops_count = 0
            self.afk_count_label.config(text="0")

    def toggle_main_loop(self):
        new_state = not self.main_loop_active

        if new_state:
            # Checking points before start
            if self.auto_purchase_var.get():
                pts = self.point_coords
                missing = [i for i in range(1, 5) if not pts.get(i)]
                if missing:
                    self.status_msg.config(text=f"Missing Points: {missing}!", fg="red")
                    # Beep or something
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
        
        listener = pynput_mouse.Listener(on_click=_on_click)
        listener.start()

    def start_rebind(self, action):
        self.recording_hotkey = action
        self.status_msg.config(text=f"Press key for '{action}'...", fg=THEME_ACCENT)
        
        # Disable buttons visually
        getattr(self, f"btn_{action}").config(state="disabled", text="...")
        
        listener = pynput_keyboard.Listener(on_press=self.on_key_press)
        listener.start()

    def on_key_press(self, key):
        if self.recording_hotkey is None: return False
        try:
            if hasattr(key, 'name'): key_name = key.name
            elif hasattr(key, 'char'): key_name = key.char
            else: key_name = str(key).replace('Key.', '')
            
            old_key = self.hotkeys[self.recording_hotkey]
            try: keyboard.remove_hotkey(old_key)
            except: pass
            
            self.hotkeys[self.recording_hotkey] = key_name
            
            # Update UI
            lbl = getattr(self, f"lbl_{self.recording_hotkey}")
            btn = getattr(self, f"btn_{self.recording_hotkey}")
            
            self.root.after(0, lambda: lbl.config(text=key_name.upper()))
            self.root.after(0, lambda: btn.config(state="normal", text="Rebind"))
            self.root.after(0, lambda: self.status_msg.config(text="Rebind Successful", fg="#00ff00"))
            
            self.register_hotkeys()
            self.recording_hotkey = None
            return False
        except Exception as e:
            self.recording_hotkey = None
            return False

    # --- ACTION LOGIC ---

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
        print("Starting Auto Purchase...")
        pts = self.point_coords
        try:
            # 1. Press E
            keyboard.press_and_release('e')
            threading.Event().wait(self.purchase_delay_after_key)
            
            # 2. Click Pt 1 (Yes)
            self._click_at(pts[1])
            threading.Event().wait(self.purchase_click_delay)

            # 3. Click Pt 2 (Input)
            self._click_at(pts[2])
            threading.Event().wait(self.purchase_click_delay)

            # 4. Type Amount
            amount = self.amount_var.get()
            keyboard.write(str(amount))
            threading.Event().wait(self.purchase_after_type_delay)

            # 5. Click Pt 1 (Confirm)
            self._click_at(pts[1])
            threading.Event().wait(self.purchase_click_delay)

            # 6. Click Pt 3 (No - Close)
            self._click_at(pts[3])
            threading.Event().wait(self.purchase_click_delay)

            # 7. Click Pt 4 (Ocean - Reset)
            self._click_at(pts[4])
            threading.Event().wait(self.purchase_click_delay)
            
        except Exception as e:
            print(f"Purchase Error: {e}")

    def check_and_purchase(self):
        if self.auto_purchase_var.get():
            self.purchase_counter += 1
            needed = max(1, self.loops_per_purchase)
            print(f"Purchase Progress: {self.purchase_counter}/{needed}")
            
            if self.purchase_counter >= needed:
                self.perform_auto_purchase_sequence()
                self.purchase_counter = 0

    def cast_line(self):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        threading.Event().wait(1.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_clicking = False
        
        # Increment Total Loop Counter
        self.total_loops_count += 1
        # Update AFK UI safely
        if self.afk_mode_active:
            self.root.after(0, lambda: self.afk_count_label.config(text=str(self.total_loops_count)))

    # --- VISION LOOP ---

    def main_loop(self):
        print("Loop Started")
        target_color = (0x55, 0xaa, 0xff)
        dark_color = (0x19, 0x19, 0x19)
        white_color = (0xff, 0xff, 0xff)
        
        import time
        if self.camera is None:
            self.camera = dxcam.create(output_color="BGR")
        
        self.camera.start(target_fps=60, video_mode=True)
        
        try:
            if self.auto_purchase_var.get():
                self.perform_auto_purchase_sequence()
            
            self.cast_line()
            last_detection_time = time.time()
            was_detecting = False
            
            while self.main_loop_active:
                x = self.overlay_area['x']
                y = self.overlay_area['y']
                w = self.overlay_area['width']
                h = self.overlay_area['height']
                
                img = self.camera.get_latest_frame()
                if img is None: 
                    threading.Event().wait(0.01)
                    continue
                
                # Crop
                img = img[y:y+h, x:x+w]
                
                # --- LOGIC IDENTICAL TO PREVIOUS VERSION ---
                # 1. Find Blue Bar (Pt1 -> Pt2)
                # 2. Determine Height using Dark Color
                # 3. Find White bar position
                # 4. Find Dark Gap middle
                # 5. PD Control
                
                # (Simplified here for brevity, assuming original logic works well)
                # I will insert the exact logic block you had to ensure functionality remains.
                
                # 1. Find Point 1 (Blue)
                point1_x = None
                point1_y = None
                found_first = False
                
                # Optimized search: check every 2nd pixel to save CPU? No, keep accuracy.
                for row in range(h):
                    for col in range(w):
                        b, g, r = img[row, col, 0:3]
                        if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                            point1_x = x + col
                            point1_y = y + row
                            found_first = True
                            break
                    if found_first: break
                
                if not found_first:
                    # Timeout Logic
                    curr = time.time()
                    if was_detecting:
                        threading.Event().wait(self.wait_after_loss)
                        was_detecting = False
                        self.check_and_purchase()
                        self.cast_line()
                        last_detection_time = time.time()
                    elif curr - last_detection_time > self.scan_timeout:
                        self.check_and_purchase()
                        self.cast_line()
                        last_detection_time = time.time()
                    threading.Event().wait(0.05)
                    continue

                # 2. Find Point 2 (Blue right edge)
                point2_x = None
                row = point1_y - y
                for col in range(w - 1, -1, -1):
                    b, g, r = img[row, col, 0:3]
                    if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                        point2_x = x + col
                        break
                
                if point2_x is None: continue
                
                # 3. Find vertical bounds (Dark color)
                temp_x_off = point1_x - x
                temp_w = point2_x - point1_x + 1
                temp_img = img[:, temp_x_off:temp_x_off + temp_w]
                
                top_y = None
                for r_idx in range(h):
                    found = False
                    for c_idx in range(temp_w):
                        b, g, r = temp_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            top_y = y + r_idx
                            found = True
                            break
                    if found: break
                
                bottom_y = None
                for r_idx in range(h - 1, -1, -1):
                    found = False
                    for c_idx in range(temp_w):
                        b, g, r = temp_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            bottom_y = y + r_idx
                            found = True
                            break
                    if found: break
                    
                if top_y is None or bottom_y is None: continue
                
                real_h = bottom_y - top_y + 1
                real_img = img[(top_y-y):(top_y-y)+real_h, temp_x_off:temp_x_off+temp_w]
                
                # 4. Find White Bar
                white_y = None
                for r_idx in range(real_h):
                    for c_idx in range(temp_w):
                        b, g, r = real_img[r_idx, c_idx, 0:3]
                        if r == white_color[0] and g == white_color[1] and b == white_color[2]:
                            white_y = y + top_y + r_idx # Absolute Y
                            break # Found top of white
                    if white_y: break
                
                # 5. Find Dark Gap (The Target)
                # Scan specifically for the gap
                dark_sections = []
                curr_start = None
                gap_cnt = 0
                # heuristic: gaps can be large
                
                for r_idx in range(real_h):
                    has_dark = False
                    for c_idx in range(temp_w):
                        b, g, r = real_img[r_idx, c_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            has_dark = True
                            break
                    
                    if has_dark:
                        if curr_start is None: curr_start = r_idx
                        gap_cnt = 0
                    else:
                        if curr_start is not None:
                            gap_cnt += 1
                            if gap_cnt > 5: # Threshold
                                end = r_idx - gap_cnt
                                dark_sections.append((curr_start, end))
                                curr_start = None
                                gap_cnt = 0
                
                if curr_start is not None:
                    dark_sections.append((curr_start, real_h - 1))
                    
                if dark_sections and white_y is not None:
                    was_detecting = True
                    last_detection_time = time.time()
                    
                    # Largest section is usually the bar
                    largest = max(dark_sections, key=lambda s: s[1]-s[0])
                    mid_local = (largest[0] + largest[1]) // 2
                    mid_abs = top_y + mid_local
                    
                    # PD Logic
                    # Error: Distance between White Bar and Middle of Dark Bar
                    # white_y is absolute, mid_abs is absolute
                    # white_y is usually the TOP of the white bar.
                    # We want white bar to overlap middle.
                    
                    # Convert white_y to relative to real_area top for calculation consistency
                    rel_white = white_y - top_y
                    
                    error = mid_local - rel_white
                    norm_err = error / real_h
                    
                    derivative = norm_err - self.previous_error
                    self.previous_error = norm_err
                    
                    output = (self.kp * norm_err) + (self.kd * derivative)
                    
                    if output > 0:
                        if not self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            self.is_clicking = True
                    else:
                        if self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self.is_clicking = False
                            
                threading.Event().wait(0.01)

        except Exception as e:
            print(f"Main Loop Crash: {e}")
        finally:
            if self.camera: self.camera.stop()
            if self.is_clicking:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

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
        self.overlay_window.minsize(50, 50)
        
        geo = f"{self.overlay_area['width']}x{self.overlay_area['height']}+{self.overlay_area['x']}+{self.overlay_area['y']}"
        self.overlay_window.geometry(geo)
        
        # Frame with Orange Border
        frame = tk.Frame(self.overlay_window, bg="black-", highlightthickness=3, highlightbackground="black")
        frame.pack(fill="both", expand=True)
        # Inner transparent-ish part (using a specific color key isn't easy in tkinter without full transparency)
        # We'll just make the inside hollow-ish by setting a different color and hoping alpha handles it
        inner = tk.Frame(frame, bg=THEME_ACCENT)
        inner.pack(fill="both", expand=True, padx=3, pady=3)

        self.overlay_drag_data = {"x": 0, "y": 0, "edge": None}
        
        # Bindings
        for w in [self.overlay_window, frame, inner]:
            w.bind("<ButtonPress-1>", self.start_overlay_drag)
            w.bind("<B1-Motion>", self.overlay_motion)
            w.bind("<Motion>", self.update_cursor)
            
        self.overlay_window.bind("<Configure>", self.on_overlay_configure)

    def get_resize_edge(self, x, y, width, height):
        edge_size = 15
        on_left = x < edge_size
        on_right = x > width - edge_size
        on_top = y < edge_size
        on_bottom = y > height - edge_size
        
        if on_top and on_left: return "nw"
        if on_top and on_right: return "ne"
        if on_bottom and on_left: return "sw"
        if on_bottom and on_right: return "se"
        if on_left: return "w"
        if on_right: return "e"
        if on_top: return "n"
        if on_bottom: return "s"
        return None

    def update_cursor(self, event):
        w = self.overlay_window.winfo_width()
        h = self.overlay_window.winfo_height()
        edge = self.get_resize_edge(event.x, event.y, w, h)
        
        cursors = {
            "nw": "size_nw_se", "ne": "size_ne_sw",
            "sw": "size_ne_sw", "se": "size_nw_se",
            "n": "size_ns", "s": "size_ns",
            "w": "size_we", "e": "size_we"
        }
        self.overlay_window.config(cursor=cursors.get(edge, "arrow"))

    def start_overlay_drag(self, event):
        self.overlay_drag_data["x"] = event.x
        self.overlay_drag_data["y"] = event.y
        w = self.overlay_window.winfo_width()
        h = self.overlay_window.winfo_height()
        self.overlay_drag_data["edge"] = self.get_resize_edge(event.x, event.y, w, h)
        self.overlay_drag_data["start_geo"] = (self.overlay_window.winfo_x(), self.overlay_window.winfo_y(), w, h)

    def overlay_motion(self, event):
        edge = self.overlay_drag_data["edge"]
        sx, sy, sw, sh = self.overlay_drag_data["start_geo"]
        dx = event.x - self.overlay_drag_data["x"]
        dy = event.y - self.overlay_drag_data["y"]
        
        if edge is None:
            # Move
            nx = self.overlay_window.winfo_x() + dx
            ny = self.overlay_window.winfo_y() + dy
            self.overlay_window.geometry(f"+{nx}+{ny}")
        else:
            # Resize
            nx, ny, nw, nh = sx, sy, sw, sh
            
            if 'e' in edge: nw = max(50, sw + dx)
            if 'w' in edge: 
                nw = max(50, sw - dx)
                nx = sx + dx
            if 's' in edge: nh = max(50, sh + dy)
            if 'n' in edge: 
                nh = max(50, sh - dy)
                ny = sy + dy
                
            self.overlay_window.geometry(f"{nw}x{nh}+{nx}+{ny}")

    def on_overlay_configure(self, event=None):
        if self.overlay_window:
            self.overlay_area = {
                'x': self.overlay_window.winfo_x(),
                'y': self.overlay_window.winfo_y(),
                'width': self.overlay_window.winfo_width(),
                'height': self.overlay_window.winfo_height()
            }

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
