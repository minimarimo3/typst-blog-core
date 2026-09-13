#import "../core/shared.typ": main-font, heading-font, math-font
#import "i18n.typ": i18n

#let _notes(data) = state("blog-footnotes-" + data.page.url, ())
#let _counter(data) = counter("blog-footnotes-" + data.page.url)

// Applied to the complete page so authored content in an abstract can also
// contribute footnotes. Both articles and fixed pages use the same exporter.
#let content-rules(data, body) = context {
  set heading(numbering: "1.")
  set text(font: main-font, ..data.site.language)
  show heading: set text(font: heading-font)
  show figure.where(kind: table): set figure.caption(position: top)
  show figure.where(kind: raw): set figure(supplement: i18n.code)
  set quote(block: true)
  if math-font != none {
    show math.equation: set text(font: math-font)
  }

  show footnote: it => context {
    let note-counter = _counter(data)
    note-counter.step()
    let num = note-counter.get().first() + 1
    _notes(data).update(notes => notes + ((number: num, body: it.body),))
    html.elem("sup", attrs: (class: "footnote-wrapper"), {
      html.elem("a", attrs: (
        id: "footnote-reference-" + str(num),
        class: "footnote-marker",
        href: "#footnote-" + str(num),
        role: "doc-noteref",
      ), "※" + str(num))
    })
  }
  body
}

#let content-body(data) = {
  html.elem("div", attrs: (class: "article-body", itemprop: "articleBody"), {
    data.body
    context {
      let notes = _notes(data).final()
      if notes.len() > 0 {
        html.elem("section", attrs: (class: "footnotes", role: "doc-endnotes", "aria-labelledby": "footnotes-heading"), {
          html.elem("h2", attrs: (id: "footnotes-heading", class: "footnotes-heading"), i18n.footnotes)
          html.elem("ol", attrs: (class: "footnotes-list"), {
            for note in notes {
              html.elem("li", attrs: (id: "footnote-" + str(note.number), role: "doc-endnote"), {
                html.div(class: "footnote-body", note.body)
                [ ]
                html.elem("a", attrs: (
                  class: "footnote-backlink",
                  href: "#footnote-reference-" + str(note.number),
                  role: "doc-backlink",
                  "aria-label": i18n.back_to_footnote_reference,
                ), "↩")
              })
            }
          })
        })
      }
    }
  })
}
