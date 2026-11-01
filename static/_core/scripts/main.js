import { initArticleActions } from "./article-actions.js";
import {
  initCodeCopy,
  initTableCopy,
  initExternalLinks,
  initRawHtmlEmbeds,
} from "./content-enhancements.js";
import {
  initFootnoteHoverPreview,
  initReferencePreview,
} from "./reference-preview.js";
import { initSiteSearch } from "./search.js";
import { initResponsiveToc } from "./responsive-toc.js";

initResponsiveToc();
initSiteSearch();
initCodeCopy();
initTableCopy();
initExternalLinks();
initRawHtmlEmbeds();
initFootnoteHoverPreview();
initReferencePreview();
initArticleActions();
