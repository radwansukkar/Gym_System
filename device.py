"""device.py - التعامل مع جهاز البصمة ZKTeco K40

الفكرة:
- Thread واحد "يملك" الاتصال بالجهاز، لأن اتصال pyzk مش آمن للاستخدام من أكثر من thread.
- هاد الـ thread بيسمع للبصمات (live_capture) وبيحط كل بصمة بطابور events.
- أي أمر ثاني (تسجيل مستخدم، تسجيل بصمة، حذف) بيدخل كـ "job"، فالـ thread بيوقف
  الاستماع لحظة، بينفذه، وبيرجع يسمع.
- إذا انقطع الاتصال بيحاول يرجع يتصل لحاله.

الأحداث اللي بتطلع من الطابور (device.events):
    ("scan", device_uid: int, time: datetime)
    ("status", connected: bool, message: str)
"""
import queue
import threading
from datetime import datetime

from zk import ZK, const

import config


class DeviceError(Exception):
    """خطأ بالتعامل مع الجهاز (رسالته جاهزة للعرض للمستخدم)."""


class _Job:
    def __init__(self, func):
        self.func = func
        self.done = threading.Event()
        self.result = None
        self.error = None


class DeviceManager:
    def __init__(self, ip=config.DEVICE_IP, port=config.DEVICE_PORT):
        self.ip = ip
        self.port = port
        self.events = queue.Queue()
        self.connected = False
        self._jobs = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------ تشغيل/إيقاف
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="DeviceThread", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    # ------------------------------------------------------------ الحلقة الرئيسية
    def _loop(self):
        while not self._stop.is_set():
            conn = None
            try:
                zk = ZK(self.ip, port=self.port, timeout=config.DEVICE_TIMEOUT)
                conn = zk.connect()
                try:
                    conn.set_time(datetime.now())   # مزامنة ساعة الجهاز
                except Exception:
                    pass
                self._set_connected(True, "متصل")
                self._listen(conn)
            except Exception as e:  # noqa: BLE001 - أي خطأ = إعادة اتصال
                self._set_connected(False, str(e) or e.__class__.__name__)
                self._fail_pending_jobs()
            finally:
                if conn is not None:
                    try:
                        conn.disconnect()
                    except Exception:
                        pass
            if not self._stop.is_set():
                self._stop.wait(config.RECONNECT_DELAY)
        self._set_connected(False, "تم الإيقاف")

    def _listen(self, conn):
        while not self._stop.is_set():
            gen = conn.live_capture(new_timeout=1)
            for att in gen:
                if att is not None:
                    self._emit_scan(att)
                # إذا في job منتظر أو طلب إيقاف: بننهي الاستماع بشكل نظيف
                if self._stop.is_set() or not self._jobs.empty():
                    conn.end_live_capture = True
            self._run_pending_jobs(conn)

    def _emit_scan(self, att):
        try:
            uid = int(att.user_id)
        except (TypeError, ValueError):
            return
        # وقت اللابتوب لحظة الاستلام (الاستماع حي فهو دقيق)
        self.events.put(("scan", uid, datetime.now().replace(microsecond=0)))

    def _set_connected(self, state, message):
        changed = state != self.connected
        self.connected = state
        if changed or not state:
            self.events.put(("status", state, message))

    # ------------------------------------------------------------ نظام الـ jobs
    def _run_pending_jobs(self, conn):
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                return
            try:
                job.result = job.func(conn)
            except Exception as e:  # noqa: BLE001
                job.error = e
            finally:
                job.done.set()

    def _fail_pending_jobs(self):
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                return
            job.error = DeviceError("انقطع الاتصال بالجهاز")
            job.done.set()

    def run_job(self, func, timeout=30):
        """ينفذ func(conn) على thread الجهاز ويرجع النتيجة (blocking)."""
        if not self.connected:
            raise DeviceError("الجهاز غير متصل")
        job = _Job(func)
        self._jobs.put(job)
        if not job.done.wait(timeout):
            raise DeviceError("انتهت مهلة الانتظار، الجهاز ما رد")
        if job.error:
            if isinstance(job.error, DeviceError):
                raise job.error
            raise DeviceError(f"خطأ من الجهاز: {job.error}") from job.error
        return job.result

    # ------------------------------------------------------------ أوامر عالية المستوى
    # ملاحظة: اسم المستخدم على الجهاز = رقمه (الاسم الحقيقي بقاعدة البيانات)،
    # لأن الجهاز ما بيعرض العربي منيح وطول الاسم محدود.

    def add_user(self, uid):
        """
        يسجل مستخدم على الجهاز (بدون بصمة بعد).
        أول شي بنمسح أي مستخدم/بصمة قديمة بنفس الرقم، حتى ما ترث البصمة القديمة.
        """
        def job(conn):
            try:
                conn.delete_user(uid=uid)
            except Exception:
                pass            # الرقم مش موجود أصلاً = عادي
            conn.set_user(uid=uid, name=str(uid), privilege=const.USER_DEFAULT,
                          user_id=str(uid))
        self.run_job(job)

    def enroll_fingerprint(self, uid, finger=0):
        """
        يشغّل شاشة تسجيل البصمة على الجهاز (المستخدم بيحط إصبعه 3 مرات).
        blocking لحد ما يخلص، فلازم تناديه من thread مش من واجهة tkinter مباشرة.
        النتيجة الحقيقية بنتأكد منها من قائمة البصمات على الجهاز، مش من رد المكتبة بس.
        """
        def job(conn):
            conn.verbose = config.DEBUG_ENROLL      # بيطبع res/finger duplicate إلخ
            try:
                lib_ok = bool(conn.enroll_user(uid=uid, temp_id=finger, user_id=str(uid)))
            finally:
                conn.verbose = False
            try:
                conn.refresh_data()
            except Exception:
                pass
            found = any(t.uid == uid and t.fid == finger for t in conn.get_templates())
            return lib_ok or found
        return self.run_job(job, timeout=150)

    def has_fingerprint(self, uid, finger=0):
        """هل المستخدم عنده بصمة مسجلة فعلاً بالجهاز؟ (من قائمة البصمات الحقيقية)"""
        def job(conn):
            return any(t.uid == uid and t.fid == finger for t in conn.get_templates())
        return self.run_job(job)

    def register_user_with_fingerprint(self, uid):
        """
        تسجيل كامل: مستخدم + بصمة. إذا فشلت البصمة بنحذف المستخدم من الجهاز
        (ما بنخلي مستخدمين عالقين بدون بصمة) وبنرمي DeviceError برسالة واضحة.
        """
        self.add_user(uid)
        try:
            ok = self.enroll_fingerprint(uid)
        except DeviceError:
            self._silent_delete(uid)
            raise
        if not ok:
            self._silent_delete(uid)
            raise DeviceError(
                "فشل تسجيل البصمة (انتهى الوقت، أو إلغاء، أو الإصبع مسجّل مسبقاً بالجهاز). "
                "اقرأ رسالة شاشة الجهاز وجرّب إصبع ثاني.")

    def _silent_delete(self, uid):
        try:
            self.delete_user(uid)
        except DeviceError:
            pass

    def delete_user(self, uid):
        def job(conn):
            conn.delete_user(uid=uid)
        self.run_job(job)

    def device_users(self):
        """قائمة (uid, privilege) لكل المستخدمين على الجهاز (للفحص)."""
        def job(conn):
            return [(u.uid, u.privilege) for u in conn.get_users()]
        return self.run_job(job)

    def device_templates(self):
        """قائمة (uid, finger_id) لكل البصمات المخزنة بالجهاز (للفحص)."""
        def job(conn):
            return [(t.uid, t.fid) for t in conn.get_templates()]
        return self.run_job(job)
