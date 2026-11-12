"""config.py - إعدادات النظام

القيم الافتراضية هون. وإذا بدك تغيّر شي بدون ما تعدّل الكود (مهم بعد تحويل البرنامج لـ exe)
حط ملف اسمه config.json جنب البرنامج، وكتب فيه بس القيم اللي بدك تغيّرها. مثال:
    {"DEVICE_IP": "192.168.50.2", "GYM_NAME": "Star Gym", "CURRENCY": "دينار"}
"""
import json
import os
import sys

# مجلد البرنامج: جنبه بتنحفظ gym.db والنسخ الاحتياطية وسجل الأخطاء (app.log)
if getattr(sys, "frozen", False):                       # نسخة exe (PyInstaller)
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

_overrides = {}
_path = os.path.join(APP_DIR, "config.json")
if os.path.exists(_path):
    try:
        with open(_path, encoding="utf-8") as f:
            _overrides = json.load(f)
    except (OSError, ValueError):
        _overrides = {}                                 # ملف تالف: نكمل بالقيم الافتراضية


def _get(name, default):
    return _overrides.get(name, default)


DEVICE_IP = _get("DEVICE_IP", "192.168.50.2")
DEVICE_PORT = _get("DEVICE_PORT", 4370)
DEVICE_TIMEOUT = _get("DEVICE_TIMEOUT", 10)             # ثواني انتظار الاتصال
RECONNECT_DELAY = _get("RECONNECT_DELAY", 3)            # ثواني بين محاولات إعادة الاتصال
DEBUG_ENROLL = _get("DEBUG_ENROLL", True)               # يطبع تفاصيل تسجيل البصمة بالكونسول

GYM_NAME = _get("GYM_NAME", "Star Gym")                 # بيظهر بعنوان التقرير اليومي
CURRENCY = _get("CURRENCY", "")                         # مثلاً "دينار" (فاضي = بس الرقم)
BACKUP_EVERY_HOURS = _get("BACKUP_EVERY_HOURS", 6)      # نسخة احتياطية دورية أثناء التشغيل
WHATSAPP_SETTLE_SECONDS = _get("WHATSAPP_SETTLE_SECONDS", 15)     # انتظار تحميل واتساب ويب قبل Enter (زوّدها إذا النت بطيء)
WHATSAPP_RETRY_GAP_SECONDS = _get("WHATSAPP_RETRY_GAP_SECONDS", 10)  # الفاصل بين ضغطتين Enter
WHATSAPP_MAX_URL = _get("WHATSAPP_MAX_URL", 1800)       # فوق هالطول التقرير بيتنسخ ويتلصق (Ctrl+V) بدل ما يتكتب بالرابط
