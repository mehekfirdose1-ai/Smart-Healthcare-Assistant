# smart-health-assistant

## Smart Medical Recommendation (patient side)

Flow: patient describes symptoms -> urgency check -> nearby hospitals & doctors -> results with reviews.

* `care.py` - disease/symptom -> specialisation catalog, urgency words, distance + rating helpers.
* Chatbot (`/health`) shows a recommendation panel after a symptom message. Urgent symptoms
  (chest pain, breathing difficulty, stroke signs, ...) show a "medical attention" alert and the nearest hospitals.
* `/find-care` - pick a disease/symptom, see matching hospitals and doctors.
* `/doctors` (filter by disease / specialisation), `/hospitals` (search by name/area),
  `/hospital/<id>`, `/doctor/<id>` - details, ratings and reviews.
* `/reviews` - latest hospital and doctor reviews. Logged-in patients can rate 1-5 stars and comment
  (one review per patient per hospital/doctor; submitting again updates it).
* Only hospitals approved by the admin are shown to patients.
* Distance: uses the patient's browser location (only if allowed) or a typed city/area.
  Hospitals registered with "Use this device's location" get exact distances; otherwise the
  distance is estimated from the city centre (shown as "≈").
* The `reviews` table is created automatically on startup.

The chatbot gives general guidance only and never diagnoses.
