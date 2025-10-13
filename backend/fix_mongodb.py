#!/usr/bin/env python3
"""
MongoDB Connection Fix Script
Provides step-by-step instructions to fix MongoDB Atlas connection
"""

print("""
🔧 MONGODB CONNECTION FIX
========================

Current Issue: Authentication failed for user 'surgiscan-admin'

FOLLOW THESE STEPS:

1️⃣  GO TO MONGODB ATLAS:
   https://cloud.mongodb.com/

2️⃣  CHECK DATABASE ACCESS:
   • Click "Database Access" in left sidebar
   • Look for user: surgiscan-admin
   • If user doesn't exist, CREATE NEW USER:
     - Username: surgiscan-admin
     - Password: [generate strong password]
     - Database User Privileges: Atlas admin

3️⃣  CHECK NETWORK ACCESS:
   • Click "Network Access" in left sidebar
   • Add IP Address: 0.0.0.0/0 (for testing)
   • Comment: "Allow all IPs for testing"

4️⃣  GET NEW CONNECTION STRING:
   • Go to "Databases" → Click "Connect"
   • Choose "Connect your application"
   • Copy connection string
   • Should look like:
     mongodb+srv://surgiscan-admin:<password>@surgiscan-mvp.0lq2ckp.mongodb.net/?retryWrites=true&w=majority&appName=surgiscan-mvp

5️⃣  UPDATE .env FILE:
   Replace MONGODB_URL with new connection string

6️⃣  RUN TEST AGAIN:
   python test_mongodb_connection.py

""")

# Test current connection
import os
from dotenv import load_dotenv

load_dotenv()
current_url = os.getenv("MONGODB_URL", "")

if current_url:
    # Hide password in URL
    safe_url = current_url
    if "@" in safe_url and "://" in safe_url:
        parts = safe_url.split("://")
        if len(parts) == 2:
            protocol = parts[0]
            rest = parts[1]
            if "@" in rest:
                auth_host = rest.split("@")
                if len(auth_host) == 2:
                    auth = auth_host[0]
                    host = auth_host[1]
                    if ":" in auth:
                        user = auth.split(":")[0]
                        safe_url = f"{protocol}://{user}:***@{host}"
    
    print(f"CURRENT CONNECTION STRING:")
    print(f"{safe_url}")
    print()

print("💡 ALTERNATIVE: CREATE NEW MONGODB ATLAS PROJECT")
print("If the above doesn't work, consider creating a fresh MongoDB Atlas project")
print("and update the connection string accordingly.")