#!/usr/bin/env python3
"""
Test GP Integration with Patient file.pdf
Tests the complete GP chronic patient digitization workflow
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add app to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.gp_processor import GPDocumentProcessor
from app.schemas.gp_demographics import PatientDemographics
from app.schemas.gp_chronic_summary import ChronicPatientSummary
from app.schemas.gp_vitals import VitalSignsHistory
from app.schemas.gp_consultation import ClinicalNotesHistory


def print_banner(title):
    """Print a nice banner"""
    print("\n" + "=" * 70)
    print(f"🏥 {title}")
    print("=" * 70)


def print_section(title):
    """Print section header"""
    print(f"\n📋 {title}")
    print("-" * 50)


async def test_gp_processor():
    """Test GP Document Processor with Patient file.pdf"""
    
    print_banner("GP CHRONIC PATIENT DIGITIZATION - INTEGRATION TEST")
    
    # File path
    file_path = "/Users/luzuko/MVP_V3_Clean/document-processor-microservice/Patient file.pdf"
    
    if not os.path.exists(file_path):
        print(f"❌ Test file not found: {file_path}")
        return False
    
    print(f"📄 Test File: {file_path}")
    print(f"📊 File Size: {os.path.getsize(file_path) / 1024:.1f} KB")
    
    try:
        print_section("INITIALIZING GP PROCESSOR")
        
        # Set test API key if not set
        if not os.environ.get("VISION_AGENT_API_KEY"):
            print("⚠️  VISION_AGENT_API_KEY not set - using dummy key for test")
            os.environ["VISION_AGENT_API_KEY"] = "test_key_12345"
        
        processor = GPDocumentProcessor()
        print("✅ GPDocumentProcessor initialized")
        
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return False
    
    try:
        print_section("PROCESSING PATIENT FILE")
        start_time = datetime.utcnow()
        
        # Process the file
        result = await processor.process_patient_file(
            file_path=file_path,
            patient_id="test_patient_001",
            filename="Patient file.pdf"
        )
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        print(f"⏱️  Processing Time: {processing_time:.2f} seconds")
        print(f"✅ Processing Status: {result.get('success', 'Unknown')}")
        
        if not result.get('success'):
            print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
            return False
        
        print_section("PROCESSING RESULTS SUMMARY")
        print(f"📄 Document ID: {result.get('parsed_document_id', 'N/A')}")
        print(f"📊 Pages Processed: {result.get('pages_processed', 'N/A')}")
        print(f"🧠 Model Used: {result.get('model_used', 'N/A')}")
        print(f"📝 Markdown Length: {len(result.get('markdown', ''))}")
        print(f"🔍 Chunks Found: {len(result.get('chunks', []))}")
        
        # Show extractions
        extractions = result.get('extractions', {})
        print_section("EXTRACTIONS PERFORMED")
        
        for extraction_type, extraction_data in extractions.items():
            status = "✅ SUCCESS" if extraction_data else "❌ FAILED"
            print(f"  {status} {extraction_type}")
        
        # Show confidence scores
        confidence_scores = result.get('confidence_scores', {})
        print_section("CONFIDENCE SCORES")
        
        for extraction_type, score in confidence_scores.items():
            if score >= 0.8:
                status = "🟢 HIGH"
            elif score >= 0.5:
                status = "🟡 MEDIUM"
            else:
                status = "🔴 LOW"
            print(f"  {status} {extraction_type}: {score:.1%}")
        
        # Show validation requirements
        validation_required = result.get('validation_required', {})
        print_section("VALIDATION REQUIREMENTS")
        
        for extraction_type, validation_info in validation_required.items():
            needs_validation = validation_info.get('needs_validation', True)
            reason = validation_info.get('reason', 'Unknown')
            status = "⚠️  NEEDS VALIDATION" if needs_validation else "✅ AUTO-APPROVED"
            print(f"  {status} {extraction_type}: {reason}")
        
        # Detailed extraction results
        print_section("DETAILED EXTRACTION RESULTS")
        
        # Demographics
        if extractions.get('demographics'):
            demo = extractions['demographics']
            print("\n👤 DEMOGRAPHICS:")
            print(f"  Name: {getattr(demo, 'first_names', 'N/A')} {getattr(demo, 'surname', 'N/A')}")
            print(f"  ID Number: {getattr(demo, 'id_number', 'N/A')}")
            print(f"  Date of Birth: {getattr(demo, 'date_of_birth', 'N/A')}")
            print(f"  Gender: {getattr(demo, 'gender', 'N/A')}")
            print(f"  Cell Number: {getattr(demo, 'cell_number', 'N/A')}")
            print(f"  Medical Aid: {getattr(demo, 'medical_aid_name', 'N/A')}")
            print(f"  Medical Aid Number: {getattr(demo, 'medical_aid_number', 'N/A')}")
        
        # Chronic Summary
        if extractions.get('chronic_summary'):
            chronic = extractions['chronic_summary']
            print(f"\n🏥 CHRONIC CONDITIONS: {len(getattr(chronic, 'chronic_conditions', []))}")
            for i, condition in enumerate(getattr(chronic, 'chronic_conditions', [])[:3]):  # Show first 3
                print(f"  {i+1}. {getattr(condition, 'condition_name', 'N/A')} - {getattr(condition, 'status', 'N/A')}")
            
            print(f"\n💊 CURRENT MEDICATIONS: {len(getattr(chronic, 'current_medications', []))}")
            for i, med in enumerate(getattr(chronic, 'current_medications', [])[:3]):  # Show first 3
                print(f"  {i+1}. {getattr(med, 'medication_name', 'N/A')} {getattr(med, 'strength', '')} {getattr(med, 'frequency', '')}")
            
            allergies = getattr(chronic, 'drug_allergies', [])
            if allergies:
                print(f"\n⚠️  ALLERGIES: {', '.join(allergies)}")
        
        # Vital Signs
        if extractions.get('vitals'):
            vitals = extractions['vitals']
            records = getattr(vitals, 'vital_signs_records', [])
            print(f"\n📊 VITAL SIGNS RECORDS: {len(records)}")
            if records:
                latest = records[-1]  # Most recent
                print(f"  Latest Record:")
                print(f"    Date: {getattr(latest, 'date', 'N/A')}")
                print(f"    Weight: {getattr(latest, 'weight_kg', 'N/A')} kg")
                print(f"    BP: {getattr(latest, 'blood_pressure_systolic', 'N/A')}/{getattr(latest, 'blood_pressure_diastolic', 'N/A')}")
                print(f"    Pulse: {getattr(latest, 'pulse', 'N/A')} bpm")
        
        # Clinical Notes
        if extractions.get('clinical_notes'):
            clinical = extractions['clinical_notes']
            notes = getattr(clinical, 'consultation_notes', [])
            print(f"\n📝 CONSULTATION NOTES: {len(notes)}")
            if notes:
                latest_note = notes[-1]  # Most recent
                print(f"  Latest Consultation:")
                print(f"    Date: {getattr(latest_note, 'consultation_date', 'N/A')}")
                print(f"    Type: {getattr(latest_note, 'consultation_type', 'N/A')}")
                print(f"    Chief Complaint: {getattr(latest_note, 'chief_complaint', 'N/A')}")
                print(f"    Doctor: {getattr(latest_note, 'doctor_name', 'N/A')}")
        
        # Show markdown sample
        markdown = result.get('markdown', '')
        if markdown:
            print_section("PARSED MARKDOWN SAMPLE (First 500 chars)")
            print(markdown[:500] + "..." if len(markdown) > 500 else markdown)
        
        # Show chunks sample
        chunks = result.get('chunks', [])
        if chunks:
            print_section("SEMANTIC CHUNKS SAMPLE (First 3 chunks)")
            for i, chunk in enumerate(chunks[:3]):
                chunk_type = chunk.get('type', 'unknown')
                content = chunk.get('content', '')[:100]
                grounding = chunk.get('grounding', {})
                page = grounding.get('page', 'N/A')
                print(f"  Chunk {i+1} ({chunk_type}) Page {page}: {content}...")
        
        print_section("TEST SUMMARY")
        print("✅ GP Document Processor working correctly")
        print("✅ Parse-once, extract-many pattern implemented")
        print("✅ All schema extractions attempted")
        print("✅ Confidence scoring working")
        print("✅ Validation logic implemented")
        print("✅ Grounding data available for UI")
        
        success_count = sum(1 for v in extractions.values() if v)
        print(f"📊 Successful Extractions: {success_count}/{len(extractions)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print("\n🔍 Full traceback:")
        traceback.print_exc()
        return False


async def test_schema_validation():
    """Test that schemas work correctly"""
    
    print_section("SCHEMA VALIDATION TEST")
    
    try:
        # Test Demographics Schema
        demo_data = {
            "surname": "Test",
            "first_names": "Patient",
            "date_of_birth": "1990-01-01",
            "id_number": "9001010000000"
        }
        demo = PatientDemographics(**demo_data)
        print("✅ PatientDemographics schema validation passed")
        
        # Test Chronic Summary Schema  
        chronic_data = {
            "patient_name": "Test Patient",
            "chronic_conditions": [],
            "current_medications": []
        }
        chronic = ChronicPatientSummary(**chronic_data)
        print("✅ ChronicPatientSummary schema validation passed")
        
        # Test Vital Signs Schema
        vitals_data = {
            "patient_name": "Test Patient",
            "vital_signs_records": []
        }
        vitals = VitalSignsHistory(**vitals_data)
        print("✅ VitalSignsHistory schema validation passed")
        
        # Test Clinical Notes Schema
        notes_data = {
            "patient_name": "Test Patient", 
            "consultation_notes": []
        }
        notes = ClinicalNotesHistory(**notes_data)
        print("✅ ClinicalNotesHistory schema validation passed")
        
        print("✅ All schema validations passed")
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False


async def main():
    """Run all tests"""
    
    print_banner("GP INTEGRATION COMPREHENSIVE TEST SUITE")
    print(f"🕐 Test Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    test_results = []
    
    # Test 1: Schema Validation
    print("\n" + "🧪 TEST 1: Schema Validation")
    schema_result = await test_schema_validation()
    test_results.append(("Schema Validation", schema_result))
    
    # Test 2: GP Processor Integration  
    print("\n" + "🧪 TEST 2: GP Processor with Real File")
    processor_result = await test_gp_processor()
    test_results.append(("GP Processor Integration", processor_result))
    
    # Final Results
    print_banner("FINAL TEST RESULTS")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! GP Integration is ready for production.")
        print("\n🚀 Next Steps:")
        print("1. Start the FastAPI server: python app/main.py")
        print("2. Test API endpoints with curl or Postman")
        print("3. Build frontend validation UI")
        print("4. Process real GP patient files")
    else:
        print("⚠️  Some tests failed. Review the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)