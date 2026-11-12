"""cleanup_test.py - تنظيف بيانات التجارب

- بيمسح من الجهاز كل المستخدمين برقم >= 100 (مستخدمين التجارب) مع بصماتهم
- مستخدمين الأدمن (أرقام أقل من 100) ما بينلمسوا
- بيعرض البصمات المتبقية بالجهاز، وبيسألك إذا بدك تمسح gym.db (بيانات التجارب)
"""
import os

from zk import ZK

import config
import db


def main():
    zk = ZK(config.DEVICE_IP, port=config.DEVICE_PORT, timeout=config.DEVICE_TIMEOUT)
    conn = zk.connect()
    try:
        conn.disable_device()
        users = conn.get_users()
        print("مستخدمين الجهاز قبل:", [(u.uid, u.privilege) for u in users])

        # بصمات: بنمسح أي بصمة uid >= 100 حتى لو المستخدم نفسه مش موجود (بصمات يتيمة)
        for t in conn.get_templates():
            if t.uid >= db.FIRST_DEVICE_UID:
                conn.delete_user_template(uid=t.uid, temp_id=t.fid)
                print("حذفت بصمة uid =", t.uid, "finger =", t.fid)

        for u in users:
            if u.uid >= db.FIRST_DEVICE_UID:
                conn.delete_user(uid=u.uid)
                print("حذفت مستخدم uid =", u.uid)

        print("مستخدمين الجهاز بعد:", [(u.uid, u.privilege) for u in conn.get_users()])
        print("بصمات الجهاز بعد:", [(t.uid, t.fid) for t in conn.get_templates()])
    finally:
        conn.enable_device()
        conn.disconnect()

    if os.path.exists(db.DB_PATH):
        if input(f"امسح {db.DB_PATH} (بيانات التجارب فقط!)؟ y/n: ").strip().lower() == "y":
            os.remove(db.DB_PATH)
            print("انمسحت. بتنعمل من جديد عند أول تشغيل.")


if __name__ == "__main__":
    main()
