"""gui/renew.py - تجديد اشتراك لاعب (محمي بكلمة سر القسم)"""
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

import db
from gui import access
from gui import common as C

QUICK_DAYS = [("شهر (30)", 30), ("3 أشهر (90)", 90), ("6 أشهر (180)", 180), ("سنة (365)", 365)]

COLUMNS = [
    ("name", "الاسم", 170, "e"),
    ("phone", "الهاتف", 90, "center"),
    ("type", "النوع", 125, "center"),
    ("days", "المتبقي", 175, "center"),
    ("state", "الحالة", 95, "center"),
    ("due", "عليه دفع", 70, "center"),
]


class RenewWindow(access.GatedWindow):
    def __init__(self, parent, gender):
        super().__init__(parent, gender)
        self.title(f"تجديد اشتراك - {access.SECTION[gender]}")
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 880, 740)
        self.transient(parent)

        self.selected = None
        self.search_var = tk.StringVar()
        self.type_var = tk.StringVar(value=db.SUB_TYPES[0])
        self.days_var = tk.StringVar(value="30")
        self.price_var = tk.StringVar()
        self.paid_var = tk.StringVar()
        self.old_var = tk.StringVar()
        self.after_var = tk.StringVar(value="—")
        self.info_var = tk.StringVar(value="اختر لاعب من القائمة")
        self.mode_var = tk.StringVar()          # تجديد ولا نوع جديد

        self._build()
        self.search_var.trace_add("write", lambda *_: self._refresh_list())
        self.type_var.trace_add("write", lambda *_: self._update_mode())
        self.price_var.trace_add("write", self._update_after)
        self.paid_var.trace_add("write", self._update_after)
        self._refresh_list()
        self.search_entry.focus_set()
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------ بناء الواجهة
    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, text=f"تجديد اشتراك — قسم {access.SECTION[self.gender]}",
                 font=C.font(18, True), bg=access.SECTION_COLOR[self.gender], fg="white",
                 pady=8).pack(fill="x", pady=(0, 10))

        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text="بحث بالاسم أو الرقم", font=C.font(13), bg=bg, fg=text).pack(side="right")
        self.search_entry = tk.Entry(top, textvariable=self.search_var, font=C.font(14),
                                     justify="right", relief="flat", bg="white")
        self.search_entry.pack(side="right", fill="x", expand=True, padx=10)

        # ترتيب الـ pack مهم: الأزرار أول (تحت)، بعدين الفورم، بعدين المعلومات، والجدول آخر شي
        # بياخد المساحة المتبقية. هيك الأزرار ما بتنقص حتى لو الشاشة صغيرة.
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x", pady=(12, 0))

        form = tk.Frame(self, bg=bg)
        form.pack(side="bottom", fill="x")
        form.columnconfigure(0, weight=1)

        tk.Label(self, textvariable=self.info_var, font=C.font(13, True), bg=C.COLORS["panel"],
                 fg="#fbc531", pady=8, wraplength=820).pack(side="bottom", fill="x", pady=(2, 8))

        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree, scroll = C.make_tree(frame, COLUMNS, height=4)
        scroll.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        def row(r, label, widget):
            tk.Label(form, text=label, font=C.font(13), bg=bg, fg=text, anchor="e"
                     ).grid(row=r, column=1, sticky="e", padx=(10, 0), pady=5)
            widget.grid(row=r, column=0, sticky="ew", pady=5)
            return widget

        def entry(var):
            return tk.Entry(form, textvariable=var, font=C.font(14), justify="right",
                            relief="flat", bg="white")

        type_box = tk.Frame(form, bg=bg)
        ttk.Combobox(type_box, textvariable=self.type_var, values=db.SUB_TYPES, state="readonly",
                     font=C.font(14), justify="right", width=12).pack(side="right")
        tk.Label(type_box, textvariable=self.mode_var, font=C.font(12, True), bg=bg,
                 fg="#fbc531").pack(side="right", padx=12)
        row(0, "نوع الاشتراك", type_box)
        row(1, "المدة (بالأيام)", entry(self.days_var))
        quick = tk.Frame(form, bg=bg)
        quick.grid(row=2, column=0, columnspan=2, sticky="e")
        for label, days in reversed(QUICK_DAYS):
            tk.Button(quick, text=label, font=C.font(10), relief="flat", bg=C.COLORS["panel"],
                      fg="white", cursor="hand2",
                      command=lambda d=days: self.days_var.set(str(d))).pack(side="right", padx=3)
        row(3, "سعر التجديد", entry(self.price_var))
        row(4, "المدفوع الآن", entry(self.paid_var))
        tk.Label(form, text="المتبقي بعد التجديد", font=C.font(13, True), bg=bg, fg=text
                 ).grid(row=5, column=1, sticky="e", padx=(10, 0), pady=5)
        tk.Label(form, textvariable=self.after_var, font=C.font(15, True), bg=bg, fg="#fbc531",
                 anchor="e").grid(row=5, column=0, sticky="ew")
        self.lbl_old = tk.Label(form, text="دفعة على المتبقي القديم", font=C.font(13), bg=bg, fg=text)
        self.lbl_old.grid(row=6, column=1, sticky="e", padx=(10, 0), pady=5)
        self.old_entry = entry(self.old_var)
        self.old_entry.grid(row=6, column=0, sticky="ew", pady=5)

        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="تجديد الاشتراك", command=self._renew, font=C.font(14, True),
                  bg=C.COLORS["save"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إغلاق", command=self.destroy, font=C.font(14, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=0, sticky="ew", padx=5)
        self._set_old_enabled(False)

    # ------------------------------------------------------------ قائمة اللاعبين
    def _refresh_list(self):
        members = db.search_members(self.search_var.get(), gender=self.gender)
        keep = str(self.selected["id"]) if self.selected else None
        self.tree.delete(*self.tree.get_children())
        for m in members:
            tag, state = C.sub_state(m)
            due = C.fmt_money(m["remaining"]) if m["remaining"] > 0 else ""
            self.tree.insert("", "end", iid=str(m["id"]), tags=(tag,),
                             values=(m["name"], m["phone"] or "", C.types_text(m), C.days_text(m),
                                     state, due))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        m = db.get_member(int(sel[0]))
        self.selected = m
        parts = [f"{x['sub_type']}: " + (f"باقي {x['days_left']} يوم" if x["active"] else "منتهي")
                 for x in m["subs"]]
        info = f"{m['name']}  |  " + "  ·  ".join(parts)
        if m["remaining"] > 0:
            info += f"  |  متبقي عليه دفع: {C.fmt_money(m['remaining'])}"
        self.info_var.set(info)
        # بنقترح النوع الأقرب للانتهاء (أو المنتهي) للتجديد، وبتقدر تختار نوع ثاني (جديد) لتضيفه
        soonest = min(m["subs"], key=lambda x: x["days_left"])
        if soonest["sub_type"] in db.SUB_TYPES:
            self.type_var.set(soonest["sub_type"])
        self._update_mode()
        self.old_var.set("")
        self._set_old_enabled(m["remaining"] > 0)
        self.lbl_old.config(text=f"دفعة على المتبقي القديم ({C.fmt_money(m['remaining'])})"
                            if m["remaining"] > 0 else "دفعة على المتبقي القديم")

    def _update_mode(self):
        """بيوضح إذا العملية تجديد لنوع عنده، أو إضافة نوع جديد للاعب."""
        if not self.selected:
            self.mode_var.set("")
            return
        sub = next((x for x in self.selected["subs"] if x["sub_type"] == self.type_var.get()), None)
        if sub is None:
            self.mode_var.set("نوع جديد للاعب")
        elif sub["active"]:
            self.mode_var.set(f"تجديد (باقي {sub['days_left']} يوم، بيكمل بعده)")
        else:
            self.mode_var.set("تجديد (منتهي، بيبدأ من اليوم)")

    def _set_old_enabled(self, enabled):
        self.old_entry.config(state="normal" if enabled else "disabled")

    def _update_after(self, *_):
        try:
            price = C.parse_number(self.price_var.get(), "السعر")
            paid = C.parse_number(self.paid_var.get() or "0", "المدفوع")
            self.after_var.set(C.fmt_money(price - paid))
        except ValueError:
            self.after_var.set("—")

    # ------------------------------------------------------------ التجديد
    def _renew(self):
        if not self.selected:
            messagebox.showwarning("تنبيه", "اختر لاعب من القائمة أولاً", parent=self)
            return
        m = self.selected
        try:
            days = C.parse_number(self.days_var.get(), "المدة", integer=True, minimum=1)
            price = C.parse_number(self.price_var.get(), "سعر التجديد")
            paid = C.parse_number(self.paid_var.get() or "0", "المدفوع")
            pay_old = C.parse_number(self.old_var.get() or "0", "الدفعة على المتبقي القديم")
            if paid > price:
                raise ValueError("المدفوع أكبر من سعر التجديد")
            if pay_old > m["remaining"] + 1e-9:
                raise ValueError("الدفعة أكبر من المتبقي القديم على اللاعب")
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        try:
            res = db.renew_subscription(m["id"], days, price, paid, sub_type=self.type_var.get(),
                                        pay_old=pay_old)
        except ValueError as e:
            messagebox.showerror("ما تم التجديد", str(e), parent=self)
            return

        last_day = date.fromisoformat(res["end_date"]) - timedelta(days=1)
        action = "تم تجديد" if res["is_renewal"] else "تمت إضافة"
        messagebox.showinfo("تم", f"{action} اشتراك «{res['sub_type']}» للاعب «{m['name']}»\n"
                                  f"من {res['start_date']} لحد {last_day.isoformat()}", parent=self)
        self.selected = None
        self._update_mode()
        self.info_var.set("اختر لاعب من القائمة")
        for var in (self.price_var, self.paid_var, self.old_var):
            var.set("")
        self.days_var.set("30")
        self._set_old_enabled(False)
        self._refresh_list()
