import os
import json
import csv
import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session
from google import genai
from google.genai import types

# 1. LOAD ENVIRONMENT VARIABLES
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "augmenza_career_default_123")

# 2. CONFIGURE GEMINI
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# 3. PERSISTENT STORAGE LOGIC
if os.path.exists('/data'):
    CSV_FILE = '/data/assessment_results.csv'
else:
    CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assessment_results.csv')

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Contact", "Email", "Post", "Skills", "Score", "Percentage", "Date"])

# --- ROUTES ---

@app.route('/')
def index():
    init_csv()
    return render_template('index.html')

@app.route('/details')
def details():
    return render_template('details.html')

@app.route('/save_details', methods=['POST'])
def save_details():
    session['name'] = request.form.get('name')
    session['email'] = request.form.get('email')
    session['phone'] = request.form.get('phone')
    return redirect(url_for('skills_page'))

@app.route('/skills')
def skills_page():
    posts = ["Developer", "QA Tester", "Devops", "Consultant", "Analyst", "HR Operation", "Talent Acquisition", "Client Acquisition", "Sales", "Marketing"]
    
    categories = {
        "Languages": ["Python", "JavaScript", "Java", "C#", "C++", "PHP", "Go", "Swift", "Rust", "SQL"],
        "Backend": ["ASP.NET Core", "Django", "Express.js", "FastAPI", "Flask", "Go Lang", "Node.js", "Laravel (PHP)", "Spring Boot", "Ruby on Rails"],
        "Frontend": ["React.js", "Angular", "Vue.js", "Tailwind", "Bootstrap", "MUI", "NgRx", "D3.js"],
        "Databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "MS SQL Server", "Oracle DB"],
        "Cloud & DevOps": ["AWS", "Azure", "Google Cloud", "Firebase", "Docker", "Kubernetes", "Kafka"],
        "API & Testing": ["GraphQL", "gRPC", "REST", "WebSockets", "Postman", "Swagger", "pytest"]
    }
    return render_template('skills.html', posts=posts, categories=categories)

@app.route('/generate_test', methods=['POST'])
def generate_test():
    session['post_applied'] = request.form.get('post')
    session['experience'] = request.form.get('experience')
    session['selected_skills'] = request.form.getlist('skills') 
    return redirect(url_for('test_page'))

@app.route('/test')
def test_page():
    post = session.get('post_applied')
    exp = session.get('experience')
    skills = session.get('selected_skills', [])
    
    MODEL_ID = "models/gemini-2.5-flash" 
    
    prompt = f"""
    Generate exactly 30 technical MCQs for a {post} role with {exp} years of experience.
    Focus ONLY on these skills/languages: {', '.join(skills)}.
    
    Format: A JSON list of objects.
    Each object must have:
    "q": "the question",
    "options": ["opt0", "opt1", "opt2", "opt3"],
    "a": 0 (index of correct answer)
    """

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        text_response = response.text.strip()
        if text_response.startswith("```json"):
            text_response = text_response.split("```json")[1].split("```")[0].strip()
        elif text_response.startswith("```"):
            text_response = text_response.split("```")[1].split("```")[0].strip()

        questions = json.loads(text_response)
        session['questions'] = questions 
        return render_template('test.html', questions=questions)
    
    except Exception as e:
        return f"Assessment Generation Error: {e}. Try again in a moment."

@app.route('/submit_test', methods=['POST'])
def submit_test():
    questions = session.get('questions', [])
    user_answers = []
    score = 0
    
    for i in range(len(questions)):
        selected = request.form.get(f'q{i}')
        correct = str(questions[i]['a'])
        user_answers.append(selected)
        if selected == correct:
            score += 1
            
    percentage = round((score / 30) * 100, 2)
    
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            session.get('name'), session.get('phone'), session.get('email'), 
            session.get('post_applied'), ", ".join(session.get('selected_skills', [])), 
            f"{score}/30", f"{percentage}%", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ])
    
    return render_template('result.html', score=score, percentage=percentage, 
                           questions=questions, user_answers=user_answers)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)