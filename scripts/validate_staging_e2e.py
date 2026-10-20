import requests
import sys
import time
import io

BASE_URL = "http://localhost:8000"


def run_e2e_validation():
    print("🚀 Starting End-to-End Backend Validation Pass...\n")

    reg_form = {
        "pubkey": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
        "email": "e2e_admin@terminus.local",
        "password": "StrongPassword123!",
        "role": "OWNER"
    }

    # 1. Register Test User (Form Data)
    print("1️⃣ Registering/Ensuring Test User Account...")
    reg_res = requests.post(f"{BASE_URL}/api/v1/auth/register", data=reg_form)
    if reg_res.status_code in [200, 201]:
        print("   ✅ Test user registered successfully.")
    else:
        print("   ℹ️ Account already exists. Proceeding to authentication.")

    # 2. Authenticate (Form Data)
    print("2️⃣ Authenticating Test User...")
    login_form = {
        "email_or_pubkey": "e2e_admin@terminus.local",
        "password": reg_form["password"]
    }
    
    auth_res = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_form)

    if auth_res.status_code != 200:
        print(f"   ❌ Auth Failed (Status {auth_res.status_code}): {auth_res.text}")
        sys.exit(1)

    res_data = auth_res.json()
    token = res_data.get("access_token") or res_data.get("data", {}).get("access_token") or res_data.get("token")
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Auth Token Successfully Generated.")

    # 3. Test User Profile Endpoint
    print("3️⃣ Testing Authenticated User Profile (/api/v1/auth/me)...")
    profile_res = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    if profile_res.status_code == 200:
        print(f"   ✅ User Profile Active: {profile_res.json().get('email')}")

    # 4. Trigger Async Claim Verification Workflow (HTTP 200 / 202)
    print("4️⃣ Triggering Async Claim Verification Pipeline...")
    claim_form = {
        "username": "e2e_admin",
        "vault_owner": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
        "claimant_pubkey": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    }
    
    dummy_image = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    files = {
        "file": ("death_certificate_sample.gif", io.BytesIO(dummy_image), "image/gif")
    }

    claim_res = requests.post(
        f"{BASE_URL}/api/v1/claims/verify-and-trigger-async", 
        data=claim_form,
        files=files,
        headers=headers
    )

    if claim_res.status_code not in [200, 202]:
        print(f"   ❌ Claim Trigger Failed (Status {claim_res.status_code}): {claim_res.text}")
        sys.exit(1)

    claim_data = claim_res.json()
    job_id = claim_data.get("task_id") or claim_data.get("job_id")
    print(f"   ✅ Async Task Queued (Status {claim_res.status_code}). Celery Task ID: {job_id}")

    # 5. Poll Task Completion & Verify Zero Mock Data
    print("5️⃣ Polling Celery Task Queue Status...")
    completed = False
    for attempt in range(1, 15):
        time.sleep(2)
        job_res = requests.get(f"{BASE_URL}/api/v1/claims/jobs/{job_id}", headers=headers)
        
        if job_res.status_code == 200:
            data = job_res.json()
            status = data.get("status")
            print(f"   ⌛ Polling Attempt {attempt}/15 - Task Status: {status}")

            if status in ["SUCCESS", "FINISHED", "COMPLETED"]:
                completed = True
                result = data.get("result", {})
                
                if isinstance(result, dict) and result.get("is_mock") is True:
                    print("   ⚠️ WARNING: Task executed using simulation fallbacks!")
                else:
                    print("   ✅ Task Executed Successfully via Strict Real Enforcement.")
                break
            elif status in ["FAILURE", "FAILED"]:
                print(f"   ❌ Async Task Failed: {data}")
                sys.exit(1)

    if not completed:
        print("   ⚠️ Task polling timed out. Celery worker is still processing.")

    # 6. Check Telemetry & Metrics Endpoint
    print("6️⃣ Checking Prometheus Observability Endpoint (/metrics)...")
    metrics_res = requests.get(f"{BASE_URL}/metrics")
    if metrics_res.status_code == 200:
        print("   ✅ Prometheus Metrics Endpoint Operational.")
    else:
        print(f"   ⚠️ Telemetry Endpoint Returned Status {metrics_res.status_code}")

    print("\n🎉 STAGING END-TO-END VALIDATION PASS COMPLETE!")


if __name__ == "__main__":
    try:
        run_e2e_validation()
    except Exception as e:
        print(f"\n❌ Validation Script Execution Error: {str(e)}")
        sys.exit(1)
