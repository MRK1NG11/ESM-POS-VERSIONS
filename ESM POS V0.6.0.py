import tkinter as tk
from tkinter import messagebox, ttk
import json, os, datetime, tempfile, platform, subprocess, time, sys
import webbrowser 
import requests 

# ================= THEME & SYSTEM SETTINGS =================
VERSION = "0.6.0"
STORE_NAME = "EAT SUM MEAT (PTY) LTD"
STORE_ADDRESS = "11 Caxton Street, East London City\nEast London, 5200, South Africa"
VAT_RATE = 0.15

TILL_NUMBER = "01"

GITHUB_VERSION_URL = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/version.txt"
GITHUB_EXE_URL = "https://github.com/MRK1NG11/ESM-POS-VERSIONS/raw/refs/heads/main/EatSumMeatPOS.exe"
GITHUB_README_URL = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/READ%20ME.txt"

# Dark Mode Eat Sum Meat Theme (Premium, High Contrast)
THEME = {
    "bg_main": "#121212",         
    "bg_panel": "#1e1e1e",        
    "brand_red": "#d32f2f",       
    "lcd_bg": "#000000",          
    "lcd_fg": "#00e676",          
    "btn_grey": "#333333",        
    "btn_white": "#2c2c2c",       
    "btn_red": "#c62828",         
    "btn_green": "#2e7d32",       
    "btn_pay_cash": "#512da8",    
    "btn_pay_card": "#0277bd",    
    "text_main": "#ffffff",       
    "text_dim": "#aaaaaa",        
    "border": "#424242"           
}

cart = []
held_cart = []
cash_received = 0
current_user = None
login_start = None
user_times = []

# Globals
current_category = "ALL"
ms_win = None
ms_grid_frame = None
ms_cat_frame = None
ms_search_name_var = None
ms_search_code_var = None

CASHIERS = ["CSH1", "CSH2", "ADMIN"]
ADMIN_PIN = "1981"

def disable_event(): pass 
def block_shortcut(event): return "break" 

def enable_scroll(tree):
    tree.bind("<MouseWheel>", lambda e: tree.yview_scroll(int(-1*(e.delta/120)), "units"))
    tree.bind("<Button-4>", lambda e: tree.yview_scroll(-1, "units"))
    tree.bind("<Button-5>", lambda e: tree.yview_scroll(1, "units"))

# ================= PATH MANAGEMENT =================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_DIR, filename)

def init_order_counter():
    trans_path = get_path("transactions.json")
    if os.path.exists(trans_path):
        try:
            with open(trans_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data: return max([t.get("order_num", 0) for t in data])
        except Exception: pass
    return 0

order_counter = init_order_counter() + 1

# ================= AUTO-UPDATER =================
def show_update_prompt(latest_version):
    prompt_win = tk.Toplevel(root)
    prompt_win.attributes("-topmost", True)
    prompt_win.overrideredirect(True)
    prompt_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    prompt_win.geometry("500x250")
    prompt_win.update_idletasks()
    x = (prompt_win.winfo_screenwidth() // 2) - 250
    y = (prompt_win.winfo_screenheight() // 2) - 125
    prompt_win.geometry(f"+{x}+{y}")
    
    tk.Label(prompt_win, text="UPDATE AVAILABLE", font=("Arial", 20, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(30, 10))
    tk.Label(prompt_win, text=f"Version {latest_version} is ready to install.", font=("Arial", 12), bg=THEME["bg_panel"], fg=THEME["text_dim"]).pack(pady=10)
    
    btn_f = tk.Frame(prompt_win, bg=THEME["bg_panel"])
    btn_f.pack(pady=20)
    
    tk.Button(btn_f, text="LATER", font=("Arial", 12, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], width=10, relief="flat", command=prompt_win.destroy).pack(side="left", padx=10)
    def do_update():
        prompt_win.destroy()
        perform_update()
    tk.Button(btn_f, text="UPDATE NOW", font=("Arial", 12, "bold"), bg=THEME["btn_green"], fg="white", width=15, relief="flat", command=do_update).pack(side="left", padx=10)

def check_for_updates():
    try:
        response = requests.get(GITHUB_VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        if latest_version and latest_version != VERSION:
            show_update_prompt(latest_version)
    except Exception: pass 

def perform_update():
    try:
        upd_win = tk.Toplevel()
        upd_win.attributes("-topmost", True)
        upd_win.overrideredirect(True) 
        upd_win.geometry("500x200")
        upd_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
        upd_win.update_idletasks()
        x = (upd_win.winfo_screenwidth() // 2) - 250
        y = (upd_win.winfo_screenheight() // 2) - 100
        upd_win.geometry(f"+{x}+{y}")
        
        tk.Label(upd_win, text="SYSTEM UPDATE", font=("Arial", 20, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(30, 10))
        tk.Label(upd_win, text="Downloading...", font=("Arial", 12), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=5)
        
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
                with open(get_path("README.txt"), 'wb') as f: f.write(readme_req.content)
        except Exception: pass 

        if getattr(sys, 'frozen', False):
            batch_script = get_path("update_swap.bat")
            current_exe = sys.executable
            with open(batch_script, "w", encoding="utf-8") as f:
                f.write(f"""@echo off\ntimeout /t 2 /nobreak > nul\ndel "{current_exe}"\nmove "{update_file}" "{current_exe}"\nstart "" "{current_exe}"\ndel "%~f0"\n""")
            subprocess.Popen([batch_script], shell=True)
            sys.exit()
        else:
            upd_win.destroy()
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit()
    except Exception as e:
        messagebox.showerror("Update Error", f"Failed to download update: {e}")

# ================= DATA LAYER =================
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
            with open(prod_path, "r", encoding="utf-8") as f: data = json.load(f)
            for c in default:
                if c not in data: data[c] = default[c]
            return data
        except Exception: return default
    else:
        with open(prod_path, "w", encoding="utf-8") as f: json.dump(default, f, indent=4)
        return default

products = load_products()

def save_local_session(session_data):
    user_times.append(session_data)
    with open(get_path("sessions.json"), "w", encoding="utf-8") as f: json.dump(user_times, f, indent=4)

def save_local_transaction(sale_data):
    data = []
    trans_path = get_path("transactions.json")
    if os.path.exists(trans_path):
        try:
            with open(trans_path, "r", encoding="utf-8") as f: data = json.load(f)
        except Exception: data = []
    data.append(sale_data)
    with open(trans_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
    with open(get_path("products.json"), "w", encoding="utf-8") as f: json.dump(products, f, indent=4)

def save_expense(etype, reason, amount):
    path = get_path("expenses.json")
    data = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: data = json.load(f)
        except: pass
    data.append({
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "type": etype,
        "reason": reason,
        "amount": amount,
        "user": current_user
    })
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def run_z_report_and_eod():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    export_pkg = {"node_id": f"TILL_{TILL_NUMBER}", "date": today, "transactions": [], "sessions": user_times}
    trans_path = get_path("transactions.json")
    total_cash, total_card = 0, 0
    
    if os.path.exists(trans_path):
        with open(trans_path, "r", encoding="utf-8") as f: 
            export_pkg["transactions"] = json.load(f)
            for t in export_pkg["transactions"]:
                if t["date"] == today:
                    if t["method"] == "CASH": total_cash += t["amount"]
                    elif t["method"] == "CARD": total_card += t["amount"]
    
    gross_total = total_cash + total_card
    z_vat = gross_total * VAT_RATE
    
    z_slip =  f"{STORE_NAME.center(32)}\n"
    z_slip += f"*** END OF DAY Z-REPORT ***".center(32) + "\n"
    z_slip += "=" * 32 + "\n"
    z_slip += f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    z_slip += f"Till: {TILL_NUMBER}   |   Printed By: {current_user}\n"
    z_slip += "-" * 32 + "\n"
    z_slip += f"TOTAL CASH:            R{total_cash:>7.2f}\n"
    z_slip += f"TOTAL CARD SALES:      R{total_card:>7.2f}\n"
    z_slip += "-" * 32 + "\n"
    z_slip += f"GROSS REVENUE:         R{gross_total:>7.2f}\n"
    z_slip += f"TOTAL VAT COLLECTED:   R{z_vat:>7.2f}\n"
    z_slip += "=" * 32 + "\n\n\n\n"
    
    print_receipt_silent(z_slip)
    eod_filename = get_path(f"EOD_PUSH_{today}.json")
    with open(eod_filename, "w", encoding="utf-8") as f: json.dump(export_pkg, f, indent=4)
    return eod_filename

if os.path.exists(get_path("sessions.json")):
    try:
        with open(get_path("sessions.json"), "r", encoding="utf-8") as f: user_times = json.load(f)
    except Exception: user_times = []

# ================= CORE LOGIC =================
def raw_total(): 
    return sum(i["price"] * i["qty"] for i in cart)

def update_cart_ui():
    for item in cart_tree.get_children():
        cart_tree.delete(item)
        
    for i in cart:
        line_tot = i["price"] * i["qty"]
        cart_tree.insert("", "end", values=(i["code"], i["qty"], i["name"], f"{i['price']:.2f}", f"{line_tot:.2f}"))
        
    final_tot = raw_total()
    total_val_lbl.config(text=f"R{final_tot:.2f}")
    
    if cart:
        if cash_received < final_tot:
            sub_val_lbl.config(text=f"DUE R{final_tot - cash_received:.2f}", fg=THEME["brand_red"])
        else:
            change = max(0, cash_received - final_tot)
            sub_val_lbl.config(text=f"CHG R{change:.2f}", fg=THEME["lcd_fg"])
    else:
        sub_val_lbl.config(text="CHG R0.00", fg=THEME["text_main"])
        
    prev_inv_lbl.config(text=f"Prev. Invoice #{order_counter}")

def add_product(code):
    barcode_entry.delete(0, tk.END)
    
    if code not in products:
        messagebox.showerror("Error", "Product Code Not Found")
        barcode_entry.focus_set()
        return
    if products[code]["stock"] <= 0:
        messagebox.showwarning("Stock", "Out of stock!")
        barcode_entry.focus_set()
        return
        
    p = products[code]
    for i in cart:
        if i["code"] == code:
            i["qty"] += 1
            p["stock"] -= 1
            update_cart_ui()
            last_scan_lbl.config(text=f"ADDED: {p['name']} | STOCK: {p['stock']} | PRICE: R{p['price']:.2f}", fg=THEME["lcd_fg"])
            barcode_entry.focus_set()
            return
            
    cart.append({"code": code, "name": p["name"], "price": p["price"], "qty": 1})
    p["stock"] -= 1
    update_cart_ui()
    last_scan_lbl.config(text=f"ADDED: {p['name']} | STOCK: {p['stock']} | PRICE: R{p['price']:.2f}", fg=THEME["lcd_fg"])
    barcode_entry.focus_set()

def void_item(event=None):
    sel = cart_tree.selection()
    if not sel: 
        messagebox.showinfo("Select Item", "Please select an item in the list to void.")
        barcode_entry.focus_set()
        return
        
    if current_user != "ADMIN":
        pw = custom_input("Manager Override", "Enter Admin PIN", is_password=True)
        if pw != ADMIN_PIN:
            messagebox.showerror("Error", "Manager override failed")
            barcode_entry.focus_set()
            return
        
    item_id = sel[0]
    idx = cart_tree.index(item_id)
    
    item = cart.pop(idx)
    products[item["code"]]["stock"] += item["qty"]
    update_cart_ui()
    barcode_entry.focus_set()

def clear_cart():
    if not cart: return
    if messagebox.askyesno("Confirm", "Clear the entire sales order?"):
        for item in cart:
            products[item["code"]]["stock"] += item["qty"]
        cart.clear()
        global cash_received
        cash_received = 0
        update_cart_ui()
        last_scan_lbl.config(text="READY TO SCAN", fg=THEME["text_dim"])
    barcode_entry.focus_set()

def toggle_hold_cart(mode):
    global held_cart, cart, cash_received
    if mode == "SAVE":
        if cart:
            if held_cart:
                messagebox.showwarning("Hold Error", "A cart is already saved! Recall it first.")
            else:
                held_cart = cart.copy()
                cart.clear()
                cash_received = 0
                update_cart_ui()
                last_scan_lbl.config(text="CART ON HOLD", fg=THEME["text_dim"])
    elif mode == "LOAD":
        if held_cart:
            cart = held_cart.copy()
            held_cart.clear()
            update_cart_ui()
            last_scan_lbl.config(text="CART RECALLED", fg=THEME["lcd_fg"])
        else:
            messagebox.showinfo("Load", "No saved sales.")
    barcode_entry.focus_set()

def add_cash(amount):
    global cash_received
    cash_received += amount
    update_cart_ui()
    barcode_entry.focus_set()

def generate_receipt_text(method, final_tot):
    vat_amt = final_tot * VAT_RATE
    excl_vat = final_tot - vat_amt
    
    r = "=" * 32 + "\n"
    r += f"{STORE_NAME.center(32)}\n"
    for line in STORE_ADDRESS.split('\n'):
        r += f"{line.center(32)}\n"
    r += f"VAT No: 4123456789".center(32) + "\n"
    r += "-" * 32 + "\n"
    r += f"Receipt: #{order_counter:<10} Till: {TILL_NUMBER}\n"
    r += f"Cashier: [{current_user}]\n"
    r += f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    r += "-" * 32 + "\n"
    r += f"{'QTY ITEM':<22} {'TOTAL':>9}\n"
    
    for i in cart:
        name = (i["name"][:13] + "..") if len(i["name"]) > 15 else i["name"][:15]
        line_tot = i["price"] * i["qty"]
        r += f"{i['qty']:<2}x {name:<16} R{line_tot:>8.2f}\n"
        
    r += "-" * 32 + "\n"
    r += f"TOTAL DUE:             R{final_tot:>7.2f}\n"
    slip_method = "PAY CARD" if method == "CARD" else "CASH SALE"
    r += f"PAID VIA:             {slip_method:>9}\n"
    
    if method == "CASH":
        r += f"CASH TENDERED:         R{cash_received:>7.2f}\n"
        r += f"CHANGE DUE:            R{max(0, cash_received - final_tot):>7.2f}\n"
        
    r += "-" * 32 + "\n"
    r += "VAT SUMMARY".center(32) + "\n"
    r += f"Total Excl VAT:        R{excl_vat:>7.2f}\n"
    r += f"VAT @ 15%:             R{vat_amt:>7.2f}\n"
    r += f"Total Incl VAT:        R{final_tot:>7.2f}\n"
    r += "=" * 32 + "\n"
    r += "THANK YOU FOR YOUR BUSINESS!".center(32) + "\n"
    r += "PLEASE RETAIN YOUR SLIP".center(32) + "\n"
    r += "-" * 32 + "\n"
    r += "Goods returnable within 7 days".center(32) + "\n"
    r += "with original receipt. E&OE.".center(32) + "\n"
    r += "Subject to store policy.".center(32) + "\n\n\n\n"
    return r

def process_payment(method):
    global order_counter, cash_received
    if not cart: return
    
    final_tot = raw_total()
    
    if method == "CASH" and cash_received == 0:
        amt_str = custom_input("Cash Tendered", "Enter exact cash received:")
        try:
            amt = float(amt_str)
            cash_received = amt
        except:
            barcode_entry.focus_set()
            return
            
    if method == "CASH" and cash_received < final_tot:
        messagebox.showwarning("Payment", f"Insufficient Cash!\nDUE: R{final_tot - cash_received:.2f}")
        barcode_entry.focus_set()
        return
    
    now = datetime.datetime.now()
    change_amt = max(0, cash_received - final_tot) if method == "CASH" else 0
    
    sale = {
        "id": now.strftime("%Y%m%d%H%M%S"),
        "order_num": order_counter,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "cashier": current_user,
        "method": method,
        "amount": final_tot,
        "change": change_amt,
        "items": cart.copy()
    }
    
    save_local_transaction(sale)
    receipt_txt = generate_receipt_text(method, final_tot)
    print_receipt_silent(receipt_txt)
    
    cart.clear()
    cash_received = 0
    order_counter = (order_counter % 999) + 1 
    update_cart_ui()
    last_scan_lbl.config(text="READY TO SCAN", fg=THEME["text_dim"])
    barcode_entry.focus_set()

def print_receipt_silent(text):
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", dir=BASE_DIR)
        with os.fdopen(fd, 'w', encoding="utf-8") as f: f.write(text)
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(0, "print", tmp, None, ".", 0)
        else:
            subprocess.run(["lp", tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e: print(f"Print error: {e}")

# ================= MODALS & INPUTS =================
def custom_input(title, prompt, is_password=False):
    win = tk.Toplevel()
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)
    win.configure(bg=THEME["bg_panel"], bd=1, relief="solid")
    win.geometry("500x300")
    win.title(title)
    win.grab_set(); win.attributes("-topmost", True)
    
    tk.Label(win, text=prompt, font=("Arial", 16, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=30)
    entry = tk.Entry(win, font=("Arial", 28), show="*" if is_password else "", justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], bd=0, relief="flat")
    entry.pack(pady=10, fill="x", padx=60); entry.focus_set()
    
    res = {"val": None}
    def submit(event=None): res["val"] = entry.get(); win.destroy()
    def cancel(): win.destroy()
        
    entry.bind("<Return>", submit)
    
    btn_frame = tk.Frame(win, bg=THEME["bg_panel"])
    btn_frame.pack(pady=30)
    tk.Button(btn_frame, text="CANCEL", font=("Arial", 12, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], width=12, height=2, relief="flat", command=cancel).pack(side="left", padx=10)
    tk.Button(btn_frame, text="CONFIRM", font=("Arial", 12, "bold"), bg=THEME["btn_green"], fg="white", width=12, height=2, relief="flat", command=submit).pack(side="left", padx=10)
    win.wait_window()
    return res["val"]

def open_manual_select():
    global ms_win, ms_grid_frame, ms_cat_frame, current_category
    global ms_search_name_var, ms_search_code_var
    if ms_win and ms_win.winfo_exists():
        ms_win.lift()
        return

    ms_win = tk.Toplevel(root)
    ms_win.attributes("-topmost", True)
    ms_win.overrideredirect(True)
    ms_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    
    w, h = 900, 650
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    ms_win.geometry(f"{w}x{h}+{x}+{y}")
    ms_win.grab_set()

    hdr = tk.Frame(ms_win, bg=THEME["brand_red"])
    hdr.pack(fill="x")
    tk.Label(hdr, text="MANUAL PRODUCT SELECT", font=("Arial", 16, "bold"), fg="white", bg=THEME["brand_red"]).pack(side="left", padx=20, pady=10)
    tk.Button(hdr, text="CLOSE", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"], relief="flat", command=ms_win.destroy).pack(side="right", padx=10, pady=5)

    search_frame = tk.Frame(ms_win, bg=THEME["bg_panel"])
    search_frame.pack(fill="x", padx=20, pady=10)
    search_frame.columnconfigure(1, weight=1); search_frame.columnconfigure(3, weight=1)

    ms_search_name_var = tk.StringVar(); ms_search_code_var = tk.StringVar()

    tk.Label(search_frame, text="🔍 Name:", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    e1 = tk.Entry(search_frame, textvariable=ms_search_name_var, font=("Arial", 16), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat")
    e1.grid(row=0, column=1, sticky="ew", padx=5)
    e1.bind("<KeyRelease>", lambda e: refresh_ms_grid())

    tk.Label(search_frame, text="🔍 Barcode:", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).grid(row=0, column=2, padx=(20,5), pady=5, sticky="w")
    e2 = tk.Entry(search_frame, textvariable=ms_search_code_var, font=("Arial", 16), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat")
    e2.grid(row=0, column=3, sticky="ew", padx=5)
    e2.bind("<KeyRelease>", lambda e: refresh_ms_grid())

    ms_cat_frame = tk.Frame(ms_win, bg=THEME["bg_panel"])
    ms_cat_frame.pack(fill="x", padx=20, pady=5)
    
    ms_grid_frame = tk.Frame(ms_win, bg=THEME["bg_panel"])
    ms_grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
    for c in range(4): ms_grid_frame.columnconfigure(c, weight=1, uniform="msgroup")

    def set_cat(cat):
        global current_category
        current_category = cat
        refresh_ms_grid()

    def refresh_ms_grid():
        for widget in ms_grid_frame.winfo_children(): widget.destroy()
        for widget in ms_cat_frame.winfo_children(): widget.destroy()

        cats = ["ALL", "MEAT", "SNACKS", "VEG", "DRINK"]
        for c in cats:
            bg_c = THEME["btn_green"] if c == current_category else THEME["btn_grey"]
            tk.Button(ms_cat_frame, text=c, font=("Arial", 12, "bold"), bg=bg_c, fg="white", height=2, width=12, relief="flat", command=lambda ct=c: set_cat(ct)).pack(side="left", padx=5)

        row, col = 0, 0
        search_n = ms_search_name_var.get().lower().strip()
        search_c = ms_search_code_var.get().lower().strip()

        for code, p in products.items():
            cat_match = (current_category == "ALL") or (p["cat"].upper() == current_category)
            name_match = search_n in p["name"].lower() if search_n else True
            code_match = search_c in code.lower() if search_c else True

            if cat_match and name_match and code_match:
                btn = tk.Button(ms_grid_frame, text=f"{p['name']}\nR{p['price']:.2f}\n[{p['stock']}]", font=("Arial", 12, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=lambda c=code: [add_product(c), ms_win.destroy()])
                btn.grid(row=row, column=col, padx=8, pady=8, sticky="nsew", ipady=20)
                col += 1
                if col > 3: col = 0; row += 1

    refresh_ms_grid()

def open_markdown():
    sel = cart_tree.selection()
    if not sel: 
        messagebox.showinfo("Select", "Please select an item in the cart to markdown.")
        return
        
    if current_user != "ADMIN":
        pw = custom_input("Manager Override", "Enter Admin PIN:", is_password=True)
        if pw != ADMIN_PIN: return
    
    idx = cart_tree.index(sel[0])
    current_item = cart[idx]

    md_win = tk.Toplevel(root)
    md_win.attributes("-topmost", True)
    md_win.overrideredirect(True)
    md_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    
    w, h = 320, 280
    md_win.geometry(f"{w}x{h}+20+{768 - h - 60}")

    tk.Label(md_win, text=f"MARKDOWN: {current_item['name'][:12]}", font=("Arial", 14, "bold"), bg=THEME["brand_red"], fg="white").pack(fill="x", pady=(0,15), ipady=5)

    tk.Label(md_win, text="Enter New Price (R):", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack()
    price_var = tk.StringVar()
    tk.Entry(md_win, textvariable=price_var, font=("Arial", 18, "bold"), justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat").pack(pady=5, fill="x", padx=40)

    tk.Label(md_win, text="OR Discount (%):", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(10,0))
    perc_var = tk.StringVar()
    tk.Entry(md_win, textvariable=perc_var, font=("Arial", 18, "bold"), justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat").pack(pady=5, fill="x", padx=40)

    def apply_md():
        p_val = price_var.get()
        pct_val = perc_var.get()
        try:
            if pct_val:
                discount = float(pct_val)
                new_price = current_item["price"] * (1 - (discount/100))
                cart[idx]["price"] = round(new_price, 2)
            elif p_val:
                cart[idx]["price"] = float(p_val)
            update_cart_ui()
            md_win.destroy()
            barcode_entry.focus_set()
        except: pass

    btn_f = tk.Frame(md_win, bg=THEME["bg_panel"])
    btn_f.pack(pady=15, fill="x")
    tk.Button(btn_f, text="CANCEL", font=("Arial", 10, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], command=lambda:[md_win.destroy(), barcode_entry.focus_set()], height=2, width=10, relief="flat").pack(side="left", padx=15)
    tk.Button(btn_f, text="APPLY", font=("Arial", 10, "bold"), bg=THEME["btn_green"], fg="white", command=apply_md, height=2, width=10, relief="flat").pack(side="right", padx=15)

def open_2nd_functions():
    win = tk.Toplevel()
    win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    win.overrideredirect(True) 
    w, h = 400, 180
    win.geometry(f"{w}x{h}+20+{768 - h - 60}")
    win.grab_set(); win.attributes("-topmost", True)

    tk.Label(win, text="2ND FUNCTIONS", font=("Arial", 16, "bold"), bg=THEME["brand_red"], fg="white").pack(fill="x", pady=(0, 15), ipady=5)

    def do_payout():
        amt = custom_input("PAY OUT", "Enter Amount to Pay Out:")
        if amt:
            reason = custom_input("PAY OUT", "Enter Reason for Pay Out:")
            if reason:
                try:
                    save_expense("PAY OUT", reason, float(amt))
                    messagebox.showinfo("Success", f"Pay Out of R{float(amt):.2f} logged.")
                    win.destroy()
                except: messagebox.showerror("Error", "Invalid amount entered.")

    tk.Button(win, text="💸 PAY OUT", font=("Arial", 14, "bold"), bg=THEME["btn_pay_card"], fg="white", height=2, relief="flat", command=do_payout).pack(fill="x", padx=40, pady=5)
    tk.Button(win, text="CLOSE", font=("Arial", 12, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], height=2, relief="flat", command=win.destroy).pack(fill="x", padx=40, pady=(15, 0))

# ================= PROFESSIONAL ADMIN PANEL & HTML EXPORT =================
def admin_panel():
    if current_user != "ADMIN": return
    
    win = tk.Toplevel(); win.attributes("-fullscreen", True); win.configure(bg=THEME["bg_main"])
    win.protocol("WM_DELETE_WINDOW", disable_event); win.bind("<Alt-F4>", block_shortcut)

    # Modern Sidebar
    sidebar = tk.Frame(win, bg="#1a1a1a", width=280); sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
    tk.Label(sidebar, text="🥩\nADMIN SUITE", font=("Arial", 26, "bold"), fg=THEME["brand_red"], bg="#1a1a1a").pack(pady=40)

    content = tk.Frame(win, bg=THEME["bg_main"]); content.pack(side="right", fill="both", expand=True)
    
    dash_f = tk.Frame(content, bg=THEME["bg_main"]); inv_f = tk.Frame(content, bg=THEME["bg_main"])
    staff_f = tk.Frame(content, bg=THEME["bg_main"]); pay_f = tk.Frame(content, bg=THEME["bg_main"])
    for f in (dash_f, inv_f, staff_f, pay_f): f.place(relx=0, rely=0, relwidth=1, relheight=1)

    def show_frame(f): f.tkraise()

    nav_f = ("Arial", 14, "bold")
    tk.Button(sidebar, text="DASHBOARD", font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(dash_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="INVENTORY", font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(inv_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="STAFF LOGS", font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(staff_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="PAY OUTS", font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(pay_f)).pack(fill="x", pady=2)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    total_day, total_cash, total_card = 0, 0, 0
    t_data = []
    if os.path.exists(get_path("transactions.json")):
        try:
            with open(get_path("transactions.json"), "r", encoding="utf-8") as f: t_data = json.load(f)
            for t in t_data:
                if t["date"] == today:
                    total_day += t["amount"]
                    if t["method"] == "CASH": total_cash += t["amount"]
                    elif t["method"] == "CARD": total_card += t["amount"]
        except: pass

    # Apply modern row heights and alternating colors to Admin Treeviews
    admin_style = ttk.Style()
    admin_style.configure("Admin.Treeview", rowheight=40, font=("Arial", 13), background=THEME["bg_panel"], fieldbackground=THEME["bg_panel"], foreground=THEME["text_main"], borderwidth=0)
    admin_style.configure("Admin.Treeview.Heading", font=("Arial", 12, "bold"), background="#1a1a1a", foreground=THEME["text_main"], relief="flat")
    admin_style.map("Admin.Treeview", background=[('selected', THEME["brand_red"])])

    # --- DASHBOARD TAB (Hierarchical Table) ---
    tk.Label(dash_f, text="TODAY'S SALES OVERVIEW", font=("Arial", 22, "bold"), bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30, 5))
    tk.Label(dash_f, text=f"GROSS: R{total_day:.2f}  |  CASH: R{total_cash:.2f}  |  CARD: R{total_card:.2f}", font=("Arial", 16, "bold"), bg=THEME["bg_main"], fg=THEME["text_main"]).pack(pady=10)

    tree_f = tk.Frame(dash_f, bg=THEME["bg_main"]); tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    
    # "tree headings" natively enables the expand dropdown arrow in the #0 column
    admin_tree = ttk.Treeview(tree_f, columns=("Order", "Time", "Qty", "Amount", "Change", "Method"), show="tree headings", style="Admin.Treeview")
    admin_tree.heading("#0", text=""); admin_tree.column("#0", width=40, stretch=False, anchor="center")
    admin_tree.heading("Order", text="ORDER / ITEM"); admin_tree.column("Order", width=250, anchor="w")
    admin_tree.heading("Time", text="TIME"); admin_tree.column("Time", width=120, anchor="center")
    admin_tree.heading("Qty", text="QTY"); admin_tree.column("Qty", width=80, anchor="center")
    admin_tree.heading("Amount", text="AMOUNT"); admin_tree.column("Amount", width=120, anchor="e")
    admin_tree.heading("Change", text="CHANGE"); admin_tree.column("Change", width=120, anchor="e")
    admin_tree.heading("Method", text="METHOD"); admin_tree.column("Method", width=120, anchor="center")
    
    admin_tree.tag_configure('evenrow', background='#1e1e1e')
    admin_tree.tag_configure('oddrow', background='#2a2a2a')
    
    admin_tree.pack(fill="both", expand=True); enable_scroll(admin_tree)

    for idx, t in enumerate(reversed(t_data)):
        if t["date"] == today:
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            total_qty = sum(i["qty"] for i in t.get("items", []))
            
            # Insert Parent Row (The Order)
            parent = admin_tree.insert("", "end", text="", values=(
                f"#{t.get('order_num')}", t['time'], total_qty, f"R{t['amount']:.2f}", f"R{t.get('change', 0):.2f}", t['method']
            ), tags=(tag,))
            
            # Insert Child Rows (The Items) inside the dropdown
            for item in t.get("items", []):
                admin_tree.insert(parent, "end", text="", values=(
                    f"↳ {item['name']}", "", item['qty'], f"R{item['price']*item['qty']:.2f}", "", ""
                ), tags=(tag,))

    # --- INVENTORY TAB ---
    tk.Label(inv_f, text="CURRENT INVENTORY LEVELS", font=("Arial", 22, "bold"), bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30, 20))
    inv_tree_f = tk.Frame(inv_f, bg=THEME["bg_main"]); inv_tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    
    inv_tree = ttk.Treeview(inv_tree_f, columns=("Code", "Name", "Price", "Stock"), show="headings", style="Admin.Treeview")
    inv_tree.heading("Code", text="STOCK CODE"); inv_tree.column("Code", width=100, anchor="center")
    inv_tree.heading("Name", text="PRODUCT NAME"); inv_tree.column("Name", width=400, anchor="w")
    inv_tree.heading("Price", text="UNIT PRICE"); inv_tree.column("Price", width=150, anchor="e")
    inv_tree.heading("Stock", text="ON HAND"); inv_tree.column("Stock", width=150, anchor="center")
    
    inv_tree.tag_configure('evenrow', background='#1e1e1e')
    inv_tree.tag_configure('oddrow', background='#2a2a2a')
    
    inv_tree.pack(fill="both", expand=True); enable_scroll(inv_tree)

    for idx, (code, p) in enumerate(products.items()):
        tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
        inv_tree.insert("", "end", values=(code, p["name"], f"R{p['price']:.2f}", p["stock"]), tags=(tag,))

    # --- STAFF LOGS TAB ---
    tk.Label(staff_f, text="TODAY'S CASHIER LOGS", font=("Arial", 22, "bold"), bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30, 20))
    staff_tree_f = tk.Frame(staff_f, bg=THEME["bg_main"]); staff_tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    
    staff_tree = ttk.Treeview(staff_tree_f, columns=("User", "Login", "Logout", "Hours"), show="headings", style="Admin.Treeview")
    staff_tree.heading("User", text="CASHIER ID"); staff_tree.column("User", width=150, anchor="center")
    staff_tree.heading("Login", text="LOGIN TIME"); staff_tree.column("Login", width=200, anchor="center")
    staff_tree.heading("Logout", text="LOGOUT TIME"); staff_tree.column("Logout", width=200, anchor="center")
    staff_tree.heading("Hours", text="HOURS LOGGED"); staff_tree.column("Hours", width=150, anchor="center")
    
    staff_tree.tag_configure('evenrow', background='#1e1e1e')
    staff_tree.tag_configure('oddrow', background='#2a2a2a')

    staff_tree.pack(fill="both", expand=True); enable_scroll(staff_tree)

    for idx, s in enumerate(user_times):
        if s['date'] == today:
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            staff_tree.insert("", "end", values=(s["user"], s["login"], s.get("logout", "ACTIVE"), s.get("hours", 0)), tags=(tag,))

    # --- PAY OUTS TAB ---
    tk.Label(pay_f, text="PAY OUTS LEDGER", font=("Arial", 22, "bold"), bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30, 20))
    pay_tree_f = tk.Frame(pay_f, bg=THEME["bg_main"]); pay_tree_f.pack(fill="both", expand=True, padx=40, pady=10)

    pay_tree = ttk.Treeview(pay_tree_f, columns=("Date", "Time", "Reason", "Amount", "User"), show="headings", style="Admin.Treeview")
    pay_tree.heading("Date", text="DATE"); pay_tree.column("Date", width=120, anchor="center")
    pay_tree.heading("Time", text="TIME"); pay_tree.column("Time", width=100, anchor="center")
    pay_tree.heading("Reason", text="REASON"); pay_tree.column("Reason", width=350, anchor="w")
    pay_tree.heading("Amount", text="AMOUNT"); pay_tree.column("Amount", width=120, anchor="e")
    pay_tree.heading("User", text="TILL / USER"); pay_tree.column("User", width=120, anchor="center")

    pay_tree.tag_configure('evenrow', background='#1e1e1e')
    pay_tree.tag_configure('oddrow', background='#2a2a2a')

    pay_tree.pack(fill="both", expand=True); enable_scroll(pay_tree)

    exp_data = []
    if os.path.exists(get_path("expenses.json")):
        try:
            with open(get_path("expenses.json"), "r", encoding="utf-8") as f: exp_data = json.load(f)
        except: pass

    for idx, ex in enumerate(reversed(exp_data)):
        tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
        pay_tree.insert("", "end", values=(ex["date"], ex["time"], ex["reason"], f"R{ex['amount']:.2f}", ex["user"]), tags=(tag,))

    def export_professional_report():
        filename = get_path(f"Daily_Report_{today}.html")
        try:
            html_content = f"""
            <html>
            <head>
                <title>Eat Sum Meat - Daily Report</title>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
                    .container {{ max-width: 1000px; margin: auto; background: white; padding: 30px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                    .header {{ background-color: {THEME['brand_red']}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    h1 {{ margin: 0; font-size: 28px; }}
                    h2 {{ color: {THEME['brand_red']}; border-bottom: 2px solid {THEME['brand_red']}; padding-bottom: 5px; margin-top: 40px; }}
                    .summary-grid {{ display: flex; justify-content: space-between; margin: 20px 0; }}
                    .card {{ background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 5px solid {THEME['brand_red']}; width: 30%; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
                    .card h3 {{ margin: 0 0 10px 0; color: #555; font-size: 16px; text-transform: uppercase; }}
                    .card p {{ margin: 0; font-size: 24px; font-weight: bold; color: #222; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
                    th, td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: left; }}
                    th {{ background-color: {THEME['brand_red']}; color: white; font-weight: bold; text-transform: uppercase; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    tr:hover {{ background-color: #f1f1f1; }}
                    .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #777; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🥩 EAT SUM MEAT POS</h1>
                        <p>Executive Daily Machine Report | Date: {today}</p>
                    </div>
                    
                    <h2>DAILY FINANCIAL SUMMARY</h2>
                    <div class="summary-grid">
                        <div class="card"><h3>Gross Revenue</h3><p>R{total_day:.2f}</p></div>
                        <div class="card" style="border-left-color: {THEME['btn_pay_cash']}"><h3>Total Cash</h3><p>R{total_cash:.2f}</p></div>
                        <div class="card" style="border-left-color: {THEME['btn_pay_card']}"><h3>Total Card</h3><p>R{total_card:.2f}</p></div>
                    </div>

                    <h2>TRANSACTION LOG</h2>
                    <table>
                        <tr><th>Order #</th><th>Time</th><th>Method</th><th>Total Amount</th><th>Items Sold</th></tr>
            """
            for t in t_data:
                if t["date"] == today:
                    items = "<br>".join([f"&bull; {i['qty']}x {i['name']}" for i in t.get("items", [])])
                    html_content += f"<tr><td>#{t.get('order_num')}</td><td>{t['time']}</td><td>{t['method']}</td><td><b>R{t['amount']:.2f}</b></td><td>{items}</td></tr>"
            
            html_content += """
                    </table>
                    
                    <h2>CASHIER SHIFT LOGS</h2>
                    <table>
                        <tr><th>User ID</th><th>Login Time</th><th>Logout Time</th><th>Hours Logged</th></tr>
            """
            for s in user_times:
                if s['date'] == today:
                    html_content += f"<tr><td>{s['user']}</td><td>{s['login']}</td><td>{s['logout']}</td><td>{s['hours']} hrs</td></tr>"
                    
            html_content += f"""
                    </table>
                    <div class="footer">Report generated securely by Eat Sum Meat POS System V{VERSION}</div>
                </div>
            </body>
            </html>
            """
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            webbrowser.open('file://' + os.path.realpath(filename))
            messagebox.showinfo("Success", f"Professional Executive Report generated and opened in your browser!\n\nSaved at: {filename}")
            
        except Exception as e: messagebox.showerror("Export Error", f"Failed to generate report: {str(e)}")

    def trigger_eod():
        if messagebox.askyesno("Confirm", "Print Z-Report?"): run_z_report_and_eod()
            
    tk.Button(sidebar, text="📄 HTML EXPORT", font=nav_f, bg=THEME["btn_pay_card"], fg="white", pady=15, relief="flat", command=export_professional_report).pack(fill="x", side="bottom", pady=2, padx=10)
    tk.Button(sidebar, text="🖨️ Z-REPORT", font=nav_f, bg=THEME["btn_green"], fg="white", pady=15, relief="flat", command=trigger_eod).pack(fill="x", side="bottom", pady=2, padx=10)
    tk.Button(sidebar, text="❌ EXIT APP", font=nav_f, bg=THEME["btn_red"], fg="white", pady=15, relief="flat", command=sys.exit).pack(fill="x", side="bottom", pady=20, padx=10)
    tk.Button(sidebar, text="⬅️ BACK TO TILL", font=nav_f, bg=THEME["btn_white"], fg=THEME["text_main"], pady=15, relief="flat", command=win.destroy).pack(fill="x", side="bottom", pady=2, padx=10)

    show_frame(dash_f)

# ================= LOGIN =================
def login_screen():
    global current_user, login_start
    win = tk.Toplevel(); win.configure(bg=THEME["bg_main"])
    win.attributes("-fullscreen", True); win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", disable_event); win.bind("<Alt-F4>", block_shortcut)
    
    card = tk.Frame(win, bg=THEME["bg_panel"], bd=1, relief="solid")
    card.place(relx=0.5, rely=0.5, anchor="center", width=500, height=380)
    
    tk.Label(card, text="🥩 EAT SUM MEAT 🥩", font=("Arial", 28, "bold"), fg=THEME["brand_red"], bg=THEME["bg_panel"]).pack(pady=(40, 5))
    tk.Label(card, text="SYSTEM LOGIN", font=("Arial", 16, "bold"), fg=THEME["text_dim"], bg=THEME["bg_panel"]).pack(pady=(0, 20))
    
    ent = tk.Entry(card, font=("Arial", 30), justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=0)
    ent.pack(pady=10, ipady=10); ent.focus_set()
    
    def do_login(event=None):
        global current_user, login_start
        c = ent.get().strip().upper()
        if c in CASHIERS:
            current_user = c
            login_start = time.time()
            user_lbl.config(text=f"Username: {current_user}")
            
            if current_user == "ADMIN":
                admin_btn.pack(side="right", padx=10, ipady=4)
            else:
                admin_btn.pack_forget()
                
            win.destroy()
            barcode_entry.focus_set() 
        else:
            messagebox.showerror("Error", "Invalid Code")
            ent.delete(0, tk.END)
            
    ent.bind("<Return>", do_login)
    tk.Button(card, text="AUTHORIZE", font=("Arial", 16, "bold"), bg=THEME["btn_green"], fg="white", width=15, relief="flat", command=do_login).pack(pady=20)
    win.wait_window()

def logoff():
    global current_user, login_start
    if cart or held_cart:
        messagebox.showwarning("Warning", "Clear or Hold active sales first.")
        return
    if current_user and login_start:
        save_local_session({"date": datetime.datetime.now().strftime("%Y-%m-%d"), "user": current_user, "login": datetime.datetime.fromtimestamp(login_start).strftime("%H:%M:%S"), "logout": datetime.datetime.now().strftime("%H:%M:%S"), "hours": 0})
        current_user, login_start = None, None
        user_lbl.config(text="Username: LOCKED")
        login_screen()

# ================= MAIN UI LAYOUT (DARK MODE GRID) =================
root = tk.Tk()
root.attributes("-fullscreen", True)
root.geometry("1024x768")
root.resizable(False, False)
root.configure(bg=THEME["bg_main"])
root.protocol("WM_DELETE_WINDOW", disable_event)
root.bind("<Alt-F4>", block_shortcut)

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", background=THEME["bg_panel"], fieldbackground=THEME["bg_panel"], foreground=THEME["text_main"], font=("Arial", 14), rowheight=35, borderwidth=0)
style.configure("Treeview.Heading", background=THEME["btn_grey"], foreground=THEME["text_main"], font=("Arial", 12, "bold"), relief="flat", borderwidth=1)
style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])

left_col = tk.Frame(root, bg=THEME["bg_main"], width=600, height=768)
left_col.place(x=0, y=0); left_col.pack_propagate(False)

right_col = tk.Frame(root, bg=THEME["bg_main"], width=424, height=768)
right_col.place(x=600, y=0); right_col.pack_propagate(False)

# ====== LEFT COLUMN ======
top_tot_f = tk.Frame(left_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=140)
top_tot_f.pack(fill="x", padx=5, pady=5); top_tot_f.pack_propagate(False)

tk.Label(top_tot_f, text="TOTAL:", font=("Arial", 32, "bold"), bg=THEME["bg_panel"], fg=THEME["brand_red"]).place(x=20, y=20)

total_val_lbl = tk.Label(top_tot_f, text="R0.00", font=("Consolas", 42, "bold"), bg=THEME["lcd_bg"], fg=THEME["lcd_fg"], bd=0, anchor="e", width=12)
total_val_lbl.place(x=180, y=10)

# Shifted sub_val_lbl to the left and increased width significantly to handle huge amounts
sub_val_lbl = tk.Label(top_tot_f, text="CHG R0.00", font=("Arial", 24, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"], anchor="e")
sub_val_lbl.place(x=250, y=85, width=330)

cart_f = tk.Frame(left_col, bd=1, relief="solid", height=380)
cart_f.pack(fill="x", padx=5, pady=0); cart_f.pack_propagate(False)

cols = ("Code", "Qty", "Description", "Unit Price", "Amount")
cart_tree = ttk.Treeview(cart_f, columns=cols, show="headings", selectmode="browse")
cart_tree.heading("Code", text="CODE"); cart_tree.column("Code", width=90, anchor="center")
cart_tree.heading("Qty", text="QTY"); cart_tree.column("Qty", width=50, anchor="center")
cart_tree.heading("Description", text="DESCRIPTION"); cart_tree.column("Description", width=250, anchor="w")
cart_tree.heading("Unit Price", text="PRICE"); cart_tree.column("Unit Price", width=90, anchor="e")
cart_tree.heading("Amount", text="TOTAL"); cart_tree.column("Amount", width=90, anchor="e")
cart_tree.pack(fill="both", expand=True)

l_actions_f = tk.Frame(left_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=180)
l_actions_f.pack(fill="x", padx=5, pady=5); l_actions_f.pack_propagate(False)

btn_font = ("Arial", 11, "bold")
btn_pad = {'padx': 4, 'pady': 4, 'sticky': 'nsew'}
for i in range(2): l_actions_f.rowconfigure(i, weight=1)
for i in range(6): l_actions_f.columnconfigure(i, weight=1)

# Action Row 1
tk.Button(l_actions_f, text="↑", font=("Arial", 16, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat").grid(row=0, column=0, **btn_pad)
tk.Button(l_actions_f, text="↓", font=("Arial", 16, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat").grid(row=0, column=1, **btn_pad)
tk.Button(l_actions_f, text="VOID\nITEM", font=btn_font, bg=THEME["btn_red"], fg="white", relief="flat", command=void_item).grid(row=0, column=2, **btn_pad)
tk.Button(l_actions_f, text="HOLD\nSALE", font=btn_font, bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=lambda: toggle_hold_cart("SAVE")).grid(row=0, column=3, **btn_pad)
tk.Button(l_actions_f, text="RECALL\nSALE", font=btn_font, bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=lambda: toggle_hold_cart("LOAD")).grid(row=0, column=4, **btn_pad)
tk.Button(l_actions_f, text="CLEAR\nCART", font=btn_font, bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=1, command=clear_cart).grid(row=0, column=5, **btn_pad)

# Action Row 2
tk.Button(l_actions_f, text="QTY", font=("Arial", 12, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat").grid(row=1, column=0, **btn_pad)
tk.Button(l_actions_f, text="MARK\nDOWN", font=btn_font, bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=open_markdown).grid(row=1, column=1, **btn_pad)
tk.Button(l_actions_f, text="MANUAL\nSELECT", font=btn_font, bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=1, command=open_manual_select).grid(row=1, column=2, **btn_pad)
tk.Button(l_actions_f, text="LOG OFF", font=btn_font, bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=1, command=logoff).grid(row=1, column=3, **btn_pad)
tk.Button(l_actions_f, text="REFUND", font=btn_font, bg=THEME["btn_red"], fg="white", relief="flat").grid(row=1, column=4, **btn_pad)
tk.Button(l_actions_f, text="2ND\nFUNC", font=btn_font, bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=open_2nd_functions).grid(row=1, column=5, **btn_pad)

# Status Bar
stat_f = tk.Frame(left_col, bg=THEME["bg_main"], height=48)
stat_f.pack(fill="x", padx=5, pady=(0,5)); stat_f.pack_propagate(False)

user_lbl = tk.Label(stat_f, text="Username: LOCKED", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"], bd=1, relief="solid", anchor="w", width=22)
user_lbl.pack(side="left", padx=2, ipady=4)
tk.Label(stat_f, text=f"Till {TILL_NUMBER}", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"], bd=1, relief="solid", width=8).pack(side="left", padx=2, ipady=4)
prev_inv_lbl = tk.Label(stat_f, text="Prev. Invoice #0", font=("Arial", 12, "bold"), bg=THEME["bg_panel"], fg=THEME["text_main"], bd=1, relief="solid", width=16)
prev_inv_lbl.pack(side="left", padx=2, ipady=4)

admin_btn = tk.Button(stat_f, text="⚙️ ADMIN VIP", font=("Arial", 11, "bold"), bg=THEME["brand_red"], fg="white", relief="flat", command=admin_panel)

# ====== RIGHT COLUMN ======
logo_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=120)
logo_f.pack(fill="x", padx=(0,5), pady=5); logo_f.pack_propagate(False)
tk.Label(logo_f, text="EAT SUM MEAT", font=("Arial", 32, "bold"), bg=THEME["bg_panel"], fg=THEME["brand_red"]).place(relx=0.5, rely=0.5, anchor="center")

input_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=90)
input_f.pack(fill="x", padx=(0,5), pady=0); input_f.pack_propagate(False)

tk.Label(input_f, text="ENTER BARCODE / SCAN", font=("Arial", 10, "bold"), bg=THEME["bg_panel"], fg=THEME["text_dim"]).place(x=15, y=5)

def on_scan(e):
    c = barcode_entry.get().strip()
    if c: add_product(c)
    barcode_entry.focus_set()

barcode_entry = tk.Entry(input_f, font=("Arial", 22, "bold"), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=0, justify="center")
barcode_entry.place(x=15, y=30, width=380, height=45)
barcode_entry.bind("<Return>", on_scan)

# --- VERIFY STRIP ---
last_scan_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=30)
last_scan_f.pack(fill="x", padx=(0,5), pady=(5,0))
last_scan_f.pack_propagate(False)
last_scan_lbl = tk.Label(last_scan_f, text="READY TO SCAN", font=("Arial", 11, "bold"), bg=THEME["bg_panel"], fg=THEME["text_dim"])
last_scan_lbl.pack(expand=True, fill="both")

# --- THE SPLIT INTERACTION AREA ---
interaction_frame = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid")
interaction_frame.pack(fill="both", expand=True, padx=(0,5), pady=5)

left_int = tk.Frame(interaction_frame, bg=THEME["bg_panel"])
left_int.pack(side="left", fill="both", expand=True, padx=(5, 2), pady=5)

right_int = tk.Frame(interaction_frame, bg=THEME["bg_panel"], width=135)
right_int.pack(side="right", fill="y", padx=(2, 5), pady=5)
right_int.pack_propagate(False)

np_grid = tk.Frame(left_int, bg=THEME["bg_panel"])
np_grid.pack(side="top", fill="both", expand=True)

cash_grid = tk.Frame(left_int, bg=THEME["bg_panel"])
cash_grid.pack(side="bottom", fill="x", pady=(5,0))

for i in range(3): np_grid.columnconfigure(i, weight=1, uniform="np")
for i in range(4): np_grid.rowconfigure(i, weight=1, uniform="np")

def num_clk(v):
    if v == "C": barcode_entry.delete(0, tk.END)
    else: barcode_entry.insert(tk.END, v)
    barcode_entry.focus_set()

keys = [('7','8','9'), ('4','5','6'), ('1','2','3'), ('.','0','C')]
for r, row in enumerate(keys):
    for c, key in enumerate(row):
        color = THEME["btn_red"] if key == "C" else THEME["btn_grey"]
        tk.Button(np_grid, text=key, font=("Arial", 18, "bold"), bg=color, fg="white", relief="flat", command=lambda k=key: num_clk(k)).grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

for i in range(4): cash_grid.columnconfigure(i, weight=1, uniform="cash")
cash_row1 = [200, 100, 50, 20]
cash_row2 = [10, 5, 2, 1]

for c, amt in enumerate(cash_row1):
    tk.Button(cash_grid, text=f"+R{amt}", font=("Arial", 11, "bold"), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", command=lambda a=amt: add_cash(a)).grid(row=0, column=c, padx=2, pady=2, sticky="nsew", ipady=8)
for c, amt in enumerate(cash_row2):
    tk.Button(cash_grid, text=f"+R{amt}", font=("Arial", 11, "bold"), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", command=lambda a=amt: add_cash(a)).grid(row=1, column=c, padx=2, pady=2, sticky="nsew", ipady=8)

tk.Button(right_int, text="←", font=("Arial", 22, "bold"), bg=THEME["btn_grey"], fg="white", relief="flat", command=lambda: barcode_entry.delete(len(barcode_entry.get())-1)).pack(side="top", fill="x", pady=(0, 5), ipady=8)
tk.Button(right_int, text="PAY\nCASH", font=("Arial", 20, "bold"), bg=THEME["btn_pay_cash"], fg="white", relief="flat", command=lambda: process_payment("CASH")).pack(side="top", fill="both", expand=True, pady=2)
tk.Button(right_int, text="PAY\nCARD", font=("Arial", 20, "bold"), bg=THEME["btn_pay_card"], fg="white", relief="flat", command=lambda: process_payment("CARD")).pack(side="bottom", fill="both", expand=True, pady=(2, 0))

# Boot Sequence
root.after(100, check_for_updates)
root.after(500, login_screen) 
root.mainloop()