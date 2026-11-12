"""reports.py - نص التقرير اليومي + فتح واتساب ويب بالرسالة جاهزة

الإرسال عبر واتساب ويب بدون أي خدمة مدفوعة: بنفتح رابط web.whatsapp.com/send بالمتصفح الافتراضي
والرسالة مكتوبة جاهزة، وإنت بتضغط "إرسال" هناك. (لازم يكون واتساب ويب مسجّل دخول بالمتصفح.)
"""
import sys
import time
import urllib.parse
import webbrowser
from datetime import date

import config
import db

# date.weekday(): الاثنين = 0
WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)


def _hours(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def _money(x):
    text = f"{x:g}"
    return f"{text} {config.CURRENCY}".strip()


def _days(n):
    if n == 1:
        return "يوم"
    if n == 2:
        return "يومين"
    return f"{n} أيام" if 3 <= n <= 10 else f"{n} يوم"


def _remaining_text(x):
    return "مسدّد بالكامل" if x <= 0.0001 else f"متبقي عليه {_money(x)}"


def _people_lines(title, people):
    """قسم من التقرير: اللاعبين اللي اشتركوا/جددوا، كل واحد باسمه وأنواعه وكم دفع وكم لسا عليه."""
    lines = ["", f"*{title} ({len(people)})*"]
    if not people:
        lines.append("• لا يوجد")
        return lines
    for i, p in enumerate(people, 1):
        kinds = " + ".join(f"{s['sub_type']} {_days(s['days'])}" for s in p["subs"])
        lines.append(f"{i}. {p['name']} — {kinds}")
        lines.append(f"   دفع {_money(p['paid'])} | {_remaining_text(p['remaining'])}")
    return lines


def build_report_text(day=None, gender=None):
    """
    نص تقرير يوم معين (الافتراضي اليوم)، جاهز للصق بواتساب (النجمة = خط عريض):
    الموظفين، عدد الحاضرين، المشتركين الجدد، المجددين، من سدد من المتبقي، وإجمالي الدفع.
    gender: تقرير قسم واحد (شباب / نساء): لاعبينه ودفعاته بس. بدون: كل الأقسام.
    """
    day = day or date.today()
    r = db.daily_report(day, gender)
    lines = [f"*تقرير {config.GYM_NAME} اليومي*"]
    if gender:
        lines.append(f"القسم: {db.SECTION_NAMES[gender]}")
    lines += [f"التاريخ: {day.isoformat()} ({WEEKDAYS[day.weekday()]})",
              "",
              "*الموظفين*"]
    if r["staff"]:
        for s in r["staff"]:
            if s["still_in"]:
                out = "موجود الآن" if day == date.today() else "ما سجّل خروج"
            else:
                out = f"خروج {s['last_out']}"
            work = f" | مدة العمل {_hours(s['worked_minutes'])}" if s["worked_minutes"] else ""
            lines.append(f"• {s['name']}: دخول {s['first_in']} | {out}{work}")
    else:
        lines.append("• لا يوجد حضور مسجّل")

    lines += ["", "*الحضور*", f"• عدد اللاعبين الحاضرين: {r['members_attended']}"]
    if r["expired_scans"]:
        lines.append(f"• بصمات باشتراك منتهي: {r['expired_scans']}")

    lines += _people_lines("الاشتراكات الجديدة", r["new_members"])
    lines += _people_lines("التجديدات", r["renewed_members"])

    lines += ["", f"*تسديد دفعات من المتبقي ({len(r['settlements'])})*"]
    if r["settlements"]:
        for i, p in enumerate(r["settlements"], 1):
            lines.append(f"{i}. {p['name']} — سدد {_money(p['paid'])} | {_remaining_text(p['remaining'])}")
    else:
        lines.append("• لا يوجد")

    lines += ["", f"*إجمالي الدفع اليوم: {_money(r['total_paid'])}*"]
    return "\n".join(lines)


def normalize_phone(raw):
    """رقم واتساب بصيغة دولية بدون + وبدون أصفار: 962791234567. بيرمي ValueError إذا غلط."""
    cleaned = str(raw).translate(_DIGITS)
    for ch in " -+()":
        cleaned = cleaned.replace(ch, "")
    if cleaned.startswith("00"):
        cleaned = cleaned[2:]
    if cleaned.startswith("0"):
        raise ValueError("اكتب الرقم مع رمز الدولة وبدون صفر بالأول، مثال: 962791234567")
    if not cleaned.isdigit() or not 8 <= len(cleaned) <= 15:
        raise ValueError("الرقم غير صحيح: لازم يكون أرقام فقط (8 لـ 15 رقم) مع رمز الدولة")
    return cleaned


def whatsapp_url(phone, text):
    return f"https://web.whatsapp.com/send?phone={phone}&text={urllib.parse.quote(text, safe='')}"


# الرابط الطويل ممكن ما يشتغل (حدود طول سطر الأوامر بويندوز)، فإذا النص طويل بنفتح المحادثة بس
# والتقرير بيكون منسوخ بالحافظة، وبيتلصق (Ctrl+V) بدل ما يتكتب بالرابط.


def whatsapp_chat_url(phone):
    return f"https://web.whatsapp.com/send?phone={phone}"


def send_mode(phone, text):
    """prefill = النص بالرابط (للتقارير القصيرة)، paste = المحادثة بس والنص بالحافظة (للطويلة)."""
    return "prefill" if len(whatsapp_url(phone, text)) <= config.WHATSAPP_MAX_URL else "paste"


def open_whatsapp(phone, text, mode=None):
    """بيفتح واتساب ويب بالمتصفح. بيرجع (تم_الفتح, الرابط, الطريقة)."""
    mode = mode or send_mode(phone, text)
    url = whatsapp_url(phone, text) if mode == "prefill" else whatsapp_chat_url(phone)
    return webbrowser.open(url), url, mode


# ---------------------------------------------------------------- إرسال تلقائي (ضغطة Enter)
# واتساب ويب بيفتح المحادثة والرسالة مكتوبة جاهزة، وبضل بس الضغط على "إرسال".
# هون البرنامج بيضغط Enter بدالك (ويندوز فقط، بدون مكتبات إضافية).
# أمان: ما بنضغط Enter إلا إذا النافذة الأمامية هي متصفح بتبويب واتساب (مش تطبيق واتساب
# للكمبيوتر ولا أي برنامج ثاني). والضغط على Enter وصندوق الكتابة فاضي ما بيعمل شي.
BROWSER_MARKERS = ("chrome", "edge", "firefox", "brave", "opera")


def is_whatsapp_browser_title(title):
    """هل عنوان النافذة لتبويب واتساب ويب بمتصفح؟ (تطبيق واتساب للكمبيوتر عنوانه "WhatsApp" بس)"""
    t = (title or "").lower()
    return "whatsapp" in t and any(marker in t for marker in BROWSER_MARKERS)


def foreground_title():
    """عنوان النافذة الأمامية (ويندوز فقط). بيرجع "" إذا ما قدر."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:  # noqa: BLE001 - مش ويندوز أو خطأ بالـ API
        return ""


def press_enter():
    import ctypes
    vk_return, key_up = 0x0D, 0x0002
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_return, 0, 0, 0)
    user32.keybd_event(vk_return, 0, key_up, 0)


def press_ctrl_v():
    import ctypes
    vk_control, vk_v, key_up = 0x11, 0x56, 0x0002
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_control, 0, 0, 0)
    user32.keybd_event(vk_v, 0, 0, 0)
    user32.keybd_event(vk_v, 0, key_up, 0)
    user32.keybd_event(vk_control, 0, key_up, 0)


def auto_press_enter(find_timeout=30, settle=None, gap=None, paste=False,
                     get_title=foreground_title, press=press_enter, press_paste=press_ctrl_v,
                     sleep=time.sleep, now=time.monotonic):
    """
    بينتظر لحد ما يصير تبويب واتساب ويب هو الأمامي، وبعدين بيستنى يتحمّل (settle)،
    وإذا paste=True بيلصق التقرير (Ctrl+V)، وبعدين بيضغط Enter مرتين بفاصل (gap)
    عشان لو الأولى كانت بدري ما تضيع (والثانية ما بتعمل شي إذا الرسالة انرسلت).
    بيرجع (نجح, رسالة). "نجح" معناها ضغطنا Enter، مش إنو واتساب أكد الإرسال.
    """
    if get_title is foreground_title and not sys.platform.startswith("win"):
        return False, "الإرسال التلقائي بيشتغل على ويندوز فقط."
    settle = config.WHATSAPP_SETTLE_SECONDS if settle is None else settle
    gap = config.WHATSAPP_RETRY_GAP_SECONDS if gap is None else gap

    deadline = now() + find_timeout
    while not is_whatsapp_browser_title(get_title()):
        if now() >= deadline:
            return False, ("ما لقيت تبويب واتساب ويب كنافذة أمامية "
                           "(لازم يكون واتساب ويب مفتوح ومسجّل دخول بمتصفح عادي).")
        sleep(1)

    sleep(settle)
    if paste:
        if not is_whatsapp_browser_title(get_title()):
            return False, "تغيّرت النافذة الأمامية قبل اللصق، فما لصقت شي."
        press_paste()
        sleep(2)
    pressed = 0
    for attempt in range(2):
        if not is_whatsapp_browser_title(get_title()):
            break                         # المستخدم راح لنافذة ثانية: ما بنضغط شي
        press()
        pressed += 1
        if attempt == 0:
            sleep(gap)
    if pressed == 0:
        return False, "تغيّرت النافذة الأمامية قبل الإرسال، فما ضغطت شي."
    what = "لصق التقرير والضغط على Enter" if paste else "الضغط على Enter"
    return True, f"تم {what} تلقائياً. تأكد من وصول الرسالة بواتساب."
