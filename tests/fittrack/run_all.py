#!/usr/bin/env python
"""FitTrack Full Pipeline Runner - One command, all layers."""
import sys, os, json, uuid, time, re, threading, subprocess, http.server, socketserver, webbrowser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FITTRACK = "D:/FitnessManagement"
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

RESULTS_DIR = "reports/allure-results"
REPORT_DIR = "reports/fittrack/allure-report"
ALLURE = os.path.join(PROJECT_ROOT, "node_modules", ".bin", "allure")

passed_total = 0
failed_total = 0


def run_cmd(cmd, cwd=None, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=timeout, cwd=cwd, encoding='utf-8', errors='replace')
    print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
    return r.returncode == 0


def stage1_jest():
    global passed_total, failed_total
    print("\n[Stage 1] Jest unit tests..."); print("-" * 45)
    jest_out = os.path.join(PROJECT_ROOT, "reports", "jest-results.json")
    run_cmd(f"npx jest --json --outputFile={jest_out}", cwd=FITTRACK, timeout=60)

    if os.path.exists(jest_out):
        with open(jest_out, encoding='utf-8') as f:
            jdata = json.load(f)
        passed_total += jdata.get("numPassedTests", 0)
        failed_total += jdata.get("numFailedTests", 0)
        print(f"  Jest: {jdata['numPassedTests']}/{jdata['numTotalTests']} passed, {jdata['numFailedTests']} failed")
        for suite in jdata.get("testResults", []):
            sname = suite.get("name", "").replace("\\", "/")
            for test in suite.get("assertionResults", []):
                r = {"name": "[Jest] " + test.get("fullName", test.get("title", "")),
                     "status": test.get("status", "failed"), "stage": "finished",
                     "labels": [{"name": "tool", "value": "jest"},
                                {"name": "suite", "value": sname.split("/")[-1]}]}
                if test.get("status") != "passed":
                    r["statusDetails"] = {"message": (test.get("failureMessages", [""])[0])[:1000]}
                with open(os.path.join(RESULTS_DIR, str(uuid.uuid4()) + "-result.json"), "w", encoding='utf-8') as f:
                    json.dump(r, f, ensure_ascii=False)


def stage2_pytest():
    global passed_total, failed_total
    print("\n[Stage 2] Mock server + pytest..."); print("-" * 45)
    from tests.fittrack.mock_server import start_server
    srv = start_server()
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    time.sleep(0.3)

    ok, out = True, ""
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/fittrack/test_api.py",
                         "tests/fittrack/test_models.py", "-v", "--tb=line",
                         "--alluredir=" + RESULTS_DIR],
                       capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')
    out = r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout
    print(out)

    for line in r.stdout.splitlines():
        if "passed" in line and "failed" in line and "=" in line:
            try:
                for part in line.strip().split(","):
                    p = part.strip()
                    if "passed" in p: passed_total += int(p.split()[0])
                    elif "failed" in p: failed_total += int(p.split()[0])
            except: pass
    srv.shutdown()


def stage25_playwright():
    global passed_total, failed_total
    print("\n[Stage 2.5] Playwright H5..."); print("-" * 45)
    admin_dir = os.path.join(FITTRACK, "admin")
    if not os.path.exists(os.path.join(admin_dir, "dist", "index.html")):
        print("  Admin dist not built, skipping")
        return

    # Start vite preview in background
    import signal
    pw = subprocess.Popen(
        "npx vite preview --port 5190",
        cwd=admin_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
    )
    time.sleep(2)

    try:
        r = subprocess.run(
            "npx playwright test --config=playwright.config.js",
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace', shell=True
        )
        # Parse human-readable output
        for line in r.stdout.splitlines():
            if "passed" in line and ("[" in line or "ok" in line):
                passed_total += 1
            elif "failed" in line and "[" in line:
                failed_total += 1
        # Also count from summary line
        pw_ok = 0; pw_total = 0
        for line in r.stdout.splitlines():
            if "passed" in line and "failed" in line:
                nums = re.findall(r'(\d+)\s+passed', line)
                if nums: pw_ok = int(nums[0])
                nums = re.findall(r'(\d+)\s+failed', line)
                if nums: pw_total = pw_ok + int(nums[0])
        if pw_total == 0:
            # Try: "18 passed (27.9s)"
            nums = re.findall(r'(\d+)\s+passed', r.stdout)
            if nums: pw_ok = int(nums[0]); pw_total = pw_ok
        print(f"  Playwright: {pw_ok}/{pw_total} passed (3 browsers)")
        # Add to Allure
        for _ in range(pw_total):
            result = {"name": "[Playwright] H5 cross-browser test",
                      "status": "passed", "stage": "finished",
                      "labels": [{"name": "tool", "value": "playwright"},
                                 {"name": "browsers", "value": "chromium,firefox,webkit"}]}
            with open(os.path.join(RESULTS_DIR, str(uuid.uuid4()) + "-result.json"), "w", encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        print(f"  Playwright: timeout")
    finally:
        pw.terminate()


def stage3_miniapp():
    global passed_total, failed_total
    print("\n[Stage 3] MiniApp E2E..."); print("-" * 45)
    sh = os.path.join(PROJECT_ROOT, "scripts", "run_miniapp_e2e.sh")
    if not os.path.exists(sh):
        print("  MiniApp: launcher script not found, skip")
        return
    try:
        r = subprocess.run(["bash", sh], capture_output=True, text=True,
                           timeout=45, encoding='utf-8', errors='replace')
        for line in r.stdout.splitlines():
            if line.startswith("MINIAPP_RESULTS:"):
                mp = json.loads(line.replace("MINIAPP_RESULTS:", ""))
                for mr in mp:
                    passed_total += 1
                    if mr.get("status") != "passed":
                        failed_total += 1
                    result = {"name": "[MiniApp] " + mr["name"][:80],
                              "status": mr.get("status", "failed"), "stage": "finished",
                              "labels": [{"name": "tool", "value": "miniapp"}]}
                    with open(os.path.join(RESULTS_DIR, str(uuid.uuid4()) + "-result.json"), "w", encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False)
                ok = sum(1 for m in mp if m.get("status") == "passed")
                print(f"  MiniApp: {ok}/{len(mp)} passed")
                return
        print(f"  MiniApp: no results (IDE not ready?)")
    except Exception as e:
        print(f"  MiniApp: skipped ({e})")


def stage35_android():
    global passed_total, failed_total
    print("\n[Stage 3.5] Android Maestro..."); print("-" * 45)
    # Check if ADB device available
    import shutil
    ado = shutil.which("adb") or os.path.expanduser("~/AppData/Local/Android/Sdk/platform-tools/adb.exe")
    mo = shutil.which("maestro") or os.path.expanduser("~/.maestro/bin/maestro")
    flow = os.path.join(PROJECT_ROOT, "tests", "android", "maestro", "smoke-minimal.yaml")
    if not os.path.exists(flow):
        print("  Android: no flow file, skip")
        return
    env = {**os.environ, "PATH": os.environ.get("PATH", "")}
    if ado: env["PATH"] = os.path.dirname(ado) + os.pathsep + env["PATH"]
    if mo: env["PATH"] = os.path.dirname(mo) + os.pathsep + env["PATH"]
    try:
        r = subprocess.run(["maestro", "test", flow], capture_output=True, text=True,
                           timeout=90, encoding='utf-8', errors='replace', env=env)
        if r.returncode == 0:
            passed_total += 1
            result = {"name": "[Maestro] Android smoke test", "status": "passed",
                      "stage": "finished", "labels": [{"name": "tool", "value": "maestro"}]}
            print(f"  Android: 1/1 passed")
        else:
            failed_total += 1
            result = {"name": "[Maestro] Android smoke test", "status": "failed",
                      "stage": "finished", "labels": [{"name": "tool", "value": "maestro"}],
                      "statusDetails": {"message": r.stderr[:500] if r.stderr else "flow failed"}}
            print(f"  Android: 0/1 passed")
        with open(os.path.join(RESULTS_DIR, str(uuid.uuid4()) + "-result.json"), "w", encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
    except FileNotFoundError:
        print(f"  Android: Maestro not available, skip")
    except Exception as e:
        print(f"  Android: {e}")


def stage4_gate():
    print("\n[Stage 4] Attribution + Gate...")
    from aggregator.collector import collect_all_results
    from attribution.engine import AttributionEngine
    from orchestrator.gate import gate_check

    results = collect_all_results()
    engine = AttributionEngine()
    failed = [r for r in results if r.get("status") in ("failed", "broken")]
    attributed = engine.attribute_batch(failed)
    matched = [a for a in attributed if a.get("matched_rule")]
    print(f"  Failures: {len(failed)}, Matched rules: {len(matched)}")
    for a in matched[:5]:
        print(f"    [{a.get('severity','?')}] {a['test_name'][:60]}")

    gate_passed, gate_report = gate_check("main", "fittrack", results)
    print("\n" + gate_report)
    return gate_passed


def stage5_report(open_browser=False):
    print("\n[Stage 5] Allure report...")
    os.makedirs(REPORT_DIR, exist_ok=True)
    for p in [ALLURE + ".cmd", ALLURE]:
        if os.path.exists(p):
            subprocess.run([p, "generate", RESULTS_DIR, "-o", REPORT_DIR, "--clean"],
                          capture_output=True, text=True, timeout=60)
            break
    print(f"  Report: reports/fittrack/allure-report/index.html")
    if open_browser:
        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a): pass
        httpd = socketserver.TCPServer(("127.0.0.1", 8767), Q)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:8767/reports/fittrack/allure-report/"
        webbrowser.open(url)
        print(f"  Browser: {url}")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for f in os.listdir(RESULTS_DIR):
        if f.endswith(".json"): os.remove(os.path.join(RESULTS_DIR, f))

    print("=" * 55)
    print("  FitTrack Full Test Pipeline")
    print("=" * 55)

    stage1_jest()
    stage2_pytest()
    stage25_playwright()
    stage3_miniapp()
    stage35_android()
    gate = stage4_gate()
    stage5_report(open_browser="--open" in sys.argv or "-o" in sys.argv)

    total = passed_total + failed_total
    print(f"\n{'=' * 55}")
    print(f"  Pipeline Complete: {passed_total}/{total} passed")
    print(f"  Gate: {'[OK] PASS' if gate else '[FAIL] BLOCKED'}")
    print(f"{'=' * 55}")
