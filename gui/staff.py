"""gui/staff.py - شاشات الموظفين

قائمة الموظفين (زرين) -> تسجيل موظف  |  الموظفين (عرض + تفاصيل + سجل دوام)
"""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

import db
from device import DeviceError
from gui import access
from gui import common as C

JOB_SUGGESTIONS = ("مدرب", "استقبال", "إدارة", "محاسب", "نظافة", "أمن")
STATE_TEXT = {"in": "داخل النادي", "out": "خرج", "absent": "ما حضر"}
STATE_TAG = {"in": "ok", "out": "", "absent": "muted"}

LIST_COLUMNS = [
    ("name", "الاسم", 200, "e"),
    ("job", "الوظيفة", 110, "center"),
    ("phone", "الهاتف", 110, "center"),
    ("state", "الحالة اليوم", 110, "center"),
    ("first", "أول دخول", 80, "center"),
    ("last", "آخر خروج", 80, "center"),
    ("worked", "مدة العمل", 100, "center"),
]

HISTORY_COLUMNS = [
    ("date", "التاريخ", 110, "center"),
    ("in", "دخول", 80, "center"),
    ("out", "خروج", 80, "center"),
    ("worked", "مدة العمل", 110, "center"),
    ("note", "ملاحظة", 170, "center"),
]


def _entry(parent, var, **kw):
    return tk.Entry(parent, textvariable=var, font=C.font(14), justify="right", relief="flat",
                    bg="white", **kw)


def _button(parent, text, command, color, **kw):
    return tk.Button(parent, text=text, command=command, font=C.font(13, True), bg=color,
                     fg="white", activeforeground="white", relief="flat", cursor="hand2", **kw)


# ============================================================ القائمة (زرين)
class StaffMenuWindow(access.GatedWindow):
    """قائمة الموظفين. محمية بكلمة سر "staff"، وبتتسكر لحالها (ومعها شاشاتها) بعد فترة بدون نشاط."""

    def __init__(self, parent, dev):
        super().__init__(parent, "staff")
        self.dev = dev
        self._windows = {}
        self.title("الموظفين")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=20)
        self.resizable(False, False)
        C.center_on(self, parent, 520, 380)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        tk.Label(self, text="الموظفين", font=C.font(20, True), bg=C.COLORS["bg"],
                 fg=C.COLORS["text"]).pack(pady=(0, 18))
        row = tk.Frame(self, bg=C.COLORS["bg"])
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1, uniform="s")
        _button(row, "تسجيل موظف", self._open_register, C.COLORS["save"], height=3
                ).grid(row=0, column=1, sticky="ew", padx=6)
        _button(row, "الموظفين", self._open_list, C.COLORS["btn"], height=3
                ).grid(row=0, column=0, sticky="ew", padx=6)
        _button(self, "تغيير كلمة السر", lambda: access.change_password(self, "staff"),
                C.COLORS["panel"], height=2).pack(fill="x", pady=(16, 0), padx=6)
        _button(self, "إغلاق", self.destroy, C.COLORS["cancel"], height=2
                ).pack(fill="x", pady=(8, 0), padx=6)

    def _show_child(self, key, factory):
        win = self._windows.get(key)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        self._windows[key] = factory()

    def _open_register(self):
        self._show_child("register", lambda: RegisterStaffWindow(self, self.dev, on_done=self._refresh_list))

    def _open_list(self):
        self._show_child("list", lambda: StaffListWindow(self, self.dev))

    def _refresh_list(self):
        win = self._windows.get("list")
        if win is not None and win.winfo_exists():
            win.refresh()


# ============================================================ تسجيل موظف
class RegisterStaffWindow(tk.Toplevel):
    def __init__(self, parent, dev, on_done=None):
        super().__init__(parent)
        self.dev = dev
        self.on_done = on_done
        self.busy = False
        self.title("تسجيل موظف")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=18)
        self.resizable(False, False)
        C.center_on(self, parent, 520, 470)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.name_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.job_var = tk.StringVar()
        self._build()
        self.name_entry.focus_set()
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self._on_close())

    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, text="تسجيل موظف جديد", font=C.font(20, True), bg=bg, fg=text
                 ).pack(pady=(0, 14))
        form = tk.Frame(self, bg=bg)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)

        def row(r, label, widget):
            tk.Label(form, text=label, font=C.font(13), bg=bg, fg=text, anchor="e"
                     ).grid(row=r, column=1, sticky="e", padx=(10, 0), pady=8)
            widget.grid(row=r, column=0, sticky="ew", pady=8)
            return widget

        self.name_entry = row(0, "الاسم", _entry(form, self.name_var))
        row(1, "رقم الهاتف", _entry(form, self.phone_var))
        row(2, "الوظيفة", ttk.Combobox(form, textvariable=self.job_var, values=JOB_SUGGESTIONS,
                                       font=C.font(14), justify="right"))

        self.lbl_state = tk.Label(self, text="", font=C.font(12, True), bg=bg, fg="#fbc531",
                                  wraplength=460, justify="center")
        self.lbl_state.pack(pady=(14, 6), fill="x")
        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", pady=(6, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        self.btn_save = _button(btns, "حفظ وتسجيل البصمة", self._save, C.COLORS["save"], height=2)
        self.btn_save.grid(row=0, column=1, sticky="ew", padx=5)
        self.btn_cancel = _button(btns, "إلغاء", self._on_close, C.COLORS["cancel"], height=2)
        self.btn_cancel.grid(row=0, column=0, sticky="ew", padx=5)

    def _set_busy(self, busy, message=""):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_save.config(state=state)
        self.btn_cancel.config(state=state)
        self.lbl_state.config(text=message)

    def _save(self):
        if self.busy:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("تنبيه", "اكتب اسم الموظف", parent=self)
            return
        phone, job = self.phone_var.get().strip(), self.job_var.get().strip()
        self._set_busy(True, "حط إصبعك على جهاز البصمة 3 مرات حسب تعليمات شاشة الجهاز...")

        def work():
            taken = {uid for uid, _ in self.dev.device_users()}    # أرقام الجهاز (أدمن وغيره)
            uid = db.peek_next_staff_uid(taken)                     # رقم الموظف: 1 - 99
            self.dev.register_user_with_fingerprint(uid)          # بصمة أولاً
            try:
                return db.add_staff(name, phone, job, device_uid=uid)
            except Exception:
                try:
                    self.dev.delete_user(uid)                      # ما نخلي مستخدم عالق
                except DeviceError:
                    pass
                raise

        C.run_in_thread(self, work, lambda res, err: self._done(name, res, err))

    def _done(self, name, result, error):
        if not self.winfo_exists():
            return
        self._set_busy(False)
        if error is not None:
            messagebox.showerror("ما تم التسجيل", str(error), parent=self)
            return
        messagebox.showinfo("تم", f"تم تسجيل الموظف «{name}» بنجاح\nرقمه على الجهاز: {result['device_uid']}",
                            parent=self)
        if self.on_done:
            self.on_done()
        self.destroy()

    def _on_close(self):
        if not self.busy:
            self.destroy()


# ============================================================ قائمة الموظفين
class StaffListWindow(tk.Toplevel):
    REFRESH_MS = 15_000       # تحديث تلقائي (عشان حالة دخول/خروج تتحدث)

    def __init__(self, parent, dev):
        super().__init__(parent)
        self.dev = dev
        self._timer = None
        self._details = None
        self.title("الموظفين")
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 900, 600)
        self.transient(parent)
        self.count_var = tk.StringVar()
        self._build()
        self.refresh()
        self._schedule()
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self):
        bg = C.COLORS["bg"]
        tk.Label(self, text="الموظفين — حالة اليوم", font=C.font(18, True), bg=C.COLORS["staff"],
                 fg="white", pady=8).pack(fill="x", pady=(0, 10))

        # الأزرار والعدّاد أول (تحت) عشان ما ينقصوا بالشاشات الصغيرة
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x")
        tk.Label(self, textvariable=self.count_var, font=C.font(12, True), bg=bg,
                 fg=C.COLORS["muted"]).pack(side="bottom", anchor="e", pady=(0, 8))

        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=4)
        self.tree, scroll = C.make_tree(frame, LIST_COLUMNS, height=8)
        self.tree.tag_configure("muted", foreground=C.COLORS["muted"])
        scroll.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._open_details())
        self.tree.bind("<Return>", lambda e: self._open_details())

        btns.columnconfigure((0, 1, 2), weight=1, uniform="b")
        _button(btns, "تفاصيل وسجل الدوام", self._open_details, C.COLORS["btn"], height=2
                ).grid(row=0, column=2, sticky="ew", padx=5)
        _button(btns, "تحديث", self.refresh, C.COLORS["panel"], height=2
                ).grid(row=0, column=1, sticky="ew", padx=5)
        _button(btns, "إغلاق", self.destroy, C.COLORS["cancel"], height=2
                ).grid(row=0, column=0, sticky="ew", padx=5)

    def refresh(self):
        rows = db.staff_today()
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        counts = {"in": 0, "out": 0, "absent": 0}
        for r in rows:
            counts[r["state"]] += 1
            tag = STATE_TAG[r["state"]]
            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,) if tag else (),
                             values=(r["name"], r["job_title"] or "", r["phone"] or "",
                                     STATE_TEXT[r["state"]], r["first_in"] or "—",
                                     r["last_out"] or "—",
                                     C.fmt_hours(r["worked_minutes"]) if r["worked_minutes"] else "—"))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])
        self.count_var.set(f"عدد الموظفين: {len(rows)}   |   داخل النادي الآن: {counts['in']}   |   "
                           f"خرجوا: {counts['out']}   |   ما حضروا: {counts['absent']}")

    def _schedule(self):
        self._timer = self.after(self.REFRESH_MS, self._auto)

    def _auto(self):
        self.refresh()
        self._schedule()

    def _open_details(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("تنبيه", "اختر موظف من القائمة أولاً", parent=self)
            return
        if self._details is not None and self._details.winfo_exists():
            self._details.destroy()
        self._details = StaffDetails(self, int(sel[0]), self.dev, on_change=self.refresh)

    def destroy(self):
        if self._timer is not None:
            try:
                self.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None
        super().destroy()


# ============================================================ تفاصيل موظف
class StaffDetails(tk.Toplevel):
    """بيانات الموظف + سجل دوامه (آخر 30 يوم) + تعديل + إيقاف."""

    def __init__(self, parent, staff_id, dev, on_change=None):
        super().__init__(parent)
        self.staff_id = staff_id
        self.dev = dev
        self.on_change = on_change
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 720, 640)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        self.title_var = tk.StringVar()
        self.info_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self._build()
        self.reload()

    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, textvariable=self.title_var, font=C.font(22, True), bg=bg, fg=text
                 ).pack(anchor="e")
        tk.Label(self, textvariable=self.info_var, font=C.font(13), bg=bg, fg=C.COLORS["muted"],
                 justify="right").pack(anchor="e", pady=(2, 8))

        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x", pady=(10, 0))
        btns.columnconfigure((0, 1, 2), weight=1, uniform="b")
        _button(btns, "تعديل البيانات", self._edit, C.COLORS["btn"], height=2
                ).grid(row=0, column=2, sticky="ew", padx=5)
        _button(btns, "إيقاف الموظف", self._deactivate, C.COLORS["bad"], height=2
                ).grid(row=0, column=1, sticky="ew", padx=5)
        _button(btns, "إغلاق", self.destroy, C.COLORS["cancel"], height=2
                ).grid(row=0, column=0, sticky="ew", padx=5)

        tk.Label(self, textvariable=self.total_var, font=C.font(13, True), bg=bg, fg="#fbc531"
                 ).pack(side="bottom", anchor="e", pady=(6, 0))

        tk.Label(self, text="سجل الدوام (آخر 30 يوم)", font=C.font(13, True), bg=bg, fg=text
                 ).pack(anchor="e")
        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=6)
        self.tree, scroll = C.make_tree(frame, HISTORY_COLUMNS, height=10)
        scroll.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)

    def reload(self):
        s = db.get_staff(self.staff_id)
        if not s:
            self.destroy()
            return
        self.title_var.set(s["name"])
        self.info_var.set(f"الوظيفة: {s['job_title'] or '—'}   |   الهاتف: {s['phone'] or '—'}   |   "
                          f"رقم الجهاز: {s['device_uid']}")
        today = date.today().isoformat()
        self.tree.delete(*self.tree.get_children())
        total, days = 0, 0
        for h in db.staff_history(self.staff_id, 30):
            if h["still_in"]:
                note, tag = ("موجود الآن", "ok") if h["date"] == today else ("ما سجّل خروج", "warn")
            else:
                note, tag = "", ""
            total += h["worked_minutes"]
            days += 1
            self.tree.insert("", "end", tags=(tag,) if tag else (),
                             values=(h["date"], h["first_in"] or "—", h["last_out"] or "—",
                                     C.fmt_hours(h["worked_minutes"]) if h["worked_minutes"] else "—",
                                     note))
        self.total_var.set(f"إجمالي ساعات العمل: {C.fmt_hours(total)}  (في {days} يوم دوام)")

    def _edit(self):
        s = db.get_staff(self.staff_id)
        EditStaffDialog(self, s, on_saved=self._saved)

    def _saved(self):
        self.reload()
        if self.on_change:
            self.on_change()

    def _deactivate(self):
        s = db.get_staff(self.staff_id)
        if not messagebox.askyesno(
                "إيقاف موظف",
                f"إيقاف «{s['name']}»؟\nبتنحذف بصمته من الجهاز، وسجلات دوامه القديمة بتضل محفوظة.",
                parent=self):
            return

        def work():
            self.dev.delete_user(s["device_uid"])        # أول من الجهاز، إذا فشل ما بنوقفه بالقاعدة
            db.deactivate_staff(self.staff_id)

        C.run_in_thread(self, work, lambda res, err: self._deactivated(s["name"], err))

    def _deactivated(self, name, error):
        if not self.winfo_exists():
            return
        if error is not None:
            messagebox.showerror("ما تم الإيقاف", str(error), parent=self)
            return
        messagebox.showinfo("تم", f"تم إيقاف «{name}»", parent=self)
        if self.on_change:
            self.on_change()
        self.destroy()


class EditStaffDialog(tk.Toplevel):
    def __init__(self, parent, staff, on_saved=None):
        super().__init__(parent)
        self.staff_id = staff["id"]
        self.on_saved = on_saved
        self.title("تعديل بيانات الموظف")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=18)
        self.resizable(False, False)
        C.center_on(self, parent, 480, 340)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        self.name_var = tk.StringVar(value=staff["name"])
        self.phone_var = tk.StringVar(value=staff["phone"] or "")
        self.job_var = tk.StringVar(value=staff["job_title"] or "")
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        form = tk.Frame(self, bg=bg)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        for r, (label, widget) in enumerate((
                ("الاسم", _entry(form, self.name_var)),
                ("رقم الهاتف", _entry(form, self.phone_var)),
                ("الوظيفة", ttk.Combobox(form, textvariable=self.job_var, values=JOB_SUGGESTIONS,
                                         font=C.font(14), justify="right")))):
            tk.Label(form, text=label, font=C.font(13), bg=bg, fg=text, anchor="e"
                     ).grid(row=r, column=1, sticky="e", padx=(10, 0), pady=8)
            widget.grid(row=r, column=0, sticky="ew", pady=8)
        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", pady=(14, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        _button(btns, "حفظ", self._save, C.COLORS["save"], height=2).grid(row=0, column=1, sticky="ew", padx=5)
        _button(btns, "إلغاء", self.destroy, C.COLORS["cancel"], height=2).grid(row=0, column=0, sticky="ew", padx=5)
        self.bind("<Return>", lambda e: self._save())

    def _save(self):
        try:
            db.update_staff(self.staff_id, self.name_var.get(), self.phone_var.get(), self.job_var.get())
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
