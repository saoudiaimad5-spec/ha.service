import os, sqlite3, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "ha_service.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "private_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("HA_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "txt", "odt", "xlsx"}
STATUSES = ["جديد", "تم التواصل", "قيد الإنجاز", "جاهز للاستلام", "تم التسليم", "ملغي"]

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL, customer_name TEXT NOT NULL,
            phone TEXT NOT NULL, email TEXT, category TEXT NOT NULL,
            service TEXT NOT NULL, details TEXT NOT NULL, quantity TEXT,
            deadline TEXT, delivery TEXT NOT NULL, payment TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'جديد', notes TEXT DEFAULT '',
            filename TEXT DEFAULT '', payment_status TEXT DEFAULT 'غير مدفوع'
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )""")
        row = db.execute("SELECT id FROM admin_users WHERE username='admin'").fetchone()
        if not row:
            # Change these credentials before putting the site online.
            db.execute("INSERT INTO admin_users(username,password_hash) VALUES(?,?)",
                       ("aimad", generate_password_hash(os.environ.get("0559910060jsk"))))
        db.commit()

init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def common():
    return {"statuses": STATUSES, "year": datetime.now().year}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/order", methods=["POST"])
def create_order():
    fields = ["customer_name", "phone", "email", "category", "service", "details", "quantity", "deadline", "delivery", "payment"]
    data = {f: request.form.get(f, "").strip() for f in fields}
    required = ["customer_name", "phone", "category", "service", "details", "delivery", "payment"]
    if any(not data[x] for x in required) or not request.form.get("consent"):
        flash("يرجى ملء الحقول المطلوبة والموافقة على معالجة الطلب.", "error")
        return redirect(url_for("index") + "#request")
    upload = request.files.get("attachment")
    stored_name = ""
    if upload and upload.filename:
        if not allowed_file(upload.filename):
            flash("نوع الملف غير مسموح. استخدم PDF أو DOCX أو صورة أو ملفًا مدعومًا.", "error")
            return redirect(url_for("index") + "#request")
        stored_name = secrets.token_hex(16) + "_" + secure_filename(upload.filename)
        upload.save(os.path.join(UPLOAD_DIR, stored_name))
    with connect() as db:
        cur = db.execute("""INSERT INTO orders
          (created_at, customer_name, phone, email, category, service, details, quantity, deadline, delivery, payment, filename)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          (datetime.now().isoformat(timespec="minutes"), data["customer_name"], data["phone"], data["email"],
           data["category"], data["service"], data["details"], data["quantity"], data["deadline"],
           data["delivery"], data["payment"], stored_name))
        order_id = cur.lastrowid
        db.commit()
    flash(f"تم تسجيل طلبك بنجاح. رقم الطلب: HA-{order_id:05d}. سيتواصل معك المكتب لتأكيد السعر والمدة.", "success")
    return redirect(url_for("index") + "#request")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect() as db:
            user = db.execute("SELECT * FROM admin_users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["admin_id"] = user["id"]
            session["admin_name"] = user["username"]
            return redirect(url_for("admin_dashboard"))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "error")
    return render_template("login.html")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    with connect() as db:
        totals = {
          "all": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
          "new": db.execute("SELECT COUNT(*) FROM orders WHERE status='جديد'").fetchone()[0],
          "progress": db.execute("SELECT COUNT(*) FROM orders WHERE status='قيد الإنجاز'").fetchone()[0],
          "ready": db.execute("SELECT COUNT(*) FROM orders WHERE status='جاهز للاستلام'").fetchone()[0],
        }
        sql = "SELECT * FROM orders WHERE 1=1"
        args = []
        if q:
            sql += " AND (customer_name LIKE ? OR phone LIKE ? OR service LIKE ? OR CAST(id AS TEXT)=?)"
            args.extend([f"%{q}%", f"%{q}%", f"%{q}%", q.replace("HA-", "").lstrip("0")])
        if status in STATUSES:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT 300"
        orders = db.execute(sql, args).fetchall()
    return render_template("admin.html", orders=orders, totals=totals, q=q, selected_status=status)

@app.route("/admin/order/<int:order_id>", methods=["POST"])
@admin_required
def update_order(order_id):
    status = request.form.get("status", "")
    notes = request.form.get("notes", "").strip()[:3000]
    payment_status = request.form.get("payment_status", "غير مدفوع")
    if status not in STATUSES:
        abort(400)
    if payment_status not in ["غير مدفوع", "بانتظار الدفع", "مدفوع في المكتب", "مدفوع إلكترونيًا", "مسترد"]:
        abort(400)
    with connect() as db:
        db.execute("UPDATE orders SET status=?, notes=?, payment_status=? WHERE id=?",
                   (status, notes, payment_status, order_id))
        db.commit()
    flash(f"تم تحديث الطلب HA-{order_id:05d}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/file/<int:order_id>")
@admin_required
def download_order_file(order_id):
    with connect() as db:
        row = db.execute("SELECT filename FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row or not row["filename"]:
        abort(404)
    return send_from_directory(UPLOAD_DIR, row["filename"], as_attachment=True)

@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        if len(new) < 12:
            flash("يجب أن تتكون كلمة المرور الجديدة من 12 حرفًا على الأقل.", "error")
        else:
            with connect() as db:
                user = db.execute("SELECT * FROM admin_users WHERE id=?", (session["admin_id"],)).fetchone()
                if user and check_password_hash(user["password_hash"], current):
                    db.execute("UPDATE admin_users SET password_hash=? WHERE id=?",
                               (generate_password_hash(new), session["admin_id"]))
                    db.commit()
                    flash("تم تغيير كلمة المرور.", "success")
                    return redirect(url_for("admin_dashboard"))
                flash("كلمة المرور الحالية غير صحيحة.", "error")
    return render_template("change_password.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
