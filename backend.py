from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import fitz  # PyMuPDF for PDF
import docx
import openai
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

openai.api_key = "YOUR_OPENAI_KEY"  # Replace with your OpenAI API Key

analytics_data = {"uploads": 0, "quizzes": 0, "scores": []}

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(filepath):
    if filepath.endswith(".pdf"):
        text=""
        doc=fitz.open(filepath)
        for page in doc:
            text+=page.get_text()
        return text
    elif filepath.endswith(".docx"):
        doc=docx.Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    elif filepath.endswith(".txt"):
        with open(filepath,"r",encoding="utf-8") as f:
            return f.read()
    return ""

def ai_generate(prompt,max_tokens=300):
    try:
        response=openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a helpful study assistant."},
                      {"role":"user","content":prompt}],
            max_tokens=max_tokens
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"AI error: {str(e)}"

@app.route("/process",methods=["POST"])
def process_file():
    if 'file' not in request.files:
        return jsonify({"error":"No file uploaded."}),400
    file=request.files['file']
    if file.filename=='' or not allowed_file(file.filename):
        return jsonify({"error":"Invalid file type."}),400

    filename=secure_filename(file.filename)
    filepath=os.path.join(app.config['UPLOAD_FOLDER'],filename)
    file.save(filepath)
    analytics_data['uploads']+=1

    text=extract_text(filepath)
    if not text:
        return jsonify({"error":"Could not extract text."}),400

    # AI Outputs
    summary=ai_generate(f"Summarize the following study notes:\n{text}",max_tokens=300)
    flashcards=ai_generate(f"Create 5 flashcards (Q/A) from these notes:\n{text}",max_tokens=300)
    mcqs_raw=ai_generate(f"Create 3 multiple choice questions with 4 options each, mark the correct answer in JSON format:\n{text}",max_tokens=300)
    recommendations=ai_generate(f"Suggest a personalized study plan based on these notes:\n{text}",max_tokens=300)

    try:
        mcqs=json.loads(mcqs_raw)
    except:
        mcqs=[{"question":"MCQs could not be generated.","options":[],"answer":""}]

    return jsonify({
        "summary":summary,
        "flashcards":flashcards,
        "mcqs":mcqs,
        "recommendations":recommendations
    })

@app.route("/submit_quiz",methods=["POST"])
def submit_quiz():
    data=request.json
    score=data.get("score",0)
    analytics_data['quizzes']+=1
    analytics_data['scores'].append(score)
    return jsonify({"message":"Quiz submitted successfully!"})

@app.route("/analytics",methods=["GET"])
def analytics():
    avg_score=sum(analytics_data['scores'])/len(analytics_data['scores']) if analytics_data['scores'] else 0
    return jsonify({
        "uploads":analytics_data['uploads'],
        "quizzes":analytics_data['quizzes'],
        "avg_score":avg_score,
        "recent":analytics_data['scores'][-5:]
    })

if __name__=="__main__":
    app.run(debug=True)
