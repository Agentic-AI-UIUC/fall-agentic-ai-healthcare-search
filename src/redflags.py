
from sentence_transformers import SentenceTransformer, util
import pandas as pd

#this checks for embedded and non embedded queries

#hard coded keywords. based on https://www.greenecountyga.gov/257/Recognizing-a-Medical-Emergency + LLM
EMERGENCY_KEYWORDS = {
    "bleeding_uncontrolled": {
        "keywords": ["bleeding that will not stop", "uncontrolled bleeding", "severe bleeding", "hemorrhage", "bleeding won't stop"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Uncontrolled bleeding can lead to shock and be life-threatening"
    },
    "breathing_problems": {
        "keywords": ["breathing problems", "difficulty breathing", "shortness of breath", "can't breathe", "trouble breathing", "choking", "severe asthma attack"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Breathing difficulties can be life-threatening and require immediate intervention"
    },
    "mental_status_change": {
        "keywords": ["change in mental status", "unusual behavior", "confusion", "difficulty arousing", "altered mental state", "disoriented", "not responding normally"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Changes in mental status can indicate serious neurological or medical conditions"
    },
    "chest_pain": {
        "keywords": ["chest pain", "heart attack", "cardiac arrest", "crushing chest pain", "chest pressure"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Chest pain can indicate a heart attack or other serious cardiac condition"
    },
    "choking": {
        "keywords": ["choking", "can't swallow", "something stuck in throat", "airway blocked"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 and perform Heimlich maneuver if trained",
        "reason": "Choking can cause airway obstruction and be fatal within minutes"
    },
    "blood_vomit_cough": {
        "keywords": ["coughing up blood", "vomiting blood", "blood in vomit", "hemoptysis", "hematemesis", "spitting up blood"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Coughing up or vomiting blood can indicate serious internal bleeding"
    },
    "loss_consciousness": {
        "keywords": ["fainting", "loss of consciousness", "passed out", "unconscious", "fainted", "blacked out", "syncope"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Loss of consciousness can indicate serious cardiovascular or neurological issues"
    },
    "suicidal_homicidal": {
        "keywords": ["feeling of committing suicide", "want to kill myself", "suicidal thoughts", "want to hurt someone", "homicidal thoughts", "feeling of murder"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911, National Suicide Prevention Lifeline (988), or go to nearest emergency room",
        "reason": "Suicidal or homicidal thoughts require immediate psychiatric intervention"
    },
    "head_spine_injury": {
        "keywords": ["head injury", "spine injury", "spinal cord injury", "neck injury", "traumatic brain injury", "concussion", "head trauma"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 and do not move the person",
        "reason": "Head or spine injuries can cause permanent disability or death if not treated properly"
    },
    "severe_vomiting": {
        "keywords": ["severe vomiting", "persistent vomiting", "can't stop vomiting", "continuous vomiting", "projectile vomiting"],
        "action": "SEEK EMERGENCY CARE - Go to emergency room if unable to keep fluids down",
        "reason": "Severe or persistent vomiting can lead to dehydration and electrolyte imbalances"
    },
    "sudden_injury": {
        "keywords": ["motor vehicle accident", "car accident", "burns", "smoke inhalation", "near drowning", "deep wound", "large wound", "severe trauma"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911",
        "reason": "Sudden severe injuries require immediate medical assessment and treatment"
    },
    "sudden_severe_pain": {
        "keywords": ["sudden severe pain", "worst pain ever", "excruciating pain", "unbearable pain", "sudden pain anywhere"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 or go to nearest emergency room",
        "reason": "Sudden severe pain may indicate serious conditions like heart attack, stroke, or internal bleeding"
    },
    "sudden_neurological": {
        "keywords": ["sudden dizziness", "sudden weakness", "change in vision", "sudden vision loss", "sudden blindness", "sudden numbness"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911",
        "reason": "Sudden neurological symptoms can indicate stroke or other serious brain conditions"
    },
    "poisoning": {
        "keywords": ["swallowed poison", "poisonous substance", "toxic ingestion", "overdose", "poisoning"],
        "action": "SEEK EMERGENCY CARE IMMEDIATELY - Call 911 and Poison Control (1-800-222-1222)",
        "reason": "Poisoning can be fatal and requires immediate treatment and decontamination"
    },
    "upper_abdominal_pain": {
        "keywords": ["upper abdominal pain", "upper stomach pain", "abdominal pressure", "severe stomach pain", "epigastric pain"],
        "action": "SEEK EMERGENCY CARE - Go to emergency room, especially if severe or with other symptoms",
        "reason": "Upper abdominal pain can indicate heart attack, gallbladder issues, or other serious conditions"
    }
}

def check_emergency_flags(user_query, use_embeddings=True, similarity_threshold=0.7):
    # user_query is a string of the user's input query
    # use_embeddings is a bool, whether to use semantic similarity in addition to keyword matching
    # similarity_threshold is a threshold for semantic similarity (embedded matching)

    user_query_lower = user_query.lower()
    
    for emergency_type, info in EMERGENCY_KEYWORDS.items():
        for keyword in info["keywords"]:
            if keyword.lower() in user_query_lower:
                return {
                    "is_emergency": True,
                    "emergency_type": emergency_type,
                    "action": info["action"],
                    "reason": info["reason"],
                    "confidence": 1.0,
                    "match_type": "keyword"
                }
    
    # If no direct matches and embeddings are enabled, check semantic similarity
    if use_embeddings:
        try:
            model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

            user_embedding = model.encode([user_query])
            
            best_match = None
            best_similarity = 0.0
            
            for emergency_type, info in EMERGENCY_KEYWORDS.items():
                for keyword in info["keywords"]:
                    keyword_embedding = model.encode([keyword])
                    similarity = util.cos_sim(user_embedding, keyword_embedding)[0][0].item()
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = (emergency_type, info)
            
            # above threshold
            if best_similarity >= similarity_threshold:
                return {
                    "is_emergency": True,
                    "emergency_type": best_match[0],
                    "action": best_match[1]["action"],
                    "reason": best_match[1]["reason"],
                    "confidence": best_similarity,
                    "match_type": "semantic"
                }
        
        except Exception as e:
            print(f"Error in semantic matching: {e}")
    
    # No emergency detected
    return {
        "is_emergency": False,
        "emergency_type": None,
        "action": None,
        "reason": None,
        "confidence": 0.0,
        "match_type": None
    }

def format_emergency_response(emergency_result):

    if not emergency_result["is_emergency"]:
        return None
    
    message = "MEDICAL EMERGENCY DETECTED \n\n"
    message += f"**{emergency_result['action']}**\n\n"
    message += f"Reason: {emergency_result['reason']}\n\n"
    message += f"Detection confidence: {emergency_result['confidence']:.2f}\n"
    message += f"Match type: {emergency_result['match_type']}\n\n"
    
    return message

#test
if __name__ == "__main__":
    test_queries = [
        "I have chest pain and shortness of breath",
        "My arm hurts a little",
        "I can't breathe properly", 
        "Sudden vision problems",
        "I fainted at work today",
        "There's blood in my vomit",
        "The bleeding won't stop from this cut",
        "I'm feeling confused and disoriented",
        "I'm choking on something",
        "I was in a car accident and hit my head",
        "I can't stop vomiting for the past 6 hours",
        "I have sudden severe pain in my stomach",
        "I'm having thoughts of hurting myself",
        "I accidentally swallowed cleaning fluid",
        "I have a mild headache"
    ]
    
    print("Testing emergency flag detection:\n")
    for query in test_queries:
        result = check_emergency_flags(query)
        print(f"Query: '{query}'")
        print(f"Emergency: {result['is_emergency']}")
        if result["is_emergency"]:
            print(format_emergency_response(result))