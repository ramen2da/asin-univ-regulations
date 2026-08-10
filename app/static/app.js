const treeEl = document.getElementById("tree");
const contentEl = document.getElementById("content");
const contentHeaderEl = document.getElementById("contentHeader");
const contentBodyEl = document.getElementById("contentBody");
const sidebarEl = document.getElementById("detailSidebar");
const searchInput = document.getElementById("searchInput");
const searchScope = document.getElementById("searchScope");
const searchBtn = document.getElementById("searchBtn");

let docFontSize = 15;
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
    label.textContent = node.name;
    label.addEventListener("click", () => {
      li.classList.remove("collapsed");
      arrow.textContent = "▾";
      loadListByCategory(node.name, node.parentL0);
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
    a.textContent = node.title;
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
  renderList(data, heading, page);
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

function renderCompareRows(changes) {
  return changes
    .map((c) => {
      const artNo = c.article_sub_no
        ? `제${c.article_no}조의${c.article_sub_no}`
        : `제${c.article_no}조`;
      return `
        <tr>
          <td class="compare-artno">${artNo}${c.article_title ? `(${c.article_title})` : ""}</td>
          <td class="compare-old">${highlightAmendments(formatArticleBody(c.old_body))}</td>
          <td class="compare-new">${highlightAmendments(formatArticleBody(c.new_body))}</td>
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
  const items = recent
    .map((r) => `<li><a href="#reg-${r.id}" data-id="${r.id}">${r.title}</a> <span style="color:#999">(${r.latest_amend})</span></li>`)
    .join("");
  setContent(`<h2>최근 제·개정 규정</h2>`, `<ul>${items}</ul>`);
  contentBodyEl.querySelectorAll("a[data-id]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      loadDetail(Number(a.dataset.id));
    });
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

async function loadRevisionsList(page) {
  clearSidebar();
  lastListView = () => loadRevisionsList(page);
  const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
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
    `<h2>개정내역</h2><p class="result-count">총 ${data.total}건 (관리자 화면에서 수정된 조문의 개정 전·후 비교를 볼 수 있습니다)</p>`,
    `<table class="reg-list">
      <thead>
        <tr><th>규정명</th><th>개정일자</th><th>변경 조문</th><th>개정 사유</th></tr>
      </thead>
      <tbody>${rows || '<tr><td colspan="4">등록된 개정내역이 없습니다.</td></tr>'}</tbody>
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
  loadRevisionsList(1);
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

loadTree();
loadRecent();
initFromHash();
