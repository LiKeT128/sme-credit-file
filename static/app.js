const euro = new Intl.NumberFormat("sk-SK", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const sqlCache = {};

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(url);
  return response.json();
}

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function fillTable(id, records, build) {
  const body = document.querySelector(`#${id} tbody`);
  body.replaceChildren();
  records.forEach((record) => {
    const tr = document.createElement("tr");
    build(tr, record);
    body.appendChild(tr);
  });
}

function renderSummary(data) {
  document.getElementById("asof").textContent = `As of ${data.as_of}`;
  document.getElementById("lede").textContent =
    `${data.overdue_files} client files are past due, and ${data.missing_statements} have no 2025 statement at all. ${data.broken} filed balance sheets do not balance.`;
  const items = [
    [data.companies, "SME clients in the book"],
    [`${data.docs_complete_pct}%`, "2025 documents received"],
    [data.overdue_files, "files with something overdue"],
    [data.broken, "balance sheets that do not balance"],
  ];
  const root = document.getElementById("stats");
  root.replaceChildren();
  items.forEach(([value, label]) => {
    const article = document.createElement("article");
    article.className = "stat";
    const strong = document.createElement("b");
    strong.textContent = value;
    const span = document.createElement("span");
    span.textContent = label;
    article.append(strong, span);
    root.appendChild(article);
  });
}

function renderChase(records) {
  fillTable("chase", records, (tr, row) => {
    tr.dataset.id = row.company_id;
    tr.append(
      cell(row.name),
      cell(row.segment),
      cell(`${row.file_progress} · ${row.docs_overdue} late`),
      cell(row.statement_2025),
      cell(String(row.priority), "num"),
    );
    tr.addEventListener("click", () => openCompany(row.company_id));
  });
}

function renderBreaks(records) {
  fillTable("breaks", records, (tr, row) => {
    tr.dataset.id = row.company_id;
    tr.append(
      cell(row.name),
      cell(String(row.fiscal_year)),
      cell(euro.format(row.total_assets_eur), "num"),
      cell(euro.format(row.imbalance_eur), "num"),
    );
    tr.addEventListener("click", () => openCompany(row.company_id));
  });
}

function renderMargins(records) {
  fillTable("margins", records, (tr, row) => {
    tr.dataset.id = row.company_id;
    tr.append(
      cell(row.name),
      cell(row.segment),
      cell(`${row.net_margin_pct}%`, "num"),
      cell(`${row.segment_avg_pct}%`, "num"),
    );
    tr.addEventListener("click", () => openCompany(row.company_id));
  });
}

function renderSegments(records) {
  const root = document.getElementById("segments");
  root.replaceChildren();
  records.forEach((row) => {
    const line = document.createElement("div");
    line.className = "bar-row";
    const name = document.createElement("span");
    name.textContent = row.segment;
    const track = document.createElement("div");
    track.className = "bar";
    const fill = document.createElement("i");
    fill.style.width = `${row.complete_pct}%`;
    track.appendChild(fill);
    const pct = document.createElement("span");
    pct.textContent = `${row.complete_pct}%`;
    line.append(name, track, pct);
    root.appendChild(line);
  });
}

function renderCycle(records) {
  const root = document.getElementById("cycle");
  root.replaceChildren();
  const labels = {
    annual_statements: "Annual statements",
    notes: "Notes",
    tax_return: "Tax return",
    bank_confirmation: "Bank confirmation",
  };
  records.forEach((row) => {
    const line = document.createElement("div");
    line.className = "cycle-row";
    const name = document.createElement("span");
    name.textContent = labels[row.doc_type] || row.doc_type;
    const meta = document.createElement("span");
    meta.textContent = `${row.avg_days_to_receive} days · ${row.arrived_late} late`;
    line.append(name, meta);
    root.appendChild(line);
  });
}

async function openSql(key) {
  if (!sqlCache.loaded) {
    Object.assign(sqlCache, await getJson("api/sql"));
    sqlCache.loaded = true;
  }
  document.getElementById("sql-title").textContent = key;
  document.getElementById("sql-body").textContent = sqlCache[key];
  document.getElementById("sql-dialog").showModal();
}

async function openCompany(id) {
  const data = await getJson(`api/company/${id}`);
  const company = data.company;
  document.getElementById("company-title").textContent = company.name;
  const body = document.getElementById("company-body");
  body.replaceChildren();
  const meta = document.createElement("p");
  meta.className = "hint";
  meta.textContent = `${company.segment} · ${company.city} · ${company.employees} people · ${company.relationship_manager} · client since ${company.client_since}`;
  body.appendChild(meta);

  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Year</th><th class='num'>Revenue</th><th class='num'>Net income</th><th class='num'>Margin</th><th class='num'>Gap</th></tr></thead>";
  const tbody = document.createElement("tbody");
  data.statements.forEach((row) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(String(row.fiscal_year)),
      cell(euro.format(row.revenue_eur), "num"),
      cell(euro.format(row.net_income_eur), "num"),
      cell(row.net_margin_pct == null ? "—" : `${row.net_margin_pct}%`, "num"),
      cell(euro.format(row.imbalance_eur), "num"),
    );
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  body.appendChild(table);

  const docs = document.createElement("div");
  docs.className = "doc-grid";
  data.documents.forEach((doc) => {
    const card = document.createElement("div");
    card.className = "doc";
    const title = document.createElement("strong");
    title.textContent = doc.doc_type.replaceAll("_", " ");
    const state = document.createElement("span");
    state.className = doc.state === "on time" ? "tag ok" : "tag warn";
    state.textContent = doc.state;
    const line = document.createElement("div");
    line.append(title, " ", state);
    const detail = document.createElement("p");
    detail.className = "hint";
    detail.textContent = doc.received_on
      ? `Received ${doc.received_on}, due ${doc.due_on}`
      : `Not received. Due ${doc.due_on}`;
    card.append(line, detail);
    docs.appendChild(card);
  });
  body.appendChild(docs);
  document.getElementById("company-dialog").showModal();
}

document.querySelectorAll("[data-key]").forEach((button) => {
  button.addEventListener("click", () => openSql(button.dataset.key));
});

Promise.all([
  getJson("api/summary"),
  getJson("api/chase"),
  getJson("api/breaks"),
  getJson("api/margins"),
  getJson("api/segments"),
  getJson("api/cycle"),
]).then(([summary, chase, breaks, margins, segments, cycle]) => {
  renderSummary(summary);
  renderChase(chase);
  renderBreaks(breaks);
  renderMargins(margins);
  renderSegments(segments);
  renderCycle(cycle);
}).catch((error) => {
  document.getElementById("lede").textContent = `Could not load the book (${error.message}).`;
});
