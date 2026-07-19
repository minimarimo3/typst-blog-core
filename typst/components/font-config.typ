#let google-font-families(fonts) = {
  fonts.pairs()
    .filter(pair => {
      let entry = pair.at(1)
      let weights = entry.at("weights", default: none)
      entry.at("web", default: none) != none and weights != none
    })
    .map(pair => {
      let entry = pair.at(1)
      entry.web.map(family => family.replace(" ", "+") + ":wght@" + entry.weights)
    })
    .flatten()
}

#let font-css-lines(fonts) = {
  fonts.pairs()
    .filter(pair => pair.at(1).at("web", default: none) != none)
    .map(pair => {
      let key = pair.at(0)
      let entry = pair.at(1)
      let fallback = entry.at("fallback", default: "serif")
      let families = entry.web.map(family => "\"" + family + "\"").join(", ")
      let value = if fallback != none {
        families + ", " + fallback
      } else {
        families
      }
      "  --font-" + key + ": " + value + ";"
    })
}
