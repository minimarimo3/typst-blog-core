const COPY_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
const CHECK_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>';
const COPY_LABELS = {
  ja: { copy: "コードをコピー", table: "表をコピー", copied: "コピーしました" },
  en: { copy: "Copy code", table: "Copy table", copied: "Copied!" },
  ko: { copy: "코드 복사", table: "표 복사", copied: "복사됨" },
  "zh-CN": { copy: "复制代码", table: "复制表格", copied: "已复制" },
  "zh-TW": { copy: "複製程式碼", table: "複製表格", copied: "已複製" },
};

function copyLabels() {
  const language = document.documentElement.lang || "ja";
  const subtags = language.split("-");
  const region = subtags.slice(1).find((subtag) => /^[A-Za-z]{2}$/.test(subtag));
  const regionalLanguage = region ? `${subtags[0].toLowerCase()}-${region.toUpperCase()}` : null;
  const labels = COPY_LABELS[language]
    ?? (regionalLanguage ? COPY_LABELS[regionalLanguage] : undefined)
    ?? COPY_LABELS[subtags[0].toLowerCase()]
    ?? COPY_LABELS.ja;

  return labels;
}

function copyButton(container, target, label, text, className) {
  const button = document.createElement("button");
  const labels = copyLabels();
  button.type = "button";
  button.className = className;
  button.setAttribute("aria-label", label);
  button.title = label;
  button.innerHTML = COPY_ICON;
  container.appendChild(button);
  let resetTimer;

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text());
      window.clearTimeout(resetTimer);
      button.classList.add("copied");
      button.innerHTML = CHECK_ICON;
      button.setAttribute("aria-label", labels.copied);
      button.title = labels.copied;
      resetTimer = window.setTimeout(() => {
        button.classList.remove("copied");
        button.innerHTML = COPY_ICON;
        button.setAttribute("aria-label", label);
        button.title = label;
      }, 2000);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(target);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  });
}

export function initCodeCopy() {
  document.querySelectorAll("pre").forEach((pre) => {
    if (pre.parentElement.classList.contains("code-block-wrapper")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);
    copyButton(wrapper, pre, copyLabels().copy,
      () => pre.querySelector("code")?.innerText ?? pre.innerText, "code-copy-btn");
  });
}

// Leave empty fields for merged cells so spreadsheet columns stay aligned.
export function tableToTsv(table) {
  const rows = Array.from(table.rows);
  const grid = rows.map(() => []);
  rows.forEach((row, y) => {
    let x = 0;
    for (const cell of row.cells) {
      while (grid[y][x] !== undefined) x++;
      const remainingRows = row.parentElement.rows.length - row.sectionRowIndex;
      const rowSpan = Math.min(cell.rowSpan || remainingRows, remainingRows);
      for (let dy = 0; dy < rowSpan && y + dy < rows.length; dy++) {
        for (let dx = 0; dx < cell.colSpan; dx++) {
          grid[y + dy][x + dx] = dy === 0 && dx === 0 ? cell.innerText.trim() : "";
        }
      }
      x += cell.colSpan;
    }
  });
  const width = Math.max(0, ...grid.map(row => row.length));
  const escape = text => /[\t\r\n"]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  return grid.map(row => Array.from({ length: width }, (_, x) => escape(row[x] ?? "")).join("\t")).join("\n");
}

export function initTableCopy() {
  document.querySelectorAll(".table-scroll").forEach((scroll) => {
    if (scroll.parentElement.classList.contains("table-block-wrapper")) return;
    const table = scroll.querySelector("table");
    if (!table) return;
    const wrapper = document.createElement("div");
    wrapper.className = "table-block-wrapper";
    scroll.parentNode.insertBefore(wrapper, scroll);
    const toolbar = document.createElement("div");
    toolbar.className = "table-copy-toolbar";
    wrapper.append(toolbar, scroll);
    copyButton(toolbar, table, copyLabels().table, () => tableToTsv(table), "table-copy-btn");
  });
}

export function initExternalLinks() {
  document.querySelectorAll("a[href]").forEach((anchor) => {
    if (anchor.hostname && anchor.hostname !== window.location.hostname) {
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener noreferrer");
    }
  });
}

export function initRawHtmlEmbeds() {
  document.querySelectorAll(".raw-html-embed").forEach((element) => {
    const htmlContent = element.getAttribute("data-html");
    if (!htmlContent) return;

    const template = document.createElement("template");
    template.innerHTML = htmlContent;

    template.content.querySelectorAll("script").forEach((oldScript) => {
      const newScript = document.createElement("script");

      for (const attribute of oldScript.attributes) {
        newScript.setAttribute(attribute.name, attribute.value);
      }

      newScript.textContent = oldScript.textContent;
      oldScript.replaceWith(newScript);
    });

    element.replaceWith(template.content);
  });
}
