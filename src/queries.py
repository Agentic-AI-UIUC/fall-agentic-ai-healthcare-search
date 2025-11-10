

from sentence_transformers import SentenceTransformer
import embeddings
from user_profile import UserProfile, UserProfileManager


# Uses mpnetv2 right now for querying but can just change it.
model3 = SentenceTransformer('sentence-transformers/LaBSE')
embeddings3 = model3.encode(embeddings.sentences)


def get_contextualized_query(user_query: str, user_profile: UserProfile = None) -> str:

	# Combines user query with their profile information for better context
	if user_profile and user_profile.is_complete():
		return f"{user_profile.get_context_string()}\n\nQuery: {user_query}"
	return user_query


def setup_user_profile(manager: UserProfileManager):
	# Interactive setup for user profile
	print("USER PROFILE SETUP")
	
	# Check for existing profiles
	existing_profiles = manager.list_profiles()
	if existing_profiles:
		print("\nExisting profiles found:")
		for i, name in enumerate(existing_profiles, 1):
			print(f"  {i}. {name}")
		
		choice = input("\nLoad existing profile? (yes/no): ").strip().lower()
		if choice in ['yes', 'y']:
			name = input("Enter name to load: ").strip()
			profile = manager.load_profile(name)
			if profile:
				return profile
	
	# Create new profile
	print("\nCreating new profile...")
	profile = UserProfile()
	
	name = input("Name: ").strip()
	gender = input("Gender (Male/Female/Other): ").strip()
	age = int(input("Age: ").strip())
	weight = float(input("Weight (kg): ").strip())
	
	conditions_input = input("Previous medical conditions (comma-separated, or press Enter for none): ").strip()
	conditions = [c.strip() for c in conditions_input.split(',')] if conditions_input else []
	
	profile.set_info(name, gender, age, weight, conditions)
	manager.save_profile(profile)
	
	print("\n Profile created successfully!")
	return profile


#To exit the query, type exit
#Wait for it to query, its encoding first so...

if __name__ == "__main__":
	print("HEALTHCARE QUERY SYSTEM WITH USER PROFILES")
	
	# Initialize profile manager
	manager = UserProfileManager()
	
	# Ask if user wants to use profile
	use_profile = input("\nWould you like to set up a user profile? (yes/no): ").strip().lower()
	
	user_profile = None
	if use_profile in ['yes', 'y']:
		user_profile = setup_user_profile(manager)
		print("ACTIVE PROFILE:")
		print(user_profile)
	
	print("\nType your query and get the top 3 most similar content items.")
	print("Type 'exit' to quit, 'profile' to view current profile.")
	
	while True:
		user_query = input("\nEnter your query: ")
		
		if user_query.strip().lower() == 'exit':
			break
		
		if user_query.strip().lower() == 'profile':
			if user_profile:
				print(user_profile)
			else:
				print("No profile loaded. Use a profile by restarting and selecting 'yes'.")
			continue
		
		# Get contextualized query if profile exists
		contextualized_query = get_contextualized_query(user_query, user_profile)
		
		# Use the contextualized query for better results
		top3 = embeddings.get_top_k_similar_content(contextualized_query, embeddings3, embeddings.sentences, model3, k=3)
		
		if user_profile:
			print("(Query processed with user profile context)")
		print("Top 3 most similar content:")
		for i, content in enumerate(top3, 1):
			print(f"\n{i}. {content[:500]}...")  # Show first 500 chars
