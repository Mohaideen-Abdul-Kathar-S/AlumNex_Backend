import base64
from csv import reader
from datetime import datetime
from tkinter import Image
from bson import ObjectId
from werkzeug.utils import secure_filename
from flask import Flask, Response,jsonify,request, send_file
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
import gridfs
import io
import re
import fitz  # PyMuPDF
import google.generativeai as genai
import os,uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
import gridfs, io, datetime
import fitz  # PyMuPDF


# mongodb+srv://mohaideenabdulkathars23csd:DzSbHU79AfKPkOk6@cluster0.8v7rv29.mongodb.net/alumnex?retryWrites=true&w=majority&appName=Cluster0
# mongodb://localhost:27017/

app = Flask(__name__)
CORS(app)
try:
    # Get from environment variable
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    
    client = MongoClient(MONGO_URI)
    db = client["alumnex"]   # your DB name
    fs = gridfs.GridFS(db)
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ Failed to connect to MongoDB:", e)




# Configure Gemini with your API key (secure this in prod)
genai.configure(api_key="AIzaSyCbVGKRCYZY8Z5dy2jAMQuxdUQ4Je4NxxU")

# Initialize the model globally (reuse for efficiency)
model = genai.GenerativeModel("gemini-1.5-flash")


@app.route('/aura_assistant', methods=['POST'])
@cross_origin()
def aura_assistant_response():
    data = request.json
    user_query = data.get('query')
    req_context = dict(data.get('context', {}))  # raw context from request

    collection = db['AIChats']
    user_cols = db['users']

    if not user_query:
        return jsonify({"error": "Missing 'query' in request."}), 400

    # Fetch student context from DB if id exists
    student_context = {}
    if 'id' in req_context:
        student_context = user_cols.find_one(
            {"_id": req_context['id']},
            {"_id": 1, "fields": 1, "roll": 1}
        ) or {}

    # Personalize query
    greetings = ["hi", "hello", "hey", "hiya"]

    if user_query.strip().lower() in greetings:
        # Return a short greeting instead of long info
        response_text = f"Hi! I'm Aura Assistant, your alumni mentor. How can I help you today?"
    else:
        # Personalized mentor response based on role
        role = student_context.get('roll', 'Student')
        if role == "Student":
            full_prompt = (
                f"You are Aura Assistant, an alumni mentor chatbot. "
                f"Guide this student on academics, career, and networking: {user_query}"
            )
        elif role == "Alumni":
            full_prompt = (
                f"You are Aura Assistant, an alumni mentor chatbot. "
                f"Guide this alumni on career growth, mentorship, and opportunities: {user_query}"
            )


    try:
        response = model.generate_content(full_prompt)

        collection.insert_one({
            '_id': str(uuid.uuid4()),
            'student_id': str(student_context.get('_id', req_context.get('id'))),
            'msg': user_query,
            'response': response.text.strip()
        })

        return jsonify({"response": response.text.strip()})

    except Exception as e:
        print("Gemini API Error:", e)
        return jsonify({"error": str(e)}), 500



@cross_origin()
@app.route('/login', methods=['POST'])
def UserLogin():
    print("login")
    data = request.json
    rollno = data.get('rollno')
    password = data.get('password')
    roll = data.get('roll')
    
    collection = db['users']

    readed = collection.find_one({'_id': rollno, 'password': password})

    if readed and readed.get('roll') == roll:
        return jsonify('user login successfully completed'), 200
    
    return jsonify('error in user login'), 401



@cross_origin
@app.route('/register', methods=['POST'])
def UserRegister():
    print("Reg")
    data = request.json
    rollno = data.get('_id')
    
    
    
    collection = db['users']
    
    if(collection.find_one({'_id':rollno}) ):
        return jsonify({'message': 'user already exists!!!'}),400
    
    

    collection.insert_one(data)
    
    return jsonify({'message':'user registration sucessfully completed'}),200

from flask import request, jsonify
from flask_cors import cross_origin

@cross_origin()
@app.route('/personalinfo', methods=['POST'])
def update_personal_info():
    data = request.json
    rollno = data.get("_id")
    print(rollno,data)

    if not rollno:
        return jsonify({'message': 'Roll number is required'}), 400

    collection = db['users']

    existing_user = collection.find_one({'_id': rollno})
    if not existing_user:
        return jsonify({'message': 'User does not exist'}), 404

    

    collection.update_one({'_id': rollno}, {'$set': data})

    return jsonify({'message': 'User information updated successfully'}), 200

@cross_origin
@app.route("/getPersonalInfo",methods=["POST"])
def GetPersonalInfo():
    data = request.json
    rollno = data["rollno"]
    connection = db['users']
    res = connection.find_one({"_id":rollno})
    print("getting profile ",rollno)
    print(rollno,res)
    if not res:
        return jsonify({"message":"user is no exists"}),404

    return jsonify(res),200


@app.route('/upload-profile', methods=['POST'])
def upload_profile():
    user_id = request.form.get('user_id')
    image = request.files.get('image')

    if not user_id or not image:
        return jsonify({'message': 'Missing user_id or image'}), 400

    filename = f"{user_id}profile"
    content_type = image.content_type

    # Save image to GridFS
    image_id = fs.put(image, filename=filename, metadata={'user_id': user_id, 'contentType': content_type})

    # Update user's profile field with the image id
    db.users.update_one(
        {"_id": user_id},
        {"$set": {"profile": str(image_id)}}
    )

    return jsonify({'message': 'Profile image uploaded successfully', 'image_id': str(image_id)}), 200







@app.route('/get-resume/<rollno>', methods=['GET'])
def get_resume(rollno):
    user = db.users.find_one({"_id": rollno})
    if not user or "resume" not in user:
        return jsonify({"message": "Resume not found"}), 404

    try:
        file_id = ObjectId(user["resume"])
        file = fs.get(file_id)
        return send_file(io.BytesIO(file.read()), 
                         mimetype=file.content_type,
                         download_name=file.filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/search_users')
def search_users():
    print("searching")
    q = request.args.get('q', '')
    users = list(db.users.find({
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": {"$regex": q, "$options": "i"}}
        ]
    }, {"_id": 1, "name": 1, "roll": 1, "profile": 1}))
    print("searched result ",users)
    return jsonify(users)



@app.route('/get-profile/<user_id>', methods=['GET'])
def get_profile(user_id):
    user = db.users.find_one({"_id": user_id})
    if not user or 'profile' not in user:
        return jsonify({'message': 'No profile image found'}), 404

    try:
        file = fs.get(ObjectId(user['profile']))
        return send_file(io.BytesIO(file.read()), mimetype=file.metadata['contentType'])
    except Exception as e:
        return jsonify({'message': 'Error fetching image', 'error': str(e)}), 500

@app.route('/upload_post', methods=['POST'])
@cross_origin()
def upload_post():
    try:
        user_id = request.form.get('user_id')
        post_data = request.form.get('post_data')
        image = request.files.get('post_image')

        if not user_id or not post_data:
            return jsonify({'message': 'Missing user_id or post_data'}), 400

        import json
        post_data = json.loads(post_data)

        if image:
            filename = f"{user_id}_post_image_{post_data['postId']}"
            content_type = image.content_type
            image_id = fs.put(image, filename=filename, metadata={'user_id': user_id, 'contentType': content_type})
            post_data['postImageId'] = str(image_id)

        posts_collection = db['posts']
        result = posts_collection.insert_one(post_data)
        post_object_id = result.inserted_id

        users_collection = db['users']
        users_collection.update_one(
            {'_id': user_id},
            {'$push': {'postsids': str(post_object_id)}}
        )

        return jsonify({'message': 'Post uploaded successfully', 'post_id': str(post_object_id)}), 200

    except Exception as e:
        return jsonify({'message': 'Error uploading post', 'error': str(e)}), 500

@app.route('/get_posts', methods=['GET'])
@cross_origin()
def get_events():
    try:
        posts_collection = db['posts']
        posts = list(posts_collection.find())

        for post in posts:
            post['_id'] = str(post['_id'])  # Convert ObjectId to string
            if 'postImageId' in post:
                post['postImageId'] = str(post['postImageId'])

        return jsonify(posts), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching posts', 'error': str(e)}), 500

@app.route('/get_post/<post_id>', methods=['GET'])
@cross_origin()
def get_post(post_id):
    print("post called ", post_id)
    try:
        post = db['posts'].find_one({"_id": ObjectId(post_id)})
        if not post:
            return jsonify({'message': 'Post not found'}), 404
        post['_id'] = str(post['_id'])
        if 'postImageId' in post:
            post['postImageId'] = str(post['postImageId'])
        return jsonify(post), 200
    except Exception as e:
        return jsonify({'message': 'Error fetching post', 'error': str(e)}), 500

    
@app.route('/get_posts/<rollno>', methods=['GET'])
@cross_origin()
def get_posts(rollno):
    try:
        posts_collection = db['posts']
        posts = list(posts_collection.find())

        user_collecion = db['users']
        user = user_collecion.find_one({'_id': rollno})
        skills = [skill.strip().lower() for skill in user['TechSkills'].split(',')]
        domain = [d.strip().lower() for d in user['domain'].split(',')]
        print("skills",skills)
        print("domain",domain)
        print("post",posts)

        # Helper function to check if a post is related to the user based on reference comparison
        def is_related(reference):
            print(reference)
            # Check if any of the skills or domain is in the reference field
            return any(skill in reference for skill in skills) or any(d in reference for d in domain)

        # Temporary list for related posts and remaining posts for non-related ones
        templist = []
        remaining_posts = []

        # Separate related and non-related posts
        for post in posts:
            post['_id'] = str(post['_id'])  # Convert ObjectId to string
            if 'postImageId' in post:
                post['postImageId'] = str(post['postImageId'])

            if is_related(post.get('reference', '').lower()):
                templist.append(post)  # Add related post to templist
            else:
                remaining_posts.append(post)  # Add non-related post to remaining_posts

        # Add remaining posts to the end of templist
        templist.extend(remaining_posts)
        print(templist)

        return jsonify(templist), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching posts', 'error': str(e)}), 500

    
    
@app.route('/get-post-image/<image_id>', methods=['GET'])
@cross_origin()
def get_post_image(image_id):
    try:
        file = fs.get(ObjectId(image_id))
        return Response(file.read(), mimetype=file.content_type)
    except Exception as e:
        return jsonify({'message': 'Error fetching image', 'error': str(e)}), 500


# Like a post
@cross_origin()
@app.route('/put_like', methods=['POST'])
def put_like():
    data = request.json
    post_id = data['_id']
    rollno = data['rollno']
    print("put_like", post_id, rollno)

    posts_collection = db['posts']
    post = posts_collection.find_one({'_id': ObjectId(post_id)})

    if not post:
        return jsonify({'message': 'Post not found'}), 404

    if 'likeset' in post and rollno in post['likeset']:
        # Roll number already liked — remove it
        posts_collection.update_one(
            {'_id': ObjectId(post_id)},
            {'$pull': {'likeset': rollno}}
        )
        return jsonify({'message': 'Like removed'}), 201
    else:
        # Roll number not liked — add it
        posts_collection.update_one(
            {'_id': ObjectId(post_id)},
            {'$addToSet': {'likeset': rollno}}
        )
        return jsonify({'message': 'Like added'}), 200


# Get like count
@cross_origin()
@app.route('/get_like', methods=['POST'])
def get_like():
    data = request.json
    post_id = data['_id']
    print("getlike", post_id)  # ✅ Corrected print statement

    posts_collection = db['posts']
    res = posts_collection.find_one({'_id': ObjectId(post_id)})

    if res is None:
        return jsonify({'like_count': 0}), 404

    like_count = len(res.get('likeset', [])) 
    comments_count = len(res.get('comments',[])) # fallback to empty list if not exists
    return jsonify({'like_count': like_count,"comments_count" : comments_count}), 200


# Get like state for a specific user (whether the rollno has liked the post or not)
@cross_origin() 
@app.route('/get_likestate', methods=['POST'])
def get_like_state():
    data = request.json
    post_id = data['_id']
    rollno = data['rollno']
    print("get_likestate", post_id, rollno)

    posts_collection = db['posts']
    post = posts_collection.find_one({'_id': ObjectId(post_id)})

    if not post:
        return jsonify({'likeState': 0}), 404

    # Check if the rollno exists in the likeset
    if 'likeset' in post and rollno in post['likeset']:
        return jsonify({'likeState': 1}), 200  # User has liked
    else:
        return jsonify({'likeState': 0}), 200  # User has not liked

@app.route("/sendRequest", methods=["POST"])
@cross_origin()
def send_request():
    data = request.json
    sender = data.get("from")
    receiver = data.get("to")
    req_type = data.get("type")

    if not sender or not receiver or not req_type:
        return jsonify({"error": "Missing fields"}), 400

    connection = db['requests']

    # Check if already sent
    existing = connection.find_one({"from": sender, "to": receiver, "type": req_type, "status": "pending"})
    if existing:
        return jsonify({"message": "Request already sent"}), 409

    # Insert new request
    connection.insert_one({
        "from": sender,
        "to": receiver,
        "type": req_type,
        "status": "pending",
        "timestamp": datetime.utcnow()
    })

    return jsonify({"message": "Request sent"}), 200

@app.route('/get_requests/<rollno>', methods=['GET'])
def get_requests(rollno):
    print("to -> ",rollno)
    requests = db.requests.find({"to": rollno})
    return jsonify([{
        "id": str(req["_id"]),
        "from": req["from"],
        "to": req["to"],
        "status": req["status"]
    } for req in requests])


@app.route('/respond_request', methods=['POST'])
def respond_request():
    data = request.json
    db.requests.update_one(
        {"_id": ObjectId(data["id"])},
        {"$set": {"status": data["response"]}}  # 'Accepted' or 'Rejected'
    )
    requestcollection = db['requests']
    userscollection = db['users']
    
    res = requestcollection.find_one({"_id":ObjectId(data["id"])})
    if(res["type"]=="mentorship_request_by_alumni"):
        
        if(data["response"]=='Accepted'):
            
            userscollection.update_one(
                {"_id":res["to"]},
                {"$set":{"mentoredby":res["from"]}}
            )
            userscollection.update_one(
            {"_id": res["from"]},
            {"$push": {"mentoring": res["to"]}}
            )
    elif(res["type"]=="mentorship_request_by_student"):
        if(data["response"]=='Accepted'):
            
            userscollection.update_one(
                {"_id":res["from"]},
                {"$set":{"mentoredby":res["to"]}}
            )
            userscollection.update_one(
            {"_id": res["to"]},
            {"$push": {"mentoring": res["from"]}}
            )
    else:
        if(data["response"]=='Accepted'):
            userscollection.update_one(
                {"_id":res["from"]},
                {"$addToSet":{"connections":res["to"]}}
            )
            userscollection.update_one(
                {"_id":res["to"]},
                {"$addToSet":{"connections":res["from"]}}
            )
        

        
    return jsonify({"message": "Request updated"})


@cross_origin
@app.route('/add_connection', methods=["POST"])
def AddConnection():
    data = request.json
    rollno = data['rollno']
    frd = data['temprollno']
    conn = db['users']

    try:
        user = conn.find_one({"_id": rollno})
        if not user:
            return jsonify({"status": 0, "message": "User not found"}), 404

        connections = user.get("connections", [])

        if frd in connections:
            # If already connected, remove from both users
            conn.update_one({"_id": rollno}, {"$pull": {"connections": frd}})
            return jsonify({"status": 2, "message": "Connection Removed"}), 200
        else:
            # If not connected, add to both users
            conn.update_one({"_id": rollno}, {"$addToSet": {"connections": frd}})
            return jsonify({"status": 1, "message": "Connection Added"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": 0, "message": "Server Error"}), 500



@cross_origin
@app.route("/get_connections/<rollno>", methods=["GET"])
def get_connections(rollno):
    print("tabchat ... exe")
    conn = db['users']
    res = conn.find_one({"_id": rollno})
    
    if res is None:
        return jsonify({"error": "User not found"}), 404

    # Safely get "connections" or return empty list if not found
    connections = res.get("connections", [])
    return jsonify(connections), 200

@app.route("/get_user/<id>", methods=["GET"])
def get_user(id):
    conn = db['users']
    user = conn.find_one({"_id": id}, {"_id": 1, "name": 1})  # add other fields if needed
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200


@cross_origin
@app.route("/check_connection/<rollno>/<temprollno>", methods=["GET"])
def check_connection(rollno, temprollno):
    
    conn = db['users']
    user = conn.find_one({"_id": rollno})
    if user and temprollno in user.get("connections", []):
        print("exe 1")
        return jsonify(1), 200
    else:
        print("exe 2")
        return jsonify(0), 200


messages_collection = db['messages']

# Utility to create a consistent chat room ID
def get_chat_id(user1, user2):
    return '_'.join(sorted([user1, user2]))

# Store a message
@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    sender = data['sender']
    receiver = data['receiver']
    text = data['text']
    timestamp = datetime.utcnow()

    chat_id = get_chat_id(sender, receiver)
    message_data = {
        'chat_id': chat_id,
        'sender': sender,
        'receiver': receiver,
        'text': text,
        'timestamp': timestamp
    }

    messages_collection.insert_one(message_data)
    return jsonify({'status': 'Message sent successfully'}), 200

# Retrieve messages between two users
@app.route('/get_messages', methods=['GET'])
def get_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')
    
    chat_id = get_chat_id(user1, user2)
    messages = list(messages_collection.find({'chat_id': chat_id}).sort('timestamp'))

    for msg in messages:
        msg['_id'] = str(msg['_id'])  # Convert ObjectId to string for JSON serialization
        msg['timestamp'] = msg['timestamp'].isoformat() + 'Z'  # Convert to ISO string

    return jsonify(messages), 200



def object_id_to_str(post):
    post['_id'] = str(post['_id'])
    if 'postImageId' in post:
        post['postImageId'] = str(post['postImageId'])
    return post

# Route to create a post (Chat or Poll)
@app.route('/create_post/<rollno>', methods=['POST'])
def create_post(rollno):
    posts_collection = db['posts'] 
    try:
        data = request.json
        
        post_data = {
            'postId':data['postId'],
            'rollno': data['rollno'],  # User's roll number
            'type': data['type'],  # 'Chat' or 'Poll'
            'title': data['title'],
            'question': data['question'],
            'reference': data['reference'],
            'restriction': data['restriction'],
        }
        
        # If it's a poll, store the options as well
        if data['type'] == 'Poll':
            post_data['options'] = data['options']
            post_data['votes'] = {opt: [] for opt in data['options']}
        
        # Insert the post into the MongoDB collection
        result = posts_collection.insert_one(post_data)
        post_object_id = result.inserted_id

        users_collection = db['users']
        users_collection.update_one(
            {'_id': rollno},
            {'$push': {'postsids': str(post_object_id)}}
        )
        
        return jsonify({'message': 'Post created successfully', 'post_id': str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({'message': 'Error creating post', 'error': str(e)}), 500
    
from bson import ObjectId

@app.route('/submit_poll/<rollno>', methods=['POST'])
def submit_vote(rollno):
    data = request.get_json()
    poll_id = data.get('poll_id')
    selected_option = data.get('option')
    print("poll data "+poll_id+" "+selected_option)

    if not poll_id or not selected_option:
        return jsonify({'error': 'Missing poll_id or option'}), 400

    posts_collection = db['posts']
    poll = posts_collection.find_one({"_id": ObjectId(poll_id)})

    if not poll:
        return jsonify({'error': 'Poll not found'}), 404

    if selected_option not in poll.get('votes', {}):
        return jsonify({'error': 'Invalid option'}), 400

    # Check if the user has already voted in any option
    for voters in poll['votes'].values():
        if rollno in voters:
            return jsonify({'error': 'User has already voted'}), 403

    # Add the user's vote
    posts_collection.update_one(
        {"_id": ObjectId(poll_id)},
        {"$push": {f'votes.{selected_option}': rollno}}
    )

    return jsonify({'message': 'Vote submitted successfully'}), 200

@app.route('/poll_results/<poll_id>', methods=['GET'])
def poll_results(poll_id):
    posts_collection = db['posts']
    poll = posts_collection.find_one({"_id": ObjectId(poll_id)})

    if not poll:
        return jsonify({'error': 'Poll not found'}), 404

    votes = poll.get('votes', {})
    total_votes = sum(len(voters) for voters in votes.values())

    results = {}
    for option, voters in votes.items():
        percent = (len(voters) / total_votes * 100) if total_votes > 0 else 0
        results[option] = {
            'count': len(voters),
            'percentage': round(percent, 2)
        }

    return jsonify({
        'question': poll.get('question'),
        'results': results,
        'total_votes': total_votes
    }), 200


    

    
    




def printdata(extracted_data):



    # Display the results
    print("\n--- Extracted Resume Data ---\n")
    for field, match in extracted_data.items():
        if isinstance(match, list):
            print(f"{field}: {', '.join(match)}")
        elif match:
            print(f"{field}: {match.group(1).strip()}")
        else:
            print(f"{field}: Not found")


@app.route('/create-meet', methods=['POST'])
def create_meet():
    meetings_collection = db['meetings']
    data = request.get_json()

    required_fields = [
        'title', 'description', 'date', 'start_time', 
        'end_time', 'platform', 'link', 'host_id'
    ]
    
    if not all(field in data and data[field] for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    # Insert into MongoDB
    inserted = meetings_collection.insert_one(data)
    return jsonify({'message': 'Meeting created successfully', 'id': str(inserted.inserted_id)}), 201

@app.route('/meetings/<host_id>', methods=['GET'])
def get_meetings(host_id):
    collection = db['meetings']
    meetings = list(collection.find({'host_id': host_id}))

    if not meetings:
        return jsonify({"message": "No meetings found for this host."}), 404

    result = []
    for meet in meetings:
        result.append({
            "_id": str(meet['_id']),
            "title": meet['title'],
            "description": meet['description'],
            "date": meet['date'],
            "start_time": meet['start_time'],
            "end_time": meet['end_time'],
            "platform": meet['platform'],
            "link": meet['link'],
            "host_id": meet['host_id'],
        })

    return jsonify(result), 200




# Helper to convert ObjectId to string
def convert_id(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.route('/meeting_detail/<meet_id>', methods=['GET'])
def get_meeting_detail(meet_id):
    meetings_collection = db["meetings"]
    try:
        meeting = meetings_collection.find_one({"_id": ObjectId(meet_id)})
        if meeting:
            return jsonify(convert_id(meeting)), 200
        else:
            return jsonify({"error": "Meeting not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_member_meet', methods=['POST'])
def add_member_meet():
    meetings_collection = db["meetings"]
    data = request.json
    meet_id = data.get("meet_id")
    student_id = data.get("student_id")

    if not meet_id or not student_id:
        return jsonify({"error": "meet_id and student_id are required"}), 400

    try:
        result = meetings_collection.update_one(
            {"_id": ObjectId(meet_id)},
            {"$addToSet": {"members": student_id}}  # avoids duplicates
        )
        if result.modified_count > 0:
            return jsonify({"message": "Member added successfully"}), 200
        else:
            return jsonify({"message": "Member already added or meeting not found"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/assigned_meetings/<student_id>', methods=['GET'])
def get_assigned_meetings(student_id):
    collection = db['meetings']
    
    # Find meetings where the given student_id is in the members list
    meetings = list(collection.find({'members': student_id}))

    if not meetings:
        return jsonify({"message": "No assigned meetings found."}), 404

    result = []
    for meet in meetings:
        result.append({
            "_id": str(meet['_id']),
            "title": meet['title'],
            "description": meet['description'],
            "date": meet['date'],
            "start_time": meet['start_time'],
            "end_time": meet['end_time'],
            "platform": meet['platform'],
            "link": meet['link'],
            "host_id": meet['host_id'],
        })

    return jsonify(result), 200

@app.route('/create_group', methods=['POST'])
def create_group():
    groups_collection = db['group']
    data = request.json
    title = data.get('title')
    description = data.get('description', '')
    members = data.get('members', [])
    created_by = data.get('created_by')

    if not title or not members:
        return jsonify({"error": "Title and members are required"}), 400

    group = {
        "title": title,
        "description": description,
        "type": "Group",
        "members": members,
        "created_by": created_by
    }

    result = groups_collection.insert_one(group)

    return jsonify({"message": "Group created", "group_id": str(result.inserted_id)}), 201


@app.route('/get_groups/<id>', methods=['GET'])
def get_groups(id):
    groups_collection = db['group']
    communities_collection = db['community']

    # --- 1. Fetch Groups ---
    groups = groups_collection.find({
        "$or": [
            {"members": id},
            {"created_by": id}
        ]
    })

    group_list = []
    group_ids = []  # keep track of group IDs

    for group in groups:
        group_id = str(group["_id"])
        group_ids.append(group_id)
        group_list.append({
            "id": group_id,
            "name": group["title"],  # safe for Flutter
            "type": group.get("type", "Group"),
            "description": group.get("description", "")
        })

    # --- 2. Fetch Communities ---
    communities = communities_collection.find({
        "$or": [
            {"groups": {"$in": group_ids}},  # FIXED: check against group IDs
            {"created_by": id}
        ]
    })

    community_list = []
    for comm in communities:
        community_list.append({
            "id": str(comm["_id"]),
            "name": comm.get("title") or comm.get("name"),  # in your DB it's "title"
            "type": comm.get("type", "Community"),
            "description": comm.get("description", "")
        })

    return jsonify({
        "groups": group_list,
        "communities": community_list
    }), 200


@app.route('/get_group_messages/<group_id>', methods=['GET'])
def get_group_messages(group_id):
    messages_collection = db['group_messages']
    messages = messages_collection.find({"group_id": group_id}).sort("timestamp", 1)

    message_list = []
    for msg in messages:
        message_list.append({
            "sender": msg["sender"],
            "message": msg["message"],
            "timestamp": msg["timestamp"].isoformat()
        })

    return jsonify(message_list), 200


@app.route('/send_group_message', methods=['POST'])
def send_group_message():
    data = request.get_json()
    message_doc = {
        "group_id": data["group_id"],
        "sender": data["sender"],
        "message": data["message"],
        "timestamp": datetime.utcnow()
    }

    db['group_messages'].insert_one(message_doc)
    return jsonify({"status": "success"}), 201


@app.route('/submit_comment', methods=['POST'])
def submit_comment():
    posts_collection = db["posts"]
    data = request.json
    post_id = data.get("postId")
    rollno = data.get("rollno")
    comment = data.get("comment")

    if not post_id or not rollno or not comment:
        return jsonify({"error": "Missing fields"}), 400

    try:
        object_id = ObjectId(post_id)
    except Exception:
        return jsonify({"error": "Invalid post ID"}), 400

    # Add or update the comment in the post's 'comments' field
    result = posts_collection.update_one(
        {"_id": object_id},
        {"$set": {f"comments.{rollno}": comment}}
    )

    if result.modified_count > 0:
        return jsonify({"message": "Comment submitted successfully"}), 200
    else:
        return jsonify({"message": "No update made"}), 200

@app.route('/get_comments/<post_id>', methods=['GET'])
def get_comments(post_id):
    posts_collection = db["posts"]
    try:
        object_id = ObjectId(post_id)
    except Exception:
        return jsonify({"error": "Invalid post ID"}), 400

    post = posts_collection.find_one({"_id": object_id})
    if not post:
        return jsonify({"error": "Post not found"}), 404

    comments = post.get("comments", {})
    return jsonify(comments), 200

@app.route('/get_detsils_leaderboard', methods=['GET'])
def get_details_leaderboard():
    users_col = db['users']
    posts_col = db['posts']
    users = users_col.find({}, {"_id": 1, "name": 1, "roll": 1, "profile": 1, "postsids": 1})
    leaderboard = []
    for user in users:
        user_posts = posts_col.find({"_id": {"$in": [ObjectId(post_id) for post_id in user.get("postsids", [])]}})
        total_likes = sum(len(post.get("likeset", [])) for post in user_posts)
        
        leaderboard.append({
            "_id": user["_id"],
            "roll": user["roll"],
            "name": user["name"],
            "profile": user.get("profile", None),
            "total_likes": total_likes
        })
    leaderboard.sort(key=lambda x: x["total_likes"], reverse=True)
    return jsonify(leaderboard),200


@app.route('/getSavedPosts/<user_id>', methods=['GET'])
def get_saved_posts(user_id):
    collection = db['users']
    user = collection.find_one({"_id": user_id}, {"saved_posts": 1})
    if not user:
        return jsonify([]), 200
    saved_posts_ids = user['saved_posts']
    print("saved posts ids", saved_posts_ids)
    return jsonify(saved_posts_ids), 200


@app.route('/saveposts/<user_id>/<post_id>', methods=['GET'])
def save_posts(user_id, post_id):
    collection = db['users']
    user = collection.find_one({"_id": user_id})
    
    if not user:
        return jsonify({"message": "User not found"}), 404

    # If 'saved_posts' does not exist, create it with post_id
    if 'saved_posts' not in user:
        collection.update_one(
            {"_id": user_id},
            {"$set": {"saved_posts": [post_id]}}
        )
        return jsonify({"message": "Post saved successfully"}), 200

    # If post_id already in saved_posts -> remove it
    if post_id in user['saved_posts']:
        collection.update_one(
            {"_id": user_id},
            {"$pull": {"saved_posts": post_id}}
        )
        return jsonify({"message": "Post removed from saved posts"}), 200

    # Else -> add post_id to saved_posts
    collection.update_one(
        {"_id": user_id},
        {"$addToSet": {"saved_posts": post_id}}
    )
    return jsonify({"message": "Post saved successfully"}), 200

from datetime import datetime, timezone
from bson import ObjectId

@app.route('/create_community', methods=['POST'])
def create_community():
    try:
        communities_collection = db['community']  # ✅ store inside "community" collection
        data = request.json

        if not data.get("name") or not data.get("groups"):
            return jsonify({"error": "Community name and groups required"}), 400

        community = {
            "title": data["name"],
            "groups": data["groups"],
            "created_by": data.get("created_by"),
            "type": "Community",
            "created_at": datetime.now(timezone.utc).isoformat()  # ✅ timezone-aware
        }

        result = communities_collection.insert_one(community)
        community["_id"] = str(result.inserted_id)  # ✅ convert ObjectId to string

        return jsonify({
            "message": "Community created successfully",
            "community": community
        }), 201

    except Exception as e:
        print("Error creating community:", str(e))
        return jsonify({"error": str(e)}), 500







def get_current_template_bytes():
    settings = db["settings"] 
    cfg = settings.find_one({"key": "certificate_template"})
    if not cfg or "file_id" not in cfg:
        # No template uploaded yet
        return None
    gfile = fs.get(ObjectId(cfg["file_id"]))
    return gfile.read()

def get_host_signature_bytes(host_id: str):
    settings = db["settings"] 
    cfg = settings.find_one({"key": "host_signature", "host_id": host_id})
    if not cfg or "file_id" not in cfg:
        return None
    gfile = fs.get(ObjectId(cfg["file_id"]))
    return gfile.read()

def put_pdf_to_gridfs(pdf_bytes: bytes, filename: str, metadata: dict):
    return fs.put(pdf_bytes, filename=filename, **({"metadata": metadata} if metadata else {}))


NAME_X, NAME_Y = 260, 302
TITLE_X, TITLE_Y = 260, 360
DATE_X, DATE_Y = 180, 472
SIGNATURE_X, SIGNATURE_Y = 340, 450


def make_certificate_pdf(
    template_bytes: bytes,
    student_name_or_id: str,
    
    title: str,
    date: str,
    signature_bytes: bytes | None = None

) -> bytes:
    """
    Draws name, title, date, and optional signature onto the first page
    of the PDF template.
    """

    # Open template PDF
    doc = fitz.open(stream=template_bytes, filetype="pdf")
    page = doc[0]  # first page

    # Draw text
    name_fontsize = 30
    title_fontsize = 20
    date_fontsize = 16

    # Name
    page.insert_text(
        (NAME_X, NAME_Y),
        student_name_or_id,
        fontname="helv",
        fontsize=name_fontsize,
        fontfile=None,
        color=(0, 0, 0),
    )

    # Title
    page.insert_text(
        (TITLE_X, TITLE_Y),
        title,
        fontname="helv",
        fontsize=title_fontsize,
        color=(0, 0, 0),
    )

    # Date
    page.insert_text(
        (DATE_X, DATE_Y),
        date,
        fontname="helv",
        fontsize=date_fontsize,
        color=(0, 0, 0),
    )

    # Signature (optional)
    if signature_bytes:
        # Calculate a rectangle for signature
        sig_width = 150
        sig_height = 50
        sig_rect = fitz.Rect(
            SIGNATURE_X,
            SIGNATURE_Y,
            SIGNATURE_X + sig_width,
            SIGNATURE_Y + sig_height,
        )
        page.insert_image(sig_rect, stream=signature_bytes, keep_proportion=True)

    # Save to bytes
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    out.seek(0)
    return out.getvalue()
    

@app.post("/template")
def upload_template():
    """
    Upload once (multipart/form-data: file=template.pdf).
    Stored in GridFS; settings.key=certificate_template points to it.
    """
    settings = db["settings"] 
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF template"}), 400

    file_id = fs.put(f.read(), filename=f.filename, content_type="application/pdf")
    settings.update_one(
        {"key": "certificate_template"},
        {"$set": {"file_id": str(file_id), "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return jsonify({"ok": True, "template_file_id": str(file_id)}), 200

@app.post("/signature")
def upload_signature():
    """
    Upload (multipart/form-data: file=signature.png|jpg, host_id=string).
    Stores per-host signature in GridFS and records in settings.
    """
    settings = db["settings"] 
    host_id = request.form.get("host_id")
    if not host_id:
        return jsonify({"error": "host_id is required"}), 400
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400
    f = request.files["file"]
    if not (f.filename.lower().endswith(".png") or f.filename.lower().endswith(".jpg") or f.filename.lower().endswith(".jpeg")):
        return jsonify({"error": "Upload PNG/JPG signature"}), 400

    file_id = fs.put(f.read(), filename=f.filename, content_type="image/*")
    settings.update_one(
        {"key": "host_signature", "host_id": host_id},
        {"$set": {"file_id": str(file_id), "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return jsonify({"ok": True, "signature_file_id": str(file_id), "host_id": host_id}), 200


@app.post("/distribute_certificates")
def distribute_certificates():
    """
    JSON: { "meet_id": "<_id string>" }
    - Loads meeting
    - Loads current template & host signature
    - Generates a certificate per member
    - Stores each in GridFS and upserts into certificates collection
    """
    meetings = db["meetings"]
    certificates = db["certificates"]
    payload = request.get_json(silent=True) or {}
    meet_id = payload.get("meet_id")
    if not meet_id:
        return jsonify({"error": "meet_id required"}), 400

    # Load meeting
    try:
        meeting = meetings.find_one({"_id": ObjectId(meet_id)})
    except:
        meeting = None
    if not meeting:
        return jsonify({"error": "meeting not found"}), 404

    members = meeting.get("members", [])
    host_id = str(meeting.get("host_id", ""))

    template_bytes = get_current_template_bytes()
    if not template_bytes:
        return jsonify({"error": "no certificate template uploaded"}), 400

    signature_bytes = get_host_signature_bytes(host_id)  # may be None

    results = []
    for sid in members:
        print(sid)
        # If you have a 'students' collection with names, you could look up here.
        stu = db.users.find_one({"_id": sid})
        name_or_id = stu.get("fields", {}).get("Full Name", sid) if stu else sid

        # name_or_id = sid  # fallback to student ID as requested

        pdf_bytes = make_certificate_pdf(template_bytes, name_or_id,meeting['title'], meeting['date'], signature_bytes)
        grid_id = put_pdf_to_gridfs(
            pdf_bytes,
            filename=f"{meet_id}_{sid}.pdf",
            metadata={"meet_id": meet_id, "student_id": sid}
        )

        # Upsert certificate record
        certificates.update_one(
            {"meet_id": meet_id, "student_id": sid},
            {"$set": {
                "meet_id": meet_id,
                "student_id": sid,
                "certificate_file_id": str(grid_id),
                "updated_at": datetime.now(timezone.utc)


            }},
            upsert=True
        )
        results.append({"student_id": sid, "certificate_file_id": str(grid_id)})

    return jsonify({
        "ok": True,
        "meet_id": meet_id,
        "generated_count": len(results),
        "items": results
    }), 200


@app.get("/certificate_file/<meet_id>/<student_id>")
def get_certificate_file(meet_id, student_id):
    """
    Streams a certificate PDF for a given meet_id + student_id.
    Looks up certificate_file_id from certificates collection.
    """
    certificates = db["certificates"] 
    cert = certificates.find_one({"meet_id": meet_id, "student_id": student_id})
    if not cert or "certificate_file_id" not in cert:
        return jsonify({"error": "certificate not found"}), 404

    try:
        gf = fs.get(ObjectId(cert["certificate_file_id"]))
    except:
        return jsonify({"error": "invalid file id"}), 400

    return send_file(
        io.BytesIO(gf.read()),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=gf.filename or f"{student_id}_{meet_id}.pdf"
    )


@app.route('/get_post_by_userid/<user_id>', methods=['GET'])
@cross_origin()
def get_post_by_userid(user_id):
    try:
        # Fetch all posts for this user_id
        posts = list(db['posts'].find({"rollno": user_id}))

        if not posts:
            return jsonify({'message': 'No posts found'}), 404

        # Convert ObjectId to string
        for post in posts:
            post['_id'] = str(post['_id'])

        return jsonify(posts), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching posts', 'error': str(e)}), 500


@app.route('/delete_post_by_userid_postid/<user_id>/<post_id>', methods=['DELETE'])
@cross_origin()
def delete_post_by_userid_postid(user_id, post_id):
    try:
        # Try deleting the post where rollno = user_id and _id = post_id
        result = db['posts'].delete_one({
            "rollno": user_id,
            "_id": ObjectId(post_id)
        })

        if result.deleted_count == 0:
            return jsonify({'message': 'Post not found'}), 404

        return jsonify({'message': 'Post deleted successfully'}), 200

    except Exception as e:
        return jsonify({'message': 'Error deleting post', 'error': str(e)}), 500



@app.route('/delete_user_field/<user_id>/<field_key>', methods=['DELETE'])
@cross_origin()
def delete_user_field(user_id, field_key):
    try:
        result = db['users'].update_one(
            {"_id": user_id},            # match by _id instead of rollno
            {"$unset": {field_key: 1}}   # remove key30, key31...
        )

        if result.modified_count == 0:
            return jsonify({"message": "Field not found or already deleted"}), 404

        return jsonify({"message": f"Field '{field_key}' deleted successfully"}), 200

    except Exception as e:
        return jsonify({"message": "Error deleting field", "error": str(e)}), 500


@app.route('/update_post/<post_id>', methods=['PUT'])
@cross_origin()
def update_post(post_id):
    try:
        post_data = request.form.get('post_data')
        image = request.files.get('post_image')

        if not post_data:
            return jsonify({'message': 'Missing post_data'}), 400

        import json
        post_data = json.loads(post_data)

        posts_collection = db['posts']

        # Build update fields
        update_fields = {**post_data}

        if image:
            # Save new image to GridFS
            filename = f"post_image_{post_id}"
            content_type = image.content_type
            image_id = fs.put(
                image,
                filename=filename,
                metadata={'post_id': post_id, 'contentType': content_type}
            )
            update_fields['postImageId'] = str(image_id)

        # Update the post
        result = posts_collection.update_one(
            {'_id': ObjectId(post_id)},
            {'$set': update_fields}
        )

        if result.matched_count == 0:
            return jsonify({'message': 'Post not found'}), 404

        return jsonify({'message': 'Post updated successfully'}), 200

    except Exception as e:
        return jsonify({'message': 'Error updating post', 'error': str(e)}), 500


@app.route('/remove_member/<meeting_id>/<member_id>', methods=['DELETE'])
@cross_origin()
def remove_member(meeting_id, member_id):
    try:
        result = db['meetings'].update_one(
            {"_id": ObjectId(meeting_id)},
            {"$pull": {"members": member_id}}
        )

        if result.modified_count == 0:
            return jsonify({"message": "Member not found or already removed"}), 404

        return jsonify({"message": f"Member {member_id} removed successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Error removing member", "error": str(e)}), 500


@app.route('/delete_meeting/<meeting_id>', methods=['DELETE'])
@cross_origin()
def delete_meeting(meeting_id):
    try:
        result = db['meetings'].delete_one({"_id": ObjectId(meeting_id)})

        if result.deleted_count == 0:
            return jsonify({"message": "Meeting not found"}), 404

        return jsonify({"message": "Meeting deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Error deleting meeting", "error": str(e)}), 500

# def serialize_doc(doc):
#     doc["_id"] = str(doc["_id"])
#     if "certificate_file_id" in doc:
#         doc["certificate_file_id"] = str(doc["certificate_file_id"])
#     if "meet_id" in doc:
#         doc["meet_id"] = str(doc["meet_id"])
#     if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
#         doc["updated_at"] = doc["updated_at"].isoformat()
#     return doc

def serialize_doc(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "certificate_file_id" in doc and doc["certificate_file_id"] is not None:
        doc["certificate_file_id"] = str(doc["certificate_file_id"])
    if "file_id" in doc and doc["file_id"] is not None:
        doc["file_id"] = str(doc["file_id"])
    if "meet_id" in doc and doc["meet_id"] is not None:
        doc["meet_id"] = str(doc["meet_id"])
    if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
        doc["updated_at"] = doc["updated_at"].isoformat()
    if "submitted_at" in doc and isinstance(doc["submitted_at"], datetime):
        doc["submitted_at"] = doc["submitted_at"].isoformat()
    return doc



@app.route('/get_certificates/<rollno>', methods=['GET'])
@cross_origin()
def get_certificates(rollno):
    print("Fetching certificates for rollno:", rollno)
    try:
        certificates_collection = db['certificates']
        certificates = list(certificates_collection.find({"student_id": rollno}))

        print("Raw certificates:", certificates)  # debug log

        certificates = [serialize_doc(cert) for cert in certificates]

        return jsonify(certificates), 200
    except Exception as e:
        import traceback
        print("Error fetching certificates:", str(e))
        traceback.print_exc()
        return jsonify({"message": "Error fetching certificates", "error": str(e)}), 500





tasks = db["tasks"]
submissions = db["submissions"]


# ---- Utilities ----
def oid(x):
    try:
        return ObjectId(x)
    except Exception:
        return None

def iso(dt: datetime | None):
    return dt.isoformat() if isinstance(dt, datetime) else dt

def sdoc(doc: dict):
    """Serialize mongo doc -> JSON-safe dict."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

def ok(data, code=200):
    return jsonify(data), code

def bad(msg, code=400):
    return jsonify({"message": msg}), code

# Recommended indexes (run once)
def ensure_indexes():
    tasks.create_index([("mentor_id", ASCENDING)])
    tasks.create_index([("student_id", ASCENDING)])
    tasks.create_index([("deadline", ASCENDING)])
    submissions.create_index([("task_id", ASCENDING)])
    submissions.create_index([("student_id", ASCENDING)])
ensure_indexes()

# ======================================================================
#                              TASKS
# ======================================================================
@app.route("/create_task", methods=["POST"])
@cross_origin()
def create_task():
    """
    Body (JSON):
    {
      "mentor_id": "23CDR110",
      "mentor_name": "Alumni Name",       (optional)
      "student_id": "101",                (optional if multi-assign)
      "student_ids": ["101","102"],       (optional for assign many)
      "title": "Assignment",
      "description": "Do this...",
      "deadline": "2025-08-25",           (ISO or yyyy-mm-dd)
      "attachments": ["link1", "link2"],  (optional references)
      "works": [                          (MANDATORY, at least 1)
        {"question": "Q1 text here"},
        {"question": "Q2 text here"},
        ...
      ]
    }
    Creates 1 task per student_id.
    """
    try:
        body = request.get_json(force=True)

        mentor_id = body.get("mentor_id")
        title = body.get("title")
        description = body.get("description", "")
        deadline = body.get("deadline")
        mentor_name = body.get("mentor_name", "")
        attachments = body.get("attachments", [])
        works = body.get("works", [])

        if not mentor_id or not title:
            return bad("mentor_id and title are required")

        if not works or len(works) == 0:
            return bad("At least one work/question is required")

        # normalize deadline
        if deadline:
            try:
                if len(deadline) == 10:
                    deadline_dt = datetime.fromisoformat(deadline + "T23:59:59")
                else:
                    deadline_dt = datetime.fromisoformat(deadline)
            except Exception:
                return bad("Invalid deadline format. Use YYYY-MM-DD or ISO8601.")
        else:
            deadline_dt = None

        # student targets
        target_student_ids = []
        if body.get("student_id"):
            target_student_ids = [body["student_id"]]
        elif body.get("student_ids"):
            target_student_ids = list(map(str, body["student_ids"]))
        else:
            return bad("Provide student_id or student_ids")

        created = []
        now = datetime.utcnow()

        for sid in target_student_ids:
            doc = {
                "mentor_id": str(mentor_id),
              
                "student_id": str(sid),
                "title": title,
                "description": description,
                "deadline": deadline_dt,
                "status": "assigned",
                "created_at": now,
                "updated_at": now,
                "attachments": attachments,
                "turnIn": [],
                "works": works    # << NEW (list of Qs)
            }
            ins = tasks.insert_one(doc)
            doc["_id"] = ins.inserted_id
            created.append(sdoc(doc))

        return ok({"message": "Tasks created", "tasks": created})

    except Exception as e:
        return ok({"message": "Error creating task", "error": str(e)}, 500)


from bson import ObjectId
from datetime import datetime

def serialize(obj):
    """Recursively convert ObjectId and datetime in dicts/lists to JSON-safe formats."""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize(v) for v in obj]
    else:
        return obj


@app.route("/get_tasks/<student_id>", methods=["GET"])
@cross_origin()
def get_tasks_for_student(student_id):
    try:
        cur = tasks.find({"student_id": str(student_id)}).sort("created_at", -1)
        docs = [serialize(x) for x in cur]   # use recursive serializer
        return ok(docs)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return bad(f"Error fetching tasks: {str(e)}", 500)



@app.route("/get_tasks_by_mentor/<mentor_id>", methods=["GET"])
@cross_origin()
def get_tasks_by_mentor(mentor_id):
    """
    List all tasks created by a mentor.
    """
    try:
        cur = tasks.find({"mentor_id": str(mentor_id)}).sort("created_at", -1)
        return ok([sdoc(x) for x in cur])
    except Exception as e:
        return ok({"message": "Error fetching mentor tasks", "error": str(e)}, 500)


@app.route("/update_task/<task_id>", methods=["PUT"])
@cross_origin()
def update_task(task_id):
    """
    Update task fields (mentor only).
    Body JSON can include: title, description, deadline, status, attachments
    """
    try:
        tid = oid(task_id)
        if not tid:
            return bad("Invalid task_id")

        body = request.get_json(force=True)
        update = {}
        for f in ["title", "description", "status", "attachments"]:
            if f in body:
                update[f] = body[f]

        if "deadline" in body:
            dl = body["deadline"]
            if dl:
                try:
                    if len(dl) == 10:
                        update["deadline"] = datetime.fromisoformat(dl + "T23:59:59")
                    else:
                        update["deadline"] = datetime.fromisoformat(dl)
                except Exception:
                    return bad("Invalid deadline format.")
            else:
                update["deadline"] = None

        if not update:
            return bad("Nothing to update")
        update["updated_at"] = datetime.utcnow()

        res = tasks.update_one({"_id": tid}, {"$set": update})
        if res.matched_count == 0:
            return bad("Task not found", 404)
        doc = tasks.find_one({"_id": tid})
        return ok(sdoc(doc))
    except Exception as e:
        return ok({"message": "Error updating task", "error": str(e)}, 500)


@app.route("/delete_task/<task_id>", methods=["DELETE"])
@cross_origin()
def delete_task(task_id):
    """
    Delete a task and its submissions (mentor).
    """
    try:
        tid = oid(task_id)
        if not tid:
            return bad("Invalid task_id")

        # delete submissions + any files from GridFS
        subs = list(submissions.find({"task_id": str(tid)}))
        for sub in subs:
            file_id = sub.get("file_id")
            if file_id:
                try:
                    fs.delete(ObjectId(file_id))
                except Exception:
                    pass
        submissions.delete_many({"task_id": str(tid)})

        res = tasks.delete_one({"_id": tid})
        if res.deleted_count == 0:
            return bad("Task not found", 404)
        return ok({"message": "Task deleted"})
    except Exception as e:
        return ok({"message": "Error deleting task", "error": str(e)}, 500)

# ======================================================================
#                           SUBMISSIONS
# ======================================================================

@app.route("/get_submissions/<task_id>", methods=["GET"])
@cross_origin()
def get_submissions(task_id):
    """
    List submissions for a task (mentor view).
    """
    try:
        tid = oid(task_id)
        if not tid:
            return bad("Invalid task_id")
        cur = submissions.find({"task_id": str(tid)}).sort("submitted_at", -1)
        return ok([sdoc(x) for x in cur])
    except Exception as e:
        return ok({"message": "Error fetching submissions", "error": str(e)}, 500)


submissions = db["submissions"]


@app.route("/submit_task/<task_id>", methods=["POST"])
def submit_task(task_id):
    try:
        # Safely extract JSON if available
        data = {}
        if request.is_json:
            data = request.get_json(force=True, silent=True) or {}

        student_id = request.form.get("student_id") or data.get("student_id")
        work = request.form.get("work") or data.get("work")
        content_text = request.form.get("content_text") or data.get("content_text")
        content_url = request.form.get("content_url") or data.get("content_url")

        file_id = None
        if "file" in request.files:
            file = request.files["file"]
            if file:
                filename = secure_filename(file.filename)
                file_id = fs.put(file, filename=filename, content_type=file.content_type)

        doc = {
            "task_id": str(task_id),
            "student_id": str(student_id),
            "work": work,
            "content_text": content_text,
            "file_id": str(file_id) if file_id else None,
            "content_url": content_url,
            "submitted_at": datetime.now(timezone.utc),
            "score": None,
            "feedback": None,
            "evaluated_by": None,
            "evaluated_at": None,
        }

        result = submissions.insert_one(doc)
        doc["_id"] = result.inserted_id  # Mongo _id

        tasks.update_one({"_id": ObjectId(task_id)},{"$addToSet": {"turnIn": {"student_id": str(student_id), "work": work}}})


        return jsonify({
            "message": "Submission saved",
            "submission": serialize_doc(doc)
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()  # print full error in console
        return jsonify({"error": str(e)}), 500


@app.route("/get_submission_file/<file_id>", methods=["GET"])
@cross_origin()
def get_submission_file(file_id):
    """
    Stream the uploaded file back (for mentor to view).
    """
    try:
        fid = oid(file_id)
        if not fid:
            return bad("Invalid file_id")
        gf = fs.get(fid)
        return app.response_class(
            gf.read(),
            mimetype=gf.metadata.get("contentType", "application/octet-stream"),
            headers={"Content-Disposition": f'inline; filename="{gf.filename}"'}
        )
    except Exception as e:
        return ok({"message": "File not found", "error": str(e)}, 404)


@app.route("/evaluate_submission/<submission_id>", methods=["PUT"])
@cross_origin()
def evaluate_submission(submission_id):
    """
    Mentor scores and leaves feedback.
    Body JSON:
    {
      "score": 0-100,
      "feedback": "optional comments",
      "evaluated_by": "23CDR110"
    }
    """
    try:
        sid = oid(submission_id)  # I assume this wraps ObjectId(submission_id)
        if not sid:
            return bad("Invalid submission_id")

        body = request.get_json(force=True)
        score = body.get("score")
        feedback = body.get("feedback", "")
        evaluated_by = body.get("evaluated_by")

        if score is None or evaluated_by is None:
            return bad("score and evaluated_by are required")

        res = submissions.update_one(
            {"_id": sid},
            {"$set": {
                "score": int(score),
                "feedback": feedback,
                "evaluated_by": str(evaluated_by),
                "evaluated_at": datetime.utcnow()
            }}
        )
        if res.matched_count == 0:
            return bad("Submission not found", 404)

        doc = submissions.find_one({"_id": sid})
        
        if doc and "task_id" in doc:
            tasks.update_one(
                {"_id": oid(doc["task_id"])},
                {"$addToSet": {
                    "evaluated": {
                        "submission_id": sid,
                        "student_id": doc["student_id"],
                        "score": doc["score"],
                        "evaluated_by": doc["evaluated_by"],
                        "evaluated_at": doc["evaluated_at"]
                    }
                }}
            )

        return ok(sdoc(doc))   # ✅ returning updated doc
    except Exception as e:
        import traceback
        traceback.print_exc()
        return bad(f"Error evaluating submission: {str(e)}", 500)

@app.route("/delete_submission/<submission_id>", methods=["DELETE"])
@cross_origin()
def delete_submission(submission_id):
    """
    Delete a submission (e.g., mentor/admin cleanup).
    """
    try:
        sid = oid(submission_id)
        if not sid:
            return bad("Invalid submission_id")

        sub = submissions.find_one({"_id": sid})
        if not sub:
            return bad("Submission not found", 404)

        file_id = sub.get("file_id")
        if file_id:
            try:
                fs.delete(ObjectId(file_id))
            except Exception:
                pass

        submissions.delete_one({"_id": sid})
        return ok({"message": "Submission deleted"})
    except Exception as e:
        return ok({"message": "Error deleting submission", "error": str(e)}, 500)


@app.route("/get_submission/<submission_id>", methods=["GET"])
def get_submission(submission_id):
    sub = submissions.find_one({"_id": ObjectId(submission_id)})
    if not sub:
        return bad("Submission not found")
    return ok(sdoc(sub))





from flask import Response
from bson import ObjectId

@app.route("/get_file_task/<file_id>", methods=["GET"])
def get_file(file_id):
    try:
        # Convert file_id back to ObjectId
        file_obj = fs.get(ObjectId(file_id))

        # Stream the file back to client
        return Response(
            file_obj.read(),
            mimetype=file_obj.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={file_obj.filename}"
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 404


# ======================================================================
#                          HEALTH / DEBUG
# ======================================================================
@app.route("/health", methods=["GET"])
def health():
    return ok({"status": "ok", "time": datetime.utcnow().isoformat()})

@app.route("/get_meeting_name", methods=["GET"])
def get_meeting_name():
    meet_id = request.args.get("meet_id")
    if not meet_id:
        return jsonify({"error": "meet_id is required"}), 400

    meeting = db.meetings.find_one({"_id": ObjectId(meet_id)}, {"title": 1, "_id": 0})
    if meeting:
        return jsonify({"title": meeting.get("title", "")})
    else:
        return jsonify({"error": "Meeting not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)