import os
import json
import datetime
import sys
import pymysql
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google import genai
from google.genai import types

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "Naresh_solanki")

# Gemini Setup
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# --- MySQL Configuration ---
def get_db_connection():
    try:
        return pymysql.connect(
            # Railway provides these via the Variables tab
            host=os.getenv("MYSQLHOST"), 
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT", 3306)),
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def init_db():
    print("\n--- [START] Database Initialization ---")
    try:
        conn = get_db_connection()
        print("✅ MySQL Connection Successful!")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                phone VARCHAR(20),
                email VARCHAR(255),
                post_applied VARCHAR(100),
                skills TEXT,
                score VARCHAR(20),
                percentage FLOAT,
                test_date DATETIME
            )
        """)
        conn.commit()
        print("✅ Database Table is Ready!")
        cursor.close()
        conn.close()
        print("--- [FINISH] Database Initialization ---\n")
    except Exception as e:
        print(f"\n❌ DATABASE ERROR: {e}")
        sys.exit(1)

init_db()

@app.route('/')
def index():
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
    session['experience'] = float(request.form.get('experience', 0))
    session['selected_skills'] = request.form.getlist('skills') 
    return render_template('instructions.html')

@app.route('/get_ai_questions')
def get_ai_questions():
    post = session.get('post_applied')
    exp = session.get('experience')
    skills = session.get('selected_skills', [])
    
    # Using your preferred model
    MODEL_ID = "gemini-2.5-flash-lite" 
    
    prompt = (
        f"Generate exactly 30 technical MCQs for a {post} role with {exp} years of experience. "
        f"Skills: {', '.join(skills)}. "
        "Return ONLY a JSON list of objects. Each object must have: "
        "\"q\" (string), \"options\" (list of 4 strings), and \"a\" (integer 0-3)."
    )

    try:
        # Increase token limit to 8192 to prevent cutting off the 30 questions
        response = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=8192,
                response_mime_type="application/json"
            )
        )
        
        text_response = response.text.strip()
        
        # Simple cleanup if markdown is present
        if "```" in text_response:
            text_response = text_response.split("```")[1].replace("json", "").strip()
            
        # Validate JSON before returning
        json.loads(text_response)
        
        return text_response 
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_test', methods=['POST'])
def start_test():
    questions_json = request.form.get('questions_data')
    if not questions_json:
        return redirect(url_for('skills_page'))
    
    questions = json.loads(questions_json)
    session['correct_answers'] = [q['a'] for q in questions]
    return render_template('test.html', questions=questions)

@app.route('/submit_test', methods=['POST'])
def submit_test():
    score = 0
    total_questions = 30 # Back to your required 30
    detailed_results = []
    ans_key = session.get('correct_answers', [])
    
    for i in range(total_questions):
        q_text = request.form.get(f'q_text_{i}')
        selected_idx = request.form.get(f'q{i}') 
        correct_idx = str(ans_key[i]) if i < len(ans_key) else None
        
        options = [
            request.form.get(f'q{i}_opt_text_0'),
            request.form.get(f'q{i}_opt_text_1'),
            request.form.get(f'q{i}_opt_text_2'),
            request.form.get(f'q{i}_opt_text_3')
        ]
        
        try:
            user_ans_text = options[int(selected_idx)] if selected_idx is not None else "Not Answered"
            corr_ans_text = options[int(correct_idx)] if correct_idx is not None else "Unknown"
            is_correct = (str(selected_idx) == correct_idx)
        except:
            user_ans_text = "Not Answered"
            corr_ans_text = "N/A"
            is_correct = False

        if is_correct: 
            score += 1
            
        detailed_results.append({
            'num': i + 1,
            'question': q_text,
            'user_answer': user_ans_text,
            'correct_answer': corr_ans_text,
            'all_options': options,
            'is_correct': is_correct
        })
            
    percentage = round((score / total_questions) * 100, 2)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO assessment_results 
            (name, phone, email, post_applied, skills, score, percentage, test_date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (session.get('name'), session.get('phone'), session.get('email'), 
                  session.get('post_applied'), ", ".join(session.get('selected_skills', [])),
                  f"{score}/{total_questions}", percentage, datetime.datetime.now())
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database Insertion Error: {e}")

    session.pop('correct_answers', None)
    return render_template('result.html', score=score, total=total_questions, percentage=percentage, results=detailed_results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)