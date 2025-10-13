#!/usr/bin/env python3
"""
Test GP Document Processing Complete Flow
Upload → Parse → Extract → Save to MongoDB
"""

import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Your imports
from app.services.gp_processor import GPDocumentProcessor
from app.services.database import DatabaseManager

load_dotenv()

async def test_complete_flow():
    """Test: Upload → Parse → Extract → Save to MongoDB"""
    
    print("🧪 Testing GP Document Processing Flow\n")
    
    # Initialize database
    db_manager = DatabaseManager(
        connection_string=os.getenv("MONGODB_URL"),
        db_name=os.getenv("DATABASE_NAME")
    )
    
    connected = await db_manager.connect()
    if not connected:
        print("❌ Database connection failed!")
        return
    
    print("✅ Database connected\n")
    
    # Initialize processor
    processor = GPDocumentProcessor(db_manager=db_manager)
    
    # Test with a sample file - you can update this path
    test_file = "test_sample.pdf"  # Update this path to your test file
    organization_id = "test-gp-practice-001"
    
    # Check if test file exists, if not create a simple one for testing
    if not os.path.exists(test_file):
        print(f"⚠️  Test file '{test_file}' not found.")
        print("   Please provide a path to a GP patient file to test with.")
        print("   You can:")
        print("   1. Update the 'test_file' variable in this script")
        print("   2. Or place a file named 'test_sample.pdf' in this directory")
        print()
        
        # Try to find any PDF files in current directory
        pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
        if pdf_files:
            print(f"   Found PDF files in current directory: {pdf_files}")
            test_file = pdf_files[0]
            print(f"   Using: {test_file}")
        else:
            print("   No PDF files found. Please add a test file and try again.")
            return
    
    print(f"📄 Processing file: {test_file}\n")
    
    try:
        result = await processor.process_and_save_patient_file(
            file_path=test_file,
            filename=os.path.basename(test_file),
            organization_id=organization_id
        )
        
        if result['success']:
            print("✅ SUCCESS! Document processed and saved\n")
            print(f"   📋 Document ID: {result['document_id']}")
            print(f"   💾 Scanned Doc ID: {result['scanned_doc_id']}")
            print(f"   📊 Parsed Doc ID: {result['parsed_doc_id']}")
            print(f"   ✏️  Validation Session ID: {result['validation_session_id']}")
            print(f"   ⏱️  Processing Time: {result['processing_time']:.2f}s\n")
            
            print("📊 Extracted Data:")
            if result['extractions'].get('demographics'):
                demo = result['extractions']['demographics']
                print(f"   Name: {demo.get('first_names', 'N/A')} {demo.get('surname', 'N/A')}")
                print(f"   ID: {demo.get('id_number', 'N/A')}")
                print(f"   DOB: {demo.get('date_of_birth', 'N/A')}")
            else:
                print("   Demographics: Not extracted")
            
            if result['extractions'].get('chronic_summary'):
                chronic = result['extractions']['chronic_summary']
                conditions = chronic.get('chronic_conditions', [])
                medications = chronic.get('current_medications', [])
                print(f"   Chronic conditions: {len(conditions)} found")
                print(f"   Current medications: {len(medications)} found")
            else:
                print("   Chronic summary: Not extracted")
            
            print("\n🎯 Confidence Scores:")
            for key, score in result['confidence_scores'].items():
                print(f"   {key}: {score:.1%}")
            
            # Verify in database
            print("\n🔍 Verifying in MongoDB...")
            
            scanned = await db_manager.db["gp_scanned_documents"].find_one(
                {"document_id": result['document_id']}
            )
            if scanned:
                print(f"   ✅ Scanned document found: {scanned['filename']} ({scanned['file_size']} bytes)")
            else:
                print("   ❌ Scanned document not found in database")
            
            parsed = await db_manager.db["gp_parsed_documents"].find_one(
                {"document_id": result['document_id']}
            )
            if parsed:
                chunks = parsed.get('parsed_data', {}).get('total_chunks', 0)
                print(f"   ✅ Parsed document found: {chunks} chunks")
            else:
                print("   ❌ Parsed document not found in database")
            
            session = await db_manager.db["gp_validation_sessions"].find_one(
                {"document_id": result['document_id']}
            )
            if session:
                print(f"   ✅ Validation session found: {session['status']}")
            else:
                print("   ❌ Validation session not found in database")
            
            print("\n🎉 All data saved successfully to MongoDB!")
            
            # Show collection counts
            print("\n📊 Collection Statistics:")
            scanned_count = await db_manager.db["gp_scanned_documents"].count_documents({})
            parsed_count = await db_manager.db["gp_parsed_documents"].count_documents({})
            session_count = await db_manager.db["gp_validation_sessions"].count_documents({})
            patients_count = await db_manager.db["gp_patients"].count_documents({})
            
            print(f"   Scanned Documents: {scanned_count}")
            print(f"   Parsed Documents: {parsed_count}")
            print(f"   Validation Sessions: {session_count}")
            print(f"   Validated Patients: {patients_count}")
            
        else:
            print(f"❌ FAILED: {result['error']}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    await db_manager.close()
    print("\n✅ Test complete!")

async def test_save_validated_patient():
    """Test the save validated patient workflow"""
    
    print("\n🧪 Testing Save Validated Patient Flow\n")
    
    # Initialize database
    db_manager = DatabaseManager(
        connection_string=os.getenv("MONGODB_URL"),
        db_name=os.getenv("DATABASE_NAME")
    )
    
    connected = await db_manager.connect()
    if not connected:
        print("❌ Database connection failed!")
        return
    
    # Initialize processor
    processor = GPDocumentProcessor(db_manager=db_manager)
    
    # Sample validated data
    validated_data = {
        'demographics': {
            'id_number': '9001015800081',
            'first_names': 'John',
            'surname': 'Doe',
            'date_of_birth': '1990-01-15',
            'gender': 'Male'
        },
        'chronic_conditions': [
            {'condition': 'Hypertension', 'diagnosed_date': '2020-01-01'},
            {'condition': 'Diabetes Type 2', 'diagnosed_date': '2021-06-15'}
        ],
        'current_medications': [
            {'medication': 'Metformin', 'dosage': '500mg', 'frequency': 'twice daily'},
            {'medication': 'Lisinopril', 'dosage': '10mg', 'frequency': 'once daily'}
        ],
        'vitals': [
            {'date': '2024-10-09', 'systolic_bp': 140, 'diastolic_bp': 90, 'weight': 85}
        ]
    }
    
    try:
        patient_id = await processor.save_validated_patient(
            organization_id="test-gp-practice-001",
            document_id="test-doc-123",
            validated_data=validated_data
        )
        
        print(f"✅ Validated patient saved with ID: {patient_id}")
        
        # Verify in database
        patient = await db_manager.db["gp_patients"].find_one({"patient_id": patient_id})
        if patient:
            print(f"   ✅ Patient record found in database")
            print(f"   Name: {patient['demographics']['first_names']} {patient['demographics']['surname']}")
            print(f"   Conditions: {len(patient['chronic_conditions'])}")
            print(f"   Medications: {len(patient['current_medications'])}")
        else:
            print("   ❌ Patient record not found in database")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    await db_manager.close()

if __name__ == "__main__":
    print("🚀 Starting GP Processing Flow Tests")
    print("=" * 50)
    
    # Test 1: Complete upload and processing flow
    asyncio.run(test_complete_flow())
    
    # Test 2: Save validated patient
    asyncio.run(test_save_validated_patient())
    
    print("\n🎯 Tests completed!")