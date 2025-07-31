import base64
from csv import reader
from datetime import datetime
from tkinter import Image
from bson import ObjectId
from flask import Flask, Response,jsonify,request, send_file
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
import gridfs
import io
import re
import fitz  # PyMuPDF
import google.generativeai as genai
import os


app = Flask(__name__)
CORS(app)
try:
    client = MongoClient("mongodb://localhost:27017")
    db = client["alumnex"]
    fs = gridfs.GridFS(db)
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ Failed to connect to MongoDB:", e)




# Configure Gemini with your API key (secure this in prod)
genai.configure(api_key="AIzaSyCbVGKRCYZY8Z5dy2jAMQuxdUQ4Je4NxxU")

# Initialize the model globally (reuse for efficiency)
model = genai.GenerativeModel("gemini-1.5-flash")



@cross_origin()
@app.route('/aura_assistant', methods=['POST'])
def aura_assistant_response():
    data = request.json
    user_query = data.get('query')
    student_context = data.get('context', {})

    if not user_query:
        return jsonify({"error": "Missing 'query' in request."}), 400

    # Personalize if context provided
    if student_context:
        intro = f"The user is a {student_context.get('year')} {student_context.get('branch')} student interested in {', '.join(student_context.get('interests', []))}. "
        full_prompt = intro + user_query
    else:
        full_prompt = user_query

    try:
        response = model.generate_content(full_prompt)
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



"""@app.route('/upload-Resume', methods=['POST'])
def upload_resume():
    user_id = request.form.get('user_id')
    resume = request.files.get('resume')

    if not user_id or not resume:
        return jsonify({'message': 'Missing user_id or resume'}), 400

    # Delete old resume if exists
    old_user = db.users.find_one({"_id": user_id})
    if old_user and "resume" in old_user:
        try:
            fs.delete(ObjectId(old_user["resume"]))
        except:
            pass

    # Save new resume
    file_id = fs.put(resume, filename=f"{user_id}_resume", content_type=resume.content_type)
    db.users.update_one({"_id": user_id}, {"$set": {"resume": str(file_id)}}, upsert=True)

    return jsonify({"message": "Resume uploaded successfully", "file_id": str(file_id)}), 200"""
    




@app.route('/upload-Resume', methods=['POST'])
def upload_resume():
    user_id = request.form.get('user_id')
    resume = request.files.get('resume')

    if not user_id or not resume:
        return jsonify({'message': 'Missing user_id or resume'}), 400

    # Delete old resume if exists
    old_user = db.users.find_one({"_id": user_id})
    if old_user and "resume" in old_user:
        try:
            fs.delete(ObjectId(old_user["resume"]))
        except:
            pass

    # Save new resume to GridFS
    file_id = fs.put(resume, filename=f"{user_id}_resume", content_type=resume.content_type)

    # Read PDF text using PyMuPDF
    resume.seek(0)
    pdf_doc = fitz.open(stream=resume.read(), filetype="pdf")
    text = ""
    for page in pdf_doc:
        text += page.get_text()

    # Extract fields using regex
    extracted_data = {
        "Gender": re.search(r"Gender\s*[:\-]?\s*(Male|Female|Other)", text, re.IGNORECASE),
        "location": re.search(r"Location\s*[:\-]?\s*([A-Za-z ,]+)", text),
        "Batch": re.search(r"Batch\s*[:\-]?\s*(20\d{2}-20\d{2})", text),
        "preferredroll": re.search(r"Preferred\s*Role\s*[:\-]?\s*([^\n]+)", text, re.IGNORECASE),
        "Higherstudies": re.search(r"Higher\s*Studies\s*[:\-]?\s*([^\n]+)", text, re.IGNORECASE),
        "Dreamcompany": re.search(r"Dream\s*Company\s*[:\-]?\s*([^\n]+)", text, re.IGNORECASE),
        "clubs": re.search(r"Clubs\s*[:\-]?\s*([^\n]+)", text, re.IGNORECASE),
        "name": re.search(r"Name\s*[:\-]?\s*([A-Za-z ]+)", text),
        "email": re.search(r"\b([\w\.-]+@[\w\.-]+)", text),
        "phoneno": re.search(r"((?:\+91[\s\-]?)?[6-9]\d{9})", text),
        "dob": re.search(r"DOB\s*[:\-]?\s*([^\n]+)", text),
        "programbranch": re.search(r"Pursuing\s+([^\n]+)", text),
        "college": re.search(r"at\s+(Kongu Engineering College)", text),
        "cgpa": re.search(r"CGPA\s*[:\-]?\s*([\d\.]+)", text),
        "hsc_percent": re.search(r"HSC\s*[:\-]?\s*(\d+)%", text),
        "TechSkills": re.findall(r"\b(C\+\+|C|Java|Python|Dart|HTML|CSS|Spring Boot|MongoDB|Flutter|Oracle|JavaScript|Node\.js|React|Figma)\b", text),
        "projects": re.search(r"(TNEA Counselling Helper.*?)Mobile App", text, re.DOTALL),
        "certification": re.search(r"(Completed an Internship.*?)training", text, re.DOTALL),
        "interests": re.search(r"(Backend Developer.*?)Spring Boot", text, re.DOTALL),
        "domain": re.search(r"(Spring Boot, Flutter.*?)Figma", text, re.DOTALL),
    }
    
    parsed_resume = {
        "name": extracted_data["name"].group(1).strip() if extracted_data["name"] else None,
        "email": extracted_data["email"].group(1).strip() if extracted_data["email"] else None,
        "phoneno": extracted_data["phoneno"].group(1).strip() if extracted_data["phoneno"] else None,
        "dob": extracted_data["dob"].group(1).strip() if extracted_data["dob"] else None,
        "Gender": extracted_data["Gender"].group(1).strip() if extracted_data["Gender"] else None,
        "location": extracted_data["location"].group(1).strip() if extracted_data["location"] else None,
        "Batch": extracted_data["Batch"].group(1).strip() if extracted_data["Batch"] else None,
        "preferredroll": extracted_data["preferredroll"].group(1).strip() if extracted_data["preferredroll"] else None,
        "Higherstudies": extracted_data["Higherstudies"].group(1).strip() if extracted_data["Higherstudies"] else None,
        "Dreamcompany": extracted_data["Dreamcompany"].group(1).strip() if extracted_data["Dreamcompany"] else None,
        "clubs": extracted_data["clubs"].group(1).strip() if extracted_data["clubs"] else None,
        "programbranch": extracted_data["programbranch"].group(1).strip() if extracted_data["programbranch"] else None,
        "college": extracted_data["college"].group(1).strip() if extracted_data["college"] else None,
        "cgpa": float(extracted_data["cgpa"].group(1)) if extracted_data["cgpa"] else None,
        "hsc_percent": int(extracted_data["hsc_percent"].group(1)) if extracted_data["hsc_percent"] else None,
        "TechSkills": list(set(extracted_data["TechSkills"])) if extracted_data["TechSkills"] else [],
        "projects": extracted_data["projects"].group(1).strip() if extracted_data["projects"] else None,
        "certificaion": extracted_data["certification"].group(1).strip() if extracted_data["certification"] else None,
        "interests": extracted_data["interests"].group(1).strip() if extracted_data["interests"] else None,
        "domain": extracted_data["domain"].group(1).strip() if extracted_data["domain"] else None,
        "created_at": datetime.utcnow()
    }
    print(parsed_resume)
    # Clean matched groups
    for key, value in extracted_data.items():
        if isinstance(value, re.Match):
            extracted_data[key] = value.group(1)
    
    db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "resume": str(file_id),
                **extracted_data
            }
        },
        upsert=True
    )

    return jsonify({
        "message": "Resume uploaded and content extracted successfully",
        "file_id": str(file_id),
    }), 200




@app.route('/get-resume/<user_id>', methods=['GET'])
def get_resume(user_id):
    user = db.users.find_one({"_id": user_id})
    if not user or "resume" not in user:
        return jsonify({"message": "Resume not found"}), 404

    file_id = ObjectId(user["resume"])
    file = fs.get(file_id)
    return send_file(io.BytesIO(file.read()), mimetype=file.content_type, as_attachment=True, download_name=file.filename)

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

    like_count = len(res.get('likeset', []))  # fallback to empty list if not exists
    return jsonify({'like_count': like_count}), 200


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
    else:
        if(data["response"]=='Accepted'):
            
            userscollection.update_one(
                {"_id":res["from"]},
                {"$set":{"mentoredby":res["to"]}}
            )
            userscollection.update_one(
            {"_id": res["to"]},
            {"$push": {"mentoring": res["from"]}}
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
    print(id)
    
    # Filter groups where 'members' contains the given id (as string)
    groups = groups_collection.find({
        "$or": [
            {"members": id},
            {"created_by": id}
            ]
        })

    group_list = []
    for group in groups:
        group_list.append({
            "id": str(group["_id"]),
            "name": group["title"],
            "type": group.get("type", "Group"),
            "description": group.get("description", "")
        })

    return jsonify(group_list), 200

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



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


