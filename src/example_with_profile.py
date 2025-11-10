
# Example: Healthcare Query System with User Profile Integration


from user_profile import UserProfile, UserProfileManager
import embeddings
from sentence_transformers import SentenceTransformer


def generate_personalized_response(query: str, retrieved_content: list, user_profile: UserProfile = None) -> str:

    # Generate a response that considers the user's background
    # Build the context
    context_parts = []
    
    # Add user profile if available
    if user_profile and user_profile.is_complete():
        context_parts.append("PATIENT CONTEXT:")
        context_parts.append(user_profile.get_context_string())

    
    # Add the query
    context_parts.append(f"\nPatient Question: {query}")
    
    # Add retrieved medical information
    context_parts.append("RELEVANT MEDICAL INFORMATION:")
    for i, content in enumerate(retrieved_content, 1):
        context_parts.append(f"\nSource {i}:")
        context_parts.append(content[:500] + "...\n")  # Show first 500 chars
    
    # Instructions for the LLM (when you integrate one)
    instructions = """
    
    INSTRUCTIONS FOR RESPONSE:
    - Consider the patient's age, gender, weight, and medical history
    - Provide advice appropriate for their demographic
    - Note any contraindications based on previous conditions
    - Adjust recommendations for their age group
    - Use empathetic, clear language
    - Always recommend professional medical consultation for serious concerns
    """
    
    context_parts.append(instructions)
    
    full_context = "\n".join(context_parts)
    
    # pass full_context to the LLM here
    # For now, we'll just return the formatted context
    
    return full_context


def main():
    #example
    print("PERSONALIZED HEALTHCARE QUERY SYSTEM - EXAMPLE")
    print("=" * 60)
    
    # Initialize components
    manager = UserProfileManager()
    
    # Example 1: Create a profile for a diabetic patient
    print("\n--- EXAMPLE 1: Diabetic Patient ---")
    profile1 = UserProfile()
    profile1.set_info(
        name="Sarah Johnson",
        gender="Female",
        age=45,
        weight=68.5,
        previous_conditions=["Type 2 Diabetes", "Hypertension"]
    )
    
    # Save the profile
    manager.save_profile(profile1)
    print(profile1)
    
    # Example query
    query1 = "I'm experiencing frequent headaches. What could be the cause?"
    
    print(f"\nQuery: {query1}")
    
    # Simulate retrieved content (in real scenario, this comes from embeddings search)
    mock_retrieved = [
        "Headaches can be caused by various factors including stress, dehydration, high blood pressure, or blood sugar fluctuations...",
        "For diabetic patients, headaches may indicate blood sugar imbalances. Both hypoglycemia and hyperglycemia can cause headaches...",
        "Hypertension is a common cause of headaches, particularly in the morning or at the back of the head..."
    ]
    
    # Generate personalized response
    response = generate_personalized_response(query1, mock_retrieved, profile1)
    print("PERSONALIZED RESPONSE CONTEXT:")
    print("=" * 60)
    print(response)
    
    # Example 2: Elderly patient
    print("\n\n--- EXAMPLE 2: Elderly Patient ---")
    profile2 = UserProfile()
    profile2.set_info(
        name="Robert Chen",
        gender="Male",
        age=72,
        weight=70.0,
        previous_conditions=["Osteoarthritis", "Heart Disease", "High Cholesterol"]
    )
    
    manager.save_profile(profile2)
    print(profile2)
    
    query2 = "What exercises are safe for me to do?"
    print(f"\nQuery: {query2}")
    
    mock_retrieved2 = [
        "Exercise is important for maintaining health, but should be appropriate for your age and condition...",
        "For patients with heart disease, low-impact exercises like walking and swimming are recommended...",
        "Arthritis patients should focus on gentle exercises that don't stress the joints..."
    ]
    
    response2 = generate_personalized_response(query2, mock_retrieved2, profile2)
    print("PERSONALIZED RESPONSE CONTEXT:")
    print("=" * 60)
    print(response2)
    
    # Show all saved profiles
    print("ALL SAVED PROFILES:")
    print("=" * 60)
    profiles = manager.list_profiles()
    for name in profiles:
        print(f"  ✓ {name}")


if __name__ == "__main__":
    main()
