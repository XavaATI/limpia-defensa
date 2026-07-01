#!/usr/bin/env python3
import urllib.request
import urllib.error
import subprocess
import json
import sys
import os
import time

# ANSI color codes
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"
RESET = "\033[0m"

log_file_path = "kali_test_suite.log"

def log(msg, color=RESET):
    clean_msg = msg
    for col in [CYAN, GREEN, RED, YELLOW, RESET]:
        clean_msg = clean_msg.replace(col, "")
    
    with open(log_file_path, "a", encoding="utf-8") as lf:
        lf.write(clean_msg + "\n")
        
    print(f"{color}{msg}{RESET}")

def print_header():
    header = fr"""{CYAN}
 _      _                 _          _____        __                      
| |    (_)_ __ ___  _ __ (_) __ _   |  __ \  ___ / _| ___ _ __  ___  __ _ 
| |    | | '_ ` _ \| '_ \| |/ _` |  | |  | |/ _ \ |_ / _ \ '_ \/ __|/ _` |
| |___ | | | | | | | |_) | | (_| |  | |__| |  __/  _|  __/ | | \__ \ (_| |
|_____| |_|_| |_| |_| .__/|_|\__,_|  |_____/ \___|_|  \___|_| |_|___/\__,_|
                    |_|                                                   
==========================================================================
              ✊ KALI-STYLE ENHANCED INTEGRATION TEST RUNNER             
==========================================================================="""
    log(header)

def make_request(url, headers=None, method="GET", body=None):
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    
    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = e.reason
        return e.code, err_body
    except Exception as e:
        return 999, str(e)

def run_tests():
    # Remove old log
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    print_header()
    
    python_cli = os.path.join(os.path.dirname(__file__), "limpia_defensa.py")
    log(f"[*] Target executable engine: {python_cli}", CYAN)
    
    # 1. Start Server on port 9999
    log("[*] Launching API server instance in background on port 9999...", CYAN)
    cmd = [sys.executable, python_cli, "api-server", "--port", "9999", "--token", "kali-token"]
    
    server_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for port to open
    time.sleep(1.5)
    
    failed_count = 0
    
    # Test 1: Port Availability
    log("[*] Test 1: Port Availability & Handshake check...", CYAN)
    status, body = make_request("http://localhost:9999/api/scan", headers={"Authorization": "Bearer kali-token"})
    if status == 200:
        log("[+] Test 1 PASS: API port 9999 successfully bound and responding.", GREEN)
    else:
        log(f"[-] Test 1 FAIL: Server did not respond properly: {body}", RED)
        failed_count += 1
        
    # Test 2: Token Auth Enforcement Check
    log("[*] Test 2: Token Authorization Enforcement...", CYAN)
    status_no_auth, body_no_auth = make_request("http://localhost:9999/api/scan")
    status_wrong_auth, body_wrong_auth = make_request("http://localhost:9999/api/scan", headers={"Authorization": "Bearer wrong-token"})
    
    if status_no_auth == 401 and status_wrong_auth == 401:
        log("[+] Test 2 PASS: Unauthorized requests successfully blocked with 401 status.", GREEN)
    else:
        log(f"[-] Test 2 FAIL: Security breach! Auth check failed: no-auth={status_no_auth}, wrong-auth={status_wrong_auth}", RED)
        failed_count += 1
        
    # Test 3: scan endpoint JSON structure check
    log("[*] Test 3: Disk Scan Endpoint response schema check...", CYAN)
    status, body = make_request("http://localhost:9999/api/scan", headers={"Authorization": "Bearer kali-token"})
    if status == 200 and "categories" in body and "summary" in body:
        log("[+] Test 3 PASS: Scan JSON metadata successfully loaded and structured.", GREEN)
    else:
        log(f"[-] Test 3 FAIL: scan structure invalid: {body}", RED)
        failed_count += 1

    # Test 4: av endpoint threat report check
    log("[*] Test 4: Antivirus Active Memory Audit check...", CYAN)
    status, body = make_request("http://localhost:9999/api/av", headers={"Authorization": "Bearer kali-token"})
    if status == 200 and "summary" in body and "threats_found" in body:
        log("[+] Test 4 PASS: AV Scan output threat-report correctly serialized.", GREEN)
    else:
        log(f"[-] Test 4 FAIL: AV report structure invalid: {body}", RED)
        failed_count += 1

    # Test 5: sandbox execution with no-network restriction checks
    log("[*] Test 5: Sandboxing Network Confinement Conformance...", CYAN)
    headers = {"Authorization": "Bearer kali-token"}
    payload = {
        "file": "/usr/bin/curl",
        "args": ["-s", "https://google.com"],
        "profile_type": "no-network"
    }
    status, body = make_request("http://localhost:9999/api/sandbox", headers=headers, method="POST", body=payload)
    if status == 200 and body.get("returncode") != 0:
        log("[+] Test 5 PASS: curl network call failed under no-network profile as restricted.", GREEN)
    else:
        log(f"[-] Test 5 FAIL: Confinement bypass or error: {body}", RED)
        failed_count += 1

    # Test 6: sandbox execution with read-only restriction checks
    log("[*] Test 6: Sandboxing Write Confinement Conformance...", CYAN)
    headers = {"Authorization": "Bearer kali-token"}
    payload = {
        "file": "/usr/bin/touch",
        "args": ["/tmp/kali_test_write.txt"],
        "profile_type": "read-only"
    }
    status, body = make_request("http://localhost:9999/api/sandbox", headers=headers, method="POST", body=payload)
    if status == 200 and "touch: /tmp/kali_test_write.txt: Operation not permitted" in body.get("stderr", ""):
        log("[+] Test 6 PASS: file write to /tmp successfully denied under read-only profile.", GREEN)
    else:
        log(f"[-] Test 6 FAIL: Write confinement bypass or unexpected outcome: {body}", RED)
        failed_count += 1

    # Test 7: bugreport system diagnostics check
    log("[*] Test 7: Bug Report System Diagnostics Serialization...", CYAN)
    status, body = make_request("http://localhost:9999/api/bugreport", headers={"Authorization": "Bearer kali-token"}, method="POST")
    if status == 200 and "os_info" in body and "system_metrics" in body and "engine_logs" in body:
        log("[+] Test 7 PASS: Diagnostics report contains active hardware specs and engine logs.", GREEN)
    else:
        log(f"[-] Test 7 FAIL: bugreport structure invalid: {body}", RED)
        failed_count += 1

    # Test 8: Store Catalog Integrity API check
    log("[*] Test 8: Store Catalog Integrity API check...", CYAN)
    status, body = make_request("http://localhost:9999/api/store/status", headers={"Authorization": "Bearer kali-token"})
    if status == 200 and body.get("integrity_passed") is True:
        log("[+] Test 8 PASS: Store Catalog integrity verified successfully.", GREEN)
    else:
        log(f"[-] Test 8 FAIL: Store status check failed: {body}", RED)
        failed_count += 1

    # Teardown background server
    log("[*] Tearing down background API test server...", CYAN)
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except Exception:
        server_process.kill()
        
    log("\n==========================================================================", YELLOW)
    if failed_count == 0:
        log("🎉 ALL TESTS PASSED SUCCESSFULLY! SYSTEM IS SECURE AND CONFINED.", GREEN)
        log(f"📝 Full logs saved to: {os.path.abspath(log_file_path)}", CYAN)
        sys.exit(0)
    else:
        log(f"❌ {failed_count} TEST(S) FAILED. VERIFY ENGINE COMPONENT COMPLIANCE.", RED)
        log(f"📝 Review detailed failures in: {os.path.abspath(log_file_path)}", CYAN)
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
