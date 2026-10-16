"""page.js is a port of dcf_engine.py. Hold it to the engine.

Runs the port under node on the same bundles and compares the whole answer:
schedule, bridge, warnings, sensitivity grid and driver ranking. Skips without
node; the page also checks itself against the engine's figures when it loads.
"""

import json
import os
import shutil
import subprocess

import pytest

from dcf_engine import driver_ranking, run_model, sensitivity_axes, sensitivity_grid
from test_pages import rich_bundle
from test_schedule import bundle, const

NODE = shutil.which("node")
PAGE_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "page.js")

RUNNER = """
const DCF = require(process.argv[1]);
const b = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const ax = DCF.sensitivityAxes(b);
process.stdout.write(JSON.stringify({
  model: DCF.runModel(b),
  grid: DCF.sensitivityGrid(b, ax[0], ax[1]),
  ranking: DCF.driverRanking(b),
}));
"""

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run_js(b):
    out = subprocess.run([NODE, "-e", RUNNER, PAGE_JS], input=json.dumps(b),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def jbss_like():
    """Uneven paths, a NOL that outlives year 6, debt and equity claims."""
    b = rich_bundle()
    b["base"]["nol"] = 5000.0
    b["assumptions"]["depreciation_rate"]["explicit"] = [0.14, 0.135, 0.13, 0.13, 0.13]
    b["assumptions"]["operating_liabilities"]["payables"] = {
        "explicit": [0.062, 0.06, 0.058, 0.056, 0.055], "terminal": 0.055}
    return b


@pytest.mark.parametrize("make", [bundle, rich_bundle, jbss_like])
def test_the_port_agrees_with_the_engine(make):
    b = make()
    want, got = run_model(b), run_js(b)
    m = got["model"]

    for key in ("ev_ops", "pv_explicit", "pv_terminal", "terminal_value",
                "pv_nol", "equity_value", "value_per_share"):
        assert m[key] == pytest.approx(want[key], rel=1e-10, abs=1e-9), key
    for py, js in zip(want["schedule"], m["schedule"]):
        for key, value in py.items():
            assert js[key] == pytest.approx(value, rel=1e-10, abs=1e-9), (py["year"], key)
    assert [x["label"] for x in m["bridge"]] == [x["label"] for x in want["bridge"]]
    assert [x["amount"] for x in m["bridge"]] == pytest.approx([x["amount"] for x in want["bridge"]])
    assert m["warnings"] == want["warnings"]


@pytest.mark.parametrize("make", [bundle, rich_bundle, jbss_like])
def test_the_port_s_sensitivity_and_ranking_agree(make):
    b = make()
    got = run_js(b)
    waccs, growths = sensitivity_axes(b)
    for row_py, row_js in zip(sensitivity_grid(b, waccs, growths), got["grid"]):
        for py, js in zip(row_py, row_js):
            assert (py is None and js is None) or js == pytest.approx(py, rel=1e-10)

    want = driver_ranking(b)
    assert [r["driver"] for r in got["ranking"]] == [r["driver"] for r in want]
    assert [r["span_share"] for r in got["ranking"]] == pytest.approx(
        [r["span_share"] for r in want], rel=1e-9)


def test_the_port_refuses_a_perpetuity_that_does_not_exist():
    b = bundle()
    b["rates"]["wacc"] = 0.03
    with pytest.raises(subprocess.CalledProcessError):
        run_js(b)
