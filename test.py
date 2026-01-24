from Connection import get_gmail_service
from inbox import get_clean_email_text

# STEP 1: get gmail service
service = get_gmail_service()
print("✅ Gmail service created")

# STEP 2: fetch ONE recent email ID
results = service.users().messages().list(
    userId="me",
    maxResults=1
).execute()

messages = results.get("messages", [])

if not messages:
    print("❌ No emails found")
    exit()

message_id = messages[0]["id"]
print("📩 Testing with message ID:", message_id)

# STEP 3: extract clean email text
clean_text = get_clean_email_text(message_id)

print("\n========== CLEAN EMAIL TEXT ==========\n")
print(clean_text)   # limit output
print("\n=====================================\n")

print("✅ inbox.py works correctly")
