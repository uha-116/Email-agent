import json
import re
from gemini_client import call_gemini
from prompts import FINAL_ANALYSIS_PROMPT


def extract_json(text: str) -> dict:
    """
    Extracts valid JSON from LLM output.
    Handles ```json ... ``` and plain JSON.
    """
    if not text:
        raise ValueError("Empty response")

    # Remove markdown code fences if present
    text = text.strip()

    # Case 1: ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    # Case 2: extra text before/after JSON
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace == -1 or last_brace == -1:
        raise ValueError("No JSON object found")

    json_text = text[first_brace:last_brace + 1]
    return json.loads(json_text)


def analyze_email(clean_email_text: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAIL CONTENT:\n" + clean_email_text
    raw_response = call_gemini(prompt)

    try:
        return extract_json(raw_response)
    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": str(e),
            "raw_response": raw_response
        }
 

text = """ 
--- IMAGE OCR TEXT ---

Linked
VNRVJIET
Download on the
App Store
GET ITON
> Google Play
Bhieeelin

From: LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>
Subject: “software engineer”: Meta - Software Engineer, Audio and more
Date: Tue, 20 Jan 2026 03:42:27 +0000 (UTC)

--- EMAIL BODY ---

Your job alert for software engineer in Hyderabad
New jobs match your preferences.
Software Engineer, Audio
Meta
Hyderabad
This company is actively hiring
View job: https://www.linkedin.com/comm/jobs/view/4308315201/?trackingId=UsFFnzNB4LDOO6wdHcEUPw%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
Software Development Engineer, India Operations
Amazon
Hyderabad
7 connections
View job: https://www.linkedin.com/comm/jobs/view/4364260762/?trackingId=dfzT3afOcfvwVCR9miAElQ%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
Software Development Engineer, Delivery Experience
Amazon
Hyderabad
This company is actively hiring
View job: https://www.linkedin.com/comm/jobs/view/4364380523/?trackingId=o5G4Sy%2BKis0H%2Fca1NRw1yw%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
Custom Software Engineer
Accenture services Pvt Ltd
Hyderabad
1 school alum
View job: https://www.linkedin.com/comm/jobs/view/4360451790/?trackingId=l%2BC6H6aLBa0Du3VS0pWUQg%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
Software Engineer, Staff A
Blackbaud India
Hyderabad
View job: https://www.linkedin.com/comm/jobs/view/4273843892/?trackingId=3quEB7jsinxH1trCZTvYQA%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
Software Developer 4
Oracle
Hyderabad
10 connections
View job: https://www.linkedin.com/comm/jobs/view/4340802919/?trackingId=OGansrKobhShP9fFnoYv5Q%3D%3D&refId=yClyZxT3%2B7R7yAXVKaP%2FEA%3D%3D&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-jobcard_body_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
---------------------------------------------------------
See all jobs on LinkedIn: https://www.linkedin.com/comm/jobs/search?keywords=software+engineer&distance=25&geoId=105556991&f_TPR=a1768738313-&sortBy=R&origin=JOB_ALERT_EMAIL&originToLandingJobPostings=4308315201,4364260762,4364380523,4360451790,4273843892,4340802919&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-primary_job_list-0-see_all_jobs_text_1739692338&trkEmail=eml-email_job_alert_digest_01-primary_job_list-0-see_all_jobs_text_1739692338-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
Job search smarter with Premium
https://www.linkedin.com/comm/premium/products/?upsellOrderOrigin=email_job_alert_digest_taj_upsell&utype=job&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-job~alert-0-premium~upsell~text&trkEmail=eml-email_job_alert_digest_01-job~alert-0-premium~upsell~text-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
----------------------------------------
This email was intended for Uharika Burjukindi (Final Year B.Tech Student at VNRVJIET | PwC Launchpad 2026)
Learn why we included this: https://www.linkedin.com/help/linkedin/answer/4788?lang=en&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-SecurityHelp-0-textfooterglimmer&trkEmail=eml-email_job_alert_digest_01-SecurityHelp-0-textfooterglimmer-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
You are receiving Job Alert emails.
Manage your job alerts: https://www.linkedin.com/comm/jobs/alerts?lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-footer-0-manage_alerts_button_text&trkEmail=eml-email_job_alert_digest_01-footer-0-manage_alerts_button_text-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
Unsubscribe: https://www.linkedin.com/job-alert-email-unsubscribe?savedSearchId=1739692338&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&ek=email_job_alert_digest_01&e=kog19o-mkm1sv8b-xy&eid=kog19o-mkm1sv8b-xy&m=unsubscribe&ts=footerGlimmer&li=0&t=plh · Help: https://www.linkedin.com/help/linkedin/answer/67?lang=en&lipi=urn%3Ali%3Apage%3Aemail_email_job_alert_digest_01%3ByJ3wxikBTviPWrXuX7CkEQ%3D%3D&midToken=AQG1la21CSCOig&midSig=0VsgAWOXF-Ss41&trk=eml-email_job_alert_digest_01-help-0-textfooterglimmer&trkEmail=eml-email_job_alert_digest_01-help-0-textfooterglimmer-null-kog19o~mkm1sv8b~xy-null-null&eid=kog19o-mkm1sv8b-xy&otpToken=MTMwNzFiZTAxMTI2Y2JjMGIwMmEwZmViNDExOGVmYmM4N2NlZDU0NTlmYTg4NjZmN2JjZjA4NmE0ODUyNTlmMGZmZGNkN2U5NDlmNWVlZjI2ZTgwY2RjYWQ3YTNjMWExZTA4MGQxNWM3YjdmYjczMDg5NDE1YmY0LDEsMQ%3D%3D
© 2026 LinkedIn Corporation, 1zwnj000 West Maude Avenue, Sunnyvale, CA 94085.
LinkedIn and the LinkedIn logo are registered trademarks of LinkedIn.
Meta Software Engineer, Audio: As an Audio Embedded Engineer at Meta, you’ll…
Your job alert for
software engineer
New jobs in Hyderabad match your preferences.
Software Engineer, Audio
Meta · Hyderabad
Actively recruiting
Software Development Engineer, India Operations
Amazon · Hyderabad
7 connections
Software Development Engineer, Delivery Experience
Amazon · Hyderabad
Actively recruiting
Custom Software Engineer
Accenture services Pvt Ltd · Hyderabad (On-site)
1 school alum
Software Engineer, Staff A
Blackbaud India · Hyderabad
Software Developer 4
Oracle · Hyderabad (On-site)
10 connections
See all jobs
Job search smarter with Premium
Try Premium for ₹0
Get the new LinkedIn desktop app
Also available on mobile
This email was intended for Uharika Burjukindi (Final Year B.Tech Student at VNRVJIET | PwC Launchpad 2026)
Learn why we included this.
You are receiving Job Alert emails.
Manage job alerts
·
Unsubscribe
·
Help
© 2026 LinkedIn Corporation, 1 000 West Maude Avenue, Sunnyvale, CA 94085.
LinkedIn and the LinkedIn logo are registered trademarks of LinkedIn.
"""

store=analyze_email(text)
print(store)