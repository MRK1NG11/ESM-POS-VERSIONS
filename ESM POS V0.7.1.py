
import tkinter as tk
from tkinter import messagebox, ttk
import json, os, datetime, tempfile, platform, subprocess
import time, sys, hashlib, shutil, threading, queue, base64
import webbrowser, logging, socket, uuid
from typing import Optional

# requests is optional — app runs in offline mode if unavailable
try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Windows 10/11 High-DPI ─────────────────────────────────
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
#  CONSTANTS  (unchanged from v0.7.1)
# ═══════════════════════════════════════════════════════════
VERSION            = "0.7.1"
STORE_NAME         = "EAT SUM MEAT (PTY) LTD"
STORE_ADDRESS      = "11 Caxton Street, East London City\nEast London, 5200, South Africa"
VAT_RATE           = 0.15
AUTO_LOGOUT_SECONDS = 300

GITHUB_VERSION_URL = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/version.txt"
GITHUB_EXE_URL     = "https://github.com/MRK1NG11/ESM-POS-VERSIONS/raw/refs/heads/main/EatSumMeatPOS.exe"
GITHUB_README_URL  = "https://raw.githubusercontent.com/MRK1NG11/ESM-POS-VERSIONS/refs/heads/main/READ%20ME.txt"

THEME = {
    "bg_main":     "#121212",
    "bg_panel":    "#1e1e1e",
    "brand_red":   "#d32f2f",
    "lcd_bg":      "#000000",
    "lcd_fg":      "#00e676",
    "btn_grey":    "#333333",
    "btn_white":   "#2c2c2c",
    "btn_red":     "#c62828",
    "btn_green":   "#2e7d32",
    "btn_pay_cash":"#512da8",
    "btn_pay_card":"#0277bd",
    "text_main":   "#ffffff",
    "text_dim":    "#aaaaaa",
    "border":      "#424242",
    "highlight":   "#ff5252",
}

# ── Security constants ──────────────────────────────────────
PIN_SALT       = "EAT_SUM_MEAT_SECURE_2026_"
ADMIN_PIN_HASH = hashlib.sha256((PIN_SALT + "1981").encode()).hexdigest()
MAX_PIN_ATTEMPTS    = 3       # failed PINs before lockout
PIN_LOCKOUT_SECONDS = 60      # seconds locked after failed attempts
MAX_INPUT_LENGTH    = 64      # max chars accepted from any field
SYNC_RETRY_INTERVAL = 15      # seconds between offline-queue retries
NET_TIMEOUT         = 4       # seconds for API calls

# ── Paths ───────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _path(f: str) -> str:
    return os.path.join(BASE_DIR, f)

# ═══════════════════════════════════════════════════════════
#  LOGGING — security + app events to rotating log file
# ═══════════════════════════════════════════════════════════
_log_dir = _path("logs")
os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(_log_dir, f"pos_{datetime.date.today().isoformat()}.log"),
            encoding="utf-8"
        ),
    ]
)
log = logging.getLogger("ESM_POS")

def sec_log(event: str, detail: str = "", user: str = "SYSTEM"):
    """Write a structured security-audit entry."""
    log.warning(f"[SECURITY] user={user} event={event} detail={detail}")

# ═══════════════════════════════════════════════════════════
#  CONFIG MANAGER  (till identity + server address)
# ═══════════════════════════════════════════════════════════
_DEFAULT_CONFIG = {
    "till_number":    "01",
    "server_host":    "127.0.0.1",
    "server_port":    5000,
    "offline_mode":   False,
    "cashiers":       ["CSH1", "CSH2", "ADMIN"],
    # base64-encoded so the plain IP isn't the first thing a casual
    # browser sees; not cryptographic — real creds live server-side
    "_enc":           True,
}

class ConfigManager:
    """Load/save till configuration from config.json."""

    _cfg: dict = {}
    _path: str = _path("config.json")

    @classmethod
    def load(cls) -> dict:
        if os.path.exists(cls._path):
            try:
                with open(cls._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # merge with defaults so new keys always exist
                merged = {**_DEFAULT_CONFIG, **raw}
                cls._cfg = merged
                log.info(f"Config loaded: till={merged['till_number']} "
                         f"server={merged['server_host']}:{merged['server_port']}")
                return merged
            except Exception as e:
                log.error(f"Config load failed: {e} — using defaults")
        cls._cfg = dict(_DEFAULT_CONFIG)
        cls.save(cls._cfg)
        return cls._cfg

    @classmethod
    def save(cls, cfg: dict):
        try:
            with open(cls._path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            log.error(f"Config save failed: {e}")

    @classmethod
    def get(cls, key: str, default=None):
        return cls._cfg.get(key, default)


CFG = ConfigManager.load()
TILL_NUMBER = CFG.get("till_number", "01")
CASHIERS    = CFG.get("cashiers", ["CSH1", "CSH2", "ADMIN"])

# ═══════════════════════════════════════════════════════════
#  FILE INTEGRITY  (tamper detection via SHA-256 sidecars)
# ═══════════════════════════════════════════════════════════
class Integrity:
    """Maintain .sha256 sidecar files; warn if data was tampered with."""

    @staticmethod
    def _sidecar(path: str) -> str:
        return path + ".sha256"

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def write(cls, path: str):
        """Called after every successful file write."""
        try:
            digest = cls._hash_file(path)
            with open(cls._sidecar(path), "w") as f:
                f.write(digest)
        except Exception as e:
            log.error(f"Integrity write failed for {path}: {e}")

    @classmethod
    def verify(cls, path: str) -> bool:
        """Return True if file matches its stored hash (or no sidecar exists yet)."""
        sc = cls._sidecar(path)
        if not os.path.exists(sc) or not os.path.exists(path):
            return True   # first run — no baseline yet
        try:
            with open(sc) as f:
                stored = f.read().strip()
            actual = cls._hash_file(path)
            if stored != actual:
                sec_log("FILE_TAMPER_DETECTED", f"path={path}")
                return False
            return True
        except Exception as e:
            log.error(f"Integrity check error: {e}")
            return True   # give benefit of doubt on I/O error


# ═══════════════════════════════════════════════════════════
#  SECURITY MANAGER  (PIN lockout, input sanitisation)
# ═══════════════════════════════════════════════════════════
class SecurityManager:
    _attempts:  int   = 0
    _locked_until: float = 0.0

    @classmethod
    def is_locked(cls) -> bool:
        return time.time() < cls._locked_until

    @classmethod
    def remaining_lockout(cls) -> int:
        return max(0, int(cls._locked_until - time.time()))

    @classmethod
    def record_failure(cls, user: str = "?"):
        cls._attempts += 1
        sec_log("PIN_FAIL", f"attempt={cls._attempts}", user)
        if cls._attempts >= MAX_PIN_ATTEMPTS:
            cls._locked_until = time.time() + PIN_LOCKOUT_SECONDS
            cls._attempts = 0
            sec_log("PIN_LOCKOUT", f"duration={PIN_LOCKOUT_SECONDS}s", user)
            log.warning(f"PIN lockout activated for {PIN_LOCKOUT_SECONDS}s")

    @classmethod
    def record_success(cls, user: str = "?"):
        cls._attempts = 0
        sec_log("PIN_SUCCESS", "", user)

    @staticmethod
    def sanitise(value: str, max_len: int = MAX_INPUT_LENGTH) -> str:
        """Strip control characters, limit length."""
        cleaned = "".join(c for c in value if c.isprintable())
        return cleaned[:max_len]

    @staticmethod
    def verify_pin(raw_pin: str, user: str = "?") -> bool:
        if SecurityManager.is_locked():
            return False
        pin_clean = SecurityManager.sanitise(raw_pin, 20)
        digest = hashlib.sha256((PIN_SALT + pin_clean).encode()).hexdigest()
        ok = digest == ADMIN_PIN_HASH
        if ok:
            SecurityManager.record_success(user)
        else:
            SecurityManager.record_failure(user)
        # Wipe local variable from memory best-effort
        pin_clean = "\x00" * len(pin_clean)
        return ok


# ═══════════════════════════════════════════════════════════
#  NETWORK MANAGER  (background sync with back-office)
# ═══════════════════════════════════════════════════════════
class NetworkManager:
    """
    All network calls happen in daemon threads so the UI
    never blocks.  Failed operations go into an offline
    queue and are retried automatically.
    """

    _offline_queue: list  = []   # list of dicts pending sync
    _queue_lock            = threading.Lock()
    _server_ok: bool       = False
    _last_ping: float      = 0.0
    _listeners: list       = []  # callbacks(status: bool)

    # ── helpers ──────────────────────────────────────────
    @classmethod
    def _base_url(cls) -> str:
        host = CFG.get("server_host", "127.0.0.1")
        port = CFG.get("server_port", 5000)
        return f"http://{host}:{port}"

    @classmethod
    def _headers(cls) -> dict:
        return {
            "X-Till-ID":      f"TILL_{TILL_NUMBER}",
            "X-Till-Version": VERSION,
            "X-Request-ID":   str(uuid.uuid4()),
            "Content-Type":   "application/json",
        }

    @classmethod
    def on_status_change(cls, cb):
        cls._listeners.append(cb)

    @classmethod
    def _notify(cls, ok: bool):
        for cb in cls._listeners:
            try:
                cb(ok)
            except Exception:
                pass

    # ── public API ────────────────────────────────────────
    @classmethod
    def ping(cls):
        """Non-blocking ping; fires on_status_change callbacks."""
        threading.Thread(target=cls._ping_worker, daemon=True).start()

    @classmethod
    def sync_sale(cls, sale_data: dict):
        """Post a sale to the back-office (background). Queues if offline."""
        threading.Thread(target=cls._sync_worker, args=(sale_data,),
                         daemon=True).start()

    @classmethod
    def fetch_products(cls, callback=None):
        """Pull product catalogue from back-office into callback(dict|None)."""
        threading.Thread(target=cls._fetch_products_worker,
                         args=(callback,), daemon=True).start()

    @classmethod
    def start_retry_loop(cls):
        """Periodically drain the offline queue in a daemon thread."""
        threading.Thread(target=cls._retry_loop, daemon=True).start()

    # ── workers ───────────────────────────────────────────
    @classmethod
    def _ping_worker(cls):
        if not REQUESTS_OK or CFG.get("offline_mode"):
            cls._update_status(False); return
        try:
            r = _requests.get(
                f"{cls._base_url()}/api/ping",
                headers=cls._headers(),
                timeout=NET_TIMEOUT
            )
            cls._update_status(r.status_code == 200)
        except Exception:
            cls._update_status(False)

    @classmethod
    def _update_status(cls, ok: bool):
        if ok != cls._server_ok:
            cls._server_ok = ok
            cls._notify(ok)
            log.info(f"Server status changed: {'ONLINE' if ok else 'OFFLINE'}")

    @classmethod
    def _sync_worker(cls, sale_data: dict):
        if not REQUESTS_OK or CFG.get("offline_mode"):
            cls._enqueue(sale_data); return
        try:
            r = _requests.post(
                f"{cls._base_url()}/api/sync_sale",
                json=sale_data,
                headers=cls._headers(),
                timeout=NET_TIMEOUT
            )
            if r.status_code == 200:
                log.info(f"Sale synced: order #{sale_data.get('order_num')}")
                cls._update_status(True)
            else:
                log.warning(f"Sync HTTP {r.status_code} — queuing")
                cls._enqueue(sale_data)
        except Exception as e:
            log.warning(f"Sync failed ({e}) — queuing")
            cls._enqueue(sale_data)
            cls._update_status(False)

    @classmethod
    def _fetch_products_worker(cls, callback):
        if not REQUESTS_OK or CFG.get("offline_mode"):
            if callback: callback(None); return
        try:
            r = _requests.get(
                f"{cls._base_url()}/api/products",
                headers=cls._headers(),
                timeout=NET_TIMEOUT
            )
            if r.status_code == 200:
                raw_list = r.json()   # list of {barcode,name,price,stock,category}
                product_map = {
                    p["barcode"]: {
                        "name":  p["name"],
                        "price": p["price"],
                        "stock": p["stock"],
                        "cat":   p.get("category", "MISC"),
                    }
                    for p in raw_list
                }
                log.info(f"Products fetched from server: {len(product_map)} items")
                if callback: callback(product_map)
                return
        except Exception as e:
            log.warning(f"Product fetch failed: {e}")
        if callback: callback(None)

    @classmethod
    def _enqueue(cls, sale_data: dict):
        with cls._queue_lock:
            cls._offline_queue.append(sale_data)
        cls._save_queue()
        log.info(f"Offline queue size: {len(cls._offline_queue)}")

    @classmethod
    def _save_queue(cls):
        try:
            p = _path("offline_queue.json")
            with cls._queue_lock:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cls._offline_queue, f)
        except Exception as e:
            log.error(f"Queue save error: {e}")

    @classmethod
    def _load_queue(cls):
        p = _path("offline_queue.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    with cls._queue_lock:
                        cls._offline_queue = json.load(f)
                log.info(f"Loaded {len(cls._offline_queue)} pending offline records")
            except Exception:
                pass

    @classmethod
    def _retry_loop(cls):
        cls._load_queue()
        while True:
            time.sleep(SYNC_RETRY_INTERVAL)
            with cls._queue_lock:
                if not cls._offline_queue:
                    continue
                pending = list(cls._offline_queue)

            succeeded = []
            for sale in pending:
                try:
                    r = _requests.post(
                        f"{cls._base_url()}/api/sync_sale",
                        json=sale,
                        headers=cls._headers(),
                        timeout=NET_TIMEOUT
                    )
                    if r.status_code == 200:
                        succeeded.append(sale)
                except Exception:
                    break   # still offline — try again next cycle

            if succeeded:
                with cls._queue_lock:
                    for s in succeeded:
                        try: cls._offline_queue.remove(s)
                        except ValueError: pass
                cls._save_queue()
                log.info(f"Retry synced {len(succeeded)} offline records")
                cls._update_status(True)


# ═══════════════════════════════════════════════════════════
#  BACKGROUND I/O WORKER  (prevents UI freezes on disk ops)
# ═══════════════════════════════════════════════════════════
_io_queue: queue.Queue = queue.Queue()

def _io_worker():
    while True:
        fn, args, kwargs = _io_queue.get()
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log.error(f"Background I/O error: {e}")
        _io_queue.task_done()

threading.Thread(target=_io_worker, daemon=True, name="IO-Worker").start()

def bg(fn, *args, **kwargs):
    """Submit fn(*args) to background I/O thread."""
    _io_queue.put((fn, args, kwargs))


# ═══════════════════════════════════════════════════════════
#  STATE GLOBALS  (same structure as v0.7.1)
# ═══════════════════════════════════════════════════════════
all_transactions: list = []
all_expenses:     list = []
user_times:       list = []
products:         dict = {}

cart:         list  = []
held_cart:    list  = []
cash_received: float = 0.0
current_user:  Optional[str] = None
login_start:   Optional[float] = None
last_activity_time: float = time.time()

current_category    = "ALL"
ms_win              = None
ms_grid_frame       = None
ms_cat_frame        = None
ms_search_name_var  = None
ms_search_code_var  = None

# ── UI widget refs (set during build) ──────────────────────
root: Optional[tk.Tk] = None
cart_tree          = None
total_val_lbl      = None
sub_val_lbl        = None
prev_inv_lbl       = None
last_scan_lbl      = None
barcode_entry      = None
user_lbl           = None
admin_btn          = None
net_indicator_lbl  = None   # NEW: live network status dot
style              = None

# ── order counter ──────────────────────────────────────────
order_counter: int = 1


# ═══════════════════════════════════════════════════════════
#  HELPER GUARDS
# ═══════════════════════════════════════════════════════════
def disable_event():
    pass

def block_shortcut(event):
    return "break"

def update_activity(event=None):
    global last_activity_time
    last_activity_time = time.time()

def enable_scroll(tree):
    tree.bind("<MouseWheel>",
              lambda e: tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))
    tree.bind("<Button-4>", lambda e: tree.yview_scroll(-1, "units"))
    tree.bind("<Button-5>", lambda e: tree.yview_scroll(1,  "units"))


# ═══════════════════════════════════════════════════════════
#  BACKUP  (unchanged logic, moved to background thread)
# ═══════════════════════════════════════════════════════════
def _do_backup():
    backup_dir = _path("backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    files = ["transactions.json", "products.json",
             "expenses.json",     "sessions.json"]
    for fname in files:
        src = _path(fname)
        if os.path.exists(src):
            try:
                shutil.copy2(src, os.path.join(backup_dir, f"{fname}.{ts}.bak"))
            except Exception as e:
                log.error(f"Backup failed {fname}: {e}")
    log.info("Backup complete")

bg(_do_backup)   # run at startup in background


# ═══════════════════════════════════════════════════════════
#  DATA LAYER  (integrity-checked reads, background writes)
# ═══════════════════════════════════════════════════════════
def _safe_load_json(path: str, default):
    if not os.path.exists(path):
        return default
    if not Integrity.verify(path):
        messagebox.showwarning(
            "Security Warning",
            f"Data file may have been modified outside the application:\n{path}\n\n"
            "Contact your system administrator."
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"JSON load error {path}: {e}")
        return default


def _safe_write_json(path: str, data):
    """Atomic write: write to .tmp then rename to prevent corruption."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        if os.path.exists(path):
            os.replace(tmp, path)
        else:
            os.rename(tmp, path)
        Integrity.write(path)
    except Exception as e:
        log.error(f"JSON write error {path}: {e}")
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass


def load_system_data():
    global all_transactions, all_expenses, user_times
    all_transactions = _safe_load_json(_path("transactions.json"), [])
    all_expenses     = _safe_load_json(_path("expenses.json"),     [])
    user_times       = _safe_load_json(_path("sessions.json"),     [])


def load_products() -> dict:
    default = {
        "1001": {"name": "Boerewors Roll",  "price": 45.0, "stock": 50,  "cat": "MEAT"},
        "1002": {"name": "Steak Roll",       "price": 65.0, "stock": 40,  "cat": "MEAT"},
        "1003": {"name": "Chicken Burger",   "price": 55.0, "stock": 35,  "cat": "MEAT"},
        "1004": {"name": "Pork Ribs",        "price": 95.0, "stock": 20,  "cat": "MEAT"},
        "2001": {"name": "Slap Chips",       "price": 25.0, "stock": 100, "cat": "SNACKS"},
        "3001": {"name": "Coke 440ml",       "price": 20.0, "stock": 120, "cat": "DRINK"},
        "4001": {"name": "Carrot Salad",     "price": 20.0, "stock": 50,  "cat": "VEG"},
    }
    prod_path = _path("products.json")
    data = _safe_load_json(prod_path, None)
    if data is None:
        bg(_safe_write_json, prod_path, default)
        return default
    # merge so new defaults always appear
    for k, v in default.items():
        if k not in data:
            data[k] = v
    return data


def init_order_counter() -> int:
    if all_transactions:
        return max(t.get("order_num", 0) for t in all_transactions)
    return 0


def save_local_session(session_data: dict):
    user_times.append(session_data)
    bg(_safe_write_json, _path("sessions.json"), user_times)


def save_local_transaction(sale_data: dict):
    all_transactions.append(sale_data)
    bg(_safe_write_json, _path("transactions.json"), all_transactions)
    bg(_safe_write_json, _path("products.json"),     products)


def save_expense(etype: str, reason: str, amount: float):
    reason = SecurityManager.sanitise(reason)
    all_expenses.append({
        "date":   datetime.datetime.now().strftime("%Y-%m-%d"),
        "time":   datetime.datetime.now().strftime("%H:%M:%S"),
        "type":   etype,
        "reason": reason,
        "amount": round(amount, 2),
        "user":   current_user,
    })
    bg(_safe_write_json, _path("expenses.json"), all_expenses)


# ═══════════════════════════════════════════════════════════
#  Z-REPORT / END OF DAY
# ═══════════════════════════════════════════════════════════
def run_z_report_and_eod():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    export_pkg = {
        "node_id":      f"TILL_{TILL_NUMBER}",
        "date":         today,
        "transactions": all_transactions,
        "sessions":     user_times,
    }
    total_cash = total_card = 0
    for t in all_transactions:
        if t["date"] == today:
            if   t["method"] == "CASH": total_cash += t["amount"]
            elif t["method"] == "CARD": total_card += t["amount"]

    gross   = round(total_cash + total_card, 2)
    z_vat   = round(gross * VAT_RATE, 2)

    z  = f"{STORE_NAME.center(32)}\n"
    z += "*** END OF DAY Z-REPORT ***".center(32) + "\n"
    z += "=" * 32 + "\n"
    z += f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    z += f"Till: {TILL_NUMBER}   |   Printed By: {current_user}\n"
    z += "-" * 32 + "\n"
    z += f"TOTAL CASH:            R{total_cash:>7.2f}\n"
    z += f"TOTAL CARD SALES:      R{total_card:>7.2f}\n"
    z += "-" * 32 + "\n"
    z += f"GROSS REVENUE:         R{gross:>7.2f}\n"
    z += f"TOTAL VAT COLLECTED:   R{z_vat:>7.2f}\n"
    z += "=" * 32 + "\n\n\n\n"

    print_receipt_silent(z)
    eod_path = _path(f"EOD_PUSH_{today}.json")
    bg(_safe_write_json, eod_path, export_pkg)
    return eod_path


# ═══════════════════════════════════════════════════════════
#  AUTO UPDATER  (unchanged from v0.7.0)
# ═══════════════════════════════════════════════════════════
def show_update_prompt(latest_version: str):
    prompt_win = tk.Toplevel(root)
    prompt_win.attributes("-topmost", True)
    prompt_win.overrideredirect(True)
    prompt_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    w, h = 500, 250
    x = (prompt_win.winfo_screenwidth()  // 2) - (w // 2)
    y = (prompt_win.winfo_screenheight() // 2) - (h // 2)
    prompt_win.geometry(f"{w}x{h}+{x}+{y}")

    hdr = tk.Frame(prompt_win, bg=THEME["brand_red"])
    hdr.pack(fill="x")
    tk.Label(hdr, text="SYSTEM UPDATE AVAILABLE", font=("Arial", 16, "bold"),
             fg="white", bg=THEME["brand_red"]).pack(pady=10)

    tk.Label(prompt_win, text=f"Version {latest_version} is ready to install.",
             font=("Arial", 13), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(30, 10))
    tk.Label(prompt_win, text="Would you like to download it now?",
             font=("Arial", 11), bg=THEME["bg_panel"], fg=THEME["text_dim"]).pack(pady=5)

    btn_f = tk.Frame(prompt_win, bg=THEME["bg_panel"])
    btn_f.pack(pady=30)
    tk.Button(btn_f, text="LATER", font=("Arial", 12, "bold"),
              bg=THEME["btn_grey"], fg=THEME["text_main"], width=12,
              relief="flat", command=prompt_win.destroy).pack(side="left", padx=10)
    tk.Button(btn_f, text="UPDATE NOW", font=("Arial", 12, "bold"),
              bg=THEME["btn_green"], fg="white", width=15, relief="flat",
              command=lambda: [prompt_win.destroy(), perform_update()]).pack(side="left", padx=10)


def check_for_updates():
    if not REQUESTS_OK: return
    def _check():
        try:
            r = _requests.get(GITHUB_VERSION_URL, timeout=5)
            latest = r.text.strip()
            if latest and latest != VERSION:
                root.after(0, lambda: show_update_prompt(latest))
        except Exception:
            pass
    threading.Thread(target=_check, daemon=True).start()


def perform_update():
    if not REQUESTS_OK:
        messagebox.showinfo("Update", "requests library not installed — update manually.")
        return
    try:
        upd_win = tk.Toplevel()
        upd_win.attributes("-topmost", True)
        upd_win.overrideredirect(True)
        upd_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
        w, h = 550, 260
        x = (upd_win.winfo_screenwidth()  // 2) - (w // 2)
        y = (upd_win.winfo_screenheight() // 2) - (h // 2)
        upd_win.geometry(f"{w}x{h}+{x}+{y}")

        hdr = tk.Frame(upd_win, bg=THEME["brand_red"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="DOWNLOADING UPDATE", font=("Arial", 16, "bold"),
                 fg="white", bg=THEME["brand_red"]).pack(pady=10)
        tk.Label(upd_win, text="Please wait while the system downloads the latest files...",
                 font=("Arial", 12), bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(20, 10))

        style.configure("Sleek.Horizontal.TProgressbar", thickness=20,
                         background=THEME["lcd_fg"], troughcolor=THEME["btn_grey"], borderwidth=0)
        progress = ttk.Progressbar(upd_win, orient="horizontal", length=450,
                                   mode="determinate", style="Sleek.Horizontal.TProgressbar")
        progress.pack(pady=10)
        perc_lbl = tk.Label(upd_win, text="0%", font=("Consolas", 16, "bold"),
                             bg=THEME["bg_panel"], fg=THEME["lcd_fg"])
        perc_lbl.pack(pady=5)
        upd_win.update()

        r = _requests.get(GITHUB_EXE_URL, stream=True, timeout=30)
        total_length = r.headers.get("content-length")
        update_file  = _path("update_temp.exe")

        with open(update_file, "wb") as f:
            if total_length is None:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk); progress.step(5); upd_win.update()
            else:
                total_length = int(total_length); downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    downloaded += len(chunk); f.write(chunk)
                    pct = int(100 * downloaded / total_length)
                    progress["value"] = pct
                    perc_lbl.config(text=f"{pct}%")
                    upd_win.update()

        try:
            rr = _requests.get(GITHUB_README_URL, timeout=10)
            if rr.status_code == 200:
                with open(_path("README.txt"), "wb") as f: f.write(rr.content)
        except Exception:
            pass

        if getattr(sys, "frozen", False):
            batch = _path("update_swap.bat")
            exe   = sys.executable
            with open(batch, "w", encoding="utf-8") as f:
                f.write(f'@echo off\ntimeout /t 2 /nobreak > nul\n'
                        f'del "{exe}"\nmove "{update_file}" "{exe}"\ndel "%~f0"\n')
            messagebox.showinfo("Update Complete",
                "Update downloaded.\n\nThe application will now close. Please relaunch.")
            subprocess.Popen([batch], shell=True)
            sys.exit()
        else:
            messagebox.showinfo("Update Complete",
                "New script downloaded.\n\nPlease restart manually.")
            upd_win.destroy(); sys.exit()

    except Exception as e:
        messagebox.showerror("Update Error", f"Failed to download update: {e}")
        if "upd_win" in dir() and upd_win.winfo_exists():
            upd_win.destroy()


# ═══════════════════════════════════════════════════════════
#  CORE CART LOGIC  (unchanged behaviour)
# ═══════════════════════════════════════════════════════════
def raw_total() -> float:
    return round(sum(round(i["price"] * i["qty"], 2) for i in cart), 2)


def update_cart_ui():
    for item in cart_tree.get_children():
        cart_tree.delete(item)
    for i in cart:
        line_tot = round(i["price"] * i["qty"], 2)
        cart_tree.insert("", "end",
                         values=(i["code"], i["qty"], i["name"],
                                 f"{i['price']:.2f}", f"{line_tot:.2f}"))
    final_tot = raw_total()
    total_val_lbl.config(text=f"R{final_tot:.2f}")
    if cart:
        if cash_received < final_tot:
            sub_val_lbl.config(
                text=f"DUE R{round(final_tot - cash_received, 2):.2f}",
                fg=THEME["brand_red"])
        else:
            change = max(0, round(cash_received - final_tot, 2))
            sub_val_lbl.config(text=f"CHG R{change:.2f}", fg=THEME["lcd_fg"])
    else:
        sub_val_lbl.config(text="CHG R0.00", fg=THEME["text_main"])
    prev_inv_lbl.config(text=f"Prev. Invoice #{order_counter}")


def add_product(code: str):
    global products
    barcode_entry.delete(0, tk.END)

    # ── input sanitation ──
    code = SecurityManager.sanitise(code, 32).strip()
    if not code:
        barcode_entry.focus_set(); return

    if code not in products:
        messagebox.showerror("Error", "Product Code Not Found")
        barcode_entry.focus_set(); return
    if products[code]["stock"] <= 0:
        messagebox.showwarning("Stock", "Out of stock!")
        barcode_entry.focus_set(); return

    p = products[code]
    for i in cart:
        if i["code"] == code:
            i["qty"] += 1; p["stock"] -= 1
            update_cart_ui()
            last_scan_lbl.config(
                text=f"ADDED: {p['name']} | STOCK: {p['stock']} | PRICE: R{p['price']:.2f}",
                fg=THEME["lcd_fg"])
            barcode_entry.focus_set()
            if cart_tree.get_children(): cart_tree.see(cart_tree.get_children()[-1])
            return

    cart.append({"code": code, "name": p["name"], "price": p["price"], "qty": 1})
    p["stock"] -= 1
    update_cart_ui()
    last_scan_lbl.config(
        text=f"ADDED: {p['name']} | STOCK: {p['stock']} | PRICE: R{p['price']:.2f}",
        fg=THEME["lcd_fg"])
    barcode_entry.focus_set()
    if cart_tree.get_children(): cart_tree.see(cart_tree.get_children()[-1])


def void_item(event=None):
    sel = cart_tree.selection()
    if not sel:
        messagebox.showinfo("Select Item", "Please select an item in the list to void.")
        barcode_entry.focus_set(); return

    if current_user != "ADMIN":
        if SecurityManager.is_locked():
            rem = SecurityManager.remaining_lockout()
            messagebox.showerror("Locked",
                f"Too many failed PIN attempts.\nPlease wait {rem} seconds.")
            barcode_entry.focus_set(); return

        pw = custom_input("Manager Override", "Enter Admin PIN", is_password=True)
        if not pw or not SecurityManager.verify_pin(pw, current_user):
            messagebox.showerror("Error", "Manager override failed")
            barcode_entry.focus_set(); return

    idx  = cart_tree.index(sel[0])
    item = cart.pop(idx)
    products[item["code"]]["stock"] += item["qty"]
    log.info(f"VOID: {item['name']} x{item['qty']} by {current_user}")
    update_cart_ui()
    barcode_entry.focus_set()


def clear_cart():
    if not cart: return
    if messagebox.askyesno("Confirm", "Clear the entire sales order?"):
        for item in cart:
            products[item["code"]]["stock"] += item["qty"]
        cart.clear()
        global cash_received
        cash_received = 0.0
        update_cart_ui()
        last_scan_lbl.config(text="READY TO SCAN", fg=THEME["text_dim"])
    barcode_entry.focus_set()


def toggle_hold_cart(mode: str):
    global held_cart, cart, cash_received
    if mode == "SAVE":
        if cart:
            if held_cart:
                messagebox.showwarning("Hold Error", "A cart is already saved! Recall it first.")
            else:
                held_cart = cart.copy()
                cart.clear(); cash_received = 0.0
                update_cart_ui()
                last_scan_lbl.config(text="CART ON HOLD", fg=THEME["text_dim"])
    elif mode == "LOAD":
        if held_cart:
            cart = held_cart.copy(); held_cart.clear()
            update_cart_ui()
            last_scan_lbl.config(text="CART RECALLED", fg=THEME["lcd_fg"])
        else:
            messagebox.showinfo("Load", "No saved sales.")
    barcode_entry.focus_set()


def add_cash(amount: float):
    global cash_received
    cash_received += amount
    update_cart_ui()
    barcode_entry.focus_set()


def generate_receipt_text(method: str, final_tot: float) -> str:
    vat_amt  = round(final_tot * VAT_RATE, 2)
    excl_vat = round(final_tot - vat_amt, 2)

    r  = "=" * 32 + "\n"
    r += f"{STORE_NAME.center(32)}\n"
    for line in STORE_ADDRESS.split("\n"):
        r += f"{line.center(32)}\n"
    r += "VAT No: 4123456789".center(32) + "\n"
    r += "-" * 32 + "\n"
    r += f"Receipt: #{order_counter:<10} Till: {TILL_NUMBER}\n"
    r += f"Cashier: [{current_user}]\n"
    r += f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    r += "-" * 32 + "\n"
    r += f"{'QTY ITEM':<22} {'TOTAL':>9}\n"
    for i in cart:
        name     = (i["name"][:13] + "..") if len(i["name"]) > 15 else i["name"][:15]
        line_tot = round(i["price"] * i["qty"], 2)
        r += f"{i['qty']:<2}x {name:<16} R{line_tot:>8.2f}\n"
    r += "-" * 32 + "\n"
    r += f"TOTAL DUE:             R{final_tot:>7.2f}\n"
    slip_method = "PAY CARD" if method == "CARD" else "CASH SALE"
    r += f"PAID VIA:             {slip_method:>9}\n"
    if method == "CASH":
        r += f"CASH TENDERED:         R{cash_received:>7.2f}\n"
        r += f"CHANGE DUE:            R{max(0, round(cash_received - final_tot, 2)):>7.2f}\n"
    r += "-" * 32 + "\n"
    r += "VAT SUMMARY".center(32) + "\n"
    r += f"Total Excl VAT:        R{excl_vat:>7.2f}\n"
    r += f"VAT @ 15%:             R{vat_amt:>7.2f}\n"
    r += f"Total Incl VAT:        R{final_tot:>7.2f}\n"
    r += "=" * 32 + "\n"
    r += "THANK YOU FOR YOUR BUSINESS!".center(32) + "\n"
    r += "PLEASE RETAIN YOUR SLIP".center(32)      + "\n"
    r += "-" * 32 + "\n"
    r += "Goods returnable within 7 days".center(32) + "\n"
    r += "with original receipt. E&OE.".center(32)   + "\n"
    r += "Subject to store policy.".center(32)        + "\n\n\n\n"
    return r


def process_payment(method: str):
    global order_counter, cash_received
    if not cart: return
    final_tot = raw_total()

    if method == "CASH" and cash_received == 0:
        amt_str = custom_input("Cash Tendered", "Enter exact cash received:")
        try:
            cash_received = float(SecurityManager.sanitise(amt_str or "", 16))
        except (ValueError, TypeError):
            barcode_entry.focus_set(); return

    if method == "CASH" and cash_received < final_tot:
        messagebox.showwarning("Payment",
            f"Insufficient Cash!\nDUE: R{final_tot - cash_received:.2f}")
        barcode_entry.focus_set(); return

    now        = datetime.datetime.now()
    change_amt = max(0, round(cash_received - final_tot, 2)) if method == "CASH" else 0

    sale = {
        "id":        now.strftime("%Y%m%d%H%M%S") + f"_{TILL_NUMBER}",
        "order_num": order_counter,
        "date":      now.strftime("%Y-%m-%d"),
        "time":      now.strftime("%H:%M:%S"),
        "cashier":   current_user,
        "till":      TILL_NUMBER,
        "method":    method,
        "amount":    final_tot,
        "change":    change_amt,
        "items":     cart.copy(),
    }

    save_local_transaction(sale)

    # ── Network sync (non-blocking) ──
    NetworkManager.sync_sale(sale)

    receipt_txt = generate_receipt_text(method, final_tot)
    bg(print_receipt_silent, receipt_txt)

    cart.clear()
    cash_received = 0.0
    order_counter = (order_counter % 999) + 1
    update_cart_ui()
    last_scan_lbl.config(text="READY TO SCAN", fg=THEME["text_dim"])
    barcode_entry.focus_set()
    log.info(f"Sale complete: #{sale['order_num']} R{final_tot:.2f} {method} [{current_user}]")


def print_receipt_silent(text: str):
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", dir=BASE_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(0, "print", tmp, None, ".", 0)
        else:
            subprocess.run(["lp", tmp],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log.error(f"Print error: {e}")


# ═══════════════════════════════════════════════════════════
#  MODALS  (custom_input — now with PIN lockout check)
# ═══════════════════════════════════════════════════════════
def custom_input(title: str, prompt: str, is_password: bool = False) -> Optional[str]:
    win = tk.Toplevel()
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)
    win.configure(bg=THEME["bg_panel"], bd=1, relief="solid")
    win.geometry("500x300")
    win.title(title)
    win.grab_set(); win.attributes("-topmost", True)

    # Lockout banner
    if is_password and SecurityManager.is_locked():
        rem = SecurityManager.remaining_lockout()
        tk.Label(win, text=f"🔒 LOCKED — wait {rem}s",
                 font=("Arial", 14, "bold"), bg=THEME["btn_red"], fg="white").pack(fill="x")

    tk.Label(win, text=prompt, font=("Arial", 16, "bold"),
             bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=30)

    entry = tk.Entry(win, font=("Arial", 28),
                     show="*" if is_password else "",
                     justify="center",
                     bg=THEME["btn_white"], fg=THEME["text_main"],
                     bd=0, relief="flat",
                     validate="key",
                     # prevent pasting more than MAX_INPUT_LENGTH chars
                     validatecommand=(win.register(
                         lambda v: len(v) <= MAX_INPUT_LENGTH), "%P"))
    entry.pack(pady=10, fill="x", padx=60)
    entry.focus_set()

    res = {"val": None}

    def submit(event=None):
        raw = entry.get()
        res["val"] = SecurityManager.sanitise(raw)
        # Wipe widget contents before destroying
        entry.delete(0, tk.END)
        win.destroy()

    def cancel():
        entry.delete(0, tk.END)
        win.destroy()

    entry.bind("<Return>", submit)
    btn_frame = tk.Frame(win, bg=THEME["bg_panel"])
    btn_frame.pack(pady=30)
    tk.Button(btn_frame, text="CANCEL",  font=("Arial", 12, "bold"),
              bg=THEME["btn_grey"], fg=THEME["text_main"],
              width=12, height=2, relief="flat", command=cancel).pack(side="left",  padx=10)
    tk.Button(btn_frame, text="CONFIRM", font=("Arial", 12, "bold"),
              bg=THEME["btn_green"], fg="white",
              width=12, height=2, relief="flat", command=submit).pack(side="left", padx=10)

    win.wait_window()
    update_activity()
    return res["val"]


# ═══════════════════════════════════════════════════════════
#  MANUAL SELECT  (unchanged UI)
# ═══════════════════════════════════════════════════════════
def open_manual_select():
    global ms_win, ms_grid_frame, ms_cat_frame, current_category
    global ms_search_name_var, ms_search_code_var
    if ms_win and ms_win.winfo_exists():
        ms_win.lift(); return

    ms_win = tk.Toplevel(root)
    ms_win.attributes("-topmost", True)
    ms_win.overrideredirect(True)
    ms_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    w, h = 900, 650
    x = (root.winfo_screenwidth()  // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    ms_win.geometry(f"{w}x{h}+{x}+{y}")
    ms_win.grab_set()

    hdr = tk.Frame(ms_win, bg=THEME["brand_red"])
    hdr.pack(fill="x")
    tk.Label(hdr, text="MANUAL PRODUCT SELECT", font=("Arial", 16, "bold"),
             fg="white", bg=THEME["brand_red"]).pack(side="left", padx=20, pady=10)
    tk.Button(hdr, text="CLOSE", font=("Arial", 12, "bold"),
              bg=THEME["bg_panel"], fg=THEME["text_main"],
              relief="flat", command=ms_win.destroy).pack(side="right", padx=10, pady=5)

    search_frame = tk.Frame(ms_win, bg=THEME["bg_panel"])
    search_frame.pack(fill="x", padx=20, pady=10)
    search_frame.columnconfigure(1, weight=1); search_frame.columnconfigure(3, weight=1)

    ms_search_name_var = tk.StringVar(); ms_search_code_var = tk.StringVar()
    tk.Label(search_frame, text="🔍 Name:", font=("Arial", 12, "bold"),
             bg=THEME["bg_panel"], fg=THEME["text_main"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    e1 = tk.Entry(search_frame, textvariable=ms_search_name_var,
                  font=("Arial", 16), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat")
    e1.grid(row=0, column=1, sticky="ew", padx=5)
    e1.bind("<KeyRelease>", lambda e: [refresh_ms_grid(), update_activity()])

    tk.Label(search_frame, text="🔍 Barcode:", font=("Arial", 12, "bold"),
             bg=THEME["bg_panel"], fg=THEME["text_main"]).grid(row=0, column=2, padx=(20,5), pady=5, sticky="w")
    e2 = tk.Entry(search_frame, textvariable=ms_search_code_var,
                  font=("Arial", 16), bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat")
    e2.grid(row=0, column=3, sticky="ew", padx=5)
    e2.bind("<KeyRelease>", lambda e: [refresh_ms_grid(), update_activity()])

    ms_cat_frame  = tk.Frame(ms_win, bg=THEME["bg_panel"]); ms_cat_frame.pack(fill="x", padx=20, pady=5)
    ms_grid_frame = tk.Frame(ms_win, bg=THEME["bg_panel"]); ms_grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
    for c in range(4): ms_grid_frame.columnconfigure(c, weight=1, uniform="msgroup")

    def set_cat(cat):
        global current_category
        current_category = cat
        refresh_ms_grid(); update_activity()

    def refresh_ms_grid():
        for w in ms_grid_frame.winfo_children(): w.destroy()
        for w in ms_cat_frame.winfo_children():  w.destroy()

        cats = ["ALL", "MEAT", "SNACKS", "VEG", "DRINK"]
        for c in cats:
            bg_c = THEME["btn_green"] if c == current_category else THEME["btn_grey"]
            tk.Button(ms_cat_frame, text=c, font=("Arial", 12, "bold"),
                      bg=bg_c, fg="white", height=2, width=12,
                      relief="flat", command=lambda ct=c: set_cat(ct)).pack(side="left", padx=5)

        row = col = 0
        search_n = ms_search_name_var.get().lower().strip()
        search_c = ms_search_code_var.get().lower().strip()
        for code, p in products.items():
            cat_match  = (current_category == "ALL") or (p["cat"].upper() == current_category)
            name_match = (search_n in p["name"].lower()) if search_n else True
            code_match = (search_c in code.lower())      if search_c else True
            if cat_match and name_match and code_match:
                btn = tk.Button(
                    ms_grid_frame,
                    text=f"{p['name']}\nR{p['price']:.2f}\n[{p['stock']}]",
                    font=("Arial", 12, "bold"),
                    bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat",
                    command=lambda c=code: [add_product(c), ms_win.destroy()])
                btn.grid(row=row, column=col, padx=8, pady=8, sticky="nsew", ipady=20)
                col += 1
                if col > 3: col = 0; row += 1

    refresh_ms_grid(); update_activity()


# ═══════════════════════════════════════════════════════════
#  MARKDOWN
# ═══════════════════════════════════════════════════════════
def open_markdown():
    sel = cart_tree.selection()
    if not sel:
        messagebox.showinfo("Select", "Please select an item in the cart to markdown.")
        return

    if current_user != "ADMIN":
        if SecurityManager.is_locked():
            rem = SecurityManager.remaining_lockout()
            messagebox.showerror("Locked", f"Too many failed PIN attempts. Wait {rem}s.")
            return
        pw = custom_input("Manager Override", "Enter Admin PIN:", is_password=True)
        if not pw or not SecurityManager.verify_pin(pw, current_user):
            return

    idx          = cart_tree.index(sel[0])
    current_item = cart[idx]

    md_win = tk.Toplevel(root)
    md_win.attributes("-topmost", True)
    md_win.overrideredirect(True)
    md_win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    w, h = 320, 280
    md_win.geometry(f"{w}x{h}+20+{768 - h - 60}")

    tk.Label(md_win, text=f"MARKDOWN: {current_item['name'][:12]}",
             font=("Arial", 14, "bold"), bg=THEME["brand_red"], fg="white").pack(fill="x", pady=(0,15), ipady=5)
    tk.Label(md_win, text="Enter New Price (R):", font=("Arial", 12, "bold"),
             bg=THEME["bg_panel"], fg=THEME["text_main"]).pack()
    price_var = tk.StringVar()
    tk.Entry(md_win, textvariable=price_var, font=("Arial", 18, "bold"),
             justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat").pack(pady=5, fill="x", padx=40)
    tk.Label(md_win, text="OR Discount (%):", font=("Arial", 12, "bold"),
             bg=THEME["bg_panel"], fg=THEME["text_main"]).pack(pady=(10,0))
    perc_var = tk.StringVar()
    tk.Entry(md_win, textvariable=perc_var, font=("Arial", 18, "bold"),
             justify="center", bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat").pack(pady=5, fill="x", padx=40)

    def apply_md():
        p_val   = SecurityManager.sanitise(price_var.get(), 12)
        pct_val = SecurityManager.sanitise(perc_var.get(), 6)
        try:
            if pct_val:
                discount = float(pct_val)
                if not (0 < discount <= 100):
                    raise ValueError("Discount out of range")
                cart[idx]["price"] = round(current_item["price"] * (1 - discount / 100), 2)
            elif p_val:
                new_price = float(p_val)
                if new_price < 0:
                    raise ValueError("Negative price")
                cart[idx]["price"] = round(new_price, 2)
            log.info(f"MARKDOWN: {current_item['name']} → R{cart[idx]['price']:.2f} by {current_user}")
            update_cart_ui(); md_win.destroy(); barcode_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid value: {e}", parent=md_win)

    btn_f = tk.Frame(md_win, bg=THEME["bg_panel"]); btn_f.pack(pady=15, fill="x")
    tk.Button(btn_f, text="CANCEL", font=("Arial", 10, "bold"),
              bg=THEME["btn_grey"], fg=THEME["text_main"], height=2, width=10,
              relief="flat", command=lambda: [md_win.destroy(), barcode_entry.focus_set()]).pack(side="left", padx=15)
    tk.Button(btn_f, text="APPLY", font=("Arial", 10, "bold"),
              bg=THEME["btn_green"], fg="white", height=2, width=10,
              relief="flat", command=apply_md).pack(side="right", padx=15)
    update_activity()


# ═══════════════════════════════════════════════════════════
#  2ND FUNCTIONS  (unchanged UI)
# ═══════════════════════════════════════════════════════════
def open_2nd_functions():
    win = tk.Toplevel()
    win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    win.overrideredirect(True)
    w, h = 400, 180
    win.geometry(f"{w}x{h}+20+{768 - h - 60}")
    win.grab_set(); win.attributes("-topmost", True)

    tk.Label(win, text="2ND FUNCTIONS", font=("Arial", 16, "bold"),
             bg=THEME["brand_red"], fg="white").pack(fill="x", pady=(0,15), ipady=5)

    def do_payout():
        amt    = custom_input("PAY OUT", "Enter Amount to Pay Out:")
        if amt:
            reason = custom_input("PAY OUT", "Enter Reason for Pay Out:")
            if reason:
                try:
                    save_expense("PAY OUT", reason, float(amt))
                    messagebox.showinfo("Success", f"Pay Out of R{float(amt):.2f} logged.")
                    win.destroy()
                except (ValueError, TypeError):
                    messagebox.showerror("Error", "Invalid amount entered.")

    tk.Button(win, text="💸 PAY OUT", font=("Arial", 14, "bold"),
              bg=THEME["btn_pay_card"], fg="white", height=2,
              relief="flat", command=do_payout).pack(fill="x", padx=40, pady=5)
    tk.Button(win, text="CLOSE", font=("Arial", 12, "bold"),
              bg=THEME["btn_grey"], fg=THEME["text_main"], height=2,
              relief="flat", command=win.destroy).pack(fill="x", padx=40, pady=(15,0))
    update_activity()


# ═══════════════════════════════════════════════════════════
#  NETWORK SETTINGS MODAL  (NEW — configure server IP/till)
# ═══════════════════════════════════════════════════════════
def open_network_settings():
    if current_user != "ADMIN": return
    win = tk.Toplevel(root)
    win.title("Network Settings")
    win.configure(bg=THEME["bg_panel"], bd=2, relief="solid")
    win.geometry("480x420")
    win.grab_set(); win.attributes("-topmost", True)

    tk.Label(win, text="NETWORK & TILL SETTINGS",
             font=("Arial", 16, "bold"), fg="white", bg=THEME["brand_red"]).pack(fill="x", ipady=10)

    def lbl_ent(parent, label, default=""):
        tk.Label(parent, text=label, font=("Arial", 11, "bold"),
                 bg=THEME["bg_panel"], fg=THEME["text_dim"]).pack(anchor="w", padx=30, pady=(10,1))
        e = tk.Entry(parent, font=("Arial", 13), bg=THEME["btn_white"],
                     fg=THEME["text_main"], relief="flat", bd=0)
        e.pack(fill="x", padx=30, ipady=5)
        e.insert(0, str(default)); return e

    e_host = lbl_ent(win, "Back-Office Server IP Address:", CFG.get("server_host", "127.0.0.1"))
    e_port = lbl_ent(win, "Server Port:",                   CFG.get("server_port", 5000))
    e_till = lbl_ent(win, "This Till Number (01, 02 …):",   CFG.get("till_number", "01"))

    # Offline toggle
    off_var = tk.BooleanVar(value=CFG.get("offline_mode", False))
    tk.Checkbutton(win, text=" Run in OFFLINE mode (no server required)",
                   variable=off_var, font=("Arial", 11, "bold"),
                   bg=THEME["bg_panel"], fg=THEME["text_main"],
                   selectcolor=THEME["btn_grey"],
                   activebackground=THEME["bg_panel"]).pack(anchor="w", padx=30, pady=14)

    # Live ping test
    ping_lbl = tk.Label(win, text="", font=("Arial", 10, "bold"),
                        bg=THEME["bg_panel"], fg=THEME["text_dim"])
    ping_lbl.pack()

    def test_conn():
        host = e_host.get().strip()
        port_str = e_port.get().strip()
        try:
            port = int(port_str)
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            ping_lbl.config(text=f"✅  Connected to {host}:{port}", fg=THEME["lcd_fg"])
        except Exception as ex:
            ping_lbl.config(text=f"❌  Cannot reach {host}:{port_str} — {ex}",
                            fg=THEME["highlight"])

    def save():
        global TILL_NUMBER
        new_cfg = dict(CFG)
        new_cfg["server_host"]  = SecurityManager.sanitise(e_host.get().strip(), 64)
        new_cfg["server_port"]  = int(e_port.get().strip() or 5000)
        new_cfg["till_number"]  = SecurityManager.sanitise(e_till.get().strip(), 4)
        new_cfg["offline_mode"] = off_var.get()
        ConfigManager.save(new_cfg)
        CFG.update(new_cfg)
        TILL_NUMBER = new_cfg["till_number"]
        NetworkManager.ping()
        log.info(f"Network settings updated: {new_cfg['server_host']}:{new_cfg['server_port']}")
        messagebox.showinfo("Saved", "Settings saved.\nChanges take effect immediately.", parent=win)
        win.destroy()

    btn_f = tk.Frame(win, bg=THEME["bg_panel"]); btn_f.pack(pady=10)
    tk.Button(btn_f, text="TEST CONNECTION", font=("Arial", 11, "bold"),
              bg=THEME["btn_grey"], fg=THEME["text_main"],
              relief="flat", padx=12, pady=6, command=test_conn).pack(side="left", padx=8)
    tk.Button(btn_f, text="SAVE", font=("Arial", 11, "bold"),
              bg=THEME["btn_green"], fg="white",
              relief="flat", padx=20, pady=6, command=save).pack(side="left", padx=8)
    tk.Button(btn_f, text="CANCEL", font=("Arial", 11, "bold"),
              bg=THEME["btn_white"], fg=THEME["text_main"],
              relief="flat", padx=12, pady=6, command=win.destroy).pack(side="left", padx=8)


# ═══════════════════════════════════════════════════════════
#  ADMIN PANEL  (unchanged UI; adds Network Settings button)
# ═══════════════════════════════════════════════════════════
def admin_panel():
    if current_user != "ADMIN": return
    update_activity()

    win = tk.Toplevel(); win.attributes("-fullscreen", True)
    win.configure(bg=THEME["bg_main"])
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)

    sidebar = tk.Frame(win, bg="#1a1a1a", width=280)
    sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
    tk.Label(sidebar, text="🥩\nADMIN SUITE", font=("Arial", 26, "bold"),
             fg=THEME["brand_red"], bg="#1a1a1a").pack(pady=40)

    content = tk.Frame(win, bg=THEME["bg_main"])
    content.pack(side="right", fill="both", expand=True)

    dash_f  = tk.Frame(content, bg=THEME["bg_main"])
    inv_f   = tk.Frame(content, bg=THEME["bg_main"])
    staff_f = tk.Frame(content, bg=THEME["bg_main"])
    pay_f   = tk.Frame(content, bg=THEME["bg_main"])
    for f in (dash_f, inv_f, staff_f, pay_f): f.place(relx=0, rely=0, relwidth=1, relheight=1)

    def show_frame(f): f.tkraise(); update_activity()

    nav_f = ("Arial", 14, "bold")
    tk.Button(sidebar, text="DASHBOARD",    font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(dash_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="INVENTORY",    font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(inv_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="STAFF LOGS",   font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(staff_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="PAY OUTS",     font=nav_f, bg="#2a2a2a", fg="white", relief="flat", pady=15, command=lambda: show_frame(pay_f)).pack(fill="x", pady=2)
    tk.Button(sidebar, text="🌐 NETWORK",   font=nav_f, bg="#1a3a2a", fg="#00e676", relief="flat", pady=15, command=open_network_settings).pack(fill="x", pady=2)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    total_day = total_cash = total_card = 0
    for t in all_transactions:
        if t["date"] == today:
            total_day += t["amount"]
            if t["method"] == "CASH": total_cash += t["amount"]
            elif t["method"] == "CARD": total_card += t["amount"]

    admin_style = ttk.Style()
    admin_style.configure("Admin.Treeview", rowheight=40, font=("Arial", 13),
                           background=THEME["bg_panel"], fieldbackground=THEME["bg_panel"],
                           foreground=THEME["text_main"], borderwidth=0)
    admin_style.configure("Admin.Treeview.Heading", font=("Arial", 12, "bold"),
                           background="#1a1a1a", foreground=THEME["text_main"], relief="flat")
    admin_style.map("Admin.Treeview", background=[("selected", THEME["brand_red"])])

    # ── Dashboard ──
    tk.Label(dash_f, text="TODAY'S SALES OVERVIEW", font=("Arial", 22, "bold"),
             bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30,5))
    tk.Label(dash_f,
             text=f"GROSS: R{total_day:.2f}  |  CASH: R{total_cash:.2f}  |  CARD: R{total_card:.2f}",
             font=("Arial", 16, "bold"), bg=THEME["bg_main"], fg=THEME["text_main"]).pack(pady=10)
    tree_f = tk.Frame(dash_f, bg=THEME["bg_main"]); tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    admin_tree = ttk.Treeview(tree_f,
        columns=("Order","Time","Qty","Amount","Change","Method"),
        show="tree headings", style="Admin.Treeview")
    admin_tree.heading("#0",      text="");     admin_tree.column("#0",     width=40, stretch=False, anchor="center")
    admin_tree.heading("Order",   text="ORDER / ITEM"); admin_tree.column("Order",  width=250, anchor="w")
    admin_tree.heading("Time",    text="TIME");  admin_tree.column("Time",   width=120, anchor="center")
    admin_tree.heading("Qty",     text="QTY");   admin_tree.column("Qty",    width=80,  anchor="center")
    admin_tree.heading("Amount",  text="AMOUNT");admin_tree.column("Amount", width=120, anchor="e")
    admin_tree.heading("Change",  text="CHANGE");admin_tree.column("Change", width=120, anchor="e")
    admin_tree.heading("Method",  text="METHOD");admin_tree.column("Method", width=120, anchor="center")
    admin_tree.tag_configure("evenrow", background="#1e1e1e")
    admin_tree.tag_configure("oddrow",  background="#2a2a2a")
    admin_tree.pack(fill="both", expand=True); enable_scroll(admin_tree)

    for idx, t in enumerate(reversed(all_transactions)):
        if t["date"] == today:
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            total_qty = sum(i["qty"] for i in t.get("items", []))
            parent = admin_tree.insert("", "end", text="", tags=(tag,),
                values=(f"#{t.get('order_num')}", t["time"], total_qty,
                        f"R{t['amount']:.2f}", f"R{t.get('change',0):.2f}", t["method"]))
            for item in t.get("items", []):
                admin_tree.insert(parent, "end", text="", tags=(tag,),
                    values=(f"↳ {item['name']}", "", item["qty"],
                            f"R{item['price']*item['qty']:.2f}", "", ""))

    # ── Inventory ──
    tk.Label(inv_f, text="CURRENT INVENTORY LEVELS", font=("Arial", 22, "bold"),
             bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30,20))
    inv_tree_f = tk.Frame(inv_f, bg=THEME["bg_main"]); inv_tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    inv_tree = ttk.Treeview(inv_tree_f, columns=("Code","Name","Price","Stock"),
                             show="headings", style="Admin.Treeview")
    inv_tree.heading("Code",  text="STOCK CODE"); inv_tree.column("Code",  width=100, anchor="center")
    inv_tree.heading("Name",  text="PRODUCT NAME"); inv_tree.column("Name", width=400, anchor="w")
    inv_tree.heading("Price", text="UNIT PRICE"); inv_tree.column("Price", width=150, anchor="e")
    inv_tree.heading("Stock", text="ON HAND");    inv_tree.column("Stock", width=150, anchor="center")
    inv_tree.tag_configure("evenrow", background="#1e1e1e")
    inv_tree.tag_configure("oddrow",  background="#2a2a2a")
    inv_tree.tag_configure("lowstock",background="#3b1a00", foreground="#ff9800")
    inv_tree.pack(fill="both", expand=True); enable_scroll(inv_tree)
    for idx, (code, p) in enumerate(products.items()):
        tag = "lowstock" if p["stock"] <= 5 else ("evenrow" if idx % 2 == 0 else "oddrow")
        inv_tree.insert("", "end", values=(code, p["name"], f"R{p['price']:.2f}", p["stock"]), tags=(tag,))

    # ── Staff Logs ──
    tk.Label(staff_f, text="TODAY'S CASHIER LOGS", font=("Arial", 22, "bold"),
             bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30,20))
    staff_tree_f = tk.Frame(staff_f, bg=THEME["bg_main"]); staff_tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    staff_tree = ttk.Treeview(staff_tree_f, columns=("User","Login","Logout","Hours"),
                               show="headings", style="Admin.Treeview")
    staff_tree.heading("User",   text="CASHIER ID");   staff_tree.column("User",   width=150, anchor="center")
    staff_tree.heading("Login",  text="LOGIN TIME");   staff_tree.column("Login",  width=200, anchor="center")
    staff_tree.heading("Logout", text="LOGOUT TIME");  staff_tree.column("Logout", width=200, anchor="center")
    staff_tree.heading("Hours",  text="HOURS LOGGED"); staff_tree.column("Hours",  width=150, anchor="center")
    staff_tree.tag_configure("evenrow", background="#1e1e1e")
    staff_tree.tag_configure("oddrow",  background="#2a2a2a")
    staff_tree.pack(fill="both", expand=True); enable_scroll(staff_tree)
    for idx, s in enumerate(user_times):
        if s["date"] == today:
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            staff_tree.insert("", "end",
                values=(s["user"], s["login"], s.get("logout","ACTIVE"), s.get("hours", 0)),
                tags=(tag,))

    # ── Pay Outs ──
    tk.Label(pay_f, text="PAY OUTS LEDGER", font=("Arial", 22, "bold"),
             bg=THEME["bg_main"], fg=THEME["brand_red"]).pack(pady=(30,20))
    pay_tree_f = tk.Frame(pay_f, bg=THEME["bg_main"]); pay_tree_f.pack(fill="both", expand=True, padx=40, pady=10)
    pay_tree = ttk.Treeview(pay_tree_f, columns=("Date","Time","Reason","Amount","User"),
                             show="headings", style="Admin.Treeview")
    pay_tree.heading("Date",   text="DATE");       pay_tree.column("Date",   width=120, anchor="center")
    pay_tree.heading("Time",   text="TIME");       pay_tree.column("Time",   width=100, anchor="center")
    pay_tree.heading("Reason", text="REASON");     pay_tree.column("Reason", width=350, anchor="w")
    pay_tree.heading("Amount", text="AMOUNT");     pay_tree.column("Amount", width=120, anchor="e")
    pay_tree.heading("User",   text="TILL / USER");pay_tree.column("User",   width=120, anchor="center")
    pay_tree.tag_configure("evenrow", background="#1e1e1e")
    pay_tree.tag_configure("oddrow",  background="#2a2a2a")
    pay_tree.pack(fill="both", expand=True); enable_scroll(pay_tree)
    for idx, ex in enumerate(reversed(all_expenses)):
        tag = "evenrow" if idx % 2 == 0 else "oddrow"
        pay_tree.insert("", "end",
            values=(ex["date"], ex["time"], ex["reason"],
                    f"R{ex['amount']:.2f}", ex["user"]),
            tags=(tag,))

    # ── Sidebar buttons ──
    def export_report():
        update_activity()
        filename = _path(f"Daily_Report_{today}.html")
        try:
            rows_html = ""
            for t in all_transactions:
                if t["date"] == today:
                    items = "<br>".join([f"&bull; {i['qty']}x {i['name']}" for i in t.get("items",[])])
                    rows_html += (f"<tr><td>#{t.get('order_num')}</td><td>{t['time']}</td>"
                                  f"<td>{t['method']}</td><td><b>R{t['amount']:.2f}</b></td>"
                                  f"<td>{items}</td></tr>")
            html = f"""<!DOCTYPE html><html><head><title>ESM Daily Report</title>
            <style>body{{font-family:'Segoe UI',sans-serif;background:#f4f6f9;color:#333;padding:20px}}
            .container{{max-width:1000px;margin:auto;background:#fff;padding:30px;box-shadow:0 4px 8px rgba(0,0,0,.1)}}
            .header{{background:{THEME['brand_red']};color:#fff;padding:20px;text-align:center}}
            h1{{margin:0;font-size:28px}}h2{{color:{THEME['brand_red']};border-bottom:2px solid {THEME['brand_red']};padding-bottom:5px;margin-top:30px}}
            .grid{{display:flex;justify-content:space-between;margin:20px 0}}
            .card{{background:#f9f9f9;padding:20px;border-radius:8px;border-left:5px solid {THEME['brand_red']};width:30%;text-align:center}}
            .card h3{{margin:0 0 10px;color:#555;font-size:14px;text-transform:uppercase}}
            .card p{{margin:0;font-size:24px;font-weight:700}}
            table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}}
            th,td{{padding:10px 12px;border:1px solid #ddd;text-align:left}}
            th{{background:{THEME['brand_red']};color:#fff;font-weight:700;text-transform:uppercase}}
            tr:nth-child(even){{background:#f9f9f9}}.footer{{margin-top:40px;text-align:center;font-size:11px;color:#777}}</style></head>
            <body><div class="container">
            <div class="header"><h1>🥩 EAT SUM MEAT POS — Daily Report</h1><p>Date: {today} | Till: {TILL_NUMBER} | Generated: {datetime.datetime.now().strftime('%H:%M')}</p></div>
            <h2>SUMMARY</h2><div class="grid">
            <div class="card"><h3>Gross Revenue</h3><p>R{total_day:.2f}</p></div>
            <div class="card"><h3>Total Cash</h3><p>R{total_cash:.2f}</p></div>
            <div class="card"><h3>Total Card</h3><p>R{total_card:.2f}</p></div></div>
            <h2>TRANSACTIONS</h2>
            <table><tr><th>Order #</th><th>Time</th><th>Method</th><th>Total</th><th>Items</th></tr>
            {rows_html}</table>
            <div class="footer">ESM POS v{VERSION}</div></div></body></html>"""
            with open(filename, "w", encoding="utf-8") as f: f.write(html)
            webbrowser.open("file://" + os.path.realpath(filename))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def trigger_eod():
        update_activity()
        if messagebox.askyesno("Confirm", "Print Z-Report and close day?"): run_z_report_and_eod()

    def safe_exit():
        if messagebox.askyesno("Exit", "Shutdown terminal?"):
            log.info(f"Terminal shutdown by {current_user}")
            sys.exit()

    tk.Button(sidebar, text="📄 HTML EXPORT", font=nav_f, bg=THEME["btn_pay_card"], fg="white",
              pady=15, relief="flat", command=export_report).pack(fill="x", side="bottom", pady=2, padx=10)
    tk.Button(sidebar, text="🖨️ Z-REPORT",   font=nav_f, bg=THEME["btn_green"],    fg="white",
              pady=15, relief="flat", command=trigger_eod).pack(fill="x", side="bottom", pady=2, padx=10)
    tk.Button(sidebar, text="❌ EXIT APP",    font=nav_f, bg=THEME["btn_red"],      fg="white",
              pady=15, relief="flat", command=safe_exit).pack(fill="x", side="bottom", pady=20, padx=10)
    tk.Button(sidebar, text="⬅️ BACK TO TILL",font=nav_f, bg=THEME["btn_white"],   fg=THEME["text_main"],
              pady=15, relief="flat", command=win.destroy).pack(fill="x", side="bottom", pady=2, padx=10)

    show_frame(dash_f)


# ═══════════════════════════════════════════════════════════
#  LOGIN  (unchanged UI; added product sync on login)
# ═══════════════════════════════════════════════════════════
def login_screen():
    global current_user, login_start
    win = tk.Toplevel(); win.configure(bg=THEME["bg_main"])
    win.attributes("-fullscreen", True); win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", disable_event)
    win.bind("<Alt-F4>", block_shortcut)

    card = tk.Frame(win, bg=THEME["bg_panel"], bd=1, relief="solid")
    card.place(relx=0.5, rely=0.5, anchor="center", width=500, height=380)

    tk.Label(card, text="🥩 EAT SUM MEAT 🥩", font=("Arial", 28, "bold"),
             fg=THEME["brand_red"], bg=THEME["bg_panel"]).pack(pady=(40,5))
    tk.Label(card, text="SYSTEM LOGIN", font=("Arial", 16, "bold"),
             fg=THEME["text_dim"], bg=THEME["bg_panel"]).pack(pady=(0,20))

    # Show network status on login screen
    net_status_text = (f"● SERVER {CFG.get('server_host')}:{CFG.get('server_port')}"
                       if not CFG.get("offline_mode") else "● OFFLINE MODE")
    tk.Label(card, text=net_status_text, font=("Arial", 9),
             fg=THEME["text_dim"], bg=THEME["bg_panel"]).pack()

    ent = tk.Entry(card, font=("Arial", 30), justify="center",
                   bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat", bd=0)
    ent.pack(pady=10, ipady=10); ent.focus_set()

    def do_login(event=None):
        global current_user, login_start, last_activity_time, products
        raw = ent.get().strip().upper()
        code = SecurityManager.sanitise(raw, 16)
        if code in CASHIERS:
            current_user       = code
            login_start        = time.time()
            last_activity_time = time.time()
            log.info(f"Login: {current_user}")
            sec_log("LOGIN", f"user={current_user}")
            user_lbl.config(text=f"Username: {current_user}")

            if current_user == "ADMIN":
                # Place it perfectly under the TOTAL text
                admin_btn.place(x=20, y=85, width=140, height=35) 
            else:
                admin_btn.place_forget()

            # Attempt to pull latest products from back-office
            def on_products(data):
                global products
                if data:
                    products = data
                    log.info("Products synced from server on login")
            NetworkManager.fetch_products(callback=on_products)

            win.destroy()
            barcode_entry.focus_set()
        else:
            sec_log("INVALID_LOGIN", f"attempted_code={code[:4]}***")
            messagebox.showerror("Error", "Invalid Code")
            ent.delete(0, tk.END)

    ent.bind("<Return>", do_login)
    tk.Button(card, text="AUTHORIZE", font=("Arial", 16, "bold"),
              bg=THEME["btn_green"], fg="white", width=15,
              relief="flat", command=do_login).pack(pady=20)
    tk.Button(win, text="SHUTDOWN TERMINAL", font=("Arial", 10),
              bg=THEME["bg_main"], fg=THEME["text_dim"],
              relief="flat", command=sys.exit).place(relx=0.5, rely=0.9, anchor="center")
    win.wait_window()


def logoff(forced: bool = False):
    global current_user, login_start
    if not forced and (cart or held_cart):
        messagebox.showwarning("Warning", "Clear or Hold active sales first.")
        return
    if forced and cart:
        toggle_hold_cart("SAVE")

    if current_user and login_start:
        hours = round((time.time() - login_start) / 3600, 4)
        save_local_session({
            "date":   datetime.datetime.now().strftime("%Y-%m-%d"),
            "user":   current_user,
            "login":  datetime.datetime.fromtimestamp(login_start).strftime("%H:%M:%S"),
            "logout": datetime.datetime.now().strftime("%H:%M:%S"),
            "hours":  hours,
        })
        log.info(f"Logout: {current_user}  hours={hours:.2f}")
        sec_log("LOGOUT", f"hours={hours:.2f}", current_user)
        current_user = None; login_start = None
        user_lbl.config(text="Username: LOCKED")
        admin_btn.place_forget()
        login_screen()


# Auto-logout idle check
def check_idle():
    if current_user is not None:
        if time.time() - last_activity_time > AUTO_LOGOUT_SECONDS:
            log.info(f"Auto-logout: {current_user} idle > {AUTO_LOGOUT_SECONDS}s")
            logoff(forced=True)
    root.after(10000, check_idle)


# ═══════════════════════════════════════════════════════════
#  NETWORK STATUS INDICATOR  (live dot in status bar)
# ═══════════════════════════════════════════════════════════
def on_network_status_change(ok: bool):
    """Called from NetworkManager daemon thread — schedule UI update safely."""
    if root and net_indicator_lbl:
        root.after(0, lambda: net_indicator_lbl.config(
            text="● SERVER" if ok else "● OFFLINE",
            fg=THEME["lcd_fg"] if ok else THEME["highlight"]
        ))


# ═══════════════════════════════════════════════════════════
#  MAIN UI  (identical to v0.7.1 + network indicator)
# ═══════════════════════════════════════════════════════════
root = tk.Tk()
root.attributes("-fullscreen", True)
root.geometry("1024x768")
root.resizable(False, False)
root.configure(bg=THEME["bg_main"])
root.protocol("WM_DELETE_WINDOW", disable_event)
root.bind("<Alt-F4>", block_shortcut)
root.bind("<Any-KeyPress>", update_activity)
root.bind("<Any-Button>",   update_activity)
root.bind("<Motion>",       update_activity)

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview",
                background=THEME["bg_panel"], fieldbackground=THEME["bg_panel"],
                foreground=THEME["text_main"], font=("Arial", 14), rowheight=35, borderwidth=0)
style.configure("Treeview.Heading",
                background=THEME["btn_grey"], foreground=THEME["text_main"],
                font=("Arial", 12, "bold"), relief="flat", borderwidth=1)
style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
style.configure("Vertical.TScrollbar",
                background=THEME["btn_grey"], troughcolor=THEME["bg_panel"],
                bordercolor=THEME["bg_panel"], arrowcolor=THEME["text_main"])

left_col  = tk.Frame(root, bg=THEME["bg_main"], width=600, height=768)
left_col.place(x=0, y=0); left_col.pack_propagate(False)

right_col = tk.Frame(root, bg=THEME["bg_main"], width=424, height=768)
right_col.place(x=600, y=0); right_col.pack_propagate(False)

# ─── LEFT COLUMN ────────────────────────────────────────────
top_tot_f = tk.Frame(left_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=140)
top_tot_f.pack(fill="x", padx=5, pady=5); top_tot_f.pack_propagate(False)

tk.Label(top_tot_f, text="TOTAL:", font=("Arial", 32, "bold"),
         bg=THEME["bg_panel"], fg=THEME["brand_red"]).place(x=20, y=20)

total_val_lbl = tk.Label(top_tot_f, text="R0.00", font=("Consolas", 42, "bold"),
                          bg=THEME["lcd_bg"], fg=THEME["lcd_fg"], bd=0, anchor="e", width=12)
total_val_lbl.place(x=180, y=10)

sub_val_lbl = tk.Label(top_tot_f, text="CHG R0.00", font=("Arial", 24, "bold"),
                        bg=THEME["bg_panel"], fg=THEME["text_main"], anchor="e")
sub_val_lbl.place(x=250, y=85, width=330)

cart_f = tk.Frame(left_col, bd=1, relief="solid", height=380, bg=THEME["bg_panel"])
cart_f.pack(fill="x", padx=5, pady=0); cart_f.pack_propagate(False)

cart_scroll = ttk.Scrollbar(cart_f, orient="vertical")
cols        = ("Code", "Qty", "Description", "Unit Price", "Amount")
cart_tree   = ttk.Treeview(cart_f, columns=cols, show="headings",
                            selectmode="browse", yscrollcommand=cart_scroll.set)
cart_scroll.config(command=cart_tree.yview)
cart_tree.heading("Code",        text="CODE");     cart_tree.column("Code",       width=90,  anchor="center")
cart_tree.heading("Qty",         text="QTY");      cart_tree.column("Qty",        width=50,  anchor="center")
cart_tree.heading("Description", text="DESCRIPTION"); cart_tree.column("Description", width=250, anchor="w")
cart_tree.heading("Unit Price",  text="PRICE");    cart_tree.column("Unit Price", width=90,  anchor="e")
cart_tree.heading("Amount",      text="TOTAL");    cart_tree.column("Amount",     width=90,  anchor="e")
cart_scroll.pack(side="right", fill="y")
cart_tree.pack(side="left", fill="both", expand=True)

l_actions_f = tk.Frame(left_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=180)
l_actions_f.pack(fill="x", padx=5, pady=5); l_actions_f.pack_propagate(False)

btn_font = ("Arial", 11, "bold")
btn_pad  = {"padx": 4, "pady": 4, "sticky": "nsew"}
for i in range(2): l_actions_f.rowconfigure(i, weight=1)
for i in range(6): l_actions_f.columnconfigure(i, weight=1)

tk.Button(l_actions_f, text="↑",        font=("Arial", 16, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=lambda: cart_tree.yview_scroll(-1, "units")).grid(row=0, column=0, **btn_pad)
tk.Button(l_actions_f, text="↓",        font=("Arial", 16, "bold"), bg=THEME["btn_grey"], fg=THEME["text_main"], relief="flat", command=lambda: cart_tree.yview_scroll(1,  "units")).grid(row=0, column=1, **btn_pad)
tk.Button(l_actions_f, text="VOID\nITEM",  font=btn_font, bg=THEME["btn_red"],   fg="white",              relief="flat", command=void_item).grid(row=0, column=2, **btn_pad)
tk.Button(l_actions_f, text="HOLD\nSALE",  font=btn_font, bg=THEME["btn_grey"],  fg=THEME["text_main"],   relief="flat", command=lambda: toggle_hold_cart("SAVE")).grid(row=0, column=3, **btn_pad)
tk.Button(l_actions_f, text="RECALL\nSALE",font=btn_font, bg=THEME["btn_grey"],  fg=THEME["text_main"],   relief="flat", command=lambda: toggle_hold_cart("LOAD")).grid(row=0, column=4, **btn_pad)
tk.Button(l_actions_f, text="CLEAR\nCART", font=btn_font, bg=THEME["btn_white"], fg=THEME["text_main"], bd=1, relief="flat", command=clear_cart).grid(row=0, column=5, **btn_pad)

tk.Button(l_actions_f, text="QTY",          font=("Arial",12,"bold"), bg=THEME["btn_grey"],  fg=THEME["text_main"], relief="flat").grid(row=1, column=0, **btn_pad)
tk.Button(l_actions_f, text="MARK\nDOWN",   font=btn_font,            bg=THEME["btn_grey"],  fg=THEME["text_main"], relief="flat", command=open_markdown).grid(row=1, column=1, **btn_pad)
tk.Button(l_actions_f, text="MANUAL\nSELECT",font=btn_font,           bg=THEME["btn_white"], fg=THEME["text_main"], bd=1, relief="flat", command=open_manual_select).grid(row=1, column=2, **btn_pad)
tk.Button(l_actions_f, text="LOG OFF",       font=btn_font,            bg=THEME["btn_white"], fg=THEME["text_main"], bd=1, relief="flat", command=logoff).grid(row=1, column=3, **btn_pad)
tk.Button(l_actions_f, text="REFUND",        font=btn_font,            bg=THEME["btn_red"],   fg="white",            relief="flat").grid(row=1, column=4, **btn_pad)
tk.Button(l_actions_f, text="2ND\nFUNC",     font=btn_font,            bg=THEME["btn_grey"],  fg=THEME["text_main"], relief="flat", command=open_2nd_functions).grid(row=1, column=5, **btn_pad)

# ─── STATUS BAR ─────────────────────────────────────────────
stat_f = tk.Frame(left_col, bg=THEME["bg_main"], height=48)
stat_f.pack(fill="x", padx=5, pady=(0,5)); stat_f.pack_propagate(False)

user_lbl = tk.Label(stat_f, text="Username: LOCKED", font=("Arial", 12, "bold"),
                     bg=THEME["bg_panel"], fg=THEME["text_main"],
                     bd=1, relief="solid", anchor="w", width=22)
user_lbl.pack(side="left", padx=2, ipady=4)

tk.Label(stat_f, text=f"Till {TILL_NUMBER}", font=("Arial", 12, "bold"),
         bg=THEME["bg_panel"], fg=THEME["text_main"],
         bd=1, relief="solid", width=8).pack(side="left", padx=2, ipady=4)

prev_inv_lbl = tk.Label(stat_f, text="Prev. Invoice #0", font=("Arial", 12, "bold"),
                          bg=THEME["bg_panel"], fg=THEME["text_main"],
                          bd=1, relief="solid", width=16)
prev_inv_lbl.pack(side="left", padx=2, ipady=4)

# ── Network indicator (NEW) ────────────────────────────────
net_indicator_lbl = tk.Label(stat_f, text="● OFFLINE", font=("Arial", 10, "bold"),
                               bg=THEME["bg_panel"], fg=THEME["highlight"],
                               bd=1, relief="solid", width=10)
net_indicator_lbl.pack(side="left", padx=2, ipady=4)

# Create the admin button but don't place it yet (do_login handles that)
admin_btn = tk.Button(top_tot_f, text="⚙ ADMIN PANEL", font=("Arial", 11, "bold"),
                       bg=THEME["brand_red"], fg="white", relief="flat", command=admin_panel)

# ─── RIGHT COLUMN ────────────────────────────────────────────
logo_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=120)
logo_f.pack(fill="x", padx=(0,5), pady=5); logo_f.pack_propagate(False)
tk.Label(logo_f, text="EAT SUM MEAT", font=("Arial", 32, "bold"),
         bg=THEME["bg_panel"], fg=THEME["brand_red"]).place(relx=0.5, rely=0.5, anchor="center")

input_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=90)
input_f.pack(fill="x", padx=(0,5), pady=0); input_f.pack_propagate(False)
tk.Label(input_f, text="ENTER BARCODE / SCAN", font=("Arial", 10, "bold"),
         bg=THEME["bg_panel"], fg=THEME["text_dim"]).place(x=15, y=5)

def on_scan(e):
    c = barcode_entry.get().strip()
    if c: add_product(c)
    barcode_entry.focus_set(); update_activity()

barcode_entry = tk.Entry(input_f, font=("Arial", 22, "bold"),
                          bg=THEME["btn_white"], fg=THEME["text_main"],
                          relief="flat", bd=0, justify="center")
barcode_entry.place(x=15, y=30, width=380, height=45)
barcode_entry.bind("<Return>", on_scan)

last_scan_f = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid", height=30)
last_scan_f.pack(fill="x", padx=(0,5), pady=(5,0)); last_scan_f.pack_propagate(False)
last_scan_lbl = tk.Label(last_scan_f, text="READY TO SCAN", font=("Arial", 11, "bold"),
                           bg=THEME["bg_panel"], fg=THEME["text_dim"])
last_scan_lbl.pack(expand=True, fill="both")

interaction_frame = tk.Frame(right_col, bg=THEME["bg_panel"], bd=1, relief="solid")
interaction_frame.pack(fill="both", expand=True, padx=(0,5), pady=5)

left_int  = tk.Frame(interaction_frame, bg=THEME["bg_panel"])
left_int.pack(side="left", fill="both", expand=True, padx=(5,2), pady=5)

right_int = tk.Frame(interaction_frame, bg=THEME["bg_panel"], width=135)
right_int.pack(side="right", fill="y", padx=(2,5), pady=5); right_int.pack_propagate(False)

np_grid   = tk.Frame(left_int, bg=THEME["bg_panel"]); np_grid.pack(side="top",    fill="both", expand=True)
cash_grid = tk.Frame(left_int, bg=THEME["bg_panel"]); cash_grid.pack(side="bottom", fill="x",  pady=(5,0))

for i in range(3): np_grid.columnconfigure(i, weight=1, uniform="np")
for i in range(4): np_grid.rowconfigure(i,    weight=1, uniform="np")

def num_clk(v):
    if v == "C": barcode_entry.delete(0, tk.END)
    else:         barcode_entry.insert(tk.END, v)
    barcode_entry.focus_set(); update_activity()

keys = [("7","8","9"), ("4","5","6"), ("1","2","3"), (".","0","C")]
for r, row in enumerate(keys):
    for c, key in enumerate(row):
        color = THEME["btn_red"] if key == "C" else THEME["btn_grey"]
        tk.Button(np_grid, text=key, font=("Arial", 18, "bold"),
                  bg=color, fg="white", relief="flat",
                  command=lambda k=key: num_clk(k)).grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

for i in range(4): cash_grid.columnconfigure(i, weight=1, uniform="cash")

for c, amt in enumerate([200, 100, 50, 20]):
    tk.Button(cash_grid, text=f"+R{amt}", font=("Arial", 11, "bold"),
              bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat",
              command=lambda a=amt: add_cash(a)).grid(row=0, column=c, padx=2, pady=2, sticky="nsew", ipady=8)
for c, amt in enumerate([10, 5, 2, 1]):
    tk.Button(cash_grid, text=f"+R{amt}", font=("Arial", 11, "bold"),
              bg=THEME["btn_white"], fg=THEME["text_main"], relief="flat",
              command=lambda a=amt: add_cash(a)).grid(row=1, column=c, padx=2, pady=2, sticky="nsew", ipady=8)

tk.Button(right_int, text="←", font=("Arial", 22, "bold"),
          bg=THEME["btn_grey"], fg="white", relief="flat",
          command=lambda: [barcode_entry.delete(len(barcode_entry.get())-1), update_activity()]
          ).pack(side="top", fill="x", pady=(0,5), ipady=8)
tk.Button(right_int, text="PAY\nCASH", font=("Arial", 20, "bold"),
          bg=THEME["btn_pay_cash"], fg="white", relief="flat",
          command=lambda: process_payment("CASH")).pack(side="top", fill="both", expand=True, pady=2)
tk.Button(right_int, text="PAY\nCARD", font=("Arial", 20, "bold"),
          bg=THEME["btn_pay_card"], fg="white", relief="flat",
          command=lambda: process_payment("CARD")).pack(side="bottom", fill="both", expand=True, pady=(2,0))


# ═══════════════════════════════════════════════════════════
#  BOOT  SEQUENCE
# ═══════════════════════════════════════════════════════════
load_system_data()
products      = load_products()
order_counter = init_order_counter() + 1

# Register network status callback so the UI dot updates live
NetworkManager.on_status_change(on_network_status_change)

# Start background services
NetworkManager.start_retry_loop()   # drain offline queue
root.after(800,   lambda: NetworkManager.ping())      # initial ping
root.after(30000, lambda: _periodic_ping())           # ping every 30 s

def _periodic_ping():
    NetworkManager.ping()
    root.after(30000, _periodic_ping)

root.after(100,   check_for_updates)
root.after(500,   login_screen)
root.after(10000, check_idle)

log.info(f"ESM POS v{VERSION} started | Till {TILL_NUMBER} | "
         f"Server {CFG.get('server_host')}:{CFG.get('server_port')}")

root.mainloop()
