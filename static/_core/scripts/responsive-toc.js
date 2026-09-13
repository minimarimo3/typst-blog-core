export function initResponsiveToc() {
  const toc = document.querySelector("[data-responsive-toc]");
  const inlineSlot = document.querySelector("[data-toc-inline-slot]");
  const desktopSlot = document.querySelector("[data-toc-desktop-slot]");

  if (!toc || !inlineSlot || !desktopSlot) return;

  const desktopQuery = window.matchMedia("(min-width: 901px)");
  const details = toc.querySelector("details");

  const updatePlacement = () => {
    if (desktopQuery.matches) {
      desktopSlot.append(toc);
      if (details) details.open = true;
      toc.dataset.tocPlacement = "desktop";
      return;
    }

    inlineSlot.append(toc);
    if (details) details.open = false;
    toc.dataset.tocPlacement = "inline";
  };

  document.documentElement.dataset.tocReady = "";
  updatePlacement();
  desktopQuery.addEventListener("change", updatePlacement);
}
