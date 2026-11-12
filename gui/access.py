"""gui/access.py - حماية الأجزاء الحساسة بكلمة سر لكل جزء:
قسم شباب، قسم نساء، التقرير اليومي، وشاشات الموظفين (scope: "ذكر" / "أنثى" / "report" / "staff")

ملاحظة أمان: هاي حماية على مستوى واجهة البرنامج. كلمات السر بتتخزن مشفّرة، بس ملف
gym.db نفسه مش مشفّر، فأي حدا عنده وصول لملفات اللابتوب بيقدر يفتحه ببرنامج ثاني.
"""
import time
import tkinter as tk
from tkinter import messagebox

import db
from gui import common as C

SECTION = db.SECTION_NAMES
SECTION_COLOR = {"ذكر": "#0984e3", "أنثى": "#c2185b"}
# اسم كل جزء محمي كما بيظهر برسائل كلمة السر
SCOPE_NAME = {"ذكر": "قسم شباب", "أنثى": "قسم نساء", "report": "التقرير اليومي", "staff": "شاشات الموظفين"}
UNLOCK_SECONDS = 300          # بعد هالمدة بدون نشاط: النافذة بتتسكر وبينطلب الباسورد من جديد
_unlocked = {}                # الجزء المحمي -> وقت انتهاء الصلاحية
_last_activity = time.time()  # آخر مرة المستخدم لمس الكيبورد أو الماوس بأي نافذة بالبرنامج


def is_unlocked(gender):
    return _unlocked.get(gender, 0) > time.time()


def unlock(gender):
    _unlocked[gender] = time.time() + UNLOCK_SECONDS


def install_activity_tracking(root):
    """بيتابع نشاط الكيبورد والماوس بكل النوافذ، عشان النافذة المحمية ما تتسكر والمستخدم شغال."""
    def touch(_event=None):
        global _last_activity
        _last_activity = time.time()
    for event in ("<Key>", "<Button>", "<Motion>"):
        root.bind_all(event, touch, add="+")


def lock(gender=None):
    if gender is None:
        _unlocked.clear()
    else:
        _unlocked.pop(gender, None)


# ------------------------------------------------------------ نوافذ حوار
class _Modal(tk.Toplevel):
    def __init__(self, parent, title, width, height, modal=True):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C.COLORS["bg"], padx=24, pady=20)
        self.resizable(False, False)
        C.center_on(self, parent, width, height)
        if parent.winfo_viewable():
            self.transient(parent)
        else:                                # شاشة الدخول: الأب مخفي، فبنخلي النافذة فوق كل شي
            self.attributes("-topmost", True)
        self.result = None
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda e: self.destroy())
        self._want_modal = modal

    def _make_modal(self):
        if self._want_modal:
            self.wait_visibility()
            self.grab_set()
            self.lift()
            self.focus_force()


def _label(parent, text, size=13, bold=False, color=None, **kw):
    return tk.Label(parent, text=text, font=C.font(size, bold), bg=C.COLORS["bg"],
                    fg=color or C.COLORS["text"], **kw)


def _password_entry(parent, var):
    return tk.Entry(parent, textvariable=var, show="●", font=C.font(16), justify="center",
                    relief="flat", bg="white", width=22)


class ChooseSectionDialog(_Modal):
    """اختيار القسم: ذكور أو إناث. النتيجة (result) = "ذكر" أو "أنثى" أو None."""

    def __init__(self, parent, title="اختر القسم", modal=True):
        super().__init__(parent, "اختيار القسم", 420, 260, modal)
        _label(self, title, 16, True).pack(pady=(0, 18))
        row = tk.Frame(self, bg=C.COLORS["bg"])
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1, uniform="s")
        for col, gender in ((1, "ذكر"), (0, "أنثى")):       # ذكور عاليمين
            tk.Button(row, text=SECTION[gender], command=lambda g=gender: self._pick(g),
                      font=C.font(18, True), bg=SECTION_COLOR[gender], fg="white",
                      activebackground=SECTION_COLOR[gender], activeforeground="white",
                      relief="flat", cursor="hand2", height=3
                      ).grid(row=0, column=col, sticky="ew", padx=6)
        self._make_modal()

    def _pick(self, gender):
        self.result = gender
        self.destroy()


class PasswordDialog(_Modal):
    """طلب كلمة سر القسم. إذا ما في وحدة (أول مرة) بيطلب إنشاءها. result = True/False."""

    def __init__(self, parent, gender, modal=True):
        self.gender = gender                      # اسم الجزء المحمي (scope)
        self.creating = not db.has_password(gender)
        name = SCOPE_NAME[gender]
        title = f"إنشاء كلمة سر: {name}" if self.creating else name
        super().__init__(parent, title, 460, 330 if self.creating else 260, modal)
        self.result = False
        self.pw_var = tk.StringVar()
        self.pw2_var = tk.StringVar()

        if self.creating:
            _label(self, f"أول استخدام: {name}\nاختر كلمة سر ({db.MIN_PASSWORD_LEN} "
                         "أحرف أو أرقام على الأقل)", 13, True, justify="center").pack(pady=(0, 12))
        else:
            _label(self, f"اكتب كلمة سر: {name}", 14, True).pack(pady=(0, 12))
        self.entry = _password_entry(self, self.pw_var)
        self.entry.pack(pady=4)
        if self.creating:
            _label(self, "أعد كتابتها للتأكيد", 12).pack(pady=(10, 2))
            _password_entry(self, self.pw2_var).pack(pady=4)

        self.lbl_err = _label(self, "", 12, True, color="#ff6b81")
        self.lbl_err.pack(pady=(8, 4))
        btns = tk.Frame(self, bg=C.COLORS["bg"])
        btns.pack(fill="x")
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="حفظ ودخول" if self.creating else "دخول", command=self._submit,
                  font=C.font(13, True), bg=C.COLORS["save"], fg="white", relief="flat",
                  cursor="hand2", height=2).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إلغاء", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2",
                  height=2).grid(row=0, column=0, sticky="ew", padx=5)
        self.bind("<Return>", lambda e: self._submit())
        self.entry.focus_set()
        self._make_modal()

    def _submit(self):
        pw = self.pw_var.get()
        if self.creating:
            if pw != self.pw2_var.get():
                self.lbl_err.config(text="كلمتين السر مش متطابقتين")
                return
            try:
                db.set_password(self.gender, pw)
            except ValueError as e:
                self.lbl_err.config(text=str(e))
                return
        elif not db.check_password(self.gender, pw):
            self.lbl_err.config(text="كلمة السر غلط")
            self.pw_var.set("")
            self.entry.focus_set()
            return
        self.result = True
        self.destroy()


class ChangePasswordDialog(_Modal):
    """تغيير كلمة سر قسم (بتطلب الحالية). result = True إذا تغيرت."""

    def __init__(self, parent, gender, modal=True):
        super().__init__(parent, f"تغيير كلمة سر: {SCOPE_NAME[gender]}", 460, 400, modal)
        self.gender = gender
        self.result = False
        self.old_var, self.new_var, self.new2_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for text, var in (("كلمة السر الحالية", self.old_var), ("كلمة السر الجديدة", self.new_var),
                          ("أعد كتابة الجديدة", self.new2_var)):
            _label(self, text, 12).pack(pady=(8, 2))
            e = _password_entry(self, var)
            e.pack()
            if var is self.old_var:
                e.focus_set()
        self.lbl_err = _label(self, "", 12, True, color="#ff6b81")
        self.lbl_err.pack(pady=(10, 4))
        btns = tk.Frame(self, bg=C.COLORS["bg"])
        btns.pack(fill="x")
        btns.columnconfigure((0, 1), weight=1, uniform="b")
        tk.Button(btns, text="تغيير", command=self._submit, font=C.font(13, True),
                  bg=C.COLORS["save"], fg="white", relief="flat", cursor="hand2",
                  height=2).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(btns, text="إلغاء", command=self.destroy, font=C.font(13, True),
                  bg=C.COLORS["cancel"], fg="white", relief="flat", cursor="hand2",
                  height=2).grid(row=0, column=0, sticky="ew", padx=5)
        self.bind("<Return>", lambda e: self._submit())
        self._make_modal()

    def _submit(self):
        if self.new_var.get() != self.new2_var.get():
            self.lbl_err.config(text="كلمتين السر الجديدتين مش متطابقتين")
            return
        try:
            db.set_password(self.gender, self.new_var.get(), old_password=self.old_var.get())
        except ValueError as e:
            self.lbl_err.config(text=str(e))
            return
        self.result = True
        self.destroy()


# ------------------------------------------------------------ نقطة الدخول
def request_access(parent, title="اختر القسم"):
    """
    بيسأل: ذكور ولا إناث؟ وبعدين كلمة سر القسم (إلا إذا انفتح قبل قليل).
    بيرجع "ذكر" / "أنثى" إذا انسمح الدخول، وإلا None.
    """
    chooser = ChooseSectionDialog(parent, title)
    parent.wait_window(chooser)
    gender = chooser.result
    if gender is None:
        return None
    if not is_unlocked(gender):
        dlg = PasswordDialog(parent, gender)
        parent.wait_window(dlg)
        if not dlg.result:
            return None
    unlock(gender)
    return gender


def login(parent, title="تسجيل الدخول: اختر القسم"):
    """
    شاشة الدخول للقسم (شباب / نساء) بكلمة سره. بيرجع "ذكر" / "أنثى" إذا نجح الدخول،
    أو None إذا المستخدم سكّر شاشة الاختيار. إذا ألغى كلمة السر بيرجع لاختيار القسم.
    بتنطلب كلمة السر كل مرة (مش من الكاش)، لأنو هاد بداية جلسة جديدة.
    """
    while True:
        chooser = ChooseSectionDialog(parent, title)
        parent.wait_window(chooser)
        gender = chooser.result
        if gender is None:
            return None
        dlg = PasswordDialog(parent, gender)
        parent.wait_window(dlg)
        if dlg.result:
            unlock(gender)
            return gender


def request_area(parent, scope):
    """
    كلمة سر جزء محمي ("report" للتقرير، "staff" للموظفين). بيرجع True إذا انسمح الدخول.
    (إذا انفتح قبل قليل ما بيسأل من جديد.)
    """
    if not is_unlocked(scope):
        dlg = PasswordDialog(parent, scope)
        parent.wait_window(dlg)
        if not dlg.result:
            return False
    unlock(scope)
    return True


def change_password(parent, gender):
    dlg = ChangePasswordDialog(parent, gender)
    parent.wait_window(dlg)
    if dlg.result:
        messagebox.showinfo("تم", f"تم تغيير كلمة سر: {SCOPE_NAME[gender]}", parent=parent)


class GatedWindow(tk.Toplevel):
    """
    نافذة جزء محمي (قسم، تقرير، موظفين): بتتسكر لحالها لما ما حدا يلمس الكيبورد أو الماوس
    بالبرنامج لمدة UNLOCK_SECONDS، وبينطلب الباسورد من جديد. (gender = اسم الجزء المحمي.)
    """

    def __init__(self, parent, gender):
        super().__init__(parent)
        self.gender = gender
        self._opened = time.time()
        self._idle_job = None
        self._check_idle()

    def _check_idle(self):
        if time.time() - max(self._opened, _last_activity) > UNLOCK_SECONDS:
            lock(self.gender)
            self.destroy()
            return
        unlock(self.gender)                    # لسا في نشاط: بنجدد صلاحية الباسورد
        self._idle_job = self.after(10_000, self._check_idle)

    def destroy(self):
        if self._idle_job is not None:
            try:
                self.after_cancel(self._idle_job)
            except tk.TclError:
                pass
            self._idle_job = None
        super().destroy()
