const loginSection = document.getElementById("loginSection");
const editorSection = document.getElementById("editorSection");
const passwordInput = document.getElementById("passwordInput");
const loginBtn = document.getElementById("loginBtn");
const loginError = document.getElementById("loginError");
const logoutLink = document.getElementById("logoutLink");

const regFilter = document.getElementById("regFilter");
const regList = document.getElementById("regList");

const articlePanel = document.getElementById("articlePanel");
const articlePanelTitle = document.getElementById("articlePanelTitle");
const articleOutline = document.getElementById("articleOutline");

const editPanel = document.getElementById("editPanel");
const editArticleHead = document.getElementById("editArticleHead");
const editBody = document.getElementById("editBody");
const revisedAt = document.getElementById("revisedAt");
const revisedSummary = document.getElementById("revisedSummary");
const saveBtn = document.getElementById("saveBtn");
const saveResult = document.getElementById("saveResult");
const emptyHint = document.getElementById("emptyHint");
const emptyHintText = document.getElementById("emptyHintText");

let allRegulations = [];
let currentRegId = null;
let currentArticles = [];
let currentArticleId = null;
let changedArticleIds = new Set();

async function api(url, options) {
  const res = await fetch(url, { ...options, credentials: "same-origin" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `요청 실패: ${res.status}`);
  }
  return res.json();
}

async function checkLogin() {
  try {
    await api("/api/admin/check");
    return true;
  } catch {
    return false;
  }
}

function showEditor() {
  loginSection.style.display = "none";
  editorSection.style.display = "flex";
  logoutLink.style.display = "inline";
  loadRegulationList();
}

function showLogin() {
  loginSection.style.display = "block";
  editorSection.style.display = "none";
  logoutLink.style.display = "none";
}

loginBtn.addEventListener("click", async () => {
  loginError.textContent = "";
  try {
    await api("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: passwordInput.value }),
    });
    passwordInput.value = "";
    showEditor();
  } catch (e) {
    loginError.textContent = e.message;
  }
});
passwordInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") loginBtn.click();
});

logoutLink.addEventListener("click", async (e) => {
  e.preventDefault();
  await api("/api/admin/logout", { method: "POST" });
  showLogin();
});

async function loadRegulationList() {
  allRegulations = await api("/api/admin/regulations");
  renderRegList(allRegulations);
}

function renderRegList(list) {
  regList.innerHTML = list
    .map((r) => `<li data-id="${r.id}">${r.seq}. ${r.title}</li>`)
    .join("");
  regList.querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", () => selectRegulation(Number(li.dataset.id)));
  });
}

regFilter.addEventListener("input", () => {
  const q = regFilter.value.trim().toLowerCase();
  const filtered = q
    ? allRegulations.filter((r) => r.title.toLowerCase().includes(q))
    : allRegulations;
  renderRegList(filtered);
});

function todayLocalISODate() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function articleLabel(a) {
  return a.sub_no ? `제${a.no}조의${a.sub_no}` : `제${a.no}조`;
}

async function selectRegulation(id) {
  currentRegId = id;
  currentArticleId = null;
  changedArticleIds = new Set();
  editPanel.style.display = "none";
  emptyHint.style.display = "none";
  saveResult.textContent = "";

  regList.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("selected", Number(li.dataset.id) === id);
  });

  const reg = await api(`/api/admin/regulations/${id}`);
  currentArticles = reg.articles;

  articlePanelTitle.textContent = reg.title;
  articlePanel.style.display = "flex";

  articleOutline.innerHTML = currentArticles
    .map(
      (a) => `
      <li data-id="${a.id}">
        ${articleLabel(a)}${a.title ? `<span class="art-title"> (${a.title})</span>` : ""}
      </li>`
    )
    .join("");
  articleOutline.querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", () => selectArticle(Number(li.dataset.id)));
  });

  emptyHintText.textContent = "가운데 목록에서 조문을 선택하세요.";
  emptyHint.style.display = "flex";
}

function articleBodyToDisplay(text) {
  const stash = [];
  const masked = (text || "").replace(/([([][^()[\]]*[)\]])/g, (m) => {
    stash.push(m);
    return `@@${stash.length - 1}@@`;
  });

  const markerRe = /[①-⑳](?![,"'"])|(?<=\s)[1-9][0-9]?\.(?=\s)/g;
  let lastIndex = 0;
  let seenCircled = false;
  let out = "";
  let m;
  while ((m = markerRe.exec(masked)) !== null) {
    out += masked.slice(lastIndex, m.index);
    const marker = m[0];
    const isCircled = /[①-⑳]/.test(marker);
    out += (!isCircled && seenCircled) ? `\n  ${marker}` : `\n${marker}`;
    if (isCircled) seenCircled = true;
    lastIndex = markerRe.lastIndex;
  }
  out += masked.slice(lastIndex);
  out = out.replace(/^\n/, "");
  return out.replace(/@@(\d+)@@/g, (mm, i) => stash[Number(i)]);
}

function articleBodyToStorage(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function selectArticle(articleId) {
  currentArticleId = articleId;
  const article = currentArticles.find((a) => a.id === articleId);
  if (!article) return;

  emptyHint.style.display = "none";
  editPanel.style.display = "flex";

  articleOutline.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("selected", Number(li.dataset.id) === articleId);
  });

  editArticleHead.textContent = `${articleLabel(article)}${article.title ? `(${article.title})` : ""}`;
  editBody.value = articleBodyToDisplay(article.body);
  editBody.dataset.original = editBody.value;
  editBody.classList.remove("changed");
  revisedAt.value = todayLocalISODate();
  revisedSummary.value = "";
  saveResult.textContent = "";
}

editBody.addEventListener("input", () => {
  editBody.classList.toggle("changed", editBody.value !== editBody.dataset.original);
});

saveBtn.addEventListener("click", async () => {
  if (!currentRegId || !currentArticleId) return;
  if (!revisedAt.value) {
    saveResult.style.color = "#c0392b";
    saveResult.textContent = "개정일자를 입력하세요.";
    return;
  }

  try {
    const storageBody = articleBodyToStorage(editBody.value);
    const result = await api(`/api/admin/regulations/${currentRegId}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        revised_at: revisedAt.value,
        summary: revisedSummary.value || null,
        articles: [{ id: currentArticleId, body: storageBody }],
      }),
    });
    saveResult.style.color = "#1a7a3c";
    saveResult.textContent =
      result.changed > 0
        ? `저장되었습니다. (${revisedAt.value} 개정으로 기록됨)`
        : "변경된 내용이 없습니다.";

    if (result.changed > 0) {
      const article = currentArticles.find((a) => a.id === currentArticleId);
      if (article) article.body = storageBody;
      editBody.value = articleBodyToDisplay(storageBody);
      editBody.dataset.original = editBody.value;
      editBody.classList.remove("changed");
      const li = articleOutline.querySelector(`li[data-id="${currentArticleId}"]`);
      if (li) li.classList.add("changed-marker");
    }
  } catch (e) {
    saveResult.style.color = "#c0392b";
    saveResult.textContent = e.message;
  }
});

(async function init() {
  const loggedIn = await checkLogin();
  if (loggedIn) showEditor();
  else showLogin();
})();
