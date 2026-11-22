from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import secrets
import hashlib
import math
import re
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import care
from flask import session, redirect, url_for, abort

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DATABASE = "healthcare.db"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# CREATE DATABASE TABLES
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            status TEXT DEFAULT 'pending'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            qualification TEXT NOT NULL,
            experience INTEGER,
            availability TEXT,
            consultation_fee REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_type TEXT NOT NULL CHECK (target_type IN ('hospital', 'doctor')),
            target_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, target_type, target_id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not email or not password:
            flash("Please fill in all fields.")

        elif password != confirm:
            flash("Passwords do not match.")

        elif len(password) < 8:
            flash("Password must be at least 8 characters.")

        else:
            conn = get_db()

            try:
                conn.execute(
                    "INSERT INTO users (email, password) VALUES (?, ?)",
                    (email, generate_password_hash(password))
                )

                conn.commit()
                flash("Registration successful. Please log in.")
                return redirect(url_for("login"))

            except sqlite3.IntegrityError:
                flash("This email is already registered.")

            finally:
                conn.close()

    return render_template("register.html")

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        try:
            admin = conn.execute(
                "SELECT * FROM admins WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin email or password.")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():

    conn = get_db()

    hospitals = conn.execute(
        "SELECT * FROM hospitals"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        hospitals=hospitals
    )

# ADMIN VIEW HOSPITAL DOCTORS
@app.route("/admin-hospital-doctors/<int:hospital_id>")
@admin_required
def admin_hospital_doctors(hospital_id):

    conn = get_db()

    hospital = conn.execute(
        "SELECT * FROM hospitals WHERE id = ?",
        (hospital_id,)
    ).fetchone()

    if not hospital:
        conn.close()
        flash("Hospital not found.")
        return redirect(url_for("admin_dashboard"))

    doctors = conn.execute("""
        SELECT * FROM doctors
        WHERE hospital_id = ?
    """, (hospital_id,)).fetchall()

    conn.close()

    return render_template(
        "admin_hospital_doctors.html",
        hospital=hospital,
        doctors=doctors
    )

# APPROVE HOSPITAL
@app.route("/approve-hospital/<int:hospital_id>", methods=["POST"])
@admin_required
def approve_hospital(hospital_id):

    conn = get_db()

    hospital = conn.execute(
        "SELECT id FROM hospitals WHERE id = ?",
        (hospital_id,)
    ).fetchone()

    if hospital:
        conn.execute(
            "UPDATE hospitals SET status = 'approved' WHERE id = ?",
            (hospital_id,)
        )
        conn.commit()
        flash("Hospital approved successfully!")
    else:
        flash("Hospital not found.")

    conn.close()

    return redirect(url_for("admin_dashboard"))


# REJECT HOSPITAL
@app.route("/reject-hospital/<int:hospital_id>", methods=["POST"])
@admin_required
def reject_hospital(hospital_id):

    conn = get_db()

    hospital = conn.execute(
        "SELECT id FROM hospitals WHERE id = ?",
        (hospital_id,)
    ).fetchone()

    if hospital:
        conn.execute(
            "UPDATE hospitals SET status = 'rejected' WHERE id = ?",
            (hospital_id,)
        )
        conn.commit()
        flash("Hospital rejected successfully!")
    else:
        flash("Hospital not found.")

    conn.close()

    return redirect(url_for("admin_dashboard"))

# ADMIN LOGOUT
@app.route("/admin-logout")
def admin_logout():

    session.pop("admin_id", None)

    flash("Admin logged out successfully.")

    return redirect(url_for("admin_login"))

# HOSPITAL REGISTRATION
@app.route("/hospital-register", methods=["GET", "POST"])
def hospital_register():

    if request.method == "POST":

        hospital_name = request.form.get("hospital_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        latitude = parse_coordinate(request.form.get("latitude"), 90)
        longitude = parse_coordinate(request.form.get("longitude"), 180)

        if not all([hospital_name, email, password, phone,
                    address, city, state]):
            flash("Please fill in all fields.")
            return render_template("hospital_register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("hospital_register.html")

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO hospitals
                (hospital_name, email, password, phone,
                 address, city, state, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hospital_name,
                email,
                generate_password_hash(password),
                phone,
                address,
                city,
                state,
                latitude,
                longitude
            ))

            conn.commit()
            flash("Hospital registration successful! Waiting for admin approval.")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("This hospital email is already registered.")

        finally:
            conn.close()

    return render_template("hospital_register.html")

# HOSPITAL LOGIN
@app.route("/hospital-login", methods=["GET", "POST"])
def hospital_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        hospital = conn.execute(
            "SELECT * FROM hospitals WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if hospital and check_password_hash(
            hospital["password"], password
        ):

            if hospital["status"] != "approved":
                flash("Your hospital account is waiting for admin approval.")
                return redirect(url_for("hospital_login"))

            session.clear()
            session["hospital_id"] = hospital["id"]
            session["hospital_name"] = hospital["hospital_name"]

            return redirect(url_for("hospital_dashboard"))

        flash("Invalid email or password.")

    return render_template("hospital_login.html")


# HOSPITAL DASHBOARD
@app.route("/hospital-dashboard")
def hospital_dashboard():

    if "hospital_id" not in session:
        return redirect(url_for("hospital_login"))

    return render_template(
        "hospital_dashboard.html",
        hospital_name=session["hospital_name"]
    )

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# HEALTH INFORMATION PAGE
@app.route("/health")
def health():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("health.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        email=session["email"]
    )


# SMARTHEALTH CHATBOT
@app.route("/chat", methods=["POST"])
def chat():

    if "user_id" not in session:
        return jsonify({
            "error": "Please log in first."
        }), 401

    data = request.get_json(silent=True) or {}

    message = data.get("message", "").lower().strip()

    if not message:
        return jsonify({
            "error": "Please enter your symptoms."
        }), 400

    # EMERGENCY SYMPTOMS
    emergency_words = [
        "chest pain",
        "difficulty breathing",
        "can't breathe",
        "cannot breathe",
        "severe bleeding",
        "fainting",
        "unconscious",
        "stroke",
        "face drooping",
        "sudden weakness"
    ]

    if any(word in message for word in emergency_words):

        reply = (
            "⚠️ EMERGENCY WARNING\n\n"
            "Your symptoms may indicate a serious medical emergency.\n\n"
            "Please seek emergency medical care immediately.\n"
            "In India, call 112.\n\n"
            "Do not wait for chatbot advice."
        )

    # FEVER
    elif "fever" in message:

        reply = (
            "🤒 FEVER INFORMATION\n\n"
            "Possible causes include infections and other illnesses.\n\n"
            "GENERAL PRECAUTIONS:\n"
            "1. Take adequate rest.\n"
            "2. Drink enough fluids.\n"
            "3. Monitor your temperature.\n"
            "4. Avoid strenuous activity.\n"
            "5. Consult a doctor if symptoms persist or worsen.\n\n"
            "Please tell me:\n"
            "1. How many days have you had fever?\n"
            "2. Do you have cough or headache?\n"
            "3. Are you experiencing chills?"
        )

    # HEADACHE
    elif "headache" in message or "migraine" in message:

        reply = (
            "🤕 HEADACHE INFORMATION\n\n"
            "Possible causes include stress, dehydration, "
            "lack of sleep or migraine.\n\n"
            "PRECAUTIONS:\n"
            "1. Rest in a quiet place.\n"
            "2. Drink enough water.\n"
            "3. Eat regular meals.\n"
            "4. Maintain proper sleep.\n"
            "5. Consult a doctor if the pain continues.\n\n"
            "A sudden, extremely severe headache needs emergency care."
        )

    # COLD AND COUGH
    elif "cold" in message or "cough" in message or "sneezing" in message:

        reply = (
            "🤧 COLD AND COUGH INFORMATION\n\n"
            "Possible causes include viral respiratory infections "
            "or allergies.\n\n"
            "PRECAUTIONS:\n"
            "1. Get enough rest.\n"
            "2. Drink plenty of fluids.\n"
            "3. Cover your mouth when coughing.\n"
            "4. Wash your hands regularly.\n"
            "5. Consult a doctor if symptoms worsen.\n\n"
            "Are you also experiencing fever or breathing difficulty?"
        )

    # STOMACH PAIN
    elif "stomach pain" in message or "stomach ache" in message:

        reply = (
            "🍽️ STOMACH PAIN INFORMATION\n\n"
            "Possible causes include indigestion, constipation "
            "or infections.\n\n"
            "PRECAUTIONS:\n"
            "1. Drink enough water.\n"
            "2. Eat light meals if tolerated.\n"
            "3. Avoid foods that make symptoms worse.\n"
            "4. Monitor your symptoms.\n"
            "5. Consult a doctor if pain continues.\n\n"
            "Severe or sudden stomach pain needs urgent medical assessment."
        )

    # ALLERGY
    elif "allergy" in message or "itching" in message or "rash" in message:

        reply = (
            "🌿 ALLERGY INFORMATION\n\n"
            "Possible symptoms include itching, sneezing, "
            "watery eyes and skin rashes.\n\n"
            "PRECAUTIONS:\n"
            "1. Avoid known allergy triggers.\n"
            "2. Keep your surroundings clean.\n"
            "3. Avoid scratching affected skin.\n"
            "4. Consult a healthcare professional.\n\n"
            "If you have swelling of the tongue or throat "
            "or difficulty breathing, seek emergency care immediately."
        )

    # DIABETES
    elif "diabetes" in message or "sugar" in message:

        reply = (
            "💙 DIABETES INFORMATION\n\n"
            "Diabetes affects how the body regulates blood glucose.\n\n"
            "GENERAL PRECAUTIONS:\n"
            "1. Monitor blood glucose as advised.\n"
            "2. Follow a balanced diet.\n"
            "3. Stay physically active if appropriate.\n"
            "4. Attend regular medical checkups.\n"
            "5. Follow your doctor's treatment plan.\n\n"
            "A blood test and medical evaluation are needed "
            "to determine whether someone has diabetes."
        )

    # SLEEP PROBLEMS
    elif "sleep" in message or "insomnia" in message:

        reply = (
            "😴 SLEEP INFORMATION\n\n"
            "Sleep difficulties can be related to stress, "
            "irregular schedules or other health conditions.\n\n"
            "PRECAUTIONS:\n"
            "1. Maintain a regular sleep schedule.\n"
            "2. Avoid caffeine close to bedtime.\n"
            "3. Reduce screen time before sleeping.\n"
            "4. Keep your bedroom comfortable.\n"
            "5. Consult a doctor if the problem continues."
        )

    # GENERAL HEALTH QUESTIONS
    else:

        reply = (
            "💙 Welcome to SmartHealth Assistant!\n\n"
            "I need a little more information to guide you.\n\n"
            "Please tell me:\n"
            "1. What symptoms are you experiencing?\n"
            "2. How many days have you had these symptoms?\n"
            "3. Are your symptoms mild, moderate or severe?\n"
            "4. Do you have any other symptoms?\n\n"
            "I can provide general health information "
            "and precautions, but I cannot diagnose diseases."
        )

    # SMART MEDICAL RECOMMENDATION
    # Step 2 of the flow: decide urgency and which kind of doctor is relevant.
    # This is guidance only - the bot never claims to diagnose a disease.
    response = {"reply": reply}

    urgent = care.is_urgent(message)
    condition = care.detect_condition(message)

    if urgent or condition:
        response["care"] = {
            "urgency": "urgent" if urgent else "low",
            "condition": condition["name"] if condition else "Medical attention",
            "specializations": (
                condition["specializations"] if condition
                else ["General Physician"]
            ),
        }

    return jsonify(response)

# HOSPITAL LOGOUT
@app.route("/hospital-logout")
def hospital_logout():

    session.pop("hospital_id", None)
    session.pop("hospital_name", None)

    flash("Hospital logged out successfully.")

    return redirect(url_for("hospital_login"))

# ADD DOCTOR
@app.route("/add-doctor", methods=["GET", "POST"])
def add_doctor():

    if "hospital_id" not in session:
        return redirect(url_for("hospital_login"))

    if request.method == "POST":

        doctor_name = request.form.get("doctor_name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        qualification = request.form.get("qualification", "").strip()
        experience = request.form.get("experience", "")
        availability = request.form.get("availability", "").strip()
        fee = request.form.get("consultation_fee", "")

        if not doctor_name or not specialization or not qualification:
            flash("Please fill in the required fields.")
            return redirect(url_for("add_doctor"))

        try:
            experience = int(experience)
            consultation_fee = float(fee) if fee else 0

            if experience < 0 or consultation_fee < 0:
                raise ValueError

        except ValueError:
            flash("Enter valid experience and consultation fee.")
            return redirect(url_for("add_doctor"))

        conn = get_db()

        conn.execute("""
            INSERT INTO doctors
            (hospital_id, doctor_name, specialization, qualification,
             experience, availability, consultation_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["hospital_id"],
            doctor_name,
            specialization,
            qualification,
            experience,
            availability,
            consultation_fee
        ))

        conn.commit()
        conn.close()

        flash("Doctor details saved successfully!")
        return redirect(url_for("view_doctors"))

    return render_template("add_doctor.html")

# VIEW DOCTORS
@app.route("/view-doctors")
def view_doctors():

    if "hospital_id" not in session:
        return redirect(url_for("hospital_login"))

    conn = get_db()

    doctors = conn.execute("""
        SELECT * FROM doctors
        WHERE hospital_id = ?
    """, (session["hospital_id"],)).fetchall()

    conn.close()

    return render_template(
        "view_doctors.html",
        doctors=doctors
    )

# ==========================================================================
# SMART MEDICAL RECOMMENDATION - PATIENT PAGES
# ==========================================================================

def parse_coordinate(value, limit):
    """Parse an optional latitude / longitude. Returns None if missing/invalid."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or abs(number) > limit:
        return None
    return number


def parse_specs(raw):
    return [s.strip() for s in (raw or "").split(",") if s.strip()][:6]


def mask_name(email):
    name, _, domain = (email or "").partition("@")
    return (name[:2] + "***@" + domain) if domain else "Patient"


def latest_reviews(conn, target_type, per_target=2):
    """Latest written reviews grouped by hospital / doctor id."""
    rows = conn.execute("""
        SELECT reviews.target_id, reviews.rating, reviews.comment,
               reviews.created_at, users.email
        FROM reviews JOIN users ON users.id = reviews.user_id
        WHERE reviews.target_type = ?
        ORDER BY reviews.created_at DESC
    """, (target_type,)).fetchall()
    grouped = {}
    for r in rows:
        items = grouped.setdefault(r["target_id"], [])
        if len(items) < per_target:
            items.append({
                "rating": r["rating"],
                "comment": r["comment"] or "",
                "by": mask_name(r["email"]),
                "date": review_date(r["created_at"]),
            })
    return grouped


def doctor_to_dict(row, ratings, primary_keys, recent=None):
    avg, cnt = ratings.get(row["id"], (0, 0))
    return {
        "id": row["id"],
        "name": row["doctor_name"],
        "specialization": row["specialization"],
        "qualification": row["qualification"],
        "experience": row["experience"],
        "availability": row["availability"] or "Not specified",
        "fee": row["consultation_fee"],
        "rating": avg,
        "reviews": cnt,
        "is_primary": care.spec_key(row["specialization"]) in primary_keys,
        "recent_reviews": (recent or {}).get(row["id"], []),
    }


def build_recommendations(conn, specs, urgent, lat, lng, area):
    """Steps 3 and 4: find approved hospitals + matching doctors near the
    patient and rank them."""
    wanted = [care.spec_key(s) for s in specs]
    primary_keys = set(wanted[:1])

    hospitals = conn.execute(
        "SELECT * FROM hospitals WHERE status = 'approved'"
    ).fetchall()
    doctors = conn.execute("SELECT * FROM doctors").fetchall()
    h_ratings = care.rating_map(conn, "hospital")
    d_ratings = care.rating_map(conn, "doctor")
    h_recent = latest_reviews(conn, "hospital")
    d_recent = latest_reviews(conn, "doctor")

    # where is the patient?
    user_point = None
    if lat is not None and lng is not None:
        user_point = (lat, lng)
    elif area:
        user_point = care.city_point(area)

    by_hospital = {}
    for d in doctors:
        by_hospital.setdefault(d["hospital_id"], []).append(d)

    results = []
    for h in hospitals:
        matching = [
            d for d in by_hospital.get(h["id"], [])
            if not wanted or care.spec_key(d["specialization"]) in wanted
        ]

        h_lat, h_lng, exact = care.hospital_point(h)
        distance = None
        if user_point and h_lat is not None:
            distance = round(care.haversine_km(user_point[0], user_point[1], h_lat, h_lng), 1)

        avg, cnt = h_ratings.get(h["id"], (0, 0))
        matching.sort(key=lambda d: (
            0 if care.spec_key(d["specialization"]) in primary_keys else 1,
            -d_ratings.get(d["id"], (0, 0))[0],
        ))

        results.append({
            "id": h["id"],
            "name": h["hospital_name"],
            "address": h["address"],
            "city": h["city"],
            "state": h["state"],
            "phone": h["phone"],
            "distance_km": distance,
            "distance_is_approx": distance is not None and not exact,
            "in_area": care.area_matches(area, h) if area else False,
            "rating": avg,
            "reviews": cnt,
            "recent_reviews": h_recent.get(h["id"], []),
            "doctors": [doctor_to_dict(d, d_ratings, primary_keys, d_recent) for d in matching],
        })

    with_specialist = [r for r in results if r["doctors"]]
    fallback = False
    if urgent:
        # emergencies: never hide a hospital, nearest first
        shown = results
    elif with_specialist:
        shown = with_specialist
    else:
        shown, fallback = results, True

    shown.sort(key=lambda r: (
        r["distance_km"] is None,
        r["distance_km"] if r["distance_km"] is not None else 0,
        not r["in_area"],
        -r["rating"],
        r["name"].lower(),
    ))

    return {
        "urgency": "urgent" if urgent else "low",
        "specializations": specs,
        "located": bool(user_point) or any(r["in_area"] for r in shown),
        "fallback": fallback,
        "hospitals": shown,
    }


@app.route("/api/care-recommendations")
def api_care_recommendations():
    specs = parse_specs(request.args.get("specs"))
    urgent = request.args.get("urgency") == "urgent"
    lat = parse_coordinate(request.args.get("lat"), 90)
    lng = parse_coordinate(request.args.get("lng"), 180)
    area = request.args.get("area", "").strip()[:100]

    conn = get_db()
    try:
        data = build_recommendations(conn, specs, urgent, lat, lng, area)
    finally:
        conn.close()
    return jsonify(data)


@app.route("/find-care")
def find_care():
    selected = care.get_condition(request.args.get("condition", ""))
    return render_template(
        "find_care.html",
        catalog=care.DISEASE_CATALOG,
        selected=selected,
        urgent=request.args.get("urgency") == "urgent",
    )


# FIND DOCTORS - PATIENT PAGE (filter by disease / specialisation)
@app.route("/doctors")
def doctors():
    q = request.args.get("q", "").strip()
    disease = care.get_condition(request.args.get("disease", ""))
    spec = request.args.get("specialization", "").strip()

    wanted = set()
    if disease:
        wanted = {care.spec_key(s) for s in disease["specializations"]}
    elif spec:
        wanted = {care.spec_key(spec)}

    conn = get_db()
    rows = conn.execute("""
        SELECT doctors.*, hospitals.hospital_name,
               hospitals.city, hospitals.state
        FROM doctors
        JOIN hospitals ON doctors.hospital_id = hospitals.id
        WHERE hospitals.status = 'approved'
        ORDER BY doctors.doctor_name
    """).fetchall()
    ratings = care.rating_map(conn, "doctor")
    recent = latest_reviews(conn, "doctor")
    conn.close()

    doctors_list = []
    for r in rows:
        if wanted and care.spec_key(r["specialization"]) not in wanted:
            continue
        if q and q.lower() not in (r["doctor_name"] + " " + r["hospital_name"]).lower():
            continue
        avg, cnt = ratings.get(r["id"], (0, 0))
        doctors_list.append({"row": r, "rating": avg, "reviews": cnt,
                             "recent": recent.get(r["id"], [])})

    return render_template(
        "doctors.html",
        doctors=doctors_list,
        catalog=care.DISEASE_CATALOG,
        q=q,
        selected_disease=disease["name"] if disease else "",
        specializations=SPECIALIZATIONS,
        selected_spec=spec,
    )


# FIND HOSPITALS - PATIENT PAGE
@app.route("/hospitals")
def hospitals():
    q = request.args.get("q", "").strip()

    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM hospitals
        WHERE status = 'approved'
        ORDER BY hospital_name
    """).fetchall()
    ratings = care.rating_map(conn, "hospital")
    recent = latest_reviews(conn, "hospital")
    counts = {
        r["hospital_id"]: r["n"] for r in conn.execute(
            "SELECT hospital_id, COUNT(*) AS n FROM doctors GROUP BY hospital_id"
        ).fetchall()
    }
    conn.close()

    hospitals_list = []
    for r in rows:
        if q and not care.area_matches(q, r) and q.lower() not in r["hospital_name"].lower():
            continue
        avg, cnt = ratings.get(r["id"], (0, 0))
        hospitals_list.append({
            "row": r, "rating": avg, "reviews": cnt,
            "doctor_count": counts.get(r["id"], 0),
            "recent": recent.get(r["id"], []),
        })

    return render_template("hospitals.html", hospitals=hospitals_list, q=q)


SPECIALIZATIONS = [
    "Cardiologist", "Neurologist", "Dermatologist", "Pediatrician",
    "Orthopedic", "Gynecologist", "General Physician", "ENT Specialist",
    "Ophthalmologist", "Psychiatrist",
]


# HOSPITAL DETAIL PAGE (doctors + reviews)
@app.route("/hospital/<int:hospital_id>")
def hospital_detail(hospital_id):
    conn = get_db()
    hospital = conn.execute(
        "SELECT * FROM hospitals WHERE id = ? AND status = 'approved'",
        (hospital_id,)
    ).fetchone()
    if not hospital:
        conn.close()
        abort(404)

    d_rows = conn.execute(
        "SELECT * FROM doctors WHERE hospital_id = ? ORDER BY doctor_name",
        (hospital_id,)
    ).fetchall()
    d_ratings = care.rating_map(conn, "doctor")
    h_avg, h_cnt = care.rating_map(conn, "hospital").get(hospital_id, (0, 0))
    reviews = fetch_reviews(conn, "hospital", hospital_id)
    my_review = fetch_my_review(conn, "hospital", hospital_id)
    conn.close()

    doctors_list = [
        {"row": d, "rating": d_ratings.get(d["id"], (0, 0))[0],
         "reviews": d_ratings.get(d["id"], (0, 0))[1]}
        for d in d_rows
    ]
    return render_template(
        "hospital_detail.html",
        hospital=hospital, doctors=doctors_list,
        rating=h_avg, review_count=h_cnt,
        reviews=reviews, my_review=my_review,
    )


# DOCTOR DETAIL PAGE (reviews)
@app.route("/doctor/<int:doctor_id>")
def doctor_detail(doctor_id):
    conn = get_db()
    doctor = conn.execute("""
        SELECT doctors.*, hospitals.hospital_name, hospitals.city,
               hospitals.state, hospitals.phone, hospitals.address
        FROM doctors JOIN hospitals ON doctors.hospital_id = hospitals.id
        WHERE doctors.id = ? AND hospitals.status = 'approved'
    """, (doctor_id,)).fetchone()
    if not doctor:
        conn.close()
        abort(404)

    avg, cnt = care.rating_map(conn, "doctor").get(doctor_id, (0, 0))
    reviews = fetch_reviews(conn, "doctor", doctor_id)
    my_review = fetch_my_review(conn, "doctor", doctor_id)
    conn.close()

    return render_template(
        "doctor_detail.html",
        doctor=doctor, rating=avg, review_count=cnt,
        reviews=reviews, my_review=my_review,
    )


def fetch_reviews(conn, target_type, target_id):
    return conn.execute("""
        SELECT reviews.rating, reviews.comment, reviews.created_at,
               users.email
        FROM reviews JOIN users ON users.id = reviews.user_id
        WHERE target_type = ? AND target_id = ?
        ORDER BY reviews.created_at DESC
    """, (target_type, target_id)).fetchall()


def fetch_my_review(conn, target_type, target_id):
    if "user_id" not in session:
        return None
    return conn.execute("""
        SELECT rating, comment FROM reviews
        WHERE user_id = ? AND target_type = ? AND target_id = ?
    """, (session["user_id"], target_type, target_id)).fetchone()


@app.template_filter("mask_email")
def mask_email(email):
    """Show reviewers as 'ma***@gmail.com' so patient emails stay private."""
    name, _, domain = (email or "").partition("@")
    return (name[:2] + "***@" + domain) if domain else "Patient"


@app.template_filter("review_date")
def review_date(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return ""


def safe_next(target, fallback):
    # only allow redirects back into this site
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback


# SUBMIT / UPDATE A REVIEW (patients only, one review per patient per target)
@app.route("/submit-review", methods=["POST"])
def submit_review():
    next_url = safe_next(request.form.get("next"), url_for("reviews"))

    if "user_id" not in session:
        flash("Please log in as a patient to write a review.")
        return redirect(url_for("login"))

    target_type = request.form.get("target_type", "")
    comment = request.form.get("comment", "").strip()[:1000]

    try:
        target_id = int(request.form.get("target_id", ""))
        rating = int(request.form.get("rating", ""))
    except ValueError:
        flash("Please choose a star rating.")
        return redirect(next_url)

    if target_type not in ("hospital", "doctor") or not 1 <= rating <= 5:
        flash("Please choose a star rating between 1 and 5.")
        return redirect(next_url)

    conn = get_db()
    try:
        if target_type == "hospital":
            exists = conn.execute(
                "SELECT 1 FROM hospitals WHERE id = ? AND status = 'approved'",
                (target_id,)).fetchone()
        else:
            exists = conn.execute("""
                SELECT 1 FROM doctors JOIN hospitals
                ON doctors.hospital_id = hospitals.id
                WHERE doctors.id = ? AND hospitals.status = 'approved'
            """, (target_id,)).fetchone()

        if not exists:
            flash("That hospital or doctor was not found.")
            return redirect(next_url)

        conn.execute("""
            INSERT INTO reviews (user_id, target_type, target_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, target_type, target_id)
            DO UPDATE SET rating = excluded.rating,
                          comment = excluded.comment,
                          created_at = excluded.created_at
        """, (session["user_id"], target_type, target_id, rating, comment,
              datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()

    flash("Thank you! Your review has been saved.")
    return redirect(next_url)


# PATIENT REVIEWS PAGE
@app.route("/reviews")
def reviews():
    kind = request.args.get("type", "hospital")
    if kind not in ("hospital", "doctor"):
        kind = "hospital"

    conn = get_db()
    if kind == "hospital":
        rows = conn.execute("""
            SELECT reviews.*, users.email,
                   hospitals.hospital_name AS target_name,
                   hospitals.id AS link_id
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN hospitals ON hospitals.id = reviews.target_id
            WHERE reviews.target_type = 'hospital' AND hospitals.status = 'approved'
            ORDER BY reviews.created_at DESC LIMIT 100
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT reviews.*, users.email,
                   doctors.doctor_name AS target_name,
                   doctors.specialization AS sub_name,
                   hospitals.hospital_name AS hospital_name,
                   doctors.id AS link_id
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN doctors ON doctors.id = reviews.target_id
            JOIN hospitals ON hospitals.id = doctors.hospital_id
            WHERE reviews.target_type = 'doctor' AND hospitals.status = 'approved'
            ORDER BY reviews.created_at DESC LIMIT 100
        """).fetchall()
    conn.close()

    return render_template("reviews.html", reviews=rows, kind=kind)


# LOGOUT
@app.route("/logout")
def logout():

    session.clear()

    flash("You have logged out.")

    return redirect(url_for("login"))


# FORGOT PASSWORD
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user:

            token = secrets.token_urlsafe(32)

            token_hash = hashlib.sha256(
                token.encode()
            ).hexdigest()

            expiry = (
                datetime.now(timezone.utc) +
                timedelta(minutes=15)
            ).isoformat()

            conn.execute(
                "INSERT INTO reset_tokens VALUES (?, ?, ?)",
                (token_hash, email, expiry)
            )

            conn.commit()

            reset_link = url_for(
                "reset_password",
                token=token,
                _external=True
            )

            conn.close()

            return render_template(
                "forgot_password.html",
                reset_link=reset_link
            )

        conn.close()

        flash("If that account exists, a reset link would be sent.")

    return render_template("forgot_password.html")


# RESET PASSWORD
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    conn = get_db()

    record = conn.execute(
        "SELECT * FROM reset_tokens WHERE token_hash = ?",
        (token_hash,)
    ).fetchone()

    if not record:

        conn.close()

        flash("Invalid or expired reset link.")

        return redirect(url_for("forgot_password"))

    expiry = datetime.fromisoformat(record["expires_at"])

    if datetime.now(timezone.utc) > expiry:

        conn.execute(
            "DELETE FROM reset_tokens WHERE token_hash = ?",
            (token_hash,)
        )

        conn.commit()
        conn.close()

        flash("Reset link expired. Please request another.")

        return redirect(url_for("forgot_password"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:

            flash("Password must be at least 8 characters.")

        elif password != confirm:

            flash("Passwords do not match.")

        else:

            conn.execute(
                "UPDATE users SET password = ? WHERE email = ?",
                (
                    generate_password_hash(password),
                    record["email"]
                )
            )

            conn.execute(
                "DELETE FROM reset_tokens WHERE email = ?",
                (record["email"],)
            )

            conn.commit()
            conn.close()

            flash("Password reset successful. Please log in.")

            return redirect(url_for("login"))

    conn.close()

    return render_template("reset_password.html")

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))
    
# RUN APPLICATION
if __name__ == "__main__":

    init_db()

    app.run(debug=True)
