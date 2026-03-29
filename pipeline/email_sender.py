import os
import resend
from typing import Dict, Any

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate


def send_email_via_resend(receiver_email: str, subject: str, content: str) -> bool:
    """
    Sends an email using the Resend API.
    Requires RESEND_API_KEY in environment.
    During testing (no custom domain), sender is onboarding@resend.dev
    and Resend only allows sending to the account owner's email.
    Once you add a custom domain, you can send to anyone.
    """
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        # Simulation mode — no API key configured
        print("\n--- SIMULATED EMAIL SEND ---")
        print(f"To: {receiver_email}")
        print(f"Subject: {subject}")
        print(content)
        print("----------------------------\n")
        print("Set RESEND_API_KEY in your .env to actually send emails.")
        return True

    try:
        resend.api_key = api_key

        # Use your verified sender address here once you add a domain in Resend.
        # For testing with the free sandbox, use: onboarding@resend.dev
        sender = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

        params: resend.Emails.SendParams = {
            "from": sender,
            "to": [receiver_email],
            "subject": subject,
            "text": content,
        }

        email = resend.Emails.send(params)
        print(f"Email sent via Resend. ID: {email.get('id')}")
        return True

    except Exception as e:
        print(f"Failed to send email via Resend: {e}")
        return False


def process_and_send_pre_medical(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Takes raw questionnaire data, formats it nicely using LLM, and sends via Email.
    """
    doctor_email = data.get("doctorEmail", "").strip()
    
    if not doctor_email:
        return {"status": "error", "message": "Doctor's email is required."}

    # Extract all the structured info
    name = data.get("patientName", "Unknown")
    dob = data.get("patientDob", "Unknown")
    gender = data.get("patientGender", "Unknown")
    contact = data.get("patientContact", "Unknown")
    emergency = data.get("emergencyContact", "Unknown")
    insurance = data.get("insuranceInfo", "Unknown")
    referring = data.get("referringPhysician", "Unknown")
    past_ill = data.get("pastIllnesses", "Unknown")
    surgeries = data.get("surgeries", "Unknown")
    immunizations = data.get("immunizations", "Unknown")
    meds = data.get("currentMeds", "Unknown")
    allergies = data.get("allergies", "Unknown")
    fam_history = data.get("familyHistory", "Unknown")
    lifestyle = data.get("lifestyleInfo", "Unknown")
    occupation = data.get("occupation", "Unknown")
    living = data.get("livingSituation", "Unknown")
    mental = data.get("mentalHealth", "Unknown")
    reason = data.get("reason", "Not provided")
    symptoms = data.get("symptoms", "Not provided")
    ros = data.get("reviewOfSystems", "Unknown")
    specialty = data.get("specialtyQuestions", "Unknown")

    # Use LangChain to format the input
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"status": "error", "message": "GROQ_API_KEY not configured for formatting."}

    llm = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=api_key)
    
    # Prompt template strictly instructing not to drop data, just format 
    template = """
    You are a medical assistant formatting a patient's comprehensive pre-consultation intake form for a doctor.
    Take the raw inputs below and present them in a clean, highly professional, easy-to-read clinical format 
    (do not use markdown blocks like ```, just use plain text with clear headings). 
    Do NOT omit any information provided by the patient. If a field says "Unknown" or was left blank, you may briefly note it as "Not provided" or omit it gracefully.

    --- INTAKE DATA ---
    1. DEMOGRAPHICS
    Name: {name}
    DOB: {dob}
    Gender: {gender}
    Contact: {contact}
    Emergency Contact: {emergency}

    2. ADMINISTRATIVE
    Insurance: {insurance}
    Referring Physician: {referring}

    3. MEDICAL HISTORY
    Past Illnesses/Chronic: {past_ill}
    Surgeries/Hospitalizations: {surgeries}
    Immunizations: {immunizations}

    4. MEDICATIONS & ALLERGIES
    Current Meds: {meds}
    Allergies: {allergies}

    5. FAMILY HISTORY
    {fam_history}

    6. SOCIAL & LIFESTYLE
    Lifestyle: {lifestyle}
    Occupation: {occupation}
    Living Situation: {living}

    7. MENTAL HEALTH
    {mental}

    8. CHIEF COMPLAINT (Reason for visit)
    Reason: {reason}
    Symptom Details: {symptoms}

    9. REVIEW OF SYSTEMS (ROS)
    {ros}

    10. SPECIALTY SPECIFIC
    {specialty}
    -------------------
    """

    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm

    try:
        response = chain.invoke({
            "name": name, "dob": dob, "gender": gender, "contact": contact,
            "emergency": emergency, "insurance": insurance, "referring": referring,
            "past_ill": past_ill, "surgeries": surgeries, "immunizations": immunizations,
            "meds": meds, "allergies": allergies, "fam_history": fam_history,
            "lifestyle": lifestyle, "occupation": occupation, "living": living,
            "mental": mental, "reason": reason, "symptoms": symptoms,
            "ros": ros, "specialty": specialty
        })
        
        formatted_content = response.content
    except Exception as e:
        return {"status": "error", "message": f"LLM Formatting failed: {str(e)}"}

    # Send the email
    subject = f"Pre-Consultation Patient Info: {name}"
    success = send_email_via_resend(receiver_email=doctor_email, subject=subject, content=formatted_content)

    if success:
        return {"status": "success", "message": "Email sent successfully! (Or simulated if missing credentials)"}
    else:
        return {"status": "error", "message": "Failed to send the email via Resend."}
