from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
import sqlite3
import secrets
import hashlib
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

app = Flask(__name__)

# Use a stable secret key in production.
# Set SECRET_KEY in your environment before deployment.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-development-secret-key"
)

DATABASE = "healthcare.db"


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
            consultation_fee REAL,
            FOREIGN KEY (hospital_id)
            REFERENCES hospitals(id)
            ON DELETE CASCADE
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


# LOGIN REQUIRED DECORATOR
def patient_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def hospital_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "hospital_id" not in session:
            return redirect(url_for("hospital_login"))
        return function(*args, **kwargs)
    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapper


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# PATIENT REGISTRATION
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


# PATIENT LOGIN
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
@patient_required
def health():
    return render_template("health.html")


# PATIENT DASHBOARD
@app.route("/dashboard")
@patient_required
def dashboard():

    return render_template(
        "dashboard.html",
        email=session["email"]
    )


# SMARTHEALTH CHATBOT
@app.route("/chat", methods=["POST"])
@patient_required
def chat():

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
            "In India, call 112.\n"
            "Do not wait for chatbot advice."
        )

    elif "fever" in message:

        reply = (
            "🤒 FEVER INFORMATION\n\n"
            "Possible causes include infections and other illnesses.\n\n"
            "1. Take adequate rest.\n"
            "2. Drink enough fluids.\n"
            "3. Monitor your temperature.\n"
            "4. Avoid strenuous activity.\n"
            "5. Consult a doctor if symptoms persist or worsen."
        )

    elif "headache" in message or "migraine" in message:

        reply = (
            "🤕 HEADACHE INFORMATION\n\n"
            "Possible causes include stress, dehydration, "
            "lack of sleep or migraine.\n\n"
            "1. Rest in a quiet place.\n"
            "2. Drink enough water.\n"
            "3. Eat regular meals.\n"
            "4. Maintain proper sleep.\n"
            "5. Consult a doctor if pain continues.\n\n"
            "A sudden, extremely severe headache needs emergency care."
        )

    elif any(word in message for word in
             ["cold", "cough", "sneezing"]):

        reply = (
            "🤧 COLD AND COUGH INFORMATION\n\n"
            "Possible causes include viral infections or allergies.\n\n"
            "1. Get enough rest.\n"
            "2. Drink plenty of fluids.\n"
            "3. Cover your mouth when coughing.\n"
            "4. Wash your hands regularly.\n"
            "5. Consult a doctor if symptoms worsen."
        )

    elif "stomach pain" in message or "stomach ache" in message:

        reply = (
            "🍽️ STOMACH PAIN INFORMATION\n\n"
            "Possible causes include indigestion, constipation "
            "or infections.\n\n"
            "1. Drink enough water.\n"
            "2. Eat light meals if tolerated.\n"
            "3. Monitor your symptoms.\n"
            "4. Consult a doctor if pain continues.\n\n"
            "Severe or sudden stomach pain needs urgent assessment."
        )

    elif any(word in message for word in
             ["allergy", "itching", "rash"]):

        reply = (
            "🌿 ALLERGY INFORMATION\n\n"
            "Possible symptoms include itching, sneezing and rashes.\n\n"
            "1. Avoid known allergy triggers.\n"
            "2. Keep your surroundings clean.\n"
            "3. Avoid scratching affected skin.\n"
            "4. Consult a healthcare professional.\n\n"
            "Tongue or throat swelling or breathing difficulty "
            "needs emergency care."
        )

    elif "diabetes" in message or "sugar" in message:

        reply = (
            "💙 DIABETES INFORMATION\n\n"
            "Diabetes affects how the body regulates blood glucose.\n\n"
            "1. Monitor blood glucose as advised.\n"
            "2. Follow a balanced diet.\n"
            "3. Stay physically active if appropriate.\n"
            "4. Attend regular medical checkups.\n"
            "5. Follow your doctor's treatment plan."
        )

    elif "sleep" in message or "insomnia" in message:

        reply = (
            "😴 SLEEP INFORMATION\n\n"
            "1. Maintain a regular sleep schedule.\n"
            "2. Avoid caffeine close to bedtime.\n"
            "3. Reduce screen time before sleeping.\n"
            "4. Keep your bedroom comfortable.\n"
            "5. Consult a doctor if the problem continues."
        )

    else:

        reply = (
            "💙 Welcome to SmartHealth Assistant!\n\n"
            "Please tell me:\n"
            "1. What symptoms are you experiencing?\n"
            "2. How many days have you had these symptoms?\n"
            "3. Are your symptoms mild, moderate or severe?\n\n"
            "I provide general health information, not a diagnosis."
        )

    return jsonify({"reply": reply})


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

        if not all([
            hospital_name, email, password,
            phone, address, city, state
        ]):
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
                 address, city, state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                hospital_name,
                email,
                generate_password_hash(password),
                phone,
                address,
                city,
                state
            ))

            conn.commit()
            flash("Registration successful! Waiting for admin approval.")
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
@hospital_required
def hospital_dashboard():

    return render_template(
        "hospital_dashboard.html",
        hospital_name=session["hospital_name"]
    )


# ADD DOCTOR
@app.route("/add-doctor", methods=["GET", "POST"])
@hospital_required
def add_doctor():

    if request.method == "POST":

        doctor_name = request.form.get("doctor_name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        qualification = request.form.get("qualification", "").strip()
        experience = request.form.get("experience", "")
        availability = request.form.get("availability", "").strip()
        fee = request.form.get("consultation_fee", "")

        if not all([doctor_name, specialization, qualification]):
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
            (hospital_id, doctor_name, specialization,
             qualification, experience, availability,
             consultation_fee)
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
@hospital_required
def view_doctors():

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


# HOSPITAL LOGOUT
@app.route("/hospital-logout")
def hospital_logout():

    session.pop("hospital_id", None)
    session.pop("hospital_name", None)

    flash("Hospital logged out successfully.")

    return redirect(url_for("hospital_login"))


# ADMIN LOGIN
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        admin = conn.execute(
            "SELECT * FROM admins WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"], password
        ):

            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_email"] = admin["email"]

            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin email or password.")

    return render_template("admin_login.html")


# ADMIN DASHBOARD
@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():

    conn = get_db()

    hospitals = conn.execute("""
        SELECT * FROM hospitals
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        hospitals=hospitals
    )


# APPROVE HOSPITAL
@app.route("/approve-hospital/<int:hospital_id>", methods=["POST"])
@admin_required
def approve_hospital(hospital_id):

    conn = get_db()

    conn.execute("""
        UPDATE hospitals
        SET status = 'approved'
        WHERE id = ?
    """, (hospital_id,))

    conn.commit()
    conn.close()

    flash("Hospital approved successfully.")

    return redirect(url_for("admin_dashboard"))


# REJECT HOSPITAL
@app.route("/reject-hospital/<int:hospital_id>", methods=["POST"])
@admin_required
def reject_hospital(hospital_id):

    conn = get_db()

    conn.execute("""
        UPDATE hospitals
        SET status = 'rejected'
        WHERE id = ?
    """, (hospital_id,))

    conn.commit()
    conn.close()

    flash("Hospital rejected.")

    return redirect(url_for("admin_dashboard"))


# ADMIN LOGOUT
@app.route("/admin-logout")
def admin_logout():

    session.clear()

    flash("Admin logged out.")

    return redirect(url_for("admin_login"))


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
                (generate_password_hash(password), record["email"])
            )

            conn.execute(
                "DELETE FROM reset_tokens WHERE token_hash = ?",
                (token_hash,)
            )

            conn.commit()
            conn.close()

            flash("Password reset successful. Please log in.")
            return redirect(url_for("login"))
        conn.close()

    return render_template("reset_password.html")


# PATIENT LOGOUT
@app.route("/logout")
def logout():

    session.clear()
    flash("You have logged out.")

    return redirect(url_for("login"))


# RUN APPLICATION
if __name__ == "__main__":

    init_db()

    app.run(debug=True)