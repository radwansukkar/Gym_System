"""gui/common.py - أدوات مشتركة للواجهة: ألوان، خطوط، أصوات، تحويل أرقام، تشغيل بالخلفية"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

FONT = "Tahoma"          # بيدعم العربي على ويندوز

COLORS = {
    "bg": "#1e272e",
    "panel": "#2f3640",
    "text": "#f5f6fa",
    "muted": "#a4b0be",
    "ok": "#2e7d32",       # اشتراك ساري
    "warn": "#ef6c00",     # قرب ينتهي
    "bad": "#c62828",      # منتهي / بصمة غير معروفة
    "staff": "#1565c0",    # موظف (دخول)
    "staff_out": "#6a1b9a",  # موظف (خروج)
    "idle": "#37474f",
    "btn": "#0984e3",
    "btn_active": "#0652a3",
    "save": "#2e7d32",
    "cancel": "#636e72",
}

WARN_DAYS = 3            # لون برتقالي إذا باقي هالعدد من الأيام أو أقل


def resource_path(relative):
    """مسار ملف داخل المشروع (بيشتغل كمان لما نحوّله لـ exe بـ PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


_icon_ref = None        # لازم نخزن الصورة حتى ما يمسحها بايثون من الذاكرة


def apply_icon(root):
    """أيقونة البرنامج = شعار الجيم، لكل النوافذ (assets/icon.ico و icon.png)."""
    global _icon_ref
    if os.name == "nt":
        try:
            root.iconbitmap(default=resource_path("assets/icon.ico"))
            return
        except tk.TclError:
            pass
    try:
        _icon_ref = tk.PhotoImage(file=resource_path("assets/icon.png"))
        root.iconphoto(True, _icon_ref)
    except tk.TclError:
        pass            # بدون أيقونة أحسن من إنو البرنامج ما يشتغل


def font(size, bold=False):
    return (FONT, size, "bold" if bold else "normal")


# ------------------------------------------------------------ الأرقام
# بنقبل أرقام عربية (٠١٢...) وفاصلة عربية، لأن الكيبورد ممكن يكون عربي
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫,،", "01234567890123456789...")


def parse_number(text, label, integer=False, minimum=0):
    cleaned = str(text).strip().translate(_DIGITS)
    if not cleaned:
        raise ValueError(f"اكتب {label}")
    try:
        value = int(cleaned) if integer else float(cleaned)
    except ValueError:
        raise ValueError(f"{label} لازم يكون رقم صحيح") from None
    if value < minimum:
        raise ValueError(f"{label} ما بيصير يكون أقل من {minimum}")
    return value


def fmt_money(x):
    return f"{x:g}"


def fmt_hours(minutes):
    return f"{minutes // 60}:{minutes % 60:02d} ساعة"


def sub_state(m):
    """
    حالة اللاعب (من db.get_member / search_members): (tag, نص).
    منتهي = كل أنواع اشتراكه منتهية. قرب الانتهاء = أي نوع ساري باقي له WARN_DAYS أو أقل.
    """
    if not m["active"]:
        return "bad", "منتهي"
    if m["min_days_left"] <= WARN_DAYS:
        return "warn", "قرب الانتهاء"
    return "ok", "ساري"


def types_text(m):
    """كل أنواع اشتراك اللاعب: "حديد + ايروبيك"."""
    return " + ".join(x["sub_type"] for x in m["subs"])


def days_text(m):
    """المتبقي لكل نوع. نوع واحد: "20 يوم". أكتر من نوع: "حديد 20 · ايروبيك منتهي"."""
    subs = m["subs"]
    if len(subs) == 1:
        return f"{subs[0]['days_left']} يوم" if subs[0]["active"] else "—"
    return " · ".join(f"{x['sub_type']} {x['days_left']}" if x["active"] else f"{x['sub_type']} منتهي"
                      for x in subs)


# ------------------------------------------------------------ جداول
def setup_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Gym.Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"],
                    foreground=COLORS["text"], rowheight=32, font=font(12), borderwidth=0)
    style.configure("Gym.Treeview.Heading", background="#485460", foreground="white",
                    font=font(12, True), relief="flat")
    style.map("Gym.Treeview", background=[("selected", COLORS["btn"])],
              foreground=[("selected", "white")])
    style.map("Gym.Treeview.Heading", background=[("active", "#57606f")])


def make_tree(parent, columns, height=10):
    """
    columns: [(key, عنوان, عرض, محاذاة)] بترتيب القراءة العربي: الأول = أقصى اليمين.
    بيرجع (tree, scrollbar). المستخدم بيعمل pack: scrollbar عاليسار، tree عاليمين.
    """
    keys = [c[0] for c in columns]
    tree = ttk.Treeview(parent, columns=keys, displaycolumns=list(reversed(keys)),
                        show="headings", style="Gym.Treeview", height=height,
                        selectmode="browse")
    for key, title, width, anchor in columns:
        tree.heading(key, text=title, anchor="center")
        tree.column(key, width=width, anchor=anchor, stretch=True)
    tree.tag_configure("ok", foreground="#7bed9f")
    tree.tag_configure("warn", foreground="#ffa502")
    tree.tag_configure("bad", foreground="#ff6b81")
    scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    return tree, scroll


# ------------------------------------------------------------ الصوت
def play_sound(kind):
    """kind: ok | warn | bad. على ويندوز بس (winsound)، وعلى غيره بصمت."""
    try:
        import winsound
    except ImportError:
        return

    def _play():
        try:
            if kind == "ok":
                winsound.Beep(1200, 150)
            elif kind == "warn":
                winsound.Beep(900, 150)
                winsound.Beep(900, 150)
            else:
                winsound.Beep(400, 500)
                winsound.Beep(300, 700)
        except RuntimeError:
            pass

    threading.Thread(target=_play, daemon=True).start()


# ------------------------------------------------------------ تشغيل بالخلفية
def run_in_thread(widget, func, on_done, poll_ms=100):
    """
    ينفذ func() بـ thread منفصل (حتى ما تعلق الواجهة)، وبعدها بينادي
    on_done(result, error) على thread الواجهة. tkinter مش آمن من threads ثانية.
    """
    q = queue.Queue()

    def worker():
        try:
            q.put((func(), None))
        except Exception as e:  # noqa: BLE001
            q.put((None, e))

    def poll():
        try:
            result, error = q.get_nowait()
        except queue.Empty:
            try:
                widget.after(poll_ms, poll)
            except tk.TclError:
                pass            # النافذة انسكرت
            return
        on_done(result, error)

    threading.Thread(target=worker, daemon=True).start()
    widget.after(poll_ms, poll)


def center_on(win, parent, width, height):
    """يوسّط النافذة على الأب، وبيصغّرها إذا أكبر من الشاشة (عشان الأزرار ما تطلع برا)."""
    parent.update_idletasks()
    width = min(width, win.winfo_screenwidth() - 40)
    height = min(height, win.winfo_screenheight() - 90)
    if parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    else:                       # الأب مخفي (شاشة تسجيل الدخول): وسّط على الشاشة
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
