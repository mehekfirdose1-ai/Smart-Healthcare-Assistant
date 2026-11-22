from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import session, redirect, url_for

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

    conn.commit()
    conn.close()


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

        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        if not all([hospital_name, email, password, phone,
                    address, city, state]):
            flash("Please fill in all fields.")
            return render_template("hospital_register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("hospital_register.html")

        if not latitude or not longitude:
            flash("Please select hospital location on the map.")
            return render_template("hospital_register.html")

        try:
            latitude = float(latitude)
            longitude = float(longitude)

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError("Invalid coordinates")

        except ValueError:
            flash("Please select a valid hospital location.")
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
            return redirect(url_for("hospital_login"))

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

    return jsonify({
        "reply": reply
    })

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

# FIND DOCTORS - PATIENT PAGE
@app.route("/doctors")
def doctors():

    conn = get_db()

    doctors_list = conn.execute("""
        SELECT doctors.*, hospitals.hospital_name,
               hospitals.city, hospitals.state
        FROM doctors
        JOIN hospitals
        ON doctors.hospital_id = hospitals.id
        WHERE hospitals.status = 'approved'
        ORDER BY doctors.doctor_name
    """).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctors_list
    )


# FIND HOSPITALS - PATIENT PAGE
@app.route("/hospitals")
def hospitals():

    conn = get_db()

    hospitals_list = conn.execute("""
        SELECT * FROM hospitals
        WHERE status = 'approved'
        ORDER BY hospital_name
    """).fetchall()

    conn.close()

    return render_template(
        "hospitals.html",
        hospitals=hospitals_list
    )

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
@app.route('/near-hospital')
def near_hospital():
    return render_template('near_hospital.html')
    
# RUN APPLICATION
if __name__ == "__main__":

    init_db()

    app.run(debug=True)
