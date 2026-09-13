#import "/site.typ": site
#import "../../core/shared.typ": base-path
#import "../i18n.typ": i18n

#let icons = (
  x: `<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><title>X</title><path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z"/></svg>`.text,
  misskey: `<svg class="bi" fill="currentColor" viewBox="0 0 160 160" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xml:space="preserve" xmlns:serif="http://www.serif.com/" style="fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;stroke-miterlimit:2;"><g transform="matrix(0.28948,0,0,0.28948,-54.705,-30.7703)"><path d="M256.418,188.976C248.558,188.944 240.758,190.308 233.379,193.013C220.308,197.613 209.533,205.888 201.091,217.802C193.02,229.329 188.977,242.195 188.977,256.409L188.977,508.89C188.977,527.332 195.52,543.29 208.576,556.732C222.032,569.803 237.99,576.331 256.418,576.331C275.259,576.331 291.204,569.803 304.274,556.747C317.73,543.291 324.441,527.332 324.441,508.89L324.441,462.983C324.584,453.04 334.824,455.655 340.01,462.983C349.691,479.76 372.36,494.119 394.193,494.119C416.026,494.119 438.005,482.196 448.375,462.983C452.304,458.354 463.377,450.455 464.52,462.983L464.52,508.89C464.52,527.332 471.047,543.29 484.104,556.732C497.574,569.803 513.511,576.331 531.953,576.331C550.78,576.331 566.739,569.803 579.809,556.747C593.265,543.291 599.977,527.332 599.977,508.89L599.977,256.409C599.977,242.195 595.752,229.329 587.309,217.802C579.224,205.874 568.653,197.613 555.597,193.013C547.912,190.314 540.228,188.976 532.543,188.976C511.788,188.976 494.301,197.046 480.073,213.188L411.636,293.281C410.107,294.438 405.006,303.247 394.178,303.247C383.379,303.247 378.868,294.439 377.325,293.296L308.297,213.188C294.47,197.046 277.173,188.976 256.418,188.976ZM682.904,188.983C666.763,188.983 652.926,194.748 641.404,206.271C630.261,217.413 624.691,231.054 624.691,247.196C624.691,263.338 630.261,277.174 641.404,288.697C652.926,299.839 666.763,305.41 682.904,305.41C699.046,305.41 712.88,299.839 724.412,288.697C735.935,277.174 741.693,263.338 741.693,247.196C741.693,231.054 735.935,217.413 724.412,206.271C712.88,194.748 699.046,188.983 682.904,188.983ZM683.473,316.947C667.331,316.947 653.495,322.713 641.972,334.236C630.449,345.768 624.691,359.602 624.691,375.744L624.691,518.118C624.691,534.259 630.449,548.095 641.972,559.618C653.504,570.761 667.341,576.331 683.473,576.331C699.624,576.331 713.27,570.761 724.412,559.618C735.935,548.095 741.693,534.259 741.693,518.118L741.693,375.744C741.693,359.593 735.935,345.759 724.412,334.236C713.261,322.713 699.614,316.947 683.473,316.947Z" style="fill-rule:nonzero;"/></g></svg>`.text,
  github: `<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><title>GitHub</title><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>`.text,
)

#let widget-author(extra-class: "") = {
  let author = site.author
  let links = author.at("links", default: ())
  let widget-class = "sidebar-widget author-widget" + if extra-class == "" { "" } else { " " + extra-class }
  html.elem(
    "div",
    attrs: (class: widget-class, "data-pagefind-ignore": "all", "data-nosnippet": ""),
    {
      html.div(class: "widget-title", i18n.author)
      html.strong(author.name)
      if author.bio != "" {
        html.p(
          class: "widget-description",
          author.bio,
        )
      }
      html.div(class: "author-links", {
        for link in links {
          let custom-icon = link.at("icon", default: none)
          let built-in-icon = icons.at(link.id, default: none)
          let has-icon = custom-icon != none or built-in-icon != none
          let link-class = "author-icon-link" + if has-icon { "" } else { " author-text-link" }
          html.elem("a", attrs: (class: link-class, href: link.url, target: "_blank", rel: "noopener noreferrer", "aria-label": link.label), {
            if custom-icon != none {
              html.elem("img", attrs: (class: "author-custom-icon", src: base-path + "/" + custom-icon, alt: ""))
            } else if built-in-icon != none {
              html.elem("div", attrs: (class: "raw-html-embed icon-" + link.id, "data-html": built-in-icon))
            } else {
              link.label
            }
          })
        }
      })
    },
  )
}

#let widget-search(extra-class: "") = {
  let widget-class = "sidebar-widget search-widget site-search" + if extra-class == "" { "" } else { " " + extra-class }
  html.elem(
    "div",
    attrs: (
      class: widget-class,
      role: "search",
      "aria-label": i18n.search,
      "data-pagefind-ignore": "all",
      "data-nosnippet": "",
      "data-search-loading": i18n.search_loading,
      "data-search-empty": i18n.search_no_results,
      "data-search-error": i18n.search_error,
    ),
    {
      html.div(class: "widget-title", i18n.search)
      html.elem(
        "input",
        attrs: (
          class: "search-input",
          type: "search",
          placeholder: i18n.search_placeholder,
          autocomplete: "off",
          "aria-label": i18n.search,
        ),
      )
      html.elem("div", attrs: (class: "search-status", role: "status", "aria-live": "polite", hidden: ""))
      html.elem("ol", attrs: (class: "search-results", "aria-label": i18n.search))
    },
  )
}

#let widget-about() = {
  html.div(class: "sidebar-widget", {
    html.div(class: "widget-title", i18n.about_blog)
    html.p(
      class: "widget-description",
      site.description,
    )
    html.p(
      class: "widget-meta-link",
      html.elem(
        "a",
        attrs: (href: base-path + "/third-party-licenses.txt"),
        i18n.third_party_licenses,
      ),
    )
  })
}

#let widget-mobile-search() = {
  html.div(class: "mobile-search", {
    widget-search()
  })
}

#let widget-responsive-toc() = html.elem("div", attrs: (class: "toc-desktop-slot", "data-toc-desktop-slot": ""), {
  html.elem(
    "section",
    attrs: (
      class: "responsive-toc",
      "aria-label": i18n.toc,
      "data-responsive-toc": "",
      "data-pagefind-ignore": "all",
      "data-nosnippet": "",
    ),
    {
      html.elem("details", attrs: (open: ""), {
        html.summary(i18n.toc)
        outline(title: none)
      })
    },
  )
})

#let widget-toc-inline-slot() = {
  html.elem("div", attrs: (class: "toc-inline-slot", "data-toc-inline-slot": ""))
}
