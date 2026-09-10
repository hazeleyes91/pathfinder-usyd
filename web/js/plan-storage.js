/**
 * Pathfinder USYD - Plan Storage Engine (PathfinderPlanV1)
 * Handles session-cookie autosave, file export/import, and UI notifications.
 */

(function () {
    const CURRENT_SCHEMA_VERSION = 1;

    let autoSaveTimeout = null;
    let isDirty = false;
    let lastSavedTime = null;
    let statusTickerInterval = null;

    // Toast Notification System
    function showToast(message, type = "info", persistent = false, onClick = null) {
        let toastContainer = document.getElementById("toast-container");
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.id = "toast-container";
            toastContainer.className =
                "fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none";
            document.body.appendChild(toastContainer);
        }

        const toast = document.createElement("div");
        const bgColors = {
            info: "bg-block text-text border-dim",
            success: "bg-block text-text border-tag-sci",
            error: "bg-block text-text border-warn-req",
        };

        toast.className = `pointer-events-auto px-3.5 py-2 text-[13px] font-semibold rounded border shadow-md transition-all duration-200 opacity-0 transform translate-y-2 flex items-center gap-2 cursor-pointer ${bgColors[type] || bgColors.info}`;
        toast.innerHTML = `<span>${message}</span>`;

        if (onClick) {
            toast.addEventListener("click", () => {
                onClick();
                toast.remove();
            });
        }

        toastContainer.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.remove("opacity-0", "translate-y-2");
        });

        // Auto-dismiss if not persistent
        if (!persistent) {
            setTimeout(() => {
                toast.classList.add("opacity-0", "translate-y-2");
                setTimeout(() => toast.remove(), 200);
            }, 2500);
        } else {
            toast.title = "Click to retry or dismiss";
            if (!onClick) {
                toast.addEventListener("click", () => toast.remove());
            }
        }
    }

    // Save Status Indicator Controller
    function _formatTimeAgo(timestamp) {
        if (!timestamp) return "just now";
        const elapsedSec = Math.floor((Date.now() - timestamp) / 1000);
        if (elapsedSec < 45) return "just now";
        const mins = Math.floor(elapsedSec / 60);
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        return `${hours}h ago`;
    }

    function _renderSavedStatusText() {
        const chip = document.getElementById("save-status");
        if (!chip || !lastSavedTime) return;
        chip.textContent = `Saved · ${_formatTimeAgo(lastSavedTime)}`;
        chip.className =
            "text-[12px] text-muted font-medium self-center px-1.5 py-0.5 rounded";
        chip.onclick = null;
        chip.style.cursor = "default";
    }

    function updateSaveStatus(state) {
        const chip = document.getElementById("save-status");
        if (!chip) return;

        if (state === "saving") {
            chip.textContent = "Saving…";
            chip.className =
                "text-[12px] text-muted opacity-80 font-medium self-center px-1.5 py-0.5 rounded";
            chip.onclick = null;
            chip.style.cursor = "default";
        } else if (state === "saved") {
            isDirty = false;
            lastSavedTime = Date.now();
            _renderSavedStatusText();

            if (!statusTickerInterval) {
                statusTickerInterval = setInterval(() => {
                    if (!isDirty && lastSavedTime) {
                        _renderSavedStatusText();
                    }
                }, 30000);
            }
        } else if (state === "error") {
            chip.textContent = "Save failed (retry)";
            chip.className =
                "text-[12px] text-warn-req font-semibold self-center px-1.5 py-0.5 rounded cursor-pointer border border-warn-req/40 hover:bg-warn-req/10";
            chip.onclick = () => triggerAutoSave(true);
            showToast(
                "Plan not saved — click to retry",
                "error",
                true,
                () => triggerAutoSave(true)
            );
        }
    }

    // Guard unsaved changes on unload
    window.addEventListener("beforeunload", (e) => {
        if (isDirty) {
            e.preventDefault();
            e.returnValue = "";
        }
    });

    // Extract Plan State from DOM
    function serializeCurrentPlan(title = "My Degree Plan") {
        const placements = [];
        const slots = document.querySelectorAll(".row-slots");

        slots.forEach((slot) => {
            const year = parseInt(slot.getAttribute("data-year"), 10);
            const term = slot.getAttribute("data-term");
            const cards = Array.from(slot.children);
            const codes = cards
                .map((card) => card.getAttribute("data-code"))
                .filter(Boolean);

            if (codes.length > 0) {
                placements.push({
                    year,
                    term,
                    codes,
                });
            }
        });

        const modeBtn = document.getElementById("btn-struct");
        const mode =
            modeBtn && modeBtn.classList.contains("active") ? "struct" : "free";

        return {
            schemaVersion: CURRENT_SCHEMA_VERSION,
            metadata: {
                title: title,
                updatedAt: new Date().toISOString(),
            },
            config: {
                mode: mode,
                maxYear: window.maxYear || 3,
            },
            placements: placements,
        };
    }

    // Ensure unit metadata is loaded into window.unitsDb before placing
    async function ensureUnitsLoaded(codes) {
        if (!codes || codes.length === 0) return;
        if (!window.unitsDb) window.unitsDb = {};

        const missing = codes.filter((c) => !window.unitsDb[c]);
        if (missing.length === 0) return;

        try {
            const res = await fetch(
                `/api/units/bulk?codes=${missing.join(",")}`,
                { credentials: "same-origin" }
            );
            if (res.ok) {
                const units = await res.json();
                units.forEach((u) => {
                    window.unitsDb[u.code] = u;
                });
            }
        } catch (e) {
            console.error("Failed to fetch missing units for plan:", e);
        }
    }

    // Hydrate Plan State to DOM
    function deserializePlan(planData) {
        if (!planData || typeof planData !== "object") {
            throw new Error("Invalid plan data format");
        }

        const placements =
            planData.placements || (Array.isArray(planData) ? planData : []);
        const config = planData.config || {};

        // Adjust mode if set
        if (config.mode && typeof window.setMode === "function") {
            window.setMode(config.mode);
        }

        // Determine max year in loaded plan (default to at least 3)
        let maxYearInPlan = config.maxYear || 3;
        placements.forEach((item) => {
            const y = parseInt(item.year, 10);
            if (y > maxYearInPlan) maxYearInPlan = y;
        });

        // Add missing year rows
        while ((window.maxYear || 0) < maxYearInPlan) {
            if (typeof window.addYear === "function") {
                window.addYear();
            } else {
                break;
            }
        }

        // Clear all current slots
        document.querySelectorAll(".row-slots").forEach((slot) => {
            slot.innerHTML = "";
        });

        // Activate seasonal terms if plan uses them
        if (typeof window.applyActiveTermsFromPlan === "function") {
            window.applyActiveTermsFromPlan(placements);
        }

        // Place unit cards
        let placedCount = 0;
        placements.forEach((item) => {
            const codes = item.codes || [];
            codes.forEach((code) => {
                if (typeof window.placeUnitInSlots === "function") {
                    window.placeUnitInSlots(code, item.year, item.term);
                    placedCount++;
                }
            });
        });

        // Trigger plan re-validation
        if (typeof window.validatePlan === "function") {
            window.validatePlan();
        }

        return placedCount;
    }

    // Backend Session Autosave
    async function _executeAutoSave() {
        try {
            updateSaveStatus("saving");
            const planData = serializeCurrentPlan();
            const res = await fetch("/api/plan/autosave", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(planData),
                credentials: "same-origin",
            });

            if (!res.ok) {
                throw new Error(`Server returned ${res.status}`);
            }
            updateSaveStatus("saved");
            return true;
        } catch (e) {
            console.error("Session autosave failed:", e);
            updateSaveStatus("error");
            return false;
        }
    }

    // Debounced Auto-Save Trigger
    function triggerAutoSave(immediate = false) {
        isDirty = true;
        updateSaveStatus("saving");
        if (autoSaveTimeout) {
            clearTimeout(autoSaveTimeout);
        }
        if (immediate) {
            return _executeAutoSave();
        }
        autoSaveTimeout = setTimeout(() => {
            _executeAutoSave();
        }, 500);
    }

    // Load Plan from Active Session Cookie
    async function loadSessionPlan() {
        try {
            const res = await fetch("/api/plan/load", {
                credentials: "same-origin",
            });
            if (!res.ok) return false;
            const data = await res.json();
            if (!data || !data.plan) return false;

            const plan = data.plan;
            const allCodes = [];
            (plan.placements || []).forEach((p) => {
                (p.codes || []).forEach((c) => {
                    if (c && !allCodes.includes(c)) allCodes.push(c);
                });
            });

            await ensureUnitsLoaded(allCodes);
            deserializePlan(plan);
            updateSaveStatus("saved");
            return true;
        } catch (e) {
            console.error("Failed to load plan from session:", e);
            return false;
        }
    }

    // File Export (JSON)
    function exportPlanToFile() {
        try {
            const planData = serializeCurrentPlan();
            const jsonStr = JSON.stringify(planData, null, 2);
            const blob = new Blob([jsonStr], { type: "application/json" });
            const url = URL.createObjectURL(blob);

            const timestamp = new Date().toISOString().split("T")[0];
            const rawTitle =
                (planData.metadata && planData.metadata.title) || "plan";
            const titleSlug = rawTitle
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-+|-+$/g, "");
            const filename = `pathfinder_${titleSlug || "plan"}_${timestamp}.json`;

            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast("Plan exported as JSON", "success");
        } catch (e) {
            console.error("Failed to export plan:", e);
            showToast("Export failed", "error");
        }
    }

    // File Import (JSON)
    async function importPlanFromFile(file) {
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async function (e) {
            try {
                const planData = JSON.parse(e.target.result);
                if (
                    !planData ||
                    typeof planData !== "object" ||
                    (!planData.placements && !Array.isArray(planData))
                ) {
                    throw new Error("Invalid plan file format");
                }

                const allCodes = [];
                (planData.placements || []).forEach((p) => {
                    (p.codes || []).forEach((c) => {
                        if (c && !allCodes.includes(c)) allCodes.push(c);
                    });
                });

                await ensureUnitsLoaded(allCodes);
                const count = deserializePlan(planData);
                triggerAutoSave(true);
                showToast(`Loaded ${count} units from JSON`, "success");
            } catch (err) {
                console.error("Failed to parse plan file:", err);
                showToast("Invalid plan JSON file", "error");
            }
        };
        reader.readAsText(file);
    }

    // Trigger File Picker Dialog
    function triggerImportDialog() {
        let input = document.getElementById("plan-file-input");
        if (!input) {
            input = document.createElement("input");
            input.type = "file";
            input.id = "plan-file-input";
            input.accept = ".json,application/json";
            input.style.display = "none";
            input.onchange = (e) => {
                if (e.target.files && e.target.files[0]) {
                    importPlanFromFile(e.target.files[0]);
                    input.value = ""; // Reset
                }
            };
            document.body.appendChild(input);
        }
        input.click();
    }

    // Export API globally
    window.PathfinderStorage = {
        loadSessionPlan: loadSessionPlan,
        exportPlan: exportPlanToFile,
        importPlan: triggerImportDialog,
        loadPlan: triggerImportDialog,
        savePlan: () => triggerAutoSave(true),
        triggerAutoSave: triggerAutoSave,
        serialize: serializeCurrentPlan,
        deserialize: deserializePlan,
        updateSaveStatus: updateSaveStatus,
    };

    // Legacy window function delegations
    window.savePlanToLocalStorage = () => triggerAutoSave(true);
    window.loadPlanFromLocalStorage = triggerImportDialog;
})();
