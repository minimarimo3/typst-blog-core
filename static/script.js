function shareX() {
  const url = encodeURIComponent(window.location.href);
  const text = encodeURIComponent(document.title);
  window.open(`https://twitter.com/intent/tweet?text=${text}&url=${url}`, "_blank", "noopener,noreferrer");
}

function shareMisskey() {
  const url = encodeURIComponent(window.location.href);
  const text = encodeURIComponent(document.title);
  window.open(`https://misskey-hub.net/share/?text=${text}&url=${url}`, "_blank", "noopener,noreferrer");
}

function openFeedback(url, entryId) {
  if (!url) return;

  const title = document.title;
  if (!entryId) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }

  const separator = url.includes("?") ? "&" : "?";
  const fullUrl = `${url}${separator}usp=pp_url&${entryId}=${encodeURIComponent(title)}`;
  window.open(fullUrl, "_blank", "noopener,noreferrer");
}

let copyToastTimer;

function copyInfo() {
  const title = document.title;
  const desc = document.querySelector(".abstract-content")?.innerText.trim()
    || document.querySelector('meta[name="description"]')?.content
    || "";
  const url = window.location.href;
  const textToCopy = `${title}\n${desc}\n${url}`;

  navigator.clipboard.writeText(textToCopy).then(() => {
    const toast = document.getElementById("copy-toast");
    if (!toast) return;
    toast.textContent = toast.dataset.copiedLabel || "Copied!";
    toast.classList.add("show");
    window.clearTimeout(copyToastTimer);
    copyToastTimer = window.setTimeout(() => {
      toast.classList.remove("show");
      copyToastTimer = window.setTimeout(() => {
        if (!toast.classList.contains("show")) {
          toast.textContent = "";
        }
      }, 300);
    }, 3000);
  });
}

let pagefindPromise;

function loadPagefind() {
  if (!pagefindPromise) {
    const basePath = document.querySelector('meta[name="base-path"]')?.content ?? "";
    pagefindPromise = import(basePath + "/pagefind/pagefind.js")
      .then((pagefind) => {
        pagefind.init();
        return pagefind;
      })
      .catch((error) => {
        pagefindPromise = undefined;
        throw error;
      });
  }

  return pagefindPromise;
}

function initSiteSearch() {
  const widgets = document.querySelectorAll(".site-search");
  if (widgets.length === 0) return;

  widgets.forEach((widget) => {
    const input = widget.querySelector(".search-input");
    const status = widget.querySelector(".search-status");
    const results = widget.querySelector(".search-results");
    if (!input || !status || !results) return;

    const loadingMessage = widget.dataset.searchLoading || "Searching...";
    const emptyMessage = widget.dataset.searchEmpty || "No matching posts.";
    const errorMessage = widget.dataset.searchError || "Could not load the search index.";
    let requestId = 0;

    const setStatus = (message) => {
      status.textContent = message;
      status.hidden = !message;
    };

    const clearResults = () => {
      results.replaceChildren();
      setStatus("");
    };

    const renderResults = (items) => {
      results.replaceChildren();

      if (items.length === 0) {
        setStatus(emptyMessage);
        return;
      }

      setStatus("");
      items.forEach((item) => {
        const li = document.createElement("li");
        li.className = "search-result";

        const link = document.createElement("a");
        link.className = "search-result-link";
        link.href = item.url;

        const title = document.createElement("span");
        title.className = "search-result-title";
        title.textContent = item.meta?.title || item.url;

        const excerpt = document.createElement("span");
        excerpt.className = "search-result-excerpt";
        excerpt.innerHTML = item.excerpt || "";

        link.append(title, excerpt);
        li.append(link);
        results.append(li);
      });
    };

    const runSearch = async () => {
      const query = input.value.trim();
      const currentRequest = ++requestId;

      if (!query) {
        clearResults();
        return;
      }

      setStatus(loadingMessage);

      try {
        const pagefind = await loadPagefind();
        const search = await pagefind.debouncedSearch(query);
        if (search === null || currentRequest !== requestId) return;

        const items = await Promise.all(search.results.slice(0, 6).map((result) => result.data()));
        if (currentRequest !== requestId) return;

        renderResults(items);
      } catch (error) {
        console.warn("Pagefind search is unavailable.", error);
        results.replaceChildren();
        setStatus(errorMessage);
      }
    };

    input.addEventListener("focus", () => {
      loadPagefind().catch(() => {});
    }, { once: true });

    input.addEventListener("input", runSearch);
  });
}

document.addEventListener("DOMContentLoaded", initSiteSearch);

document.addEventListener("DOMContentLoaded", () => {
  const copyIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  const checkIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>';

  const _labels = {
    ja: { copy: "コードをコピー", copied: "コピーしました" },
    en: { copy: "Copy code", copied: "Copied!" },
    ko: { copy: "코드 복사", copied: "복사됨" },
    "zh-CN": { copy: "复制代码", copied: "已复制" },
    "zh-TW": { copy: "複製程式碼", copied: "已複製" },
  };
  const _lang = document.documentElement.lang || "ja";
  const labels = _labels[_lang] ?? _labels.ja;

  document.querySelectorAll("pre").forEach((pre) => {
    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    const btn = document.createElement("button");
    btn.className = "code-copy-btn";
    btn.setAttribute("aria-label", labels.copy);
    btn.innerHTML = copyIcon;
    wrapper.appendChild(btn);

    btn.addEventListener("click", () => {
      const code = pre.querySelector("code")?.innerText ?? pre.innerText;
      navigator.clipboard.writeText(code).then(() => {
        btn.classList.add("copied");
        btn.innerHTML = checkIcon;
        btn.setAttribute("aria-label", labels.copied);
        setTimeout(() => {
          btn.classList.remove("copied");
          btn.innerHTML = copyIcon;
          btn.setAttribute("aria-label", labels.copy);
        }, 2000);
      }).catch(() => {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(pre);
        selection?.removeAllRanges();
        selection?.addRange(range);
      });
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("a[href]").forEach((a) => {
    if (a.hostname && a.hostname !== window.location.hostname) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".raw-html-embed").forEach((el) => {
    const htmlContent = el.getAttribute("data-html");
    if (!htmlContent) return;

    const template = document.createElement("template");
    template.innerHTML = htmlContent;

    template.content.querySelectorAll("script").forEach((oldScript) => {
      const newScript = document.createElement("script");

      for (const attr of oldScript.attributes) {
        newScript.setAttribute(attr.name, attr.value);
      }

      newScript.textContent = oldScript.textContent;
      oldScript.replaceWith(newScript);
    });

    el.replaceWith(template.content);
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const footnoteMarkers = Array.from(
    document.querySelectorAll('.footnote-marker[role="doc-noteref"][href^="#"]'),
  );
  const supportsHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (footnoteMarkers.length === 0 || !supportsHover) return;

  const hoverPreview = document.createElement("div");
  hoverPreview.id = "footnote-hover-preview";
  hoverPreview.className = "footnote-hover-preview";
  hoverPreview.setAttribute("role", "tooltip");
  hoverPreview.setAttribute("data-pagefind-ignore", "all");
  hoverPreview.setAttribute("data-nosnippet", "");
  hoverPreview.hidden = true;
  document.body.append(hoverPreview);

  let activeMarker = null;

  const fragmentToId = (href) => {
    try {
      return decodeURIComponent(href.slice(1));
    } catch {
      return href.slice(1);
    }
  };

  const hideHoverPreview = () => {
    activeMarker?.removeAttribute("aria-describedby");
    activeMarker = null;
    hoverPreview.hidden = true;
    hoverPreview.replaceChildren();
  };

  const showHoverPreview = (marker) => {
    const href = marker.getAttribute("href");
    const footnote = href ? document.getElementById(fragmentToId(href)) : null;
    const footnoteBody = footnote?.querySelector(".footnote-body");
    if (!footnoteBody) return;

    hoverPreview.replaceChildren(footnoteBody.cloneNode(true));
    hoverPreview.hidden = false;
    activeMarker?.removeAttribute("aria-describedby");
    activeMarker = marker;
    marker.setAttribute("aria-describedby", hoverPreview.id);

    const markerRect = marker.getBoundingClientRect();
    const previewRect = hoverPreview.getBoundingClientRect();
    const gap = 8;
    const viewportPadding = 10;
    const left = Math.min(
      window.innerWidth - previewRect.width - viewportPadding,
      Math.max(
        viewportPadding,
        markerRect.left + markerRect.width / 2 - previewRect.width / 2,
      ),
    );
    const above = markerRect.top - previewRect.height - gap;
    const top = above >= viewportPadding ? above : markerRect.bottom + gap;

    hoverPreview.style.left = `${left}px`;
    hoverPreview.style.top = `${top}px`;
  };

  footnoteMarkers.forEach((marker) => {
    marker.addEventListener("mouseenter", () => showHoverPreview(marker));
    marker.addEventListener("mouseleave", hideHoverPreview);
    marker.addEventListener("click", hideHoverPreview);
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const citationLinks = Array.from(document.querySelectorAll('a[role="doc-biblioref"][href^="#"]'));
  const footnoteMarkers = Array.from(
    document.querySelectorAll('.footnote-marker[role="doc-noteref"][href^="#"]'),
  );
  const previewSources = [...citationLinks, ...footnoteMarkers];
  if (previewSources.length === 0) return;

  const sidebarInner = document.querySelector(".sidebar-inner");
  const preview = document.createElement("aside");
  preview.id = "reference-preview";
  preview.className = "sidebar-widget reference-preview";
  preview.setAttribute("role", "dialog");
  preview.setAttribute("aria-modal", "false");
  preview.setAttribute("aria-labelledby", "reference-preview-title");
  preview.setAttribute("aria-live", "polite");
  preview.setAttribute("data-pagefind-ignore", "all");
  preview.setAttribute("data-nosnippet", "");

  const header = document.createElement("div");
  header.className = "reference-preview-header";

  const title = document.createElement("h3");
  title.id = "reference-preview-title";
  title.className = "widget-title reference-preview-title";
  title.textContent = "参考文献";

  const closeButton = document.createElement("button");
  closeButton.className = "reference-preview-close";
  closeButton.type = "button";
  const article = document.querySelector("article[data-content-preview-close-label]");
  closeButton.setAttribute(
    "aria-label",
    article?.dataset.contentPreviewCloseLabel || "Close preview",
  );
  closeButton.textContent = "x";

  const body = document.createElement("div");
  body.className = "reference-preview-body";

  header.append(title, closeButton);
  preview.append(header, body);

  if (sidebarInner) {
    sidebarInner.prepend(preview);
  } else {
    document.body.append(preview);
  }

  let activeSource = null;

  const clearActiveSource = () => {
    previewSources.forEach((link) => {
      link.classList.remove("content-preview-source-is-active");
      link.setAttribute("aria-expanded", "false");
    });
  };

  const closePreview = ({ restoreFocus = false } = {}) => {
    preview.classList.remove("is-open");
    clearActiveSource();
    if (restoreFocus && activeSource?.isConnected) activeSource.focus();
    activeSource = null;
  };

  const fragmentToId = (href) => {
    try {
      return decodeURIComponent(href.slice(1));
    } catch {
      return href.slice(1);
    }
  };

  const cloneBibliographyEntry = (entry) => {
    const list = document.createElement("ol");
    list.className = "reference-preview-list";

    const clone = entry.cloneNode(true);
    clone.removeAttribute("id");
    clone.classList.add("reference-preview-entry");

    clone.querySelectorAll('[role="doc-backlink"]').forEach((link) => {
      link.replaceWith(document.createTextNode(link.textContent));
    });

    list.append(clone);
    return list;
  };

  const cloneFootnoteEntry = (entry) => {
    const footnoteBody = entry.querySelector(".footnote-body");
    if (!footnoteBody) return null;

    const clone = footnoteBody.cloneNode(true);
    clone.classList.add("footnote-preview-entry");
    return clone;
  };

  const openPreview = (link) => {
    const href = link.getAttribute("href");
    const entry = document.getElementById(fragmentToId(href));
    if (!entry) return;

    const isFootnote = link.matches('.footnote-marker[role="doc-noteref"]');
    const content = isFootnote
      ? cloneFootnoteEntry(entry)
      : cloneBibliographyEntry(entry);
    if (!content) return;

    const sectionTitle = isFootnote
      ? document.getElementById("footnotes-heading")?.textContent.trim() || "Footnotes"
      : entry.closest('[role="doc-bibliography"]')?.querySelector("h1, h2, h3")?.textContent.trim()
        || "References";

    body.replaceChildren(content);
    title.textContent = `${sectionTitle} ${link.textContent.trim()}`;

    clearActiveSource();
    activeSource = link;
    link.classList.add("content-preview-source-is-active");
    link.setAttribute("aria-expanded", "true");
    preview.classList.add("is-open");
  };

  previewSources.forEach((link) => {
    link.setAttribute("aria-controls", "reference-preview");
    link.setAttribute("aria-haspopup", "dialog");
    link.setAttribute("aria-expanded", "false");
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest(
      'a[role="doc-biblioref"][href^="#"], .footnote-marker[role="doc-noteref"][href^="#"]',
    );
    if (!link) return;

    event.preventDefault();
    event.stopPropagation();
    openPreview(link);
  });

  closeButton.addEventListener("click", () => closePreview({ restoreFocus: true }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && preview.classList.contains("is-open")) {
      closePreview({ restoreFocus: true });
    }
  });
});
