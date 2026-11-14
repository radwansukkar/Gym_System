"""db.py - قاعدة بيانات نظام الجيم (SQLite)

ملاحظات التصميم:
- end_date حصري: اشتراك 30 يوم يبدأ اليوم، آخر يوم فيه = اليوم + 29.
  days_left = end_date - اليوم، والاشتراك ساري إذا days_left > 0.
- device_uid: رقم المستخدم على جهاز البصمة. الموظفين من 1 لـ 99، واللاعبين من 100 وطالع،
  فما في تعارض بينهم. والتخصيص بيتجنب أرقام موجودة أصلاً على الجهاز (مثل الأدمن).
- الدفع: لكل اشتراك سعر كلي (price) ودفعات (payments)، والمتبقي = السعر - المدفوع.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import config

DB_PATH = os.path.join(config.APP_DIR, "gym.db")         # جنب البرنامج دايماً (مش حسب مكان التشغيل)
BACKUP_DIR = os.path.join(config.APP_DIR, "backups")
BACKUP_KEEP = 30              # بنحتفظ بآخر 30 نسخة احتياطية
DUPLICATE_WINDOW_MIN = 5      # بصمتين خلال هالمدة = حضور واحد
FIRST_DEVICE_UID = 100       # أرقام اللاعبين على الجهاز من هون وطالع
STAFF_UID_FIRST = 1          # أرقام الموظفين على الجهاز: من 1 لـ 99
STAFF_UID_LAST = 99
SUB_TYPES = ("حديد", "ايروبيك", "بوكسينج")
GENDERS = ("ذكر", "أنثى")
SECTION_NAMES = {"ذكر": "شباب", "أنثى": "نساء"}   # أسماء القسمين بالواجهة والتقرير
PASSWORD_SCOPES = GENDERS + ("report", "staff")   # كلمة سر: شباب، نساء، التقرير اليومي، الموظفين
STAFF_DUPLICATE_WINDOW_MIN = 2   # بصمتين للموظف خلال هالمدة = بصمة وحدة (مش دخول ثم خروج)
PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD_LEN = 4


# ---------------------------------------------------------------- اتصال
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now():
    return datetime.now().replace(microsecond=0)


def _today():
    return date.today()


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    gender      TEXT,
    device_uid  INTEGER NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES members(id),
    sub_type    TEXT NOT NULL,
    start_date  TEXT NOT NULL,
    days        INTEGER NOT NULL,
    end_date    TEXT NOT NULL,
    price       REAL NOT NULL,
    is_renewal  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id),
    amount          REAL NOT NULL,
    paid_at         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    job_title   TEXT,
    device_uid  INTEGER NOT NULL UNIQUE,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_type TEXT NOT NULL CHECK (person_type IN ('member','staff','unknown')),
    person_id   INTEGER,
    device_uid  INTEGER NOT NULL,
    scanned_at  TEXT NOT NULL,
    scan_date   TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ok','expired','unknown')),
    direction   TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_att_date   ON attendance(scan_date);
CREATE INDEX IF NOT EXISTS idx_att_uid    ON attendance(device_uid);
CREATE INDEX IF NOT EXISTS idx_members_nm ON members(name);
CREATE INDEX IF NOT EXISTS idx_subs_member ON subscriptions(member_id);
"""


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        # ترقية قواعد البيانات القديمة (اللي انعملت قبل إضافة الجنس)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(members)")]
        if "gender" not in cols:
            conn.execute("ALTER TABLE members ADD COLUMN gender TEXT")
        att_cols = [r["name"] for r in conn.execute("PRAGMA table_info(attendance)")]
        if "direction" not in att_cols:
            conn.execute("ALTER TABLE attendance ADD COLUMN direction TEXT")


# ---------------------------------------------------------------- كلمات السر
# كلمة سر لكل جزء محمي (scope): "ذكر" (شباب) / "أنثى" (نساء) / "report" (التقرير) / "staff" (الموظفين).
# بتتخزن مشفّرة (PBKDF2 مع salt) مش نص عادي.
def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_hash(password, stored):
    try:
        iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def _pw_key(scope):
    if scope not in PASSWORD_SCOPES:
        raise ValueError("القسم غير معروف")
    return f"password:{scope}"


def has_password(scope):
    with db() as conn:
        return conn.execute("SELECT 1 FROM settings WHERE key=?", (_pw_key(scope),)).fetchone() is not None


def check_password(scope, password):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (_pw_key(scope),)).fetchone()
    return bool(row) and _verify_hash(password, row["value"])


def set_password(scope, new_password, old_password=None):
    """
    أول مرة (ما في كلمة سر) بتنحط مباشرة. إذا في وحدة قديمة لازم تنعطى الحالية لتغييرها.
    """
    if len(new_password) < MIN_PASSWORD_LEN:
        raise ValueError(f"كلمة السر لازم تكون {MIN_PASSWORD_LEN} أحرف أو أرقام على الأقل")
    if has_password(scope) and not check_password(scope, old_password or ""):
        raise ValueError("كلمة السر الحالية غير صحيحة")
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (_pw_key(scope), _hash_password(new_password)))


def admin_set_password(scope, new_password):
    """
    تعيين كلمة سر جديدة بدون طلب القديمة (لما حدا ينساها). بيستخدمها المالك بأداة
    reset_passwords_gui.py بس. كلمات السر مخزنة بشكل ما بينفع يرجع منه النص الأصلي،
    فما في طريقة "نعرفها"، بس بنقدر نستبدلها.
    """
    if len(new_password) < MIN_PASSWORD_LEN:
        raise ValueError(f"كلمة السر لازم تكون {MIN_PASSWORD_LEN} أحرف أو أرقام على الأقل")
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (_pw_key(scope), _hash_password(new_password)))


def clear_password(scope):
    """مسح كلمة سر (لمن حدا ينساها). بيستخدمها reset_passwords.py بس."""
    with db() as conn:
        conn.execute("DELETE FROM settings WHERE key=?", (_pw_key(scope),))


# أسماء قديمة (كانت للأقسام بس) بنخليها شغالة
has_gender_password = has_password
check_gender_password = check_password
set_gender_password = set_password
clear_gender_password = clear_password


# ---------------------------------------------------------------- أدوات داخلية
def _next_device_uid(conn, taken=()):
    """رقم اللاعب التالي (من 100 وطالع). taken = أرقام مستخدمة على الجهاز مش مسجلة بالقاعدة."""
    row = conn.execute(
        "SELECT MAX(m) FROM (SELECT MAX(device_uid) AS m FROM members "
        "UNION ALL SELECT MAX(device_uid) FROM staff)"
    ).fetchone()
    current = max([row[0] or 0, *taken])
    return max(current, FIRST_DEVICE_UID - 1) + 1


def _next_staff_uid(conn, taken=()):
    """أصغر رقم فاضي للموظف بين 1 و99، بيتجنب أرقام القاعدة وأرقام الجهاز (taken) مثل الأدمن."""
    used = {r[0] for r in conn.execute("SELECT device_uid FROM staff")} | set(taken)
    for uid in range(STAFF_UID_FIRST, STAFF_UID_LAST + 1):
        if uid not in used:
            return uid
    raise ValueError(f"امتلأت أرقام الموظفين ({STAFF_UID_FIRST} - {STAFF_UID_LAST})")


def _check_money(price, paid):
    if price < 0 or paid < 0:
        raise ValueError("المبالغ لا يمكن أن تكون سالبة")
    if paid > price:
        raise ValueError("المدفوع أكبر من سعر الاشتراك")


def _add_subscription(conn, member_id, sub_type, days, price, paid):
    """
    يضيف اشتراك من نوع معين. لكل نوع تاريخ انتهاء مستقل: إذا اللاعب عنده نفس النوع وهو لسا ساري
    بيكمل بعده، وإلا بيبدأ من اليوم. is_renewal = اللاعب كان عنده هالنوع من قبل.
    """
    if sub_type not in SUB_TYPES:
        raise ValueError("نوع الاشتراك غير صحيح")
    if days <= 0:
        raise ValueError("المدة لازم تكون أكبر من صفر")
    _check_money(price, paid)

    today = _today()
    last = conn.execute(
        "SELECT end_date FROM subscriptions WHERE member_id=? AND sub_type=? "
        "ORDER BY end_date DESC, id DESC LIMIT 1", (member_id, sub_type)
    ).fetchone()
    start = today
    if last and date.fromisoformat(last["end_date"]) > today:
        start = date.fromisoformat(last["end_date"])        # لسا ساري: التجديد بيكمل بعده
    end = start + timedelta(days=days)
    is_renewal = last is not None

    cur = conn.execute(
        "INSERT INTO subscriptions (member_id, sub_type, start_date, days, end_date, "
        "price, is_renewal, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (member_id, sub_type, start.isoformat(), days, end.isoformat(),
         price, int(is_renewal), _now().isoformat(sep=" ")),
    )
    sub_id = cur.lastrowid
    if paid > 0:
        conn.execute(
            "INSERT INTO payments (subscription_id, amount, paid_at) VALUES (?,?,?)",
            (sub_id, paid, _now().isoformat(sep=" ")),
        )
    return sub_id, start, end, is_renewal


def _member_status(conn, m):
    """
    حالة اللاعب. اللاعب ممكن يكون مشترك بأكثر من نوع (حديد + ايروبيك...) ولكل نوع مدته.
    subs: آخر اشتراك لكل نوع [{sub_type, start_date, end_date, last_day, days_left, active}]
    active: في نوع واحد ساري على الأقل (يعني بيقدر يدخل).
    days_left / min_days_left: أكبر / أصغر عدد أيام متبقية بين الأنواع السارية.
    sub_type: الأنواع السارية مفصولة بـ " + " (أو آخر نوع إذا كلها منتهية).
    """
    rows = conn.execute(
        "SELECT * FROM subscriptions WHERE member_id=? ORDER BY end_date DESC, id DESC", (m["id"],)
    ).fetchall()
    total = conn.execute(
        "SELECT COALESCE(SUM(price),0) FROM subscriptions WHERE member_id=?", (m["id"],)
    ).fetchone()[0]
    paid = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN subscriptions s ON s.id=p.subscription_id WHERE s.member_id=?", (m["id"],)
    ).fetchone()[0]

    today = _today()
    latest = {}
    for r in rows:                       # الأحدث أول، فأول واحد بنشوفه من كل نوع هو آخر اشتراك فيه
        latest.setdefault(r["sub_type"], r)
    subs = []
    for sub_type, r in latest.items():
        end = date.fromisoformat(r["end_date"])
        left = (end - today).days
        subs.append({"sub_id": r["id"], "sub_type": sub_type, "start_date": r["start_date"],
                     "end_date": r["end_date"],
                     "last_day": (end - timedelta(days=1)).isoformat(),
                     "days_left": max(left, 0), "active": left > 0})
    order = {t: i for i, t in enumerate(SUB_TYPES)}
    subs.sort(key=lambda x: (not x["active"], order.get(x["sub_type"], 99)))
    active = [x for x in subs if x["active"]]

    info = {
        "id": m["id"], "name": m["name"], "phone": m["phone"], "gender": m["gender"],
        "device_uid": m["device_uid"], "created_at": m["created_at"],
        "subs": subs, "sub_type": None, "start_date": None, "end_date": None,
        "days_left": 0, "min_days_left": 0, "active": bool(active),
        "total_price": total, "total_paid": paid, "remaining": total - paid,
    }
    if active:
        main = max(active, key=lambda x: x["end_date"])
        info.update(sub_type=" + ".join(x["sub_type"] for x in active),
                    start_date=main["start_date"], end_date=main["end_date"],
                    days_left=max(x["days_left"] for x in active),
                    min_days_left=min(x["days_left"] for x in active))
    elif rows:
        r = rows[0]                      # أحدث اشتراك (كلها منتهية)
        info.update(sub_type=r["sub_type"], start_date=r["start_date"], end_date=r["end_date"])
    return info


# ---------------------------------------------------------------- اللاعبين
def peek_next_device_uid(taken=()):
    """
    رقم اللاعب التالي على الجهاز (بدون حجزه). نستخدمه لتسجيل البصمة قبل حفظ اللاعب.
    taken: أرقام المستخدمين الموجودين فعلاً على الجهاز (من device.device_users()).
    """
    with db() as conn:
        return _next_device_uid(conn, taken)


def peek_next_staff_uid(taken=()):
    """رقم الموظف التالي على الجهاز (1 - 99) بدون حجزه. taken متل فوق."""
    with db() as conn:
        return _next_staff_uid(conn, taken)


def add_member(name, phone, sub_type=None, days=None, price=None, paid=None, device_uid=None,
               gender=None, subscriptions=None):
    """
    يسجل لاعب جديد + اشتراكاته + دفعاته. يرجع member_id و device_uid.
    اشتراك واحد: sub_type, days, price, paid.
    أكثر من نوع: subscriptions=[{"sub_type": "حديد", "days": 30, "price": 50, "paid": 50}, ...]
    كل نوع إله مدته وسعره ودفعته. إذا أي اشتراك فيه خطأ بتنلغي العملية كلها.
    device_uid: إذا انعطى (من peek_next_device_uid) بنستخدمه، وإلا بنولّد رقم تلقائي.
    """
    name = name.strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    if gender is not None and gender not in GENDERS:
        raise ValueError("الجنس لازم يكون ذكر أو أنثى")
    if subscriptions is None:
        if None in (sub_type, days, price, paid):
            raise ValueError("بيانات الاشتراك ناقصة")
        subscriptions = [{"sub_type": sub_type, "days": days, "price": price, "paid": paid}]
    if not subscriptions:
        raise ValueError("اختر نوع اشتراك واحد على الأقل")
    types = [x["sub_type"] for x in subscriptions]
    if len(set(types)) != len(types):
        raise ValueError("نوع الاشتراك مكرر")
    with db() as conn:
        uid = device_uid if device_uid is not None else _next_device_uid(conn)
        cur = conn.execute(
            "INSERT INTO members (name, phone, gender, device_uid, created_at) "
            "VALUES (?,?,?,?,?)",
            (name, phone.strip(), gender, uid, _now().isoformat(sep=" ")),
        )
        member_id = cur.lastrowid
        for x in subscriptions:
            _add_subscription(conn, member_id, x["sub_type"], x["days"], x["price"], x["paid"])
    return {"member_id": member_id, "device_uid": uid}


def renew_subscription(member_id, days, price, paid, sub_type=None, pay_old=0):
    """
    تجديد نوع اشتراك، أو إضافة نوع جديد للاعب (مثلاً عنده حديد وبدك تضيف ايروبيك).
    - نفس النوع وهو ساري: بيكمل بعد تاريخ انتهائه. نفس النوع وهو منتهي: بيبدأ من اليوم.
    - نوع جديد: بيبدأ من اليوم وبنحسبه اشتراك جديد (مش تجديد).
    sub_type=None: آخر نوع اشترك فيه اللاعب.
    pay_old: دفعة اختيارية على المتبقي القديم، بتنحسب بنفس العملية (يا كلها يا ولا شي).
    """
    if pay_old < 0:
        raise ValueError("المبلغ لا يمكن أن يكون سالباً")
    with db() as conn:
        m = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        if not m:
            raise ValueError("اللاعب غير موجود")
        old_due = _member_status(conn, m)["remaining"]
        if pay_old > old_due + 1e-9:
            raise ValueError("المبلغ أكبر من المتبقي القديم على اللاعب")
        if sub_type is None:
            last = conn.execute(
                "SELECT sub_type FROM subscriptions WHERE member_id=? "
                "ORDER BY end_date DESC, id DESC LIMIT 1", (member_id,)
            ).fetchone()
            sub_type = last["sub_type"] if last else SUB_TYPES[0]
        if pay_old > 0:
            _pay_remaining(conn, member_id, pay_old)      # الدفعة القديمة أول (على الاشتراكات القديمة)
        _, start, end, is_renewal = _add_subscription(conn, member_id, sub_type, days, price, paid)
    return {"start_date": start.isoformat(), "end_date": end.isoformat(),
            "is_renewal": is_renewal, "sub_type": sub_type}


def _pay_remaining(conn, member_id, amount):
    subs = conn.execute(
        "SELECT s.id, s.price - COALESCE((SELECT SUM(amount) FROM payments "
        "WHERE subscription_id=s.id),0) AS due "
        "FROM subscriptions s WHERE s.member_id=? ORDER BY s.id", (member_id,)
    ).fetchall()
    left = amount
    for s in subs:
        if left <= 1e-9:
            break
        if s["due"] > 1e-9:
            pay = min(left, s["due"])
            conn.execute(
                "INSERT INTO payments (subscription_id, amount, paid_at) VALUES (?,?,?)",
                (s["id"], pay, _now().isoformat(sep=" ")),
            )
            left -= pay
    if left > 1e-9:
        raise ValueError("المبلغ أكبر من المتبقي على اللاعب")   # بيلغي الدفعات (rollback)


def pay_remaining(member_id, amount):
    """دفع جزء/كل المتبقي على اللاعب (بيوزع على أقدم الاشتراكات أولاً)."""
    if amount <= 0:
        raise ValueError("المبلغ لازم يكون أكبر من صفر")
    with db() as conn:
        _pay_remaining(conn, member_id, amount)


def update_member(member_id, name, phone=""):
    """تعديل اسم اللاعب ورقم هاتفه. (القسم/الجنس ثابت عشان ما ينتقل اللاعب بين القسمين بالغلط.)"""
    name = name.strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    with db() as conn:
        cur = conn.execute("UPDATE members SET name=?, phone=? WHERE id=?",
                           (name, phone.strip(), member_id))
        if cur.rowcount == 0:
            raise ValueError("اللاعب غير موجود")


def update_subscription_days(subscription_id, days):
    """
    تعديل مدة اشتراك: آخر يوم = تاريخ البداية + المدة الجديدة.
    بنسمح بتعديل آخر اشتراك من كل نوع بس (الأقدم تاريخ مضى، وتعديله بيلخبط التجديدات اللي بعده).
    """
    if days <= 0:
        raise ValueError("المدة لازم تكون أكبر من صفر")
    with db() as conn:
        sub = conn.execute("SELECT * FROM subscriptions WHERE id=?", (subscription_id,)).fetchone()
        if not sub:
            raise ValueError("الاشتراك غير موجود")
        latest = conn.execute(
            "SELECT id FROM subscriptions WHERE member_id=? AND sub_type=? "
            "ORDER BY end_date DESC, id DESC LIMIT 1", (sub["member_id"], sub["sub_type"])
        ).fetchone()
        if latest["id"] != subscription_id:
            raise ValueError("تقدر تعدّل مدة آخر اشتراك من كل نوع بس")
        end = date.fromisoformat(sub["start_date"]) + timedelta(days=days)
        conn.execute("UPDATE subscriptions SET days=?, end_date=? WHERE id=?",
                     (days, end.isoformat(), subscription_id))
    return {"days": days, "start_date": sub["start_date"], "end_date": end.isoformat(),
            "last_day": (end - timedelta(days=1)).isoformat(),
            "days_left": max((end - _today()).days, 0)}


def get_member(member_id):
    with db() as conn:
        m = conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        return _member_status(conn, m) if m else None


def search_members(query="", gender=None):
    """
    بحث بالاسم أو رقم الهاتف. الاستعلام الفاضي = كل اللاعبين.
    gender: إذا انعطى بيرجع لاعبين هالقسم بس (الواجهة دايماً بتمرره بالقوائم المحمية).
    """
    q = f"%{query.strip()}%"
    sql = "SELECT * FROM members WHERE (name LIKE ? OR phone LIKE ?)"
    params = [q, q]
    if gender is not None:
        sql += " AND gender = ?"
        params.append(gender)
    with db() as conn:
        rows = conn.execute(sql + " ORDER BY name", params).fetchall()
        return [_member_status(conn, r) for r in rows]


def member_history(member_id):
    """سجل اشتراكات اللاعب مع المدفوع والمتبقي لكل اشتراك."""
    with db() as conn:
        rows = conn.execute(
            "SELECT s.*, COALESCE((SELECT SUM(amount) FROM payments "
            "WHERE subscription_id=s.id),0) AS paid FROM subscriptions s "
            "WHERE s.member_id=? ORDER BY s.id DESC", (member_id,)
        ).fetchall()
        return [dict(r) | {"remaining": r["price"] - r["paid"]} for r in rows]


# ---------------------------------------------------------------- الموظفين
def add_staff(name, phone="", job_title="", device_uid=None):
    name = name.strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    with db() as conn:
        uid = device_uid if device_uid is not None else _next_staff_uid(conn)
        cur = conn.execute(
            "INSERT INTO staff (name, phone, job_title, device_uid, created_at) "
            "VALUES (?,?,?,?,?)",
            (name, phone.strip(), job_title.strip(), uid, _now().isoformat(sep=" ")),
        )
    return {"staff_id": cur.lastrowid, "device_uid": uid}


def list_staff(active_only=True):
    with db() as conn:
        sql = "SELECT * FROM staff"
        if active_only:
            sql += " WHERE active=1"
        return [dict(r) for r in conn.execute(sql + " ORDER BY name").fetchall()]


def get_staff(staff_id):
    with db() as conn:
        r = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
        return dict(r) if r else None


def update_staff(staff_id, name, phone="", job_title=""):
    name = name.strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    with db() as conn:
        cur = conn.execute("UPDATE staff SET name=?, phone=?, job_title=? WHERE id=?",
                           (name, phone.strip(), job_title.strip(), staff_id))
        if cur.rowcount == 0:
            raise ValueError("الموظف غير موجود")


def deactivate_staff(staff_id):
    """إيقاف موظف (ما بنحذف سجلاته القديمة). بصمته بتنحذف من الجهاز من الواجهة."""
    with db() as conn:
        conn.execute("UPDATE staff SET active=0 WHERE id=?", (staff_id,))


def staff_today(day=None):
    """كل الموظفين الفعّالين مع حالتهم اليوم: state = in (داخل) / out (خرج) / absent (ما حضر)."""
    day = (day or _today()).isoformat()
    with db() as conn:
        out = []
        for r in conn.execute("SELECT * FROM staff WHERE active=1 ORDER BY name").fetchall():
            summary = _staff_summary(conn, r["id"], day)
            state = "absent" if summary["scans"] == 0 else ("in" if summary["still_in"] else "out")
            out.append({"id": r["id"], "name": r["name"], "phone": r["phone"],
                        "job_title": r["job_title"], "device_uid": r["device_uid"],
                        "state": state, **summary})
        return out


def staff_history(staff_id, days=30):
    """ملخص دوام موظف لكل يوم من آخر days يوم (الأيام اللي فيها بصمات بس، الأحدث أول)."""
    since = (_today() - timedelta(days=days - 1)).isoformat()
    with db() as conn:
        dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT scan_date FROM attendance WHERE person_type='staff' "
            "AND person_id=? AND scan_date>=? ORDER BY scan_date DESC", (staff_id, since))]
        return [{"date": d, **_staff_summary(conn, staff_id, d)} for d in dates]


# ---------------------------------------------------------------- الحضور
def _staff_summary(conn, staff_id, day):
    """
    ملخص دوام موظف باليوم. البصمات بتتحسب بالتناوب: الأولى دخول، الثانية خروج، وهيك.
    مدة العمل = مجموع (خروج - دخول) للأزواج المكتملة.
    """
    rows = conn.execute(
        "SELECT scanned_at FROM attendance WHERE person_type='staff' AND person_id=? "
        "AND scan_date=? AND status='ok' ORDER BY scanned_at, id", (staff_id, day)
    ).fetchall()
    times = [datetime.fromisoformat(r["scanned_at"]) for r in rows]
    worked = timedelta()
    for i in range(0, len(times) - 1, 2):
        worked += times[i + 1] - times[i]
    return {
        "first_in": times[0].strftime("%H:%M") if times else None,
        "last_out": times[-1].strftime("%H:%M") if times and len(times) % 2 == 0 else None,
        "worked_minutes": int(worked.total_seconds() // 60),
        "still_in": len(times) % 2 == 1,
        "scans": len(times),
    }


def record_attendance(device_uid, timestamp=None):
    """
    يستدعى عند كل بصمة من الجهاز. يرجع نتيجة جاهزة للعرض:
    {kind, name, status, days_left, remaining, duplicate, ...}
    للموظف: direction = "in" (دخول) أو "out" (خروج) + worked_minutes + first_in.
    """
    ts = timestamp or _now()
    device_uid = int(device_uid)
    day = ts.date().isoformat()
    with db() as conn:
        result = {"kind": "unknown", "name": None, "status": "unknown",
                  "days_left": 0, "remaining": 0, "duplicate": False,
                  "member_id": None, "sub_type": None, "last_day": None,
                  "subs": [], "min_days_left": 0, "direction": None, "worked_minutes": 0, "first_in": None}
        person_type, person_id = "unknown", None

        m = conn.execute("SELECT * FROM members WHERE device_uid=?", (device_uid,)).fetchone()
        s = None if m else conn.execute(
            "SELECT * FROM staff WHERE device_uid=? AND active=1", (device_uid,)
        ).fetchone()

        if m:
            st = _member_status(conn, m)
            person_type, person_id = "member", m["id"]
            last_day = None
            if st["end_date"]:      # end_date حصري، فآخر يوم فعلي = قبله بيوم
                last_day = (date.fromisoformat(st["end_date"]) - timedelta(days=1)).isoformat()
            result.update(kind="member", name=st["name"], days_left=st["days_left"],
                          min_days_left=st["min_days_left"], subs=st["subs"],
                          remaining=st["remaining"], member_id=m["id"],
                          sub_type=st["sub_type"], last_day=last_day,
                          status="ok" if st["active"] else "expired")
        elif s:
            person_type, person_id = "staff", s["id"]
            result.update(kind="staff", name=s["name"], status="ok")

        # كم بصمة سجل الموظف اليوم (بتحدد دخول أو خروج)
        n_staff = 0
        if person_type == "staff":
            n_staff = conn.execute(
                "SELECT COUNT(*) FROM attendance WHERE person_type='staff' AND person_id=? "
                "AND scan_date=? AND status='ok'", (person_id, day)
            ).fetchone()[0]

        # منع التكرار (للموظف مدة أقصر عشان ما نمنع خروج حقيقي)
        window = STAFF_DUPLICATE_WINDOW_MIN if person_type == "staff" else DUPLICATE_WINDOW_MIN
        last = conn.execute(
            "SELECT scanned_at FROM attendance WHERE device_uid=? ORDER BY id DESC LIMIT 1",
            (device_uid,),
        ).fetchone()
        if last:
            diff = (ts - datetime.fromisoformat(last["scanned_at"])).total_seconds()
            if 0 <= diff < window * 60:
                result["duplicate"] = True
                if person_type == "staff" and n_staff:
                    summary = _staff_summary(conn, person_id, day)
                    result.update(direction="in" if (n_staff - 1) % 2 == 0 else "out",
                                  worked_minutes=summary["worked_minutes"],
                                  first_in=summary["first_in"])
                return result

        direction = None
        if person_type == "staff":
            direction = "in" if n_staff % 2 == 0 else "out"
        conn.execute(
            "INSERT INTO attendance (person_type, person_id, device_uid, scanned_at, "
            "scan_date, status, direction) VALUES (?,?,?,?,?,?,?)",
            (person_type, person_id, device_uid, ts.isoformat(sep=" "), day,
             result["status"], direction),
        )
        if person_type == "staff":
            summary = _staff_summary(conn, person_id, day)
            result.update(direction=direction, worked_minutes=summary["worked_minutes"],
                          first_in=summary["first_in"])
        return result


# ---------------------------------------------------------------- التقرير اليومي
def _remaining_at(conn, member_id, day):
    """المتبقي على لاعب (كل اشتراكاته) بنهاية يوم معين، فالتقرير القديم بيضل دقيق."""
    price = conn.execute(
        "SELECT COALESCE(SUM(price),0) FROM subscriptions WHERE member_id=? AND date(created_at)<=?",
        (member_id, day)).fetchone()[0]
    paid = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN subscriptions s ON s.id=p.subscription_id "
        "WHERE s.member_id=? AND date(p.paid_at)<=?", (member_id, day)).fetchone()[0]
    return price - paid


def _day_subscriptions(conn, day, renewal, gender=None):
    """اشتراكات انعملت باليوم (جديدة أو تجديد) مجمّعة لكل لاعب: الاسم، الأنواع، المدفوع، المتبقي."""
    rows = conn.execute(
        "SELECT s.id, s.member_id, s.sub_type, s.days, s.price, m.name FROM subscriptions s "
        "JOIN members m ON m.id=s.member_id WHERE date(s.created_at)=? AND s.is_renewal=? "
        "AND (? IS NULL OR m.gender=?) ORDER BY s.id", (day, int(renewal), gender, gender)).fetchall()
    people = {}
    for r in rows:                      # dict بيحافظ على ترتيب أول ظهور
        p = people.setdefault(r["member_id"], {"name": r["name"], "subs": [], "paid": 0.0})
        p["subs"].append({"sub_type": r["sub_type"], "days": r["days"], "price": r["price"]})
        p["paid"] += conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE subscription_id=? AND date(paid_at)=?",
            (r["id"], day)).fetchone()[0]
    for member_id, p in people.items():
        p["remaining"] = _remaining_at(conn, member_id, day)
    return list(people.values())


def daily_report(day=None, gender=None):
    """
    تقرير يوم: حضور الموظفين، عدد حضور اللاعبين، وبالتفصيل:
    gender ("ذكر" / "أنثى"): تقرير هالقسم بس (اللاعبين ودفعاتهم). الموظفين بيظهروا بكل الأحوال.
    new_members: اللي اشتركوا (اسم، أنواعهم ومدتهم، كم دفع، كم لسا عليه)
    renewed_members: اللي جددوا (نفس التفاصيل)
    settlements: اللي سددوا دفعة من متبقي قديم (اسم، كم سدد، كم لسا عليه)
    total_paid: مجموع كل الدفعات باليوم
    """
    day = (day or _today()).isoformat()
    with db() as conn:
        staff_rows = conn.execute(
            "SELECT st.id, st.name, MIN(a.scanned_at) AS first_scan "
            "FROM attendance a JOIN staff st ON st.id=a.person_id "
            "WHERE a.person_type='staff' AND a.scan_date=? GROUP BY st.id ORDER BY first_scan",
            (day,),
        ).fetchall()
        staff = []
        for r in staff_rows:
            summary = _staff_summary(conn, r["id"], day)
            staff.append({"name": r["name"], "first_in": summary["first_in"],
                          "last_out": summary["last_out"],
                          "worked_minutes": summary["worked_minutes"],
                          "still_in": summary["still_in"]})
        members_attended = conn.execute(
            "SELECT COUNT(DISTINCT a.person_id) FROM attendance a "
            "JOIN members m ON m.id=a.person_id "
            "WHERE a.person_type='member' AND a.status='ok' AND a.scan_date=? "
            "AND (? IS NULL OR m.gender=?)", (day, gender, gender)
        ).fetchone()[0]
        expired_scans = conn.execute(
            "SELECT COUNT(*) FROM attendance a JOIN members m ON m.id=a.person_id "
            "WHERE a.person_type='member' AND a.status='expired' AND a.scan_date=? "
            "AND (? IS NULL OR m.gender=?)", (day, gender, gender)
        ).fetchone()[0]

        new_members = _day_subscriptions(conn, day, renewal=False, gender=gender)
        renewed_members = _day_subscriptions(conn, day, renewal=True, gender=gender)

        # تسديد دفعات على اشتراكات قديمة (مش اشتراكات انعملت اليوم)
        settlements = []
        for r in conn.execute(
                "SELECT s.member_id, m.name, SUM(p.amount) AS paid "
                "FROM payments p JOIN subscriptions s ON s.id=p.subscription_id "
                "JOIN members m ON m.id=s.member_id "
                "WHERE date(p.paid_at)=? AND date(s.created_at)<>? AND (? IS NULL OR m.gender=?) "
                "GROUP BY s.member_id ORDER BY MIN(p.id)", (day, day, gender, gender)).fetchall():
            settlements.append({"name": r["name"], "paid": r["paid"],
                                "remaining": _remaining_at(conn, r["member_id"], day)})

        total_paid = conn.execute(
            "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
            "JOIN subscriptions s ON s.id=p.subscription_id JOIN members m ON m.id=s.member_id "
            "WHERE date(p.paid_at)=? AND (? IS NULL OR m.gender=?)", (day, gender, gender)
        ).fetchone()[0]

    return {
        "date": day,
        "staff": staff,
        "members_attended": members_attended,
        "expired_scans": expired_scans,
        "new_members": new_members,
        "renewed_members": renewed_members,
        "settlements": settlements,
        "new_subscriptions": len(new_members),        # عدد الأشخاص (مش عدد الاشتراكات)
        "renewals": len(renewed_members),
        "total_paid": total_paid,
    }


# ---------------------------------------------------------------- نسخ احتياطي
def backup_db():
    """نسخة واحدة باليوم (بتتكتب فوق نسخة نفس اليوم) + حذف النسخ الأقدم من آخر BACKUP_KEEP. يرجع المسار."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f"gym_{_today().isoformat()}.db")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    _prune_backups()
    return target


def _prune_backups():
    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith("gym_") and f.endswith(".db"))      # الاسم فيه التاريخ فالترتيب زمني
    for old in files[:max(len(files) - BACKUP_KEEP, 0)]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass


# ---------------------------------------------------------------- إعدادات عامة (رقم واتساب صاحب الجيم...)
def get_setting(key, default=None):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
