from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
import config
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# S3 client initialization
s3_client = boto3.client(
    's3',
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
    region_name=config.AWS_REGION
)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # Plain text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    profile = db.relationship('Profile', backref='user', uselist=False, cascade='all, delete-orphan')

class Profile(db.Model):
    __tablename__ = 'profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bio = db.Column(db.Text)
    github_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    projects = db.Column(db.Text)  # Comma-separated
    image_url = db.Column(db.String(500))
    resume_url = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Helper function to upload files to S3
def upload_to_s3(file, folder):
    if not file:
        return None
    
    timestamp = int(datetime.utcnow().timestamp())
    filename = secure_filename(file.filename)
    s3_key = f"{folder}/{session['user_id']}_{timestamp}_{filename}"
    
    try:
        s3_client.upload_fileobj(
            file,
            config.S3_BUCKET,
            s3_key,
            ExtraArgs={'ACL': 'public-read'}
        )
        return f"https://{config.S3_BUCKET}.s3.{config.AWS_REGION}.amazonaws.com/{s3_key}"
    except ClientError:
        return None

# Routes
@app.route('/')
def index():
    users_with_profiles = db.session.query(User).join(Profile).all()
    return render_template('index.html', users=users_with_profiles)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered')
            return render_template('register.html')
        
        # Create new user
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['user_email'] = user.email
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = Profile.query.filter_by(user_id=session['user_id']).first()
    
    if request.method == 'POST':
        bio = request.form.get('bio', '')
        github_url = request.form.get('github_url', '')
        linkedin_url = request.form.get('linkedin_url', '')
        projects = request.form.get('projects', '')
        
        # Handle file uploads
        image_url = None
        resume_url = None
        
        if 'image' in request.files and request.files['image'].filename:
            image_url = upload_to_s3(request.files['image'], 'images')
        
        if 'resume' in request.files and request.files['resume'].filename:
            resume_url = upload_to_s3(request.files['resume'], 'resumes')
        
        if profile:
            # Update existing profile
            profile.bio = bio
            profile.github_url = github_url
            profile.linkedin_url = linkedin_url
            profile.projects = projects
            if image_url:
                profile.image_url = image_url
            if resume_url:
                profile.resume_url = resume_url
            profile.updated_at = datetime.utcnow()
        else:
            # Create new profile
            profile = Profile(
                user_id=session['user_id'],
                bio=bio,
                github_url=github_url,
                linkedin_url=linkedin_url,
                projects=projects,
                image_url=image_url,
                resume_url=resume_url
            )
            db.session.add(profile)
        
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('dashboard.html', user=user, profile=profile)

@app.route('/portfolio/<email>')
def portfolio(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Portfolio not found')
        return redirect(url_for('index'))
    
    profile = Profile.query.filter_by(user_id=user.id).first()
    if not profile:
        flash('Portfolio not found')
        return redirect(url_for('index'))
    
    # Convert projects string to list
    projects_list = []
    if profile.projects:
        projects_list = [p.strip() for p in profile.projects.split(',') if p.strip()]
    
    return render_template('portfolio.html', user=user, profile=profile, projects=projects_list)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    results = {}
    
    # Check RDS / Database
    try:
        db.session.execute("SELECT 1")
        results['rds'] = '✅ RDS is connected and responsive.'
    except Exception as e:
        results['rds'] = f'❌ RDS check failed: {str(e)}'

    # Check S3 Bucket Access
    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION
        )
        response = s3.list_objects_v2(Bucket=config.S3_BUCKET, MaxKeys=1)
        results['s3'] = f"✅ S3 bucket '{config.S3_BUCKET}' is accessible."
    except ClientError as e:
        results['s3'] = f"❌ S3 access failed: {e.response['Error']['Message']}"
    except Exception as e:
        results['s3'] = f"❌ S3 access failed: {str(e)}"

    # EC2 Metadata (only works inside EC2)
    try:
        import requests
        instance_id = requests.get("http://169.254.169.254/latest/meta-data/instance-id", timeout=2).text
        az = requests.get("http://169.254.169.254/latest/meta-data/placement/availability-zone", timeout=2).text
        public_ip = requests.get("http://169.254.169.254/latest/meta-data/public-ipv4", timeout=2).text

        results['ec2'] = f"✅ EC2 instance running (ID: {instance_id}, AZ: {az}, Public IP: {public_ip})"
    except Exception as e:
        results['ec2'] = f"⚠️ EC2 metadata access failed: {str(e)}"

    # Print to console and return
    print("\n--- Health Check Summary ---")
    for service, status in results.items():
        print(f"{service.upper()}: {status}")

    return "<br>".join(f"<strong>{key.upper()}</strong>: {value}" for key, value in results.items())


# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)