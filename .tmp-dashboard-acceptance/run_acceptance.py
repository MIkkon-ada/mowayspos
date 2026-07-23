"""FIX-DASHBOARD-LOCAL-BROWSER-ACCEPTANCE — Playwright browser acceptance."""
from __future__ import annotations

import json, os, sys, time
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent
FRONTEND_URL = "http://127.0.0.1:6001"
DASHBOARD_URL = f"{FRONTEND_URL}/home/dashboard"

USERNAME = os.environ.get("MOWAYS_LOCAL_TEST_USERNAME", "")
PASSWORD = os.environ.get("MOWAYS_LOCAL_TEST_PASSWORD", "")

RESULTS = {}
CONSOLE_ERRORS = []
PAGE_ERRORS = []


def ap(*args):
    print(*args, flush=True)


def record(name, passed, detail=""):
    RESULTS[name] = {"passed": passed, "detail": detail}
    ap(f"  {'[PASS]' if passed else '[FAIL]'} {name}: {detail}")


def skeleton_visible(page) -> bool:
    """检测骨架是否可见：Skel 组件使用 inline animation 包含 'skeleton-shimmer'"""
    return page.evaluate("""() => {
        for (const el of document.querySelectorAll('div')) {
            if (el.style.animation && el.style.animation.includes('skeleton-shimmer'))
                return true;
        }
        return false;
    }""")


def task_count_visible(page) -> bool:
    return page.locator("text=任务总数").first.is_visible()


def updating_visible(page) -> bool:
    return page.locator("text=更新中...").first.is_visible()


def error_banner_visible(page) -> bool:
    return page.locator("text=更新失败，当前显示上次成功加载的数据。").first.is_visible()


def blocked_visible(page) -> bool:
    return page.locator("text=请先选择").first.is_visible()


def ensure_env():
    if not USERNAME or not PASSWORD:
        ap("FAIL: MOWAYS_LOCAL_TEST_USERNAME / MOWAYS_LOCAL_TEST_PASSWORD missing")
        sys.exit(1)
    ap(f"[OK] user={USERNAME}")


# ── login ──
def login(page):
    ap("[login]")
    page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    if not page.locator("input[type='password']").is_visible():
        ap("  already logged in")
        return
    page.locator("input[type='text']").first.fill(USERNAME)
    page.locator("input[type='password']").first.fill(PASSWORD)
    page.locator("button[type='submit']").first.click()
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(1500)
    ap("  login done")


def goto_dashboard(page):
    page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector("text=任务总数", timeout=20000)
        ap("  data ready")
        return True
    except:
        ap(f"  blocked={blocked_visible(page)}")
        return False


# ── month selector helper ──
# select[0] = scope  (不要改！)
# select[1] = month  (可以用来触发刷新)
def toggle_month(page):
    """切换月份选择器（第二个select）来触发 overview 刷新"""
    all_selects = page.locator("select")
    if all_selects.count() < 2:
        ap("  no month select found")
        return False

    month_select = all_selects.nth(1)
    if not month_select.is_enabled():
        ap("  month select disabled")
        return False

    options = month_select.locator("option")
    cnt = options.count()
    if cnt <= 1:
        ap("  only one month option")
        return False

    # get current value
    cur = page.evaluate("() => document.querySelectorAll('select')[1].value")
    ap(f"  current month: '{cur}'")

    # find a different value
    for j in range(cnt):
        val = options.nth(j).get_attribute("value")
        if val and val != cur:
            month_select.select_option(value=val)
            ap(f"  changed month to: '{val}'")
            return True

    ap("  no different month to select")
    return False


# ── overview delay helper ──
class OverviewDelay:
    def __init__(self, page, ms=2000):
        self.page = page
        self.ms = ms
        self.done = False
        self._handler = None

    def __enter__(self):
        def h(route):
            if not self.done:
                ap(f"  [route] delaying overview {self.ms}ms ...")
                time.sleep(self.ms / 1000.0)
                self.done = True
            route.continue_()
        self._handler = h
        self.page.route("**/api/dashboard/overview*", h)

    def __exit__(self, *args):
        self.page.unroute("**/api/dashboard/overview*")


class OverviewFail:
    def __init__(self, page):
        self.page = page

    def __enter__(self):
        self.page.route("**/api/dashboard/overview*",
            lambda r: r.fulfill(status=500, body=json.dumps({"detail": "server_error"}),
                               headers={"Content-Type": "application/json"}))

    def __exit__(self, *args):
        self.page.unroute("**/api/dashboard/overview*")


# ═══════════════════ SCENARIO A ═══════════════════
def A_normal(page):
    ap("\n=== A: normal data ===")
    CONSOLE_ERRORS.clear(); PAGE_ERRORS.clear()

    ok = goto_dashboard(page)
    if not ok:
        record("正常数据态", False, "blocked / no data")
        page.screenshot(path=str(OUTPUT_DIR / "01-data-ready.png"), full_page=True)
        return

    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUTPUT_DIR / "01-data-ready.png"), full_page=True)
    record("正常数据态", True, "data loaded")


# ═══════════════════ SCENARIO B ═══════════════════
def B_slow_load(page):
    ap("\n=== B: slow first load ===")
    if not task_count_visible(page):
        ap("  SKIP: no data")
        record("首次慢加载", False, "no data")
        return

    # delay overview then full page reload → clean React mount
    with OverviewDelay(page, 2000):
        ap("  reloading for fresh React mount ...")
        page.reload(wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(400)

        sk = skeleton_visible(page)
        ap(f"  B-1 skeleton: {sk}")
        task = task_count_visible(page)
        ap(f"  B-2 task hidden: {not task}")

        page.screenshot(path=str(OUTPUT_DIR / "02-initial-loading.png"), full_page=True)

    page.wait_for_selector("text=任务总数", timeout=30000)
    page.wait_for_timeout(800)

    sk_gone = not skeleton_visible(page)
    ap(f"  B-3 skeleton gone: {sk_gone}")
    page.screenshot(path=str(OUTPUT_DIR / "03-initial-loaded.png"), full_page=True)

    record("首次慢加载", sk and (not task) and sk_gone, f"sk={sk}->done")


# ═══════════════════ SCENARIO C ═══════════════════
def C_refresh(page):
    ap("\n=== C: refresh with data ===")
    if not task_count_visible(page):
        ap("  SKIP: no data")
        record("已有数据刷新", False, "no data")
        return

    with OverviewDelay(page, 2000):
        ok = toggle_month(page)
        if not ok:
            ap("  cannot toggle month")
            record("已有数据刷新", False, "cannot toggle filter")
            return

        # Poll for updating indicator — it may appear after a short React render cycle
        old = task_count_visible(page)
        upd = updating_visible(page)
        for _ in range(5):
            if upd:
                break
            page.wait_for_timeout(200)
            upd = updating_visible(page)
            old = task_count_visible(page)
        ap(f"  C-1 old data: {old}")
        ap(f"  C-2 updating: {upd}")
        sk = skeleton_visible(page)
        ap(f"  C-3 skeleton: {not sk}")

        page.screenshot(path=str(OUTPUT_DIR / "04-refreshing.png"), full_page=True)

    page.wait_for_selector("text=任务总数", timeout=30000)
    page.wait_for_timeout(800)

    upd_gone = not updating_visible(page)
    ap(f"  C-4 updating gone: {upd_gone}")
    page.screenshot(path=str(OUTPUT_DIR / "05-refresh-complete.png"), full_page=True)

    record("已有数据刷新", old and upd and (not sk) and upd_gone)


# ═══════════════════ SCENARIO D ═══════════════════
def D_refresh_error(page):
    ap("\n=== D: refresh error ===")
    if not task_count_visible(page):
        ap("  SKIP: no data")
        record("刷新失败保留旧数据", False, "no data")
        record("错误恢复", False, "no data")
        return

    with OverviewFail(page):
        ap("  overview -> 500")
        ok = toggle_month(page)
        if not ok:
            ap("  cannot toggle month")
            record("刷新失败保留旧数据", False, "cannot trigger")
            record("错误恢复", False, "cannot trigger")
            return
        page.wait_for_timeout(2500)

        # debug
        url = page.evaluate("() => window.location.href")
        ap(f"  url: {url}")
        txt = page.locator("body").inner_text()[:300]
        ap(f"  body: {txt}")

        old = task_count_visible(page)
        ap(f"  D-1 old data: {old}")
        err = error_banner_visible(page)
        ap(f"  D-2 error banner: {err}")
        sk = skeleton_visible(page)
        ap(f"  D-3 skeleton: {not sk}")
        blk = blocked_visible(page)
        ap(f"  D-blocked: {blk}")

        page.screenshot(path=str(OUTPUT_DIR / "06-refresh-error.png"), full_page=True)

    # recover
    ap("  unroute 500, recovering ...")
    goto_dashboard(page)
    page.wait_for_timeout(1500)

    err_gone = not error_banner_visible(page)
    ap(f"  D-4 error gone: {err_gone}")

    page.screenshot(path=str(OUTPUT_DIR / "07-error-recovered.png"), full_page=True)

    record("刷新失败保留旧数据", old and err and (not sk) and (not blk))
    record("错误恢复", err_gone)


# ═══════════════════ SCENARIO E ═══════════════════
def E_favicon(page):
    ap("\n=== E: favicon + console ===")
    CONSOLE_ERRORS.clear(); PAGE_ERRORS.clear()

    page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    href = page.evaluate("() => document.querySelector(\"link[rel='icon']\")?.getAttribute('href') || null")
    ap(f"  favicon: {href}")
    fav_ok = href is not None and "favicon.ico" not in str(href)

    ce = len(CONSOLE_ERRORS)
    pe = len(PAGE_ERRORS)
    ap(f"  console: {ce}, page errors: {pe}")
    for c in CONSOLE_ERRORS[:5]:
        ap(f"    [{c['type']}] {c['text'][:150]}")

    max_up = any("Maximum update depth" in e for e in PAGE_ERRORS)

    record("favicon", fav_ok, f"href={href}")
    record("Console", pe == 0 and not max_up, f"ce={ce} pe={pe}")


# ═══════════════════ REPORT ═══════════════════
def gen_report():
    lines = [
        "# Dashboard Local Browser Acceptance Report",
        "",
        f"**Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "**Branch**: fix-dashboard-loading-and-static-assets",
        "**Commit**: 54a6878e234cfe5c2649d2c131c2dc3905f06686",
        f"**Frontend**: {FRONTEND_URL}",
        f"**Backend**: http://127.0.0.1:8008",
        f"**User**: {USERNAME}",
        "",
        "## Results", "",
        "| Scenario | Result | Detail |",
        "|----------|--------|--------|",
    ]
    for n, r in RESULTS.items():
        lines.append(f"| {n} | **{'PASS' if r['passed'] else 'FAIL'}** | {r.get('detail','')} |")

    lines += ["", "## Screenshots", "",
              "| Scenario | File |",
              "|----------|------|",
              "| A normal | 01-data-ready.png |",
              "| B skeleton | 02-initial-loading.png |",
              "| B loaded | 03-initial-loaded.png |",
              "| C refreshing | 04-refreshing.png |",
              "| C done | 05-refresh-complete.png |",
              "| D error | 06-refresh-error.png |",
              "| D recovered | 07-error-recovered.png |"]

    (OUTPUT_DIR / "acceptance-report.md").write_text("\n".join(lines), encoding="utf-8")
    ap("report saved")


def main():
    ensure_env()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
            ap("[browser] Chrome")
        except:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ap("[browser] Chromium")

        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        ctx.tracing.start(screenshots=True, snapshots=True)
        page = ctx.new_page()

        page.on("console", lambda m: (CONSOLE_ERRORS.append({"text": m.text, "type": m.type}) if m.type in ("error", "warning") else None))
        page.on("pageerror", lambda e: PAGE_ERRORS.append(str(e)))

        try:
            login(page)
            A_normal(page)
            B_slow_load(page)
            C_refresh(page)
            D_refresh_error(page)
            E_favicon(page)
            gen_report()
        except Exception as e:
            ap(f"\nABORT: {e}")
            import traceback; traceback.print_exc()
            page.screenshot(path=str(OUTPUT_DIR / "error-snapshot.png"), full_page=True)
        finally:
            ctx.tracing.stop(path=str(OUTPUT_DIR / "playwright-trace.zip"))
            browser.close()

    all_ok = all(r["passed"] for r in RESULTS.values())
    ap("\n" + "=" * 50)
    ap(f"ACCEPTANCE: {'ALL PASS' if all_ok else 'SOME FAIL'}")
    for n, r in RESULTS.items():
        ap(f"  {'[PASS]' if r['passed'] else '[FAIL]'} {n}")


if __name__ == "__main__":
    main()
