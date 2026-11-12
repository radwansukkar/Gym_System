"""test_db.py - اختبار db.py على قاعدة مؤقتة (ما بيلمس gym.db الحقيقية)"""
import os
import db

db.DB_PATH = "test_gym.db"
db.BACKUP_DIR = "test_backups"       # مجلد مؤقت، مش backups الحقيقي
if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)
db.init_db()

# 1) لاعب جديد: سعر 100، دفع 60 فقط
r = db.add_member("أحمد علي", "0791234567", "حديد", days=30, price=100, paid=60)
print("1) new member:", r)
m = db.get_member(r["member_id"])
print("   days_left =", m["days_left"], "| remaining =", m["remaining"])
assert m["days_left"] == 30 and m["remaining"] == 40

# 2) دفع المتبقي
db.pay_remaining(r["member_id"], 40)
assert db.get_member(r["member_id"])["remaining"] == 0
print("2) remaining paid OK")

# 3) تجديد وهو لسا ساري: لازم يكمل بعد الانتهاء
db.renew_subscription(r["member_id"], days=30, price=100, paid=100)
m = db.get_member(r["member_id"])
print("3) after renew days_left =", m["days_left"])
assert m["days_left"] == 60

# 4) موظف
s = db.add_staff("خالد", "0780000000", "مدرب")
print("4) staff:", s)

# 5) حضور: لاعب، موظف، بصمة مكررة، بصمة مجهولة
print("5) member scan :", db.record_attendance(r["device_uid"]))
print("   staff scan  :", db.record_attendance(s["device_uid"]))
dup = db.record_attendance(r["device_uid"])
print("   duplicate   :", dup["duplicate"])
assert dup["duplicate"] is True
print("   unknown scan:", db.record_attendance(999)["status"])

# 6) لاعب بدون دفع (اشتراك ساري)، بحث
db.add_member("سامي حسن", "0795555555", "بوكسينج", days=10, price=50, paid=0)
print("6) search 'سامي':", [x["name"] for x in db.search_members("سامي")])

# 7) تقرير اليوم
print("7) report:", db.daily_report())

# 8) نسخة احتياطية
print("8) backup:", db.backup_db())

# 8b) حذف النسخ القديمة: بنحتفظ بآخر BACKUP_KEEP بس
import glob
db.BACKUP_KEEP = 3
for i in range(1, 8):
    open(os.path.join(db.BACKUP_DIR, f"gym_2020-01-0{i}.db"), "w").close()
db.backup_db()
left = sorted(os.path.basename(p) for p in glob.glob(os.path.join(db.BACKUP_DIR, "gym_*.db")))
assert len(left) == 3 and left[-1] == f"gym_{db._today().isoformat()}.db", left
print("8b) backups pruned:", left)
import shutil; shutil.rmtree(db.BACKUP_DIR)

# 8c) الإعدادات العامة
assert db.get_setting("owner_phone") is None and db.get_setting("owner_phone", "x") == "x"
db.set_setting("owner_phone", "962791234567"); db.set_setting("owner_phone", "962790000000")
assert db.get_setting("owner_phone") == "962790000000"
print("8c) settings ok")

# 9) الجنس
g = db.add_member("سارة محمد", "0796", "ايروبيك", days=30, price=60, paid=60, gender="أنثى")
assert db.get_member(g["member_id"])["gender"] == "أنثى"
try:
    db.add_member("خطأ", "", "حديد", days=1, price=1, paid=1, gender="غير ذلك")
    raise SystemExit("لازم يرفض جنس غير صحيح")
except ValueError:
    pass
print("9) gender ok, old members without gender:", db.get_member(r["member_id"])["gender"])

# 9b) فلترة الأقسام: كل قسم بيشوف أسماء قسمه بس
db.add_member("عمر", "0797", "حديد", days=30, price=40, paid=40, gender="ذكر")
males = [x["name"] for x in db.search_members("", gender="ذكر")]
females = [x["name"] for x in db.search_members("", gender="أنثى")]
print("9b) males:", males, "| females:", females)
assert "سارة محمد" in females and "سارة محمد" not in males
assert "عمر" in males and "عمر" not in females
assert db.search_members("سارة", gender="ذكر") == []

# 9c) كلمات سر الأقسام
assert db.has_gender_password("ذكر") is False
db.set_gender_password("ذكر", "1234")
assert db.has_gender_password("ذكر") and db.check_gender_password("ذكر", "1234")
assert not db.check_gender_password("ذكر", "9999") and not db.check_gender_password("أنثى", "1234")
for bad in (lambda: db.set_gender_password("ذكر", "5678", old_password="0000"),   # قديمة غلط
            lambda: db.set_gender_password("ذكر", "12"),                          # قصيرة
            lambda: db.set_gender_password("غير", "1234")):                       # قسم غلط
    try:
        bad(); raise SystemExit("لازم يرفض")
    except ValueError:
        pass
db.set_gender_password("ذكر", "5678", old_password="1234")
assert db.check_gender_password("ذكر", "5678") and not db.check_gender_password("ذكر", "1234")
with db.db() as c:
    stored = c.execute("SELECT value FROM settings WHERE key='password:ذكر'").fetchone()[0]
assert "5678" not in stored and stored.count("$") == 2        # مشفرة مش نص عادي
db.clear_gender_password("ذكر")
assert not db.has_gender_password("ذكر")
print("9c) passwords ok")

# 9d) تجديد مع دفعة على المتبقي القديم (بنفس العملية)
p = db.add_member("باسل", "0798", "حديد", days=30, price=100, paid=20, gender="ذكر")["member_id"]
assert db.get_member(p)["remaining"] == 80
db.renew_subscription(p, days=30, price=50, paid=50, pay_old=30)
assert db.get_member(p)["remaining"] == 50 and len(db.member_history(p)) == 2
try:                                    # دفعة أكبر من المتبقي القديم: لازم يرفض وما يتغير شي
    db.renew_subscription(p, days=30, price=50, paid=50, pay_old=999)
    raise SystemExit("لازم يرفض")
except ValueError:
    pass
assert db.get_member(p)["remaining"] == 50 and len(db.member_history(p)) == 2
print("9d) renew + pay_old ok (rollback on error)")

# 9e) دخول وخروج الموظفين
from datetime import datetime, time as dtime
def at(h, m): return datetime.combine(db._today(), dtime(h, m))
nour = db.add_staff("نور", "", "مدرب")["device_uid"]
ramy = db.add_staff("رامي", "", "استقبال")["device_uid"]
r1 = db.record_attendance(nour, at(8, 0));  assert r1["direction"] == "in"
r2 = db.record_attendance(nour, at(8, 1));  assert r2["duplicate"] and r2["direction"] == "in"
r3 = db.record_attendance(nour, at(12, 0)); assert r3["direction"] == "out" and r3["worked_minutes"] == 240
r4 = db.record_attendance(nour, at(12, 30)); assert r4["direction"] == "in"
r5 = db.record_attendance(nour, at(17, 0)); assert r5["direction"] == "out" and r5["worked_minutes"] == 510
db.record_attendance(ramy, at(9, 0))
rep = {x["name"]: x for x in db.daily_report()["staff"]}
assert rep["نور"]["first_in"] == "08:00" and rep["نور"]["last_out"] == "17:00"
assert rep["نور"]["worked_minutes"] == 510 and rep["نور"]["still_in"] is False
assert rep["رامي"]["still_in"] is True and rep["رامي"]["last_out"] is None
print("9e) staff in/out ok:", rep["نور"])

# 9f) شاشات الموظفين: حالة اليوم، السجل، التعديل، الإيقاف
today = {x["name"]: x for x in db.staff_today()}
assert today["نور"]["state"] == "out" and today["رامي"]["state"] == "in"
assert today["خالد"]["state"] == "in"
lazy = db.add_staff("كسول", "", "نظافة")
assert {x["name"]: x for x in db.staff_today()}["كسول"]["state"] == "absent"
nour_id = [x for x in db.list_staff() if x["name"] == "نور"][0]["id"]
hist = db.staff_history(nour_id)
assert len(hist) == 1 and hist[0]["worked_minutes"] == 510 and hist[0]["date"] == db._today().isoformat()
db.update_staff(nour_id, "نور الدين", "0780001", "مدرب أول")
assert db.get_staff(nour_id)["name"] == "نور الدين" and db.get_staff(nour_id)["job_title"] == "مدرب أول"
try:
    db.update_staff(nour_id, "  ")
    raise SystemExit("لازم يرفض اسم فاضي")
except ValueError:
    pass
db.deactivate_staff(lazy["staff_id"])
assert "كسول" not in [x["name"] for x in db.staff_today()]
assert db.record_attendance(lazy["device_uid"])["kind"] == "unknown"      # بصمة موظف موقوف = غير معروفة
print("9f) staff screens data ok")

# 9g) أرقام الجهاز: الموظفين 1-99، واللاعبين من 100، وتجنب أرقام الجهاز (الأدمن)
staff_uids = sorted(x["device_uid"] for x in db.list_staff(active_only=False))
member_uids = sorted(x["device_uid"] for x in db.search_members(""))
assert all(1 <= u <= 99 for u in staff_uids) and all(u >= 100 for u in member_uids)
assert staff_uids == list(range(1, len(staff_uids) + 1))                     # متسلسلة من 1
assert db.peek_next_staff_uid() == len(staff_uids) + 1
free = db.peek_next_staff_uid()
assert db.peek_next_staff_uid({free}) == free + 1                       # الأدمن على نفس الرقم: بيتخطاه
assert db.peek_next_device_uid() == max(member_uids) + 1 and db.peek_next_device_uid({5000}) == 5001
try:
    db.peek_next_staff_uid(set(range(1, 100)))
    raise SystemExit("لازم يرفض لما تمتلي الأرقام")
except ValueError:
    pass
print("9g) device numbers ok: staff", staff_uids[:4], "... members from", member_uids[0])

# 9h) أكثر من نوع اشتراك للاعب الواحد، لكل نوع مدته
def nmembers(): return len(db.search_members(""))
before_new = db.daily_report()["new_subscriptions"]
two = db.add_member("متعدد", "0700", gender="ذكر", subscriptions=[
    {"sub_type": "ايروبيك", "days": 10, "price": 30, "paid": 10},
    {"sub_type": "حديد", "days": 30, "price": 50, "paid": 50}])
st = db.get_member(two["member_id"])
assert [x["sub_type"] for x in st["subs"]] == ["حديد", "ايروبيك"]                    # بترتيب الأنواع المعروف
assert st["sub_type"] == "حديد + ايروبيك" and st["days_left"] == 30 and st["min_days_left"] == 10
assert st["remaining"] == 20 and st["active"]
assert db.daily_report()["new_subscriptions"] == before_new + 1                       # لاعب واحد مش اشتراكين
# أي خطأ بأي نوع بيلغي العملية كلها (ما بينحفظ لاعب ناقص)
n0 = nmembers()
for bad in ([{"sub_type": "حديد", "days": 30, "price": 50, "paid": 50}, {"sub_type": "حديد", "days": 5, "price": 5, "paid": 5}],
            [{"sub_type": "حديد", "days": 30, "price": 50, "paid": 50}, {"sub_type": "ايروبيك", "days": 5, "price": 5, "paid": 99}],
            []):
    try:
        db.add_member("ما بينحفظ", "", gender="ذكر", subscriptions=bad); raise SystemExit("لازم يرفض")
    except ValueError:
        pass
assert nmembers() == n0
# إضافة نوع جديد للاعب عنده حديد بس
solo = db.add_member("حديد بس", "0701", "حديد", 30, 40, 40, gender="ذكر")["member_id"]
res = db.renew_subscription(solo, days=15, price=20, paid=20, sub_type="ايروبيك")
assert res["is_renewal"] is False and res["sub_type"] == "ايروبيك"
st = db.get_member(solo); days = {x["sub_type"]: x["days_left"] for x in st["subs"]}
assert days == {"حديد": 30, "ايروبيك": 15}, days
# تجديد نفس النوع وهو ساري: بيكمل بعده، والنوع الثاني ما بيتأثر
res = db.renew_subscription(solo, days=30, price=40, paid=40, sub_type="حديد")
assert res["is_renewal"] is True
days = {x["sub_type"]: x["days_left"] for x in db.get_member(solo)["subs"]}
assert days == {"حديد": 60, "ايروبيك": 15}, days
# نوع واحد انتهى والثاني ساري: بيقدر يدخل، والنوع المنتهي بيبين منتهي
with db.db() as c:
    c.execute("UPDATE subscriptions SET start_date='2020-01-01', end_date='2020-02-01' "
              "WHERE member_id=? AND sub_type='حديد'", (solo,))
st = db.get_member(solo)
assert st["active"] and st["sub_type"] == "ايروبيك" and [x["active"] for x in st["subs"]] == [True, False]
r = db.record_attendance(db.get_member(solo)["device_uid"], at(15, 0))
assert r["status"] == "ok" and r["min_days_left"] == 15 and {x["sub_type"]: x["active"] for x in r["subs"]} == {"ايروبيك": True, "حديد": False}
# كل الأنواع انتهت: ممنوع الدخول
with db.db() as c:
    c.execute("UPDATE subscriptions SET start_date='2020-01-01', end_date='2020-02-01' WHERE member_id=?", (solo,))
st = db.get_member(solo)
assert not st["active"] and st["days_left"] == 0
assert db.record_attendance(st["device_uid"], at(16, 0))["status"] == "expired"
# تجديد نوع منتهي: بيبدأ من اليوم
db.renew_subscription(solo, days=20, price=10, paid=10, sub_type="حديد")
assert {x["sub_type"]: x["days_left"] for x in db.get_member(solo)["subs"]}["حديد"] == 20
print("9h) multiple subscription types ok")

# 9i) كلمات سر التقرير والموظفين (مستقلة عن الأقسام)
for scope in ("report", "staff"):
    assert not db.has_password(scope)
db.set_password("report", "rep1"); db.set_password("staff", "stf2")
assert db.check_password("report", "rep1") and not db.check_password("report", "stf2")
assert db.check_password("staff", "stf2") and not db.check_password("staff", "rep1")
assert not db.has_password("ذكر")                                     # كلمات الأقسام ما تأثرت
try:
    db.set_password("report", "new1", old_password="غلط"); raise SystemExit("لازم يرفض")
except ValueError:
    pass
try:
    db.set_password("other", "abcd"); raise SystemExit("لازم يرفض اسم غلط")
except ValueError:
    pass
db.set_password("report", "rep9", old_password="rep1"); assert db.check_password("report", "rep9")
db.clear_password("report"); assert not db.has_password("report") and db.has_password("staff")
print("9i) report/staff passwords ok")

# 9j) تفاصيل التقرير اليومي: مين اشترك وجدد وسدد، وكم دفع وكم لسا عليه
from datetime import timedelta
yday = (db._today() - timedelta(days=1)).isoformat() + " 10:00:00"
old_b = db.add_member("بائع قديم", "0900", subscriptions=[{"sub_type": "حديد", "days": 30, "price": 100, "paid": 40}], gender="ذكر")
old_c = db.add_member("مسدد", "0901", "ايروبيك", 30, 80, 20, gender="أنثى")
with db.db() as c:                         # بنرجّع اشتراكاتهم ودفعاتهم لأمس
    for mid in (old_b["member_id"], old_c["member_id"]):
        c.execute("UPDATE subscriptions SET created_at=? WHERE member_id=?", (yday, mid))
        c.execute("UPDATE payments SET paid_at=? WHERE subscription_id IN "
                  "(SELECT id FROM subscriptions WHERE member_id=?)", (yday, mid))
total_before = db.daily_report()["total_paid"]
db.renew_subscription(old_b["member_id"], 30, 50, 30, sub_type="حديد", pay_old=25)   # جدد + سدد 25 من القديم
db.pay_remaining(old_c["member_id"], 20)                                            # سدد بس
nd = db.add_member("جديد اليوم", "0902", gender="ذكر", subscriptions=[
    {"sub_type": "حديد", "days": 30, "price": 50, "paid": 50},
    {"sub_type": "بوكسينج", "days": 10, "price": 20, "paid": 5}])
rep = db.daily_report()
new = {p["name"]: p for p in rep["new_members"]}
ren = {p["name"]: p for p in rep["renewed_members"]}
sett = {p["name"]: p for p in rep["settlements"]}
p = new["جديد اليوم"]
assert p["paid"] == 55 and p["remaining"] == 15 and [x["sub_type"] for x in p["subs"]] == ["حديد", "بوكسينج"]
assert [x["days"] for x in p["subs"]] == [30, 10]
assert ren["بائع قديم"]["paid"] == 30 and ren["بائع قديم"]["remaining"] == 55         # 60 - 25 + 20
assert sett["بائع قديم"]["paid"] == 25 and sett["بائع قديم"]["remaining"] == 55
assert sett["مسدد"]["paid"] == 20 and sett["مسدد"]["remaining"] == 40
assert "مسدد" not in new and "مسدد" not in ren and "بائع قديم" not in new
assert rep["new_subscriptions"] == len(rep["new_members"]) and rep["renewals"] == len(rep["renewed_members"])
assert rep["total_paid"] - total_before == 30 + 25 + 20 + 55
# تقرير أمس: المتبقي كان وقتها (مش اليوم)
yrep = db.daily_report(db._today() - timedelta(days=1))
yn = {p["name"]: p for p in yrep["new_members"]}
assert yn["بائع قديم"]["paid"] == 40 and yn["بائع قديم"]["remaining"] == 60 and yn["مسدد"]["remaining"] == 60
assert yrep["settlements"] == [] and yrep["renewed_members"] == []
print("9j) daily report details ok")

# 9k) تعديل بيانات اللاعب ومدة اشتراكه
em = db.add_member("قبل التعديل", "000", gender="ذكر", subscriptions=[
    {"sub_type": "حديد", "days": 30, "price": 50, "paid": 50},
    {"sub_type": "ايروبيك", "days": 10, "price": 30, "paid": 30}])["member_id"]
db.update_member(em, " بعد التعديل ", " 0799 ")
g = db.get_member(em)
assert g["name"] == "بعد التعديل" and g["phone"] == "0799" and g["gender"] == "ذكر"        # الجنس ما بيتغير
for bad in (lambda: db.update_member(em, "  "), lambda: db.update_member(999999, "x")):
    try:
        bad(); raise SystemExit("لازم يرفض")
    except ValueError:
        pass
sid = {x["sub_type"]: x["sub_id"] for x in g["subs"]}
r = db.update_subscription_days(sid["حديد"], 45)
assert r["days"] == 45 and r["days_left"] == 45
days = {x["sub_type"]: x["days_left"] for x in db.get_member(em)["subs"]}
assert days == {"حديد": 45, "ايروبيك": 10}, days                                           # النوع الثاني ما تأثر
assert db.update_subscription_days(sid["ايروبيك"], 1)["days_left"] == 1
assert db.get_member(em)["remaining"] == 0                                                 # الدفع ما تأثر
for bad_days in (0, -3):
    try:
        db.update_subscription_days(sid["حديد"], bad_days); raise SystemExit("لازم يرفض")
    except ValueError:
        pass
# بعد تجديد نفس النوع: بس آخر اشتراك بيتعدّل (الأقدم بيلخبط السلسلة)
db.renew_subscription(em, 30, 40, 40, sub_type="حديد")
newest = {x["sub_type"]: x["sub_id"] for x in db.get_member(em)["subs"]}["حديد"]
assert newest != sid["حديد"]
try:
    db.update_subscription_days(sid["حديد"], 5); raise SystemExit("لازم يرفض تعديل اشتراك قديم")
except ValueError as e:
    assert "آخر اشتراك" in str(e)
assert db.update_subscription_days(newest, 10)["days"] == 10
try:
    db.update_subscription_days(999999, 5); raise SystemExit("لازم يرفض")
except ValueError:
    pass
print("9k) edit member + subscription duration ok")

# 9l) تقرير القسم: كل قسم بيشوف لاعبينه ودفعاتهم بس
def totals(): return db.daily_report(gender="ذكر"), db.daily_report(gender="أنثى"), db.daily_report()
m0, f0, a0 = totals()
rm = db.add_member("رجل تقرير", "1", "حديد", 30, 10, 10, gender="ذكر")
rf = db.add_member("سيدة تقرير", "2", "ايروبيك", 30, 25, 20, gender="أنثى")
db.record_attendance(rm["device_uid"], at(18, 0)); db.record_attendance(rf["device_uid"], at(18, 5))
m1, f1, a1 = totals()
assert m1["total_paid"] - m0["total_paid"] == 10 and f1["total_paid"] - f0["total_paid"] == 20
assert a1["total_paid"] - a0["total_paid"] == 30
assert m1["members_attended"] - m0["members_attended"] == 1 and f1["members_attended"] - f0["members_attended"] == 1
names_m = [p["name"] for p in m1["new_members"]]; names_f = [p["name"] for p in f1["new_members"]]
assert "رجل تقرير" in names_m and "سيدة تقرير" not in names_m
assert "سيدة تقرير" in names_f and "رجل تقرير" not in names_f
assert m1["new_subscriptions"] == len(m1["new_members"]) and f1["renewals"] == len(f1["renewed_members"])
assert m1["staff"] == a1["staff"] == f1["staff"]                                           # الموظفين بكل الأحوال
print("9l) gender-scoped report ok")

# 10) ترقية قاعدة بيانات قديمة (بدون عمود gender)
import sqlite3
old_db = "test_old.db"
if os.path.exists(old_db):
    os.remove(old_db)
con = sqlite3.connect(old_db)
con.executescript(db.SCHEMA.replace("    gender      TEXT,\n", "").replace(",\n    direction   TEXT", ""))
con.execute("INSERT INTO members (name, phone, device_uid, created_at) VALUES ('قديم','1',100,'2026-01-01 00:00:00')")
con.commit(); con.close()
db.DB_PATH = old_db
db.init_db()
assert db.search_members("قديم")[0]["gender"] is None
legacy_staff = db.add_staff("قديم", "", "")["device_uid"]
assert db.record_attendance(legacy_staff)["direction"] == "in"     # عمود direction انضاف
print("10) migration ok")
os.remove(old_db)

os.remove("test_gym.db")
print("\nكل الاختبارات نجحت ✅")
