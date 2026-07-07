(function () {
    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function annotateText(rawText, affectedCodes, boldGrades) {
        var html = escapeHtml(rawText);

        (affectedCodes || []).forEach(function (code) {
            html = html.replace(
                new RegExp("\\b" + code + "\\b", "g"),
                "<strong>" + code + "</strong>",
            );
        });

        if (boldGrades) {
            html = html.replace(
                /\b(\d{2,3}(?:\.\d+)?%?|High Distinction|Distinction|Credit|Pass|Merit|HD|DN|CR|PS|FL)\b/g,
                "<strong>$1</strong>",
            );
        }

        return html;
    }

    function isSoftWarning(warning) {
        return !!(
            warning &&
            warning.message &&
            warning.message.startsWith("Advisory check")
        );
    }

    function humanizeSoftWarningCodes(rawWarningText) {
        var warningMap = {
            degree_restriction: "Degree restriction applies",
            grade_threshold: "Grade requirement applies",
            logic_simplified: "Complex logic simplified",
            permission_required: "Departmental permission required",
            recommended_preparation: "Recommended preparation",
            other: "Other advisory constraints",
        };

        return (rawWarningText || "")
            .split(", ")
            .map(function (entry) {
                var normalized = entry.trim().toLowerCase();
                return warningMap[normalized] || entry;
            })
            .join(", ");
    }

    function warningBoxClassFromTypeKey(typeKey) {
        if (typeKey === "miss") return "warning-box-miss";
        if (typeKey.indexOf("soft") === 0) return "warning-box-soft";
        return "warning-box-req";
    }

    function getWarningPresentation(warning) {
        var colorClass = "text-warn-req";
        var svgMarkup = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></svg>';
        var typeKey = "req";
        var tooltipMsg = warning.message || "";
        var soft = isSoftWarning(warning);

        if (soft) {
            colorClass = "text-warn-soft";

            var lowerMsg = (warning.message || "").toLowerCase();
            if (
                lowerMsg.includes("grade") ||
                lowerMsg.includes("mark") ||
                lowerMsg.includes("distinction") ||
                lowerMsg.includes("credit") ||
                lowerMsg.includes("pass")
            ) {
                typeKey = "soft-grade";
            } else if (
                lowerMsg.includes("permission") ||
                lowerMsg.includes("consent") ||
                lowerMsg.includes("approval") ||
                lowerMsg.includes("coordinator")
            ) {
                typeKey = "soft-permission";
            } else if (lowerMsg.includes("assumed knowledge")) {
                typeKey = "soft-assumed";
            } else if (
                lowerMsg.includes("manual review") ||
                lowerMsg.includes("unparsed")
            ) {
                typeKey = "soft-manual";
            } else {
                typeKey = "soft";
            }

            var rawWarning = (warning.soft_warning || warning.message || "")
                .replace(/^Advisory check for [A-Z0-9]+:\s*/i, "")
                .replace(/^Soft warning\(s\):\s*/i, "");
            tooltipMsg = humanizeSoftWarningCodes(rawWarning);

            svgMarkup = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';
        } else {
            if (warning.soft_warning) {
                var mapped = humanizeSoftWarningCodes(
                    (warning.soft_warning || "").replace(
                        /^Soft warning\(s\):\s*/i,
                        "",
                    ),
                );
                tooltipMsg += " (" + mapped + ")";
            }

            if (warning.type === "session_mismatch") {
                colorClass = "text-warn-miss";
                typeKey = "miss";
                svgMarkup = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>';
            }
        }

        return {
            colorClass: colorClass,
            svgMarkup: svgMarkup,
            typeKey: typeKey,
            tooltipMsg: (tooltipMsg || "").trim(),
            boxClass: warningBoxClassFromTypeKey(typeKey),
            isSoft: soft,
        };
    }

    function getSummaryTitle(warning) {
        var soft = isSoftWarning(warning);

        if (warning.type === "overload") return "Overload Warning";
        if (warning.type === "session_mismatch") return "Session Mismatch";
        if (warning.type === "prereq_unmet" && !soft) return "Unmet Prerequisite";
        if (warning.type === "coreq_unmet" && !soft) return "Corequisite Unmet";
        if (warning.type === "prohibited") return "Prohibition Conflict";

        if (soft) {
            var lowerMsg = (warning.message || "").toLowerCase();
            if (
                lowerMsg.includes("grade") ||
                lowerMsg.includes("mark") ||
                lowerMsg.includes("threshold")
            ) {
                return "Grade Requirement";
            }
            if (
                lowerMsg.includes("permission") ||
                lowerMsg.includes("consent") ||
                lowerMsg.includes("coordinator")
            ) {
                return "Permission Required";
            }
            if (lowerMsg.includes("assumed")) return "Assumed Knowledge";
            return "Advisory Warning";
        }

        return (warning.type || "warning").replace(/_/g, " ");
    }

    window.WarningUtils = {
        annotateText: annotateText,
        escapeHtml: escapeHtml,
        getSummaryTitle: getSummaryTitle,
        getWarningPresentation: getWarningPresentation,
        isSoftWarning: isSoftWarning,
    };
})();
