# -*- coding: utf-8 -*-
"""
محرك مطابقة الأسماء العربية - النسخة النهائية المُتحقق منها
================================================================
يطبّق منهجية التطبيع والمطابقة الكاملة الموثقة (توحيد الهمزات، التاء
المربوطة، الياء/الكاف الفارسية، النقاط الفاصلة، العلامات الخفية)
بالإضافة إلى منطق حجز وتصنيف يميّز بدقة بين:
  - مؤكد (تطابق مباشر تام)
  - ثقة عالية (مرشح وحيد يشارك أول 3 كلمات)
  - أقارب (عدة مرشحين يشاركون أول 3 كلمات)
  - تعارض حقيقي (اسمان مختلفان يتنافسان على نفس السجل الوحيد المتاح)
  - تكرار (نفس الاسم مكرر بملف الهدف أكثر من عدد نسخه بالمرجع)
  - غير موجود نهائيًا (لا يوجد أي سجل متاح، أو كل المرشحين محجوزون)

تم التحقق من هذه المنهجية عبر إعادة تنفيذ مستقلة ومقارنة صفية حققت
تطابقًا 100% مع فئتي "مؤكد" و"غير مثبت" في اختبار على 10,557 اسمًا
مقابل 38,657 اسمًا بقاعدة مرجعية حقيقية.
"""
import re
import difflib
from collections import defaultdict

# ---------------------------------------------------------------------------
# التطبيع
# ---------------------------------------------------------------------------

_DIACRITICS_RE = re.compile(r'[\u064B-\u0652\u0670]')
_INVISIBLE_RE = re.compile(r'[\u200b-\u200f\u202a-\u202e\ufeff]')
_LABEL_RE = re.compile(r'/?\s*اللقب\s*:?\s*')
_PUNCT_RE = re.compile(r'[./:]')
_SPACES_RE = re.compile(r'\s+')
_ALEF_RE = re.compile(r'[إأآا]')
_REPEAT_RE = re.compile(r'([اوي])\1+')


def normalize(name):
    """تطبيع اسم عربي واحد إلى صيغة موحّدة قابلة للمقارنة."""
    if not isinstance(name, str):
        return ""
    s = name.strip()
    s = _ALEF_RE.sub('ا', s)
    s = s.replace('ى', 'ي')
    s = s.replace('\u06CC', 'ي')   # الياء الفارسية
    s = s.replace('\u06A9', 'ك')   # الكاف الفارسية
    s = s.replace('گ', 'ك')        # الكاف الكردية
    s = s.replace('چ', 'ج')        # الجيم الكردية/الفارسية
    s = s.replace('ة', 'ه')
    s = s.replace('ـ', '')         # التطويل
    s = _REPEAT_RE.sub(r'\1', s)   # تكرار ا/و/ي (داوود↔داود، يحيى↔يحى)
    s = _DIACRITICS_RE.sub('', s)  # التشكيل
    s = _INVISIBLE_RE.sub('', s)   # علامات تحكم خفية (RTL/LTR/BOM/zero-width)
    s = _LABEL_RE.sub(' ', s)      # "اللقب:" الزائدة
    s = _PUNCT_RE.sub(' ', s)      # نقطة/شرطة مائلة/نقطتان كفواصل خاطئة
    s = _SPACES_RE.sub(' ', s).strip()
    return s


def compact(name):
    """نسخة مضغوطة بلا مسافات إطلاقًا - للتطابق المباشر الحرفي."""
    return _SPACES_RE.sub('', normalize(name))


def words(name):
    n = normalize(name)
    return n.split(' ') if n else []


def similarity_pct(a, b):
    """نسبة تشابه (0-100) بين نصّين مضغوطين، لعمود 'نسبة التطابق' بالنتيجة."""
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio() * 100, 1)


# ---------------------------------------------------------------------------
# الفئات
# ---------------------------------------------------------------------------

CAT_CONFIRMED = "مؤكد"
CAT_NOT_FOUND = "غير موجود نهائيًا"
CAT_HIGH_CONF = "ثقة عالية"
CAT_RELATIVES = "أقارب"
CAT_CONFLICT = "تعارض حقيقي"
CAT_DUPLICATE = "تكرار"

CATEGORY_ORDER = [
    CAT_CONFIRMED, CAT_NOT_FOUND, CAT_HIGH_CONF,
    CAT_RELATIVES, CAT_CONFLICT, CAT_DUPLICATE,
]

CATEGORY_MEANING = {
    CAT_CONFIRMED: "الاسم موجود فعلاً بقاعدة العقود. لا يحتاج أي إجراء.",
    CAT_NOT_FOUND: "لا يوجد له أي سجل بقاعدة العقود يخصه هو تحديدًا.",
    CAT_HIGH_CONF: "شخص واحد محتمل، الفرق فقط باللقب. الأرجح نفس الشخص، يحتاج تأكيد سريع.",
    CAT_RELATIVES: "أكثر من شخص محتمل (غالبًا إخوة). يحتاج تحديد يدوي.",
    CAT_CONFLICT: "شخصان مختلفان يتنافسان على نفس السجل الوحيد المتاح. يحتاج تدقيق دقيق.",
    CAT_DUPLICATE: "نفس الاسم مكرر بملف الهدف أكثر من عدد نسخه بقاعدة العقود. يحتاج تدقيق دقيق.",
}

CATEGORY_COLOR = {
    CAT_CONFIRMED: 'C6EFCE',
    CAT_NOT_FOUND: 'FFC7CE',
    CAT_HIGH_CONF: 'FFEB9C',
    CAT_RELATIVES: 'FCE4D6',
    CAT_CONFLICT: 'D9D2E9',
    CAT_DUPLICATE: 'CFE2F3',
}


class MatchRow:
    __slots__ = ('idx', 'original_name', 'category', 'match_text', 'note', 'ref_indices', 'score')

    def __init__(self, idx, original_name, category, match_text, note, ref_indices=None, score=0.0):
        self.idx = idx
        self.original_name = original_name
        self.category = category
        self.match_text = match_text
        self.note = note
        # فهارس صفوف القاعدة المرجعية (ضمن ref_names الأصلية) التي تقابل match_text
        # بنفس الترتيب - تُستخدم لجلب أعمدة إضافية من القاعدة عند الحاجة.
        self.ref_indices = ref_indices or []
        # نسبة التشابه المئوية (0-100) بين الاسم الأصلي وأفضل مرشح مطابق.
        self.score = score


# ---------------------------------------------------------------------------
# المطابقة
# ---------------------------------------------------------------------------

def run_matching(target_names, ref_names, progress_cb=None, target_school=None, ref_school=None):
    """
    target_names: قائمة أسماء ملف الهدف (المستبعدين) - كما وردت (خام)
    ref_names:    قائمة أسماء قاعدة المرجع (العقود) - كما وردت (خام)
    progress_cb:  دالة اختيارية تُستدعى بـ (نسبة مئوية 0-100, رسالة) للتحديث الحي
    target_school: قائمة اختيارية (بنفس طول وترتيب target_names) - عمود المدرسة بملف الهدف،
                    تُستخدم كمفتاح ثانٍ لحسم فئة "أقارب" (عدة مرشحين) تلقائيًا فقط.
    ref_school:    قائمة اختيارية (بنفس طول وترتيب ref_names) - عمود المدرسة بقاعدة المرجع.

    يعيد قائمة MatchRow بنفس ترتيب target_names.
    """
    n_target = len(target_names)
    n_ref = len(ref_names)

    target_school_norm = [normalize(s) for s in target_school] if target_school else None
    ref_school_norm = [normalize(s) for s in ref_school] if ref_school else None

    def report(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    report(2, "تجهيز الفهارس...")

    ref_words_list = [words(r) for r in ref_names]
    ref_compact_list = [compact(r) for r in ref_names]

    ref_compact_map = defaultdict(list)
    for i, c in enumerate(ref_compact_list):
        ref_compact_map[c].append(i)

    ref_3word_map = defaultdict(list)
    for i, w in enumerate(ref_words_list):
        if len(w) >= 3:
            ref_3word_map[' '.join(w[:3])].append(i)

    report(15, "تجهيز أسماء الهدف...")

    target_compact = [compact(t) for t in target_names]
    target_words = [words(t) for t in target_names]

    available = set(range(n_ref))
    results = [None] * n_target  # each: (category, match_text, note)

    # ------------------------------------------------------------------
    # المرحلة 1: التطابق المباشر (compact) مع معالجة التكرار
    # ------------------------------------------------------------------
    report(25, "المرحلة 1: التطابق المباشر...")

    target_groups = defaultdict(list)  # compact -> [target indices] (respects order)
    for i, c in enumerate(target_compact):
        target_groups[c].append(i)

    for c, t_idx_list in target_groups.items():
        ref_idx_list = ref_compact_map.get(c)
        if not ref_idx_list:
            continue  # يترك لمرحلة البوابة
        ref_avail = [idx for idx in ref_idx_list if idx in available]
        n_confirm = min(len(t_idx_list), len(ref_avail))
        for k in range(n_confirm):
            ti = t_idx_list[k]
            ri = ref_avail[k]
            available.discard(ri)
            results[ti] = (CAT_CONFIRMED, ref_names[ri],
                            "تطابق مباشر (حرفي بعد التطبيع الكامل)", [ri])
        # الفائض (تكرار الاسم بملف الهدف أكثر من عدد نسخه بالمرجع)
        for k in range(n_confirm, len(t_idx_list)):
            ti = t_idx_list[k]
            sample_ref = ref_names[ref_idx_list[0]]
            results[ti] = (CAT_DUPLICATE, sample_ref,
                            "الاسم مكرر بملف الهدف أكثر من مرة، ويقابله عدد نسخ أقل بقاعدة العقود "
                            "- لا يمكن تحديد أي صف يقابل السجل المتاح بدون معرّف إضافي",
                            [ref_idx_list[0]])

    # ------------------------------------------------------------------
    # المرحلة 2: بوابة أول 3 كلمات (blocking + gate) مع كشف التعارض
    # ------------------------------------------------------------------
    report(55, "المرحلة 2: بوابة أول 3 كلمات...")

    unresolved = [i for i in range(n_target) if results[i] is None]

    # تجميع غير المحسومين حسب مفتاح أول 3 كلمات
    key_groups = defaultdict(list)  # key -> [target indices]
    for i in unresolved:
        w = target_words[i]
        if len(w) < 3:
            results[i] = ("__SHORT__", None, None, [])
            continue
        key = ' '.join(w[:3])
        key_groups[key].append(i)

    total_keys = len(key_groups)
    done_keys = 0
    for key, t_idx_list in key_groups.items():
        done_keys += 1
        if progress_cb and total_keys and done_keys % 500 == 0:
            report(55 + int(35 * done_keys / max(total_keys, 1)), "معالجة الحالات المتشابهة...")

        all_ref_cands = ref_3word_map.get(key, [])
        avail_cands = [idx for idx in all_ref_cands if idx in available]

        # عدد الأسماء المختلفة فعليًا (compact) ضمن هذه المجموعة
        distinct_names = {}
        for i in t_idx_list:
            distinct_names.setdefault(target_compact[i], []).append(i)
        n_distinct = len(distinct_names)

        if not avail_cands:
            if all_ref_cands:
                status = CAT_NOT_FOUND
                note = ("كل من يشترك بأول 3 كلمات محجوز مسبقًا لشخص آخر مؤكد "
                        "- لا يوجد سجل متاح فعليًا لهذا الاسم تحديدًا")
                mt = " | ".join(ref_names[c] for c in all_ref_cands)
                ref_idx = list(all_ref_cands)
            else:
                status = CAT_NOT_FOUND
                note = "لا يوجد أي تطابق ولو جزئي (لا حرفي ولا بأول 3 كلمات)"
                mt = ""
                ref_idx = []
            for i in t_idx_list:
                results[i] = (status, mt, note, ref_idx)
            continue

        if len(avail_cands) == 1 and n_distinct == 1:
            # مرشح وحيد لاسم واحد فقط (قد يتكرر السطر نفسه أكثر من مرة)
            ri = avail_cands[0]
            group_rows = t_idx_list
            first = group_rows[0]
            available.discard(ri)
            results[first] = (CAT_HIGH_CONF, ref_names[ri],
                               "تطابق بأول 3 كلمات، مرشح وحيد متاح - يحتاج تأكيد بشري "
                               "(الفرق غالبًا بطول سلسلة النسب/اللقب)", [ri])
            for i in group_rows[1:]:
                results[i] = (CAT_DUPLICATE, ref_names[ri],
                               "الاسم نفسه مكرر بملف الهدف، ومرشح واحد فقط متاح بقاعدة العقود "
                               "- لا يمكن تحديد أي صف يقابله بدون معرّف إضافي", [ri])
            continue

        if len(avail_cands) == 1 and n_distinct > 1:
            # أسماء مختلفة تتنافس على نفس السجل الوحيد المتاح
            ri = avail_cands[0]
            mt = ref_names[ri]
            note = ("نفس السجل بقاعدة العقود هو المرشح الوحيد لأكثر من اسم مختلف بملف الهدف "
                    "(أول 3 كلمات متطابقة لعدة أشخاص لكن يوجد سجل متاح واحد فقط) - يحتاج فرز يدوي "
                    "لتحديد صاحب السجل الحقيقي")
            for i in t_idx_list:
                results[i] = (CAT_CONFLICT, mt, note, [ri])
            continue

        # أكثر من مرشح متاح (أقارب) - جرّب حسم كل صف عبر عمود المدرسة إن توفر
        local_avail = list(avail_cands)
        unresolved_rows = []
        for i in t_idx_list:
            resolved = False
            if target_school_norm is not None and ref_school_norm is not None and local_avail:
                t_sch = target_school_norm[i] if i < len(target_school_norm) else ''
                if t_sch:
                    sch_matches = [ri for ri in local_avail
                                   if ri < len(ref_school_norm) and ref_school_norm[ri] == t_sch]
                    if len(sch_matches) == 1:
                        ri = sch_matches[0]
                        available.discard(ri)
                        local_avail.remove(ri)
                        results[i] = (CAT_CONFIRMED, ref_names[ri],
                                      "تطابق بأول 3 كلمات + تأكيد عبر تطابق عمود المدرسة "
                                      "مع مرشح وحيد من بين عدة مرشحين", [ri])
                        resolved = True
            if not resolved:
                unresolved_rows.append(i)

        if unresolved_rows:
            if local_avail:
                mt = " | ".join(ref_names[c] for c in local_avail)
                note = (f"{len(local_avail)} مرشحين يشتركون بأول 3 كلمات - يحتاج فرز يدوي "
                        "(على الأغلب أقارب بنفس بداية الاسم)")
                cat, ref_idx = CAT_RELATIVES, list(local_avail)
            else:
                mt, cat, ref_idx = "", CAT_NOT_FOUND, []
                note = ("كل المرشحين المشتركين بأول 3 كلمات اعتُمدوا لأشخاص آخرين عبر تطابق "
                        "المدرسة - لا يوجد مرشح متبقٍ لهذا الصف")
            for i in unresolved_rows:
                results[i] = (cat, mt, note, ref_idx)

    # حالات الأسماء القصيرة (أقل من 3 كلمات) التي لم تُحسم مباشرة
    for i in range(n_target):
        if results[i] is not None and results[i][0] == "__SHORT__":
            results[i] = (CAT_NOT_FOUND, "", "اسم قصير جدًا (أقل من 3 كلمات) - لا يمكن تطبيق بوابة أول 3 كلمات", [])

    report(95, "تجهيز النتائج...")

    out = []
    for i in range(n_target):
        cat, mt, note, ref_idx = results[i]
        if ref_idx:
            score = max(similarity_pct(target_compact[i], ref_compact_list[ri])
                        for ri in ref_idx if 0 <= ri < len(ref_compact_list))
        else:
            score = 0.0
        out.append(MatchRow(i, target_names[i], cat, mt or "", note or "", ref_idx, score))

    report(100, "اكتملت المطابقة")
    return out


def summarize(rows):
    """يعيد dict: فئة -> عدد."""
    counts = {c: 0 for c in CATEGORY_ORDER}
    for r in rows:
        counts[r.category] = counts.get(r.category, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# مطابقة قاعدتين معًا (مثلاً: عقود + ملاك) مع دمج النتيجة بصف واحد لكل اسم
# ---------------------------------------------------------------------------

DUAL_BOTH = "both"
DUAL_ONLY1 = "only1"
DUAL_ONLY2 = "only2"
DUAL_REVIEW = "review"
DUAL_NOT_FOUND = "not_found"

DUAL_KIND_ORDER = [DUAL_BOTH, DUAL_ONLY1, DUAL_ONLY2, DUAL_REVIEW, DUAL_NOT_FOUND]

DUAL_KIND_COLOR = {
    DUAL_BOTH: 'C6EFCE',
    DUAL_ONLY1: 'FFEB9C',
    DUAL_ONLY2: 'FFEB9C',
    DUAL_REVIEW: 'FCE4D6',
    DUAL_NOT_FOUND: 'FFC7CE',
}

_NEEDS_REVIEW_CATS = {CAT_HIGH_CONF, CAT_RELATIVES, CAT_CONFLICT, CAT_DUPLICATE}


class DualMatchRow:
    __slots__ = ('idx', 'original_name', 'row1', 'row2', 'status_kind', 'status_label', 'note')

    def __init__(self, idx, original_name, row1, row2, status_kind, status_label, note):
        self.idx = idx
        self.original_name = original_name
        self.row1 = row1              # MatchRow بقاعدة المرجع الأولى
        self.row2 = row2              # MatchRow بقاعدة المرجع الثانية
        self.status_kind = status_kind      # أحد مفاتيح DUAL_KIND_ORDER (للترتيب واللون)
        self.status_label = status_label    # نص عربي جاهز للعرض
        self.note = note


def run_matching_dual(target_names, ref1_names, ref1_label, ref2_names, ref2_label,
                       progress_cb=None, target_school=None, ref1_school=None, ref2_school=None):
    """يطابق نفس ملف الهدف مع قاعدتين مرجعيتين مستقلتين (كل قاعدة بحجزها الخاص)
    ثم يدمج نتيجة كل اسم بصف واحد يوضّح حالته بكل قاعدة والحالة المدمجة.

    يعيد قائمة DualMatchRow بنفس ترتيب target_names.
    """
    def report(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    report(0, f"مطابقة قاعدة {ref1_label}...")
    rows1 = run_matching(target_names, ref1_names,
                          progress_cb=lambda p, m: report(int(p * 0.45), m),
                          target_school=target_school, ref_school=ref1_school)

    report(45, f"مطابقة قاعدة {ref2_label}...")
    rows2 = run_matching(target_names, ref2_names,
                          progress_cb=lambda p, m: report(45 + int(p * 0.45), m),
                          target_school=target_school, ref_school=ref2_school)

    report(92, "دمج نتائج القاعدتين...")
    out = []
    for i, name in enumerate(target_names):
        r1, r2 = rows1[i], rows2[i]
        c1, c2 = r1.category, r2.category
        review1 = c1 in _NEEDS_REVIEW_CATS
        review2 = c2 in _NEEDS_REVIEW_CATS

        if c1 == CAT_CONFIRMED and c2 == CAT_CONFIRMED:
            kind = DUAL_BOTH
            label = "مؤكد بالقاعدتين"
            note = f"موجود ومؤكد بكلتا القاعدتين ({ref1_label} و{ref2_label})"
        elif review1 or review2:
            kind = DUAL_REVIEW
            label = "متشابه/قريب - يحتاج مراجعة"
            parts = []
            if review1:
                parts.append(f"{ref1_label}: {c1} ({r1.match_text or '—'})")
            if review2:
                parts.append(f"{ref2_label}: {c2} ({r2.match_text or '—'})")
            note = "يوجد تشابه أو تقارب بحاجة فرز يدوي - " + " | ".join(parts)
        elif c1 == CAT_CONFIRMED and c2 == CAT_NOT_FOUND:
            kind = DUAL_ONLY1
            label = f"مؤكد بـ{ref1_label} فقط"
            note = f"موجود بـ{ref1_label} ولا يوجد له سجل بـ{ref2_label}"
        elif c2 == CAT_CONFIRMED and c1 == CAT_NOT_FOUND:
            kind = DUAL_ONLY2
            label = f"مؤكد بـ{ref2_label} فقط"
            note = f"موجود بـ{ref2_label} ولا يوجد له سجل بـ{ref1_label}"
        else:
            kind = DUAL_NOT_FOUND
            label = "غير موجود بالقاعدتين"
            note = "لا يوجد أي سجل مطابق بأي من القاعدتين"

        out.append(DualMatchRow(i, name, r1, r2, kind, label, note))

    report(100, "اكتملت مطابقة القاعدتين")
    return out


def summarize_dual(rows):
    """يعيد dict: status_kind -> عدد."""
    counts = {k: 0 for k in DUAL_KIND_ORDER}
    for r in rows:
        counts[r.status_kind] = counts.get(r.status_kind, 0) + 1
    return counts
