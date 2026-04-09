from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import threading
import json
from pageindex.page_index import page_index_main
from pageindex.utils import ConfigLoader
from pageindex.database import init_db, SessionLocal
from pageindex.models import Job

app = Flask(__name__)
CORS(app)

# Initialize Database on startup
init_db()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def process_document(job_id, file_path, options):
    db = SessionLocal()
    try:
        # Update status to processing
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'processing'
            db.commit()
        
        # Load config with user options
        config_loader = ConfigLoader()
        opt = config_loader.load(options)
        
        # Run PageIndex processing
        result = page_index_main(file_path, opt)
        
        # Save result to database
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'completed'
            job.result = result
            db.commit()
            
    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'failed'
            job.error = str(e)
            db.commit()
        print(f"Error processing job {job_id}: {e}")
    finally:
        db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        job_id = str(uuid.uuid4())
        filename = f"{job_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Extract options from request
        options = {
            'model': request.form.get('model'),
            'toc_check_page_num': int(request.form.get('toc_check_page_num', 20)),
            'max_page_num_each_node': int(request.form.get('max_page_num_each_node', 10)),
            'max_token_num_each_node': int(request.form.get('max_token_num_each_node', 20000)),
            'if_add_node_id': request.form.get('if_add_node_id', 'yes'),
            'if_add_node_summary': request.form.get('if_add_node_summary', 'yes'),
            'if_add_doc_description': request.form.get('if_add_doc_description', 'no'),
            'if_add_node_text': request.form.get('if_add_node_text', 'no'),
        }
        
        # Clean up None values
        options = {k: v for k, v in options.items() if v is not None}
        
        # Create Job in Database
        db = SessionLocal()
        try:
            new_job = Job(
                id=job_id,
                filename=file.filename,
                status='pending',
                options=options
            )
            db.add(new_job)
            db.commit()
        finally:
            db.close()
        
        # Start processing in background
        thread = threading.Thread(target=process_document, args=(job_id, file_path, options))
        thread.start()
        
        return jsonify({'job_id': job_id})

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job.id,
            'filename': job.filename,
            'status': job.status,
            'error': job.error,
            'created_at': job.created_at.isoformat() if job.created_at else None
        })
    finally:
        db.close()

@app.route('/api/result/<job_id>', methods=['GET'])
def get_result(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
            
        if job.status != 'completed':
            return jsonify({'error': 'Result not ready', 'status': job.status}), 400
        
        return jsonify(job.result)
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
