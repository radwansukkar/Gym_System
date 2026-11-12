"""gui/main_window.py - الشاشة الرئيسية: عرض البصمات + الأزرار الأربعة"""
import logging
import queue
import tkinter as tk
from tkinter import messagebox

import db
from gui import access
from gui import common as C
from gui.members_list import MembersListWindow
from gui.register_member import RegisterMemberWindow
from gui.renew import RenewWindow
from gui.report_window import ReportWindow
from gui.staff import StaffMenuWindow

IDLE_RESET_MS = 8000       # بعد كم ميلي ثانية الشاشة بترجع لوضع الانتظار


def days_phrase(n):
    if n == 1:
        return "باقي يوم واحد"
    if n == 2:
        return "باقي يومان"
    if 3 <= n <= 10:
        return f"باقي {n} أيام"
    return f"باقي {n} يوم"


class MainWindow:
    """
    الشاشة الرئيسية لقسم واحد (gender = "ذكر" / "أنثى") بعد تسجيل الدخول بكلمة سر القسم.
    كل الشاشات (تسجيل، تجديد، قائمة، تقرير) بتشتغل على هالقسم بس. "تبديل القسم" بيرجع لشاشة الدخول.
    """

    def __init__(self, root, dev, gender):
        self.root = root
        self.dev = dev
        self.gender = gender
        self._reset_timer = None
        self._register_win = None
        self._staff_win = None
        self._report_win = None
        self._wins = {}              # النوع (renew / members) -> النافذة
        self._fullscreen = False

        C.setup_styles(root)
        access.install_activity_tracking(root)
        root.title("نظام إدارة الجيم")
        root.geometry("1000x700")
        root.minsize(820, 600)
        root.configure(bg=C.COLORS["bg"])
        root.bind("<F11>", self._toggle_fullscreen)
        root.bind("<Escape>", lambda e: self._set_fullscreen(False))

        self._build_topbar()
        self._build_card()
        self._build_buttons()

        self._set_status(None, "جاري الاتصال...")
        self._apply_session()
        self._show_idle()
        root.after(200, self._poll_events)

    # ---------------------------------------------------------------- بناء الواجهة
    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C.COLORS["panel"])
        bar.pack(fill="x")
        # حالة الجهاز أول (عالشمال) عشان تضل ظاهرة حتى لو الشاشة ضيقة
        self.lbl_status = tk.Label(bar, text="", font=C.font(12, True),
                                   bg=C.COLORS["panel"], fg=C.COLORS["muted"])
        self.lbl_status.pack(side="left", padx=14)
        tk.Label(bar, text="نظام إدارة الجيم", font=C.font(18, True),
                 bg=C.COLORS["panel"], fg=C.COLORS["text"]).pack(side="right", padx=14, pady=12)
        self.lbl_section = tk.Label(bar, text="", font=C.font(13, True), fg="white", padx=12, pady=4)
        self.lbl_section.pack(side="right", padx=4)
        tk.Button(bar, text="تبديل القسم", command=self._switch_section, font=C.font(11, True),
                  bg=C.COLORS["cancel"], fg="white", activebackground="#4b5457",
                  activeforeground="white", relief="flat", cursor="hand2", padx=10, pady=4
                  ).pack(side="right", padx=4)
        tk.Button(bar, text="التقرير اليومي", command=self._open_report, font=C.font(11, True),
                  bg="#128c7e", fg="white", activebackground="#0b6b5f", activeforeground="white",
                  relief="flat", cursor="hand2", padx=10, pady=4).pack(side="right", padx=4)

    def _build_card(self):
        self.card = tk.Frame(self.root, bg=C.COLORS["idle"])
        self.card.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        inner = tk.Frame(self.card, bg=C.COLORS["idle"])
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self._card_widgets = [self.card, inner]

        def label(size, bold=False, pady=4):
            lbl = tk.Label(inner, text="", font=C.font(size, bold), fg="white",
                           bg=C.COLORS["idle"], wraplength=880, justify="center")
            lbl.pack(pady=pady)
            self._card_widgets.append(lbl)
            return lbl

        self.lbl_title = label(24, True)
        self.lbl_name = label(54, True, pady=10)
        self.lbl_big = label(40, True)
        self.lbl_info = label(22)
        self.lbl_extra = label(22, True, pady=10)

    def _build_buttons(self):
        row = tk.Frame(self.root, bg=C.COLORS["bg"])
        row.pack(fill="x", padx=20, pady=(0, 20))
        buttons = [
            ("تسجيل لاعب جديد", self._open_register),
            ("تجديد اشتراك", lambda: self._open_section_window("renew", RenewWindow)),
            ("قائمة اللاعبين", lambda: self._open_section_window("members", MembersListWindow)),
            ("قائمة الموظفين", self._open_staff),
        ]
        for i in range(4):
            row.columnconfigure(i, weight=1, uniform="btn")
        # RTL: أول زر عالأيمن
        for i, (text, cmd) in enumerate(buttons):
            tk.Button(row, text=text, command=cmd, font=C.font(14, True),
                      bg=C.COLORS["btn"], fg="white", activebackground=C.COLORS["btn_active"],
                      activeforeground="white", relief="flat", cursor="hand2", height=2,
                      ).grid(row=0, column=3 - i, sticky="ew", padx=4)

    # ---------------------------------------------------------------- عرض البطاقة
    def _show(self, color, title="", name="", big="", info="", extra="", big_size=40):
        for w in self._card_widgets:
            w.configure(bg=color)
        self.lbl_title.config(text=title)
        self.lbl_name.config(text=name)
        self.lbl_big.config(text=big, font=C.font(big_size, True))
        self.lbl_info.config(text=info)
        self.lbl_extra.config(text=extra)

    def _show_idle(self):
        self._show(C.COLORS["idle"], title="بانتظار البصمة", info="ضع إصبعك على جهاز البصمة")

    def _schedule_idle(self):
        if self._reset_timer:
            self.root.after_cancel(self._reset_timer)
        self._reset_timer = self.root.after(IDLE_RESET_MS, self._show_idle)

    def _set_status(self, connected, message):
        if connected is None:
            color, dot = C.COLORS["warn"], "●"
        elif connected:
            color, dot = "#44bd32", "●"
        else:
            color, dot = "#e84118", "●"
        text = {True: "متصل بالجهاز", False: "الجهاز غير متصل"}.get(
            connected, message)
        self.lbl_status.config(text=f"{dot} {text}", fg=color)

    # ---------------------------------------------------------------- أحداث الجهاز
    def _poll_events(self):
        try:
            while True:
                ev = self.dev.events.get_nowait()
                try:
                    if ev[0] == "status":
                        self._set_status(ev[1], ev[2])
                    elif ev[0] == "scan":
                        self._on_scan(ev[1], ev[2])
                except Exception:  # noqa: BLE001 - خطأ ببصمة وحدة ما بيوقف الباقي
                    logging.getLogger("gym").exception("فشلت معالجة بصمة")
                    self._show(C.COLORS["bad"], title="خطأ بمعالجة البصمة",
                               info="التفاصيل بملف app.log")
                    self._schedule_idle()
        except queue.Empty:
            pass
        self.root.after(200, self._poll_events)

    def _on_scan(self, uid, ts):
        r = db.record_attendance(uid, ts)
        note = "  (بصمة مكررة، ما انسجل حضور جديد)" if r["duplicate"] else ""

        if r["kind"] == "staff":
            C.play_sound("ok")
            when = ts.strftime("%H:%M")
            worked = C.fmt_hours(r["worked_minutes"])
            if r["direction"] == "out":
                self._show(C.COLORS["staff_out"], title="موظف — تسجيل خروج", name=r["name"],
                           big=f"مدة العمل اليوم: {worked}", info=f"وقت الخروج: {when}{note}")
            else:
                since = f"  |  عمل اليوم: {worked}" if r["worked_minutes"] > 0 else ""
                self._show(C.COLORS["staff"], title="موظف — تسجيل دخول", name=r["name"],
                           big="✔ تم تسجيل الدخول", info=f"وقت الدخول: {when}{since}{note}")

        elif r["kind"] == "member" and r["status"] == "ok":
            subs = r["subs"]
            active = [x for x in subs if x["active"]]
            expired = [x for x in subs if not x["active"]]
            warn = r["min_days_left"] <= C.WARN_DAYS
            C.play_sound("warn" if warn else "ok")
            extra = f"متبقي عليه دفع: {C.fmt_money(r['remaining'])}" if r["remaining"] > 0 else ""
            if len(subs) == 1:                                  # نوع واحد: الشكل المعتاد
                big, size = days_phrase(r["days_left"]), 40
                info = f"{subs[0]['sub_type']}  |  آخر يوم: {subs[0]['last_day']}{note}"
            else:                                               # كل نوع بسطر ومدته
                big = "\n".join(
                    f"{x['sub_type']}: {days_phrase(x['days_left'])}"
                    + (" ⚠" if x["days_left"] <= C.WARN_DAYS else "") for x in active)
                size = 40 if len(active) == 1 else 30
                info = ("منتهي: " + "، ".join(x["sub_type"] for x in expired) + note) if expired else note.strip()
            self._show(
                C.COLORS["warn"] if warn else C.COLORS["ok"],
                title=("⚠ الاشتراك على وشك الانتهاء" if len(subs) == 1 else "⚠ في اشتراك على وشك الانتهاء") if warn
                else "✔ الاشتراك ساري",
                name=r["name"], big=big, info=info, extra=extra, big_size=size)

        elif r["kind"] == "member":      # كل الأنواع منتهية
            C.play_sound("bad")
            extra = f"متبقي عليه دفع: {C.fmt_money(r['remaining'])}" if r["remaining"] > 0 else ""
            subs = r["subs"]
            if len(subs) == 1:
                info = f"{subs[0]['sub_type']}  |  انتهى بتاريخ: {subs[0]['last_day']}"
            elif subs:
                info = "   |   ".join(f"{x['sub_type']}: انتهى {x['last_day']}" for x in subs)
            else:
                info = "ما عنده اشتراك"
            self._show(C.COLORS["bad"], title="✖ الاشتراك منتهي", name=r["name"],
                       big="لازم يجدد الاشتراك", info=info + note, extra=extra)

        else:                            # بصمة غير معروفة
            C.play_sound("bad")
            self._show(C.COLORS["bad"], title="✖ بصمة غير معروفة", name="غير مسجّل",
                       info=f"رقم المستخدم على الجهاز: {uid}{note}")
        self._schedule_idle()

    # ---------------------------------------------------------------- الأزرار
    def _open_register(self):
        if self._register_win is not None and self._register_win.winfo_exists():
            self._register_win.lift()
            return
        self._register_win = RegisterMemberWindow(self.root, self.dev, self.gender)

    def _open_report(self):
        if self._report_win is not None and self._report_win.winfo_exists():
            self._report_win.lift()
            return
        if not access.request_area(self.root, "report"):      # كلمة سر التقرير
            return
        self._report_win = ReportWindow(self.root, self.gender)

    def _open_staff(self):
        if self._staff_win is not None and self._staff_win.winfo_exists():
            self._staff_win.lift()
            return
        if not access.request_area(self.root, "staff"):       # كلمة سر الموظفين
            return
        self._staff_win = StaffMenuWindow(self.root, self.dev)

    def _open_section_window(self, kind, factory):
        """تجديد / قائمة اللاعبين لقسم الجلسة: بدون أسئلة، لأنو الدخول انعمل بالأول."""
        win = self._wins.get(kind)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        self._wins[kind] = factory(self.root, self.gender)

    # ---------------------------------------------------------------- جلسة القسم
    def _apply_session(self):
        name = db.SECTION_NAMES[self.gender]
        self.lbl_section.config(text=f"قسم {name}", bg=access.SECTION_COLOR[self.gender])
        self.root.title(f"نظام إدارة الجيم — قسم {name}")

    def set_session(self, gender):
        """بيبدّل القسم: بيسكّر كل النوافذ المفتوحة وبيقفل كلمات سر التقرير والموظفين."""
        for win in list(self.root.winfo_children()):
            if isinstance(win, tk.Toplevel):
                win.destroy()
        access.lock("report")
        access.lock("staff")
        self.gender = gender
        self._wins.clear()
        self._register_win = self._staff_win = self._report_win = None
        if self._reset_timer:
            self.root.after_cancel(self._reset_timer)
            self._reset_timer = None
        self._apply_session()
        self._show_idle()

    def _switch_section(self):
        """تبديل القسم: بيخبّي الشاشة (عشان ما يبين شي) وبيطلب الدخول لأي قسم بكلمة سره."""
        hidden = [w for w in self.root.winfo_children()
                  if isinstance(w, tk.Toplevel) and w.winfo_viewable()]
        for w in hidden:                    # حتى القوائم المفتوحة (فيها أسماء) ما لازم تبين
            w.withdraw()
        self.root.withdraw()
        gender = access.login(self.root, "تبديل القسم: اختر القسم")
        if gender is not None:
            self.set_session(gender)        # بيسكّر كل النوافذ القديمة
        else:
            for w in hidden:                # ألغى: بنرجّع كل شي متل ما كان
                if w.winfo_exists():
                    w.deiconify()
        self.root.deiconify()

    def _soon(self, name):
        messagebox.showinfo("قريباً", f"شاشة «{name}» بنضيفها بالمراحل الجاية", parent=self.root)

    def _toggle_fullscreen(self, _event=None):
        self._set_fullscreen(not self._fullscreen)

    def _set_fullscreen(self, state):
        self._fullscreen = state
        self.root.attributes("-fullscreen", state)
