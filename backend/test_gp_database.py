#!/usr/bin/env python3
"""
Test GP document upload and database saving
"""

import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

async def test_gp_database():
    """Test GP database collections and data"""
    
    print("🧪 Testing GP Database Integration")
    print("=" * 50)
    
    # Connect to MongoDB
    mongodb_url = os.getenv("MONGODB_URL")
    database_name = os.getenv("DATABASE_NAME", "surgiscan")
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ MongoDB connected successfully")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"📊 Collections in database: {collections}")
        
        # Check GP-specific collections
        gp_collections = [c for c in collections if 'gp' in c.lower()]
        print(f"🏥 GP-related collections: {gp_collections}")
        
        # Check if gp_patients collection exists and has data
        if "gp_patients" in collections:
            patient_count = await db.gp_patients.count_documents({})
            print(f"👥 GP Patients in database: {patient_count}")
            
            # Show sample patient if any
            if patient_count > 0:
                sample_patient = await db.gp_patients.find_one({})
                print(f"📄 Sample patient structure:")
                print(f"   - Patient ID: {sample_patient.get('patient_id')}")
                print(f"   - Filename: {sample_patient.get('filename')}")
                print(f"   - Created: {sample_patient.get('created_at')}")
                print(f"   - Validated: {sample_patient.get('is_validated')}")
                print(f"   - Extractions: {list(sample_patient.get('extractions', {}).keys())}")
        else:
            print("ℹ️  gp_patients collection doesn't exist yet - will be created on first upload")
        
        # Check if gp_parsed_documents collection exists
        if "gp_parsed_documents" in collections:
            parsed_count = await db.gp_parsed_documents.count_documents({})
            print(f"📚 GP Parsed documents: {parsed_count}")
        
        # Check historic_documents collection (main documents)
        if "historic_documents" in collections:
            historic_count = await db.historic_documents.count_documents({})
            print(f"🗄️  Historic documents: {historic_count}")
        
        print("\n✅ Database test complete!")
        print("\nYou can now:")
        print("1. Upload GP documents via the frontend")
        print("2. Validate extracted data")
        print("3. Check database for saved documents")
        
    except Exception as e:
        print(f"❌ Error testing database: {e}")
    
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_gp_database())