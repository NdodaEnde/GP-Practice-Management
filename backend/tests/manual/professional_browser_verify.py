"""
Live browser verification of the Professional pages after the rebuild + sweep.

Drives real Chromium (Playwright) against the running CRA dev server (:3000 ->
backend :8002). Logs in via the real /api/auth/login as the demo admin
(demo-gp-workspace-001, a Professional workspace with real EHR data), stores the
JWT in localStorage (same as the app), then visits each Professional page and
the PatientEHR tabs.

For each page it records: HTTP failures (>=400) on /api/* calls, console errors,
and a screenshot. The pass condition is "no 4xx/5xx on the page's data calls and
no console errors" — i.e. the pages actually load real data through the rebuilt,
token-scoped endpoints.

Read-only (no writes). Run: RUN_PROF_VERIFY=1 .venv/bin/python tests/manual/professional_browser_verify.py
"""
import os, sys, json, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

FE = os.environ.get("PROF_FE", "http://localhost:3000")
BE = os.environ.get("PROF_BE", "http://localhost:8002")
EMAIL = os.environ.get("PROF_EMAIL", "admin@surgiscan.com")
PASSWORD = os.environ.get("PROF_PASSWORD", "password123")
PATIENT_ID = "42d73864-6dfa-4ede-9bf8-bde07741d92e"  # Luzuko Ndzuta (real conditions/meds)
SHOT = Path("/tmp")

if os.environ.get("RUN_PROF_VERIFY") != "1":
    print("Set RUN_PROF_VERIFY=1 to run."); sys.exit(2)

# 1) Real login -> tokens
req = urllib.request.Request(f"{BE}/api/auth/login",
    data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
tok = json.loads(urllib.request.urlopen(req, timeout=15).read())
assert tok.get("access_token"), f"login failed: {tok}"
print(f"logged in as {EMAIL}; workspace token acquired")

PAGES = [
    ("dashboard", "/dashboard"),
    ("patients", "/patients"),
    ("patient_ehr_overview", f"/patients/{PATIENT_ID}"),
    ("analytics", "/analytics"),
    ("billing", "/billing"),
    ("reception", "/reception"),
    ("queue_display", "/queue/display"),
    ("financial_dashboard", "/financial-dashboard"),
    ("claims", "/claims-management"),
    ("prescriptions", f"/patients/{PATIENT_ID}/prescriptions"),
]
EHR_TABS = ["overview", "vitals", "medications", "investigations", "documents"]

results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # seed tokens on the FE origin
    page.goto(FE, wait_until="domcontentloaded")
    page.evaluate("""([a,r]) => { localStorage.setItem('access_token',a); localStorage.setItem('refresh_token',r); }""",
                  [tok["access_token"], tok.get("refresh_token", "")])

    def visit(name, path):
        api_fails, console_errs = [], []
        def on_resp(r):
            if "/api/" in r.url and r.status >= 400:
                api_fails.append(f"{r.status} {r.request.method} {r.url.split('?')[0].replace(BE,'')}")
        def on_console(m):
            if m.type == "error":
                console_errs.append(m.text[:160])
        page.on("response", on_resp)
        page.on("console", on_console)
        page.goto(f"{FE}{path}", wait_until="networkidle", timeout=30000)
        time.sleep(1.5)
        shot = SHOT / f"prof_{name}.png"
        page.screenshot(path=str(shot), full_page=True)
        page.remove_listener("response", on_resp)
        page.remove_listener("console", on_console)
        ok = not api_fails and not console_errs
        results.append((name, ok, api_fails, console_errs, str(shot)))
        print(f"  {'PASS' if ok else 'FAIL'}  {name:24} api_fails={api_fails} console_errs={console_errs}")

    for name, path in PAGES:
        visit(name, path)
        if name == "patient_ehr_overview":
            for tab in EHR_TABS:
                try:
                    page.get_by_role("tab", name=tab, exact=False).first.click(timeout=4000)
                    time.sleep(1.0)
                    page.screenshot(path=str(SHOT / f"prof_ehr_{tab}.png"), full_page=True)
                    print(f"     ehr tab '{tab}' -> /tmp/prof_ehr_{tab}.png")
                except Exception as e:
                    print(f"     ehr tab '{tab}' click skipped: {str(e)[:60]}")

    browser.close()

bad = [r for r in results if not r[1]]
print(f"\n=== {len(results)-len(bad)}/{len(results)} pages clean; {len(bad)} with issues ===")
for n, ok, af, ce, _ in bad:
    print(f"  {n}: api_fails={af} console_errs={ce}")
sys.exit(1 if bad else 0)
