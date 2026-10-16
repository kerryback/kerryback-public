// The page's calculator: a line-for-line port of dcf_engine.py, so the Baseline
// tab can be edited and the DCF tab revalued in the browser.
//
// This is the recursion's third home, after the Python engine and the
// workbook's formulas. It is held to the engine two ways: tests/test_page_js.py
// runs it under node against run_model, and the page itself re-values the
// suggested numbers on load and flags any disagreement with the figures the
// engine wrote into it.

var DCF = (function () {
  var N_EXPLICIT = 5, TRANSITION = 6, PERPETUITY = 7;
  var SCALARS = ["sales_growth", "ebitda_margin", "sales_to_net_ppe",
                 "depreciation_rate", "cash_tax_rate"];
  var SIDES = ["operating_assets", "operating_liabilities"];

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function total(o) { var s = 0; for (var k in o) s += o[k]; return s; }
  function drv(spec, t) { return t <= N_EXPLICIT ? spec.explicit[t - 1] : spec.terminal; }
  function label(k) {
    var s = String(k).replace(/_/g, " ").trim();
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function runModel(b) {
    var a = b.assumptions, base = b.base, wacc = b.rates.wacc;
    var g = a.sales_growth.terminal;
    var lim = b.rates.nol_limitation === undefined ? 0.8 : b.rates.nol_limitation;
    if (!(wacc > g)) throw new Error("WACC (" + fmt(wacc, "pct") + ") must exceed terminal growth (" +
                                     fmt(g, "pct") + "); the perpetuity does not exist.");

    var s = [base.sales], t, k;
    for (t = 1; t <= PERPETUITY + 1; t++) s.push(s[t - 1] * (1 + drv(a.sales_growth, t)));

    var nppePrev = base.net_ppe;
    var nwcPrev = total(base.operating_assets || {}) - total(base.operating_liabilities || {});
    var nol = +(base.nol || 0), rows = [];
    for (t = 1; t <= PERPETUITY; t++) {
      var sales = s[t];
      var nppe = s[t + 1] / drv(a.sales_to_net_ppe, t);
      var dep = drv(a.depreciation_rate, t) * nppePrev;
      var capex = nppe - nppePrev + dep;
      var ratio = 0;
      for (k in a.operating_assets) ratio += drv(a.operating_assets[k], t);
      for (k in a.operating_liabilities) ratio -= drv(a.operating_liabilities[k], t);
      var nwc = ratio * sales;
      var ebitda = drv(a.ebitda_margin, t) * sales;
      var ebit = ebitda - dep;

      var rate = drv(a.cash_tax_rate, t), used, taxable, tax, open = nol;
      if (t >= PERPETUITY) { used = 0; taxable = ebit; tax = rate * ebit; }
      else if (ebit <= 0) { used = 0; taxable = 0; tax = 0; nol -= ebit; }
      else { used = Math.min(lim * ebit, nol); taxable = ebit - used; tax = rate * taxable; nol -= used; }

      var fcf = ebitda - tax - capex - (nwc - nwcPrev);
      var df = 1 / Math.pow(1 + wacc, t);
      rows.push({ year: t, sales: sales, next_sales: s[t + 1], ebitda: ebitda, net_ppe: nppe,
                  depreciation: dep, capex: capex, nwc: nwc, delta_nwc: nwc - nwcPrev, ebit: ebit,
                  nol_open: open, nol_used: used, nol_close: nol, taxable_income: taxable, tax: tax,
                  effective_tax_rate: ebit ? tax / ebit : 0, fcf: fcf, discount_factor: df,
                  pv_fcf: fcf * df });
      nppePrev = nppe; nwcPrev = nwc;
    }

    var perp = rows[PERPETUITY - 1], pvExplicit = 0;
    for (t = 0; t < TRANSITION; t++) pvExplicit += rows[t].pv_fcf;
    var tv = perp.fcf / (wacc - g);
    var pvTerminal = tv / Math.pow(1 + wacc, TRANSITION);
    var evOps = pvExplicit + pvTerminal;

    var nolSix = rows[TRANSITION - 1].nol_close, pvNol = 0, unexhausted = false;
    if (nolSix > 0) {
      if (perp.ebit <= 0) unexhausted = true;
      else {
        var left = nolSix, e = perp.ebit, yr = PERPETUITY, tr = drv(a.cash_tax_rate, PERPETUITY);
        while (left > 0 && yr < PERPETUITY + 200) {
          var u = Math.min(lim * e, left);
          pvNol += tr * u / Math.pow(1 + wacc, yr);
          left -= u; e *= 1 + g; yr++;
        }
        unexhausted = left > 0;
      }
    }

    var bridge = [{ label: "Enterprise value of operations", amount: evOps }];
    if (pvNol) bridge.push({ label: "PV of remaining NOL carryforward", amount: pvNol });
    for (k in base.nonoperating_assets || {}) bridge.push({ label: "Plus " + label(k).toLowerCase(), amount: +base.nonoperating_assets[k] });
    for (k in base.debt_claims || {}) bridge.push({ label: "Less " + label(k).toLowerCase(), amount: -base.debt_claims[k] });
    for (k in base.equity_claims || {}) bridge.push({ label: "Less " + label(k).toLowerCase(), amount: -base.equity_claims[k] });
    var equity = 0;
    bridge.forEach(function (x) { equity += x.amount; });
    var shares = b.meta.diluted_shares || 0;

    return { schedule: rows, ev_ops: evOps, pv_explicit: pvExplicit, pv_terminal: pvTerminal,
             terminal_value: tv, pv_nol: pvNol, bridge: bridge, equity_value: equity,
             value_per_share: shares ? equity / shares : null,
             warnings: warnings(b, rows, perp, nolSix, pvNol, unexhausted) };
  }

  function warnings(b, rows, perp, nolSix, pvNol, unexhausted) {
    var a = b.assumptions, out = [];
    if (nolSix > 0) out.push("A carryforward of " + fmt1(nolSix) + " survives year 6. Its shield is valued separately at " +
                             fmt1(pvNol) + " and shown in the bridge, so the perpetuity is taxed at the full rate.");
    if (unexhausted) out.push("The carryforward is not exhausted within 200 years of steady state; the shield above is a lower bound.");
    if (perp.ebit <= 0) out.push("Terminal EBIT is not positive, so the perpetuity is negative. The model cannot value this company as a going concern on these assumptions.");
    var neg = rows.filter(function (r) { return r.capex < 0; }).map(function (r) { return r.year; });
    if (neg.length) out.push("Implied capex is negative in year(s) [" + neg.join(", ") + "]: the sales-to-PP&E turnover is shrinking the asset base faster than it depreciates.");
    if (rows.some(function (r) { return r.sales <= 0; })) out.push("Sales reach zero or below inside the forecast.");
    var k5 = drv(a.sales_to_net_ppe, N_EXPLICIT), kt = a.sales_to_net_ppe.terminal;
    if (kt && Math.abs(k5 - kt) / Math.abs(kt) > 0.10)
      out.push("Year 5's sales-to-PP&E turnover (" + k5.toFixed(2) + ") is more than 10 percent from terminal (" +
               kt.toFixed(2) + "), so year 6 absorbs the whole adjustment.");
    var units = String(b.meta.units || "").toLowerCase();
    if (units.indexOf("million") >= 0 && b.base.sales > 1e7)
      out.push("meta.units says millions but base sales is " + fmt(b.base.sales, "num") + ". If the statements are in dollars and the share count is in millions, value per share is wrong by a factor of a million.");
    return out;
  }

  function tryValue(b) { try { return runModel(b).value_per_share; } catch (e) { return null; } }

  function sensitivityAxes(b) {
    var w = b.rates.wacc, g = b.assumptions.sales_growth.terminal;
    return [[-0.02, -0.01, 0, 0.01, 0.02].map(function (d) { return w + d; }),
            [-0.01, -0.005, 0, 0.005, 0.01].map(function (d) { return g + d; })];
  }

  function sensitivityGrid(b, waccs, growths) {
    return waccs.map(function (w) {
      return growths.map(function (g) {
        var trial = clone(b);
        trial.rates.wacc = w;
        trial.assumptions.sales_growth.terminal = g;
        return tryValue(trial);
      });
    });
  }

  function driverRanking(b) {
    var entries = SCALARS.map(function (n) { return [n, null]; });
    SIDES.forEach(function (side) { for (var k in b.assumptions[side]) entries.push([side, k]); });
    var base = tryValue(b), out = [];
    entries.forEach(function (en) {
      var rel = en[0] === "sales_to_net_ppe", size = rel ? 0.05 : 0.01, vals = [];
      [-size, size].forEach(function (sh) {
        var trial = clone(b);
        var sp = en[1] === null ? trial.assumptions[en[0]] : trial.assumptions[en[0]][en[1]];
        sp.explicit = sp.explicit.map(function (v) { return rel ? v * (1 + sh) : v + sh; });
        sp.terminal = rel ? sp.terminal * (1 + sh) : sp.terminal + sh;
        vals.push(tryValue(trial));
      });
      if (vals[0] === null || vals[1] === null) return;
      var span = Math.abs(vals[1] - vals[0]);
      out.push({ driver: (en[1] === null ? en[0] : en[1]).replace(/_/g, " "), name: en[0], key: en[1],
                 shift: rel ? "5% of itself" : "1pp", low: vals[0], high: vals[1], span: span,
                 base: base, span_share: base ? span / Math.abs(base) : null });
    });
    out.sort(function (x, y) { return y.span - x.span; });
    return out;
  }

  // Mirrors build_pages.fmt.
  function comma(v, d) { return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function fmt1(v) { return comma(v, 1); }
  function fmt(v, kind) {
    if (v === null || v === undefined) return "—";
    if (kind === "pct") return comma(v * 100, 1) + "%";
    if (kind === "mult") return comma(v, 2) + "×";
    if (kind === "factor") return comma(v, 4);
    if (kind === "share") return comma(v, 2);
    return Math.abs(v) < 100 ? comma(v, 1) : comma(v, 0);
  }

  return { runModel: runModel, sensitivityAxes: sensitivityAxes, sensitivityGrid: sensitivityGrid,
           driverRanking: driverRanking, fmt: fmt, clone: clone, SCALARS: SCALARS, SIDES: SIDES };
})();

if (typeof module !== "undefined" && module.exports) module.exports = DCF;

if (typeof document !== "undefined") (function () {
  var DATA = JSON.parse(document.getElementById("dcf-data").textContent);
  var fmt = DCF.fmt, clone = DCF.clone;
  var REC = DATA.bundle;
  var state = clone(REC);

  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function byId(id) { return document.getElementById(id); }

  // ------------------------------------------------------------ tabs
  function select(btn) {
    btn.parentElement.querySelectorAll('[role="tab"]').forEach(function (b) {
      var on = b === btn;
      b.setAttribute("aria-selected", on);
      byId(b.getAttribute("aria-controls")).hidden = !on;
    });
  }
  document.querySelectorAll('[role="tab"]').forEach(function (b) {
    b.addEventListener("click", function () {
      select(b);
      try { history.replaceState(null, "", "#" + b.id.slice(2)); } catch (e) {}
    });
  });
  var want = location.hash.slice(1), tab = want && byId("t-" + want);
  if (tab) select(tab);

  // ------------------------------------------------------------ cells
  // Each input names where its number lives in the bundle.
  function locate(inp) {
    var path = inp.dataset.path.split("."), col = inp.dataset.col;
    return {
      unit: inp.dataset.unit,
      get: function (b) {
        var o = b;
        for (var i = 0; i < path.length; i++) o = o[path[i]];
        return col === undefined ? o : (+col < 5 ? o.explicit[+col] : o.terminal);
      },
      set: function (v) {
        var o = state;
        for (var i = 0; i < path.length - 1; i++) o = o[path[i]];
        var last = path[path.length - 1];
        if (col === undefined) o[last] = v;
        else if (+col < 5) o[last].explicit[+col] = v;
        else o[last].terminal = v;
      }
    };
  }
  function shown(v, unit) {
    var x = unit === "%" ? v * 100 : v, d = unit === "x" ? 2 : 1, s = x.toFixed(d), r = +x.toFixed(4);
    if (unit === "n") return String(r);
    return +s === r ? s : String(r);
  }
  function inputs() { return document.querySelectorAll("#p-baseline input[data-path]"); }
  function mark(inp, ref) { inp.classList.toggle("edited", Math.abs(ref.get(state) - ref.get(REC)) > 1e-12); }
  function fill() {
    inputs().forEach(function (inp) {
      var ref = locate(inp);
      inp.value = shown(ref.get(state), ref.unit);
      inp.classList.remove("bad");
      mark(inp, ref);
    });
  }

  // Edits survive a reload. The key carries a hash of the suggested numbers,
  // so a rebuild with new suggestions starts clean rather than resurrecting
  // edits made against the old ones.
  function save() { try { localStorage.setItem(DATA.store, JSON.stringify(state)); } catch (e) {} }
  try {
    var saved = JSON.parse(localStorage.getItem(DATA.store) || "null");
    if (saved && saved.assumptions) state = saved;
  } catch (e) {}

  document.addEventListener("input", function (ev) {
    var inp = ev.target;
    if (!inp.dataset || !inp.dataset.path) return;
    var v = parseFloat(inp.value.replace(/,/g, "")), ref = locate(inp);
    if (inp.value.trim() === "" || !isFinite(v)) { inp.classList.add("bad"); return; }
    inp.classList.remove("bad");
    ref.set(ref.unit === "%" ? v / 100 : v);
    mark(inp, ref);
    save();
    render();
  });
  document.addEventListener("change", function (ev) {
    var inp = ev.target;
    if (inp.dataset && inp.dataset.path && inp.classList.contains("bad")) {
      var ref = locate(inp);
      inp.value = shown(ref.get(state), ref.unit);
      inp.classList.remove("bad");
    }
  });
  byId("reset").addEventListener("click", function () {
    state = clone(REC);
    try { localStorage.removeItem(DATA.store); } catch (e) {}
    fill();
    render();
  });
  byId("copy-csv").addEventListener("click", function () {
    var text = byId("csv-text").value, btn = this;
    function done() { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1500); }
    try { navigator.clipboard.writeText(text).then(done, function () { byId("csv-text").select(); }); }
    catch (e) { byId("csv-text").select(); }
  });

  // ------------------------------------------------------------ the CSV, as dcf_assumptions writes it
  function num(v, unit) { var x = unit === "%" ? v * 100 : v; return String(+x.toPrecision(8)); }
  function csv(b) {
    var a = b.assumptions, lines = ["row,key,unit,Y1,Y2,Y3,Y4,Y5,Terminal"];
    var units = { sales_growth: "%", ebitda_margin: "%", sales_to_net_ppe: "x", depreciation_rate: "%", cash_tax_rate: "%" };
    function row(name, key, unit, spec) {
      lines.push([name, key, unit].concat(spec.explicit.concat([spec.terminal]).map(function (v) { return num(v, unit); })).join(","));
    }
    DCF.SCALARS.forEach(function (n) { row(n, "", units[n], a[n]); });
    DCF.SIDES.forEach(function (side) { for (var k in a[side]) row(side, k, "%", a[side][k]); });
    lines.push("wacc,,%," + num(b.rates.wacc, "%"));
    lines.push("nol_limitation,,%," + num(b.rates.nol_limitation === undefined ? 0.8 : b.rates.nol_limitation, "%"));
    lines.push("opening_nol,,n," + num(+(b.base.nol || 0), "n"));
    lines.push("diluted_shares,,n," + num(b.meta.diluted_shares || 0, "n"));
    return lines.join("\n") + "\n";
  }

  // ------------------------------------------------------------ the DCF tab, as build_pages renders it
  var LINES = [["sales", "Sales", "num"], ["ebitda", "EBITDA", "num"], ["depreciation", "Depreciation", "num"],
    ["ebit", "EBIT", "num"], ["nol_open", "NOL carryforward, opening", "num"], ["nol_used", "NOL used", "num"],
    ["taxable_income", "Taxable income", "num"], ["tax", "Cash taxes", "num"],
    ["effective_tax_rate", "Effective tax rate", "pct"], ["net_ppe", "Net PP&E, closing", "num"],
    ["capex", "Capital expenditure", "num"], ["nwc", "Net working capital, closing", "num"],
    ["delta_nwc", "Investment in working capital", "num"], ["fcf", "Free cash flow", "num"],
    ["discount_factor", "Discount factor", "factor"], ["pv_fcf", "PV of free cash flow", "num"]];

  function scheduleTable(m) {
    var h = "<table><thead><tr><th>Forecast</th>";
    m.schedule.forEach(function (r) {
      h += "<th class='fc'>Year " + r.year + (r.year === 6 ? " · transition" : r.year === 7 ? " · perpetuity" : "") + "</th>";
    });
    h += "</tr></thead><tbody>";
    LINES.forEach(function (L) {
      h += "<tr" + (L[0] === "fcf" ? " class='total'" : "") + "><td>" + esc(L[1]) + "</td>";
      m.schedule.forEach(function (r) { h += "<td>" + fmt(r[L[0]], L[2]) + "</td>"; });
      h += "</tr>";
      if (L[0] === "fcf") {
        h += "<tr class='derived'><td>Free cash flow growth</td><td>&mdash;</td>";
        for (var i = 1; i < m.schedule.length; i++) {
          var p = m.schedule[i - 1].fcf;
          h += p > 0 ? "<td>" + fmt(m.schedule[i].fcf / p - 1, "pct") + "</td>" : "<td>&mdash;</td>";
        }
        h += "</tr>";
      }
    });
    return h + "</tbody></table>";
  }

  function bridgeTable(b, m) {
    var h = "<table><tbody>";
    function line(l, v, kind, tot) {
      h += "<tr" + (tot ? " class='total'" : "") + "><td>" + esc(l) + "</td><td>" + fmt(v, kind || "num") + "</td></tr>";
    }
    line("PV of free cash flow, years 1 to 6", m.pv_explicit);
    line("Terminal value at the end of year 6", m.terminal_value);
    line("PV of the terminal value", m.pv_terminal);
    m.bridge.forEach(function (x, i) { line(x.label, x.amount, "num", i === 0); });
    line("Equity value", m.equity_value, "num", true);
    line("Diluted shares", b.meta.diluted_shares);
    line("Value per share", m.value_per_share, "share", true);
    return h + "</tbody></table>";
  }

  function sensitivityTable(b) {
    var ax = DCF.sensitivityAxes(b), grid = DCF.sensitivityGrid(b, ax[0], ax[1]);
    var h = "<table><thead><tr><th>WACC \\ terminal growth</th>" +
            ax[1].map(function (g) { return "<th>" + fmt(g, "pct") + "</th>"; }).join("") + "</tr></thead><tbody>";
    ax[0].forEach(function (w, i) {
      h += "<tr><td>" + fmt(w, "pct") + "</td>";
      ax[1].forEach(function (g, j) {
        h += "<td class='" + (i === 2 && j === 2 ? "sens here" : "sens") + "'>" + fmt(grid[i][j], "share") + "</td>";
      });
      h += "</tr>";
    });
    return h + "</tbody></table>";
  }

  function rankingTable(b) {
    var rows = DCF.driverRanking(b);
    if (!rows.length) return "<p class='note'>No driver could be varied without breaking the model, so there is nothing to rank.</p>";
    var widest = rows[0].span_share || 1;
    var h = "<table><thead><tr><th>Driver</th><th>Moved</th><th>Moves the value by</th><th></th></tr></thead><tbody>";
    rows.forEach(function (r) {
      var share = r.span_share || 0;
      h += "<tr><td>" + esc(r.driver) + "</td><td>" + esc(r.shift) + "</td><td>" + (share * 100).toFixed(1) +
           "%</td><td class='bar'><span style='width:" + Math.max(2, Math.round(100 * share / widest)) + "%'></span></td></tr>";
    });
    return h + "</tbody></table>";
  }

  // ------------------------------------------------------------ parity with the engine
  var drift = null;
  (function () {
    var c = DATA.check;
    function off(x, y) { return Math.abs(x - y) > 1e-6 * Math.max(1, Math.abs(y)); }
    try {
      var m = DCF.runModel(REC);
      var bad = off(m.ev_ops, c.ev_ops) || off(m.equity_value, c.equity_value) ||
                m.schedule.some(function (r, i) { return off(r.fcf, c.fcf[i]); });
      if (bad) drift = "This page's calculator disagrees with dcf_engine.py on the suggested numbers, so its revaluations cannot be trusted. Rebuild the page and report the mismatch.";
    } catch (e) { drift = "This page's calculator failed on the suggested numbers: " + e.message; }
  })();

  // ------------------------------------------------------------ render
  function render() {
    var edited = document.querySelectorAll("#p-baseline input.edited").length;
    byId("tg").textContent = fmt(state.assumptions.sales_growth.terminal, "pct");
    byId("csv-text").value = csv(state);
    byId("dcf-status").textContent = edited
      ? "Valued on the Baseline tab with " + edited + " edited cell" + (edited > 1 ? "s" : "") + "."
      : "Valued on the suggested forecasts in the Baseline tab. Edit them there and this tab revalues.";

    var m, warn = drift ? [drift] : [];
    try { m = DCF.runModel(state); }
    catch (e) {
      byId("warnings").innerHTML = warn.concat([e.message]).map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("");
      ["h-ev", "h-eq", "h-vps"].forEach(function (id) { byId(id).textContent = "—"; });
      ["schedule", "bridge", "sensitivity", "ranking"].forEach(function (id) { byId(id).innerHTML = ""; });
      byId("readout-text").textContent = e.message;
      return;
    }
    byId("warnings").innerHTML = warn.concat(m.warnings).map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("");
    byId("h-ev").textContent = fmt(m.ev_ops, "num");
    byId("h-eq").textContent = fmt(m.equity_value, "num");
    byId("h-vps").textContent = fmt(m.value_per_share, "share");
    byId("readout-text").innerHTML = "Value per share at these forecasts: <b>" + fmt(m.value_per_share, "share") + "</b>" +
      (edited ? " (suggested: " + fmt(DATA.check.value_per_share, "share") + ")" : "") + " — details on the DCF tab.";
    byId("schedule").innerHTML = scheduleTable(m);
    byId("bridge").innerHTML = bridgeTable(state, m);
    byId("sensitivity").innerHTML = sensitivityTable(state);
    byId("ranking").innerHTML = rankingTable(state);
  }

  fill();
  render();
})();
