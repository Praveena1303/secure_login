from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from pymongo import MongoClient
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import cv2
from google.auth.transport.requests import Request
import base64
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB Setup
client = MongoClient('mongodb://localhost:27017/')
db = client['login_security']
users_collection = db['users']
login_attempts_collection = db['login_attempts']

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Gmail Authentication
def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

# Create Message for Email
def create_message(to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_string().encode()).decode()}

# Send Alert Email
def send_alert_email(user_email, alert_content):
    creds = gmail_authenticate()
    service = build('gmail', 'v1', credentials=creds)
    message = create_message(user_email, "Alert Notification", alert_content)
    try:
        service.users().messages().send(userId='me', body=message).execute()
        print("Alert email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

# Routes
@app.route("/")
def index():
    return render_template("index.html", stylesheet="style.css")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        users_collection.insert_one({'username': username, 'email': email, 'password': password})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data['email']
        password = data['password']
        user = users_collection.find_one({'email': email})
        
        if user and user['password'] == password:
            send_alert_email(email, "Successful login detected")
            session['user_id'] = str(user['_id'])
            return jsonify({"success": True})  # Respond with JSON

        # Failed login attempt
        alert_content = "Failed login attempt detected"
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                filename = f"unknown_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(filename, frame)
                alert_content += f" Image captured: {filename}"
            cap.release()
        else:
            alert_content += f" IP Address: {request.remote_addr}"
        send_alert_email(email, alert_content)
        return jsonify({"success": False})  # Respond with JSON

    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('home.html')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1", port=5000)
