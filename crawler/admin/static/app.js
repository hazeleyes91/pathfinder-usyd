// admin/static/app.js

// Hardcoded Mock Data for static file preview fallback
const mockRulesDatabase = {
  "AGRI3888": {
    "unit_code": "AGRI3888",
    "title": "Digital Crop and Pasture Production",
    "prerequisites_expr": {
      "type": "logical",
      "rule": {
        "type": "logical",
        "operator": "AND",
        "operands": [
          { "type": "credit_points", "credit_points": 12, "level": null, "unit_codes": null, "subjects": null },
          { "type": "logical", "operator": "OR", "operands": [] }
        ]
      }
    },
    "corequisites_expr": { "type": "none" },
    "prohibitions_expr": { "type": "unit", "unit_code": "AGRO4003" },
    "needs_curation": true,
    "flagged": false,
    "raw_rules": {
      "prerequisites": "12 credit points from (AGRO3004 or AGRI2001 or BIOL2X31 or AGEN2005)",
      "corequisites": "None",
      "prohibitions": "AGRO4003"
    }
  },
  "COMP2123": {
    "unit_code": "COMP2123",
    "title": "Data Structures and Algorithms",
    "prerequisites_expr": {
      "type": "logical",
      "operator": "OR",
      "operands": [
        { "type": "unit", "unit_code": "INFO1110" },
        { "type": "unit", "unit_code": "INFO1910" },
        { "type": "unit", "unit_code": "INFO1113" }
      ]
    },
    "corequisites_expr": { "type": "none" },
    "prohibitions_expr": {
      "type": "logical",
      "operator": "OR",
      "operands": [
        { "type": "unit", "unit_code": "INFO1105" },
        { "type": "unit", "unit_code": "COMP2823" }
      ]
    },
    "needs_curation": false,
    "flagged": false,
    "raw_rules": {
      "prerequisites": "INFO1110 or INFO1910 or INFO1113",
      "corequisites": "None",
      "prohibitions": "INFO1105 or COMP2823"
    }
  },
  "COMP2823": {
    "unit_code": "COMP2823",
    "title": "Data Structures and Algorithms (Adv)",
    "prerequisites_expr": { "type": "none" },
    "corequisites_expr": { "type": "none" },
    "prohibitions_expr": { "type": "unit", "unit_code": "COMP2123" },
    "needs_curation": true,
    "flagged": false,
    "raw_rules": {
      "prerequisites": "Distinction level results in (INFO1110 or INFO1910 or INFO1113)",
      "corequisites": "None",
      "prohibitions": "COMP2123"
    }
  }
};

let rulesDatabase = {};
let currentFilter = "all";
let searchQuery = "";
let isLiveMode = false;

// Initialize app
document.addEventListener("DOMContentLoaded", async () => {
    await loadRules();
    setupEventListeners();
});

// Load rules from API or fallback to mock data
async function loadRules() {
    try {
        const response = await fetch("/api/rules");
        if (response.ok) {
            rulesDatabase = await response.json();
            isLiveMode = true;
            console.log("Loaded live data from FastAPI backend.");
        } else {
            throw new Error("API returned non-200");
        }
    } catch (e) {
        rulesDatabase = mockRulesDatabase;
        isLiveMode = false;
        console.warn("Failed to fetch live API rules. Operating in static mockup mode with fallback records.", e);
    }
    updateStats();
    renderGrid();
}

// Update header counters
function updateStats() {
    const total = Object.keys(rulesDatabase).length;
    let pending = 0;
    let curated = 0;
    let flagged = 0;
    
    Object.values(rulesDatabase).forEach(unit => {
        if (unit.needs_curation) {
            pending++;
        } else {
            curated++;
        }
        if (unit.flagged) {
            flagged++;
        }
    });
    
    document.getElementById("stat-total").innerText = total;
    document.getElementById("stat-curated").innerText = curated;
    document.getElementById("stat-pending").innerText = pending;
    document.getElementById("stat-flagged").innerText = flagged;
}

// Bind navigation and search actions
function setupEventListeners() {
    // Search input handler
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            searchQuery = e.target.value.toLowerCase().trim();
            renderGrid();
        });
    }

    // Filter pills handler
    const pills = document.querySelectorAll(".filter-pill");
    pills.forEach(pill => {
        pill.addEventListener("click", (e) => {
            pills.forEach(p => p.classList.remove("active"));
            e.target.classList.add("active");
            currentFilter = e.target.getAttribute("data-filter");
            renderGrid();
        });
    });

    // Tab switching handler
    const tabCuration = document.getElementById("tab-curation");
    const tabStats = document.getElementById("tab-stats");
    const curationView = document.getElementById("curation-view");
    const statsView = document.getElementById("stats-view");
    
    if (tabCuration && tabStats && curationView && statsView) {
        tabCuration.addEventListener("click", () => {
            tabCuration.classList.add("active");
            tabStats.classList.remove("active");
            curationView.classList.remove("hidden");
            statsView.classList.add("hidden");
            updateStats();
            renderGrid();
        });
        
        tabStats.addEventListener("click", () => {
            tabStats.classList.add("active");
            tabCuration.classList.remove("active");
            curationView.classList.add("hidden");
            statsView.classList.remove("hidden");
            loadAndRenderStats();
        });
    }
}

// Renders the responsive rules list
function renderGrid() {
    const grid = document.getElementById("rules-grid");
    grid.innerHTML = "";
    
    const filteredUnits = Object.values(rulesDatabase).filter(unit => {
        // Apply search query match
        const matchesSearch = unit.unit_code.toLowerCase().includes(searchQuery) || 
                              unit.title.toLowerCase().includes(searchQuery);
                              
        // Apply category filter match
        let matchesFilter = true;
        if (currentFilter === "pending") {
            matchesFilter = unit.needs_curation === true;
        } else if (currentFilter === "curated") {
            matchesFilter = unit.needs_curation === false;
        } else if (currentFilter === "flagged") {
            matchesFilter = unit.flagged === true;
        }
        
        return matchesSearch && matchesFilter;
    });

    if (filteredUnits.length === 0) {
        grid.innerHTML = `<div class="empty-state">No units match the selected search or filter criteria.</div>`;
        return;
    }

    filteredUnits.forEach(unit => {
        const card = createUnitCard(unit);
        grid.appendChild(card);
    });
}

// Create individual unit curation card DOM node (Split into 2 columns: left: text/actions; right: json editor)
function createUnitCard(unit) {
    const card = document.createElement("article");
    card.className = `bg-bg border p-6 flex flex-row gap-6 transition-colors border-text ${unit.needs_curation ? 'border-warn-pre' : ''}`;
    card.id = `card-${unit.unit_code}`;

    const statusText = unit.needs_curation ? "Needs Curation" : "Curated";
    const statusClass = unit.needs_curation ? "pending" : "verified";
    
    const isFlagged = unit.flagged || false;
    const flagText = isFlagged ? "Remove Flag" : "Flag for Later";
    
    // Extract any soft warnings
    const warnings = [];
    const getParserWarnings = (expr) => {
        if (!expr) return null;
        let list = [];
        if (expr.warnings) list = list.concat(expr.warnings);
        if (expr.rule && expr.rule.warnings) list = list.concat(expr.rule.warnings);
        
        if (list.length === 0) return null;
        return list.map(w => {
            return w.split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        }).join(', ');
    };
    
    const prereqWarn = getParserWarnings(unit.prerequisites_expr);
    if (prereqWarn) warnings.push(`Prerequisites: ${prereqWarn}`);
    
    const coreqWarn = getParserWarnings(unit.corequisites_expr);
    if (coreqWarn) warnings.push(`Corequisites: ${coreqWarn}`);
    
    const prohibWarn = getParserWarnings(unit.prohibitions_expr);
    if (prohibWarn) warnings.push(`Prohibitions: ${prohibWarn}`);
    
    const warningsHtml = warnings.length > 0 ? `
        <div class="bg-transparent border border-warn-miss p-3 flex flex-col gap-1.5 mt-2">
            ${warnings.map(w => `
                <div class="flex items-start gap-2 text-warn-miss text-[13px] leading-snug">
                    <span class="mt-0.5">⚠️</span>
                    <span class="font-semibold">${w}</span>
                </div>
            `).join('')}
        </div>
    ` : '';
    
    card.innerHTML = `
        <div class="flex-1 flex flex-col gap-4 border-r border-text pr-6">
            <div class="flex justify-between items-start">
                <div>
                    <h2 class="font-extrabold text-[20px] tracking-tight">${unit.unit_code}</h2>
                    <div class="text-[14px] text-dim font-semibold">${unit.title}</div>
                </div>
            </div>
            
            ${warningsHtml}
            
            <div class="flex flex-col gap-3 mt-2">
                <div class="flex flex-col gap-1">
                    <strong class="text-[12px] font-extrabold uppercase tracking-wide text-dim">Prerequisites Raw:</strong>
                    <div class="bg-block border border-dim p-2.5 text-dim text-[13px] leading-relaxed h-[60px] overflow-y-auto">${unit.raw_rules.prerequisites || 'None'}</div>
                </div>
                <div class="flex flex-col gap-1">
                    <strong class="text-[12px] font-extrabold uppercase tracking-wide text-dim">Corequisites Raw:</strong>
                    <div class="bg-block border border-dim p-2.5 text-dim text-[13px] leading-relaxed h-[60px] overflow-y-auto">${unit.raw_rules.corequisites || 'None'}</div>
                </div>
                <div class="flex flex-col gap-1">
                    <strong class="text-[12px] font-extrabold uppercase tracking-wide text-dim">Prohibitions Raw:</strong>
                    <div class="bg-block border border-dim p-2.5 text-dim text-[13px] leading-relaxed h-[60px] overflow-y-auto">${unit.raw_rules.prohibitions || 'None'}</div>
                </div>
            </div>

            <div class="flex gap-3 mt-auto pt-4">
                <button class="bg-active text-active-txt px-4 py-2 text-[13px]" id="save-btn-${unit.unit_code}" onclick="saveUnitEdits('${unit.unit_code}')">Save Changes</button>
                <button class="border border-text px-4 py-2 text-[13px] ${isFlagged ? 'bg-text text-bg' : 'bg-transparent text-text'}" id="flag-btn-${unit.unit_code}" onclick="toggleFlag('${unit.unit_code}')">${flagText}</button>
                <button class="border px-4 py-2 text-[13px] ${unit.needs_curation ? 'border-warn-pre text-warn-pre' : 'border-text text-text'}" onclick="toggleStatus('${unit.unit_code}')">${statusText}</button>
            </div>
        </div>
        
        <div class="flex-[1.2] flex flex-col gap-4">
            <div class="flex border-b border-text">
                <button class="tab-btn active" onclick="switchTab(this, 'prerequisites')">Prereq JSON</button>
                <button class="tab-btn" onclick="switchTab(this, 'corequisites')">Coreq JSON</button>
                <button class="tab-btn" onclick="switchTab(this, 'prohibitions')">Prohibitions JSON</button>
            </div>

            <div class="flex flex-col flex-1 min-h-[240px]" id="content-${unit.unit_code}">
                <!-- Active JSON editor textarea will render here -->
            </div>
        </div>
    `;

    // Render the default tab (prerequisites)
    renderTabContent(card.querySelector("#content-" + unit.unit_code), unit, 'prerequisites');

    return card;
}

// Tabs state switching
window.switchTab = function(btnElement, type) {
    const tabsContainer = btnElement.parentElement;
    const tabContent = tabsContainer.nextElementSibling;
    const unitCode = tabContent.id.replace("content-", "");
    
    // Toggle active classes on tab buttons
    tabsContainer.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    btnElement.classList.add("active");
    
    const unit = rulesDatabase[unitCode];
    renderTabContent(tabContent, unit, type);
};

// Render tab inner JSON editor fields
function renderTabContent(container, unit, type) {
    const exprKey = `${type}_expr`;
    const exprObj = unit[exprKey] || { type: "none" };
    const exprStr = JSON.stringify(exprObj, null, 2);

    container.innerHTML = `
        <div class="flex flex-col flex-1 relative gap-2">
            <textarea class="json-editor valid" id="editor-${unit.unit_code}-${type}" oninput="validateEditor(this)" spellcheck="false">${exprStr}</textarea>
            <div class="text-[12px] font-bold flex items-center gap-1 text-text" id="msg-${unit.unit_code}-${type}">✓ Valid JSON Schema</div>
        </div>
    `;
}

// Live JSON Editor Syntax validation
window.validateEditor = function(textarea) {
    const value = textarea.value.trim();
    const idParts = textarea.id.split("-");
    const unitCode = idParts[1];
    const type = idParts[2];
    const msgDiv = document.getElementById(`msg-${unitCode}-${type}`);
    const saveBtn = document.getElementById(`save-btn-${unitCode}`);

    try {
        const parsed = JSON.parse(value);
        
        // Basic schema validator checks
        if (!parsed.type) {
            throw new Error("Missing required root field: 'type'");
        }
        
        textarea.classList.remove("invalid");
        textarea.classList.add("valid");
        msgDiv.className = "text-[12px] font-bold flex items-center gap-1 text-text";
        msgDiv.innerText = "✓ Valid JSON Schema";
        saveBtn.removeAttribute("disabled");
        saveBtn.classList.remove("opacity-50", "cursor-not-allowed");
    } catch (err) {
        textarea.classList.remove("valid");
        textarea.classList.add("invalid");
        msgDiv.className = "text-[12px] font-bold flex items-center gap-1 text-warn-pre";
        msgDiv.innerText = `✗ JSON Syntax Error: ${err.message}`;
        saveBtn.setAttribute("disabled", "true");
        saveBtn.classList.add("opacity-50", "cursor-not-allowed");
    }
};

// Toggle unit curation flag
window.toggleStatus = async function(unitCode) {
    const unit = rulesDatabase[unitCode];
    unit.needs_curation = !unit.needs_curation;
    
    if (isLiveMode) {
        try {
            await syncUnitWithServer(unitCode);
        } catch (e) {
            console.error("Failed to sync toggle to backend", e);
        }
    }
    
    updateStats();
    renderGrid();
};

// Toggle unit flagged for later status
window.toggleFlag = async function(unitCode) {
    const unit = rulesDatabase[unitCode];
    unit.flagged = !unit.flagged;
    
    if (isLiveMode) {
        try {
            await syncUnitWithServer(unitCode);
        } catch (e) {
            console.error("Failed to sync flag status to backend", e);
        }
    }
    
    updateStats();
    renderGrid();
};

// Save edited tabs json schemas
window.saveUnitEdits = async function(unitCode) {
    const unit = rulesDatabase[unitCode];
    
    // Read from current input textareas
    const types = ['prerequisites', 'corequisites', 'prohibitions'];
    let hasError = false;
    
    types.forEach(type => {
        const textarea = document.getElementById(`editor-${unitCode}-${type}`);
        if (textarea) {
            try {
                const parsed = JSON.parse(textarea.value);
                unit[`${type}_expr`] = parsed;
            } catch (e) {
                hasError = true;
            }
        }
    });

    if (hasError) {
        alert("Cannot save. One or more expressions contain JSON syntax errors.");
        return;
    }

    // Toggle Needs Curation to false on explicit user save
    unit.needs_curation = false;

    if (isLiveMode) {
        try {
            const success = await syncUnitWithServer(unitCode);
            if (success) {
                alert(`Successfully saved and verified ${unitCode}.`);
            } else {
                alert(`Validation failed on backend for ${unitCode}. Please check schema structure.`);
                unit.needs_curation = true; // revert
            }
        } catch (e) {
            alert(`Network error saving rules for ${unitCode}.`);
            unit.needs_curation = true;
        }
    } else {
        alert(`[Mockup Mode] Saved rules for ${unitCode} locally in browser memory.`);
    }

    updateStats();
    renderGrid();
};

// Send updated rule entry to FastAPI server
async function syncUnitWithServer(unitCode) {
    const unit = rulesDatabase[unitCode];
    const payload = {
        prerequisites_expr: unit.prerequisites_expr,
        corequisites_expr: unit.corequisites_expr,
        prohibitions_expr: unit.prohibitions_expr,
        needs_curation: unit.needs_curation,
        flagged: unit.flagged || false
    };

    const response = await fetch(`/api/rules/${unitCode}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    return response.ok;
}

// Fetch stats from backend and populate Stats View
async function loadAndRenderStats() {
    if (!isLiveMode) {
        document.getElementById("dash-total").innerText = Object.keys(rulesDatabase).length;
        document.getElementById("dash-active").innerText = Object.keys(rulesDatabase).length;
        document.getElementById("dash-curated").innerText = Object.values(rulesDatabase).filter(u => !u.needs_curation).length;
        document.getElementById("dash-pending").innerText = Object.values(rulesDatabase).filter(u => u.needs_curation).length;
        document.getElementById("dash-flagged").innerText = Object.values(rulesDatabase).filter(u => u.flagged).length;
        return;
    }
    
    try {
        const res = await fetch("/api/stats");
        if (!res.ok) throw new Error("Stats API error");
        const data = await res.json();
        
        // 1. Overview Cards
        document.getElementById("dash-total").innerText = data.total_units;
        document.getElementById("dash-active").innerText = data.active_units;
        document.getElementById("dash-curated").innerText = data.curated_units;
        document.getElementById("dash-pending").innerText = data.needs_curation_units;
        document.getElementById("dash-flagged").innerText = data.flagged_units;
        
        // 2. Validity Breakdown
        document.getElementById("validity-planning").innerText = data.validity_counts.valid_for_planning || 0;
        document.getElementById("validity-review").innerText = data.validity_counts.needs_manual_review || 0;
        document.getElementById("validity-blocked").innerText = data.validity_counts.blocked_by_curator || 0;
        
        // 3. Warnings Breakdown
        const warningsContainer = document.getElementById("warnings-list-container");
        warningsContainer.innerHTML = "";
        
        const formatWarningKey = (w) => {
            return w.split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        };
        
        const allWarningTypes = [
            "degree_restriction",
            "grade_threshold",
            "logic_simplified",
            "permission_required",
            "recommended_preparation",
            "other"
        ];
        
        allWarningTypes.forEach(warn => {
            const count = data.warning_counts[warn] || 0;
            const div = document.createElement("div");
            div.className = "flex justify-between py-1 border-b border-block";
            div.innerHTML = `
                <span>${formatWarningKey(warn)}:</span>
                <span class="font-bold text-text">${count}</span>
            `;
            warningsContainer.appendChild(div);
        });
        
        // 4. Subject Area Tables
        const tbody = document.getElementById("subject-table-body");
        tbody.innerHTML = "";
        data.top_subject_stats.forEach(item => {
            const tr = document.createElement("tr");
            tr.className = "border-b border-block";
            tr.innerHTML = `
                <td class="py-2 font-bold">${item.subject}</td>
                <td class="py-2 text-right">${item.total}</td>
                <td class="py-2 text-right text-warn-pre font-bold">${item.needs_curation}</td>
                <td class="py-2 text-right">${item.warnings_count}</td>
            `;
            tbody.appendChild(tr);
        });
        
        // 5. AI Logs
        const logsContainer = document.getElementById("ai-logs-container");
        logsContainer.innerHTML = "";
        if (!data.recent_ai_attempts || data.recent_ai_attempts.length === 0) {
            logsContainer.innerHTML = `<div class="text-[13px] text-dim italic py-4">No recent AI parsing attempts recorded.</div>`;
        } else {
            const sortedAttempts = [...data.recent_ai_attempts].reverse();
            sortedAttempts.forEach(log => {
                const item = document.createElement("div");
                item.className = "border border-block p-3 flex flex-col gap-2 bg-block/10";
                item.innerHTML = `
                    <div class="flex justify-between text-[11px] font-extrabold uppercase tracking-wide text-dim">
                        <span>Unit: <b class="text-text">${log.unit_code}</b> (${log.field_name})</span>
                    </div>
                    <div class="text-[12px] font-semibold">Raw: <span class="font-mono text-dim select-all">${log.raw_text}</span></div>
                    <details class="text-[12px]">
                        <summary class="cursor-pointer text-dim hover:text-text select-none">Show Parsed Output</summary>
                        <pre class="bg-block p-2 mt-1 overflow-x-auto text-[11px] font-mono text-text">${JSON.stringify(log.parsed_output, null, 2)}</pre>
                    </details>
                `;
                logsContainer.appendChild(item);
            });
        }
        
    } catch (err) {
        console.error("Failed to load/render stats", err);
    }
}
