"""One page, four tabs: Line items, Forecasts, Baseline, DCF."""

import json
import pathlib
import re

import pytest

from dcf_engine import run_model
from build_pages import LIVE_RELOAD, build_page, build_pages, fmt
from dcf_engine import sensitivity_axes, sensitivity_grid
from test_schedule import bundle, const


def rich_bundle():
    """A bundle that exercises every branch the report has to render."""
    b = bundle()
    b["meta"]["ticker"] = "RICH"
    b["meta"]["fiscal_year_end"] = "2025-12-31"
    b["base"]["nol"] = 250.0
    b["base"]["nonoperating_assets"] = {"cash": 50.0, "investments": 12.0}
    b["base"]["debt_claims"] = {"long_term_debt": 400.0, "lease_liabilities": 75.0}
    b["base"]["equity_claims"] = {"noncontrolling_interests": 30.0}
    b["base"]["operating_assets"]["inventories"] = 90.0
    b["assumptions"]["operating_assets"]["inventories"] = const(0.08)
    b["assumptions"]["ebitda_margin"]["explicit"] = [-0.05, 0.02, 0.12, 0.18, 0.21]
    b["assumptions"]["ebitda_margin"]["rationale"] = "A loss year, then a recovery."
    b["assumptions"]["sales_growth"]["guidance"] = (
        "How to think about the margin on volume: guidance covers one year, so "
        "years 2 through 5 are a fade you have to argue for.")
    b["assumptions"]["sales_growth"]["citations"] = [
        {"quote": "Nut costs are the whole story this year.",
         "speaker": "Frank S. Pellegrino",
         "source": "transcripts/FY2026Q4.txt"}]
    b["assumptions"]["sales_growth"]["explicit"] = [0.30, 0.15, 0.08, 0.05, 0.04]
    b["assumptions"]["sales_to_net_ppe"]["explicit"] = [1.6, 1.7, 1.8, 1.9, 2.4]
    b["classification"] = [
        {"line": "Accounts receivable, net", "bucket": "operating_asset",
         "key": "receivables", "note": "Trade receivables."},
        {"line": "Inventories", "bucket": "operating_asset", "key": "inventories",
         "note": "Finished goods."},
        {"line": "Accounts payable", "bucket": "operating_liability",
         "key": "payables", "note": "Trade payables."},
    ]
    b["rates"]["wacc_derivation"] = "CAPM: 4.2 + 1.1 x 5.0 = 9.7 percent."
    b["history"] = {
        "years": [2021, 2022, 2023, 2024, 2025],
        "ratios": {"sales_growth": {2022: 0.12, 2023: 0.04},
                   "operating_assets": {"receivables": {2022: 0.19}}},
        "notes": ["EBITDA did not cover depreciation in 2025."],
    }
    return b


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    out = tmp_path_factory.mktemp("page")
    return pathlib.Path(build_pages(rich_bundle(), str(out), slug="rich")).read_text(encoding="utf-8")


def panel(page, name):
    """The HTML of one tab panel, up to the next panel."""
    start = page.index(f'id="p-{name}"')
    nxt = page.find('role="tabpanel"', start + 1)
    return page[start:nxt if nxt > 0 else len(page)]


def page_data(page):
    m = re.search(r'<script type="application/json" id="dcf-data">(.*?)</script>', page, re.S)
    return json.loads(m.group(1))


def test_one_file_named_for_the_slug(tmp_path):
    path = build_pages(rich_bundle(), str(tmp_path), slug="rich")
    assert path.endswith("rich.html")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["rich.html"]


def test_four_tabs_in_one_row_with_no_nesting(page):
    tabs = re.findall(r'role="tab" id="t-([a-z]+)"', page)
    assert tabs == ["lines", "evidence", "baseline", "dcf"]
    assert page.count('role="tablist"') == 1
    for label in (">Line items<", ">Forecasts<", ">Baseline<", ">DCF<"):
        assert label in page
    # Line items opens first; the others start hidden.
    assert re.search(r'id="p-lines"[^>]*>', page).group(0).find("hidden") < 0
    for name in ("evidence", "baseline", "dcf"):
        assert "hidden" in re.search(rf'id="p-{name}"[^>]*>', page).group(0)


def test_the_page_follows_the_reader_s_appearance_setting(page):
    assert "prefers-color-scheme: dark" in page
    assert "--ground: #ffffff" in page


def test_no_network_references(page):
    assert "http://" not in page
    assert "https://" not in page


def test_no_template_token_survives(page):
    assert not re.search(r"__[A-Z_]+__", page)


def test_the_page_does_not_point_at_the_workbook(page):
    assert ".xlsx" not in page


def test_the_classification_is_the_line_items_tab(page):
    lines = panel(page, "lines")
    assert "Accounts receivable, net" in lines
    assert "Trade receivables." in lines
    assert "operating_liability" in lines


def test_the_evidence_is_the_forecasts_tab(page):
    ev = panel(page, "evidence")
    assert "Driver by driver" in ev
    assert "<section class='guide'>" in ev
    assert "How to think about the margin" in ev
    assert "Nut costs are the whole story" in ev and "<cite>" in ev
    assert "Frank S. Pellegrino" in ev
    assert "A loss year, then a recovery." in ev
    assert "History" in ev and "Suggested" in ev
    assert "Moving it 1pp each way moves the value" in ev


def test_the_numbers_are_presented_as_suggestions(page):
    flat = " ".join(panel(page, "evidence").split())
    assert "a suggestion, not a conclusion" in flat
    assert "The decision is yours" in flat


def test_history_notes_sit_with_the_evidence(page):
    assert "did not cover depreciation" in panel(page, "evidence")


def test_no_history_notes_means_no_history_section(tmp_path):
    b = rich_bundle()
    b["history"]["notes"] = []
    text = pathlib.Path(build_pages(b, str(tmp_path), slug="x")).read_text()
    assert "What the history showed" not in text


def test_every_forecast_cell_on_the_baseline_is_an_input(page):
    base = panel(page, "baseline")
    b = rich_bundle()
    n_rows = 5 + len(b["assumptions"]["operating_assets"]) + len(b["assumptions"]["operating_liabilities"])
    cells = re.findall(r"<input[^>]*data-path='assumptions\.[^']+'[^>]*data-col='(\d)'", base)
    assert len(cells) == n_rows * 6
    for path in ("rates.wacc", "rates.nol_limitation", "base.nol", "meta.diluted_shares"):
        assert f"data-path='{path}'" in base


def test_inputs_show_the_suggested_numbers(page):
    base = panel(page, "baseline")
    # Growth 30 percent in year 1, a 2.40x terminal turnover's year-5 value.
    assert re.search(r"data-path='assumptions\.sales_growth'[^>]*data-col='0'[^>]*value='30\.0'", base)
    assert re.search(r"data-path='assumptions\.sales_to_net_ppe'[^>]*data-col='4'[^>]*value='2\.40'", base)


def test_historical_columns_show_what_history_there_is(page):
    base = panel(page, "baseline")
    assert "2021" in base and "2025" in base
    assert "class='hist'>12.0%" in base


def test_the_dcf_tab_is_rendered_by_the_engine_before_any_script_runs(page):
    dcf = panel(page, "dcf")
    want = run_model(rich_bundle())
    assert fmt(want["ev_ops"], "num") in dcf
    assert fmt(want["equity_value"], "num") in dcf
    assert fmt(want["value_per_share"], "share") in dcf
    assert "Free cash flow" in dcf


def test_the_sensitivity_table_centres_on_the_base_case(page):
    b = rich_bundle()
    waccs, growths = sensitivity_axes(b)
    grid = sensitivity_grid(b, waccs, growths)
    assert "sens here" in page
    assert fmt(grid[2][2], "share") in panel(page, "dcf")


def test_the_ranking_is_on_the_dcf_tab_widest_first(page):
    dcf = panel(page, "dcf")
    block = dcf[dcf.index("Which arguments are worth having"):dcf.index("Cost of capital")]
    shares = [float(x) for x in re.findall(r"<td>([\d.]+)%</td>", block)]
    assert shares == sorted(shares, reverse=True)
    assert len(shares) >= 5


def test_warnings_are_rendered(page):
    dcf = panel(page, "dcf")
    assert "carryforward" in dcf
    assert "absorbs the whole adjustment" in dcf


def test_the_wacc_derivation_is_on_the_dcf_tab(page):
    assert "CAPM: 4.2" in panel(page, "dcf")


def test_the_page_carries_the_engine_s_answer_to_check_itself_against(page):
    data = page_data(page)
    want = run_model(rich_bundle())
    assert data["check"]["value_per_share"] == pytest.approx(want["value_per_share"])
    assert data["check"]["fcf"] == pytest.approx([r["fcf"] for r in want["schedule"]])
    assert data["bundle"]["assumptions"]["sales_growth"]["explicit"][0] == pytest.approx(0.30)
    # Numbers only: the argument stays in the HTML, not in the data block.
    assert "guidance" not in json.dumps(data)


def test_saved_edits_are_keyed_to_the_suggested_numbers(tmp_path):
    a = page_data(pathlib.Path(build_pages(rich_bundle(), str(tmp_path / "a"), slug="r")).read_text())
    b2 = rich_bundle()
    b2["assumptions"]["ebitda_margin"]["terminal"] = 0.25
    b = page_data(pathlib.Path(build_pages(b2, str(tmp_path / "b"), slug="r")).read_text())
    assert a["store"] != b["store"]


def test_the_page_offers_its_numbers_as_assumptions_csv(page):
    assert "assumptions.csv" in panel(page, "baseline")
    assert "id='copy-csv'" in page or 'id="copy-csv"' in page


def test_live_mode_adds_only_the_reload_poller(tmp_path):
    plain = pathlib.Path(build_pages(rich_bundle(), str(tmp_path / "p"), slug="r")).read_text()
    live = pathlib.Path(build_pages(rich_bundle(), str(tmp_path / "l"), slug="r", live=True)).read_text()
    assert LIVE_RELOAD not in plain
    assert LIVE_RELOAD in live
    assert live.count("<script") == plain.count("<script") + 1


def test_a_script_close_tag_in_the_data_cannot_end_the_block(tmp_path):
    b = rich_bundle()
    b["meta"]["units"] = "USD </script> thousands"
    text = pathlib.Path(build_pages(b, str(tmp_path), slug="x")).read_text()
    assert page_data(text)["bundle"]["meta"]["units"] == "USD </script> thousands"


def test_a_bundle_with_no_guidance_at_all_says_so(tmp_path):
    b = rich_bundle()
    for name in ("sales_growth", "ebitda_margin"):
        for field in ("rationale", "guidance", "citations"):
            b["assumptions"][name].pop(field, None)
    out = tmp_path / "bare.html"
    build_page(b, str(out))
    assert "not enough to choose from" in out.read_text(encoding="utf-8")


def test_html_in_a_company_name_is_escaped(tmp_path):
    b = rich_bundle()
    b["meta"]["company"] = "Smith & Sons <Holdings>"
    out = tmp_path / "escaped.html"
    build_page(b, str(out))
    text = out.read_text(encoding="utf-8")
    assert "<Holdings>" not in text
    assert "&lt;Holdings&gt;" in text
    assert "Smith &amp; Sons" in text


def test_a_company_with_no_history_still_renders(tmp_path):
    b = rich_bundle()
    del b["history"]
    text = pathlib.Path(build_pages(b, str(tmp_path), slug="nohist")).read_text()
    assert not re.search(r"__[A-Z_]+__", text)
