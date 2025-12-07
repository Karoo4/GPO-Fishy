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

# --- 1. FORCE ADMIN (Required for Clicking) ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- CONFIGURATION ---
THEME_BG = "#0b0b0b"
THEME_ACCENT = "#ff8d00" # Orange
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_AFK = ("Segoe UI", 48, "bold")

# IMAGE URLS
VIVI_URL = "https://static0.srcdn.com/wordpress/wp-content/uploads/2023/10/vivi.jpg?q=49&fit=crop&w=825&dpr=2"
DUCK_URL = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.ytimg.com%2Fvi%2FX8YUuU7OpOA%2Fmaxresdefault.jpg&f=1&nofb=1&ipt=6d669298669fff2e4f438b54453c1f59c1655ca19fa2407ea1c42e471a4d7ab6"
TITLE_LOGO_URL = "https://image2url.com/images/1765149562249-ff56b103-b5ea-4402-a896-0ed38202b804.png"

class KarooFarm:
    def __init__(self, root):
        self.root = root
        self.root.title("Karoo Fish")
        self.root.geometry("450x900")
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
        
        # --- FLAGS ---
        self.is_performing_action = False # Locks detection while buying/storing/baiting
        self.last_cast_time = 0.0
        
        # Overlay Logic State
        self.resize_threshold = 10
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
        self.start_x = 0
        self.start_y = 0
        self.win_start_x = 0
        self.win_start_y = 0
        self.win_start_w = 0
        self.win_start_h = 0
        
        # Overlay Config
        self.border_size = 5      
        self.title_size = 0       
        
        # Logic Config
        self.purchase_counter = 0     
        self.total_loops_count = 0    
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0
        self.scan_timeout = 15.0
        self.wait_after_loss = 1.0
        
        # --- DELAYS ---
        self.purchase_delay_after_key = 2.0   
        self.purchase_click_delay = 0.8       
        self.purchase_after_type_delay = 0.8
        self.clean_step_delay = 1.5           
        
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
        
        # Points
        self.point_coords = {1: None, 2: None, 3: None, 4: None, 5: None, 6: None}
        self.point_labels = {} 

        # Images
        self.bg_main = self.load_processed_image(VIVI_URL, 0.3)
        self.bg_afk = self.load_processed_image(DUCK_URL, 0.4)
        self.img_title = self.load_title_image(TITLE_LOGO_URL)

        self.setup_ui()
        self.register_hotkeys()

    def get_dpi_scale(self):
        try: return self.root.winfo_fpixels('1i') / 96.0
        except: return 1.0

    def load_processed_image(self, url, darkness=0.5):
        # Loads background wallpapers
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            img = img.resize((500, 950), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(ImageEnhance.Brightness(img).enhance(darkness))
        except: return None

    def load_title_image(self, url):
        # Loads the Logo resizing it to fit width ~300px
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

    # --- UI ---
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
        canvas = tk.Canvas(self.page_main, bg=THEME_BG, highlightthickness=0)
        sb = ttk.Scrollbar(self.page_main, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=sb.set)
        
        frame = tk.Frame(canvas, bg=THEME_BG)
        canvas.create_window((0, 0), window=frame, anchor="nw", width=430)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # --- LOGO SECTION ---
        if self.img_title:
            tk.Label(frame, image=self.img_title, bg=THEME_BG).pack(pady=(20, 10))
        else:
            tk.Label(frame, text="Karoo Fish", font=FONT_TITLE, bg=THEME_BG, fg=THEME_ACCENT).pack(pady=(20, 10))

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

        # Auto Store
        self.create_section(frame, "Auto Store Fruit")
        self.item_check_var = tk.BooleanVar(value=True)
        self.create_toggle(frame, "Enable Auto Store", self.item_check_var)
        self.create_point_row(frame, 5, "Pt 5 (Store Button)")

        # Auto Bait
        self.create_section(frame, "Auto Bait")
        self.auto_bait_var = tk.BooleanVar(value=False)
        self.create_toggle(frame, "Enable Auto Bait", self.auto_bait_var)
        self.create_point_row(frame, 6, "Pt 6 (Bait Location)")

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
            # Check requirements
            req = []
            if self.auto_purchase_var.get(): req.extend([1,2,4])
            if self.item_check_var.get(): req.append(5)
            if self.auto_bait_var.get(): req.append(6) # Require Bait Point
            
            if any(not self.point_coords.get(p) for p in req):
                self.main_loop_active = False
                self.status_msg.config(text="Missing Points!", fg="red")
                return
            
            self.purchase_counter = 0
            self.loop_status.config(text="Main Loop: ON", fg="#00ff00")
            
            # HIDE OVERLAY SO BOT CAN SEE
            if self.overlay_window:
                self.overlay_window.withdraw()
                
            threading.Thread(target=self.run_loop, daemon=True).start()
        else:
            self.loop_status.config(text="Main Loop: OFF", fg="red")
            self.is_clicking = False
            self.is_performing_action = False
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            
            # SHOW OVERLAY AGAIN
            if self.overlay_window:
                self.overlay_window.deiconify()

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

    # --- MOUSE HELPERS ---
    def move_to(self, pt):
        """Moves the mouse to coordinates WITHOUT clicking."""
        if not pt: return
        try:
            x, y = int(pt[0]), int(pt[1])
            win32api.SetCursorPos((x, y))
            time.sleep(0.02)
            # Force Relative Move to wake up game camera/cursor logic
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
            time.sleep(0.05)
        except Exception: pass

    def click(self, pt, debug_name="Target", hold_time=0.1):
        if not pt: 
            print(f"Skipping {debug_name} - No Coords")
            return
        try:
            x, y = int(pt[0]), int(pt[1])
            print(f"Clicking: {debug_name} at {x},{y}")
            # 1. Move
            win32api.SetCursorPos((x, y))
            time.sleep(0.02)
            # 2. Force Relative Move
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
            time.sleep(0.05)
            # 3. Down
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            # 4. Hold
            time.sleep(hold_time) 
            # 5. Up
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            # 6. Recovery
            time.sleep(0.05)
        except Exception as e: print(f"Click Error on {debug_name}: {e}")

    # --- ACTIONS ---

    def perform_auto_purchase_sequence(self):
        try:
            print("--- START AUTO BUY ---")
            self.is_performing_action = True # BLOCK CASTING
            
            if not all([self.point_coords[1], self.point_coords[2], self.point_coords[4]]):
                print("Missing coords for purchase")
                return

            print("Pressing E to open shop...")
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
            
            # JUST MOVE to Ocean, don't click yet.
            self.move_to(self.point_coords[4])
            time.sleep(self.purchase_click_delay)
            
            print("--- END AUTO BUY ---")
            
        except Exception as e: print(f"Purchase Error: {e}")
        finally:
            self.is_performing_action = False # UNBLOCK CASTING

    def perform_store_fruit(self):
        p5 = self.point_coords.get(5)
        if not p5: return
        
        # User defined check coordinate
        chk_x, chk_y = 1262, 156

        def check_red_pixel():
            img = self.camera.get_latest_frame()
            if img is None: return False
            if chk_y >= img.shape[0] or chk_x >= img.shape[1]: return False
            
            b, g, r = img[chk_y, chk_x] # BGR format
            match_r = r > 230
            match_g = 70 < g < 130
            match_b = 70 < b < 130
            return match_r and match_g and match_b

        try:
            print("--- AUTO STORE SEQUENCE ---")
            self.is_performing_action = True # BLOCK CASTING

            # 1. Equip potential fruit
            keyboard.press_and_release('3')
            time.sleep(self.clean_step_delay)

            # 2. Click Store Button
            self.click(p5, "Pt 5 (Store Fruit)")
            time.sleep(self.clean_step_delay) # Wait for text to appear

            # 3. Check specific pixel for #ff6666
            if check_red_pixel():
                print("Duplicate Fruit Detected (#ff6666 found). Deleting...")
                keyboard.press_and_release('backspace')
                time.sleep(self.clean_step_delay)
            else:
                print("Fruit Stored (or Empty/No Warning).")

            # 4. RESET EQUIPMENT (CRITICAL FIX FOR ROD)
            # Switch to '1' first (Combat/Fist) to clear hands
            keyboard.press_and_release('1')
            time.sleep(self.clean_step_delay)
            
            # Switch to '2' (Rod).
            keyboard.press_and_release('2')
            time.sleep(self.clean_step_delay)
            
            # 5. Reset mouse to Ocean (Pt 4) WITHOUT CLICKING
            self.move_to(self.point_coords[4])
            time.sleep(self.clean_step_delay)
            
        except Exception as e: 
            print(f"Store Error: {e}")
            keyboard.press_and_release('1')
            time.sleep(0.5)
            keyboard.press_and_release('2')
        finally:
            self.is_performing_action = False # UNBLOCK CASTING

    def perform_bait_select(self):
        if not self.auto_bait_var.get(): return
        
        p6 = self.point_coords.get(6)
        if not p6: return

        try:
            print("--- AUTO BAIT SELECT ---")
            self.is_performing_action = True # Block casting
            
            # 1. Click the Bait Location
            self.click(p6, "Pt 6 (Bait Select)")
            time.sleep(0.5) 
            
            # 2. Move Cursor back to Ocean (Pt 4)
            self.move_to(self.point_coords[4])
            time.sleep(0.2)
            
            print("--- BAIT SELECTED ---")
        except Exception as e:
            print(f"Bait Error: {e}")
        finally:
            self.is_performing_action = False # Unblock

    def cast(self):
        if self.is_performing_action: return # Double check
        
        # Cast uses a long hold (1.0s)
        self.click(self.point_coords[4], "Cast (Long)", hold_time=1.0)
        self.is_clicking = False
        self.total_loops_count += 1
        
        # --- CRITICAL UPDATE: Update Last Cast Time ---
        self.last_cast_time = time.time()
        
        if self.afk_mode_active: self.root.after(0, lambda: self.afk_count_label.config(text=str(self.total_loops_count)))
        
        self.previous_error = 0
        time.sleep(0.5)

    def run_loop(self):
        print("Main Loop started (Using Original Detection + SAFETY LOCK)")
        
        target_color = (0x55, 0xaa, 0xff)  # RGB
        dark_color = (0x19, 0x19, 0x19)
        white_color = (0xff, 0xff, 0xff)

        if self.camera is None:
            self.camera = dxcam.create(output_color="BGR")
        self.camera.start(target_fps=60, video_mode=True)

        try:
            # Initial Sequence
            if self.auto_purchase_var.get(): self.perform_auto_purchase_sequence()
            self.cast()
            
            last_detection_time = time.time()
            was_detecting = False

            while self.main_loop_active:
                # --- INTERFERENCE CHECK ---
                if self.is_performing_action:
                    time.sleep(0.1)
                    continue

                x, y = self.overlay_area['x'], self.overlay_area['y']
                width, height = self.overlay_area['width'], self.overlay_area['height']

                img = self.camera.get_latest_frame()
                if img is None:
                    time.sleep(0.01)
                    continue

                img = img[y:y+height, x:x+width]

                # 1. Find Point 1 (Left Blue Edge)
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
                        
                        # --- POST-GAME LOGIC ---
                        
                        # 1. Purchase
                        if self.auto_purchase_var.get():
                            self.purchase_counter += 1
                            if self.purchase_counter >= self.loops_var.get():
                                self.perform_auto_purchase_sequence()
                                self.purchase_counter = 0
                        
                        # 2. Store Fruit
                        if self.item_check_var.get(): 
                            self.perform_store_fruit()
                            
                        # 3. Auto Bait
                        if self.auto_bait_var.get():
                            self.perform_bait_select()
                        
                        # 4. Final Cast
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

                # 2. Find Point 2 (Right Blue Edge)
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

                # 3. Define Real Area
                temp_area_x = point1_x
                temp_area_width = point2_x - point1_x + 1
                temp_x_offset = temp_area_x - x
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

                # 4. Check White Target
                real_height = bottom_y - top_y + 1
                real_x_offset = temp_x_offset
                real_y_offset = top_y - y
                real_img = img[real_y_offset:real_y_offset+real_height, real_x_offset:real_x_offset+temp_area_width]
                
                white_top_y = None
                for r_idx in range(real_height):
                    for c_idx in range(temp_area_width):
                        b, g, r = real_img[r_idx, c_idx, 0:3]
                        if r == white_color[0] and g == white_color[1] and b == white_color[2]:
                            white_top_y = top_y + r_idx
                            break
                    if white_top_y is not None: break

                if white_top_y is None: continue

                # 5. FIND THE SLIDER
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

                # --- 6. LOGIC & SAFETY LOCK ---
                if dark_sections and white_top_y is not None:
                    was_detecting = True
                    last_detection_time = time.time()
                    
                    largest_section = max(dark_sections, key=lambda s: s['size'])
                    
                    raw_error = largest_section['middle'] - white_top_y
                    normalized_error = raw_error / real_height if real_height > 0 else raw_error
                    
                    derivative = normalized_error - self.previous_error
                    self.previous_error = normalized_error
                    
                    pd_output = (self.kp_var.get() * normalized_error) + (self.kd_var.get() * derivative)
                    
                    # === CRITICAL SAFETY CHECK ===
                    time_since_cast = time.time() - self.last_cast_time
                    
                    if pd_output > 0:
                        if time_since_cast > 3.0: # ONLY CLICK IF SAFE
                            if not self.is_clicking:
                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                self.is_clicking = True
                    else:
                        if self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self.is_clicking = False
                
                time.sleep(0.01)

        except Exception as e:
            print(f"Error in run_loop: {e}")
        finally:
            self.camera.stop()
            if self.is_clicking:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_clicking = False

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
        
        # Filled Transparent Box (30% Opacity)
        self.overlay_window.attributes('-alpha', 0.3) 
        
        self.overlay_window.geometry(f"{self.overlay_area['width']}x{self.overlay_area['height']}+{self.overlay_area['x']}+{self.overlay_area['y']}")
        
        # Filled with Theme Accent
        self.overlay_window.configure(bg=THEME_ACCENT)

        # Create canvas for border (and interaction)
        self.canvas = tk.Canvas(self.overlay_window, bg=THEME_ACCENT, 
                                highlightthickness=self.border_size, 
                                highlightbackground=THEME_ACCENT)
        self.canvas.pack(fill='both', expand=True)

        # Bind events
        self.canvas.bind('<Button-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.canvas.bind('<Motion>', self.on_mouse_move)
        
        self.resizing = False
        self.dragging = False
        self.resize_edge = None
        self.start_x = 0
        self.start_y = 0

    def on_mouse_move(self, event):
        x, y = event.x, event.y
        w = self.overlay_window.winfo_width()
        h = self.overlay_window.winfo_height()
        
        edge = 15
        left = x < edge
        right = x > w - edge
        top = y < edge
        bottom = y > h - edge
        
        if top and left: self.canvas.config(cursor='top_left_corner')
        elif top and right: self.canvas.config(cursor='top_right_corner')
        elif bottom and left: self.canvas.config(cursor='bottom_left_corner')
        elif bottom and right: self.canvas.config(cursor='bottom_right_corner')
        elif left: self.canvas.config(cursor='sb_h_double_arrow')
        elif right: self.canvas.config(cursor='sb_h_double_arrow')
        elif top: self.canvas.config(cursor='sb_v_double_arrow')
        elif bottom: self.canvas.config(cursor='sb_v_double_arrow')
        else: self.canvas.config(cursor='fleur')

    def on_mouse_down(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.win_start_x = self.overlay_window.winfo_x()
        self.win_start_y = self.overlay_window.winfo_y()
        self.win_start_w = self.overlay_window.winfo_width()
        self.win_start_h = self.overlay_window.winfo_height()
        
        x, y = event.x, event.y
        w, h = self.win_start_w, self.win_start_h
        edge = 15
        
        self.resize_edge = {
            'left': x < edge,
            'right': x > w - edge,
            'top': y < edge,
            'bottom': y < h - edge
        }
        
        if any(self.resize_edge.values()):
            self.resizing = True
        else:
            self.dragging = True

    def on_mouse_drag(self, event):
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        
        if self.dragging:
            nx = self.win_start_x + dx
            ny = self.win_start_y + dy
            self.overlay_window.geometry(f"+{nx}+{ny}")
            self.save_geo()
            
        elif self.resizing:
            nx, ny, nw, nh = self.win_start_x, self.win_start_y, self.win_start_w, self.win_start_h
            
            if self.resize_edge['right']: nw += dx
            if self.resize_edge['bottom']: nh += dy
            if self.resize_edge['left']:
                nx += dx
                nw -= dx
            if self.resize_edge['top']:
                ny += dy
                nh -= dy
                
            nw = max(50, nw)
            nh = max(50, nh)
            self.overlay_window.geometry(f"{nw}x{nh}+{nx}+{ny}")
            self.save_geo()

    def on_mouse_up(self, event):
        self.dragging = False
        self.resizing = False
        self.save_geo()

    def save_geo(self, e=None):
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
