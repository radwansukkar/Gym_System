"""reset_passwords_gui.py - أداة المالك: تعيين كلمة سر جديدة لما حدا ينساها

كلمات السر مخزنة بشكل ما بينفع نرجّع منه النص الأصلي (مش ممكن "نعرفها")، بس بنقدر نعيّن وحدة جديدة.
- بتشتغل بدون بايثون: ابنيها exe بـ build_reset_tool.bat وانسخها على فلاشة.
- حطها جنب gym.db (أو اختار الملف من الزر). بتاخد نسخة احتياطية من gym.db قبل ما تغيّر شي.
- ما تنترك على لابتوب الجيم: أي حدا معه الأداة بيقدر يغيّر أي كلمة سر ويشوف كل البيانات.
"""
import os
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import db
from gui import common as C

SCOPES = [("ذكر", "قسم شباب"), ("أنثى", "قسم نساء"), ("report", "التقرير اليومي"), ("staff", "شاشات الموظفين")]


class ResetApp:
    def __init__(self, root, db_path=None):
        self.root = root
        root.title("استعادة كلمة السر — Star Gym")
        root.configure(bg=C.COLORS["bg"], padx=26, pady=20)
        root.resizable(False, False)
        self.path_var = tk.StringVar()
        self.scope_var = tk.StringVar(value=SCOPES[0][0])
        self.new_var = tk.StringVar()
        self.new2_var = tk.StringVar()
        self.status_vars = {}
        self._build()
        self.set_path(db_path or (db.DB_PATH if os.path.exists(db.DB_PATH) else ""))

    # ------------------------------------------------------------ واجهة
    def _build(self):
        bg, text, muted = C.COLORS["bg"], C.COLORS["text"], C.COLORS["muted"]
        tk.Label(self.root, text="تعيين كلمة سر جديدة", font=C.font(18, True), bg=bg, fg=text
                 ).pack(anchor="e")
        tk.Label(self.root, text="كلمات السر ما بتنعرف (مخزنة مشفرة)، بس بتتبدّل بوحدة جديدة.",
                 font=C.font(11), bg=bg, fg=muted).pack(anchor="e", pady=(2, 12))

        row = tk.Frame(self.root, bg=bg)
        row.pack(fill="x")
        tk.Button(row, text="اختيار ملف gym.db", command=self.choose_file, font=C.font(11, True),
                  bg=C.COLORS["panel"], fg="white", relief="flat", cursor="hand2", padx=10
                  ).pack(side="left")
        tk.Label(row, textvariable=self.path_var, font=C.font(10), bg=bg, fg=muted, anchor="e",
                 wraplength=420, justify="right").pack(side="right", fill="x", expand=True, padx=8)

        tk.Label(self.root, text="أي جزء؟", font=C.font(13, True), bg=bg, fg=text
                 ).pack(anchor="e", pady=(14, 4))
        for scope, label in SCOPES:
            line = tk.Frame(self.root, bg=bg)
            line.pack(fill="x", pady=1)
            self.status_vars[scope] = tk.StringVar()
            tk.Label(line, textvariable=self.status_vars[scope], font=C.font(10), bg=bg,
                     fg=muted).pack(side="left")
            tk.Radiobutton(line, text=label, variable=self.scope_var, value=scope, font=C.font(13),
                           bg=bg, fg=text, selectcolor=C.COLORS["panel"], activebackground=bg,
                           activeforeground=text, cursor="hand2").pack(side="right")

        for label, var in (("كلمة السر الجديدة", self.new_var), ("أعد كتابتها", self.new2_var)):
            tk.Label(self.root, text=label, font=C.font(12), bg=bg, fg=text).pack(anchor="e", pady=(10, 2))
            tk.Entry(self.root, textvariable=var, show="●", font=C.font(15), justify="center",
                     relief="flat", bg="white", width=26).pack(anchor="e")
        self.lbl_msg = tk.Label(self.root, text="", font=C.font(12, True), bg=bg, fg="#ff6b81",
                                wraplength=460, justify="right")
        self.lbl_msg.pack(anchor="e", pady=(10, 4))
        tk.Button(self.root, text="تعيين كلمة السر", command=self.apply, font=C.font(14, True),
                  bg=C.COLORS["save"], fg="white", relief="flat", cursor="hand2", height=2
                  ).pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------ منطق
    def choose_file(self):
        path = filedialog.askopenfilename(title="اختر ملف gym.db", filetypes=[("قاعدة البيانات", "*.db")])
        if path:
            self.set_path(path)

    def set_path(self, path):
        self.path_var.set(path or "ما اخترت ملف بعد")
        self.path = path
        for scope, _ in SCOPES:
            self.status_vars[scope].set("")
        if not path or not os.path.exists(path):
            return
        db.DB_PATH = path
        try:
            for scope, _ in SCOPES:
                self.status_vars[scope].set("محمي بكلمة سر" if db.has_password(scope) else "ما في كلمة سر بعد")
        except sqlite3.Error:
            self.path = ""
            self.path_var.set("هاد مش ملف gym.db صحيح")

    def apply(self):
        if not self.path or not os.path.exists(self.path):
            return self._error("اختر ملف gym.db أول (الزر فوق).")
        new, again = self.new_var.get(), self.new2_var.get()
        if new != again:
            return self._error("كلمتين السر مش متطابقتين.")
        if len(new) < db.MIN_PASSWORD_LEN:
            return self._error(f"كلمة السر لازم تكون {db.MIN_PASSWORD_LEN} أحرف أو أرقام على الأقل.")
        scope = self.scope_var.get()
        label = dict(SCOPES)[scope]
        if not messagebox.askyesno("تأكيد", f"تعيين كلمة سر جديدة لـ «{label}»؟\nبتاخد نسخة احتياطية من الملف أول.",
                                   parent=self.root):
            return
        try:
            backup = self._backup()
            db.DB_PATH = self.path
            db.admin_set_password(scope, new)
        except (ValueError, sqlite3.Error, OSError) as e:
            return self._error(f"ما تم التغيير: {e}")
        self.new_var.set("")
        self.new2_var.set("")
        self.lbl_msg.config(text="")
        self.set_path(self.path)
        messagebox.showinfo("تم", f"تم تعيين كلمة سر «{label}».\nالنسخة الاحتياطية: {os.path.basename(backup)}",
                            parent=self.root)

    def _backup(self):
        folder = os.path.dirname(os.path.abspath(self.path))
        target = os.path.join(folder, f"gym_before_password_reset_{datetime.now():%Y%m%d_%H%M%S}.db")
        src, dst = sqlite3.connect(self.path), sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return target

    def _error(self, message):
        self.lbl_msg.config(text=message)


def main():
    root = tk.Tk()
    C.apply_icon(root)
    ResetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
