import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load your environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Use Service Role Key

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_KEY in your .env file.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Map your local directories to your Supabase storage buckets
MAPPING = {
    "wiki": "wiki",          # local folder -> bucket name
    "raw": "raw",
    "Clippings": "clippings",
    "Skills": "skills"
}

def upload_local_data():
    root_dir = Path(__file__).parent
    
    for local_folder, bucket_name in MAPPING.items():
        folder_path = root_dir / local_folder
        
        if not folder_path.exists():
            print(f"⚠️ Local folder '{local_folder}' not found. Skipping...")
            continue
            
        print(f"\n🚀 Scanning local folder '{local_folder}' for upload to bucket '{bucket_name}'...")
        
        # Grab all files in the directory (skipping subdirectories for now)
        files = [f for f in folder_path.iterdir() if f.is_file()]
        
        if not files:
            print(f"  ↳ No files found in '{local_folder}'.")
            continue
            
        for file_path in files:
            filename = file_path.name
            if filename.startswith('.'): # Skip system files like .DS_Store
                continue
                
            print(f"  ↳ Uploading {filename}...", end="", flush=True)
            
            try:
                with open(file_path, "rb") as f:
                    file_data = f.read()
                
                # Determine basic content type header
                content_type = "text/plain"
                if filename.endswith(".md"):
                    content_type = "text/markdown"
                elif filename.endswith(".py"):
                    content_type = "text/x-python"

                supabase.storage.from_(bucket_name).upload(
                    path=filename,
                    file=file_data,
                    file_options={"x-upsert": "true", "content-type": content_type}
                )
                print(" ✅ Success")
            except Exception as e:
                print(f" ❌ Failed: {str(e)}")

if __name__ == "__main__":
    print("✨ Starting Wiki-LLM Local-to-Cloud Migration Script ✨")
    upload_local_data()
    print("\n🎉 Migration completed!")