"""reset_passwords.py - مسح كلمة سر (لما حدا ينساها). شغّله من مجلد المشروع، والبرنامج مسكّر.

بعد المسح، أول مرة بتفتح فيها الجزء المحمي البرنامج بيطلب منك تنشئ كلمة سر جديدة.
"""
import db

db.init_db()
OPTIONS = {
    "1": ("قسم شباب", ["ذكر"]),
    "2": ("قسم نساء", ["أنثى"]),
    "3": ("التقرير اليومي", ["report"]),
    "4": ("شاشات الموظفين", ["staff"]),
    "5": ("الكل", list(db.PASSWORD_SCOPES)),
}
for key, (label, _) in OPTIONS.items():
    print(f"{key}) {label}")
choice = OPTIONS.get(input("أي كلمة سر بدك تمسح؟ ").strip())
if not choice:
    raise SystemExit("اختيار غير صحيح")
if input(f"متأكد من مسح كلمة سر ({choice[0]})؟ (y/n): ").strip().lower() == "y":
    for scope in choice[1]:
        db.clear_password(scope)
    print("تم. بتنعمل كلمة سر جديدة أول ما تفتح الجزء المحمي.")
