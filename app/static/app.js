const treeEl = document.getElementById("tree");
const contentEl = document.getElementById("content");
const contentHeaderEl = document.getElementById("contentHeader");
const contentBodyEl = document.getElementById("contentBody");
const sidebarEl = document.getElementById("detailSidebar");
const searchInput = document.getElementById("searchInput");
const searchScope = document.getElementById("searchScope");
const searchBtn = document.getElementById("searchBtn");

let docFontSize = 16;
let lastListView = null;

function setContent(headerHtml, bodyHtml) {
  contentHeaderEl.innerHTML = headerHtml;
  contentBodyEl.innerHTML = bodyHtml;
  contentBodyEl.scrollTop = 0;
}

function goBack() {
  if (lastListView) {
    lastListView();
  } else {
    loadRecent();
  }
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`요청 실패: ${res.status}`);
  return res.json();
}

const ICON_FOLDER =
  '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>';
const ICON_DOC =
  '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6"/><path d="M9 17h6"/></svg>';

function renderTreeNode(node) {
  const li = document.createElement("li");
  li.className = node.type;

  if (node.type === "category") {
    li.classList.add("collapsed");

    const header = document.createElement("div");
    header.className = "node-header";

    const arrow = document.createElement("span");
    arrow.className = "toggle-arrow";
    arrow.textContent = "▸";
    arrow.addEventListener("click", () => {
      li.classList.toggle("collapsed");
      arrow.textContent = li.classList.contains("collapsed") ? "▸" : "▾";
    });
    header.appendChild(arrow);

    const label = document.createElement("span");
    label.className = "label cat-link";
    label.innerHTML = `${ICON_FOLDER}<span>${node.name}</span>`;
    label.addEventListener("click", () => {
      if (li.classList.contains("collapsed")) {
        li.classList.remove("collapsed");
        arrow.textContent = "▾";
        loadListByCategory(node.name, node.parentL0);
      } else {
        li.classList.add("collapsed");
        arrow.textContent = "▸";
      }
    });
    header.appendChild(label);

    li.appendChild(header);

    const ul = document.createElement("ul");
    node.children.forEach((child) => {
      child.parentL0 = node.parentL0 !== undefined ? node.parentL0 : node.name;
      ul.appendChild(renderTreeNode(child));
    });
    li.appendChild(ul);
  } else {
    const a = document.createElement("a");
    a.href = `#reg-${node.id}`;
    a.dataset.regId = node.id;
    a.innerHTML = `${ICON_DOC}<span>${node.title}</span>`;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      loadDetail(node.id);
    });
    li.appendChild(a);
  }
  return li;
}

async function loadTree() {
  const data = await fetchJSON("/api/tree");
  const root = document.createElement("ul");
  data.forEach((node) => {
    node.parentL0 = node.name;
    root.appendChild(renderTreeNode(node));
  });
  treeEl.innerHTML = "";
  treeEl.appendChild(root);
}

function markActiveTreeLink(id) {
  treeEl.querySelectorAll("a.active").forEach((a) => a.classList.remove("active"));
  const link = treeEl.querySelector(`a[data-reg-id="${id}"]`);
  if (!link) return;
  link.classList.add("active");
  let li = link.closest("li");
  while (li) {
    const parentCategory = li.parentElement.closest("li.category");
    if (parentCategory) {
      parentCategory.classList.remove("collapsed");
      const arrow = parentCategory.querySelector(":scope > .node-header .toggle-arrow");
      if (arrow) arrow.textContent = "▾";
    }
    li = parentCategory;
  }
}

function isTopLevelCategory(name, data) {
  return data.some((n) => n.name === name);
}

const PAGE_SIZE = 20;
let currentListParams = null;
let currentListHeading = "";

async function loadListByCategory(name, parentL0) {
  const params = new URLSearchParams();
  if (parentL0 && parentL0 !== name) {
    params.set("category_l0", parentL0);
    params.set("category_l1", name);
  } else {
    params.set("category_l0", name);
  }
  await loadList(params, name, 1);
}

async function runSearch() {
  const q = searchInput.value.trim();
  if (!q) return;
  const params = new URLSearchParams({ q, scope: searchScope.value });
  await loadList(params, `'${q}' 검색 결과`, 1);
}

async function loadList(params, heading, page) {
  currentListParams = params;
  currentListHeading = heading;
  lastListView = () => loadList(params, heading, page);

  const fetchParams = new URLSearchParams(params);
  fetchParams.set("page", page);
  fetchParams.set("page_size", PAGE_SIZE);

  const data = await fetchJSON(`/api/regulations?${fetchParams.toString()}`);
  if (data.scope === "body") {
    renderBodySearchResults(data, heading, page);
  } else {
    renderList(data, heading, page);
  }
}

function renderBodySearchResults(data, heading, page) {
  clearSidebar();
  const rows = data.results
    .map((r) => {
      const anchor = r.article_sub_no ? `article-${r.article_no}-${r.article_sub_no}` : `article-${r.article_no}`;
      return `
      <tr data-reg="${r.regulation_id}" data-anchor="${anchor}">
        <td>
          <div class="body-hit-reg">${r.regulation_title}</div>
          <div class="body-hit-art">${r.article_label}</div>
        </td>
        <td class="body-hit-snippet">${r.snippet}</td>
      </tr>`;
    })
    .join("");

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const pagerHtml = totalPages > 1 ? `
    <div class="pager">
      <button id="prevPage" ${page <= 1 ? "disabled" : ""}>&larr; 이전</button>
      <span>${page} / ${totalPages} 페이지</span>
      <button id="nextPage" ${page >= totalPages ? "disabled" : ""}>다음 &rarr;</button>
    </div>` : "";

  setContent(
    `<h2>${heading}</h2><p class="result-count">총 ${data.total}건 (조문 기준)</p>`,
    `<table class="reg-list body-hit-list">
      <thead>
        <tr><th>규정 / 조문</th><th>내용</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="2">결과가 없습니다.</td></tr>'}</tbody>
    </table>
    ${pagerHtml}`
  );

  contentBodyEl.querySelectorAll("tbody tr[data-reg]").forEach((tr) => {
    tr.addEventListener("click", () => goToArticle(Number(tr.dataset.reg), tr.dataset.anchor));
  });

  const prevBtn = document.getElementById("prevPage");
  const nextBtn = document.getElementById("nextPage");
  if (prevBtn) prevBtn.addEventListener("click", () => loadList(currentListParams, currentListHeading, page - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadList(currentListParams, currentListHeading, page + 1));
}

function renderList(data, heading, page) {
  clearSidebar();
  const rows = data.results
    .map(
      (r) => `
      <tr data-id="${r.id}">
        <td>${r.seq}</td>
        <td>${r.title}</td>
        <td>${r.enact_date || "-"}</td>
        <td>${r.latest_amend || "-"}</td>
      </tr>`
    )
    .join("");

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  const pagerHtml = totalPages > 1 ? `
    <div class="pager">
      <button id="prevPage" ${page <= 1 ? "disabled" : ""}>&larr; 이전</button>
      <span>${page} / ${totalPages} 페이지</span>
      <button id="nextPage" ${page >= totalPages ? "disabled" : ""}>다음 &rarr;</button>
    </div>` : "";

  setContent(
    `<h2>${heading}</h2><p class="result-count">총 ${data.total}건</p>`,
    `<table class="reg-list">
      <thead>
        <tr><th>번호</th><th>규정명</th><th>제정일</th><th>최근 개정일</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="4">결과가 없습니다.</td></tr>'}</tbody>
    </table>
    ${pagerHtml}`
  );

  contentBodyEl.querySelectorAll("tbody tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => loadDetail(Number(tr.dataset.id)));
  });

  const prevBtn = document.getElementById("prevPage");
  const nextBtn = document.getElementById("nextPage");
  if (prevBtn) prevBtn.addEventListener("click", () => loadList(currentListParams, currentListHeading, page - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadList(currentListParams, currentListHeading, page + 1));
}

function renderArticles(articles) {
  let lastChapter = null, lastSection = null, lastGwan = null;
  let html = "";

  articles.forEach((a) => {
    if (a.chapter !== lastChapter) {
      html += `<div class="chapter-tag">${a.chapter || ""}</div>`;
      lastChapter = a.chapter;
      lastSection = null;
      lastGwan = null;
    }
    if (a.section && a.section !== lastSection) {
      html += `<div class="chapter-tag">${a.section}</div>`;
      lastSection = a.section;
    }
    if (a.gwan && a.gwan !== lastGwan) {
      html += `<div class="chapter-tag">${a.gwan}</div>`;
      lastGwan = a.gwan;
    }
    const artNo = a.sub_no ? `제${a.no}조의${a.sub_no}` : `제${a.no}조`;
    const anchorId = a.sub_no ? `article-${a.no}-${a.sub_no}` : `article-${a.no}`;
    html += `<p class="article" id="${anchorId}"><span class="art-no">${artNo}${a.title ? `(${a.title})` : ""}</span>${highlightAmendments(formatArticleBody(stripArticleHead(a.body, a.no, a.sub_no)))}</p>`;
  });

  return html;
}

function renderAttachmentFile(att) {
  if (!att.file_url) {
    return `<p class="placeholder">원본 PDF에서 이 서식의 페이지를 찾지 못했습니다 (원본 문서에 내용 없이 삭제 표시만 있는 경우일 수 있습니다).</p>`;
  }
  return `
    <div class="attachment-file">
      <a href="${att.file_url}" target="_blank" class="file-open-link">새 창에서 원본 열기 / 다운로드</a>
      <iframe src="${att.file_url}" class="attachment-pdf" title="${att.label}"></iframe>
    </div>`;
}

function renderOutline(articles) {
  let lastChapter = null;
  let html = "";
  articles.forEach((a) => {
    if (a.chapter !== lastChapter) {
      html += `<div class="outline-chapter">${a.chapter || ""}</div>`;
      lastChapter = a.chapter;
    }
    const artNo = a.sub_no ? `제${a.no}조의${a.sub_no}` : `제${a.no}조`;
    const anchorId = a.sub_no ? `article-${a.no}-${a.sub_no}` : `article-${a.no}`;
    html += `<a href="#" data-article="${anchorId}">${artNo}${a.title ? `(${a.title})` : ""}</a>`;
  });
  return html;
}

function renderSidebar(regId, articles, attachments) {
  if ((!articles || !articles.length) && (!attachments || !attachments.length)) {
    sidebarEl.innerHTML = "";
    return;
  }

  const outlineHtml = articles && articles.length
    ? `<div class="sidebar-section"><h3>조별목록</h3><ul>${renderOutline(articles)}</ul></div>`
    : "";

  const attHtml = attachments && attachments.length
    ? `<div class="sidebar-section"><h3>별표 및 서식</h3><ul>${attachments
        .map((att) => `<a href="#" data-reg="${regId}" data-ord="${att.ordinal}">${att.label}</a>`)
        .join("")}</ul></div>`
    : "";

  sidebarEl.innerHTML = outlineHtml + attHtml;

  sidebarEl.querySelectorAll("a[data-ord]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      loadAttachmentDetail(Number(a.dataset.reg), Number(a.dataset.ord));
    });
  });
  sidebarEl.querySelectorAll("a[data-article]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      goToArticle(regId, a.dataset.article);
    });
  });
}

async function goToArticle(regId, anchorId) {
  let el = document.getElementById(anchorId);
  if (!el) {
    await loadDetail(regId);
    el = document.getElementById(anchorId);
  }
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearSidebar() {
  sidebarEl.innerHTML = "";
}

function renderDocHeader(backText, breadcrumbInner, title) {
  return `
    <div class="doc-header-top">
      <span class="back-link" id="backLink">${backText}</span>
      <div class="breadcrumb">${breadcrumbInner}</div>
    </div>
    <div class="doc-title-bar">
      <div class="doc-toolbar">
        <button id="fontDown">가&minus;</button>
        <button id="fontUp">가+</button>
        <button id="printBtn">인쇄</button>
      </div>
      <h2>${title}</h2>
    </div>`;
}

function bindDocToolbar() {
  document.getElementById("fontDown").addEventListener("click", () => adjustFontSize(-1));
  document.getElementById("fontUp").addEventListener("click", () => adjustFontSize(1));
  document.getElementById("printBtn").addEventListener("click", () => window.print());
}

function adjustFontSize(delta) {
  docFontSize = Math.min(20, Math.max(12, docFontSize + delta));
  const detailEl = contentBodyEl.querySelector(".reg-detail");
  if (detailEl) detailEl.style.fontSize = `${docFontSize}px`;
}

function stripArticleHead(body, no, subNo) {
  // The source PDF isn't consistent about whitespace between "제N조" and the
  // following "(title)" (e.g. "제1조(목적)" vs "제10조 (개정 ...)"), so match
  // loosely rather than requiring an exact prefix string.
  const subPart = subNo ? `\\s*의\\s*${subNo}` : "";
  const re = new RegExp(`^제\\s*${no}\\s*조${subPart}(?:\\s*\\([^)]*\\))?`);
  return body.replace(re, "");
}

function formatArticleBody(text) {
  // The source text jams 항 markers (①②③...) and their nested 호 markers
  // (1. 2. 3...) into one running paragraph with no line breaks. Break each
  // onto its own line, and indent 호 markers that are nested under a 항.
  //
  // Dates and amendment notes like "(개정 2011. 9. 23)" can also contain a
  // "N. " pattern, so parenthetical/bracketed spans are protected first and
  // restored at the end, to avoid mistaking a date fragment for a list marker.
  const stash = [];
  let masked = text.replace(/([([][^()[\]]*[)\]])/g, (m) => {
    stash.push(m);
    return `@@${stash.length - 1}@@`;
  });

  const markerRe = /[①-⑳](?![,”"'])|(?<=\s)[1-9][0-9]?\.(?=\s)/g;
  let lastIndex = 0;
  let seenCircled = false;
  let spanOpen = false;
  let html = "";
  let m;

  while ((m = markerRe.exec(masked)) !== null) {
    const chunk = masked.slice(lastIndex, m.index);
    html += spanOpen ? chunk + "</span>" : chunk;
    spanOpen = false;

    const marker = m[0];
    const isCircled = /[①-⑳]/.test(marker);
    const nested = !isCircled && seenCircled;

    if (nested) {
      // No leading <br> here: .list-indent is display:block, which already
      // starts its own line. Adding <br> too creates a double line-break
      // (blank line) between consecutive nested items.
      html += `<span class="list-indent">${marker}`;
      spanOpen = true;
    } else {
      html += `<br>${marker}`;
    }
    if (isCircled) seenCircled = true;
    lastIndex = markerRe.lastIndex;
  }

  const tail = masked.slice(lastIndex);
  html += spanOpen ? tail + "</span>" : tail;
  html = html.replace(/^(<br>)/, "");

  return html.replace(/@@(\d+)@@/g, (mm, i) => stash[Number(i)]);
}

function highlightAmendments(text) {
  return text.replace(
    /([([])([^()[\]]*?(?:개정|신설|삭제|폐지)[^()[\]]*?)([)\]])/g,
    (m, open, inner, close) => `<span class="amend-tag">${open}${inner}${close}</span>`
  );
}

async function loadDetail(id) {
  const [r, revisionsMap] = await Promise.all([
    fetchJSON(`/api/regulations/${id}`),
    fetchJSON(`/api/regulations/${id}/revisions`),
  ]);
  location.hash = `reg-${id}`;
  markActiveTreeLink(id);

  const amendHtml = r.amendments.length
    ? `<div class="amend-list">제·개정 이력: ${r.amendments
        .map((d) => `<a href="#" class="amend-date-link" data-date="${d}">${d}</a>`)
        .join(", ")}</div>
       <div class="amend-note" id="amendNote" style="display:none"></div>`
    : "";

  const addendaHtml = r.addenda.length
    ? `<div class="addenda"><strong>부칙</strong><br>${r.addenda.join("<br>")}</div>`
    : "";

  const breadcrumbInner = `홈 <span class="sep">&rsaquo;</span> ${[r.category_l0, r.category_l1].filter(Boolean).join(' <span class="sep">&rsaquo;</span> ')} <span class="sep">&rsaquo;</span> ${r.title}`;

  setContent(
    renderDocHeader("&larr; 목록으로", breadcrumbInner, r.title),
    `<div class="reg-detail" id="regDetailBody" style="font-size:${docFontSize}px">
       <div class="reg-meta">
         분류: ${[r.category_l0, r.category_l1].filter(Boolean).join(" &gt; ")}
         ${r.enact_date ? ` · 제정일: ${r.enact_date}` : ""}
         ${r.source_pages ? ` · 원본 PDF p.${r.source_pages}` : ""}
       </div>
       ${amendHtml}
       ${renderArticles(r.articles)}
       ${addendaHtml}
     </div>`
  );

  renderSidebar(id, r.articles, r.attachments);

  document.getElementById("backLink").addEventListener("click", goBack);
  bindDocToolbar();

  contentBodyEl.querySelectorAll(".amend-date-link").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const d = a.dataset.date;
      const rev = revisionsMap[d];
      const note = document.getElementById("amendNote");
      if (rev) {
        note.style.display = "none";
        loadRevisionCompare(id, rev.id);
      } else {
        note.style.display = "block";
        note.textContent = `${d} 개정: 시스템 도입 이전 자료로 상세 변경 비교를 제공하지 않습니다.`;
      }
    });
  });
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function diffBodies(oldText, newText) {
  const tokenize = (s) => s.match(/\S+|\s+/g) || [];
  const a = tokenize(oldText || "");
  const b = tokenize(newText || "");
  const n = a.length;
  const m = b.length;

  // LCS length table, built backwards so it can be walked forwards below.
  const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  let oldHtml = "";
  let newHtml = "";
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      const same = escapeHtml(a[i]);
      oldHtml += same;
      newHtml += same;
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      oldHtml += `<span class="diff-del">${escapeHtml(a[i])}</span>`;
      i++;
    } else {
      newHtml += `<span class="diff-ins">${escapeHtml(b[j])}</span>`;
      j++;
    }
  }
  while (i < n) {
    oldHtml += `<span class="diff-del">${escapeHtml(a[i])}</span>`;
    i++;
  }
  while (j < m) {
    newHtml += `<span class="diff-ins">${escapeHtml(b[j])}</span>`;
    j++;
  }
  return { oldHtml, newHtml };
}

function renderCompareRows(changes) {
  return changes
    .map((c) => {
      const artNo = c.article_sub_no
        ? `제${c.article_no}조의${c.article_sub_no}`
        : `제${c.article_no}조`;
      const { oldHtml, newHtml } = diffBodies(c.old_body, c.new_body);
      return `
        <tr>
          <td class="compare-artno">${artNo}${c.article_title ? `(${c.article_title})` : ""}</td>
          <td class="compare-old">${highlightAmendments(formatArticleBody(oldHtml))}</td>
          <td class="compare-new">${highlightAmendments(formatArticleBody(newHtml))}</td>
        </tr>`;
    })
    .join("");
}

async function loadRevisionCompare(regId, revisionId) {
  const [reg, rev] = await Promise.all([
    fetchJSON(`/api/regulations/${regId}`),
    fetchJSON(`/api/revisions/${revisionId}`),
  ]);
  location.hash = `reg-${regId}-rev-${revisionId}`;

  const breadcrumbInner = `홈 <span class="sep">&rsaquo;</span> ${reg.title} <span class="sep">&rsaquo;</span> 신구조문대조표`;

  setContent(
    renderDocHeader(`&larr; ${reg.title}으로 돌아가기`, breadcrumbInner, `신구조문대조표 (${rev.revised_at})`),
    `<div class="reg-detail" style="font-size:${docFontSize}px">
       ${rev.summary ? `<p class="reg-meta">개정 사유: ${rev.summary}</p>` : ""}
       <table class="compare-table">
         <thead><tr><th>조문</th><th>개정 전</th><th>개정 후</th></tr></thead>
         <tbody>${renderCompareRows(rev.changes) || '<tr><td colspan="3">변경 내역이 없습니다.</td></tr>'}</tbody>
       </table>
     </div>`
  );

  renderSidebar(regId, reg.articles, reg.attachments);
  document.getElementById("backLink").addEventListener("click", () => loadDetail(regId));
  bindDocToolbar();
}

async function loadAttachmentDetail(regId, ordinal) {
  const r = await fetchJSON(`/api/regulations/${regId}`);
  const att = r.attachments.find((a) => a.ordinal === ordinal);
  location.hash = `reg-${regId}-att-${ordinal}`;

  const breadcrumbInner = `홈 <span class="sep">&rsaquo;</span> ${r.title} <span class="sep">&rsaquo;</span> 별표·서식`;

  setContent(
    renderDocHeader(`&larr; ${r.title}으로 돌아가기`, breadcrumbInner, att ? att.label : "서식을 찾을 수 없습니다"),
    `<div class="reg-detail" style="font-size:${docFontSize}px">${att ? renderAttachmentFile(att) : ""}</div>`
  );

  renderSidebar(regId, r.articles, r.attachments);

  document.getElementById("backLink").addEventListener("click", () => loadDetail(regId));
  bindDocToolbar();
}

async function loadRecent() {
  clearSidebar();
  lastListView = () => loadRecent();
  const recent = await fetchJSON("/api/regulations/recent?limit=10");
  const rows = recent
    .map((r) => `<tr data-id="${r.id}"><td>${r.title}</td><td>${r.latest_amend}</td></tr>`)
    .join("");

  setContent(
    `<h2>최근 제·개정 규정</h2>`,
    `<table class="reg-list">
      <thead>
        <tr><th>규정명</th><th>최근 개정일</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="2">결과가 없습니다.</td></tr>'}</tbody>
    </table>`
  );

  contentBodyEl.querySelectorAll("tbody tr[data-id]").forEach((tr) => {
    tr.addEventListener("click", () => loadDetail(Number(tr.dataset.id)));
  });
}

async function loadAttachmentsList(page) {
  clearSidebar();
  lastListView = () => loadAttachmentsList(page);
  const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
  const data = await fetchJSON(`/api/attachments?${params.toString()}`);

  const rows = data.results
    .map(
      (a) => `
      <tr data-reg="${a.regulation_id}" data-ord="${a.ordinal}">
        <td>${a.regulation_title}</td>
        <td>${a.label}</td>
        <td>${a.file_url ? "원본 PDF" : "내용 없음"}</td>
        <td>${a.start_page ? `p.${a.start_page}${a.end_page && a.end_page !== a.start_page ? `~${a.end_page}` : ""}` : "-"}</td>
      </tr>`
    )
    .join("");

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const pagerHtml = totalPages > 1 ? `
    <div class="pager">
      <button id="prevAttPage" ${page <= 1 ? "disabled" : ""}>&larr; 이전</button>
      <span>${page} / ${totalPages} 페이지</span>
      <button id="nextAttPage" ${page >= totalPages ? "disabled" : ""}>다음 &rarr;</button>
    </div>` : "";

  setContent(
    `<h2>서식 정보</h2><p class="result-count">총 ${data.total}건</p>`,
    `<table class="reg-list">
      <thead>
        <tr><th>규정명</th><th>서식명</th><th>형태</th><th>원본 페이지</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="4">결과가 없습니다.</td></tr>'}</tbody>
    </table>
    ${pagerHtml}`
  );

  contentBodyEl.querySelectorAll("tbody tr[data-reg]").forEach((tr) => {
    tr.addEventListener("click", () => loadAttachmentDetail(Number(tr.dataset.reg), Number(tr.dataset.ord)));
  });

  const prevBtn = document.getElementById("prevAttPage");
  const nextBtn = document.getElementById("nextAttPage");
  if (prevBtn) prevBtn.addEventListener("click", () => loadAttachmentsList(page - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadAttachmentsList(page + 1));
}

let revisionFilters = { q: "", dateFrom: "", dateTo: "" };

async function loadRevisionsList(page, filters) {
  if (filters) revisionFilters = filters;
  clearSidebar();
  lastListView = () => loadRevisionsList(page);

  const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
  if (revisionFilters.q) params.set("q", revisionFilters.q);
  if (revisionFilters.dateFrom) params.set("date_from", revisionFilters.dateFrom);
  if (revisionFilters.dateTo) params.set("date_to", revisionFilters.dateTo);

  const data = await fetchJSON(`/api/revisions?${params.toString()}`);

  const rows = data.results
    .map(
      (rv) => `
      <tr data-reg="${rv.regulation_id}" data-rev="${rv.id}">
        <td>${rv.regulation_title}</td>
        <td>${rv.revised_at}</td>
        <td>${rv.changed_count}개 조문</td>
        <td>${rv.summary || "-"}</td>
      </tr>`
    )
    .join("");

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const pagerHtml = totalPages > 1 ? `
    <div class="pager">
      <button id="prevRevPage" ${page <= 1 ? "disabled" : ""}>&larr; 이전</button>
      <span>${page} / ${totalPages} 페이지</span>
      <button id="nextRevPage" ${page >= totalPages ? "disabled" : ""}>다음 &rarr;</button>
    </div>` : "";

  setContent(
    `<h2>개정내역</h2>
     <div class="rev-filter-bar">
       <input type="text" id="revFilterQ" placeholder="규정명으로 필터" value="${revisionFilters.q}">
       <label>부터 <input type="date" id="revFilterFrom" value="${revisionFilters.dateFrom}"></label>
       <label>까지 <input type="date" id="revFilterTo" value="${revisionFilters.dateTo}"></label>
       <button id="revFilterApply">필터 적용</button>
       <button id="revFilterReset">초기화</button>
     </div>
     <p class="result-count">총 ${data.total}건 (개정 전·후 조문을 비교해 볼 수 있는 이력만 모았습니다)</p>`,
    `<table class="reg-list">
      <thead>
        <tr><th>규정명</th><th>개정일자</th><th>변경 조문</th><th>개정 사유</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="4">조건에 맞는 개정내역이 없습니다.</td></tr>'}</tbody>
    </table>
    ${pagerHtml}`
  );

  contentBodyEl.querySelectorAll("tbody tr[data-rev]").forEach((tr) => {
    tr.addEventListener("click", () => loadRevisionCompare(Number(tr.dataset.reg), Number(tr.dataset.rev)));
  });

  const prevBtn = document.getElementById("prevRevPage");
  const nextBtn = document.getElementById("nextRevPage");
  if (prevBtn) prevBtn.addEventListener("click", () => loadRevisionsList(page - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => loadRevisionsList(page + 1));

  const applyFilters = () => {
    loadRevisionsList(1, {
      q: document.getElementById("revFilterQ").value.trim(),
      dateFrom: document.getElementById("revFilterFrom").value,
      dateTo: document.getElementById("revFilterTo").value,
    });
  };
  document.getElementById("revFilterApply").addEventListener("click", applyFilters);
  document.getElementById("revFilterQ").addEventListener("keypress", (e) => {
    if (e.key === "Enter") applyFilters();
  });
  document.getElementById("revFilterReset").addEventListener("click", () => {
    loadRevisionsList(1, { q: "", dateFrom: "", dateTo: "" });
  });
}

document.getElementById("navForms").addEventListener("click", (e) => {
  e.preventDefault();
  loadAttachmentsList(1);
});
document.getElementById("navRecent").addEventListener("click", (e) => {
  e.preventDefault();
  loadRecent();
});
document.getElementById("navRevisions").addEventListener("click", (e) => {
  e.preventDefault();
  loadRevisionsList(1, { q: "", dateFrom: "", dateTo: "" });
});
document.getElementById("homeLink").addEventListener("click", () => {
  location.hash = "";
  loadRecent();
});

searchBtn.addEventListener("click", runSearch);
searchInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") runSearch();
});

function initFromHash() {
  const m2 = location.hash.match(/^#reg-(\d+)-att-(\d+)/);
  if (m2) {
    loadAttachmentDetail(Number(m2[1]), Number(m2[2]));
    return;
  }
  const m3 = location.hash.match(/^#reg-(\d+)-rev-(\d+)/);
  if (m3) {
    loadRevisionCompare(Number(m3[1]), Number(m3[2]));
    return;
  }
  const m = location.hash.match(/^#reg-(\d+)/);
  if (m) loadDetail(Number(m[1]));
}

window.addEventListener("hashchange", initFromHash);

(async function init() {
  await loadTree();
  loadRecent();
  initFromHash();
})();
