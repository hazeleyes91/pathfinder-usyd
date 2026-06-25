// crawlers/curation_static/app.js

// 1. Mock Rules Data (Fallback for standalone file viewing)
const MOCK_RULES = {
  "AGRI3888": {
    "unit_code": "AGRI3888",
    "title": "Digital Crop and Pasture Production",
    "needs_curation": true,
    "raw_rules": {
      "prerequisites": "12 credit points from (AGRO3004 or AGRI2001 or BIOL2X31 or AGEN2005)",
      "corequisites": "None",
      "prohibitions": "AGRO4003"
    },
    "prerequisites_expr": {
      "type": "logical",
      "rule": {
        "type": "logical",
        "operator": "AND",
        "operands": [
          { "type": "credit_points", "credit_points": 12, "level": null, "subject": "ANY" },
          { "type": "logical", "operator": "OR", "operands": [] }
        ]
      }
    },
    "corequisites_expr": { "type": "none", "rule": null },
    "prohibitions_expr": { "type": "unit", "unit_code": "AGRO4003" }
  },
  "AMED3001": {
    "unit_code": "AMED3001",
    "title": "Cancer",
    "needs_curation": true,
    "raw_rules": {
      "prerequisites": "12 credit points from (IMMU2101 or MEDS2004 or MIMI2002)",
      "corequisites": "None",
      "prohibitions": "AMED3901"
    },
    "prerequisites_expr": {
      "type": "logical",
      "rule": {
        "type": "logical",
        "operator": "OR",
        "operands": [
          { "type": "unit", "unit_code": "IMMU2101" },
          { "type": "unit", "unit_code": "MEDS2004" },
          { "type": "unit", "unit_code": "MIMI2002" }
        ]
      }
    },
    "corequisites_expr": { "type": "none", "rule": null },
    "prohibitions_expr": { "type": "unit", "unit_code": "AMED3901" }
  },
  "COMP2123": {
    "unit_code": "COMP2123",
    "title": "Data Structures and Algorithms",
    "needs_curation": false,
    "raw_rules": {
      "prerequisites": "INFO1110 or INFO1910 or INFO1113",
      "corequisites": "None",
      "prohibitions": "COMP2823"
    },
    "prerequisites_expr": {
      "type": "logical",
      "operator": "OR",
      "operands": [
        { "type": "unit", "unit_code": "INFO1110" },
        { "type": "unit", "unit_code": "INFO1910" },
        { "type": "unit", "unit_code": "INFO1113" }
      ]
    },
    "corequisites_expr": { "type": "none", "rule": null },
    "prohibitions_expr": { "type": "unit", "unit_code": "COMP2823" }
  }
};

// 2. Global State
let rulesDatabase = {};
let currentFilter = 'all';
let searchQuery = '';

// Check if running on local file system (mock mode)
const isStandalone = window.location.origin.startsWith('file') || window.location.hostname === '';
const API_URL = isStandalone ? null : '/api/rules';

// 3. Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  fetchRules();
});

// 4. Setup Global UI Event Listeners
function setupEventListeners() {
  // Search Bar
  const searchInput = document.getElementById("search-input");
  searchInput.addEventListener("input", (e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    renderGrid();
  });

  // Filter Pills
  const pills = document.querySelectorAll(".pill");
  pills.forEach(pill => {
    pill.addEventListener("click", (e) => {
      pills.forEach(p => p.classList.remove("active"));
      e.target.classList.add("active");
      currentFilter = e.target.dataset.filter;
      renderGrid();
    });
  });
}

// 5. Fetch Rules Database
async function fetchRules() {
  try {
    if (isStandalone) {
      console.log("Curation Portal: Running in standalone mockup mode.");
      rulesDatabase = JSON.parse(JSON.stringify(MOCK_RULES)); // Deep clone mock data
      updateStats();
      renderGrid();
    } else {
      const response = await fetch(API_URL);
      if (!response.ok) throw new Error("Could not load rules from API.");
      rulesDatabase = await response.json();
      updateStats();
      renderGrid();
    }
  } catch (error) {
    console.error("Fetch Error, falling back to mock data:", error);
    rulesDatabase = JSON.parse(JSON.stringify(MOCK_RULES));
    updateStats();
    renderGrid();
  }
}

// 6. Update Real-time Statistics
function updateStats() {
  const list = Object.values(rulesDatabase);
  const total = list.length;
  const pending = list.filter(item => item.needs_curation).length;
  const curated = total - pending;

  document.getElementById("stat-total").textContent = total;
  document.getElementById("stat-curated").textContent = curated;
  document.getElementById("stat-pending").textContent = pending;
}

// 7. Render Card Grid
function renderGrid() {
  const grid = document.getElementById("units-grid");
  grid.innerHTML = "";

  const filteredList = Object.values(rulesDatabase).filter(unit => {
    // Apply search filter
    const matchesSearch = unit.unit_code.toLowerCase().includes(searchQuery) ||
                          unit.title.toLowerCase().includes(searchQuery);

    // Apply pill filter
    let matchesPill = true;
    if (currentFilter === 'pending') {
      matchesPill = unit.needs_curation === true;
    } else if (currentFilter === 'curated') {
      matchesPill = unit.needs_curation === false;
    }

    return matchesSearch && matchesPill;
  });

  if (filteredList.length === 0) {
    grid.innerHTML = `<div class="empty-state">No units match your search filters.</div>`;
    return;
  }

  filteredList.forEach(unit => {
    const card = createUnitCard(unit);
    grid.appendChild(card);
  });
}

// 8. Create Card Component Node
function createUnitCard(unit) {
  const card = document.createElement("div");
  card.className = "unit-card";
  card.id = `card-${unit.unit_code}`;

  const badgeClass = unit.needs_curation ? 'badge-pending' : 'badge-curated';
  const badgeText = unit.needs_curation ? 'Needs Curation' : 'Curated';

  card.innerHTML = `
    <div class="card-header">
      <div class="card-title-area">
        <h3>${unit.unit_code}</h3>
        <p>${unit.title}</p>
      </div>
      <div class="status-badge-container" onclick="toggleCurationStatus('${unit.unit_code}')">
        <span class="badge ${badgeClass}" id="badge-${unit.unit_code}">${badgeText}</span>
      </div>
    </div>

    <div class="tabs-nav">
      <button class="tab-btn active" onclick="switchTab(this, 'prereq', '${unit.unit_code}')">Prerequisites</button>
      <button class="tab-btn" onclick="switchTab(this, 'coreq', '${unit.unit_code}')">Corequisites</button>
      <button class="tab-btn" onclick="switchTab(this, 'prohib', '${unit.unit_code}')">Prohibitions</button>
    </div>

    <div class="tab-content">
      <!-- Prerequisites Tab -->
      <div class="tab-panel active" id="tab-prereq-${unit.unit_code}">
        <div class="raw-rule-box">
          <span>Raw Prerequisite Text</span>
          <p>${unit.raw_rules?.prerequisites || 'None'}</p>
        </div>
        <div class="editor-container">
          <div class="editor-header">
            <span>JSON Expression Schema</span>
            <span class="validation-indicator valid" id="val-prereq-${unit.unit_code}">Valid JSON</span>
          </div>
          <textarea class="json-textarea valid-json" id="editor-prereq-${unit.unit_code}" oninput="validateJSON(this, 'val-prereq-${unit.unit_code}', '${unit.unit_code}')">${JSON.stringify(unit.prerequisites_expr || {type: "none"}, null, 2)}</textarea>
        </div>
      </div>

      <!-- Corequisites Tab -->
      <div class="tab-panel" id="tab-coreq-${unit.unit_code}">
        <div class="raw-rule-box">
          <span>Raw Corequisite Text</span>
          <p>${unit.raw_rules?.corequisites || 'None'}</p>
        </div>
        <div class="editor-container">
          <div class="editor-header">
            <span>JSON Expression Schema</span>
            <span class="validation-indicator valid" id="val-coreq-${unit.unit_code}">Valid JSON</span>
          </div>
          <textarea class="json-textarea valid-json" id="editor-coreq-${unit.unit_code}" oninput="validateJSON(this, 'val-coreq-${unit.unit_code}', '${unit.unit_code}')">${JSON.stringify(unit.corequisites_expr || {type: "none"}, null, 2)}</textarea>
        </div>
      </div>

      <!-- Prohibitions Tab -->
      <div class="tab-panel" id="tab-prohib-${unit.unit_code}">
        <div class="raw-rule-box">
          <span>Raw Prohibition Text</span>
          <p>${unit.raw_rules?.prohibitions || 'None'}</p>
        </div>
        <div class="editor-container">
          <div class="editor-header">
            <span>JSON Expression Schema</span>
            <span class="validation-indicator valid" id="val-prohib-${unit.unit_code}">Valid JSON</span>
          </div>
          <textarea class="json-textarea valid-json" id="editor-prohib-${unit.unit_code}" oninput="validateJSON(this, 'val-prohib-${unit.unit_code}', '${unit.unit_code}')">${JSON.stringify(unit.prohibitions_expr || {type: "none"}, null, 2)}</textarea>
        </div>
      </div>
    </div>

    <div class="card-footer">
      <button class="btn btn-secondary" onclick="resetCard('${unit.unit_code}')">Reset</button>
      <button class="btn btn-primary" id="save-btn-${unit.unit_code}" onclick="saveUnit('${unit.unit_code}')">Save Changes</button>
    </div>
  `;

  return card;
}

// 9. Tab Switching Logic
function switchTab(btn, tabName, unitCode) {
  const card = document.getElementById(`card-${unitCode}`);
  
  // Update active tab button
  const tabBtns = card.querySelectorAll(".tab-btn");
  tabBtns.forEach(b => b.classList.remove("active"));
  btn.classList.add("active");

  // Update active tab panel
  const panels = card.querySelectorAll(".tab-panel");
  panels.forEach(p => p.classList.remove("active"));
  
  card.querySelector(`#tab-${tabName}-${unitCode}`).classList.add("active");
}

// 10. Live JSON Validation
function validateJSON(textarea, indicatorId, unitCode) {
  const indicator = document.getElementById(indicatorId);
  const text = textarea.value.trim();
  const saveBtn = document.getElementById(`save-btn-${unitCode}`);

  try {
    if (text === "") {
      throw new Error("JSON cannot be empty");
    }
    JSON.parse(text);
    
    // UI Valid State
    textarea.classList.remove("invalid-json");
    textarea.classList.add("valid-json");
    indicator.textContent = "Valid JSON";
    indicator.className = "validation-indicator valid";
    saveBtn.disabled = false;
  } catch (e) {
    // UI Invalid State
    textarea.classList.remove("valid-json");
    textarea.classList.add("invalid-json");
    indicator.textContent = "Syntax Error";
    indicator.className = "validation-indicator invalid";
    saveBtn.disabled = true;
  }
}

// 11. Curation State Toggle (Header Badge Click)
function toggleCurationStatus(unitCode) {
  const unit = rulesDatabase[unitCode];
  if (!unit) return;

  unit.needs_curation = !unit.needs_curation;
  
  // Render badge changes
  const badge = document.getElementById(`badge-${unitCode}`);
  if (unit.needs_curation) {
    badge.className = "badge badge-pending";
    badge.textContent = "Needs Curation";
  } else {
    badge.className = "badge badge-curated";
    badge.textContent = "Curated";
  }

  updateStats();
  
  // Save status change automatically if desired, or let users click Save
}

// 12. Save Updates Action
async function saveUnit(unitCode) {
  const unit = rulesDatabase[unitCode];
  if (!unit) return;

  const saveBtn = document.getElementById(`save-btn-${unitCode}`);
  const originalText = saveBtn.textContent;
  
  try {
    // Read JSON texts
    const prereqExpr = JSON.parse(document.getElementById(`editor-prereq-${unitCode}`).value);
    const coreqExpr = JSON.parse(document.getElementById(`editor-coreq-${unitCode}`).value);
    const prohibExpr = JSON.parse(document.getElementById(`editor-prohib-${unitCode}`).value);

    // Update local state
    unit.prerequisites_expr = prereqExpr;
    unit.corequisites_expr = coreqExpr;
    unit.prohibitions_expr = prohibExpr;

    saveBtn.textContent = "Saving...";
    saveBtn.disabled = true;

    if (isStandalone) {
      // Simulate network latency in standalone mode
      await new Promise(resolve => setTimeout(resolve, 800));
      console.log(`Mock Saved rules for ${unitCode}:`, unit);
    } else {
      // Post payload to API
      const payload = {
        prerequisites_expr: prereqExpr,
        corequisites_expr: coreqExpr,
        prohibitions_expr: prohibExpr,
        needs_curation: unit.needs_curation
      };

      const response = await fetch(`${API_URL}/${unitCode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "API Save failed.");
      }
    }

    // Success styling feedback
    saveBtn.textContent = "Saved ✓";
    saveBtn.style.background = varTextForColor('--emerald');
    setTimeout(() => {
      saveBtn.textContent = originalText;
      saveBtn.style.background = "";
      saveBtn.disabled = false;
      renderGrid(); // Refilter if curation status caused grid shifts
    }, 1500);

  } catch (error) {
    console.error("Save Error:", error);
    alert(`Failed to save rules for ${unitCode}: ${error.message}`);
    saveBtn.textContent = originalText;
    saveBtn.disabled = false;
  }
}

// 13. Reset Card back to DB State
function resetCard(unitCode) {
  const unit = rulesDatabase[unitCode];
  if (!unit) return;
  
  // Re-render only this card
  const grid = document.getElementById("units-grid");
  const oldCard = document.getElementById(`card-${unitCode}`);
  const newCard = createUnitCard(unit);
  
  grid.replaceChild(newCard, oldCard);
}

// Helper to resolve CSS variables in JavaScript for success state
function varTextForColor(cssVarName) {
  return getComputedStyle(document.documentElement).getPropertyValue(cssVarName).trim();
}
