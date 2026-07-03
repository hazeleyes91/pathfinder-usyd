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

        // Suppress transitions during clear/reapply to prevent white flash
        var transitionSections = [
            "dsp-prereq-section",
            "dsp-coreq-section",
            "dsp-prohibit-section",
            "dsp-assumed-section",
        ];
        transitionSections.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.classList.add("no-transition");
        });

        clearSectionWarnings();

        var unit = unitsDb && unitsDb[code];
        if (unit) {
            var plainFields = {
                "dsp-prereq": unit.prereq || "None",
                "dsp-coreq": unit.coreq || "None",
                "dsp-prohibit": unit.prohibit || "None",
                "dsp-assumed": unit.assumed || "None",
            };

            Object.entries(plainFields).forEach(function (entry) {
                var id = entry[0];
                var text = entry[1];
                var el = document.getElementById(id);
                if (el) el.innerHTML = window.WarningUtils.escapeHtml(text);
            });
        }

        var allWarnings = warnings || [];
        var unitWarnings = allWarnings.filter(function (warning) {
            return warning.unit_code === code;
        });

        var sectionMap = {
            prereq_unmet: {
                sectionId: "dsp-prereq-section",
                spanId: "dsp-prereq",
                field: "prereq",
            },
            coreq_unmet: {
                sectionId: "dsp-coreq-section",
                spanId: "dsp-coreq",
                field: "coreq",
            },
            prohibited: {
                sectionId: "dsp-prohibit-section",
                spanId: "dsp-prohibit",
                field: "prohibit",
            },
        };

        unitWarnings.forEach(function (warning) {
            var isSoft = window.WarningUtils.isSoftWarning(warning);

            if (warning.type === "session_mismatch") {
                var availField = document.getElementById("dsp-avail-field");
                if (availField) availField.classList.add("warn-miss");
                return;
            }

            var mapping = sectionMap[warning.type];
            if (!mapping) return;

            var section = document.getElementById(mapping.sectionId);
            var span = document.getElementById(mapping.spanId);
            if (!section || !span) return;

            section.classList.add(isSoft ? "warn-soft" : "warn-req");

            var currentUnit = unitsDb && unitsDb[code];
            var rawText = currentUnit
                ? currentUnit[mapping.field] || "None"
                : span.textContent;

            span.innerHTML = window.WarningUtils.annotateText(
                rawText,
                warning.affected_codes,
                isSoft,
            );
        });

        // Re-enable transitions after the frame paints
        requestAnimationFrame(function () {
            transitionSections.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.classList.remove("no-transition");
            });
        });

        var placedCard = document.querySelector(
            '.placed-unit-card[data-code="' + code + '"]',
        );
        if (placedCard) {
            var row = placedCard.closest(".row-slots");
            if (row) {
                var year = parseInt(row.getAttribute("data-year"), 10);
                var term = row.getAttribute("data-term");
                var overloaded = allWarnings.some(function (warning) {
                    return (
                        warning.type === "overload" &&
                        warning.year === year &&
                        warning.term === term
                    );
                });

                var banner = document.getElementById("dsp-overload-banner");
                if (banner) banner.style.display = overloaded ? "block" : "none";
            }
        }
    }

    window.WarningDetails = {
        clearSectionWarnings: clearSectionWarnings,
        updateDetailsWarnings: updateDetailsWarnings,
    };
})();
