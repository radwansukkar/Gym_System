"""gui/members_list.py - قائمة اللاعبين لقسم الجلسة (شباب أو نساء) + تفاصيل اللاعب وتعديله"""
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

import db
from gui import access
from gui import common as C

FILTERS = ("الكل", "ساري", "قرب الانتهاء", "منتهي", "عليه دفع")

COLUMNS = [
    ("name", "الاسم", 190, "e"),
    ("phone", "الهاتف", 100, "center"),
    ("type", "النوع", 130, "center"),
    ("days", "المتبقي", 180, "center"),
    ("state", "الحالة", 95, "center"),
    ("due", "عليه دفع", 75, "center"),
]

HISTORY_COLUMNS = [
    ("start", "من", 100, "center"),
    ("last", "آخر يوم", 100, "center"),
    ("days", "المدة", 70, "center"),
    ("type", "النوع", 90, "center"),
    ("price", "السعر", 80, "center"),
    ("paid", "المدفوع", 80, "center"),
    ("rest", "المتبقي", 80, "center"),
]


class MembersListWindow(access.GatedWindow):
    def __init__(self, parent, gender):
        super().__init__(parent, gender)
        self.title(f"قائمة اللاعبين - {access.SECTION[gender]}")
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 900, 680)
        self.transient(parent)

        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value=FILTERS[0])
        self.count_var = tk.StringVar()
        self._details = None

        self._build()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.filter_var.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self.search_entry.focus_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, text=f"قائمة اللاعبين — قسم {access.SECTION[self.gender]}",
                 font=C.font(18, True), bg=access.SECTION_COLOR[self.gender], fg="white",
                 pady=8).pack(fill="x", pady=(0, 10))

        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text="بحث", font=C.font(13), bg=bg, fg=text).pack(side="right")
        self.search_entry = tk.Entry(top, textvariable=self.search_var, font=C.font(14),
                                     justify="right", relief="flat", bg="white")
        self.search_entry.pack(side="right", fill="x", expand=True, padx=10)
        ttk.Combobox(top, textvariable=self.filter_var, values=FILTERS, state="readonly",
                     font=C.font(12), justify="right", width=14).pack(side="left")
        tk.Label(top, text="عرض", font=C.font(13), bg=bg, fg=text).pack(side="left", padx=(0, 6))

        # الأزرار والعدّاد أول (تحت) عشان ما ينقصوا بالشاشات الصغيرة، والجدول بياخد الباقي
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x")
        tk.Label(self, textvariable=self.count_var, font=C.font(12, True), bg=bg,
                 fg=C.COLORS["muted"]).pack(side="bottom", anchor="e", pady=(0, 8))

        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree, scroll = C.make_tree(frame, COLUMNS, height=8)
        scroll.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._open_details())
        self.tree.bind("<Return>", lambda e: self._open_details())

        btns.columnconfigure((0, 1, 2), weight=1, uniform="b")
        tk.Button(btns, text="تفاصيل اللاعب", command=self._open_details, font=C.font(13, True),
                  bg=C.COLORS["btn"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=2, sticky="ew", padx=5)
        tk.Button(btns, text="تغيير كلمة سر القسم",
                  command=lambda: access.change_password(self, self.gender),
                  font=C.font(13, True), bg=C.COLORS["panel"], fg="white", relief="flat",
                  cursor="hand2", height=2).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إغلاق", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=0, sticky="ew", padx=5)

    # ------------------------------------------------------------ البيانات
    def refresh(self):
        members = db.search_members(self.search_var.get(), gender=self.gender)
        counts = {"ok": 0, "warn": 0, "bad": 0}
        for m in members:
            counts[C.sub_state(m)[0]] += 1
        owing = sum(1 for m in members if m["remaining"] > 0)
        self.count_var.set(f"العدد: {len(members)}   |   ساري: {counts['ok']}   |   "
                           f"قرب الانتهاء: {counts['warn']}   |   منتهي: {counts['bad']}   |   "
                           f"عليهم دفع: {owing}")

        want = self.filter_var.get()
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for m in members:
            tag, state = C.sub_state(m)
            if (want == "ساري" and tag != "ok") or (want == "قرب الانتهاء" and tag != "warn") \
                    or (want == "منتهي" and tag != "bad") \
                    or (want == "عليه دفع" and m["remaining"] <= 0):
                continue
            due = C.fmt_money(m["remaining"]) if m["remaining"] > 0 else ""
            self.tree.insert("", "end", iid=str(m["id"]), tags=(tag,),
                             values=(m["name"], m["phone"] or "", C.types_text(m), C.days_text(m),
                                     state, due))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])

    def _open_details(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("تنبيه", "اختر لاعب من القائمة أولاً", parent=self)
            return
        if self._details is not None and self._details.winfo_exists():
            self._details.destroy()
        self._details = MemberDetails(self, int(sel[0]), on_change=self.refresh)


class MemberDetails(tk.Toplevel):
    """تفاصيل لاعب: بياناته، سجل اشتراكاته ودفعاته، وتسديد جزء من المتبقي."""

    def __init__(self, parent, member_id, on_change=None):
        super().__init__(parent)
        self.member_id = member_id
        self.on_change = on_change
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 780, 730)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        self.title_var = tk.StringVar()
        self.info_var = tk.StringVar()
        self.subs_var = tk.StringVar()
        self.rest_var = tk.StringVar()
        self.pay_var = tk.StringVar()
        self._build()
        self.reload()

    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, textvariable=self.title_var, font=C.font(22, True), bg=bg, fg=text
                 ).pack(anchor="e")
        tk.Label(self, textvariable=self.info_var, font=C.font(13), bg=bg, fg=C.COLORS["muted"],
                 justify="right").pack(anchor="e", pady=(2, 4))
        tk.Label(self, textvariable=self.subs_var, font=C.font(13, True), bg=bg, fg=text,
                 justify="right").pack(anchor="e", pady=(0, 6))
        self.lbl_rest = tk.Label(self, textvariable=self.rest_var, font=C.font(15, True), bg=bg,
                                 fg="#fbc531")
        self.lbl_rest.pack(anchor="e", pady=(0, 8))

        tk.Button(self, text="إغلاق", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).pack(side="bottom", fill="x", pady=(8, 0))
        edit_row = tk.Frame(self, bg=bg)
        edit_row.pack(side="bottom", fill="x", pady=(8, 0))
        edit_row.columnconfigure((0, 1), weight=1, uniform="e")
        tk.Button(edit_row, text="تعديل البيانات", command=self._edit_member, font=C.font(12, True),
                  bg=C.COLORS["btn"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(edit_row, text="تعديل مدة اشتراك (اختر من السجل)", command=self._edit_duration,
                  font=C.font(12, True), bg=C.COLORS["btn"], fg="white", relief="flat",
                  cursor="hand2", height=2).grid(row=0, column=0, sticky="ew", padx=4)
        self.pay_frame = tk.Frame(self, bg=bg)
        self.pay_frame.pack(side="bottom", fill="x", pady=(8, 4))

        tk.Label(self, text="سجل الاشتراكات", font=C.font(13, True), bg=bg, fg=text
                 ).pack(anchor="e")
        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=6)
        self.tree, scroll = C.make_tree(frame, HISTORY_COLUMNS, height=6)
        scroll.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)

        tk.Label(self.pay_frame, text="تسديد دفعة", font=C.font(13), bg=bg, fg=text).pack(side="right")
        tk.Entry(self.pay_frame, textvariable=self.pay_var, font=C.font(14), justify="right",
                 relief="flat", bg="white", width=12).pack(side="right", padx=10)
        tk.Button(self.pay_frame, text="تسديد", command=self._pay, font=C.font(12, True),
                  bg=C.COLORS["save"], fg="white", relief="flat", cursor="hand2", padx=18
                  ).pack(side="right")

    def reload(self):
        m = db.get_member(self.member_id)
        tag, state = C.sub_state(m)
        self.title_var.set(m["name"])
        self.info_var.set(f"الهاتف: {m['phone'] or '—'}   |   الحالة: {state}   |   "
                          f"رقم الجهاز: {m['device_uid']}")
        self.subs_var.set("\n".join(
            f"{x['sub_type']}: " + (f"باقي {x['days_left']} يوم (آخر يوم {x['last_day']})"
                                   if x["active"] else f"منتهي (انتهى {x['last_day']})")
            for x in m["subs"]))
        if m["remaining"] > 0:
            self.rest_var.set(f"المتبقي عليه دفع: {C.fmt_money(m['remaining'])}")
            self.lbl_rest.config(fg="#fbc531")
        else:
            self.rest_var.set("لا يوجد متبقي ✔")
            self.lbl_rest.config(fg="#7bed9f")
        # خانة التسديد بس إذا في متبقي
        for child in self.pay_frame.winfo_children():
            child.config(state="normal" if m["remaining"] > 0 else "disabled") \
                if isinstance(child, (tk.Entry, tk.Button)) else None

        self.tree.delete(*self.tree.get_children())
        for h in db.member_history(self.member_id):
            last_day = (date.fromisoformat(h["end_date"]) - timedelta(days=1)).isoformat()
            self.tree.insert("", "end", iid=str(h["id"]), tags=("bad" if h["remaining"] > 0 else "ok",),
                             values=(h["start_date"], last_day, h["days"], h["sub_type"],
                                     C.fmt_money(h["price"]), C.fmt_money(h["paid"]),
                                     C.fmt_money(h["remaining"])))

    def _changed(self):
        self.reload()
        if self.on_change:
            self.on_change()

    def _edit_member(self):
        EditMemberDialog(self, db.get_member(self.member_id), on_saved=self._changed)

    def _edit_duration(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("تنبيه", "اختر الاشتراك اللي بدك تعدّل مدته من سجل الاشتراكات أولاً",
                                parent=self)
            return
        sub_id = int(sel[0])
        m = db.get_member(self.member_id)
        if sub_id not in {s["sub_id"] for s in m["subs"]}:
            messagebox.showwarning("تنبيه", "تقدر تعدّل مدة آخر اشتراك من كل نوع بس "
                                            "(الاشتراكات الأقدم بتضل للسجل)", parent=self)
            return
        sub = next(h for h in db.member_history(self.member_id) if h["id"] == sub_id)
        EditDurationDialog(self, sub, on_saved=self._changed)

    def _pay(self):
        try:
            amount = C.parse_number(self.pay_var.get(), "المبلغ", minimum=0)
            if amount <= 0:
                raise ValueError("اكتب مبلغ أكبر من صفر")
            db.pay_remaining(self.member_id, amount)
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        self.pay_var.set("")
        self.reload()
        if self.on_change:
            self.on_change()
        messagebox.showinfo("تم", "تم تسجيل الدفعة", parent=self)


class EditMemberDialog(tk.Toplevel):
    """تعديل اسم اللاعب ورقم هاتفه. (القسم ثابت.)"""

    def __init__(self, parent, member, on_saved=None):
        super().__init__(parent)
        self.member_id = member["id"]
        self.on_saved = on_saved
        self.title("تعديل بيانات اللاعب")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=18)
        self.resizable(False, False)
        C.center_on(self, parent, 500, 300)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._save())

        self.name_var = tk.StringVar(value=member["name"])
        self.phone_var = tk.StringVar(value=member["phone"] or "")
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        form = tk.Frame(self, bg=bg)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        for r, (label, var) in enumerate((("الاسم", self.name_var), ("رقم الهاتف", self.phone_var))):
            tk.Label(form, text=label, font=C.font(13), bg=bg, fg=text, anchor="e"
                     ).grid(row=r, column=1, sticky="e", padx=(10, 0), pady=8)
            entry = tk.Entry(form, textvariable=var, font=C.font(14), justify="right",
                             relief="flat", bg="white")
            entry.grid(row=r, column=0, sticky="ew", pady=8)
            if r == 0:
                entry.focus_set()
        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", pady=(16, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="حفظ", command=self._save, font=C.font(13, True), bg=C.COLORS["save"],
                  fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إلغاء", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=0, sticky="ew", padx=5)

    def _save(self):
        try:
            db.update_member(self.member_id, self.name_var.get(), self.phone_var.get())
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class EditDurationDialog(tk.Toplevel):
    """
    تعديل مدة اشتراك (آخر اشتراك من نوعه). آخر يوم = تاريخ البداية + المدة الجديدة.
    بنعرض النتيجة قبل الحفظ.
    """

    def __init__(self, parent, sub, on_saved=None):
        super().__init__(parent)
        self.sub = sub
        self.on_saved = on_saved
        self.title("تعديل مدة الاشتراك")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=18)
        self.resizable(False, False)
        C.center_on(self, parent, 540, 440)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._save())

        self.days_var = tk.StringVar(value=str(sub["days"]))
        self.preview_var = tk.StringVar()
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        start = date.fromisoformat(sub["start_date"])
        current_last = (date.fromisoformat(sub["end_date"]) - timedelta(days=1)).isoformat()
        tk.Label(self, text=f"اشتراك {sub['sub_type']}", font=C.font(18, True), bg=bg, fg=text
                 ).pack(anchor="e")
        tk.Label(self, text=f"يبدأ: {start.isoformat()}   |   المدة الحالية: {sub['days']} يوم   |   "
                            f"آخر يوم: {current_last}", font=C.font(12), bg=bg,
                 fg=C.COLORS["muted"], justify="right", wraplength=480).pack(anchor="e", pady=(4, 14))
        row = tk.Frame(self, bg=bg)
        row.pack(fill="x")
        tk.Label(row, text="المدة الجديدة (بالأيام)", font=C.font(13), bg=bg, fg=text).pack(side="right")
        self.entry = tk.Entry(row, textvariable=self.days_var, font=C.font(16), justify="center",
                              relief="flat", bg="white", width=10)
        self.entry.pack(side="right", padx=12)
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        tk.Label(self, textvariable=self.preview_var, font=C.font(14, True), bg=bg, fg="#fbc531",
                 wraplength=480, justify="right").pack(anchor="e", pady=14)
        tk.Label(self, text="الدفع والسعر ما بيتغيروا. لتغيير المبلغ سجّل دفعة أو تجديد.",
                 font=C.font(11), bg=bg, fg=C.COLORS["muted"], wraplength=480,
                 justify="right").pack(anchor="e")
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x", pady=(16, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="حفظ", command=self._save, font=C.font(13, True), bg=C.COLORS["save"],
                  fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إلغاء", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=0, sticky="ew", padx=5)
        self.days_var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _update_preview(self):
        try:
            days = C.parse_number(self.days_var.get(), "المدة", integer=True, minimum=1)
        except ValueError:
            self.preview_var.set("—")
            return
        end = date.fromisoformat(self.sub["start_date"]) + timedelta(days=days)
        left = (end - date.today()).days
        status = f"باقي {left} يوم" if left > 0 else "الاشتراك بيصير منتهي"
        self.preview_var.set(f"بعد التعديل: آخر يوم {(end - timedelta(days=1)).isoformat()}  |  {status}")

    def _save(self):
        try:
            days = C.parse_number(self.days_var.get(), "المدة", integer=True, minimum=1)
            db.update_subscription_days(self.sub["id"], days)
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
