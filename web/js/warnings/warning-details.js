(function () {
    function clearSectionWarnings() {
        [
            "dsp-prereq-section",
            "dsp-coreq-section",
            "dsp-prohibit-section",
            "dsp-assumed-section",
        ].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.classList.remove("warn-req", "warn-soft", "warn-miss");
        });

        var availField = document.getElementById("dsp-avail-field");
        if (availField) {
            availField.classList.remove("warn-req", "warn-soft", "warn-miss");
        }

        var banner = document.getElementById("dsp-overload-banner");
        if (banner) banner.style.display = "none";
    }

    function updateDetailsWarnings(code, unitsDb, warnings) {
        if (!window.WarningUtils) return;

        var unit = unitsDb && unitsDb[code];
        if (!unit) {
            clearSectionWarnings();
            return;
        }

        var allWarnings = warnings || [];
        var unitWarnings = allWarnings.filter(function (warning) {
            return warning.unit_code === code;
        });

        // Precompute warning state for each details sidebar block
        var sections = {
            prereq: {
                sectionId: "dsp-prereq-section",
                spanId: "dsp-prereq",
                rawText: unit.prereq || "None",
                warningClass: null,
                isSoft: false,
                affectedCodes: []
            },
            coreq: {
                sectionId: "dsp-coreq-section",
                spanId: "dsp-coreq",
                rawText: unit.coreq || "None",
                warningClass: null,
                isSoft: false,
                affectedCodes: []
            },
            prohibit: {
                sectionId: "dsp-prohibit-section",
                spanId: "dsp-prohibit",
                rawText: unit.prohibit || "None",
                warningClass: null,
                isSoft: false,
                affectedCodes: []
            },
            assumed: {
                sectionId: "dsp-assumed-section",
                spanId: "dsp-assumed",
                rawText: unit.assumed || "None",
                warningClass: null,
                isSoft: false,
                affectedCodes: []
            }
        };

        var availWarningClass = null;

        unitWarnings.forEach(function (warning) {
            if (warning.type === "session_mismatch") {
                availWarningClass = "warn-miss";
                return;
            }

            var isSoft = window.WarningUtils.isSoftWarning(warning);
            var key = null;
            if (warning.type === "prereq_unmet") key = "prereq";
            else if (warning.type === "coreq_unmet") key = "coreq";
            else if (warning.type === "prohibited") key = "prohibit";

            if (key) {
                var sec = sections[key];
                sec.isSoft = isSoft;
                sec.warningClass = isSoft ? "warn-soft" : "warn-req";
                if (warning.affected_codes) {
                    sec.affectedCodes = sec.affectedCodes.concat(warning.affected_codes);
                }
            }
        });

        // Apply calculated states to the DOM in a single pass
        Object.keys(sections).forEach(function (key) {
            var sec = sections[key];
            var sectionEl = document.getElementById(sec.sectionId);
            var spanEl = document.getElementById(sec.spanId);
            if (!sectionEl || !spanEl) return;

            // Apply warning classes
            sectionEl.classList.remove("warn-req", "warn-soft", "warn-miss");
            if (sec.warningClass) {
                sectionEl.classList.add(sec.warningClass);
            }

            // Populate text/markup
            if (sec.warningClass) {
                spanEl.innerHTML = window.WarningUtils.annotateText(
                    sec.rawText,
                    sec.affectedCodes,
                    sec.isSoft
                );
            } else {
                spanEl.innerHTML = window.WarningUtils.escapeHtml(sec.rawText);
            }
        });

        // Update availability warning class
        var availField = document.getElementById("dsp-avail-field");
        if (availField) {
            availField.classList.remove("warn-req", "warn-soft", "warn-miss");
            if (availWarningClass) {
                availField.classList.add(availWarningClass);
            }
        }

        // Update overload banner
        var banner = document.getElementById("dsp-overload-banner");
        if (banner) {
            var overloaded = false;
            var placedCard = document.querySelector(
                '.placed-unit-card[data-code="' + code + '"]',
            );
            if (placedCard) {
                var row = placedCard.closest(".row-slots");
                if (row) {
                    var year = parseInt(row.getAttribute("data-year"), 10);
                    var term = row.getAttribute("data-term");
                    overloaded = allWarnings.some(function (warning) {
                        return (
                            warning.type === "overload" &&
                            warning.year === year &&
                            warning.term === term
                        );
                    });
                }
            }
            banner.style.display = overloaded ? "block" : "none";
        }
    }

    window.WarningDetails = {
        clearSectionWarnings: clearSectionWarnings,
        updateDetailsWarnings: updateDetailsWarnings,
    };
})();
