/* Smart Medical Recommendation - shared by the chatbot and /find-care.
 *
 * CareFinder.mount(container, { urgency, specializations, condition })
 *   3. Find nearby hospitals and doctors (GPS with permission, or a typed area)
 *   4. Display recommendations (hospital, distance, address, doctors, reviews)
 */
(function () {
    "use strict";

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (k) {
            if (k === "class") node.className = attrs[k];
            else if (k === "text") node.textContent = attrs[k];
            else node.setAttribute(k, attrs[k]);
        });
        (children || []).forEach(function (c) { if (c) node.appendChild(c); });
        return node;
    }

    function stars(avg) {
        var wrap = el("span", { "class": "stars" });
        var full = Math.round(avg);
        for (var i = 1; i <= 5; i++) {
            wrap.appendChild(el("span", { "class": i <= full ? "" : "off", text: "★" }));
        }
        return wrap;
    }

    function ratingBlock(avg, count) {
        var box = el("span");
        if (!count) {
            box.appendChild(el("span", { "class": "rating-text", text: "No reviews yet" }));
            return box;
        }
        box.appendChild(stars(avg));
        box.appendChild(el("span", { "class": "rating-text", text: avg.toFixed(1) + " (" + count + (count === 1 ? " review)" : " reviews)") }));
        return box;
    }

    // written reviews: stars + comment + reviewer + date
    function reviewList(list, label) {
        var box = el("div", { "class": "rec-reviews" });
        box.appendChild(el("div", { "class": "rec-reviews-title", text: label }));
        if (!list || !list.length) {
            box.appendChild(el("div", { "class": "muted", text: "No written reviews yet." }));
            return box;
        }
        list.forEach(function (r) {
            var item = el("div", { "class": "rec-review" }, [
                stars(r.rating),
                el("span", { "class": "rating-text", text: r.by + (r.date ? " · " + r.date : "") })
            ]);
            if (r.comment) item.appendChild(el("div", { "class": "rec-review-text", text: "“" + r.comment + "”" }));
            box.appendChild(item);
        });
        return box;
    }

    function mount(container, opts) {
        var urgent = opts.urgency === "urgent";
        var specs = opts.specializations || [];
        var coords = null;

        container.innerHTML = "";
        var panel = el("div", { "class": "care-panel" });
        container.appendChild(panel);

        // Step 2 result: urgency
        panel.appendChild(el("div", { "class": "care-alert " + (urgent ? "urgent" : "low") }, [
            el("b", { text: urgent ? "Medical attention recommended. " : "Low urgency. " }),
            el("span", { text: urgent
                ? "Please get prompt medical care. In India call 112 for emergencies. Nearby hospitals are shown below."
                : "General guidance applies, but a doctor can help if symptoms continue. Suggested specialist: " + (specs[0] || "General Physician") + "." })
        ]));

        // Step 3: location
        var input = el("input", { type: "text", placeholder: "Enter your area or city (e.g. Hassan)", maxlength: "100", "aria-label": "Your area" });
        var gpsBtn = el("button", { type: "button", "class": "btn ghost small", text: "📍 Use my location" });
        var goBtn = el("button", { type: "button", "class": "btn small", text: "Search" });
        var msg = el("div", { "class": "care-loc-msg" });

        panel.appendChild(el("div", { "class": "care-step" }, [
            el("div", { "class": "num", text: "3" }),
            el("div", {}, [
                el("h4", { text: "Find nearby hospitals and doctors" }),
                el("p", { text: "Share your location (only if you allow it) or type your area. Your location is not saved." })
            ])
        ]));
        panel.appendChild(el("div", { "class": "care-loc" }, [input, gpsBtn, goBtn]));
        panel.appendChild(msg);

        // Step 4: results
        panel.appendChild(el("div", { "class": "care-step" }, [
            el("div", { "class": "num", text: "4" }),
            el("div", {}, [el("h4", { text: "Recommended hospitals and doctors" })])
        ]));
        var results = el("div");
        panel.appendChild(results);

        function load() {
            results.textContent = "Loading…";
            var q = new URLSearchParams();
            q.set("specs", specs.join(","));
            q.set("urgency", urgent ? "urgent" : "low");
            if (coords) { q.set("lat", coords.lat); q.set("lng", coords.lng); }
            if (input.value.trim()) q.set("area", input.value.trim());

            fetch("/api/care-recommendations?" + q.toString())
                .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
                .then(render)
                .catch(function () { results.textContent = "Sorry, could not load hospitals right now."; });
        }

        function hospitalLine(h) {
            var meta = [h.name];
            if (h.distance_km !== null) meta.push((h.distance_is_approx ? "≈ " : "") + h.distance_km + " km");
            else if (h.in_area) meta.push("In your area");
            meta.push(h.address + ", " + h.city);
            return meta.join(" · ");
        }

        function render(data) {
            results.innerHTML = "";

            if (!data.hospitals.length) {
                results.appendChild(el("p", { "class": "muted", text: "No approved hospitals are available yet." }));
                return;
            }
            if (!data.located) {
                results.appendChild(el("p", { "class": "rec-note", text: "Add your area or share your location to sort by distance." }));
            }

            // ---- Doctors first ----
            var docs = [];
            data.hospitals.forEach(function (h) {
                h.doctors.forEach(function (d) { docs.push({ d: d, h: h }); });
            });

            results.appendChild(el("h3", { "class": "rec-section", text: "👨‍⚕️ Recommended doctors" + (docs.length ? " (" + docs.length + ")" : "") }));

            if (!docs.length) {
                results.appendChild(el("p", { "class": "rec-note", text: "No " + specs.join(" / ") + " is listed yet. Hospitals are shown below." }));
            }

            docs.forEach(function (x) {
                var d = x.d, h = x.h;
                var card = el("div", { "class": "rec-card doc-first" }, [
                    el("div", { "class": "rec-head" }, [
                        el("h4", { text: "👨‍⚕️ " + d.name }),
                        ratingBlock(d.rating, d.reviews)
                    ]),
                    el("div", {}, [
                        el("span", { "class": "chip", text: d.specialization }),
                        d.is_primary ? el("span", { "class": "chip green", text: "Best match" }) : null
                    ]),
                    el("div", { "class": "rec-meta", text: d.qualification + " · " + d.experience + " yrs experience · " + d.availability + " · Fee ₹" + d.fee }),
                    el("div", { "class": "rec-meta", text: "🏥 " + hospitalLine(h) + (h.phone ? " · 📞 " + h.phone : "") }),
                    reviewList(d.recent_reviews, "Doctor reviews"),
                    el("div", { style: "margin-top:10px" }, [
                        el("a", { "class": "btn small", href: "/doctor/" + d.id, text: "All reviews / write a review" })
                    ])
                ]);
                results.appendChild(card);
            });

            // ---- Then hospitals ----
            results.appendChild(el("h3", { "class": "rec-section", text: "🏥 Nearby hospitals (" + data.hospitals.length + ")" }));

            data.hospitals.forEach(function (h) {
                var card = el("div", { "class": "rec-card" }, [
                    el("div", { "class": "rec-head" }, [
                        el("h4", { text: h.name }),
                        ratingBlock(h.rating, h.reviews)
                    ]),
                    el("div", { "class": "rec-meta", text: (h.distance_km !== null ? (h.distance_is_approx ? "≈ " : "") + h.distance_km + " km · " : (h.in_area ? "In your area · " : "")) + h.address + ", " + h.city + (h.phone ? " · 📞 " + h.phone : "") }),
                    el("div", { "class": "rec-meta", text: h.doctors.length ? h.doctors.length + " matching doctor" + (h.doctors.length > 1 ? "s" : "") + " here" : "No matching specialist listed here" }),
                    reviewList(h.recent_reviews, "Hospital reviews"),
                    el("div", { style: "margin-top:10px" }, [
                        el("a", { "class": "btn small", href: "/hospital/" + h.id, text: "Hospital details & reviews" })
                    ])
                ]);
                results.appendChild(card);
            });
        }

        gpsBtn.addEventListener("click", function () {
            if (!navigator.geolocation) { msg.textContent = "Your browser does not support location. Please type your area."; return; }
            msg.textContent = "Waiting for location permission…";
            navigator.geolocation.getCurrentPosition(function (pos) {
                coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                msg.textContent = "Using your current location.";
                load();
            }, function () {
                msg.textContent = "Location was not shared. Please type your area instead.";
            }, { timeout: 10000 });
        });
        goBtn.addEventListener("click", function () { coords = null; msg.textContent = ""; load(); });
        input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); goBtn.click(); } });

        load();
    }

    window.CareFinder = { mount: mount };
})();
