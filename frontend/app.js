(function () {
  const data = window.BBT_LEADS_DATA || { meta: {}, options: {}, leads: [] };
  const leads = data.leads || [];
  const filterLabels = {
    evidenceYear: "Year",
    geography: "Geography",
    productArea: "Product area",
    companyType: "Company type",
    companyStage: "Stage",
    fundingStage: "Funding",
    hiringSignal: "Hiring",
    triggerType: "Trigger",
    persona: "Persona",
    bbtQuadrant: "BBT quadrant",
    sourceType: "Source type",
  };

  const state = {
    filters: Object.fromEntries((data.filterFields || []).map((field) => [field, []])),
    search: "",
    segment: "all",
    selectedId: leads[0] ? leads[0].id : "",
    sortField: "",
    sortDirection: "asc",
  };

  const segments = {
    all: () => true,
    ireland2026: (lead) =>
      lead.evidenceYear === "2026" &&
      lead.geography === "Ireland" &&
      lead.companyType === "Startup",
    spinouts: (lead) =>
      lead.companyType === "University spinout" &&
      ["2026", "2025", "2024"].includes(lead.evidenceYear),
    hiring: (lead) => lead.hiringSignal === "Yes",
    fundedAi: (lead) =>
      lead.productArea === "AI / SaMD" &&
      lead.fundingStage &&
      lead.fundingStage !== "Unknown",
    regulatory: (lead) => lead.companyStage === "Regulatory / commercial",
    ukDigital: (lead) => lead.geography === "UK" && lead.productArea === "Digital health",
    vcScaleups: (lead) =>
      lead.sourceType === "VC portfolio" && lead.companyType === "Scaleup / growing company",
  };

  const els = {
    dataMeta: document.getElementById("dataMeta"),
    kpiStrip: document.getElementById("kpiStrip"),
    filterGrid: document.getElementById("filterGrid"),
    searchInput: document.getElementById("searchInput"),
    clearFilters: document.getElementById("clearFilters"),
    resultCount: document.getElementById("resultCount"),
    activeFilterText: document.getElementById("activeFilterText"),
    leadRows: document.getElementById("leadRows"),
    dossierContent: document.getElementById("dossierContent"),
  };

  function isFunded(lead) {
    return Boolean(lead.fundingStage && lead.fundingStage !== "Unknown");
  }

  function verified(lead) {
    return lead.evidenceStatus === "Verified trigger";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function display(value, fallback = "Unknown") {
    return value || fallback;
  }

  function shortText(value, maxLength) {
    if (!value) return "No description captured";
    return value.length > maxLength ? value.slice(0, maxLength - 1).trim() + "..." : value;
  }

  function safeUrl(url) {
    if (!url || !/^https?:\/\//i.test(url)) return "";
    return url;
  }

  function renderMeta() {
    const generated = data.meta.generatedAt ? data.meta.generatedAt.replace("T", " ") : "unknown";
    els.dataMeta.textContent = `${data.meta.leadCount || leads.length} leads from ${data.meta.sourceWorkbook || "workbook"} · generated ${generated}`;
  }

  function renderKpis() {
    const kpis = [
      ["Total leads", leads.length],
      ["2026 leads", leads.filter((lead) => lead.evidenceYear === "2026").length],
      ["Ireland leads", leads.filter((lead) => lead.geography === "Ireland").length],
      ["Hiring signals", leads.filter((lead) => lead.hiringSignal === "Yes").length],
      ["Funded leads", leads.filter(isFunded).length],
      ["Verified triggers", leads.filter(verified).length],
    ];
    els.kpiStrip.innerHTML = kpis
      .map(([label, value]) => `<article class="kpi"><strong>${value.toLocaleString()}</strong><span>${label}</span></article>`)
      .join("");
  }

  function renderFilters() {
    els.filterGrid.innerHTML = (data.filterFields || [])
      .map((field) => {
        const options = data.options[field] || [];
        return `
          <div class="filter-control">
            <span>${filterLabels[field] || field}</span>
            <details class="filter-menu" data-filter="${field}">
              <summary id="filter-summary-${field}">Any</summary>
              <div class="filter-options">
                ${options
                  .map(
                    (option) => `
                      <label>
                        <input type="checkbox" value="${escapeHtml(option)}">
                        <span>${escapeHtml(option)}</span>
                      </label>
                    `
                  )
                  .join("")}
              </div>
            </details>
          </div>
        `;
      })
      .join("");

    els.filterGrid.querySelectorAll(".filter-menu").forEach((menu) => {
      menu.addEventListener("toggle", () => {
        if (menu.open) closeFilterMenus(menu);
      });
      menu.addEventListener("change", () => {
        const field = menu.dataset.filter;
        state.filters[field] = Array.from(menu.querySelectorAll("input:checked")).map((input) => input.value);
        state.segment = "all";
        updateFilterSummary(field);
        setActiveSegment();
        render();
      });
    });
  }

  function closeFilterMenus(exceptMenu) {
    document.querySelectorAll(".filter-menu[open]").forEach((menu) => {
      if (menu !== exceptMenu) menu.open = false;
    });
  }

  function activeFilters() {
    return Object.entries(state.filters).filter(([, values]) => values.length);
  }

  function updateFilterSummary(field) {
    const summary = document.getElementById(`filter-summary-${field}`);
    const values = state.filters[field] || [];
    if (!summary) return;
    if (!values.length) {
      summary.textContent = "Any";
    } else if (values.length === 1) {
      summary.textContent = values[0];
    } else {
      summary.textContent = `${values.length} selected`;
    }
  }

  function sortedLeads(rows) {
    const field = state.sortField;
    if (!field) return rows;
    const direction = state.sortDirection === "desc" ? -1 : 1;
    return [...rows].sort((left, right) => {
      const leftValue = left[field] || "";
      const rightValue = right[field] || "";
      if (field === "evidenceYear") {
        const leftYear = Number(leftValue) || 0;
        const rightYear = Number(rightValue) || 0;
        return (leftYear - rightYear) * direction;
      }
      const leftSort = leftValue.replace(/^[^a-z0-9]+/i, "");
      const rightSort = rightValue.replace(/^[^a-z0-9]+/i, "");
      return leftSort.localeCompare(rightSort, undefined, { numeric: true, sensitivity: "base" }) * direction;
    });
  }

  function filteredLeads() {
    const search = state.search.trim().toLowerCase();
    const rows = leads.filter((lead) => {
      const segmentMatch = (segments[state.segment] || segments.all)(lead);
      const filterMatch = activeFilters().every(([field, values]) => values.includes(lead[field]));
      const searchMatch = !search || lead.searchText.includes(search);
      return segmentMatch && filterMatch && searchMatch;
    });
    return sortedLeads(rows);
  }

  function badgeClass(value) {
    if (value === "Yes" || value === "Verified trigger") return "green";
    if (value && value !== "Unknown" && value !== "No verified trigger") return "amber";
    return "";
  }

  function renderRows(rows) {
    if (!rows.length) {
      els.leadRows.innerHTML = `<tr><td class="empty" colspan="9">No leads match these filters.</td></tr>`;
      return;
    }

    els.leadRows.innerHTML = rows
      .slice(0, 500)
      .map((lead) => {
        const website = safeUrl(lead.website);
        const company = website
          ? `<a href="${escapeHtml(website)}" target="_blank" rel="noreferrer">${escapeHtml(lead.company)}</a>`
          : escapeHtml(lead.company);
        return `
          <tr data-id="${escapeHtml(lead.id)}" class="${lead.id === state.selectedId ? "selected" : ""}">
            <td class="company-cell">${company}</td>
            <td class="description-cell">${escapeHtml(shortText(lead.description, 150))}</td>
            <td>${escapeHtml(display(lead.productArea))}</td>
            <td>${escapeHtml(display(lead.geography))}</td>
            <td>${escapeHtml(display(lead.companyStage))}</td>
            <td><span class="badge ${badgeClass(lead.triggerType)}">${escapeHtml(display(lead.triggerType))}</span></td>
            <td>${escapeHtml(display(lead.evidenceYear, "None"))}</td>
            <td>${escapeHtml(display(lead.persona))}</td>
            <td>${escapeHtml(display(lead.bbtQuadrant))}</td>
          </tr>
        `;
      })
      .join("");

    els.leadRows.querySelectorAll("tr[data-id]").forEach((row) => {
      row.addEventListener("click", (event) => {
        if (event.target.tagName === "A") return;
        state.selectedId = row.dataset.id;
        render();
      });
    });
  }

  function linkField(label, url) {
    const safe = safeUrl(url);
    const value = safe
      ? `<a href="${escapeHtml(safe)}" target="_blank" rel="noreferrer">${escapeHtml(safe)}</a>`
      : `<span class="missing-link">Not captured</span>`;
    return `<li><strong>${escapeHtml(label)}:</strong> ${value}</li>`;
  }

  function contactLine(name, title, url) {
    if (!name && !title && !url) return "";
    const label = [name, title].filter(Boolean).join(" · ") || "LinkedIn profile";
    const safe = safeUrl(url);
    return safe
      ? `<li><a href="${escapeHtml(safe)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a></li>`
      : `<li>${escapeHtml(label)}</li>`;
  }

  function detail(label, value) {
    return `<div class="detail"><span>${escapeHtml(label)}</span><strong>${escapeHtml(display(value))}</strong></div>`;
  }

  function renderDossier(rows) {
    if (!rows.length) {
      els.dossierContent.innerHTML = `<div class="empty">No lead selected.</div>`;
      return;
    }

    const selected = rows.find((lead) => lead.id === state.selectedId) || rows[0];
    if (!selected) {
      els.dossierContent.innerHTML = `<div class="empty">No lead selected.</div>`;
      return;
    }
    state.selectedId = selected.id;

    const links = [
      linkField("Company website", selected.website),
      linkField("Source evidence", selected.sourceUrl),
      linkField("LinkedIn company page", selected.linkedinCompanyUrl),
    ];

    const contacts = [
      contactLine(selected.executiveContactName, selected.executiveContactTitle, selected.executiveLinkedinUrl),
      contactLine(selected.technicalContactName, selected.technicalContactTitle, selected.technicalLinkedinUrl),
      contactLine(selected.qualityContactName, selected.qualityContactTitle, selected.qualityLinkedinUrl),
    ].filter(Boolean);

    els.dossierContent.innerHTML = `
      <div class="dossier-inner">
        <h2>${escapeHtml(selected.company)}</h2>
        <div class="dossier-meta">
          <span class="badge">${escapeHtml(display(selected.evidenceYear, "No year"))}</span>
          <span class="badge ${badgeClass(selected.evidenceStatus)}">${escapeHtml(display(selected.evidenceStatus))}</span>
          <span class="badge">${escapeHtml(display(selected.persona))}</span>
        </div>

        <p>${escapeHtml(display(selected.description, "No description captured."))}</p>

        <div class="detail-grid">
          ${detail("Product area", selected.productArea)}
          ${detail("Product type", selected.productType)}
          ${detail("Geography", selected.geography)}
          ${detail("Company stage", selected.companyStage)}
          ${detail("Funding stage", selected.fundingStage)}
          ${detail("Hiring signal", selected.hiringSignal)}
          ${detail("BBT quadrant", selected.bbtQuadrant)}
          ${detail("Trigger type", selected.triggerType)}
        </div>

        <h3>Links</h3>
        <ul class="link-list">${links.join("")}</ul>

        <h3>Evidence</h3>
        <p><strong>${escapeHtml(display(selected.sourceName))}</strong> · ${escapeHtml(display(selected.sourceType))}</p>
        <p>${escapeHtml(display(selected.discoveryRationale, "No rationale captured."))}</p>

        <h3>Programme</h3>
        <div class="detail-grid">
          ${detail("Accelerator", selected.acceleratorProgram)}
          ${detail("Cohort", selected.cohortLabel)}
          ${detail("Cohort year", selected.cohortYear)}
          ${detail("Category / track", selected.categoryTrack)}
        </div>

        <h3>LinkedIn and Contacts</h3>
        <div class="detail-grid">
          ${detail("Company status", selected.linkedinCompanyStatus)}
          ${detail("Contact status", selected.linkedinContactStatus)}
        </div>
        <ul class="link-list">${contacts.length ? contacts.join("") : "<li>No contact profiles captured</li>"}</ul>

        <h3>Next Actions</h3>
        <div class="actions">
          <button class="action-button" type="button" disabled>Find news</button>
          <button class="action-button" type="button" disabled>Expand description</button>
          <button class="action-button" type="button" disabled>Find LinkedIn/key people</button>
          <button class="action-button" type="button" disabled>Generate outreach email</button>
        </div>
        <div class="placeholder-note">These actions are reserved for the enrichment layer; v1 uses the workbook export only.</div>
      </div>
    `;
  }

  function renderSummary(rows) {
    const count = rows.length;
    els.resultCount.textContent = `${count.toLocaleString()} lead${count === 1 ? "" : "s"}`;
    const filters = activeFilters().map(([field, values]) => `${filterLabels[field] || field}: ${values.join(", ")}`);
    if (state.search) filters.push(`Search: ${state.search}`);
    if (state.segment !== "all") filters.unshift(`Segment: ${document.querySelector(`[data-segment="${state.segment}"]`).textContent}`);
    els.activeFilterText.textContent = filters.length ? filters.join(" · ") : "No filters active";
  }

  function setActiveSegment() {
    document.querySelectorAll(".segment").forEach((button) => {
      button.classList.toggle("active", button.dataset.segment === state.segment);
    });
  }

  function updateSortHeaders() {
    document.querySelectorAll(".sort-button").forEach((button) => {
      const isActive = button.dataset.sort === state.sortField;
      const marker = button.querySelector("span");
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-sort", isActive ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none");
      if (marker) marker.textContent = isActive ? (state.sortDirection === "asc" ? "^" : "v") : "";
    });
  }

  function render() {
    const rows = filteredLeads();
    if (!rows.some((lead) => lead.id === state.selectedId) && rows[0]) {
      state.selectedId = rows[0].id;
    }
    updateSortHeaders();
    renderSummary(rows);
    renderRows(rows);
    renderDossier(rows);
  }

  function clearFilters() {
    Object.keys(state.filters).forEach((field) => {
      state.filters[field] = [];
      const menu = document.querySelector(`.filter-menu[data-filter="${field}"]`);
      if (menu) {
        menu.querySelectorAll("input").forEach((input) => {
          input.checked = false;
        });
        menu.open = false;
      }
      updateFilterSummary(field);
    });
    state.search = "";
    state.segment = "all";
    els.searchInput.value = "";
    setActiveSegment();
    render();
  }

  function bindEvents() {
    els.searchInput.addEventListener("input", () => {
      state.search = els.searchInput.value;
      render();
    });
    els.clearFilters.addEventListener("click", clearFilters);
    document.querySelectorAll(".segment").forEach((button) => {
      button.addEventListener("click", () => {
        state.segment = button.dataset.segment;
        setActiveSegment();
        render();
      });
    });
    document.querySelectorAll(".sort-button").forEach((button) => {
      button.addEventListener("click", () => {
        const field = button.dataset.sort;
        if (state.sortField === field) {
          state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
        } else {
          state.sortField = field;
          state.sortDirection = field === "evidenceYear" ? "desc" : "asc";
        }
        render();
      });
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".filter-menu")) closeFilterMenus();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeFilterMenus();
    });
  }

  renderMeta();
  renderKpis();
  renderFilters();
  bindEvents();
  render();
})();
