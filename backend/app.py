from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import re
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

load_dotenv()
app = Flask(__name__)
CORS(app)

# ✅ Gemini API Setup
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# ✅ Correct Gemini Model Initialization
model = genai.GenerativeModel(model_name="models/gemini-2.5-pro-exp-03-25")


# ✅ Extract details
def extract_info(text):
    email = re.search(r'[\w\.-]+@[\w\.-]+', text)
    phone = re.search(r'\b\d{10}\b', text)

    def extract_name(text):
        lines = text.strip().split('\n')
        for line in lines:
            if any(x in line.lower() for x in ['email', 'linkedin', 'github', 'phone']):
                continue
            if len(line.split()) <= 4 and not re.search(r'\d|http|www', line):
                return line.strip()
        return "Name not found"

    return {
        "name": extract_name(text),
        "email": email.group() if email else "",
        "phone": phone.group() if phone else "",
        "text": text
    }

# ✅ Resume Upload
@app.route("/upload", methods=["POST"])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['resume']
    if file.filename.endswith('.pdf'):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()

        extracted = extract_info(text)
        return jsonify(extracted)
    else:
        return jsonify({"error": "Unsupported file type"}), 400

@app.route("/ats-gemini", methods=["POST"])
def ats_using_gemini():
    data = request.get_json()
    resume_text = data.get("resumeText", "")
    job_text = data.get("jobText", "")

    if not resume_text or not job_text:
        return jsonify({"error": "Missing resumeText or jobText"}), 400

    prompt = f"""
You are an ATS (Applicant Tracking System) Analyzer AI.

Given the following RESUME and JOB DESCRIPTION:
----------------------------
RESUME:
{resume_text}

----------------------------
JOB DESCRIPTION:
{job_text}
----------------------------

✅ TASKS:
1. Calculate the ATS Match Score (as percentage based on keyword relevance)
2. Highlight matched skills and relevant keywords
3. Give a short summary of the resume

Format your response as JSON:
{{
  "ats_score": "score in %",
  "matched_keywords": ["keyword1", "keyword2", ...],
  "summary": "brief summary"
}}
"""

    try:
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        print("Gemini raw response:", text_response)

        # Use regex to safely extract JSON from the response
        json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
        if not json_match:
            raise ValueError("Gemini response did not contain valid JSON")

        result = json.loads(json_match.group())
        return jsonify(result)

    except Exception as e:
        print("❌ Gemini processing failed:", str(e))
        return jsonify({"error": "Gemini processing failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
