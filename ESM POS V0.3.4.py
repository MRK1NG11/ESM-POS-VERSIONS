import tkinter as tk
from tkinter import messagebox, ttk
import json, os, datetime, tempfile, platform, subprocess, time, csv, sys
import requests # Make sure to run: pip install requests

# ================= THEME & SYSTEM SETTINGS =================
VERSION = "0.3.4"
STORE_NAME = "EAT SUM MEAT (PTY) LTD"
STORE_ADDRESS = "123 Braai Street, East London"
VAT_RATE = 0.15 # 15% VAT

# --- GITHUB AUTO-UPDATER SETTINGS ---
# IMPORTANT: Update these to your permanent, public raw URLs (NO ?token= at the end!)
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/version.txt"
GITHUB_EXE_URL = "https://github.com/MRK1NG11/ESM-POS-VERSIONS/raw/refs/heads/main/EatSumMeatPOS.exe"
GITHUB_README_URL = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/READ%20ME.txt"

THEME = {
    "bg_dark": "#0d0d0d",      
    "bg_panel": "#1a1a1a",     
    "bg_input": "#262626",     
    "primary": "#E53935",      
    "primary_hover": "#b71c1c",
    "accent": "#FF9800",       
    "text_main": "#ffffff",
    "text_dim": "#9e9e9e",
    "success": "#00E676",      
    "warning": "#FF1744",      
    "disabled": "#333333",
    "exact_btn": "#00C853",
    "receipt_paper": "#f9f9f9"
}

cart = []
held_cart = []
cash_received = 0
current_user = None
login_start = None
user_times = []
order_counter = 1

CASHIERS = ["CSH1", "CSH2", "ADMIN"]
ADMIN_PIN = "1981"

def disable_event(): pass 
def block_shortcut(event): return "break" 

# ================= PATH MANAGEMENT =================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_DIR, filename)

# ================= AUTO-UPDATER LOGIC =================
def show_update_prompt(latest_version):
    # FEATURE 3: Custom Update Prompt Window
    prompt_win = tk.Toplevel(root)
    prompt_win.attributes("-topmost", True)
    prompt_win.overrideredirect(True)
    prompt_win.configure(bg=THEME["bg_panel"], highlightthickness=2, highlightbackground=THEME["accent"])
    prompt_win.geometry("500x250")
    
    prompt_win.update_idletasks()
    x = (prompt_win.winfo_screenwidth() // 2) - 250
    y = (prompt_win.winfo_screenheight() // 2) - 125
    prompt_win.geometry(f"+{x}+{y}")
    
    tk.Label(prompt_win, text="🚀 UPDATE AVAILABLE", font=("Arial", 22, "bold"), fg=THEME["accent"], bg=THEME["bg_panel"]).pack(pady=(30, 10))
    tk.Label(prompt_win, text=f"Version {latest_version} is ready to install.", font=("Arial", 14), fg=THEME["text_main"], bg=THEME["bg_panel"]).pack(pady=10)
    
    btn_f = tk.Frame(prompt_win, bg=THEME["bg_panel"])
    btn_f.pack(pady=20)
    
    tk.Button(btn_f, text="LATER", font=("Arial", 14, "bold"), bg="#555", fg="white", width=10, relief="flat", command=prompt_win.destroy).pack(side="left", padx=10)
    def do_update():
        prompt_win.destroy()
        perform_update()
    tk.Button(btn_f, text="UPDATE NOW", font=("Arial", 14, "bold"), bg=THEME["primary"], fg="white", width=15, relief="flat", command=do_update).pack(side="left", padx=10)

def check_for_updates():
    try:
        response = requests.get(GITHUB_VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version and latest_version != VERSION:
            show_update_prompt(latest_version)
    except Exception as e:
        print(f"Update check failed: {e}") 

def perform_update():
    try:
        upd_win = tk.Toplevel()
        upd_win.attributes("-topmost", True)
        upd_win.overrideredirect(True) 
        upd_win.geometry("500x200")
        upd_win.configure(bg=THEME["bg_panel"], highlightthickness=2, highlightbackground=THEME["primary"])
        
        upd_win.update_idletasks()
        x = (upd_win.winfo_screenwidth() // 2) - 250
        y = (upd_win.winfo_screenheight() // 2) - 100
        upd_win.geometry(f"+{x}+{y}")
        
        tk.Label(upd_win, text="🥩 SYSTEM UPDATE", font=("Arial", 22, "bold"), fg=THEME["primary"], bg=THEME["bg_panel"]).pack(pady=(30, 10))
        tk.Label(upd_win, text="Update in progress, the system will restart soon.", font=("Arial", 12), fg=THEME["text_main"], bg=THEME["bg_panel"]).pack(pady=5)
        
        progress = ttk.Progressbar(upd_win, orient="horizontal", length=400, mode="determinate")
        progress.pack(pady=20)
        upd_win.update()

        r = requests.get(GITHUB_EXE_URL, stream=True, timeout=30)
        total_length = r.headers.get('content-length')
        update_file = get_path("update_temp.exe")
        
        with open(update_file, 'wb') as f:
            if total_length is None: 
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.step(5)
                    upd_win.update()
            else:
                total_length = int(total_length)
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    f.write(chunk)
                    progress["value"] = int(100 * downloaded / total_length)
                    upd_win.update()

        try:
            readme_req = requests.get(GITHUB_README_URL, timeout=10)
            if readme_req.status_code == 200:
                with open(get_path("README.txt"), 'wb') as f:
                    f.write(readme_req.content)
        except Exception as e:
            print(f"README Update Failed: {e}") 

        # FEATURE 4: Silent Restart
        if getattr(sys, 'frozen', False):
            batch_script = get_path("update_swap.bat")
            current_exe = sys.executable
            
            with open(batch_script, "w") as f:
                f.write(f"""@echo off
timeout /t 2 /nobreak > nul
del "{current_exe}"
move "{update_file}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
""")
            subprocess.Popen([batch_script], shell=True)
            sys.exit()
        else:
            upd_win.destroy()
            # Silently restart the python script if running in developer mode
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit()
    except Exception as e:
        messagebox.showerror("Update Error", f"Failed to download update: {e}")

# ================= DATA ACCESS LAYER =================
def load_products():
    default = {
        "1001": {"name": "Boerewors Roll", "price": 45.0, "stock": 50, "cat": "MEAT"},
        "1002": {"name": "Steak Roll", "price": 65.0, "stock": 40, "cat": "MEAT"},
        "1003": {"name": "Chicken Burger", "price": 55.0, "stock": 35, "cat": "MEAT"},
        "1004": {"name": "Pork Ribs", "price": 95.0, "stock": 20, "cat": "MEAT"},
        "2001": {"name": "Slap Chips", "price": 25.0, "stock": 100, "cat": "SNACKS"},
        "3001": {"name": "Coke 440ml", "price": 20.0, "stock": 120, "cat": "DRINK"},
        "4001": {"name": "Carrot Salad", "price": 20.0, "stock": 50, "cat": "VEG"},
    }
    prod_path = get_path("products.json")
    if os.path.exists(prod_path):
        try:
            with open(prod_path, "r") as f: data = json.load(f)
            for c in default:
                if c not in data: data[c] = default[c]
            return data
        except: return default
    else:
        with open(prod_path, "w") as f: json.dump(default, f, indent=4)
        return default

products = load_products()

def sync_stock_global():
    with open(get_path("products.json"), "w") as f: json.dump(products, f, indent=4)

def save_local_session(session_data):
    user_times.append(session_data)
    with open(get_path("sessions.json"), "w") as f: json.dump(user_times, f, indent=4)

def save_local_transaction(sale_data):
    data = []
    trans_path = get_path("transactions.json")
    if os.path.exists(trans_path):
        try:
            with open(trans_path, "r") as f: data = json.load(f)
        except: data = []
    data.append(sale_data)
    with open(trans_path, "w") as f: json.dump(data, f, indent=4)
    sync_stock_global()

def run_end_of_day_export():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    export_pkg = {
        "node_id": "TILL_01",
        "date": today,
        "transactions": [],
        "sessions": user_times
    }
    trans_path = get_path("transactions.json")
    if os.path.exists(trans_path):
        with open(trans_path, "r") as f: export_pkg["transactions"] = json.load(f)
    
    eod_filename = get_path(f"EOD_PUSH_{today}.json")
    with open(eod_filename, "w") as f: json.dump(export_pkg, f, indent=4)
    return eod_filename

if os.path.exists(get_path("sessions.json")):
    try:
        with open(get_path("sessions.json"), "r") as f: user_times = json.load(f)
    except: user_times = []

# ================= CORE LOGIC =================
def raw_total(): 
    return sum(i["price"] * i["qty"] for i in cart)

def update_cart_ui():
    cart_list.delete(0, tk.END)
    for i in cart:
        name = (i["name"][:13] + "..") if len(i["name"]) > 15 else i["name"]
        line = f"{name:<15} x{i['qty']:<2} R{i['price']*i['qty']:>7.2f}"
        cart_list.insert(tk.END, line)
    
    cart_list.yview_moveto(1)
    final_tot = raw_total()
    total_lbl.config(text=f"TOTAL: R{final_tot:.2f}")
    
    if cart and cash_received < final_tot:
        shortfall = final_tot - cash_received
        change_lbl.config(text=f"DUE: R{shortfall:.2f}", fg=THEME["warning"])
    else:
        change = max(0, cash_received - final_tot)
        change_lbl.config(text=f"CHANGE: R{change:.2f}", fg=THEME["success"])
        
    refresh_product_grid()

def add_product(code):
    if code not in products:
        messagebox.showerror("Error", "Product Code Not Found")
        barcode_entry.focus_set()
        return
    if products[code]["stock"] <= 0:
        messagebox.showwarning("Stock", "Out of stock!")
        barcode_entry.focus_set()
        return
    for i in cart:
        if i["code"] == code:
            i["qty"] += 1
            products[code]["stock"] -= 1
            update_cart_ui()
            barcode_entry.focus_set()
            return
    cart.append({"code": code, "name": products[code]["name"], "price": products[code]["price"], "qty": 1})
    products[code]["stock"] -= 1
    update_cart_ui()
    barcode_entry.focus_set()

def void_item():
    sel = cart_list.curselection()
    if not sel: 
        messagebox.showinfo("Select Item", "Please tap an item in the cart to void it.")
        barcode_entry.focus_set()
        return
    pw = custom_input("Manager Override", "Enter Admin PIN", is_password=True)
    if pw != ADMIN_PIN:
        messagebox.showerror("Error", "Manager override failed")
        barcode_entry.focus_set()
        return
    item = cart.pop(sel[0])
    products[item["code"]]["stock"] += item["qty"]
    update_cart_ui()
    barcode_entry.focus_set()

def clear_cart():
    if not cart: return
    if messagebox.askyesno("Confirm", "Clear the entire order?"):
        for item in cart:
            products[item["code"]]["stock"] += item["qty"]
        cart.clear()
        clear_cash()
        update_cart_ui()
    barcode_entry.focus_set()

def toggle_hold_cart():
    global held_cart, cart
    if cart:
        if held_cart:
            messagebox.showwarning("Hold Error", "There is already a cart on hold! Recall or clear it first.")
        else:
            held_cart = cart.copy()
            cart.clear()
            clear_cash()
            update_cart_ui()
            hold_btn.config(text="RECALL", bg=THEME["accent"], fg="black")
    elif held_cart:
        cart = held_cart.copy()
        held_cart.clear()
        update_cart_ui()
        hold_btn.config(text="HOLD", bg="#555", fg="white")
    else:
        messagebox.showinfo("Hold", "Cart is empty and no orders are on hold.")
    barcode_entry.focus_set()

def add_cash(amount):
    global cash_received
    cash_received += amount
    cash_lbl.config(text=f"CASH IN: R{cash_received:.2f}")
    update_cart_ui()
    barcode_entry.focus_set()

def set_exact_cash():
    global cash_received
    if not cart: return
    final_tot = raw_total()
    if cash_received < final_tot:
        cash_received = final_tot
        cash_lbl.config(text=f"CASH IN: R{cash_received:.2f}")
        update_cart_ui()
    barcode_entry.focus_set()

def clear_cash():
    global cash_received
    cash_received = 0
    cash_lbl.config(text=f"CASH IN: R0.00")
    update_cart_ui()

def generate_receipt_text(method, final_tot):
    vat_amt = final_tot * VAT_RATE
    excl_vat = final_tot - vat_amt
    
    r =  f"{STORE_NAME.center(32)}\n"
    r += f"{STORE_ADDRESS.center(32)}\n"
    r += f"VAT No: 4123456789".center(32) + "\n"
    r += "=" * 32 + "\n"
    r += f"Sales: #{order_counter}  Till: 01\n"
    r += f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    r += f"Cashier: {current_user}\n"
    r += "-" * 32 + "\n"
    
    for i in cart:
        name = i["name"][:18]
        line_tot = i["price"] * i["qty"]
        r += f"{name:<18} x{i['qty']:<2} R{line_tot:>7.2f}\n"
        
    r += "-" * 32 + "\n"
    r += f"TOTAL (Incl VAT):      R{final_tot:>7.2f}\n"
    r += f"PAID VIA:              {method:>8}\n"
    
    if method == "CASH":
        r += f"CASH TENDERED:         R{cash_received:>7.2f}\n"
        r += f"CHANGE DUE:            R{max(0, cash_received - final_tot):>7.2f}\n"
        
    r += "-" * 32 + "\n"
    r += f"Total Excl VAT:        R{excl_vat:>7.2f}\n"
    r += f"VAT @ 15%:             R{vat_amt:>7.2f}\n"
    r += "=" * 32 + "\n"
    r += "THANK YOU FOR YOUR BUSINESS!".center(32) + "\n"
    r += "PLEASE RETAIN YOUR SLIP".center(32) + "\n\n\n\n"
    return r

def process_payment(method):
    global order_counter
    if not cart: return
    
    final_tot = raw_total()
    if method == "CASH" and cash_received < final_tot:
        messagebox.showwarning("Payment", f"Insufficient Cash!\nDUE: R{final_tot - cash_received:.2f}")
        barcode_entry.focus_set()
        return
    
    now = datetime.datetime.now()
    sale = {
        "id": now.strftime("%Y%m%d%H%M%S"),
        "order_num": order_counter,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "cashier": current_user,
        "method": method,
        "amount": final_tot,
        "items": cart.copy()
    }
    
    save_local_transaction(sale)
    receipt_txt = generate_receipt_text(method, final_tot)
    print_receipt_silent(receipt_txt)
    
    cart.clear()
    clear_cash()
    order_counter = (order_counter % 99) + 1
    # FEATURE 1: Order -> Sales
    order_lbl.config(text=f"SALES #{order_counter}")
    update_cart_ui()
    
    barcode_entry.focus_set()

def print_receipt_silent(text):
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", dir=BASE_DIR)
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(0, "print", tmp, None, ".", 0)
        else:
            subprocess.run(["lp", tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Print error: {e}")

# ================= CUSTOM INPUTS =================
def custom_input(title, prompt, is_password=False):
    win = tk.Toplevel()
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)
    win.configure(bg=THEME["bg_panel"])
    win.geometry("550x350")
    win.title(title)
    win.grab_set(); win.attributes("-topmost", True)
    
    tk.Label(win, text=prompt, font=("Arial", 20, "bold"), fg=THEME["text_main"], bg=THEME["bg_panel"]).pack(pady=30)
    entry = tk.Entry(win, font=("Arial", 28), show="*" if is_password else "", justify="center", bg=THEME["bg_input"], fg=THEME["accent"], insertbackground="white", relief="flat")
    entry.pack(pady=10, ipady=10, fill="x", padx=40); entry.focus_set()
    
    res = {"val": None}
    def submit(event=None): res["val"] = entry.get(); win.destroy()
    def cancel(): win.destroy()
        
    entry.bind("<Return>", submit)
    
    btn_frame = tk.Frame(win, bg=THEME["bg_panel"])
    btn_frame.pack(pady=30)
    tk.Button(btn_frame, text="CANCEL", font=("Arial", 16, "bold"), bg="#555", fg="white", width=12, height=2, relief="flat", command=cancel).pack(side="left", padx=10)
    tk.Button(btn_frame, text="CONFIRM", font=("Arial", 16, "bold"), bg=THEME["primary"], fg=THEME["text_main"], width=12, height=2, relief="flat", command=submit).pack(side="left", padx=10)
    win.wait_window()
    return res["val"]

# ================= ADMIN PANEL =================
def admin_panel():
    pw = custom_input("Admin", "Enter Admin PIN", is_password=True)
    if pw != ADMIN_PIN: 
        barcode_entry.focus_set()
        return
    
    win = tk.Toplevel(); win.attributes("-fullscreen", True); win.configure(bg=THEME["bg_dark"])
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)
    
    hdr = tk.Frame(win, bg=THEME["bg_panel"], padx=20)
    hdr.pack(fill="x", pady=(0, 10))
    tk.Label(hdr, text="🥩 SYSTEM ADMIN DASHBOARD", font=("Arial", 30, "bold"), fg=THEME["primary"], bg=THEME["bg_panel"]).pack(side="left", pady=15)
    
    btn_frame = tk.Frame(hdr, bg=THEME["bg_panel"])
    btn_frame.pack(side="right")
    
    def trigger_eod():
        if messagebox.askyesno("Run EOD", "Run End of Day sequence and stage data for Back Office?"):
            file_loc = run_end_of_day_export()
            messagebox.showinfo("EOD Success", f"Data packaged for server sync:\n{file_loc}")
            
    tk.Button(btn_frame, text="RUN EOD (SYNC PREP)", font=("Arial", 14, "bold"), bg=THEME["exact_btn"], fg="white", height=2, relief="flat", padx=15, command=trigger_eod).pack(side="left", padx=10)
    
    def nuke_system():
        if messagebox.askyesno("WARNING", "Are you sure you want to completely exit the POS system?"):
            root.destroy()
            sys.exit()
            
    tk.Button(btn_frame, text="EXIT POS SYSTEM", font=("Arial", 14, "bold"), bg=THEME["warning"], fg="white", height=2, relief="flat", padx=15, command=nuke_system).pack(side="left", padx=10)

    main_frame = tk.Frame(win, bg=THEME["bg_dark"])
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def create_table(parent, title, columns):
        frame = tk.Frame(parent, bg=THEME["bg_panel"])
        frame.pack(side="left", fill="both", expand=True, padx=10)
        tk.Label(frame, text=title, font=("Arial", 16, "bold"), fg=THEME["text_main"], bg=THEME["bg_panel"], anchor="w").pack(fill="x", padx=10, pady=(10,5))
        
        tree = ttk.Treeview(frame, columns=columns, show="headings", style="Dark.Treeview")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=120, stretch=True)
        
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y", pady=(0, 10), padx=(0, 5))
        tree.pack(fill="both", expand=True, padx=(10,0), pady=(0, 10))
        return tree, frame

    sales_tree, sales_frame = create_table(main_frame, "Today's Local Sales", ("Time", "Order", "Method", "Amount"))
    
    stock_tree, stock_frame = create_table(main_frame, "Live Inventory", ("Code", "Product", "Category", "Stock"))
    
    def admin_add_stock():
        sel = stock_tree.selection()
        if not sel:
            messagebox.showinfo("Select Product", "Please click a product in the table first.")
            return
        
        item = stock_tree.item(sel[0])
        code = str(item['values'][0])
        
        qty_str = custom_input("Add Stock", f"How much stock to add for {item['values'][1]}?")
        if qty_str and qty_str.isdigit():
            qty = int(qty_str)
            products[code]["stock"] += qty
            sync_stock_global() 
            
            stock_tree.delete(sel[0])
            stock_tree.insert("", "end", values=(code, products[code]['name'], products[code]['cat'], products[code]['stock']))
            refresh_product_grid()
            messagebox.showinfo("Success", f"Added {qty} to {products[code]['name']} stock.")
        elif qty_str is not None:
            messagebox.showerror("Error", "Please enter a valid number.")

    tk.Button(stock_frame, text="+ ADD STOCK TO SELECTED", font=("Arial", 12, "bold"), bg=THEME["primary"], fg="white", relief="flat", command=admin_add_stock).pack(fill="x", padx=10, pady=(0, 10))

    sess_tree, sess_frame = create_table(main_frame, "Cashier Logins", ("Date", "User", "In", "Out", "Hrs"))

    total_day = 0
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    sales_found = False
    
    trans_path = get_path("transactions.json")
    if os.path.exists(trans_path):
        try:
            with open(trans_path, "r") as f: t_data = json.load(f)
            for t in reversed(t_data):
                if t["date"] == today:
                    sales_tree.insert("", "end", values=(t['time'], f"#{t.get('order_num','?')}", t['method'], f"R{t['amount']:.2f}"))
                    total_day += t["amount"]
                    sales_found = True
        except: pass

    if not sales_found: sales_tree.insert("", "end", values=("-", "No Sales Yet", "-", "-"))

    for code, p in products.items():
        stock_tree.insert("", "end", values=(code, p['name'], p['cat'], p['stock']))

    if len(user_times) > 0:
        for s in reversed(user_times):
            sess_tree.insert("", "end", values=(s['date'], s['user'], s['login'], s['logout'], f"{s['hours']}h"))
    else:
        sess_tree.insert("", "end", values=("-", "No Completed", "Sessions", "Yet", "-"))

    bottom = tk.Frame(win, bg=THEME["bg_panel"]); bottom.pack(fill="x", side="bottom")
    tk.Label(bottom, text=f"DAILY REVENUE: R{total_day:.2f}", font=("Arial", 30, "bold"), fg=THEME["success"], bg=THEME["bg_panel"]).pack(side="left", padx=30, pady=20)
    
    def close_admin():
        win.destroy()
        barcode_entry.focus_set() 
        
    tk.Button(bottom, text="CLOSE ADMIN PANEL", font=("Arial", 18, "bold"), bg=THEME["primary"], fg=THEME["text_main"], height=2, relief="flat", padx=30, command=close_admin).pack(side="right", padx=30, pady=20)

# ================= LOGIN / LOGOUT =================
def login_screen():
    global current_user, login_start
    win = tk.Toplevel(); win.configure(bg=THEME["bg_dark"])
    win.attributes("-fullscreen", True) 
    win.attributes("-topmost", True)
    
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)
    win.grab_set() 
    
    card = tk.Frame(win, bg=THEME["bg_panel"], bd=0, highlightthickness=2, highlightbackground=THEME["primary"])
    card.place(relx=0.5, rely=0.5, anchor="center", width=600, height=450)
    
    tk.Label(card, text="🥩 EAT SUM MEAT 🥩", font=("Arial", 35, "bold"), fg=THEME["primary"], bg=THEME["bg_panel"]).pack(pady=(50, 10))
    tk.Label(card, text="SECURE CASHIER LOGIN", font=("Arial", 16), fg=THEME["text_dim"], bg=THEME["bg_panel"]).pack(pady=10)
    
    ent = tk.Entry(card, font=("Arial", 40), justify="center", width=8, bg=THEME["bg_input"], fg=THEME["accent"], insertbackground="white", relief="flat")
    ent.pack(pady=30, ipady=10); ent.focus_set()
    
    def do_login(event=None):
        global current_user, login_start
        c = ent.get().strip().upper()
        if c in CASHIERS:
            current_user = c
            login_start = time.time()
            cashier_lbl.config(text=f"USER: {current_user}")
            win.grab_release()
            win.destroy()
            barcode_entry.focus_set() 
        else:
            messagebox.showerror("Error", "Invalid Cashier Code")
            ent.delete(0, tk.END)
            
    ent.bind("<Return>", do_login)
    tk.Button(card, text="AUTHORIZE", font=("Arial", 22, "bold"), bg=THEME["primary"], fg=THEME["text_main"], width=15, height=2, relief="flat", command=do_login).pack(pady=20)
    win.wait_window()

def logoff():
    global current_user, login_start, held_cart
    
    if cart or held_cart:
        if not messagebox.askyesno("Warning", "You have active or held orders. Logging off will clear them and return stock. Continue?"):
            barcode_entry.focus_set()
            return
        if cart:
            for i in cart: products[i["code"]]["stock"] += i["qty"]
            cart.clear()
        if held_cart:
            for i in held_cart: products[i["code"]]["stock"] += i["qty"]
            held_cart.clear()
            hold_btn.config(text="HOLD", bg="#555", fg="white")
            
    if current_user and login_start:
        login_time = datetime.datetime.fromtimestamp(login_start)
        logout_time = datetime.datetime.now()
        duration = (logout_time - login_time).total_seconds() / 3600
        
        session_data = {
            "date": login_time.strftime("%Y-%m-%d"),
            "user": current_user,
            "login": login_time.strftime("%H:%M:%S"),
            "logout": logout_time.strftime("%H:%M:%S"),
            "hours": round(duration, 2)
        }
        save_local_session(session_data)
        
        current_user = None
        login_start = None
        clear_cash()
        update_cart_ui()
        login_screen()

# ================= MAIN UI STYLING & SETUP =================
root = tk.Tk(); root.attributes("-fullscreen", True); root.configure(bg=THEME["bg_dark"])
root.protocol("WM_DELETE_WINDOW", disable_event)
root.bind("<Alt-F4>", block_shortcut)

style = ttk.Style()
style.theme_use("clam")
style.configure("Dark.Vertical.TScrollbar", background="#333", troughcolor=THEME["bg_dark"], bordercolor=THEME["bg_dark"], arrowcolor="#ffffff", relief="flat")
style.map("Dark.Vertical.TScrollbar", background=[("active", "#555")])
style.configure("Dark.Treeview", background=THEME["bg_dark"], foreground=THEME["text_main"], fieldbackground=THEME["bg_dark"], rowheight=40, font=("Arial", 13), borderwidth=0)
style.configure("Dark.Treeview.Heading", background=THEME["bg_input"], foreground=THEME["accent"], font=("Arial", 14, "bold"), borderwidth=0)
style.map("Dark.Treeview", background=[("selected", THEME["primary"])])

# --- HEADER ---
hdr = tk.Frame(root, bg=THEME["bg_panel"], height=80)
hdr.pack(fill="x", side="top"); hdr.pack_propagate(False)

tk.Label(hdr, text="🥩 EAT SUM MEAT POS", font=("Arial", 30, "bold"), fg=THEME["primary"], bg=THEME["bg_panel"]).pack(side="left", padx=30, pady=15)
clock_lbl = tk.Label(hdr, font=("Arial", 18, "bold"), fg=THEME["text_main"], bg=THEME["bg_panel"]); clock_lbl.pack(side="right", padx=30, pady=20)
cashier_lbl = tk.Label(hdr, text="USER: NONE", font=("Arial", 18, "bold"), fg=THEME["accent"], bg=THEME["bg_panel"]); cashier_lbl.pack(side="right", padx=30, pady=20)

# FEATURE 1: Order -> Sales
order_lbl = tk.Label(hdr, text=f"SALES #{order_counter}", font=("Arial", 22, "bold"), fg=THEME["success"], bg=THEME["bg_panel"]); order_lbl.pack(side="right", padx=30, pady=20)

def tick(): clock_lbl.config(text=datetime.datetime.now().strftime('%Y-%m-%d  %H:%M:%S')); root.after(1000, tick)
tick()

# --- BODY ---
main_body = tk.Frame(root, bg=THEME["bg_dark"])
main_body.pack(fill="both", expand=True, pady=15, padx=15)

# COL 1: CART CARD
left_col = tk.Frame(main_body, bg=THEME["bg_panel"], width=450); left_col.pack(side="left", fill="y", padx=10); left_col.pack_propagate(False)

cart_frame = tk.Frame(left_col, bg=THEME["bg_panel"])
cart_frame.pack(fill="both", expand=True, padx=10, pady=10)

cart_scroll = ttk.Scrollbar(cart_frame, orient="vertical", style="Dark.Vertical.TScrollbar")
cart_scroll.pack(side="right", fill="y")

cart_list = tk.Listbox(cart_frame, font=("Consolas", 18), bg=THEME["bg_input"], fg=THEME["text_main"], selectbackground=THEME["primary"], borderwidth=0, highlightthickness=0, yscrollcommand=cart_scroll.set)
cart_list.pack(side="left", fill="both", expand=True)
cart_scroll.config(command=cart_list.yview)

totals_frame = tk.Frame(left_col, bg=THEME["bg_panel"], pady=15, padx=20); totals_frame.pack(fill="x")
total_lbl = tk.Label(totals_frame, text="TOTAL: R0.00", font=("Arial", 38, "bold"), fg=THEME["text_main"], bg=THEME["bg_panel"], anchor="e"); total_lbl.pack(fill="x", pady=(0, 10))
cash_lbl = tk.Label(totals_frame, text="CASH IN: R0.00", font=("Arial", 20), fg=THEME["text_dim"], bg=THEME["bg_panel"], anchor="e"); cash_lbl.pack(fill="x", pady=5)
change_lbl = tk.Label(totals_frame, text="CHANGE: R0.00", font=("Arial", 28, "bold"), fg=THEME["success"], bg=THEME["bg_panel"], anchor="e"); change_lbl.pack(fill="x")

# COL 2: SCAN, NUMPAD & PAY CARD
mid_col = tk.Frame(main_body, bg=THEME["bg_panel"], width=340); mid_col.pack(side="left", fill="y", padx=10); mid_col.pack_propagate(False)

def handle_scan(event=None):
    code = barcode_entry.get().strip(); barcode_entry.delete(0, tk.END)
    if code: add_product(code)
    barcode_entry.focus_set()

def numpad_click(val):
    if val == "C": barcode_entry.delete(0, tk.END)
    elif val == "ENT": handle_scan()
    else: barcode_entry.insert(tk.END, val)
    barcode_entry.focus_set()

barcode_entry = tk.Entry(mid_col, font=("Arial", 30), justify="center", bg=THEME["bg_input"], fg=THEME["accent"], insertbackground="white", relief="flat")
barcode_entry.pack(fill="x", pady=15, padx=15, ipady=5); barcode_entry.bind("<Return>", handle_scan)

numpad_frame = tk.Frame(mid_col, bg=THEME["bg_panel"]); numpad_frame.pack(fill="x", padx=10)
keys = [('7','8','9'), ('4','5','6'), ('1','2','3'), ('C','0','ENT')]
for r, row in enumerate(keys):
    for c, key in enumerate(row):
        color = THEME["primary"] if key in ['C','ENT'] else "#333"
        tk.Button(numpad_frame, text=key, font=("Arial", 22, "bold"), bg=color, fg="white", height=2, width=5, relief="flat", command=lambda k=key: numpad_click(k)).grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

# Action Row
btn_row = tk.Frame(mid_col, bg=THEME["bg_panel"]); btn_row.pack(fill="x", pady=(15, 5), padx=15)
tk.Button(btn_row, text="VOID", font=("Arial", 16, "bold"), bg="#555", fg="white", height=2, relief="flat", command=void_item).pack(side="left", fill="x", expand=True, padx=(0,2))
hold_btn = tk.Button(btn_row, text="HOLD", font=("Arial", 16, "bold"), bg="#555", fg="white", height=2, relief="flat", command=toggle_hold_cart)
hold_btn.pack(side="left", fill="x", expand=True, padx=(2,2))
tk.Button(btn_row, text="CLEAR", font=("Arial", 16, "bold"), bg=THEME["warning"], fg="white", height=2, relief="flat", command=clear_cart).pack(side="left", fill="x", expand=True, padx=(2,0))

# 2-Row Cash Grid
cash_frame = tk.Frame(mid_col, bg=THEME["bg_panel"]); cash_frame.pack(fill="x", pady=5, padx=15)
r1 = tk.Frame(cash_frame, bg=THEME["bg_panel"]); r1.pack(fill="x")
for amt in [1, 2, 5, 10]:
    tk.Button(r1, text=f"+R{amt}", font=("Arial", 14, "bold"), bg="#444", fg="white", height=2, relief="flat", command=lambda a=amt: add_cash(a)).pack(side="left", expand=True, padx=3, pady=3)
r2 = tk.Frame(cash_frame, bg=THEME["bg_panel"]); r2.pack(fill="x")
for amt in [20, 50, 100, 200]:
    tk.Button(r2, text=f"+R{amt}", font=("Arial", 14, "bold"), bg="#444", fg="white", height=2, relief="flat", command=lambda a=amt: add_cash(a)).pack(side="left", expand=True, padx=3, pady=3)

tk.Button(mid_col, text="EXACT CASH", font=("Arial", 16, "bold"), bg=THEME["exact_btn"], fg="white", height=2, relief="flat", command=set_exact_cash).pack(fill="x", padx=15, pady=(5,0))
tk.Button(mid_col, text="PAY CASH", font=("Arial", 22, "bold"), bg=THEME["primary"], fg=THEME["text_main"], height=2, relief="flat", command=lambda: process_payment("CASH")).pack(fill="x", padx=15, pady=10)
tk.Button(mid_col, text="PAY EFT", font=("Arial", 22, "bold"), bg="#0288d1", fg=THEME["text_main"], height=2, relief="flat", command=lambda: process_payment("EFT")).pack(fill="x", padx=15, pady=(0, 15))

# COL 3: PRODUCT GRID CARD
right_col = tk.Frame(main_body, bg=THEME["bg_panel"]); right_col.pack(side="left", fill="both", expand=True, padx=10)
cat_frame = tk.Frame(right_col, bg=THEME["bg_panel"]); cat_frame.pack(fill="x", pady=15, padx=15)
grid_frame = tk.Frame(right_col, bg=THEME["bg_panel"]); grid_frame.pack(fill="both", expand=True, padx=15, pady=10)

# FEATURE 2: Force strict uniform column widths in the product grid
for c in range(3):
    grid_frame.columnconfigure(c, weight=1, uniform="group1")

category_buttons = {}
current_category = "ALL"

def refresh_product_grid(cat=None):
    global current_category
    if cat: current_category = cat
    
    for c_name, btn in category_buttons.items():
        if c_name == current_category: btn.config(bg=THEME["primary"])
        else: btn.config(bg="#333")

    for widget in grid_frame.winfo_children(): widget.destroy()
    
    row, col = 0, 0
    for code, p in products.items():
        if current_category == "ALL" or p["cat"].upper() == current_category:
            
            is_out = p["stock"] <= 0
            if is_out: stock_color = THEME["warning"] 
            elif p["stock"] <= 5: stock_color = THEME["warning"]
            elif p["stock"] <= 20: stock_color = THEME["accent"]
            else: stock_color = THEME["text_dim"] 
            
            bg_color = THEME["bg_input"]
            btn_container = tk.Frame(grid_frame, bg=bg_color, bd=1, relief="ridge", width=190, height=130)
            btn_container.grid_propagate(False) 
            btn_container.grid(row=row, column=col, padx=10, pady=10, sticky="nsew") # Added sticky to stretch strictly
            
            top_lbl = tk.Label(btn_container, text=f"{p['name']}\nR{p['price']:.2f}", font=("Arial", 16, "bold"), bg=bg_color, fg=THEME["text_main"])
            top_lbl.pack(expand=True, fill="both", pady=(10,0))
            
            stock_txt = "OUT OF STOCK" if is_out else f"Stock: {p['stock']}"
            btm_lbl = tk.Label(btn_container, text=stock_txt, font=("Arial", 14, "bold"), bg=bg_color, fg=stock_color)
            btm_lbl.pack(side="bottom", pady=(0,10))
            
            if not is_out:
                def make_handler(c): return lambda e: add_product(c)
                handler = make_handler(code)
                btn_container.bind("<Button-1>", handler)
                top_lbl.bind("<Button-1>", handler)
                btm_lbl.bind("<Button-1>", handler)

            col += 1
            if col > 2: col = 0; row += 1

cats = ["ALL", "MEAT", "SNACKS", "VEG", "DRINK"]
for c in cats: 
    b = tk.Button(cat_frame, text=c, font=("Arial", 18, "bold"), fg=THEME["text_main"], width=9, height=2, relief="flat", command=lambda ct=c: [refresh_product_grid(ct), barcode_entry.focus_set()])
    b.pack(side="left", padx=5)
    category_buttons[c] = b

# --- BOTTOM BAR ---
btm_bar = tk.Frame(root, bg=THEME["bg_panel"], height=70); btm_bar.pack(fill="x", side="bottom", pady=(10,0))
tk.Button(btm_bar, text="LOG OFF", font=("Arial", 16, "bold"), bg="#333", fg=THEME["text_main"], width=15, height=2, relief="flat", command=logoff).pack(side="left", padx=30, pady=10)

tk.Label(btm_bar, text=f"Version {VERSION}", font=("Arial", 14), fg=THEME["text_dim"], bg=THEME["bg_panel"]).pack(side="left", expand=True)

tk.Button(btm_bar, text="ADMIN PANEL", font=("Arial", 16, "bold"), bg="#333", fg=THEME["accent"], width=15, height=2, relief="flat", command=admin_panel).pack(side="right", padx=30, pady=10)

refresh_product_grid()

# Boot Sequence
root.after(100, check_for_updates) 
root.after(500, login_screen) 
root.mainloop()