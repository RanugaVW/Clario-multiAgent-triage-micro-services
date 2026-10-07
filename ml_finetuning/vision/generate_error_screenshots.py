"""Build a training set of synthetic error screenshots for the Qwen2-VL fine-tune.

The task the model has to learn is "read the error, ignore the interface". So every
image here deliberately surrounds one real error message with the kind of noise
Tesseract falls for: nav bars, buttons, form labels, timestamps, watermarks.

The label is the error text only. Nothing else.

    python generate_error_screenshots.py --n 3000 --out data/vision_train

Produces  <out>/images/*.png  and  <out>/labels.jsonl  with one
{"image": "...", "error": "..."} per line.

The 34 real screenshots in Testing/11 are NEVER used here - they stay held out as
the test set, so the evaluation after fine-tuning is still honest.
"""
from __future__ import annotations

import argparse
import json
import random
import string
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── fonts ────────────────────────────────────────────────────────────────────
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
             "/kaggle/input/dejavu-fonts", "/usr/share/fonts"]


def _find(*names: str) -> str | None:
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return str(p)
    for d in FONT_DIRS:
        hits = sorted(Path(d).rglob(names[0])) if Path(d).exists() else []
        if hits:
            return str(hits[0])
    return None


SANS = _find("DejaVuSans.ttf", "LiberationSans-Regular.ttf")
SANS_B = _find("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf") or SANS
MONO = _find("DejaVuSansMono.ttf", "LiberationMono-Regular.ttf") or SANS


def font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


# ── the error corpus ─────────────────────────────────────────────────────────
# Shapes taken from the real Rysera LMS errors in Testing/11's ground_truth.csv.
# Add your own templates here: the closer these are to what your app really
# prints, the better the fine-tune transfers to the held-out set.
def _uuid() -> str:
    return str(uuid.uuid4())


def _token(n: int = 40) -> str:
    return "".join(random.choices(string.hexdigits.lower(), k=n))


def _file() -> str:
    stem = random.choice(["finalproject", "assignment2", "report", "lecture-notes", "submission",
                          "week3-quiz", "capstone", "thesis-draft", "bank-slip", "receipt",
                          "module4", "practical-5", "group-report"])
    ext = random.choice(["pdf", "pptm", "docx", "zip", "mp4", "xlsx", "png", "jpg"])
    tail = random.choice(["", " [Autosaved]", " [Autosaved] [Autosaved]", " (1)", " (2)", " - Copy"])
    return f"{stem}.{ext}{tail}"


def _order_id() -> str:
    return f"ORD-{random.randint(1000000000000, 1999999999999)}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=7))}"


def _component() -> str:
    comp = random.choice(["CertificateViewer", "CheckoutForm", "EnrolButton", "ProfileCard",
                          "SubmissionUpload", "QuizRunner", "ForumThread", "BatchSelector",
                          "PaymentPanel", "CourseHeader", "VideoPlayer", "GradeTable"])
    hook = random.choice(["useCallback", "useEffect", "useMemo", "onSubmit", "handleClick"])
    inner = random.choice(["render", "load", "submit", "fetchData", "confirm", "upload"])
    return f"{comp}.{hook}[{inner}{random.choice(['', 'Certificate', 'Content', 'Payment'])}]"


def _fields() -> str:
    pool = ["Full Name", "Phone Number", "Address", "City", "Postal Code", "NIC", "Date of Birth",
            "Emergency Contact", "District", "Guardian Name", "Email"]
    return ", ".join(random.sample(pool, k=random.randint(2, 5)))


def _table() -> str:
    return random.choice(["forum_questions", "topic_contents", "enrolments", "submissions",
                          "payments", "certificates", "users", "batches", "quiz_attempts",
                          "ticket_drafts", "resolutions", "course_modules"])


def _column() -> str:
    return random.choice(["user_id", "course_id", "batch_id", "payment_id", "slot", "position",
                          "certificate_id", "submitted_at", "amount"])


def _constraint() -> str:
    return random.choice(["topic_contents_unique_position", "users_email_key", "enrolments_pkey",
                          "submissions_unique_slot", "uq_certificate_serial", "idx_payment_ref",
                          "batches_code_key", "quiz_attempts_unique_try"])


def _bad_uuid() -> str:
    return random.choice(["undefined", "null", "ai-course", "", "NaN", "course-123",
                          "[object Object]", "new", "draft"])


def _bucket() -> str:
    return random.choice(["submissions", "bank-slips", "certificates", "course-media", "avatars"])


def _coupon() -> str:
    return "RYS" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


ERROR_TEMPLATES = [
    # ── Postgres / Supabase ──────────────────────────────────────────────────
    lambda: f'Failed to create content: duplicate key value violates unique constraint "{_constraint()}"',
    lambda: f'duplicate key value violates unique constraint "{_constraint()}"',
    lambda: f'Failed to create question: null value in column "{_column()}" of relation "{_table()}" violates not-null constraint',
    lambda: f'null value in column "{_column()}" of relation "{_table()}" violates not-null constraint',
    lambda: f'invalid input syntax for type uuid: "{_bad_uuid()}"',
    lambda: f'Failed to fetch questions: invalid input syntax for type uuid: "{_bad_uuid()}"',
    lambda: f'Failed to load {random.choice(["submissions", "enrolments", "certificates", "batches", "grades"])}: invalid input syntax for type uuid: "{_bad_uuid()}"',
    lambda: f'insert or update on table "{_table()}" violates foreign key constraint "{random.choice(["fk_course", "fk_user", "fk_batch", "fk_payment"])}"',
    lambda: f"permission denied for {random.choice(['table', 'relation'])} {_table()}",
    lambda: f"Cannot coerce the result to a single JSON {random.choice(['object', 'row', 'record'])}",
    lambda: f"Registration Failed - Failed to register for event: Cannot coerce the result to a single JSON object",
    lambda: f"new row violates row-level security policy for table \"{_table()}\"",

    # ── JSON / parsing ───────────────────────────────────────────────────────
    lambda: f"Unexpected token '{random.choice('TUNIOF<')}', \"{random.choice(['Too many r', 'Internal S', 'Unauthoriz', 'Not Found', 'Forbidden', '<!DOCTYPE '])}\"... is not valid JSON",
    lambda: f"Unexpected end of JSON input",
    lambda: f"SyntaxError: Unexpected token '{random.choice('<{}')}' in JSON at position {random.randint(0, 900)}",

    # ── Next.js / server actions ─────────────────────────────────────────────
    lambda: f'Login Failed - Server Action "{_token(40)}" was not found on the server.',
    lambda: f'Server Action "{_token(40)}" was not found on the server.',
    lambda: f"Application error: a client-side exception has occurred (see the browser console for more information).",

    # ── Auth / permissions ───────────────────────────────────────────────────
    lambda: random.choice(["Sign-in Failed - fetch failed", "Login Failed - network request failed",
                           "Login Failed - could not reach the server"]),
    lambda: random.choice(["Sign-up Failed - Unauthorized", "Registration Failed - Access Denied",
                           "Enrolment Failed - Unauthorized"]),
    lambda: f"Unauthorized (Console Error - {_component()})",
    lambda: 'Login Failed - Forbidden (response: {"success":false,"error":"Forbidden"})',
    lambda: f"{random.choice(['Admins', 'Instructors', 'Staff accounts'])} cannot enroll - these accounts are restricted from purchasing or enrolling in courses.",
    lambda: f"Session expired. Please sign in again. (code: {random.choice(['AUTH_401', 'TOKEN_EXPIRED', 'JWT_MALFORMED', 'REFRESH_FAILED'])})",
    lambda: f"Access denied - your role ({random.choice(['student', 'guest', 'auditor'])}) cannot view this page.",

    # ── Uploads / storage ────────────────────────────────────────────────────
    lambda: f"Upload failed: Invalid key: {_bucket()}/{_uuid()}/{_uuid()}/{_file()}",
    lambda: f"Upload failed: Invalid key: {_bucket()}/{_uuid()}/{_file()}",
    lambda: f"Upload failed: {random.choice(['Bucket', 'Container', 'Storage path'])} not found",
    lambda: f"Upload failed - We couldn't upload your {random.choice(['bank slip', 'payment receipt', 'proof of payment'])}. Please try again.",
    lambda: f"Upload failed - Failed to upload {random.choice(['bank slip', 'receipt', 'assignment file', 'profile photo'])}",
    lambda: f"Upload failed: file exceeds the {random.choice([5, 10, 25, 50, 100, 500])}MB limit",
    lambda: f"Failed to generate signed URL: Object not found",
    lambda: f"Failed to generate signed URL: Object not found (Console Error - {_component()})",
    lambda: f"Failed to generate signed URL: {random.choice(['Object not found', 'Bucket not found', 'Access denied'])}",

    # ── Payments ─────────────────────────────────────────────────────────────
    lambda: f"Payment failed. Please try again or contact support. (Order ID: {_order_id()})",
    lambda: f"{random.choice(['PayHere', 'WebXpay', 'Stripe'])} payment declined: {random.choice(['insufficient funds', 'card expired', 'issuer declined', 'do not honour', 'invalid CVV'])}",
    lambda: f"Invalid coupon format (e.g., {_coupon()})",
    lambda: f"Coupon {_coupon()} has expired or has already been used.",
    lambda: f"Payment verification pending - we could not match your bank slip to order {_order_id()}.",

    # ── Certificates ─────────────────────────────────────────────────────────
    lambda: f"Certificate Not Found - This link is {random.choice(['invalid', 'expired', 'not yet approved'])}, or the certificate no longer exists.",
    lambda: f"Name is too long for this certificate ({random.randint(660, 980)}px > {random.randint(600, 659)}px). Try shorter initials.",
    lambda: f"Certificate generation failed: {random.choice(['template missing', 'font not embedded', 'signature image unavailable'])}",

    # ── Profile / validation ─────────────────────────────────────────────────
    lambda: f"Please complete your profile before enrolling. Missing: {_fields()}",
    lambda: f"Invalid {random.choice(['contentId', 'moduleId', 'lessonId', 'topicId'])}",
    lambda: f"Missing {random.choice(['contentId', 'moduleId', 'batchId', 'topicId'])}",
    lambda: f"Missing required field: {random.choice(['batchId', 'courseId', 'submissionId', 'quizId'])}",

    # ── Generic / network / runtime ──────────────────────────────────────────
    lambda: random.choice(["Something went wrong. Please try again.",
                           "An unexpected error occurred. Refresh the page and try again.",
                           "Sorry, something broke on our side. Please retry in a moment.",
                           "We hit an unexpected problem. Try again shortly."]),
    lambda: f"Failed to load {random.choice(['submissions', 'questions', 'certificates', 'batches', 'course content', 'grades'])}",
    lambda: f"TypeError: Cannot read properties of {random.choice(['undefined', 'null'])} (reading '{random.choice(['map', 'id', 'length', 'title', 'status', 'url', 'name'])}')",
    lambda: f"Error: connect ETIMEDOUT {'.'.join(str(random.randint(1, 254)) for _ in range(4))}:{random.choice([5432, 6379, 443, 8080, 3000])}",
    lambda: f"Request failed with status code {random.choice([400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504])}",
    lambda: f"Failed to fetch: {random.choice(['NetworkError when attempting to fetch resource', 'Load failed', 'The operation was aborted'])}",
    lambda: f"Quota exceeded: you have used {random.randint(100, 500)} of {random.randint(100, 500)} requests for today.",
    lambda: f"Could not save changes - row was modified by another user (version {random.randint(2, 40)}).",
    lambda: f"Video processing failed: {random.choice(['unsupported codec', 'file too large', 'corrupt container', 'audio track missing'])}",
    lambda: f"{random.choice(['TypeError', 'ReferenceError', 'RangeError'])}: {random.choice(['x is not a function', 'y is not defined', 'Maximum call stack size exceeded'])} (Console Error - {_component()})",
]

# ── interface noise ──────────────────────────────────────────────────────────
# Real screens are full of plausible-looking data: names, emails, phone numbers,
# dates, grades. That is exactly what the model has to learn to ignore - an email
# address looks far more "important" than a button label, so it is the harder and
# more useful distractor.
NAV = ["Dashboard", "My Courses", "Assignments", "Grades", "Calendar", "Messages", "Settings",
       "Library", "Discussions", "Certificates", "Profile", "Help", "Reports", "Batches"]
BUTTONS = ["Save", "Cancel", "Submit", "Upload", "Browse", "Remove", "Add", "Retry", "Close",
           "Minimize", "Continue", "Back", "Next", "Download", "Share", "Approve", "Export"]
FILLER = ["Drop PDF files here or click to browse", "Selected files:", "No items yet",
          "Showing 1-10 of 42", "Last updated 2 minutes ago", "All changes saved",
          "Autosaving...", "rysera.com/learn", "system.rysera.com", "3 unread notifications"]

FIRST = ["Nimal", "Kavindi", "Dilshan", "Sanduni", "Tharindu", "Amaya", "Ruwan", "Hiruni",
         "Chamath", "Nethmi", "Pasindu", "Ishara", "Yasiru", "Dinusha", "Sahan", "Oshadi"]
LAST = ["Perera", "Fernando", "Silva", "Jayasuriya", "Bandara", "Rathnayake", "Wickrama",
        "Gunasekara", "Alwis", "Dissanayake", "Ekanayake", "Weerasinghe"]
COURSES = ["Intro to AI", "Data Structures", "Web Development", "Machine Learning Basics",
           "Cloud Fundamentals", "Database Systems", "Mobile App Development", "Cyber Security",
           "Python for Beginners", "UI/UX Design", "Statistics for DS", "DevOps Essentials"]
STATUSES = [("Approved", "#1A7F4B"), ("Pending", "#B5730B"), ("Overdue", "#B3261E"),
            ("Submitted", "#2F5FBF"), ("Graded", "#5B3BA6"), ("Draft", "#6B7280")]


def _person(rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _email(rng, name: str) -> str:
    f, l = name.lower().split()
    return f"{f}.{l[:4]}{rng.randint(0, 99)}@{rng.choice(['rysera.lk', 'gmail.com', 'student.rysera.lk', 'yahoo.com'])}"


def _phone(rng) -> str:
    return rng.choice([f"+94 7{rng.randint(0,8)} {rng.randint(100,999)} {rng.randint(1000,9999)}",
                       f"07{rng.randint(0,8)}-{rng.randint(100,999)}-{rng.randint(1000,9999)}",
                       f"011 {rng.randint(200,299)} {rng.randint(1000,9999)}"])


def _date(rng) -> str:
    return f"{rng.randint(1,28)} {rng.choice(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])} 202{rng.randint(4,6)}"


THEMES = [
    # bg, panel, text, muted, chrome, error_bg, error_fg
    ("#FFFFFF", "#F4F5F7", "#1F2328", "#8A8F98", "#E6E8EB", "#FDECEA", "#B3261E"),
    ("#FAFAFA", "#FFFFFF", "#202124", "#9AA0A6", "#DADCE0", "#FCE8E6", "#C5221F"),
    ("#12141A", "#1B1E26", "#E6E8EB", "#767C87", "#262A33", "#2C1618", "#F2746B"),
    ("#0D1117", "#161B22", "#C9D1D9", "#6E7681", "#21262D", "#3A1417", "#FF7B72"),
    ("#F7F9FC", "#FFFFFF", "#111827", "#6B7280", "#E5E7EB", "#FEF2F2", "#DC2626"),
]


def rint(rng, lo: int, hi: int) -> int:
    """randint that survives narrow layouts, where a computed hi can fall below lo."""
    lo, hi = int(lo), int(hi)
    if hi < lo:
        lo, hi = hi, lo
    return rng.randint(lo, hi)


def wrap(draw, text: str, fnt, max_w: int) -> list[str]:
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # a very long unbroken token (a uuid path) still has to be cut
    out = []
    for ln in lines:
        while draw.textlength(ln, font=fnt) > max_w and len(ln) > 4:
            cut = max(4, int(len(ln) * max_w / max(1, draw.textlength(ln, font=fnt))))
            out.append(ln[:cut])
            ln = ln[cut:]
        out.append(ln)
    return out


def render(error: str, rng: random.Random) -> Image.Image:
    w, h = rng.choice([(1280, 800), (1366, 768), (1024, 768), (1440, 900), (900, 1400),
                       (1536, 864), (820, 1180), (480, 900), (1600, 900), (1180, 820)])
    bg, panel, text, muted, chrome, err_bg, err_fg = rng.choice(THEMES)
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)

    f_nav = font(SANS, rng.randint(13, 16))
    f_body = font(SANS, rng.randint(13, 17))
    f_small = font(SANS, rng.randint(11, 13))
    f_err = font(rng.choice([SANS, SANS_B, MONO]), rng.randint(14, 19))
    f_title = font(SANS_B, rng.randint(18, 24))

    # top chrome
    d.rectangle([0, 0, w, 56], fill=chrome)
    brand = rng.choice(["Rysera LMS", "Learning Portal", "Course Manager"])
    d.text((20, 20), brand, font=f_title, fill=text)
    x = 20 + int(d.textlength(brand, font=f_title)) + rng.randint(28, 56)
    nav_limit = w - 340  # keep clear of the signed-in user label on the right
    for item in rng.sample(NAV, k=rng.randint(4, 7)):
        if x + d.textlength(item, font=f_nav) > nav_limit:
            break
        d.text((x, 22), item, font=f_nav, fill=muted)
        x += int(d.textlength(item, font=f_nav)) + rng.randint(24, 44)
    who = _person(rng)
    d.text((w - 320, 22), f"{who}  ·  {rng.randint(1,23):02d}:{rng.randint(0,59):02d}", font=f_small, fill=muted)
    if rng.random() < 0.5:
        d.text((32, 68), " / ".join(rng.sample(NAV, k=rng.randint(2, 3))), font=f_small, fill=muted)

    # optional sidebar
    content_x = 32
    if w >= 900 and rng.random() < 0.45:
        d.rectangle([0, 56, 210, h], fill=panel)
        y = 84
        for item in rng.sample(NAV, k=rng.randint(5, 8)):
            d.text((24, y), item, font=f_nav, fill=muted)
            y += rng.randint(34, 46)
        content_x = 244

    # a content panel - a filled form, a data table, or a list of course cards
    py = rint(rng, 90, 150)
    pw = w - content_x - 32
    ph = rint(rng, 240, max(260, min(430, h - 240)))
    d.rounded_rectangle([content_x, py, content_x + pw, py + ph], radius=10, fill=panel)
    block = rng.choice(["form", "table", "cards"])
    y = py + 20

    if block == "form":
        person = _person(rng)
        vals = [("Full Name", person), ("Email", _email(rng, person)), ("Phone Number", _phone(rng)),
                ("Course", rng.choice(COURSES)), ("Due Date", _date(rng)),
                ("Batch", f"B-{rng.randint(10,48)}"), ("NIC", f"{rng.randint(70,99)}{rng.randint(1000000,9999999)}V"),
                ("City", rng.choice(["Colombo", "Kandy", "Galle", "Negombo", "Matara", "Jaffna"]))]
        for lab, val in rng.sample(vals, k=rng.randint(3, 5)):
            d.text((content_x + 20, y), lab, font=f_small, fill=muted)
            bw = rint(rng, min(240, pw - 60), max(140, min(460, pw - 60)))
            d.rounded_rectangle([content_x + 20, y + 18, content_x + 20 + bw, y + 48],
                                radius=6, outline=chrome, width=1)
            d.text((content_x + 32, y + 26), val, font=f_body, fill=text)
            y += 64
            if y > py + ph - 70:
                break

    elif block == "table":
        cols = [("Student", 190), ("Email", 230), ("Phone", 150), ("Status", 100)]
        cx = content_x + 20
        for name, cw_ in cols:
            if cx + cw_ < content_x + pw - 20:
                d.text((cx, y), name, font=font(SANS_B, f_small.size), fill=muted)
            cx += cw_
        y += 26
        d.line([content_x + 20, y, content_x + pw - 20, y], fill=chrome, width=1)
        y += 10
        for _ in range(rng.randint(3, 6)):
            if y > py + ph - 40:
                break
            person = _person(rng)
            cells = [person, _email(rng, person), _phone(rng), None]
            cx = content_x + 20
            for (lab, cw_), val in zip(cols, cells):
                if cx + cw_ > content_x + pw - 20:
                    break
                if val is None:
                    st, sc = rng.choice(STATUSES)
                    d.rounded_rectangle([cx, y - 2, cx + int(d.textlength(st, font=f_small)) + 20, y + 20],
                                        radius=9, fill=sc)
                    d.text((cx + 10, y + 1), st, font=f_small, fill="#FFFFFF")
                else:
                    d.text((cx, y), val, font=f_small, fill=text if cx == content_x + 20 else muted)
                cx += cw_
            y += 34

    else:  # cards
        for _ in range(rng.randint(2, 4)):
            if y > py + ph - 78:
                break
            cw_ = pw - 40
            d.rounded_rectangle([content_x + 20, y, content_x + 20 + cw_, y + 64], radius=8,
                                outline=chrome, width=1)
            ini = "".join(p[0] for p in _person(rng).split())
            d.ellipse([content_x + 32, y + 14, content_x + 68, y + 50], fill=chrome)
            d.text((content_x + 42, y + 24), ini, font=font(SANS_B, f_small.size), fill=text)
            d.text((content_x + 82, y + 14), rng.choice(COURSES), font=f_body, fill=text)
            d.text((content_x + 82, y + 38), f"{rng.randint(1,24)} lessons  ·  {rng.randint(5,100)}% complete  ·  due {_date(rng)}",
                   font=f_small, fill=muted)
            pw_bar = int((cw_ - 120) * rng.random())
            d.rounded_rectangle([content_x + 82, y + 56, content_x + 82 + max(8, pw_bar), y + 60],
                                radius=2, fill=muted)
            y += 76

    for t in rng.sample(FILLER, k=rng.randint(1, 2)):
        if y < py + ph - 26:
            d.text((content_x + 20, y), t, font=f_small, fill=muted)
            y += 24
    bx = content_x + 20
    for b in rng.sample(BUTTONS, k=rng.randint(2, 4)):
        bw = int(d.textlength(b, font=f_small)) + 28
        if bx + bw > content_x + pw - 20:
            break
        d.rounded_rectangle([bx, py + ph - 46, bx + bw, py + ph - 16], radius=6, fill=chrome)
        d.text((bx + 14, py + ph - 39), b, font=f_small, fill=text)
        bx += bw + 12

    # the error itself - toast, banner, modal or bare console line
    style = rng.choice(["toast", "banner", "modal", "console"])
    max_w = pw - 72
    lines = wrap(d, error, f_err, max_w)
    lh = (f_err.size + 7)
    box_h = len(lines) * lh + 46
    if style == "toast":
        ex, ey, ew = w - min(520, pw) - 24, h - box_h - 40, min(520, pw)
        lines = wrap(d, error, f_err, ew - 48)
        box_h = len(lines) * lh + 46
    elif style == "modal":
        ew = min(680, pw)
        ex, ey = (w - ew) // 2, (h - box_h) // 2
        lines = wrap(d, error, f_err, ew - 48)
        box_h = len(lines) * lh + 46
        d.rectangle([0, 0, w, h], fill=None)
    elif style == "banner":
        ex, ey, ew = content_x, py + ph + 24, pw
    else:  # console
        ex, ey, ew = content_x, py + ph + 24, pw

    if style == "console":
        d.rectangle([ex, ey, ex + ew, ey + box_h], fill="#0B0D11")
        d.text((ex + 16, ey + 14), "Console", font=f_small, fill="#6E7681")
        for i, ln in enumerate(lines):
            d.text((ex + 16, ey + 34 + i * lh), ln, font=font(MONO, f_err.size), fill="#FF7B72")
    else:
        d.rounded_rectangle([ex, ey, ex + ew, ey + box_h], radius=8, fill=err_bg,
                            outline=err_fg, width=rng.choice([0, 1, 2]))
        head = rng.choice(["Error", "ERROR", "Something went wrong", "Failed", "Alert"])
        d.text((ex + 20, ey + 12), head, font=font(SANS_B, f_err.size), fill=err_fg)
        for i, ln in enumerate(lines):
            d.text((ex + 20, ey + 14 + (i + 1) * lh), ln, font=f_err, fill=err_fg)

    # watermark / footer noise
    if rng.random() < 0.5:
        d.text((w - 190, h - 28), rng.choice(FILLER), font=f_small, fill=muted)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--out", type=Path, default=Path("data/vision_train"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--exclude", type=Path, default=None,
                    help="CSV/JSONL/TXT of held-out error strings that must never be generated")
    args = ap.parse_args()

    blocked: set[str] = set()
    if args.exclude and args.exclude.exists():
        raw = args.exclude.read_text(encoding="utf-8-sig")
        if args.exclude.suffix == ".csv":
            import csv as _csv
            for r in _csv.DictReader(raw.splitlines()):
                for k in ("Original Error", "error", "Error"):
                    if k in r and r[k]:
                        blocked.add(r[k].strip())
        else:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    line = json.loads(line).get("error", "")
                if line:
                    blocked.add(line.strip())
        print(f"Excluding {len(blocked)} held-out strings - none will appear in training.")

    rng = random.Random(args.seed)
    random.seed(args.seed)
    img_dir = args.out / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    with open(args.out / "labels.jsonl", "w", encoding="utf-8") as f:
        seen: set[str] = set()
        for i in range(args.n):
            for _ in range(200):
                error = rng.choice(ERROR_TEMPLATES)()
                if error not in seen and error.strip() not in blocked:
                    break
            else:
                continue
            seen.add(error)
            img = render(error, rng)
            name = f"err_{i:05d}.png"
            img.save(img_dir / name, optimize=True)
            f.write(json.dumps({"image": f"images/{name}", "error": error}) + "\n")
            if (i + 1) % 250 == 0:
                print(f"  {i + 1}/{args.n}")

    print(f"Wrote {args.n} images to {img_dir} and labels.jsonl beside it.")
    print(f"Distinct error strings: {len(seen)} / {args.n}")
    print(f"Overlap with the held-out set: {len(seen & blocked)} (must be 0)")
    print("The 34 real screenshots in Testing/11 are untouched - keep them as the test set.")


if __name__ == "__main__":
    main()
