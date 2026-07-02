(function () {
    function clearCardAndRowWarnings() {
        document.querySelectorAll(".badges-container").forEach(function (container) {
            container.innerHTML = "";
        });

        document
            .querySelectorAll(".semester-row-header")
            .forEach(function (header) {
                var overloadBadge = header.querySelector(".overload-badge");
                if (overloadBadge) overloadBadge.remove();
            });
    }

    function renderCardAndRowWarnings(warnings) {
        if (!window.WarningUtils) return;

        (warnings || []).forEach(function (warning) {
            if (warning.type === "overload") {
                var rowId = "y" + warning.year + "-" + warning.term + "-row";
                var rowEl = document.getElementById(rowId);
                if (!rowEl) return;

                var header = rowEl.querySelector(".semester-row-header");
                if (!header) return;

                var badge = document.createElement("span");
                badge.className =
                    "overload-badge text-warn-miss ml-2 font-bold cursor-help";
                badge.title = warning.message;
                badge.textContent = "⚠ OVERLOAD";
                header.appendChild(badge);
                return;
            }

            var slot = document.querySelector(
                '.row-slots[data-year="' +
                    warning.year +
                    '"][data-term="' +
                    warning.term +
                    '"]',
            );
            if (!slot) return;

            var card = slot.querySelector('[data-code="' + warning.unit_code + '"]');
            if (!card) return;

            var badgesContainer = card.querySelector(".badges-container");
            if (!badgesContainer) return;

            var display = window.WarningUtils.getWarningPresentation(warning);

            var badge = badgesContainer.querySelector(
                '[data-warn-type="' + display.typeKey + '"]',
            );

            if (!badge) {
                badge = document.createElement("span");
                badge.className =
                    display.colorClass +
                    " warning-badge-icon cursor-help flex items-center group relative";
                badge.setAttribute("data-warn-type", display.typeKey);
                badge.innerHTML =
                    display.svgMarkup +
                    '<div class="warning-tooltip ' +
                    display.boxClass +
                    '">' +
                    display.tooltipMsg +
                    "</div>";
                badgesContainer.appendChild(badge);
            } else {
                var tooltip = badge.querySelector(".warning-tooltip");
                if (tooltip) {
                    tooltip.textContent += "\n• " + display.tooltipMsg;
                }
            }
        });
    }

    function renderActiveWarningsSummary(warnings) {
        if (!window.WarningUtils) return;

        var container = document.getElementById("dsp-global-warnings");
        if (!container) return;

        container.innerHTML = "";

        if (!warnings || warnings.length === 0) return;

        var header = document.createElement("div");
        header.className =
            "font-extrabold text-[12px] uppercase tracking-wide text-text mb-1";
        header.textContent = "Active Plan Warnings";
        container.appendChild(header);

        warnings.forEach(function (warning) {
            var display = window.WarningUtils.getWarningPresentation(warning);
            var boxClass = display.boxClass;
            if (warning.type === "overload" || warning.type === "session_mismatch") {
                boxClass = "warning-box-miss";
            }

            var item = document.createElement("div");
            item.className =
                "text-[12px] " +
                boxClass +
                " p-2 rounded-[4px] mb-1.5 leading-snug border text-left";
            item.innerHTML =
                "<span class=\"font-bold\">" +
                (warning.unit_code ? warning.unit_code + ": " : "") +
                "</span>" +
                window.WarningUtils.getSummaryTitle(warning);
            container.appendChild(item);
        });
    }

    window.WarningRenderers = {
        clearCardAndRowWarnings: clearCardAndRowWarnings,
        renderActiveWarningsSummary: renderActiveWarningsSummary,
        renderCardAndRowWarnings: renderCardAndRowWarnings,
    };
})();
