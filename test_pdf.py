import sys
import time
import requests

# Default server endpoint
BASE_URL = "http://localhost:8000/api/v1/claims"

def run_pdf_test(pdf_path):
    print(f"📄 Uploading '{pdf_path}' to Terminus V2 backend...")
    
    try:
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path, f, "application/pdf")}
            data = {
                "username": "aggie_dev",
                "vault_owner": "11111111111111111111111111111111",
                "claimant_pubkey": "11111111111111111111111111111111"
            }
            
            # 1. Trigger Async Job
            res = requests.post(f"{BASE_URL}/verify-and-trigger-async", data=data, files=files)
            if res.status_code != 202:
                print(f"❌ Failed to submit claim ({res.status_code}): {res.text}")
                return
            
            payload = res.json()
            task_id = payload.get("task_id")
            print(f"⚡ Claim Queued Successfully! Task ID: {task_id}")

            # 2. Poll Status
            print("🔄 Waiting for Redis & Celery worker OCR results...")
            for _ in range(15):
                time.sleep(2)
                poll_res = requests.get(f"{BASE_URL}/jobs/{task_id}")
                poll_data = poll_res.json()
                status = poll_data.get("status")
                print(f"   Status: {status}")
                
                if status in ("SUCCESS", "FAILURE"):
                    print("\n🎉 Verification Completed! Worker Payload:")
                    print(poll_data)
                    break

    except FileNotFoundError:
        print(f"❌ Error: File '{pdf_path}' was not found.")
    except Exception as e:
        print(f"❌ Network Error: Is the Docker stack running? ({e})")

if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "sample.pdf"
    run_pdf_test(target_file)