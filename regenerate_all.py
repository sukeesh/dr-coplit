import base64
import requests
import os
import hashlib
import redis
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# OpenAI API Key
api_key = os.getenv('OPENAI_API_KEY')

# Connect to Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)


# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


# Function to hash the image file
def hash_image(image_path):
    hasher = hashlib.md5()
    with open(image_path, 'rb') as image_file:
        # Read the file in chunks
        while chunk := image_file.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


# Function to get image details from GPT
def get_image_details(base64_image):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please extract all relevant details from this prescription image including patient name, prescribed drugs, dosage, and any notes."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if response.status_code != 200:
        logging.error(f"Error fetching details from GPT: {response.status_code} - {response.text}")
        return {}

    return response.json()

# Main function to process images in the directory
def process_images_in_directory(base_directory):
    for patient_directory in os.listdir(base_directory):
        patient_path = os.path.join(base_directory, patient_directory)

        if os.path.isdir(patient_path):
            patient_name = patient_directory

            for filename in os.listdir(patient_path):
                if filename.endswith(".jpg") or filename.endswith(".jpeg"):
                    image_path = os.path.join(patient_path, filename)

                    # Hash the image file
                    image_hash = hash_image(image_path)

                    # Check if the image has been processed
                    if redis_client.exists(image_hash):
                        logging.info(f"Image {filename} for patient {patient_name} already processed.")
                        continue

                    # Getting the base64 string
                    base64_image = encode_image(image_path)

                    # Get image details from GPT
                    image_details = get_image_details(base64_image)

                    if not image_details:
                        logging.error(f"No details returned for image {filename}. Skipping.")
                        continue

                    # Assuming the response contains structured details
                    prescription_details = {
                        "filename": filename,
                        "hash": image_hash,
                        "patient_name": patient_name,
                        "details": image_details  # Customize this based on the response
                    }

                    # Convert all values to strings
                    prescription_details_str = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in
                                                prescription_details.items()}

                    # Log the types of each value
                    for key, value in prescription_details_str.items():
                        logging.debug(f"Key: {key}, Type: {type(value)}")

                    # Store the details in Redis
                    redis_client.hset(image_hash, mapping=prescription_details_str)

                    # Index the prescription by patient name
                    redis_client.sadd(f"patient:{patient_name}", image_hash)

                    logging.info(f"Processed {filename} for patient {patient_name}: {prescription_details}")

if __name__ == "__main__":
    # Base directory to your patient images
    base_images_directory = "/Users/sukeesh/workspace/sukeesh/drcopilot/assets/patients/"
    process_images_in_directory(base_images_directory)

def generate_all_patient_data():
    baseimages_directory = "/Users/sukeesh/workspace/sukeesh/drcopilot/assets/patients/"
    process_images_in_directory(baseimages_directory)
