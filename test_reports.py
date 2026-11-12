"""test_reports.py - اختبار نص التقرير اليومي ورابط واتساب (على قاعدة مؤقتة)"""
import os
import sys
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta

import config
import db
import reports

db.DB_PATH = "test_reports.db"
if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)
db.init_db()


def at(h, m, day=None):
    return datetime.combine(day or date.today(), dtime(h, m))


# بيانات: موظفين، لاعبين، دفعات
a = db.add_staff("أيمن", "", "مدرب")["device_uid"]
b = db.add_staff("بسام", "", "استقبال")["device_uid"]
db.record_attendance(a, at(8, 0)); db.record_attendance(a, at(17, 0))      # أيمن: 9 ساعات
db.record_attendance(b, at(9, 30))                                           # بسام: لسا موجود
m1 = db.add_member("لاعب 1", "1", "حديد", 30, 100, 100, gender="ذكر")
m2 = db.add_member("لاعبة 2", "2", "ايروبيك", 30, 60, 30, gender="أنثى")
db.renew_subscription(m1["member_id"], 30, 50, 50)
db.record_attendance(m1["device_uid"], at(10, 0)); db.record_attendance(m2["device_uid"], at(11, 0))
old = db.add_member("منتهي", "3", "حديد", 5, 10, 10, gender="ذكر")
with db.db() as c:
    c.execute("UPDATE subscriptions SET start_date='2020-01-01', end_date='2020-01-06' WHERE member_id=?", (old["member_id"],))
db.record_attendance(old["device_uid"], at(12, 0))

text = reports.build_report_text()
print(text)
assert f"تقرير {config.GYM_NAME} اليومي" in text and date.today().isoformat() in text
assert "• أيمن: دخول 08:00 | خروج 17:00 | مدة العمل 9:00" in text
assert "• بسام: دخول 09:30 | موجود الآن" in text
assert "عدد اللاعبين الحاضرين: 2" in text          # المنتهي ما انحسب حاضر
assert "بصمات باشتراك منتهي: 1" in text
assert "*الاشتراكات الجديدة (3)*" in text and "*التجديدات (1)*" in text
# كل واحد باسمه، أنواعه، كم دفع، وكم لسا عليه
assert "1. لاعب 1 — حديد 30 يوم\n   دفع 100 | مسدّد بالكامل" in text, text
assert "2. لاعبة 2 — ايروبيك 30 يوم\n   دفع 30 | متبقي عليه 30" in text, text
assert "1. لاعب 1 — حديد 30 يوم\n   دفع 50 | مسدّد بالكامل" in text           # بقسم التجديدات
assert "*تسديد دفعات من المتبقي (0)*\n• لا يوجد" in text
assert "*إجمالي الدفع اليوم: 190*" in text, text    # 100 + 30 + 50 (تجديد) + 10
assert text.index("*الحضور*") < text.index("*الاشتراكات الجديدة") < text.index("*التجديدات") \
    < text.index("*تسديد") < text.index("*إجمالي")                          # الترتيب المطلوب

# لاعب قديم (اشتراكه من أمس) بيسدد جزء، ولاعب جديد بنوعين
yday = (date.today() - timedelta(days=1)).isoformat() + " 09:00:00"
debtor = db.add_member("عليه دين", "7", "حديد", 30, 90, 30, gender="ذكر")
with db.db() as c:
    c.execute("UPDATE subscriptions SET created_at=? WHERE member_id=?", (yday, debtor["member_id"]))
    c.execute("UPDATE payments SET paid_at=? WHERE subscription_id IN (SELECT id FROM subscriptions WHERE member_id=?)", (yday, debtor["member_id"]))
db.pay_remaining(debtor["member_id"], 25)
db.add_member("نوعين", "8", gender="أنثى", subscriptions=[
    {"sub_type": "حديد", "days": 30, "price": 50, "paid": 50}, {"sub_type": "ايروبيك", "days": 10, "price": 20, "paid": 5}])
text2 = reports.build_report_text()
assert "*تسديد دفعات من المتبقي (1)*\n1. عليه دين — سدد 25 | متبقي عليه 35" in text2, text2           # 90 - 30 - 25
assert "حديد 30 يوم + ايروبيك 10 أيام" in text2 and "3. منتهي — حديد 5 أيام" in text2
assert "   دفع 55 | متبقي عليه 15" in text2
assert "*الاشتراكات الجديدة (4)*" in text2          # عليه دين اشتراكه أمس فما انحسب جديد اليوم
assert "*إجمالي الدفع اليوم: 270*" in text2, text2  # 190 + 25 + 55
print(text2)

# تقرير قسم واحد: بيشوف لاعبينه ودفعاتهم بس، وبيكتب اسم القسم
tm = reports.build_report_text(gender="ذكر"); tf = reports.build_report_text(gender="أنثى")
assert "القسم: شباب" in tm and "القسم: نساء" in tf and "القسم:" not in text2
assert "عليه دين" in tm and "عليه دين" not in tf and "نوعين" in tf and "نوعين" not in tm
assert "لاعبة 2" in tf and "لاعبة 2" not in tm and "لاعب 1 —" in tm and "لاعب 1 —" not in tf
assert "• أيمن:" in tm and "• أيمن:" in tf                                  # الموظفين بالتقريرين
assert "*إجمالي الدفع اليوم: 185*" in tm, tm                                 # شباب: 100 + 50 (تجديد) + 10 + 25 (تسديد عليه دين)
assert "*إجمالي الدفع اليوم: 85*" in tf, tf                                  # نساء: 30 + 55   (185 + 85 = 270 الإجمالي)
print("section reports ok")

# بعد تعيين العملة
config.CURRENCY = "دينار"
assert "*إجمالي الدفع اليوم: 270 دينار*" in reports.build_report_text()
assert "دفع 55 دينار | متبقي عليه 15 دينار" in reports.build_report_text()
config.CURRENCY = ""

# تقرير يوم فاضي + يوم أمس: الموظف اللي ما سجل خروج
empty = reports.build_report_text(date.today() - timedelta(days=30))
assert "لا يوجد حضور مسجّل" in empty and "عدد اللاعبين الحاضرين: 0" in empty and "*إجمالي الدفع اليوم: 0*" in empty
assert "*الاشتراكات الجديدة (0)*\n• لا يوجد" in empty
db.record_attendance(b, at(9, 0, date.today() - timedelta(days=1)))
assert "ما سجّل خروج" in reports.build_report_text(date.today() - timedelta(days=1))
print("report text ok")

# أرقام الهاتف
n = reports.normalize_phone
assert n("962791234567") == n("+962 79 123 4567") == n("00962-79-1234567") == n("٩٦٢٧٩١٢٣٤٥٦٧") == "962791234567"
for bad in ("0791234567", "123", "abc", "", "9627912345678901234"):
    try:
        n(bad); raise SystemExit(f"لازم يرفض: {bad}")
    except ValueError:
        pass
print("phone ok")

# رابط واتساب: بيرجع نفس النص لما نفك ترميزه (عربي + سطور جديدة + نجوم)
url = reports.whatsapp_url("962791234567", text)
assert url.startswith("https://web.whatsapp.com/send?phone=962791234567&text=")
q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
assert q["phone"] == ["962791234567"] and q["text"] == [text]
print("url ok, length", len(url))

# الإرسال التلقائي (Enter): بنختبر المنطق بنوافذ وهمية، مش ويندوز فعلي
assert reports.is_whatsapp_browser_title("WhatsApp - Google Chrome")
assert reports.is_whatsapp_browser_title("(3) WhatsApp - Google Chrome")
assert reports.is_whatsapp_browser_title("WhatsApp and 1 more page - Personal - Microsoft Edge")
assert reports.is_whatsapp_browser_title("WhatsApp — Mozilla Firefox")
assert not reports.is_whatsapp_browser_title("WhatsApp")                 # تطبيق واتساب للكمبيوتر: ممنوع
assert not reports.is_whatsapp_browser_title("Untitled - Notepad")
assert not reports.is_whatsapp_browser_title("")


class Sim:
    """ساعة وهمية + عناوين نوافذ بتتغير مع الوقت + تسجيل ضغطات Enter."""
    def __init__(self, titles):
        self.t, self.titles, self.presses, self.pastes, self.sleeps = 0, titles, [], [], []
    def now(self): return self.t
    def sleep(self, s): self.t += s; self.sleeps.append(s)
    def title(self):
        current = ""
        for start, name in self.titles:
            if self.t >= start: current = name
        return current
    def press(self): self.presses.append(self.t)
    def paste(self): self.pastes.append(self.t)
    def run(self, **kw):
        return reports.auto_press_enter(get_title=self.title, press=self.press, press_paste=self.paste,
                                        sleep=self.sleep, now=self.now, settle=15, gap=10, **kw)

# 1) المتصفح بيصير أمامي بعد 3 ثواني: بيضغط مرتين (بعد 15 ثانية تحميل، وبعدها بـ 10)
sim = Sim([(0, "Inbox - Mail"), (3, "WhatsApp - Google Chrome")])
ok, msg = sim.run(); assert ok and len(sim.presses) == 2 and sim.presses == [18, 28], (sim.presses, msg)
# 2) ما انفتح واتساب أبداً: ما بيضغط شي
sim = Sim([(0, "Inbox - Mail")]); ok, msg = sim.run(); assert not ok and sim.presses == [] and "ما لقيت" in msg
# 3) تطبيق واتساب للكمبيوتر بالمقدمة (مش المتصفح): ما بيضغط
sim = Sim([(0, "WhatsApp")]); ok, msg = sim.run(); assert not ok and sim.presses == []
# 4) المستخدم بدّل لنافذة ثانية قبل الضغطة الأولى: ما بيضغط شي
sim = Sim([(0, "WhatsApp - Google Chrome"), (5, "Document1 - Word")]); ok, msg = sim.run()
assert not ok and sim.presses == [] and "تغيّرت" in msg
# 5) بدّل بعد الضغطة الأولى: بيضغط مرة وحدة بس وبيعتبرها نجحت
sim = Sim([(0, "WhatsApp - Google Chrome"), (20, "Document1 - Word")]); ok, msg = sim.run()
assert ok and len(sim.presses) == 1
# 6) على لينكس/ماك بيرفض فوراً بدون انتظار
assert reports.auto_press_enter()[0] is False or sys.platform.startswith("win")
# 7) وضع اللصق (تقرير طويل): لصق مرة وحدة بعد التحميل، وبعدها Enter مرتين، واللصق ما بيتكرر أبداً
sim = Sim([(0, "Inbox - Mail"), (3, "WhatsApp - Google Chrome")])
ok, msg = sim.run(paste=True)
assert ok and sim.pastes == [18] and sim.presses == [20, 30] and "لصق" in msg, (sim.pastes, sim.presses, msg)
# 8) وضع اللصق: المستخدم بدّل نافذة قبل اللصق -> ما بيلصق ولا بيضغط شي
sim = Sim([(0, "WhatsApp - Google Chrome"), (5, "Document1 - Word")]); ok, msg = sim.run(paste=True)
assert not ok and sim.pastes == [] and sim.presses == [] and "اللصق" in msg
# 9) وضع اللصق: تطبيق واتساب للكمبيوتر مش المتصفح -> ممنوع
sim = Sim([(0, "WhatsApp")]); ok, msg = sim.run(paste=True); assert not ok and sim.pastes == [] and sim.presses == []
# 10) تقرير قصير بيروح بالرابط، وطويل بيروح بوضع اللصق (والرابط ما بيحمل النص)
short, long_text = "تقرير قصير", "سطر طويل جداً\n" * 400
assert reports.send_mode("962791234567", short) == "prefill"
assert reports.send_mode("962791234567", long_text) == "paste"
old_limit = config.WHATSAPP_MAX_URL
config.WHATSAPP_MAX_URL = 100000; assert reports.send_mode("962791234567", long_text) == "prefill"   # بتقدر ترفع الحد من config.json
config.WHATSAPP_MAX_URL = old_limit
import webbrowser
seen = []; webbrowser.open = lambda url: (seen.append(url), True)[1]
opened, url, mode = reports.open_whatsapp("962791234567", long_text); assert opened and mode == "paste"
assert url == "https://web.whatsapp.com/send?phone=962791234567" and "text=" not in url
opened, url, mode = reports.open_whatsapp("962791234567", short); assert mode == "prefill" and "text=" in url
print("auto-send logic ok")

os.remove(db.DB_PATH)
print("\nكل اختبارات التقرير نجحت ✅")
