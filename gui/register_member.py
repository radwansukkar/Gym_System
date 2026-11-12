"""gui/register_member.py - شاشة تسجيل لاعب جديد (بيانات + اشتراك أو أكتر + دفع + بصمة)

اللاعب ممكن يشترك بأكثر من نوع (حديد + ايروبيك...) ولكل نوع مدته وسعره ودفعته.
"""
import tkinter as tk
from tkinter import messagebox, ttk

import db
from device import DeviceError
from gui import common as C

DURATIONS = ("30", "90", "180", "365")          # اقتراحات للمدة (بتقدر تكتب أي رقم)
DISABLED_BG = "#7f8c8d"
SECTION_COLORS = {"ذكر": "#0984e3", "أنثى": "#c2185b"}


class RegisterMemberWindow(tk.Toplevel):
    def __init__(self, parent, dev, gender):
        super().__init__(parent)
        self.dev = dev
        self.gender = gender                  # قسم الجلسة (ذكر / أنثى): ما بيتغير بالتسجيل
        self.busy = False

        self.title("تسجيل لاعب جديد")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=16)
        self.resizable(False, False)
        C.center_on(self, parent, 700, 740)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.name_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.total_var = tk.StringVar(value="—")
        # لكل نوع اشتراك: تفعيل + مدة + سعر + مدفوع + متبقي
        self.rows = {t: {"on": tk.BooleanVar(value=False), "days": tk.StringVar(value="30"),
                         "price": tk.StringVar(), "paid": tk.StringVar(),
                         "rest": tk.StringVar(value="—"), "widgets": []}
                     for t in db.SUB_TYPES}

        self._build()
        for row in self.rows.values():
            for key in ("price", "paid"):
                row[key].trace_add("write", self._update_remaining)
        self.name_entry.focus_set()
        self.bind("<Escape>", lambda e: self._on_close())

    # ------------------------------------------------------------ بناء الواجهة
    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, text="تسجيل لاعب جديد", font=C.font(20, True), bg=bg, fg=text
                 ).pack(pady=(0, 10))

        # الأزرار والملاحظات أول (تحت) عشان ما ينقصوا بالشاشات الصغيرة
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x", pady=(6, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        self.btn_save = tk.Button(btns, text="حفظ وتسجيل البصمة", command=self._save,
                                  font=C.font(12, True), bg=C.COLORS["save"], fg="white",
                                  relief="flat", cursor="hand2", height=2)
        self.btn_save.grid(row=0, column=1, sticky="ew", padx=5)
        self.btn_cancel = tk.Button(btns, text="إلغاء", command=self._on_close,
                                    font=C.font(12, True), bg=C.COLORS["cancel"], fg="white",
                                    relief="flat", cursor="hand2", height=2)
        self.btn_cancel.grid(row=0, column=0, sticky="ew", padx=5)
        self.lbl_state = tk.Label(self, text="", font=C.font(12, True), bg=bg, fg="#fbc531",
                                  wraplength=620, justify="center")
        self.lbl_state.pack(side="bottom", pady=(8, 0), fill="x")

        # --- بيانات اللاعب
        form = tk.Frame(self, bg=bg)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)

        def row(r, label, widget):
            tk.Label(form, text=label, font=C.font(13), bg=bg, fg=text, anchor="e"
                     ).grid(row=r, column=1, sticky="e", padx=(10, 0), pady=6)
            widget.grid(row=r, column=0, sticky="ew", pady=6)
            return widget

        def entry(var):
            return tk.Entry(form, textvariable=var, font=C.font(14), justify="right",
                            relief="flat", bg="white")

        def section_label(p):
            return tk.Label(p, text=f"قسم {db.SECTION_NAMES[self.gender]}", font=C.font(14, True),
                            bg=SECTION_COLORS[self.gender], fg="white", pady=3)

        self.name_entry = row(0, "الاسم", entry(self.name_var))
        row(1, "القسم", section_label(form))
        row(2, "رقم الهاتف", entry(self.phone_var))

        # --- جدول الاشتراكات (عمود النوع عالأيمن)
        tk.Label(self, text="الاشتراكات (فعّل نوع أو أكتر، ولكل نوع مدته وسعره)",
                 font=C.font(13, True), bg=bg, fg=text).pack(anchor="e", pady=(12, 4))
        table = tk.Frame(self, bg=C.COLORS["panel"], padx=10, pady=8)
        table.pack(fill="x")
        headers = ["النوع", "المدة (أيام)", "السعر", "المدفوع", "المتبقي"]
        for i, h in enumerate(headers):
            tk.Label(table, text=h, font=C.font(11, True), bg=C.COLORS["panel"],
                     fg=C.COLORS["muted"]).grid(row=0, column=4 - i, padx=6, pady=(0, 4))
        for r, sub_type in enumerate(db.SUB_TYPES, start=1):
            self._build_type_row(table, r, sub_type)

        tk.Label(self, text="إجمالي المتبقي", font=C.font(13, True), bg=bg, fg=text
                 ).pack(anchor="e", pady=(10, 0))
        tk.Label(self, textvariable=self.total_var, font=C.font(18, True), bg=bg, fg="#fbc531"
                 ).pack(anchor="e")

    def _build_type_row(self, table, r, sub_type):
        panel = C.COLORS["panel"]
        row = self.rows[sub_type]
        check = tk.Checkbutton(table, text=sub_type, variable=row["on"], font=C.font(13, True),
                               bg=panel, fg=C.COLORS["text"], selectcolor=C.COLORS["bg"],
                               activebackground=panel, activeforeground=C.COLORS["text"],
                               cursor="hand2", anchor="e", width=9,
                               command=lambda t=sub_type: self._toggle(t))
        check.grid(row=r, column=4, padx=6, pady=5, sticky="e")
        days = ttk.Combobox(table, textvariable=row["days"], values=DURATIONS, width=7,
                            font=C.font(12), justify="center")
        price = tk.Entry(table, textvariable=row["price"], font=C.font(13), justify="center",
                         relief="flat", width=9)
        paid = tk.Entry(table, textvariable=row["paid"], font=C.font(13), justify="center",
                        relief="flat", width=9)
        for col, w in ((3, days), (2, price), (1, paid)):
            w.grid(row=r, column=col, padx=6, pady=5)
        tk.Label(table, textvariable=row["rest"], font=C.font(13, True), bg=panel, fg="#fbc531",
                 width=8).grid(row=r, column=0, padx=6, pady=5)
        row["widgets"] = [days, price, paid]
        self._set_row_enabled(sub_type, False)

    # ------------------------------------------------------------ منطق
    def _set_row_enabled(self, sub_type, enabled):
        days, price, paid = self.rows[sub_type]["widgets"]
        days.config(state="normal" if enabled else "disabled")
        for w in (price, paid):
            w.config(state="normal" if enabled else "disabled", disabledbackground=DISABLED_BG,
                     bg="white")

    def _toggle(self, sub_type):
        on = self.rows[sub_type]["on"].get()
        self._set_row_enabled(sub_type, on)
        if on:
            self.rows[sub_type]["widgets"][1].focus_set()       # بيروح عالسعر
        self._update_remaining()

    def _update_remaining(self, *_):
        total, valid, any_on = 0.0, True, False
        for sub_type, row in self.rows.items():
            if not row["on"].get():
                row["rest"].set("—")
                continue
            any_on = True
            try:
                price = C.parse_number(row["price"].get(), "السعر")
                paid = C.parse_number(row["paid"].get() or "0", "المدفوع")
                row["rest"].set(C.fmt_money(price - paid))
                total += price - paid
            except ValueError:
                row["rest"].set("—")
                valid = False
        self.total_var.set(C.fmt_money(total) if any_on and valid else "—")

    def _collect(self):
        name = self.name_var.get().strip()
        if not name:
            raise ValueError("اكتب اسم اللاعب")
        subs = []
        for sub_type, row in self.rows.items():
            if not row["on"].get():
                continue
            try:
                days = C.parse_number(row["days"].get(), "المدة", integer=True, minimum=1)
                price = C.parse_number(row["price"].get(), "السعر")
                paid = C.parse_number(row["paid"].get() or "0", "المدفوع")
                if paid > price:
                    raise ValueError("المدفوع أكبر من السعر")
            except ValueError as e:
                raise ValueError(f"{sub_type}: {e}") from None
            subs.append({"sub_type": sub_type, "days": days, "price": price, "paid": paid})
        if not subs:
            raise ValueError("اختر نوع اشتراك واحد على الأقل")
        return dict(name=name, gender=self.gender, phone=self.phone_var.get().strip(),
                    subscriptions=subs)

    def _set_busy(self, busy, message=""):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_save.config(state=state)
        self.btn_cancel.config(state=state)
        self.lbl_state.config(text=message)

    def _save(self):
        if self.busy:
            return
        try:
            data = self._collect()
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return

        self._set_busy(True, "حط إصبعك على جهاز البصمة 3 مرات حسب تعليمات شاشة الجهاز...")

        def work():
            taken = {uid for uid, _ in self.dev.device_users()}    # أرقام الجهاز (أدمن وغيره)
            uid = db.peek_next_device_uid(taken)
            self.dev.register_user_with_fingerprint(uid)          # بصمة أولاً
            try:
                return db.add_member(device_uid=uid, **data)      # وبعدها الحفظ
            except Exception:
                try:
                    self.dev.delete_user(uid)                      # ما نخلي مستخدم عالق
                except DeviceError:
                    pass
                raise

        C.run_in_thread(self, work, lambda res, err: self._done(data["name"], res, err))

    def _done(self, name, result, error):
        if not self.winfo_exists():
            return
        self._set_busy(False)
        if error is not None:
            messagebox.showerror("ما تم التسجيل", str(error), parent=self)
            return
        messagebox.showinfo("تم", f"تم تسجيل «{name}» بنجاح\nرقمه على الجهاز: {result['device_uid']}",
                            parent=self)
        self.destroy()

    def _on_close(self):
        if self.busy:
            return          # ما بنسكر النافذة أثناء تسجيل البصمة
        self.destroy()
