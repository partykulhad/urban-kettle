#!/usr/bin/env python3
"""
Local QR generation test — no Kivy required.
Tests the full prefetch path: warmup, cold call, warm call (cached session).
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from utils.api_client import ApiClient
from config import MACHINE_ID

# QRUtils uses cv2 which may not be installed; inline what we need
try:
    from utils.qr_utils import QRUtils
    _HAS_QR_UTILS = True
except ImportError:
    _HAS_QR_UTILS = False
    print("⚠️  qr_utils unavailable (cv2 missing) — skipping PIL render test")

CUPS_TO_TEST = [1, 2, 3]

def separator(label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)

def test_qr_generation(api_client, cups, label=""):
    tag = f"[{cups} cup{'s' if cups != 1 else ''}]{f' {label}' if label else ''}"
    print(f"\n{tag} Calling generate_payment_qr()...")
    t0 = time.time()
    result = api_client.generate_payment_qr(MACHINE_ID, cups)
    elapsed = time.time() - t0

    if result is None:
        print(f"{tag} ❌ FAILED — API returned None ({elapsed:.2f}s)")
        return None

    qr_id = result.get('id', 'N/A')
    has_image = bool(result.get('imageContent'))
    amount = result.get('amount', 'N/A')
    print(f"{tag} ✅ OK in {elapsed:.2f}s — id={qr_id}, amount={amount}, hasImageContent={has_image}")

    if has_image:
        content = result['imageContent']
        print(f"{tag}    imageContent length: {len(content)} chars")
        print(f"{tag}    imageContent preview: {content[:60]}...")
        if _HAS_QR_UTILS:
            t1 = time.time()
            img = QRUtils.generate_qr_from_content(content)
            gen_time = time.time() - t1
            if img:
                print(f"{tag}    PIL image generated in {gen_time*1000:.1f}ms — size: {img.size}")
            else:
                print(f"{tag}    ❌ QRUtils.generate_qr_from_content() returned None")
    else:
        print(f"{tag}    ⚠️  No imageContent in response. Keys: {list(result.keys())}")

    return result

def main():
    separator("Step 1: API warmup (same as app startup)")
    api = ApiClient()
    t0 = time.time()
    # warmup_apis() is async, run it inline for measurement
    urls = [
        "https://kulhad.vercel.app/api/MachinesStatus",
        "https://kulhad.vercel.app/api/direct-payment",
    ]
    import requests
    for url in urls:
        try:
            r = requests.head(url, timeout=4)
            print(f"  HEAD {url.split('/')[4]} → {r.status_code}")
        except Exception as e:
            print(f"  HEAD {url} → ERROR: {e}")
    print(f"  Warmup done in {time.time()-t0:.2f}s")

    separator("Step 2: Cold call (first real QR request after warmup)")
    r1 = test_qr_generation(api, 1, label="COLD")

    separator("Step 3: Warm calls (session already open, TCP reused)")
    for cups in CUPS_TO_TEST:
        test_qr_generation(api, cups, label="WARM")

    separator("Step 4: Cancel test QRs to avoid phantom charges")
    to_cancel = []
    if r1 and r1.get('id'):
        to_cancel.append(r1['id'])
    for qr_id in to_cancel:
        try:
            resp = api.cancel_payment(qr_id)
            print(f"  Cancel {qr_id}: {'OK' if resp else 'FAILED'}")
        except Exception as e:
            print(f"  Cancel {qr_id}: ERROR {e}")

    separator("Done")

if __name__ == "__main__":
    main()
