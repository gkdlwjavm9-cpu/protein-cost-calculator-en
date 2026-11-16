# -*- coding: utf-8 -*-
"""
Runs the pure calculation logic inside index.html with quickjs (no browser needed).

    python3 tests/test_tool.py
"""
import json
import os
import re
import sys

import quickjs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(HERE, "index.html")


def load_logic():
    src = open(HTML, encoding="utf-8").read()
    m = re.search(r"/\* PURE_LOGIC_START \*/(.*?)/\* PURE_LOGIC_END \*/", src, re.S)
    if not m:
        raise SystemExit("PURE_LOGIC block not found")
    ctx = quickjs.Context()
    ctx.eval(m.group(1))
    return ctx


def js(ctx, expr):
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


failures = []


def check(label, got, want, tol=1e-6):
    if isinstance(want, float) and isinstance(got, (int, float)):
        ok = abs(got - want) <= tol * max(1.0, abs(want))
    else:
        ok = got == want
    print(f"{'OK ' if ok else 'BAD'}  {label:<52} got={got!r}  want={want!r}")
    if not ok:
        failures.append(label)


def near(label, got, want, tol=1e-6):
    check(label, round(float(got), 6) if got is not None else None,
          round(float(want), 6), tol)


def main():
    ctx = load_logic()

    # 1. Number parsing
    check("toNumber('4.99')", js(ctx, "toNumber('4.99')"), 4.99)
    check("toNumber('$4.99')", js(ctx, "toNumber('$4.99')"), 4.99)
    check("toNumber('1,299')", js(ctx, "toNumber('1,299')"), 1299)
    check("toNumber(' 24 g ')", js(ctx, "toNumber(' 24 g ')"), 24)
    check("toNumber('') is NaN", js(ctx, "String(toNumber(''))"), "NaN")
    check("toNumber('abc') is NaN", js(ctx, "String(toNumber('abc'))"), "NaN")

    # 2. Unit conversion (1 lb = 453.59237 g, 1 oz = 28.349523125 g)
    near("toGrams(1,'lb')", js(ctx, "toGrams(1,'lb')"), 453.59237)
    near("toGrams(16,'oz')", js(ctx, "toGrams(16,'oz')"), 453.59237)
    near("toGrams(500,'g')", js(ctx, "toGrams(500,'g')"), 500)
    check("toGrams(0,'g') is NaN", js(ctx, "String(toGrams(0,'g'))"), "NaN")
    check("toGrams(-1,'lb') is NaN", js(ctx, "String(toGrams(-1,'lb'))"), "NaN")
    check("toGrams(1,'stone') is NaN", js(ctx, "String(toGrams(1,'stone'))"), "NaN")

    # 3. Protein basis: label per 100 g vs label per serving
    check("proteinPer100g basis 100g",
          js(ctx, "proteinPer100g({protein:23, basis:'100g'})"), 23)
    near("proteinPer100g basis serving (24 g / 113 g)",
         js(ctx, "proteinPer100g({protein:24, basis:'serving', servingSize:113})"), 24 / 113 * 100)
    check("proteinPer100g serving without servingSize is NaN",
          js(ctx, "String(proteinPer100g({protein:24, basis:'serving'}))"), "NaN")

    # 4. Core row: chicken breast $4.99 / 1 lb / 23 g protein per 100 g / 120 kcal
    row = js(ctx, "calcRow({name:'Chicken breast', price:4.99, size:1, unit:'lb', protein:23, kcal:120, basis:'100g'}, 150)")
    near("grams in 1 lb", row["grams"], 453.59237)
    near("cost per 100 g", row["costPer100g"], 4.99 / 453.59237 * 100)
    near("cost per g protein", row["costPerGProtein"], 4.99 / (453.59237 * 0.23))
    near("protein per $1", row["proteinPerDollar"], 453.59237 * 0.23 / 4.99)
    near("protein calorie share", row["proteinShare"], 23 * 4 / 120)
    near("grams needed for 150 g target", row["gramsForTarget"], 150 * 100 / 23)
    near("cost to hit 150 g", row["costToTarget"], 150 * 100 / 23 * 4.99 / 453.59237)
    near("kcal to hit 150 g", row["kcalForTarget"], 150 * 100 / 23 * 120 / 100)

    # 4b. Same food described per serving must give the same $/g protein
    a = js(ctx, "calcRow({name:'A', price:5.99, size:32, unit:'oz', protein:20, basis:'100g'}, 150)")
    b = js(ctx, "calcRow({name:'B', price:5.99, size:32, unit:'oz', protein:22.4, servingSize:112, basis:'serving'}, 150)")
    near("per-100g and per-serving agree", b["costPerGProtein"], a["costPerGProtein"], 1e-6)

    # 5. Missing data degrades gracefully
    z = js(ctx, "calcRow({name:'Olive oil', price:9.99, size:16, unit:'oz', protein:0, kcal:884, basis:'100g'}, 150)")
    check("protein 0 -> costPerGProtein null", z["costPerGProtein"], None)
    near("protein 0 still gives cost per 100 g", z["costPer100g"], 9.99 / 453.59237 * 100)
    bad = js(ctx, "calcRow({name:'x', price:10, size:0, unit:'g', protein:10, basis:'100g'}, 150)")
    check("size 0 -> costPer100g null", bad["costPer100g"], None)
    r0 = js(ctx, "calcRow({name:'Tofu', price:2.49, size:14, unit:'oz', protein:11, basis:'100g'}, 0)")
    check("target 0 -> costToTarget null", r0["costToTarget"], None)
    nk = js(ctx, "calcRow({name:'Tofu', price:2.49, size:14, unit:'oz', protein:11, basis:'100g'}, 150)")
    check("no kcal -> proteinShare null", nk["proteinShare"], None)

    # 6. Price column units are the same ranking, scaled
    c1 = js(ctx, "costPerUnit(calcRow({name:'c', price:4.99, size:1, unit:'lb', protein:23, basis:'100g'}, 150), '100g')")
    c2 = js(ctx, "costPerUnit(calcRow({name:'c', price:4.99, size:1, unit:'lb', protein:23, basis:'100g'}, 150), 'lb')")
    c3 = js(ctx, "costPerUnit(calcRow({name:'c', price:4.99, size:1, unit:'lb', protein:23, basis:'100g'}, 150), 'oz')")
    near("cost per lb of a $4.99/lb item", c2, 4.99)
    near("cost per oz = per lb / 16", c3, 4.99 / 16, 1e-5)
    near("per 100 g relation", c1, 4.99 / 4.5359237, 1e-6)
    check("costPerUnit with bad unit is null",
          js(ctx, "String(costPerUnit(calcRow({name:'c', price:4.99, size:1, unit:'lb', protein:23, basis:'100g'}, 150), 'stone'))"), "null")

    # 7. Ranking: ascending, uncomputable rows last
    order = js(ctx, """rankRows([
        {name:'Pricey', price:9, size:100, unit:'g', protein:10, basis:'100g'},
        {name:'NoProtein', price:1, size:100, unit:'g', protein:0, basis:'100g'},
        {name:'Cheap', price:1, size:100, unit:'g', protein:20, basis:'100g'}
      ], 150).map(r => r.name)""")
    check("ascending by $/g protein, nulls last", order, ["Cheap", "Pricey", "NoProtein"])
    desc = js(ctx, """rankRows([
        {name:'Pricey', price:9, size:100, unit:'g', protein:10, basis:'100g'},
        {name:'Cheap', price:1, size:100, unit:'g', protein:20, basis:'100g'}
      ], 150, 'costPerGProtein', 'desc').map(r => r.name)""")
    check("descending order", desc, ["Pricey", "Cheap"])
    sizeSort = js(ctx, """rankRows([
        {name:'A', price:1, size:100, unit:'g', protein:20, basis:'100g'},
        {name:'B', price:1, size:2, unit:'lb', protein:20, basis:'100g'}
      ], 150, 'price', 'desc').map(r => r.name)""")
    check("equal prices keep a stable label order", sizeSort, ["A", "B"])

    # 8. Presets: 26 items, every one computable, cheapest is dry lentils
    preset = js(ctx, "PRESETS.map(p => calcRow(p, 150))")
    check("preset count", len(preset), 26)
    check("every preset has cost per 100 g", all(r["costPer100g"] is not None for r in preset), True)
    check("every preset has cost per g protein", all(r["costPerGProtein"] is not None for r in preset), True)
    check("preset names are unique", len({r["name"] for r in preset}), 26)
    s = js(ctx, "summary(PRESETS, 150)")
    check("cheapest preset", s["cheapest"]["name"], "Lentils, dry")
    near("cheapest $/g protein", s["cheapest"]["costPerGProtein"], 2.29 / (453.59237 * 0.25))
    check("priciest preset", s["priciest"]["name"], "Broccoli, frozen 12 oz")
    near("spread", s["spread"], (2.29 / (340.194 * 0.028)) / (2.29 / (453.59237 * 0.25)), 1e-3)
    near("daily cost at 150 g on the cheapest", s["dailyCost"], 150 * 2.29 / (453.59237 * 0.25))
    near("weekly cost = 7 days", s["weeklyCost"], s["dailyCost"] * 7)
    near("monthly cost = 30 days", s["monthlyCost"], s["dailyCost"] * 30)
    # Independent sanity check of one preset end to end: eggs, dozen, $3.29 / 600 g / 13 g protein
    eggs = [r for r in preset if r["name"].startswith("Eggs")][0]
    near("eggs $/g protein", eggs["costPerGProtein"], 3.29 / (600 * 0.13))
    near("eggs cost for 150 g target", eggs["costToTarget"], 150 / 0.13 * 3.29 / 600)

    # 9. Target suggestion from bodyweight
    t = js(ctx, "suggestTarget(180, 'lb', 'active')")
    near("180 lb in kg", t["kg"], 180 / 2.2046226218, 1e-6)
    check("180 lb active low", t["low"], round(180 / 2.2046226218 * 1.4))
    check("180 lb active high", t["high"], round(180 / 2.2046226218 * 1.8))
    tkg = js(ctx, "suggestTarget(80, 'kg', 'build')")
    check("80 kg building low", tkg["low"], 144)
    check("80 kg building high", tkg["high"], 176)
    tcut = js(ctx, "suggestTarget(80, 'kg', 'cut')")
    check("cutting is higher than general health", tcut["low"] > js(ctx, "suggestTarget(80,'kg','light')")["high"], True)
    check("no weight -> null", js(ctx, "String(suggestTarget('', 'lb', 'active'))"), "null")
    check("zero weight -> null", js(ctx, "String(suggestTarget(0, 'lb', 'active'))"), "null")
    check("unknown level falls back", js(ctx, "suggestTarget(80, 'kg', 'nope')")["low"], 112)

    # 10. Formatting
    check("formatUSD(0.04782)", js(ctx, "formatUSD(0.04782)"), "$0.048")
    check("formatUSD(4.99)", js(ctx, "formatUSD(4.99)"), "$4.99")
    check("formatUSD(54.99)", js(ctx, "formatUSD(54.99)"), "$54.99")
    check("formatUSD(null)", js(ctx, "formatUSD(null)"), "—")
    check("formatCents(0.04782)", js(ctx, "formatCents(0.04782)"), "4.78¢")
    check("formatCents(0.2134)", js(ctx, "formatCents(0.2134)"), "21.3¢")
    check("formatPct(0.7667)", js(ctx, "formatPct(0.7667)"), "77%")
    check("formatNum(1234567, 1)", js(ctx, "formatNum(1234567, 1)"), "1,234,567.0")
    check("formatGrams(20.907)", js(ctx, "formatGrams(20.907)"), "20.9 g")
    check("formatGrams(652.17)", js(ctx, "formatGrams(652.17)"), "652 g")
    check("formatSize(453.59237)", js(ctx, "formatSize(453.59237)"), "1.00 lb")
    check("formatSize(113.398)", js(ctx, "formatSize(113.398)"), "4.00 oz")
    check("formatSize(20)", js(ctx, "formatSize(20)"), "20 g")

    # 11. TSV copy
    tsv = ctx.eval("toTSV(rankRows([{name:'Chicken breast', price:4.99, size:1, unit:'lb', protein:23, kcal:120, basis:'100g'}], 150))")
    lines = tsv.split("\n")
    check("TSV header first cell", lines[0].split("\t")[0], "Food")
    check("TSV header unit label", lines[0].split("\t")[3], "Cost /100 g")
    check("TSV cost per g protein", lines[1].split("\t")[4], "0.048")
    check("TSV cost for target", lines[1].split("\t")[7], "7.17")
    tsv_lb = ctx.eval("toTSV(rankRows([{name:'Chicken breast', price:4.99, size:1, unit:'lb', protein:23, kcal:120, basis:'100g'}], 150), 'lb')")
    check("TSV per-lb header", tsv_lb.split("\n")[0].split("\t")[3], "Cost /lb")
    check("TSV per-lb value", tsv_lb.split("\n")[1].split("\t")[3], "4.99")

    # 12. Empty state
    empty = js(ctx, "summary([], 150)")
    check("empty summary count", empty["count"], 0)
    check("empty summary cheapest", empty["cheapest"], None)

    print("\n" + ("All checks passed" if not failures else f"{len(failures)} failed: {failures}"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
