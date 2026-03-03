# User Profile Management System
# Handles user information storage and retrieval using JSON files


import json
import os
from datetime import datetime
from typing import List, Optional, Dict


class UserProfile:
    # Stores and manages user health information
    
    def __init__(self):
        self.name: Optional[str] = None
        self.gender: Optional[str] = None
        self.age: Optional[int] = None
        self.weight: Optional[float] = None
        self.previous_conditions: List[str] = []
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
    
    def set_info(self, name: str, gender: str, age: int, weight: float, 
                 previous_conditions: Optional[List[str]] = None):
        # Set user information
        self.name = name
        self.gender = gender
        self.age = age
        self.weight = weight
        
        if previous_conditions:
            self.previous_conditions = previous_conditions
        else:
            self.previous_conditions = []
        
        # Set timestamps
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def add_condition(self, condition: str):
        # Add a new condition to the user's medical history
        if condition not in self.previous_conditions:
            self.previous_conditions.append(condition)
            self.updated_at = datetime.now().isoformat()
    
    def remove_condition(self, condition: str):
        # Remove a condition from the user's medical history
        if condition in self.previous_conditions:
            self.previous_conditions.remove(condition)
            self.updated_at = datetime.now().isoformat()
    
    def get_context_string(self) -> str:
        # Returns formatted user info for LLM context
        conditions_str = ', '.join(self.previous_conditions) if self.previous_conditions else 'None reported'
        
        return f"""Patient Profile:
- Name: {self.name}
- Gender: {self.gender}
- Age: {self.age} years old
- Weight: {self.weight} kg
- Previous Medical Conditions: {conditions_str}"""
    
    def to_dict(self) -> Dict:
        # Convert profile to dictionary for JSON serialization
        return {
            'name': self.name,
            'gender': self.gender,
            'age': self.age,
            'weight': self.weight,
            'previous_conditions': self.previous_conditions,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def from_dict(self, data: Dict):
        # loads profile fromd dict
        self.name = data.get('name')
        self.gender = data.get('gender')
        self.age = data.get('age')
        self.weight = data.get('weight')
        self.previous_conditions = data.get('previous_conditions', [])
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
    
    def is_complete(self) -> bool:
        return all([
            self.name,
            self.gender,
            self.age is not None,
            self.weight is not None
        ])
    
    def __str__(self) -> str:
        return self.get_context_string()


class UserProfileManager:
    # Manages user profile persistence using JSON files
    
    def __init__(self, profiles_dir: str = 'user_profiles'):
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.profiles_dir = os.path.join(script_dir, profiles_dir)
        
        # Create directory if it doesn't exist
        os.makedirs(self.profiles_dir, exist_ok=True)
    
    def _get_profile_path(self, user_name: str) -> str:
        safe_name = "".join(c for c in user_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_').lower()
        return os.path.join(self.profiles_dir, f"{safe_name}.json")
    
    def save_profile(self, profile: UserProfile) -> bool:
        # Save a user profile to JSON file
        try:
            if not profile.name:
                raise ValueError("Profile must have a name to be saved")
            
            file_path = self._get_profile_path(profile.name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, indent=4, ensure_ascii=False)
            
            print(f"Profile saved successfully: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error saving profile: {e}")
            return False
    
    def load_profile(self, user_name: str) -> Optional[UserProfile]:
        # Load a user profile from JSON file

        try:
            file_path = self._get_profile_path(user_name)
            
            if not os.path.exists(file_path):
                print(f"No profile found for user: {user_name}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            profile = UserProfile()
            profile.from_dict(data)
            
            print(f"Profile loaded successfully: {user_name}")
            return profile
            
        except Exception as e:
            print(f"Error loading profile: {e}")
            return None
    
    def profile_exists(self, user_name: str) -> bool:
        # Check if a profile exists for a user

        file_path = self._get_profile_path(user_name)
        return os.path.exists(file_path)
    
    def list_profiles(self) -> List[str]:

        try:
            if not os.path.exists(self.profiles_dir):
                return []
            
            profiles = []
            for filename in os.listdir(self.profiles_dir):
                if filename.endswith('.json'):
                    # Load the profile to get the actual name
                    file_path = os.path.join(self.profiles_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'name' in data:
                            profiles.append(data['name'])
            
            return profiles
            
        except Exception as e:
            print(f"Error listing profiles: {e}")
            return []
    
    def delete_profile(self, user_name: str) -> bool:
        # Delete a user profile

        try:
            file_path = self._get_profile_path(user_name)
            
            if not os.path.exists(file_path):
                print(f"No profile found for user: {user_name}")
                return False
            
            os.remove(file_path)
            print(f"Profile deleted successfully: {user_name}")
            return True
            
        except Exception as e:
            print(f"Error deleting profile: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    # Create a profile manager
    manager = UserProfileManager()
    
    # Create a new user profile
    profile = UserProfile()
    profile.set_info(
        name="John Doe",
        gender="Male",
        age=35,
        weight=75.5,
        previous_conditions=["Hypertension", "Type 2 Diabetes"]
    )
    
    print("Created Profile:")
    print(profile)
    
    # Save the profile
    manager.save_profile(profile)
    
    # Load the profile
    loaded_profile = manager.load_profile("John Doe")
    if loaded_profile:
        print("Loaded Profile:")
        print(loaded_profile)
    
    # List all profiles
    print("All saved profiles:")
    for name in manager.list_profiles():
        print(f"  - {name}")
