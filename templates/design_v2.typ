// ============================================================
// Speak Abroad Academy — DESIGN V2 (brief CN10)
// Départ volontaire de l'ancienne charte teal/rose.
// Palette : pine (main) / amber (accent) / grey (tertiaire)
// Typo : Archivo (titres) + Source Serif 4 (corps) + Noto Sans SC
// ============================================================

#let data = json("content/chapter1_v2.json")
#let meta = data.meta

// ---- Palette (3 couleurs, cf. brief) ----
#let c-main  = rgb("#1A5E52")   // pine profond — titres, structure
#let c-acc   = rgb("#E5A33C")   // amber — accents, exercices
#let c-grey  = rgb("#5A6068")   // gris — texte secondaire
// tints dérivées (pas des couleurs supplémentaires)
#let t-main  = rgb("#EAF1EF")   // lignes alternées tableaux
#let t-acc   = rgb("#FBF3E2")   // fond boîtes exercices
#let t-panel = rgb("#F3F6F5")   // panneau dialogue
#let hairline = rgb("#D8DCDA")

#let f-head = "Archivo"
#let f-body = "Source Serif 4"
#let f-zh   = "Noto Sans SC"

// ---- Page : 6×9", marges miroir avec gutter ----
#set page(
  width: 6in, height: 9in,
  margin: (inside: 0.8in, outside: 0.58in, top: 0.92in, bottom: 0.78in),
  binding: left,
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
      text(font: f-head, weight: 500, size: 7.5pt, fill: c-grey, tracking: 0.6pt)[#upper(meta.footer_label)],
      text(font: f-head, weight: 700, size: 9pt, fill: c-main)[#context counter(page).display()]
    )
  ],
)
#counter(page).update(meta.page_start)

#set text(font: f-body, size: 9.3pt, fill: rgb("#1E2124"), lang: "en")
#set par(justify: true, leading: 0.62em, spacing: 0.85em)
#set strong(delta: 200)

// ---- Helpers ----
#let zh(s) = text(font: f-zh, size: 9.2pt)[#s]
#let py(s) = text(font: f-body, style: "italic", fill: c-grey, size: 8.2pt)[#s]

#let rich(s) = {
  let parts = ()
  let rest = s
  while rest.len() > 0 {
    let m = rest.match(regex("\\{(zh|py):([^}]*)\\}|\\*\\*([^*]+)\\*\\*|\\*([^*]+)\\*"))
    if m == none { parts.push(rest); break }
    if m.start > 0 { parts.push(rest.slice(0, m.start)) }
    if m.captures.at(0) == "zh" { parts.push(zh(m.captures.at(1))) }
    else if m.captures.at(0) == "py" { parts.push(py(m.captures.at(1))) }
    else if m.captures.at(2) != none { parts.push(strong(m.captures.at(2))) }
    else { parts.push(emph(m.captures.at(3))) }
    rest = rest.slice(m.end)
  }
  parts.join()
}

// ---- H1 : ouverture de section (page dédiée, badge) ----
#let section-opener(b) = block(above: 0em, below: 1.6em,
  grid(columns: (5pt, 1fr), column-gutter: 14pt, align: (top, top),
    rect(width: 5pt, height: 48pt, fill: c-acc),
    stack(spacing: 6pt,
      text(font: f-head, weight: 600, size: 9.5pt, fill: c-grey, tracking: 2.2pt)[SECTION #str(b.num)],
      par(justify: false, leading: 0.45em)[#text(font: f-head, weight: 800, size: 18pt, fill: c-main, tracking: 0.3pt)[#upper(b.title)]]
    )
  )
)

// ---- H1bis : titre de chapitre (badge numéroté + caps) ----
#let chapter-title(b) = block(above: 0em, below: 1.3em)[
  #grid(columns: (auto, 1fr), column-gutter: 12pt, align: (top, top),
    rect(width: 34pt, height: 34pt, fill: c-main, radius: 4pt,
      align(center + horizon, text(font: f-head, weight: 800, size: 19pt, fill: white)[#b.num])),
    [
      #text(font: f-head, weight: 800, size: 16.5pt, fill: c-main)[#upper(b.title)]
    ]
  )
  #v(0.4em)
  #line(length: 100%, stroke: 1.1pt + c-main)
]

// ---- H2 : leçon — Title Case, medium, rule amber courte ----
#let h2(t) = block(above: 1.7em, below: 0.85em)[
  #text(font: f-head, weight: 700, size: 12.5pt, fill: c-main)[#t]
  #v(0.18em)
  #line(length: 34pt, stroke: 2pt + c-acc)
]

// ---- H3 : sous-section — small caps, marqueur carré ----
#let h3(t) = block(above: 1.4em, below: 0.6em)[
  #box(baseline: 8%, rect(width: 6pt, height: 6pt, fill: c-acc))
  #h(5pt)
  #text(font: f-head, weight: 600, size: 10.5pt, fill: rgb("#1E2124"), tracking: 0.9pt)[#upper(t)]
]

// ---- Dialogue : panneau ombré + barre verticale + speakers ----
#let dialogue(b) = block(above: 1.2em, below: 1.2em, breakable: true,
  fill: t-panel, stroke: (left: 3.5pt + c-main), radius: (top-right: 3pt, bottom-right: 3pt),
  inset: (x: 13pt, y: 10pt), width: 100%)[
  #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 1.4pt)[DIALOGUE]
  #for it in b.items {
    if it.kind == "stage" {
      block(above: 0.7em, below: 0.3em,
        text(style: "italic", fill: c-grey, size: 8.7pt)[#it.text])
    } else {
      block(above: 0.3em, below: 0.3em,
        grid(columns: (52pt, 1fr), column-gutter: 8pt, align: (right, left),
          text(font: f-head, weight: 700, size: 8pt, fill: c-acc.darken(18%), tracking: 0.7pt)[#upper(it.speaker)],
          [
            #zh(it.zh) \
            #py(it.pinyin) #h(6pt) #text(size: 8.6pt, fill: c-grey)[— #it.en]
          ]
        )
      )
    }
  }
]

// ---- Tableaux : sans bordures, header à filet, lignes alternées ----
#let vocab-table(b) = block(above: 1.1em, below: 1.1em,
  table(
    columns: (1.2fr, 1fr),
    stroke: (x, y) => if y == 0 { (bottom: 1.2pt + c-main) } else { (bottom: 0.4pt + hairline) },
    inset: (x: 9pt, y: 5.5pt),
    fill: (col, row) => if row == 0 { white } else if calc.even(row) { t-main } else { white },
    table.header(
      align(left, text(font: f-head, weight: 700, size: 8.5pt, fill: c-main, tracking: 0.5pt)[#upper(b.header_left)]),
      align(left, text(font: f-head, weight: 700, size: 8.5pt, fill: c-main, tracking: 0.5pt)[#upper(b.header_right)])
    ),
    ..b.rows.map(r => (
      align(left)[#zh(r.zh) #h(3pt) #py(r.pinyin)],
      align(left + horizon)[#text(size: 9pt)[#r.en]]
    )).flatten()
  )
)

// ---- Exercices : boîte teintée, label-pill, cf. brief §2 ----
#let ex-label(num, title) = [
  #box(fill: c-acc, radius: 20pt, inset: (x: 9pt, y: 3.5pt),
    text(font: f-head, weight: 700, size: 8.5pt, fill: white, tracking: 0.6pt)[✎ EXERCISE #num])
  #h(7pt)
  #text(font: f-head, weight: 700, size: 11pt, fill: c-main)[#title]
]

#let exercise-matching(b) = block(above: 1.4em, below: 1.4em,
  rect(fill: t-acc, radius: 5pt, width: 100%, inset: (x: 13pt, y: 12pt), stroke: 0.6pt + c-acc.lighten(35%))[
    #ex-label(b.num, b.title)
    #v(0.5em)
    #text(size: 8.9pt)[#b.instructions]
    #v(0.5em)
    #grid(columns: (1fr, 1fr), column-gutter: 10pt,
      rect(fill: white.transparentize(30%), radius: 3pt, inset: 9pt, width: 100%)[
        #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 0.8pt)[COLUMN A]
        #v(0.25em)
        #for (i, it) in b.col_a.enumerate() [
          #block(above: 0.4em, below: 0em)[#text(font: f-head, weight: 700, size: 8.5pt, fill: c-acc.darken(18%))[#(i + 1).] #zh(it.zh) #py(it.pinyin)]
        ]
      ],
      rect(fill: white.transparentize(30%), radius: 3pt, inset: 9pt, width: 100%)[
        #text(font: f-head, weight: 700, size: 8pt, fill: c-main, tracking: 0.8pt)[COLUMN B]
        #v(0.25em)
        #for (i, it) in b.col_b.enumerate() [
          #block(above: 0.4em, below: 0em)[#text(font: f-head, weight: 700, size: 8.5pt, fill: c-acc.darken(18%))[#("ABCDE".at(i)).] #text(size: 9pt)[#it]]
        ]
      ]
    )
  ]
)

// ---- Rendu ----
#for b in data.blocks {
  if b.type == "section_opener" { section-opener(b) }
  else if b.type == "chapter" { chapter-title(b) }
  else if b.type == "h2" { h2(rich(b.text)) }
  else if b.type == "h3" { h3(b.text) }
  else if b.type == "para" { par(rich(b.text)) }
  else if b.type == "vocab_table" { vocab-table(b) }
  else if b.type == "dialogue" { dialogue(b) }
  else if b.type == "exercise_matching" { exercise-matching(b) }
}
