import time

import streamlit as st
import redis
import json
from openai import OpenAI
import os
from regenerate_all import generate_all_patient_data

# Set your OpenAI API key
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Connect to Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def get_all_patient_names():
    keys = redis_client.keys('patient:*')
    patient_names = [key.decode('utf-8').split(':', 1)[1] for key in keys]
    return list(set(patient_names))

def get_prescriptions_by_patient(patient_name):
    image_hashes = redis_client.smembers(f"patient:{patient_name}")
    prescriptions = []
    for image_hash in image_hashes:
        image_hash = image_hash.decode('utf-8') if isinstance(image_hash, bytes) else image_hash
        prescription_data = redis_client.hgetall(image_hash)
        # Decode bytes to strings
        prescription = {key.decode('utf-8'): value.decode('utf-8') for key, value in prescription_data.items()}
        # If 'details' is a JSON string, parse it
        if 'details' in prescription:
            try:
                prescription['details'] = json.loads(prescription['details'])
            except json.JSONDecodeError:
                pass
        prescriptions.append(prescription)
    return prescriptions

def summarize_patient_data(patient_name, prescriptions):
    # Prepare the data to send to GPT
    prescription_texts = []
    for prescription in prescriptions:
        details = prescription.get('details')
        if isinstance(details, dict):
            details_text = json.dumps(details, indent=2)
        else:
            details_text = details
        prescription_texts.append(details_text)

    combined_text = "\n\n".join(prescription_texts)

    # Prompt for GPT
    prompt = f"""
You are a medical assistant for the Doctor. Please provide a comprehensive summary for the patient named {patient_name} based on the following prescription records.

**Instructions**:
- Omit any patient personal information like phone number, address, etc.
- For details that can change over time (e.g., weight, height, blood pressure), mention the record date alongside each entry.
- Present the information in a clear and concise manner.

**Prescription Records**:
{combined_text}

The summary should be useful for a doctor to quickly assess the patient's history at a glance.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0
    )

    summary = response.choices[0].message.content.strip()
    return summary


def regenerate_all():
    import time
    generate_all_patient_data()
    st.success("All summaries have been regenerated.")
    st.experimental_set_query_params(_=str(time.time()))


def main():
    st.title("Dr.CoPilot")

    # Fetch patient names
    patient_names = get_all_patient_names()

    if not patient_names:
        st.warning("No patients found in the database.")
        return

    # Add the "Regenerate All Summaries" button
    if st.button("Regenerate All Summaries"):
        with st.spinner("Regenerating all summaries..."):
            regenerate_all()
    else:
        # Auto-complete patient name input
        patient_name = st.selectbox("Select a patient", sorted(patient_names))

        if patient_name:
            # Fetch prescriptions for the selected patient
            prescriptions = get_prescriptions_by_patient(patient_name)
            if prescriptions:
                if st.button("Generate Summary"):
                    with st.spinner("Generating summary..."):
                        summary = summarize_patient_data(patient_name, prescriptions)
                    st.subheader("Patient Summary")
                    st.markdown(summary)

                # Text input for "Current prescription"
                prescription_input = st.text_input("Enter prescription details ")

                # Display the entered prescription after user hits enter
                if prescription_input:
                    with st.spinner("Generating summary..."):
                        prompt_1 = f"""
                        Below is the past medical history of the patient {patient_name}. 
                        -------------------
                        This are all the raw prescription data -- {prescriptions}
                        -------------------
                        Now, the patient has come with the following issue and the current problem is 
                        {prescription_input}
                        -------------------
                        Please keep in mind, the patient past history and suggest any possible causes along with drug suggestions.
                        """
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "user", "content": prompt_1}
                            ],
                            max_tokens=500,
                            temperature=0
                        )
                        st.markdown(response.choices[0].message.content.strip())
            else:
                st.warning(f"No prescriptions found for {patient_name}.")


if __name__ == "__main__":
    main()
