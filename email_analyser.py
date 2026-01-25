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
Hexa
Vv

VENURA

From: Jia from Unstop <noreply@dare2compete.news>
Subject: Volopay is hiring for the role of Backend Developer Internship!
Date: Sun, 25 Jan 2026 05:42:22 +0000

--- EMAIL BODY ---

unstop
Tap to apply!
Jobs & Internships
Hi Burjukindi, here are some top opportunities curated just for you!
Software Development Internship
stratzi.ai
Stipend:
INR 35,000
Location:
Pune
Data Analytics Internship
Hexa Solution
Stipend:
INR 27,000
Location:
Work From Home
Back End Developer Internship
BotGauge
Stipend:
INR 20,000
Location:
Work From Home
Campus Ambassador Carnival
Unstop
UI/UX Designer Internship
7s IQ Pvt. Ltd.
Stipend:
INR 10,000
Location:
Work From Home
Data Analyst Internship
Vaidsys Technologies
Stipend:
INR 15,000
Location:
Work From Home
Cloud Engineer Internship
Alactic Inc.
Stipend:
INR 7,000
Location:
South West Delhi
Training Videos and Manuals Creator Internship
Nasher Miles Pvt.Ltd
Stipend:
INR 5,000
Location:
Mumbai
Testing Engineer and QA Paid Internship
Vishvena Techno Solutions Pvt. Ltd.
Stipend:
INR 5,000
Location:
Work From Home
MERN Stack Internship
BPH Technologies LLP
Location:
Work From Home
UI/UX Designer Internship
HxP Technologies
Location:
Work From Home
Artificial Intelligence & Machine Learning Internship
Venura EdTech
Location:
Work From Home
Web Development Internship
Confluent Solutions
Location:
Work From Home
Java Internship
App Genesis Soft Solutions Private Limited
Location:
Work From Home
Market Intelligence Internship (Cloud, AI Infrastructure)
Atomity
Location:
Work From Home
Backend Developer Internship
Volopay
Location:
Bengaluru
Explore more opportunities
Free ATS resumes & competition decks from mentors at
Google, Meesho, Amazon, Accenture
& more:
Grab now!
Competition
Hiring Challenges
Quizzes
Hackathons
Internships
Jobs
Get noticed by 30,000+ employers on Unstop
Complete your profile
© 2026
Unstop
. All rights reserved.
Unsubscribe
Unsubscribe Here
"""

store=analyze_email(text)
print(store)