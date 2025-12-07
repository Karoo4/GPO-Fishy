import tkinter as tk
from tkinter import ttk
import threading
import keyboard
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
import sys
import ctypes
import dxcam
import win32api
import win32con
from PIL import Image, ImageTk, ImageEnhance
import requests
from io import BytesIO
import time

# --- CONFIGURATION ---
THEME_BG = "#0b0b0b"
THEME_ACCENT = "#ff8d00" # Orange
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")

VIVI_URL = "https://static0.srcdn.com/wordpress/wp-content/uploads/2023/10/vivi.jpg?q=49&fit=crop&w=825&dpr=2"
DUCK_URL = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.ytimg.com%2Fvi%2FX8YUuU7OpOA%2Fmaxresdefault.jpg&f=1&nofb=1&ipt=6d669298669fff2e4f438b54453c1f59c1655ca19fa2407ea1c42e471a4d7ab6"

class KarooFarm:
    def __init__(self, root):
        self.root = root
        self.root.title("Karoo Farm")
        self.root.geometry("450x850")
        self.root.configure(bg=THEME_BG)
        self.root.attributes('-topmost', True)

        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass

        # State
        self.main_loop_active = False
        self.overlay_active = False
        self.afk_mode_active = False
        self.overlay_window = None
        self.is_clicking = False
        self.recording_hotkey = None
        
        # Overlay Config
        self.border_size = 10     # Thick border for resizing
        self.title_size = 30      # Thick bar for dragging
        
        # Logic Config
        self.purchase_counter = 0     
        self.total_loops_count = 0    
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0
        self.scan_timeout = 15.0
        self.wait_after_loss = 1.0
        
        # Auto Buy Timing
        self.purchase_delay_after_key = 2.0
        self.purchase_click_delay = 0.8
        self.purchase_after_type_delay = 0.8
        
        # Items
        self.check_items = True

        self.dpi_scale = self.get_dpi_scale()
        
        # Initial Overlay Size
        self.overlay_area = {
            'x': 100, 'y': 100, 
            'width': int(180 * self.dpi_scale), 
            'height': int(500 * self.dpi_scale)
        }

        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3', 'toggle_afk': 'f4'}
        self.camera = None
        self.point_coords = {1: None, 2: None, 3: None, 4: None, 5: None}
        self.point_buttons = {}
        self.point_labels = {} 

        # Images
        self.bg_main = self.load_processed_image(VIVI_URL, 0.3)
        self.bg_afk = self.load_processed_image(DUCK_URL, 0.4)

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
        except: return None

    # --- UI ---
    def setup_ui(self):
        self.container = tk.Frame(self.root, bg=THEME_BG)
        self.container.pack(fill="both", expand=True)

        # Main Page
        self.page_main = tk.Frame(self.container, bg=THEME_BG)
        self.page_main.place(relwidth=1, relheight=1)
        if self.bg_main: tk.Label(self.page_main, image=self.bg_main, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        self.create_main_widgets()

        # AFK Page
        self.page_afk = tk.Frame(self.container, bg=THEME_BG)
        if self.bg_afk: tk.Label(self.page_afk, image=self.bg_afk, bg=THEME_BG).place(x=0, y=0, relwidth=1, relheight=1)
        self.create_afk_widgets()

    def create_main_widgets(self):
        canvas = tk.Canvas(self.page_main, bg=THEME_BG, highlightthickness=0)
        sb = ttk.Scrollbar(self.page_main, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=sb.set)
        
        frame = tk.Frame(canvas, bg=THEME_BG)
        canvas.create_window((0, 0), window=frame, anchor="nw", width=430)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        tk.Label(frame, text="Karoo Farm", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(pady=(20, 10))

        # Status
        st = tk.Frame(frame, bg=THEME_BG, highlightbackground=THEME_ACCENT, highlightthickness=1)
        st.pack(fill="x", padx=20, pady=10)
        self.loop_status = tk.Label(st, text="Main Loop: OFF", font=FONT_BOLD, bg=THEME_BG, fg="red")
        self.loop_status.pack(pady=5)
        self.overlay_status = tk.Label(st, text="Overlay: OFF", font=FONT_MAIN, bg=THEME_BG, fg="gray")
        self.overlay_status.pack(pady=5)

        # Auto Buy
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

        # Inventory
        self.create_section(frame, "Inventory / Item Check")
        self.item_check_var = tk.BooleanVar(value=True)
        self.create_toggle(frame, "Enable Item Cleaning", self.item_check_var)
        self.create_point_row(frame, 5, "Pt 5 (Slot 3 Check)")

        # Settings
        self.create_section(frame, "Settings")
        self.kp_var = tk.DoubleVar(value=self.kp)
        self.create_input(frame, "Kp:", self.kp_var, True)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        self.kd_var = tk.DoubleVar(value=self.kd)
        self.create_input(frame, "Kd:", self.kd_var, True)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        self.create_input(frame, "Timeout:", self.timeout_var, True)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))

        # Hotkeys
        self.create_section(frame, "Hotkeys")
        for k, label in [('toggle_loop', 'Loop'), ('toggle_overlay', 'Overlay'), ('toggle_afk', 'AFK'), ('exit', 'Exit')]:
            self.create_hotkey_row(frame, label, k)

        self.status_msg = tk.Label(frame, text="", bg=THEME_BG, fg=THEME_ACCENT)
        self.status_msg.pack(pady=20)

    def create_afk_widgets(self):
        tk.Label(self.page_afk, text="AFK MODE", font=("Segoe UI", 30, "bold"), bg=THEME_BG, fg=THEME_ACCENT).place(relx=0.5, rely=0.2, anchor="center")
        tk.Label(self.page_afk, text="Total Loops:", font=("Segoe UI", 12), bg=THEME_BG, fg="white").place(relx=0.5, rely=0.4, anchor="center")
        self.afk_count_label = tk.Label(self.page_afk, text="0", font=FONT_AFK, bg=THEME_BG, fg=THEME_ACCENT)
        self.afk_count_label.place(relx=0.5, rely=0.5, anchor="center")
        self.afk_hint_label = tk.Label(self.page_afk, text="Press F4 to return", font=("Segoe UI", 10, "italic"), bg=THEME_BG, fg="gray")
        self.afk_hint_label.place(relx=0.5, rely=0.8, anchor="center")

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

    # --- LOGIC ---
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
            self.page_afk.place(relwidth=1, relheight=1)
            self.afk_hint_label.config(text=f"Press {self.hotkeys['toggle_afk'].upper()} to return")
        else:
            self.page_afk.place_forget()
            self.page_main.place(relwidth=1, relheight=1)
            self.total_loops_count = 0
            self.afk_count_label.config(text="0")

    def toggle_loop(self):
        self.main_loop_active = not self.main_loop_active
        if self.main_loop_active:
            req = []
            if self.auto_purchase_var.get(): req.extend([1,2,4])
            if self.item_check_var.get(): req.append(5)
            if any(not self.point_coords.get(p) for p in req):
                self.main_loop_active = False
                self.status_msg.config(text="Missing Points!", fg="red")
                return
            
            self.purchase_counter = 0
            self.loop_status.config(text="Main Loop: ON", fg="#00ff00")
            threading.Thread(target=self.run_loop, daemon=True).start()
        else:
            self.loop_status.config(text="Main Loop: OFF", fg="red")
            self.is_clicking = False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

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

    def click(self, pt):
        if not pt: return
        try:
            x, y = int(pt[0]), int(pt[1])
            win32api.SetCursorPos((x, y))
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except: pass

    def do_purchase(self):
        try:
            keyboard.press_and_release('e')
            time.sleep(self.purchase_delay_after_key)
            self.click(self.point_coords[1])
            time.sleep(self.purchase_click_delay)
            self.click(self.point_coords[2])
            time.sleep(self.purchase_click_delay)
            keyboard.write(str(self.amount_var.get()))
            time.sleep(self.purchase_after_type_delay)
            self.click(self.point_coords[1])
            time.sleep(self.purchase_click_delay)
            self.click(self.point_coords[2]) # Seq requested: Input again?
            time.sleep(self.purchase_click_delay)
            self.click(self.point_coords[4])
            time.sleep(self.purchase_click_delay)
        except: pass

    def do_item_check(self):
        p5 = self.point_coords.get(5)
        if not p5: return
        try:
            keyboard.press_and_release('3')
            time.sleep(0.3)
            self.click(p5)
            time.sleep(0.5)
            keyboard.press_and_release('backspace')
            time.sleep(0.3)
            keyboard.press_and_release('2')
            time.sleep(0.5)
        except: pass

    def run_loop(self):
        if self.camera is None: self.camera = dxcam.create(output_color="BGR")
        self.camera.start(target_fps=60, video_mode=True)
        try:
            if self.auto_purchase_var.get(): self.do_purchase()
            self.click(self.point_coords[4])
            self.cast()
            
            last_det = time.time()
            detecting = False
            
            while self.main_loop_active:
                # Get overlay geometry
                ox, oy = self.overlay_area['x'], self.overlay_area['y']
                ow, oh = self.overlay_area['width'], self.overlay_area['height']
                
                # CRITICAL: Offset capture area to ignore the overlay borders
                # The overlay has a 30px top bar and 10px side borders
                # We crop INSIDE that
                
                scan_x = ox + self.border_size
                scan_y = oy + self.title_size
                scan_w = ow - (self.border_size * 2)
                scan_h = oh - self.title_size - self.border_size
                
                if scan_w < 10 or scan_h < 10:
                    time.sleep(0.1); continue
                
                img = self.camera.get_latest_frame()
                if img is None: time.sleep(0.01); continue
                
                # Crop
                img = img[scan_y:scan_y+scan_h, scan_x:scan_x+scan_w]
                
                # Vision Logic (Blue->Dark->White->Gap)
                target = (0x55, 0xaa, 0xff)
                
                # Find Blue
                p1x, p1y, found = None, None, False
                for r in range(scan_h):
                    for c in range(scan_w):
                        b,g,r_ = img[r,c]
                        if r_==target[0] and g==target[1] and b==target[2]:
                            p1x, p1y, found = c, r, True; break
                    if found: break
                
                if not found:
                    if detecting:
                        time.sleep(self.wait_after_loss)
                        detecting = False
                        if self.auto_purchase_var.get():
                            self.purchase_counter += 1
                            if self.purchase_counter >= self.loops_var.get():
                                self.do_purchase(); self.purchase_counter = 0
                        if self.item_check_var.get(): self.do_item_check()
                        self.cast(); last_det = time.time()
                    elif time.time() - last_det > self.timeout_var.get():
                        if self.item_check_var.get(): self.do_item_check()
                        self.cast(); last_det = time.time()
                    time.sleep(0.05); continue
                
                # Found Blue -> Detecting State
                detecting = True; last_det = time.time()
                
                # Find Width
                p2x = None
                for c in range(scan_w-1, -1, -1):
                    b,g,r_ = img[p1y, c]
                    if r_==target[0] and g==target[1] and b==target[2]:
                        p2x = c; break
                if not p2x: continue
                
                # Crop to Bar Width
                bar = img[:, p1x:p2x+1]
                bh, bw = bar.shape[0], bar.shape[1]
                
                # Find Vertical Bounds (Dark)
                dark = (0x19, 0x19, 0x19)
                ty, by = None, None
                for r in range(bh):
                    for c in range(bw):
                        b,g,r_ = bar[r,c]
                        if r_==dark[0] and g==dark[1] and b==dark[2]: ty=r; break
                    if ty: break
                for r in range(bh-1, -1, -1):
                    for c in range(bw):
                        b,g,r_ = bar[r,c]
                        if r_==dark[0] and g==dark[1] and b==dark[2]: by=r; break
                    if by: break
                if not ty or not by: continue
                
                # Crop to Bar Height
                real = bar[ty:by+1, :]
                rh = real.shape[0]
                
                # Find White
                white = (0xff, 0xff, 0xff)
                wy = None
                for r in range(rh):
                    for c in range(bw):
                        b,g,r_ = real[r,c]
                        if r_==white[0] and g==white[1] and b==white[2]: wy=r; break
                    if wy: break
                
                # Find Gaps
                gaps = []
                st, gc = None, 0
                for r in range(rh):
                    is_d = False
                    for c in range(bw):
                        b,g,r_ = real[r,c]
                        if r_==dark[0] and g==dark[1] and b==dark[2]: is_d=True; break
                    if is_d:
                        if st is None: st = r
                        gc = 0
                    else:
                        if st is not None:
                            gc += 1
                            if gc > 5:
                                gaps.append((st, r-gc))
                                st, gc = None, 0
                if st: gaps.append((st, rh-1))
                
                if gaps and wy is not None:
                    # PD Control
                    best = max(gaps, key=lambda x: x[1]-x[0])
                    mid = (best[0] + best[1]) // 2
                    
                    err = mid - wy
                    n_err = err / rh
                    deriv = n_err - self.previous_error
                    self.previous_error = n_err
                    
                    out = (self.kp_var.get() * n_err) + (self.kd_var.get() * deriv)
                    
                    if out > 0 and not self.is_clicking:
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        self.is_clicking = True
                    elif out <= 0 and self.is_clicking:
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        self.is_clicking = False
                
                time.sleep(0.01)

        except Exception as e: print(e)
        finally:
            self.camera.stop()
            if self.is_clicking: win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def cast(self):
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
        self.overlay_window.attributes('-topmost', True)
        self.overlay_window.attributes('-alpha', 0.8) # Slight see through
        self.overlay_window.wm_attributes("-transparentcolor", "magenta") # Magic color
        
        self.overlay_window.geometry(f"{self.overlay_area['width']}x{self.overlay_area['height']}+{self.overlay_area['x']}+{self.overlay_area['y']}")
        
        # Main container with Magenta background (Transparent)
        # We draw frames AROUND the center to create the "Hollow" look
        
        bg = tk.Frame(self.overlay_window, bg="magenta")
        bg.pack(fill="both", expand=True)
        
        # Title Bar (Top)
        bar = tk.Frame(bg, bg=THEME_ACCENT, height=self.title_size, cursor="fleur")
        bar.pack(side="top", fill="x")
        tk.Label(bar, text="DRAG HERE", bg=THEME_ACCENT, fg="black", font=("Segoe UI", 9, "bold")).pack(expand=True)
        
        # Bottom Border
        bot = tk.Frame(bg, bg=THEME_ACCENT, height=self.border_size, cursor="sb_v_double_arrow")
        bot.pack(side="bottom", fill="x")
        
        # Left Border
        left = tk.Frame(bg, bg=THEME_ACCENT, width=self.border_size, cursor="sb_h_double_arrow")
        left.pack(side="left", fill="y")
        
        # Right Border
        right = tk.Frame(bg, bg=THEME_ACCENT, width=self.border_size, cursor="sb_h_double_arrow")
        right.pack(side="right", fill="y")

        # Bindings
        self.drag_data = {"x": 0, "y": 0}
        
        # Move
        bar.bind("<ButtonPress-1>", self.start_move)
        bar.bind("<B1-Motion>", self.do_move)
        
        # Resize
        right.bind("<ButtonPress-1>", self.start_resize)
        right.bind("<B1-Motion>", lambda e: self.do_resize(e, "x"))
        bot.bind("<ButtonPress-1>", self.start_resize)
        bot.bind("<B1-Motion>", lambda e: self.do_resize(e, "y"))
        
        # Corners (using the intersection of frames via careful binding or visual corners)
        # Simplified: Right border handles Width, Bottom handles Height.
        
        self.overlay_window.bind("<Configure>", self.save_geo)

    def start_move(self, e):
        self.drag_data = {"x": e.x_root, "y": e.y_root, "wx": self.overlay_window.winfo_x(), "wy": self.overlay_window.winfo_y()}

    def do_move(self, e):
        dx = e.x_root - self.drag_data["x"]
        dy = e.y_root - self.drag_data["y"]
        self.overlay_window.geometry(f"+{self.drag_data['wx']+dx}+{self.drag_data['wy']+dy}")

    def start_resize(self, e):
        self.drag_data = {"x": e.x_root, "y": e.y_root, "w": self.overlay_window.winfo_width(), "h": self.overlay_window.winfo_height()}

    def do_resize(self, e, axis):
        dx = e.x_root - self.drag_data["x"]
        dy = e.y_root - self.drag_data["y"]
        w, h = self.drag_data["w"], self.drag_data["h"]
        if axis == "x": w += dx
        if axis == "y": h += dy
        self.overlay_window.geometry(f"{max(50, w)}x{max(50, h)}")

    def save_geo(self, e):
        if self.overlay_window:
            self.overlay_area = {'x': self.overlay_window.winfo_x(), 'y': self.overlay_window.winfo_y(), 
                                 'width': self.overlay_window.winfo_width(), 'height': self.overlay_window.winfo_height()}

    def destroy_overlay(self):
        if self.overlay_window: self.overlay_window.destroy(); self.overlay_window = None

    def exit_app(self):
        self.main_loop_active = False
        self.destroy_overlay()
        try: keyboard.unhook_all()
        except: pass
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = KarooFarm(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()
