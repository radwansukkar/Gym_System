"""main.py - نقطة تشغيل البرنامج. شغّله من أي مكان: python main.py (أو StarGym.exe)"""
import ctypes
import logging
import os
import socket
import sys
import tkinter as tk
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

import config
import db
from device import DeviceManager
from gui import access
from gui import common as C
from gui.main_window import MainWindow

SINGLE_INSTANCE_PORT = 47653        # بورت محلي بنحجزه عشان ما ينفتح البرنامج مرتين
log = logging.getLogger("gym")


def setup_logging():
    """سجل الأخطاء app.log جنب البرنامج. ضروري لأنو نسخة exe (بدون كونسول) ما بتعرض الأخطاء."""
    handler = RotatingFileHandler(os.path.join(config.APP_DIR, "app.log"), maxBytes=500_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    sys.excepthook = lambda *exc: log.critical("خطأ غير معالج", exc_info=exc)


def ensure_single_instance():
    """بيرجع socket (لازم نضل ماسكينه) إذا هاي أول نسخة، أو None إذا البرنامج شغال مسبقاً."""
    guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        guard.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        guard.listen(1)
    except OSError:
        guard.close()
        return None
    return guard


def safe_backup():
    try:
        path = db.backup_db()
        log.info("نسخة احتياطية: %s", path)
    except Exception:  # noqa: BLE001 - النسخ الاحتياطي ما لازم يوقف البرنامج
        log.exception("فشلت النسخة الاحتياطية")


def main():
    setup_logging()
    guard = ensure_single_instance()
    if guard is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("نظام إدارة الجيم", "البرنامج شغال مسبقاً (شوف شريط المهام).")
        return

    db.init_db()
    safe_backup()
    log.info("تشغيل البرنامج (الجهاز %s:%s)", config.DEVICE_IP, config.DEVICE_PORT)

    dev = DeviceManager()
    dev.start()

    try:    # عشان أيقونة البرنامج تظهر بشريط المهام بدل أيقونة بايثون
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("stargym.system")
    except Exception:  # noqa: BLE001 - مش ويندوز
        pass

    root = tk.Tk()
    root.withdraw()                       # ما بنبين الشاشة الرئيسية قبل تسجيل الدخول
    C.apply_icon(root)

    def on_tk_error(exc, value, tb):
        log.error("خطأ بالواجهة", exc_info=(exc, value, tb))
        messagebox.showerror("خطأ غير متوقع", f"حصل خطأ: {value}\nالتفاصيل بملف app.log")

    root.report_callback_exception = on_tk_error

    gender = access.login(root, "تسجيل الدخول: اختر القسم")      # شباب أو نساء، بكلمة سر القسم
    if gender is None:                                           # سكّر شاشة الدخول: خروج
        dev.stop()
        root.destroy()
        guard.close()
        return
    MainWindow(root, dev, gender)
    root.deiconify()

    every_ms = int(config.BACKUP_EVERY_HOURS * 3600 * 1000)

    def periodic_backup():
        safe_backup()
        root.after(every_ms, periodic_backup)

    root.after(every_ms, periodic_backup)

    def on_close():
        safe_backup()
        dev.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    guard.close()


if __name__ == "__main__":
    main()
