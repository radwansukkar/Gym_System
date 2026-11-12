"""console_test.py - اختبار ربط الجهاز بقاعدة البيانات بدون واجهة

1) استماع: كل بصمة بتنسجل بالحضور وبتطبع النتيجة
2) تسجيل لاعب تجريبي: بيانات + المستخدم على الجهاز + البصمة
"""
import queue
import threading

import config
import db
from device import DeviceError, DeviceManager

db.init_db()
dev = DeviceManager(config.DEVICE_IP, config.DEVICE_PORT)
dev.start()

LABELS = {"ok": "✅ ساري", "expired": "🔴 منتهي", "unknown": "🔴 بصمة غير معروفة"}


def handle_events(stop_flag):
    while not stop_flag.is_set():
        try:
            ev = dev.events.get(timeout=0.5)
        except queue.Empty:
            continue
        if ev[0] == "status":
            print("\n[الجهاز]", "متصل ✅" if ev[1] else f"غير متصل ❌ ({ev[2]})")
        elif ev[0] == "scan":
            r = db.record_attendance(ev[1], ev[2])
            dup = " (مكررة، ما انسجلت)" if r["duplicate"] else ""
            print(f"\n[بصمة] uid={ev[1]} | {r['kind']} | {r['name']} | "
                  f"{LABELS[r['status']]} | باقي {r['days_left']} يوم | "
                  f"متبقي دفع {r['remaining']}{dup}")


def register_test_member():
    name = input("الاسم: ")
    phone = input("رقم الهاتف (Enter للتخطي): ")
    sub_type = input(f"النوع {db.SUB_TYPES}: ")
    days = int(input("المدة بالأيام: "))
    price = float(input("السعر الكلي: "))
    paid = float(input("المدفوع: "))

    # الرقم على الجهاز بيتولد تلقائي (100, 101, 102...) وما بنسأل عنه
    uid = db.peek_next_device_uid({u for u, _ in dev.device_users()})
    print(f"رقم الجهاز التلقائي: {uid}")
    print(">>> حط إصبعك على الجهاز 3 مرات حسب تعليمات شاشة الجهاز...")
    try:
        # أول البصمة، وإذا نجحت بنحفظ اللاعب. وإذا فشلت ما بيضل شي عالق لا بالجهاز ولا بالقاعدة
        dev.register_user_with_fingerprint(uid)
    except DeviceError as e:
        print("❌", e)
        return
    r = db.add_member(name, phone, sub_type, days, price, paid, device_uid=uid)
    print(f"✅ انحفظ اللاعب (device_uid={r['device_uid']})")


def main():
    stop_flag = threading.Event()
    t = threading.Thread(target=handle_events, args=(stop_flag,), daemon=True)
    t.start()
    try:
        while True:
            print("\n1) تسجيل لاعب تجريبي   2) مستخدمي الجهاز   3) بصمات الجهاز   0) خروج")
            print("(البصمات بتنطبع تلقائياً بأي وقت)")
            c = input("> ").strip()
            if c == "1":
                register_test_member()
            elif c == "2":
                try:
                    print(dev.device_users())
                except DeviceError as e:
                    print("❌", e)
            elif c == "3":
                try:
                    print(dev.device_templates())
                except DeviceError as e:
                    print("❌", e)
            elif c == "0":
                break
    finally:
        stop_flag.set()
        dev.stop()


if __name__ == "__main__":
    main()
