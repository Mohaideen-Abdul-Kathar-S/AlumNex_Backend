import difflib
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import gridfs
from PIL import Image, ImageEnhance
import pytesseract
import re
import cv2
import numpy as np
import io

from flask import Flask, request, jsonify
from flask_cors import CORS
import easyocr
import io
import re
import base64
from PIL import Image

app = Flask(__name__)

# CORS setup for your specific frontend origin
CORS(app)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['imageDB']
fs = gridfs.GridFS(db)

"""@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    file_id = fs.put(file, filename=file.filename, metadata={'contentType': file.content_type})
    return jsonify({'message': 'Image uploaded successfully', 'file_id': str(file_id)}), 200"""
    


# Specify the tesseract executable path if needed
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Adjust to your installation path

"""
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    try:
        # Convert uploaded image to PIL image
        image = Image.open(file.stream)

        # Preprocess the image to improve OCR accuracy
        image = image.convert('L')  # Convert to grayscale
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2)  # Increase contrast (adjust value as needed)
        image = image.point(lambda p: p > 180 and 255)  # Apply thresholding

        # OCR - extract text
        extracted_text = pytesseract.image_to_string(image)

        # Debugging: print extracted text to check what the OCR sees
        print("Extracted Text:", extracted_text)

        # Check if it's an ID card (basic pattern or keywords)
        if not re.search(r'ID\s*Card|Identity\s*Card|College\s*ID', extracted_text, re.IGNORECASE):
            return jsonify({'message': 'Uploaded image is not an ID card'}), 400

        # Check if it's from Kongu Engineering College
        if 'Kongu Engineering College' not in extracted_text:
            return jsonify({'message': 'Not a valid Kongu Engineering College ID card'}), 400

        # Extract specific info with more refined regex patterns
        name_match = re.search(r'Name\s*[:\-]?\s*(.*)', extracted_text)
        regno_match = re.search(r'Register\s*Number\s*[:\-]?\s*(\d+)', extracted_text)
        dept_match = re.search(r'Department\s*[:\-]?\s*(.*)', extracted_text)

        name = name_match.group(1).strip() if name_match else 'Not found'
        regno = regno_match.group(1).strip() if regno_match else 'Not found'
        dept = dept_match.group(1).strip() if dept_match else 'Not found'

        # Return the extracted data as a JSON response
        return jsonify({
            'message': 'Valid ID card from Kongu Engineering College',
            'name': name,
            'register_number': regno,
            'department': dept,
            'raw_text': extracted_text  # Optional for debugging purposes
        }), 200

    except Exception as e:
        return jsonify({'message': f'Error processing image: {str(e)}'}), 500 """

text = ""
# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])  # Add languages as needed, e.g. ['en', 'hi']

@app.route('/')
def home():
    return 'EasyOCR Flask server is running!'

@app.route('/upload', methods=['POST'])
def upload_image():
    try:
        data = request.get_json()
        base64_image = data.get('image')

        if not base64_image:
            return jsonify({'error': 'No image data provided'}), 400

        # Extract base64 content (remove prefix if present)
        base64_image = re.sub('^data:image/.+;base64,', '', base64_image)

        # Convert base64 to bytes and open image
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_bytes))

        # Use EasyOCR to read text
        results = reader.readtext(image_bytes)
        extracted_text = "\n".join([res[1] for res in results])
        
        text = extracted_text
        printdata(text)
        
        return jsonify({'text': extracted_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def printdata(text):

# Then apply the regex
    extracted_data = {
        "name": re.search(r"Name\s*\n([A-Za-z ]+)", text),
        "email": re.search(r"\b([\w\.-]+@[\w\.-]+)", text),
        "phone": re.search(r"((?:\+91[\s\-]?)?[6-9]\d{9})", text),
        "dob": re.search(r"DOB\s*\n([^\n]+)", text),
        "program_branch": re.search(r"Pursuing\s+([^\n]+)", text),
        "college": re.search(r"at\s+(Kongu Engineering College)", text),
        "cgpa": re.search(r"CGPA\s*[:\-]?\s*([\d\.]+)", text),
        "hsc_percent": re.search(r"with\s+(\d+)%", text),
        "skills": re.findall(r"\b(C|Java|Python|Dart|HTML|CSS|Spring Boot|MongoDB|Flutter|Oracle)\b", text),
        "projects": re.search(r"(TNEA Counselling Helper.*?)Mobile App", text, re.DOTALL),
        "certifications": re.search(r"(Completed an Internship.*?)training", text, re.DOTALL),
        "interests": re.search(r"(Backend Developer.*?)Spring Boot", text, re.DOTALL),
        "domain": re.search(r"(Spring Boot,Flutter.*?)Figma", text, re.DOTALL),
    }

    # Display the results
    print("\n--- Extracted Resume Data ---\n")
    for field, match in extracted_data.items():
        if isinstance(match, list):
            print(f"{field}: {', '.join(match)}")
        elif match:
            print(f"{field}: {match.group(1).strip()}")
        else:
            print(f"{field}: Not found")
























def collect_information(extracted_text):
    lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]

    # Check for both "KONGU" and "ENGINEERING COLLEGE"
    kongu_present = any('KONGU' in line.upper() for line in lines)
    engg_present = any('ENGINEERING COLLEGE' in line.upper() for line in lines)

    if kongu_present and engg_present and len(lines) >= 10:
        # Assuming fixed positions
        name = lines[6]
        branch = lines[7]
        roll_number = lines[8]
        phone = ''

        # Search from the end for a 10-digit number
        for line in reversed(lines):
            match = re.search(r'\b\d{10}\b', line)
            if match:
                phone = match.group(0)
                break

        print("Name:", name)
        print("Branch:", branch)
        print("Roll Number:", roll_number)
        print("Phone:", phone)
    else:
        print("This is not a valid Kongu ID card text.")



@app.route('/get-image', methods=['GET'])
def get_image():
    file = fs.find().sort('uploadDate', -1).limit(1)[0]
    return send_file(
        io.BytesIO(file.read()),
        mimetype=file.metadata.get('contentType', 'image/jpeg'),
        as_attachment=False
    )

@app.route('/list-images', methods=['GET'])
def list_images():
    files = fs.find()
    images = [{'id': str(file._id), 'filename': file.filename} for file in files]
    return jsonify(images)

from gridfs.errors import NoFile

@app.route('/get-image-by-id', methods=['GET'])
def get_image_by_id():
    image_id = request.args.get('id')
    if not image_id:
        return jsonify({'message': 'No image ID provided'}), 400

    try:
        from bson import ObjectId
        image_id = ObjectId(image_id)
        
        try:
            file = fs.get(image_id)  # Try to fetch the image using GridFS
        except NoFile:
            return jsonify({'message': 'File not found'}), 404

        return send_file(
            io.BytesIO(file.read()),
            mimetype=file.metadata.get('contentType', 'image/jpeg'),
            as_attachment=False
        )
    except Exception as e:
        print(f"Error fetching image with ID {image_id}: {str(e)}")
        return jsonify({'message': 'Error fetching image', 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
