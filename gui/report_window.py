"""gui/report_window.py - التقرير اليومي: معاينة، تعديل، وإرسال لصاحب الجيم عبر واتساب ويب"""
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox

import db
import reports
from gui import access
from gui import common as C

PHONE_KEY = "owner_phone"
AUTO_KEY = "auto_send"        # "1" = البرنامج بيضغط Enter بدالك بعد فتح واتساب ويب


class PhoneDialog(tk.Toplevel):
    """رقم واتساب صاحب الجيم. result = الرقم المنسّق أو None."""

    def __init__(self, parent, current="", modal=True):
        super().__init__(parent)
        self.title("رقم واتساب صاحب الجيم")
        self.configure(bg=C.COLORS["bg"], padx=24, pady=20)
        self.resizable(False, False)
        C.center_on(self, parent, 520, 330)
        self.transient(parent)
        self.result = None
        self.var = tk.StringVar(value=current)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._submit())

        bg, text = C.COLORS["bg"], C.COLORS["text"]
        tk.Label(self, text="رقم واتساب صاحب الجيم", font=C.font(16, True), bg=bg, fg=text
                 ).pack(pady=(0, 6))
        tk.Label(self, text="مع رمز الدولة وبدون صفر وبدون +\nمثال: 962791234567",
                 font=C.font(12), bg=bg, fg=C.COLORS["muted"], justify="center").pack(pady=(0, 10))
        self.entry = tk.Entry(self, textvariable=self.var, font=C.font(16), justify="center",
                              relief="flat", bg="white", width=24)
        self.entry.pack(pady=4)
        self.lbl_err = tk.Label(self, text="", font=C.font(12, True), bg=bg, fg="#ff6b81",
                                wraplength=440)
        self.lbl_err.pack(pady=(8, 4))
        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", pady=(6, 0))
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="حفظ", command=self._submit, font=C.font(13, True),
                  bg=C.COLORS["save"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إلغاء", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2", height=2
                  ).grid(row=0, column=0, sticky="ew", padx=5)
        self.entry.focus_set()
        if modal:
            self.wait_visibility()
            self.grab_set()

    def _submit(self):
        try:
            phone = reports.normalize_phone(self.var.get())
        except ValueError as e:
            self.lbl_err.config(text=str(e))
            return
        db.set_setting(PHONE_KEY, phone)
        self.result = phone
        self.destroy()


class ReportWindow(access.GatedWindow):
    """التقرير اليومي. محمي بكلمة سر "report" وبيتسكر لحاله بعد فترة بدون نشاط."""

    def __init__(self, parent, section=None):
        super().__init__(parent, "report")
        self.section = section              # قسم الجلسة (ذكر / أنثى): التقرير بيشمل لاعبين هالقسم بس
        self.title("التقرير اليومي")
        self.configure(bg=C.COLORS["bg"], padx=20, pady=14)
        C.center_on(self, parent, 800, 760)
        self.transient(parent)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.phone_var = tk.StringVar()
        self.hint_var = tk.StringVar()
        self.auto_var = tk.BooleanVar(value=db.get_setting(AUTO_KEY) == "1")
        self._build()
        self._update_phone_label()
        self.refresh()
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------ بناء الواجهة
    def _build(self):
        bg, text = C.COLORS["bg"], C.COLORS["text"]
        heading = "التقرير اليومي"
        if self.section:
            heading += f" — قسم {db.SECTION_NAMES[self.section]}"
        tk.Label(self, text=heading, font=C.font(18, True), bg="#128c7e", fg="white",
                 pady=8).pack(fill="x", pady=(0, 10))

        # الأزرار والملاحظات أول (تحت) عشان ما ينقصوا بالشاشات الصغيرة
        btns = tk.Frame(self, bg=bg)
        btns.pack(side="bottom", fill="x", pady=(10, 0))
        btns.columnconfigure((0, 1, 2, 3), weight=1, uniform="b")
        self.btn_send = tk.Button(btns, text="إرسال عبر واتساب", command=self._send,
                                  font=C.font(15, True), bg="#128c7e", fg="white",
                                  activeforeground="white", relief="flat", cursor="hand2",
                                  height=2)
        self.btn_send.grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 8))
        for col, (label, cmd) in enumerate((("إغلاق", self.destroy),
                                            ("كلمة السر", lambda: access.change_password(self, "report")),
                                            ("رقم الواتساب", self._ask_phone),
                                            ("نسخ النص", self._copy))):
            tk.Button(btns, text=label, command=cmd, font=C.font(12, True),
                      bg=C.COLORS["panel"] if label != "إغلاق" else C.COLORS["cancel"],
                      fg="white", relief="flat", cursor="hand2", height=2
                      ).grid(row=1, column=col, sticky="ew", padx=5)
        tk.Label(self, textvariable=self.hint_var, font=C.font(11), bg=bg, fg="#fbc531",
                 wraplength=720, justify="right").pack(side="bottom", anchor="e", pady=(6, 0))
        tk.Checkbutton(self, text="إرسال تلقائي: البرنامج بيضغط Enter بدالي (لا تلمس الكيبورد خلال ~30 ثانية)",
                       variable=self.auto_var, command=self._toggle_auto, font=C.font(11, True),
                       bg=bg, fg=text, selectcolor=C.COLORS["panel"], activebackground=bg,
                       activeforeground=text, cursor="hand2").pack(side="bottom", anchor="e")
        tk.Label(self, textvariable=self.phone_var, font=C.font(12, True), bg=bg,
                 fg=C.COLORS["muted"]).pack(side="bottom", anchor="e", pady=(8, 0))

        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text="تاريخ التقرير", font=C.font(13), bg=bg, fg=text).pack(side="right")
        tk.Entry(top, textvariable=self.date_var, font=C.font(14), justify="center",
                 relief="flat", bg="white", width=12).pack(side="right", padx=10)
        for label, cmd in (("عرض", self.refresh),
                           ("أمس", lambda: self._set_day(date.today() - timedelta(days=1))),
                           ("اليوم", lambda: self._set_day(date.today()))):
            tk.Button(top, text=label, command=cmd, font=C.font(11, True), bg=C.COLORS["btn"],
                      fg="white", relief="flat", cursor="hand2", padx=12
                      ).pack(side="right", padx=3)

        frame = tk.Frame(self, bg=bg)
        frame.pack(fill="both", expand=True, pady=10)
        self.text = tk.Text(frame, font=C.font(13), wrap="word", bg=C.COLORS["panel"], fg=text,
                            insertbackground="white", relief="flat", padx=14, pady=12, height=12)
        self.text.tag_configure("rtl", justify="right")
        scroll = tk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

    # ------------------------------------------------------------ منطق
    def _set_day(self, day):
        self.date_var.set(day.isoformat())
        self.refresh()

    def _parse_day(self):
        raw = self.date_var.get().strip().translate(reports._DIGITS)
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ValueError("اكتب التاريخ بهالشكل: 2026-11-08") from None

    def refresh(self):
        try:
            day = self._parse_day()
        except ValueError as e:
            messagebox.showwarning("تنبيه", str(e), parent=self)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", reports.build_report_text(day, self.section))
        self.text.tag_add("rtl", "1.0", "end")
        self.hint_var.set("تقدر تعدّل النص قبل الإرسال. الإرسال بيفتح واتساب ويب بالمتصفح وإنت بتضغط إرسال هناك.")

    def _report_text(self):
        return self.text.get("1.0", "end").strip()

    def _update_phone_label(self):
        phone = db.get_setting(PHONE_KEY)
        self.phone_var.set(f"سيُرسل إلى: +{phone}" if phone else "ما في رقم محفوظ، اضغط «رقم الواتساب»")

    def _ask_phone(self):
        dlg = PhoneDialog(self, db.get_setting(PHONE_KEY, ""))
        self.wait_window(dlg)
        self._update_phone_label()
        return dlg.result

    def _set_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _copy(self):
        self._set_clipboard(self._report_text())
        self.hint_var.set("تم نسخ النص. بتقدر تلصقه بأي محادثة.")

    def _send(self):
        text = self._report_text()
        if not text:
            messagebox.showwarning("تنبيه", "التقرير فاضي", parent=self)
            return
        phone = db.get_setting(PHONE_KEY) or self._ask_phone()
        if not phone:
            return
        # تقرير طويل: الرابط ما بيتحمل النص، فبننسخه وبنفتح المحادثة بس (بيتلصق Ctrl+V)
        mode = reports.send_mode(phone, text)
        if mode == "paste":
            self._set_clipboard(text)
        opened, _url, mode = reports.open_whatsapp(phone, text, mode)
        if not opened:
            self._copy()
            messagebox.showerror("ما انفتح المتصفح",
                                 "ما قدرت أفتح المتصفح، بس نسخت النص. افتح واتساب والصقه.",
                                 parent=self)
            return
        if self.auto_var.get():
            self.btn_send.config(state="disabled")
            self.hint_var.set("جاري الإرسال التلقائي... لا تلمس الكيبورد ولا الماوس (حوالي 30 ثانية).")
            C.run_in_thread(self, lambda: reports.auto_press_enter(paste=(mode == "paste")),
                            self._auto_done)
        elif mode == "paste":
            self.hint_var.set("انفتحت المحادثة بواتساب ويب والتقرير منسوخ: اضغط Ctrl+V بصندوق الكتابة "
                              "وبعدين إرسال. وإذا طلب تسجيل دخول، سجّل وجرّب مرة ثانية.")
        else:
            self.hint_var.set("انفتح واتساب ويب بالمتصفح. اضغط إرسال هناك. وإذا طلب تسجيل دخول، "
                              "سجّل وبعدها جرّب الإرسال مرة ثانية.")

    def _toggle_auto(self):
        on = self.auto_var.get()
        db.set_setting(AUTO_KEY, "1" if on else "0")
        self.hint_var.set("الإرسال التلقائي شغال: بعد فتح واتساب ويب البرنامج بيضغط Enter بدالك."
                          if on else "الإرسال التلقائي مطفي: بتضغط إرسال بإيدك بواتساب ويب.")

    def _auto_done(self, result, error):
        if not self.winfo_exists():
            return
        self.btn_send.config(state="normal")
        if error is not None:
            self.hint_var.set(f"فشل الإرسال التلقائي ({error}). اضغط إرسال يدوياً بواتساب ويب.")
            return
        ok, message = result
        self.hint_var.set(message if ok else f"{message} اضغط إرسال يدوياً بواتساب ويب.")
