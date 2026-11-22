"""Helpers for the Smart Medical Recommendation feature.

* DISEASE_CATALOG  - maps diseases / symptoms to the doctor specialisations
                     that treat them (single source of truth for the chatbot
                     and the "Find Care" page).
* detect_condition - finds the best catalog match in free text.
* geo helpers      - distance between the patient and a hospital.
* rating helpers   - average star rating for hospitals and doctors.

The app only gives general guidance. It never diagnoses a disease.
"""

import math
import re

# --------------------------------------------------------------------------
# Disease / symptom  ->  specialisation
# Order matters: the first entry whose keyword matches wins, so the urgent
# conditions are listed first.
# `specializations[0]` is the primary specialist, the rest are alternatives.
# --------------------------------------------------------------------------
DISEASE_CATALOG = [
    {
        "name": "Chest pain / Heart problems",
        "specializations": ["Cardiologist", "General Physician"],
        "keywords": ["chest pain", "heart", "palpitation", "blood pressure",
                     "hypertension", "cholesterol"],
    },
    {
        "name": "Stroke / Sudden weakness",
        "specializations": ["Neurologist", "General Physician"],
        "keywords": ["stroke", "face drooping", "sudden weakness",
                     "paralysis", "slurred speech"],
    },
    {
        "name": "Breathing difficulty / Asthma",
        "specializations": ["General Physician"],
        "keywords": ["difficulty breathing", "can't breathe", "cannot breathe",
                     "shortness of breath", "breathless", "asthma", "wheezing"],
    },
    {
        "name": "Severe bleeding / Fainting",
        "specializations": ["General Physician"],
        "keywords": ["severe bleeding", "bleeding", "fainting", "unconscious"],
    },
    {
        "name": "Headache / Migraine",
        "specializations": ["Neurologist", "General Physician"],
        "keywords": ["headache", "migraine", "seizure", "epilepsy",
                     "dizziness", "numbness"],
    },
    {
        "name": "Fever / Infection",
        "specializations": ["General Physician"],
        "keywords": ["fever", "infection", "typhoid", "malaria", "dengue",
                     "flu", "body ache"],
    },
    {
        "name": "Ear, nose & throat problems",
        "specializations": ["ENT Specialist", "General Physician"],
        "keywords": ["ear pain", "earache", "ear", "sinus", "tonsil",
                     "sore throat", "throat", "nose bleed", "hearing"],
    },
    {
        "name": "Cold & cough",
        "specializations": ["General Physician", "ENT Specialist"],
        "keywords": ["cold", "cough", "sneezing", "runny nose"],
    },
    {
        "name": "Stomach / Digestive problems",
        "specializations": ["General Physician"],
        "keywords": ["stomach pain", "stomach ache", "stomach", "vomiting",
                     "diarrhoea", "diarrhea", "acidity", "gastric",
                     "indigestion", "constipation"],
    },
    {
        "name": "Skin problems / Allergy",
        "specializations": ["Dermatologist", "General Physician"],
        "keywords": ["allergy", "itching", "rash", "acne", "eczema", "skin",
                     "hair fall"],
    },
    {
        "name": "Diabetes / Thyroid",
        "specializations": ["General Physician"],
        "keywords": ["diabetes", "sugar", "thyroid"],
    },
    {
        "name": "Bone & joint problems",
        "specializations": ["Orthopedic", "General Physician"],
        "keywords": ["fracture", "back pain", "joint pain", "knee", "arthritis",
                     "bone", "sprain", "neck pain", "shoulder pain"],
    },
    {
        "name": "Eye problems",
        "specializations": ["Ophthalmologist"],
        "keywords": ["eye", "vision", "conjunctivitis", "blurred"],
    },
    {
        "name": "Mental health / Sleep",
        "specializations": ["Psychiatrist", "General Physician"],
        "keywords": ["anxiety", "depression", "stress", "panic", "insomnia",
                     "sleep", "mood"],
    },
    {
        "name": "Women's health / Pregnancy",
        "specializations": ["Gynecologist"],
        "keywords": ["pregnancy", "pregnant", "period", "menstrual", "pcos"],
    },
    {
        "name": "Child health",
        "specializations": ["Pediatrician", "General Physician"],
        "keywords": ["child", "baby", "infant", "newborn", "vaccination"],
    },
]

# Words that mean "get medical attention now" (same list the chatbot uses).
EMERGENCY_WORDS = [
    "chest pain", "difficulty breathing", "can't breathe", "cannot breathe",
    "severe bleeding", "fainting", "unconscious", "stroke", "face drooping",
    "sudden weakness",
]


def _contains(text, phrase):
    # prefix word boundary so "ear" does not match "heart", but "rash" matches
    # "rashes".
    return re.search(r"\b" + re.escape(phrase), text) is not None


def is_urgent(text):
    text = (text or "").lower()
    return any(w in text for w in EMERGENCY_WORDS)


def detect_condition(text):
    """Return the first catalog entry whose keyword appears in `text`."""
    text = (text or "").lower().replace("heartburn", "acidity")
    # an emergency phrase always wins, whatever else was typed
    for word in EMERGENCY_WORDS:
        if word in text:
            for entry in DISEASE_CATALOG:
                if word in entry["keywords"]:
                    return entry
    for entry in DISEASE_CATALOG:
        if any(_contains(text, k) for k in entry["keywords"]):
            return entry
    return None


def get_condition(name):
    for entry in DISEASE_CATALOG:
        if entry["name"] == name:
            return entry
    return None


# --------------------------------------------------------------------------
# Specialisation matching ("cardiologist" == "Cardiologist" == "Cardiology")
# --------------------------------------------------------------------------
_SPEC_PATTERNS = {
    "cardiologist": r"cardio|heart",
    "neurologist": r"neuro",
    "dermatologist": r"derma|skin",
    "pediatrician": r"pediat|paediat|child",
    "orthopedic": r"ortho",
    "gynecologist": r"gyn|obstet",
    "general physician": r"general|physician|\bgp\b|family",
    "ent specialist": r"\bent\b|otolaryn|ear.?nose",
    "ophthalmologist": r"ophthal|eye",
    "psychiatrist": r"psychiat|mental",
}


def spec_key(value):
    value = (value or "").strip().lower()
    for key, pattern in _SPEC_PATTERNS.items():
        if re.search(pattern, value):
            return key
    return value


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------
# Approximate city centres. Used when a hospital was registered without exact
# coordinates, or when the patient types a city instead of sharing GPS.
CITY_COORDS = {
    "hassan": (13.0072, 76.0962), "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946), "mysuru": (12.2958, 76.6394),
    "mysore": (12.2958, 76.6394), "mangaluru": (12.9141, 74.8560),
    "mangalore": (12.9141, 74.8560), "hubballi": (15.3647, 75.1240),
    "hubli": (15.3647, 75.1240), "dharwad": (15.4589, 75.0078),
    "belagavi": (15.8497, 74.4977), "belgaum": (15.8497, 74.4977),
    "kalaburagi": (17.3297, 76.8343), "gulbarga": (17.3297, 76.8343),
    "ballari": (15.1394, 76.9214), "bellary": (15.1394, 76.9214),
    "shivamogga": (13.9299, 75.5681), "shimoga": (13.9299, 75.5681),
    "tumakuru": (13.3379, 77.1173), "tumkur": (13.3379, 77.1173),
    "davanagere": (14.4644, 75.9218), "udupi": (13.3409, 74.7421),
    "chikkamagaluru": (13.3161, 75.7720), "chikmagalur": (13.3161, 75.7720),
    "mandya": (12.5218, 76.8951), "chitradurga": (14.2251, 76.3980),
    "kolar": (13.1357, 78.1326), "raichur": (16.2120, 77.3439),
    "bidar": (17.9104, 77.5199), "vijayapura": (16.8302, 75.7100),
    "chennai": (13.0827, 80.2707), "hyderabad": (17.3850, 78.4867),
    "mumbai": (19.0760, 72.8777), "pune": (18.5204, 73.8567),
    "delhi": (28.6139, 77.2090), "new delhi": (28.6139, 77.2090),
    "kolkata": (22.5726, 88.3639), "ahmedabad": (23.0225, 72.5714),
    "kochi": (9.9312, 76.2673), "thiruvananthapuram": (8.5241, 76.9366),
    "coimbatore": (11.0168, 76.9558), "vijayawada": (16.5062, 80.6480),
    "visakhapatnam": (17.6868, 83.2185), "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462), "nagpur": (21.1458, 79.0882),
}


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def city_point(text):
    """Find a known city name inside free text -> (lat, lng) or None."""
    text = (text or "").lower()
    # longest names first so "new delhi" beats "delhi"
    for name in sorted(CITY_COORDS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", text):
            return CITY_COORDS[name]
    return None


def area_matches(area_text, hospital):
    """True when the area typed by the patient appears in the hospital's
    city / address / state."""
    tokens = [t for t in re.split(r"[\s,]+", (area_text or "").lower()) if len(t) >= 3]
    if not tokens:
        return False
    haystack = " ".join(
        str(hospital[k] or "") for k in ("city", "address", "state")
    ).lower()
    return any(t in haystack for t in tokens)


def hospital_point(hospital):
    """(lat, lng, is_exact) for a hospital row."""
    if hospital["latitude"] is not None and hospital["longitude"] is not None:
        return hospital["latitude"], hospital["longitude"], True
    pt = city_point(hospital["city"])
    if pt:
        return pt[0], pt[1], False
    return None, None, False


# --------------------------------------------------------------------------
# Ratings
# --------------------------------------------------------------------------
def rating_map(conn, target_type):
    rows = conn.execute(
        """SELECT target_id, AVG(rating) AS avg_rating, COUNT(*) AS cnt
           FROM reviews WHERE target_type = ? GROUP BY target_id""",
        (target_type,),
    ).fetchall()
    return {r["target_id"]: (round(r["avg_rating"], 1), r["cnt"]) for r in rows}
