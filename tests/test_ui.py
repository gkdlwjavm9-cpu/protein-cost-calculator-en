# -*- coding: utf-8 -*-
"""
Runs the WHOLE inline <script> of index.html (logic + UI wiring) in quickjs
against a minimal DOM stub, so the page's behaviour is checked without a browser.

    python3 tests/test_ui.py

Covers: first paint, preset load, sorting, add/remove, target changes, unit
toggle, bodyweight suggester, localStorage round trip, CTA wiring, clear all.
"""
import json
import os
import re
import sys

import quickjs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(HERE, "index.html")

PRELUDE = r"""
var __els = {};
var __thEls = [];
var __store = {};

function El(sel){
  this.sel = sel; this._html = ""; this.textContent = ""; this.value = "";
  this.hidden = false; this.style = {}; this.children = []; this.attrs = {};
  this.handlers = {}; this.className = "";
  this.classList = {
    _s: {},
    add: function(c){ this._s[c] = 1; },
    remove: function(c){ delete this._s[c]; },
    contains: function(c){ return !!this._s[c]; }
  };
}
Object.defineProperty(El.prototype, "innerHTML", {
  get: function(){ return this._html; },
  set: function(v){ this._html = String(v); this.children = []; }
});
El.prototype.addEventListener = function(t, f){
  if (!this.handlers[t]) this.handlers[t] = [];
  this.handlers[t].push(f);
};
El.prototype.fire = function(t, ev){
  var list = this.handlers[t] || [];
  for (var i = 0; i < list.length; i++) list[i].call(this, ev || {preventDefault: function(){}});
  return list.length;
};
El.prototype.appendChild = function(c){ this.children.push(c); return c; };
El.prototype.querySelectorAll = function(){ return []; };
El.prototype.querySelector = function(s){ return new El(s); };
El.prototype.setAttribute = function(k, v){ this.attrs[k] = v; if (k === "data-del") this.isDel = true; };
El.prototype.getAttribute = function(k){ return this.attrs[k]; };
El.prototype.focus = function(){ this.focused = true; };
El.prototype.reset = function(){ this.resetCalled = true; };
El.prototype.select = function(){};

var document = {
  querySelector: function(sel){
    if (!__els[sel]) __els[sel] = new El(sel);
    return __els[sel];
  },
  createElement: function(tag){ var e = new El("<" + tag + ">"); e.tagName = tag; return e; },
  querySelectorAll: function(sel){
    if (sel === "th[data-sort]") return __thEls;
    return [];
  },
  body: new El("body"),
  execCommand: function(){ return true; }
};

var navigator = {};
var localStorage = {
  getItem: function(k){ return Object.prototype.hasOwnProperty.call(__store, k) ? __store[k] : null; },
  setItem: function(k, v){ __store[k] = String(v); },
  removeItem: function(k){ delete __store[k]; }
};
var __timers = [];
function setTimeout(fn, ms){ __timers.push(fn); return __timers.length; }
function clearTimeout(){}
function confirm(){ return true; }
"""


def build_ctx():
    src = open(HTML, encoding="utf-8").read()
    m = re.search(r"<script>(.*?)</script>", src, re.S)
    if not m:
        raise SystemExit("inline script not found")
    ctx = quickjs.Context()
    ctx.eval(PRELUDE)
    # register the sortable headers the way the markup declares them
    ctx.eval("""
      ['name','price','grams','costPerDisplay','costPerGProtein','proteinPerDollar','proteinShare','costToTarget']
        .forEach(function(k){
          var th = new El('th');
          th.setAttribute('data-sort', k);
          __thEls.push(th);
        });
    """)
    ctx.eval(m.group(1))
    return ctx


def js(ctx, expr):
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


failures = []


def check(label, got, want):
    ok = got == want
    print(f"{'OK ' if ok else 'BAD'}  {label:<56} got={got!r}  want={want!r}")
    if not ok:
        failures.append(label)


def contains(label, haystack, needle):
    ok = needle in (haystack or "")
    print(f"{'OK ' if ok else 'BAD'}  {label:<56} {'contains' if ok else 'MISSING'} {needle!r}")
    if not ok:
        failures.append(label)


def first_row(ctx):
    return ctx.eval("document.querySelector('#tbody').children[0].innerHTML")


def main():
    ctx = build_ctx()
    src = open(HTML, encoding="utf-8").read()

    # --- first paint: empty state, no crash ---
    check("boots with 0 rows", js(ctx, "document.querySelector('#tbody').children.length"), 0)
    check("empty message visible", js(ctx, "document.querySelector('#empty').style.display"), "block")
    check("empty stats shown", "0" in ctx.eval("document.querySelector('#stats').innerHTML"), True)
    check("target input shows default", js(ctx, "document.querySelector('#f-target').value"), 150)

    # --- preset load ---
    check("preset button bound", js(ctx, "document.querySelector('#load-preset').handlers.click.length"), 1)
    ctx.eval("document.querySelector('#load-preset').fire('click')")
    check("26 presets in table", js(ctx, "document.querySelector('#tbody').children.length"), 26)
    check("empty message hidden", js(ctx, "document.querySelector('#empty').style.display"), "none")
    check("state holds 26 items", js(ctx, "state.items.length"), 26)
    check("saved to localStorage", js(ctx, "JSON.parse(localStorage.getItem('protein-cost-calc-en-v1')).items.length"), 26)
    contains("cheapest row is lentils first", first_row(ctx), "Lentils")
    contains("best pill on the cheapest row", first_row(ctx), 'class="pill">best')
    contains("stats name the cheapest", ctx.eval("document.querySelector('#stats').innerHTML"), "Lentils, dry")
    contains("stats show daily cost", ctx.eval("document.querySelector('#stats').innerHTML"), "/ day")
    ctx.eval("document.querySelector('#load-preset').fire('click')")
    check("second preset load adds nothing", js(ctx, "state.items.length"), 26)
    contains("second load explained", ctx.eval("document.querySelector('#toast').textContent"), "already in the list")

    # --- sorting ---
    ctx.eval("__thEls[1].fire('click')")           # price
    check("sort key became price", js(ctx, "state.sortKey"), "price")
    check("price sorts descending first", js(ctx, "state.dir"), "desc")
    contains("most expensive first", first_row(ctx), "Whey protein powder")
    ctx.eval("__thEls[1].fire('click')")
    check("clicking again flips direction", js(ctx, "state.dir"), "asc")
    contains("cheapest price first", first_row(ctx), "Black beans")
    ctx.eval("__thEls[4].fire('click')")           # cost per g protein
    check("protein cost sorts ascending", js(ctx, "state.dir"), "asc")
    contains("lentils back on top", first_row(ctx), "Lentils")
    ctx.eval("__thEls[0].fire('click')")           # name
    check("name sort bound", js(ctx, "state.sortKey"), "name")

    # --- add a food through the form ---
    ctx.eval("""
      document.querySelector('#f-name').value = 'Cottage cheese, test';
      document.querySelector('#f-price').value = '5.49';
      document.querySelector('#f-size').value = '24';
      document.querySelector('#f-size-unit').value = 'oz';
      document.querySelector('#f-protein').value = '11';
      document.querySelector('#f-protein-basis').value = '100g';
      document.querySelector('#f-kcal').value = '81';
      document.querySelector('#add-form').fire('submit');
    """)
    check("form added one item", js(ctx, "state.items.length"), 27)
    check("table re-rendered", js(ctx, "document.querySelector('#tbody').children.length"), 27)
    check("form reset after add", js(ctx, "document.querySelector('#add-form').resetCalled"), True)
    check("toast shown", js(ctx, "document.querySelector('#toast').textContent"), "Cottage cheese, test added")
    check("new item saved", js(ctx, "JSON.parse(localStorage.getItem('protein-cost-calc-en-v1')).items.length"), 27)

    # invalid input is rejected without adding
    ctx.eval("""
      document.querySelector('#f-name').value = '';
      document.querySelector('#f-price').value = '4.99';
      document.querySelector('#f-size').value = '1';
      document.querySelector('#f-size-unit').value = 'lb';
      document.querySelector('#f-protein').value = '20';
      document.querySelector('#add-form').fire('submit');
    """)
    check("nameless food rejected", js(ctx, "state.items.length"), 27)
    check("rejection explained", js(ctx, "document.querySelector('#toast').textContent"), "Give the food a name first")

    # per-serving label needs a serving size
    ctx.eval("""
      document.querySelector('#f-name').value = 'Serving label test';
      document.querySelector('#f-protein-basis').value = 'serving';
      document.querySelector('#f-serving').value = '';
      document.querySelector('#add-form').fire('submit');
    """)
    check("per-serving without size rejected", js(ctx, "state.items.length"), 27)
    contains("explains the missing serving size", ctx.eval("document.querySelector('#toast').textContent"), "Serving size")

    ctx.eval("""
      document.querySelector('#f-serving').value = '113';
      document.querySelector('#add-form').fire('submit');
    """)
    check("per-serving label accepted", js(ctx, "state.items.length"), 28)
    check("stored basis is serving", js(ctx, "state.items[state.items.length-1].basis"), "serving")
    check("serving size stored", js(ctx, "state.items[state.items.length-1].servingSize"), 113)

    # --- target changes ---
    ctx.eval("document.querySelector('#f-target').value = '200'; document.querySelector('#f-target').fire('input')")
    check("target updated", js(ctx, "state.target"), 200)
    contains("stats follow the target", ctx.eval("document.querySelector('#stats').innerHTML"), "200 g a day")
    ctx.eval("document.querySelector('#target-chips').children[2].fire('click')")
    check("chip sets target 150", js(ctx, "state.target"), 150)
    check("target input follows chip", js(ctx, "document.querySelector('#f-target').value"), 150)

    # --- display unit toggle ---
    check("three unit chips", js(ctx, "document.querySelector('#display-units').children.length"), 3)
    ctx.eval("document.querySelector('#display-units').children[1].fire('click')")
    check("display unit is lb", js(ctx, "state.displayUnit"), "lb")
    contains("header says per lb", ctx.eval("document.querySelector('#th-cost').innerHTML"), "Cost / lb")
    ctx.eval("__thEls[4].fire('click')")
    contains("row price now per lb", first_row(ctx), "$")
    check("unit choice persisted", js(ctx, "JSON.parse(localStorage.getItem('protein-cost-calc-en-v1')).displayUnit"), "lb")

    # --- bodyweight suggester ---
    ctx.eval("""
      document.querySelector('#f-weight').value = '180';
      document.querySelector('#f-weight-unit').value = 'lb';
      document.querySelector('#f-level').value = 'active';
      document.querySelector('#suggest-btn').fire('click');
    """)
    contains("suggestion range shown", ctx.eval("document.querySelector('#suggest-out').innerHTML"), "114–147 g")
    contains("suggestion offers a button", ctx.eval("document.querySelector('#suggest-out').innerHTML"), "Use 131 g")
    ctx.eval("document.querySelector('#use-suggest').fire('click')")
    check("suggested mid applied", js(ctx, "state.target"), 131)

    # --- clear all ---
    ctx.eval("document.querySelector('#clear-all').fire('click')")
    check("cleared", js(ctx, "state.items.length"), 0)
    check("table emptied", js(ctx, "document.querySelector('#tbody').children.length"), 0)
    check("empty message back", js(ctx, "document.querySelector('#empty').style.display"), "block")

    # --- storage round trip ---
    ctx.eval("state.items = []; localStorage.setItem('protein-cost-calc-en-v1', JSON.stringify({items:[{name:'Eggs',price:3.29,size:600,unit:'g',protein:13,kcal:143,basis:'100g'}],target:170,displayUnit:'oz'}))")
    ctx.eval("load(); render();")
    check("restored from storage", js(ctx, "state.items.length"), 1)
    check("restored target", js(ctx, "state.target"), 170)
    check("restored unit", js(ctx, "state.displayUnit"), "oz")
    check("restored row rendered", js(ctx, "document.querySelector('#tbody').children.length"), 1)

    # --- CTA wiring ---
    check("CTA points at the Gumroad product",
          js(ctx, "document.querySelector('#gumroad-link').href"),
          "https://rwg4002.gumroad.com/l/high-protein-meal-prep-calculator")
    src_cta = re.search(r'<a class="cta-btn" id="gumroad-link"[^>]*>', src).group(0)
    check("CTA opens in a new tab", 'target="_blank"' in src_cta and 'rel="noopener"' in src_cta, True)
    check("CTA copy carries the price and code", "$12" in src and "LAUNCH25" in src, True)
    check("two ad slots present", src.count('class="adslot"'), 2)

    # --- offline / dependency check on the file itself ---
    check("no external script/link/font", bool(re.search(r'<(script|link)[^>]+(src|href)="https?://', src)), False)
    check("no fetch/XHR", bool(re.search(r'fetch\s*\(|XMLHttpRequest', src)), False)

    print("\n" + ("All UI checks passed" if not failures else f"{len(failures)} failed: {failures}"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
