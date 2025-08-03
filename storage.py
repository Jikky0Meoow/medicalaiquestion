from datetime import datetime, timedelta

user_uploads = {}
user_scores = {}

def can_upload_file(user_id):
    now = datetime.now()
    uploads = user_uploads.get(user_id, [])
    uploads = [u for u in uploads if now - u < timedelta(hours=24)]
    user_uploads[user_id] = uploads
    return len([u for u in uploads if now - u < timedelta(hours=1)]) < 2 and len(uploads) < 5

def register_file_upload(user_id):
    user_uploads.setdefault(user_id, []).append(datetime.now())

def reset_user_score(user_id):
    user_scores[user_id] = 0

def add_user_answer(user_id, is_correct):
    if is_correct:
        user_scores[user_id] += 1

def get_user_score(user_id):
    return user_scores.get(user_id, 0)