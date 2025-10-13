#!/usr/bin/env python3
"""
Check if GP documents were uploaded and saved to database
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

async def check_gp_uploads():
    """Check for GP documents in the database"""
    
    print("🔍 Checking GP Document Uploads")
    print("=" * 50)
    
    # Connect to MongoDB
    mongodb_url = os.getenv("MONGODB_URL")
    database_name = os.getenv("DATABASE_NAME", "surgiscan")
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
        
        # Check all collections for GP data
        collections = await db.list_collection_names()
        gp_collections = [c for c in collections if 'gp' in c.lower()]
        
        print(f"🔍 All collections: {len(collections)}")
        print(f"🏥 GP collections found: {gp_collections}")
        
        # Check gp_patients collection
        if "gp_patients" in collections:
            count = await db.gp_patients.count_documents({})
            print(f"\n📊 GP Patients: {count}")
            
            if count > 0:
                # Show recent uploads
                recent_patients = await db.gp_patients.find({}).sort("created_at", -1).limit(5).to_list(length=5)
                
                for i, patient in enumerate(recent_patients, 1):
                    print(f"\n👤 Patient {i}:")
                    print(f"   Patient ID: {patient.get('patient_id')}")
                    print(f"   Filename: {patient.get('filename')}")
                    print(f"   Created: {patient.get('created_at')}")
                    print(f"   Validated: {patient.get('is_validated', False)}")
                    print(f"   Validation Status: {patient.get('validation_status', 'pending')}")
                    
                    # Show extractions
                    extractions = patient.get('extractions', {})
                    if extractions:
                        print(f"   Data Extracted:")
                        for key in extractions.keys():
                            print(f"     - {key}")
                    
                    # Show confidence scores
                    confidence_scores = patient.get('confidence_scores', {})
                    if confidence_scores:
                        print(f"   Confidence Scores:")
                        for key, score in confidence_scores.items():
                            print(f"     - {key}: {score:.2f}")
                    
                    print("   " + "-" * 40)
        
        # Check gp_parsed_documents collection  
        if "gp_parsed_documents" in collections:
            count = await db.gp_parsed_documents.count_documents({})
            print(f"\n📚 GP Parsed Documents: {count}")
            
            if count > 0:
                recent_docs = await db.gp_parsed_documents.find({}).sort("created_at", -1).limit(3).to_list(length=3)
                for doc in recent_docs:
                    print(f"   📄 Document ID: {doc.get('_id')}")
                    print(f"      Chunks: {len(doc.get('chunks', []))}")
                    print(f"      Created: {doc.get('created_at')}")
        
        # Check if no GP collections exist yet
        if not gp_collections and "gp_patients" not in collections:
            print(f"\n⚠️  No GP collections found yet.")
            print(f"   This could mean:")
            print(f"   1. Upload hasn't completed processing yet")
            print(f"   2. There was an error during processing")
            print(f"   3. Collections will be created on first successful save")
        
        # Check recent activity in logs
        print(f"\n🔍 Checking recent activity...")
        
        # Check historic_documents (might have recent uploads)
        recent_historic = await db.historic_documents.find({}).sort("created_at", -1).limit(3).to_list(length=3)
        if recent_historic:
            print(f"📋 Recent historic documents: {len(recent_historic)}")
            for doc in recent_historic:
                print(f"   - {doc.get('document_filename', 'Unknown')} ({doc.get('created_at')})")
        
        print(f"\n✅ Database check complete!")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_gp_uploads())