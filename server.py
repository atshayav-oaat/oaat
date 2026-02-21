from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import boto3
import requests
from supabase import create_client

app = Flask(__name__)
CORS(app) # Essential for Framer to talk to Render

# Config from Environment Variables
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
rekognition = boto3.client('rekognition', 
    region_name='us-east-1',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

@app.route('/linkedin-oidc', methods=['POST'])
def linkedin_sync():
    data = request.json
    # Sync LinkedIn data to your Supabase table
    try:
        supabase.table("oneatatime_userlist").upsert({
            "id": data.get("sub"),
            "full_name": data.get("name"),
            "linkedin_photo": data.get("picture"),
            "email": data.get("email"),
            "verification_status": "pending_selfie"
        }).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/send-otp', methods=['POST'])
def send_otp():
    # Add your WhatsApp Logic here using os.getenv("WHATSAPP_TOKEN")
    return jsonify({"success": True})

@app.route('/verify-selfie', methods=['POST'])
def verify_selfie():
    data = request.json
    user_id = data.get("user_id")
    selfie_base64 = data.get("selfie").split(",")[1] # Strip the data:image prefix

    # 1. Get user data for the LinkedIn Photo URL
    user = supabase.table("oneatatime_userlist").select("linkedin_photo").eq("id", user_id).single().execute()
    li_photo_url = user.data['linkedin_photo']

    # 2. Compare via AWS Rekognition
    try:
        li_photo_bytes = requests.get(li_photo_url).content
        import base64
        selfie_bytes = base64.b64decode(selfie_base64)

        response = rekognition.compare_faces(
            SourceImage={'Bytes': li_photo_bytes},
            TargetImage={'Bytes': selfie_bytes},
            SimilarityThreshold=80
        )

        match = len(response['FaceMatches']) > 0
        if match:
            supabase.table("oneatatime_userlist").update({"verification_status": "verified"}).eq("id", user_id).execute()
        
        return jsonify({"match": match, "similarity": response['FaceMatches'][0]['Similarity'] if match else 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
