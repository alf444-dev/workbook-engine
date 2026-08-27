// ============================================================
// LEARN CHINESE (CN10) — livre complet, design v2 (brief CN10)
// Rendu 100 % automatique depuis content/book.json
// ============================================================

#let data = json("/content/book_typed.json")
#let akey = json("/content/answer_key.json")
#let meta = data.meta

// ---- Palette ----
#let c-main  = rgb("#1A5E52")
#let c-acc   = rgb("#E5A33C")
#let c-grey  = rgb("#5A6068")
#let t-main  = rgb("#EAF1EF")
#let t-acc   = rgb("#FBF3E2")
#let t-panel = rgb("#F3F6F5")
#let hairline = rgb("#D8DCDA")

#let f-head = "Archivo"
#let f-body = "Source Serif 4"
#let f-zh   = "Noto Sans SC"

#let footer-label = state("footer-label", "")

// ---- Front matter : pas de header/footer ----
#set page(width: 6in, height: 9in,
  margin: (inside: 0.8in, outside: 0.58in, top: 0.92in, bottom: 0.78in),
  binding: left)
#set text(font: f-body, size: 9.3pt, fill: rgb("#1E2124"), lang: "en")
#set par(justify: true, leading: 0.62em, spacing: 0.85em)
#set strong(delta: 200)

// masquer les headings (ils ne servent qu'à la TOC/outline)
#show heading: it => {}

// ---- Helpers ----
#let zh(s) = text(font: f-zh, size: 9.2pt)[#s]
#let py(s) = text(font: f-body, style: "italic", fill: c-grey, size: 8.2pt)[#s]

#let rich(s) = {
  let parts = ()
  let rest = s
  while rest.len() > 0 {
    let m = rest.match(regex("\\{zh:([^}]*)\\}|\\{py:([^}]*)\\}|\\{br\\}|\\*\\*([^*]+)\\*\\*|\\*([^*]+)\\*"))
    if m == none { parts.push(rest); break }
    if m.start > 0 { parts.push(rest.slice(0, m.start)) }
    if m.captures.at(0) != none { parts.push(zh(m.captures.at(0))) }
    else if m.captures.at(1) != none { parts.push([[#py(m.captures.at(1))]]) }
    else if m.captures.at(2) != none { parts.push(strong(rich(m.captures.at(2)))) }
    else if m.captures.at(3) != none { parts.push(emph(rich(m.captures.at(3)))) }
    else { parts.push(linebreak()) }
    rest = rest.slice(m.end)
  }
  parts.join()
}

// ---- Composants ----
#let section-opener(b) = block(above: 0em, below: 1.6em,
  grid(columns: (5pt, 1fr), column-gutter: 14pt, align: (top, top),
    rect(width: 5pt, height: 48pt, fill: c-acc),
    stack(spacing: 6pt,
      text(font: f-head, weight: 600, size: 9.5pt, fill: c-grey, tracking: 2.2pt)[SECTION #str(b.num)],
      par(justify: false, leading: 0.45em)[#text(font: f-head, weight: 800, size: 17pt, fill: c-main, tracking: 0.3pt)[#upper(b.title)]]
    )
  )
)

#let chapter-title(num, title, eyebrow: none) = block(above: 0em, below: 1.2em)[
  #if eyebrow != none [
    #text(font: f-head, weight: 600, size: 8.5pt, fill: c-grey, tracking: 2pt)[#upper(eyebrow)]
    #v(0.15em)
  ]
  #grid(columns: if num != none { (auto, 1fr) } else { (1fr,) }, column-gutter: 12pt, align: (top, top),
    ..if num != none {
      (rect(width: 32pt, height: 32pt, fill: c-main, radius: 4pt,
        align(center + horizon, text(font: f-head, weight: 800, size: 17pt, fill: white)[#str(num)])),)
    } else { () },
    par(justify: false, leading: 0.5em)[#text(font: f-head, weight: 800, size: 15pt, fill: c-main)[#upper(title)]]
  )
  #v(0.35em)
  #line(length: 100%, stroke: 1.1pt + c-main)
]

#let h2(t) = block(above: 1.7em, below: 0.85em)[
  #text(font: f-head, weight: 700, size: 12pt, fill: c-main)[#t]
  #v(0.18em)
  #line(length: 34pt, stroke: 2pt + c-acc)
]

#let h3(t) = block(above: 1.4em, below: 0.6em)[
  #box(baseline: 8%, rect(width: 6pt, height: 6pt, fill: c-acc))
  #h(5pt)
  #text(font: f-head, weight: 600, size: 10pt, tracking: 0.9pt)[#upper(t)]
]

#let minihead(t) = block(above: 1.2em, below: 0.45em,
  text(font: f-head, weight: 700, size: 9.5pt, fill: rgb("#1E2124"))[#t])

#let dia-line(it, compact: false) = {
  let body = [
    #zh(it.zh) \
    #py(it.pinyin)#if it.en != "" [ #h(6pt) #text(size: 8.6pt, fill: c-grey)[— #it.en]]
  ]
  let sp = it.at("speaker", default: "")
  block(above: 0.35em, below: 0.35em,
    if sp != "" {
      grid(columns: (52pt, 1fr), column-gutter: 8pt, align: (right, left),
        text(font: f-head, weight: 700, size: 8pt, fill: c-acc.darken(18%), tracking: 0.7pt)[#upper(sp)],
        body)
    } else {
      pad(left: 10pt, body)
    }
  )
}

#let dialogue(b) = block(above: 1.2em, below: 1.2em, breakable: true,
  fill: t-panel, stroke: (left: 3.5pt + c-main), radius: (top-right: 3pt, bottom-right: 3pt),
  inset: (x: 13pt, y: 10pt), width: 100%)[
  #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 1.4pt)[DIALOGUE]
  #for it in b.items {
    if it.kind == "stage" {
      block(above: 0.7em, below: 0.3em,
        text(style: "italic", fill: c-grey, size: 8.7pt)[#rich(it.text)])
    } else {
      dia-line(it)
    }
  }
]

#let render-table(b, tight: false) = {
  let ncols = calc.max(1, b.ncols)
  let has-header = b.rows.len() > 1 and not b.rows.first().any(c => c.contains("{zh:"))
  let body-rows = if has-header { b.rows.slice(1) } else { b.rows }
  block(above: if tight { 0.7em } else { 1.1em }, below: if tight { 0.7em } else { 1.1em },
    table(
      columns: (1fr,) * ncols,
      stroke: (x, y) => if has-header and y == 0 { (bottom: 1.2pt + c-main) } else { (bottom: 0.4pt + hairline) },
      inset: (x: 8pt, y: 5pt),
      fill: (col, row) => {
        let r = if has-header { row - 1 } else { row }
        if has-header and row == 0 { white } else if calc.odd(r) { t-main } else { white }
      },
      ..if has-header {
        b.rows.first().map(c => align(left + horizon,
          text(font: f-head, weight: 700, size: 8.3pt, fill: c-main, tracking: 0.4pt)[#upper(rich(c))]))
      } else { () },
      ..body-rows.map(r => {
        let cells = r.map(c => align(left + horizon, text(size: 8.9pt)[#rich(c)]))
        while cells.len() < ncols { cells.push([]) }
        cells.slice(0, ncols)
      }).flatten()
    )
  )
}

// ---- rendu spécifique par type d'exercice ----
#let ex-instructions(b) = {
  let first = b.blocks.find(x => x.type == "para")
  if first != none { block(below: 0.5em, text(size: 8.9pt)[#rich(first.text)]) }
}

#let opt-label(l) = text(font: f-head, weight: 700, size: 8.5pt, fill: c-acc.darken(18%))[#l.]

#let render-exercise(b, fallback) = {
  let kind = b.at("ex_type", default: "")
  let d = b.at("data", default: (:))

  if kind == "matching" and "col_a" in d {
    ex-instructions(b)
    grid(columns: (1fr, 1fr), column-gutter: 10pt,
      block(fill: white.transparentize(30%), radius: 3pt, inset: 9pt, width: 100%)[
        #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 0.8pt)[COLUMN A]
        #for it in d.col_a [
          #block(above: 0.4em, below: 0em)[#opt-label(it.label) #rich(it.text)]
        ]
      ],
      block(fill: white.transparentize(30%), radius: 3pt, inset: 9pt, width: 100%)[
        #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 0.8pt)[COLUMN B]
        #for it in d.col_b [
          #block(above: 0.4em, below: 0em)[#opt-label(it.label) #rich(it.text)]
        ]
      ]
    )
  } else if kind == "mcq" and "items" in d and d.items.all(x => "options" in x) {
    ex-instructions(b)
    for (i, it) in d.items.enumerate() {
      block(above: 0.7em, below: 0.25em)[
        #text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#str(i + 1).] #rich(it.prompt)
      ]
      let long = it.options.any(o => o.text.len() > 34)
      pad(left: 14pt,
        if long or it.options.len() > 2 {
          stack(spacing: 4pt, ..it.options.map(o => [#opt-label(o.label) #rich(o.text)]))
        } else {
          grid(columns: (1fr, 1fr), column-gutter: 10pt,
            ..it.options.map(o => [#opt-label(o.label) #rich(o.text)]))
        }
      )
    }
  } else if kind == "fill_blank" and "items" in d and d.items.len() > 0 {
    ex-instructions(b)
    if d.at("bank", default: ()).len() > 0 {
      block(above: 0.4em, below: 0.6em, fill: white.transparentize(30%), radius: 3pt,
        inset: (x: 9pt, y: 6pt), width: 100%)[
        #text(font: f-head, weight: 700, size: 7.5pt, fill: c-main, tracking: 0.8pt)[WORD BANK]
        #h(6pt)
        #d.bank.map(w => rich(w)).join(text(fill: c-grey)[  ·  ])
      ]
    }
    for (i, it) in d.items.enumerate() {
      block(above: 0.45em, below: 0em)[
        #text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#str(i + 1).] #rich(it.prompt)
        #if it.at("en", default: "") != "" [ #text(size: 8.4pt, fill: c-grey)[ (#it.en)]]
      ]
    }
  } else if kind == "true_false" and "items" in d and d.items.all(x => "statement" in x) {
    ex-instructions(b)
    for (i, it) in d.items.enumerate() {
      block(above: 0.5em, below: 0em)[
        #text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#str(i + 1).]
        #if it.at("context", default: "") != "" [#rich(it.context) \ #h(12pt)]
        #rich(it.statement)
        #h(6pt) #text(fill: c-grey, size: 8.5pt)[T / F]
      ]
    }
  } else if "items" in d and d.items.len() > 0 and d.items.all(x => "prompt" in x) {
    ex-instructions(b)
    for (i, it) in d.items.enumerate() {
      block(above: 0.45em, below: 0em)[
        #text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#str(i + 1).] #rich(it.prompt)
      ]
    }
  } else {
    fallback(b.blocks, tight: true)
  }
}

#let render-blocks(blocks, tight: false) = {
  for b in blocks {
    if b.type == "para" { par(rich(b.text)) }
    else if b.type == "h2" { h2(rich(b.text)) }
    else if b.type == "h3" { h3(rich(b.text)) }
    else if b.type == "minihead" { minihead(rich(b.text)) }
    else if b.type == "table" { render-table(b, tight: tight) }
    else if b.type == "dialogue" { dialogue(b) }
    else if b.type == "dia_line" { dia-line(b) }
    else if b.type == "exercise" {
      block(above: 1.3em, below: 1.3em, breakable: true,
        fill: t-acc, radius: 5pt, width: 100%, inset: (x: 13pt, y: 11pt),
        stroke: 0.6pt + c-acc.lighten(35%))[
        #box(fill: c-acc, radius: 20pt, inset: (x: 9pt, y: 3.5pt),
          text(font: f-head, weight: 700, size: 8pt, fill: white, tracking: 0.6pt)[✎ EXERCISE #str(b.num)])
        #h(7pt)
        #text(font: f-head, weight: 700, size: 10.5pt, fill: c-main)[#b.title]
        #v(0.35em)
        #render-exercise(b, render-blocks)
      ]
    }
  }
}

// ============================================================
// FRONT MATTER
// ============================================================
// page 1 : blanche (brief)
#pagebreak()
// page 2 : titre
#v(2.2in)
#align(center)[
  #text(font: f-head, weight: 800, size: 34pt, fill: c-main, tracking: 1pt)[LEARN\ CHINESE]
  #v(0.25in)
  #text(font: f-head, weight: 600, size: 14pt, fill: c-acc.darken(12%), tracking: 3pt)[FOR ADULT BEGINNERS]
]
#pagebreak()
// TOC
#text(font: f-head, weight: 800, size: 18pt, fill: c-main)[TABLE OF CONTENTS]
#v(0.6em)
#show outline.entry.where(level: 1): it => block(above: 1em, below: 0.2em,
  text(font: f-head, weight: 700, size: 9pt, fill: c-main, it.indented(none, it.inner())))
#show outline.entry.where(level: 2): it => block(above: 0.35em, below: 0em,
  text(size: 8.8pt, it.indented(none, it.inner())))
#outline(title: none, depth: 2)

// ============================================================
// CORPS — headers/footers actifs
// ============================================================
#set page(
  header-ascent: 45%,
  header: [
    #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 1.1pt)[#meta.book_title]
    #h(6pt)
    #text(font: f-head, weight: 500, size: 8pt, fill: c-grey, tracking: 1.1pt)[#meta.book_subtitle]
    #v(-0.5em)
    #line(length: 100%, stroke: 0.5pt + hairline)
  ],
  footer: [
    #line(length: 100%, stroke: 0.5pt + hairline)
    #v(-0.45em)
    #grid(columns: (1fr, auto), align: (left, right),
      text(font: f-head, weight: 500, size: 7.5pt, fill: c-grey, tracking: 0.6pt)[#context upper(footer-label.get())],
      text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#context counter(page).display()]
    )
  ],
)

#let after-section = state("after-section", false)

#for ch in data.chapters {
  if ch.kind == "section" {
    pagebreak(weak: true)
    footer-label.update("Section " + str(ch.num) + ": " + ch.title)
    heading(level: 1)[SECTION #str(ch.num): #upper(ch.title)]
    section-opener(ch)
    after-section.update(true)
  } else {
    context {
      if not after-section.get() { pagebreak(weak: true) }
    }
    after-section.update(false)
    if ch.kind == "intro" {
      footer-label.update("Introduction")
      heading(level: 1)[INTRODUCTION]
      chapter-title(none, "Introduction")
    } else if ch.kind == "conclusion" {
      footer-label.update("Conclusion")
      heading(level: 1)[CONCLUSION]
      chapter-title(none, "Conclusion")
    } else if ch.kind == "answers" {
      footer-label.update("Answer Keys")
      heading(level: 1)[ANSWER KEYS]
      chapter-title(none, "Answer Keys")
      // générée depuis les exercices : les titres ne peuvent pas diverger
      let cur-section = ""
      for L in akey {
        let sec = if L.section == none { "" } else { "SECTION " + str(L.section.num) + ": " + L.section.title }
        if sec != cur-section {
          cur-section = sec
          block(above: 1.2em, below: 0.4em)[
            #text(font: f-head, weight: 700, size: 9pt, fill: c-acc.darken(20%), tracking: 1.2pt)[#upper(sec)]
            #v(-0.35em)
            #line(length: 100%, stroke: 0.6pt + c-acc)
          ]
        }
        block(above: 0.7em, below: 0.2em,
          text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#upper(L.lesson)])
        for ex in L.exercises {
          block(above: 0.25em, below: 0em, pad(left: 8pt)[
            #text(font: f-head, weight: 600, size: 8pt, fill: c-grey)[EX #str(ex.num) · #ex.title —]
            #h(3pt)
            #ex.answers.enumerate().map(((i, a)) => [#text(weight: 600)[#str(i + 1).] #rich(a)]).join(text(fill: c-grey)[  ·  ])
          ])
        }
      }
      continue
    } else if ch.kind == "story" {
      heading(level: 2)[STORY #str(ch.num): #upper(ch.title)]
      chapter-title(none, ch.title, eyebrow: "Story " + str(ch.num))
    } else {
      heading(level: 2)[#upper(ch.title)]
      chapter-title(ch.num, ch.title)
    }
    render-blocks(ch.blocks)
  }
}

// page blanche finale si nombre de pages impair (brief)
#metadata(none) <book-end>
#context {
  let n = counter(page).at(<book-end>).first()
  if calc.odd(n) { pagebreak() }
}
