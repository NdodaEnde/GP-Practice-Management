#!/usr/bin/env python3
"""
Simple GP Integration Test
Tests schemas and basic functionality without complex imports
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_schema_imports():
    """Test that all GP schemas can be imported"""
    print("🧪 Testing GP Schema Imports...")
    
    try:
        from app.schemas.gp_demographics import PatientDemographics
        print("✅ PatientDemographics imported successfully")
        
        from app.schemas.gp_chronic_summary import ChronicPatientSummary, ChronicCondition, CurrentMedication
        print("✅ ChronicPatientSummary imported successfully")
        
        from app.schemas.gp_vitals import VitalSignsHistory, VitalSignsRecord
        print("✅ VitalSignsHistory imported successfully")
        
        from app.schemas.gp_consultation import ClinicalNotesHistory, ConsultationNote
        print("✅ ClinicalNotesHistory imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Schema import failed: {e}")
        return False


def test_schema_creation():
    """Test creating schema instances with sample data"""
    print("\n🧪 Testing Schema Creation...")
    
    try:
        from app.schemas.gp_demographics import PatientDemographics
        from app.schemas.gp_chronic_summary import ChronicPatientSummary, ChronicCondition, CurrentMedication
        from app.schemas.gp_vitals import VitalSignsHistory, VitalSignsRecord
        from app.schemas.gp_consultation import ClinicalNotesHistory, ConsultationNote
        
        # Test Demographics
        demo = PatientDemographics(
            surname="Maleshoane",
            first_names="Mamello",
            date_of_birth="1991-02-03",
            id_number="9102030847087",
            gender="Female",
            cell_number="071 45 19 723",
            medical_aid_name="BONITAS GEMS",
            medical_aid_number="30128497186"
        )
        print("✅ PatientDemographics instance created")
        print(f"   Patient: {demo.first_names} {demo.surname}")
        print(f"   ID: {demo.id_number}")
        print(f"   Medical Aid: {demo.medical_aid_name}")
        
        # Test Chronic Condition
        condition = ChronicCondition(
            condition_name="Type 2 Diabetes",
            icd10_code="E11",
            diagnosed_date="2018",
            status="Controlled"
        )
        
        # Test Medication
        medication = CurrentMedication(
            medication_name="Metformin",
            strength="500mg",
            frequency="BD",
            indication="Type 2 Diabetes"
        )
        
        # Test Chronic Summary
        chronic = ChronicPatientSummary(
            patient_name="Mamello Maleshoane",
            chronic_conditions=[condition],
            current_medications=[medication],
            drug_allergies=["Penicillin - rash"]
        )
        print("✅ ChronicPatientSummary instance created")
        print(f"   Conditions: {len(chronic.chronic_conditions)}")
        print(f"   Medications: {len(chronic.current_medications)}")
        print(f"   Allergies: {len(chronic.drug_allergies)}")
        
        # Test Vital Signs
        vital_record = VitalSignsRecord(
            date="2024-01-15",
            weight_kg=96.1,
            blood_pressure_systolic=138,
            blood_pressure_diastolic=83,
            pulse=94
        )
        
        vitals = VitalSignsHistory(
            patient_name="Mamello Maleshoane",
            vital_signs_records=[vital_record],
            latest_weight=96.1,
            latest_bp="138/83"
        )
        print("✅ VitalSignsHistory instance created")
        print(f"   Records: {len(vitals.vital_signs_records)}")
        print(f"   Latest BP: {vitals.latest_bp}")
        print(f"   Latest Weight: {vitals.latest_weight}kg")
        
        # Test Consultation Note
        consultation = ConsultationNote(
            consultation_date="2024-01-15",
            consultation_type="Follow-up",
            chief_complaint="Diabetes follow-up",
            subjective="Patient reports feeling well",
            objective="BP: 138/83, Weight: 96.1kg",
            assessment="Type 2 Diabetes - well controlled",
            plan="Continue Metformin 500mg BD",
            doctor_name="Dr. Mokeki"
        )
        
        clinical_notes = ClinicalNotesHistory(
            patient_name="Mamello Maleshoane",
            consultation_notes=[consultation],
            total_consultations=1,
            date_range="2024-01-15 to 2024-01-15"
        )
        print("✅ ClinicalNotesHistory instance created")
        print(f"   Consultations: {len(clinical_notes.consultation_notes)}")
        print(f"   Latest Visit: {clinical_notes.consultation_notes[0].consultation_date}")
        print(f"   Doctor: {clinical_notes.consultation_notes[0].doctor_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints_import():
    """Test that GP endpoints can be imported"""
    print("\n🧪 Testing GP API Endpoints Import...")
    
    try:
        from app.api.gp_endpoints import gp_router
        print("✅ GP router imported successfully")
        print(f"   Prefix: {gp_router.prefix}")
        print(f"   Tags: {gp_router.tags}")
        
        # Count routes
        route_count = len(gp_router.routes)
        print(f"   Routes: {route_count} endpoints")
        
        # List some routes
        for route in gp_router.routes[:5]:  # First 5 routes
            methods = getattr(route, 'methods', ['UNKNOWN'])
            path = getattr(route, 'path', 'unknown')
            print(f"     {list(methods)[0]} {path}")
        
        return True
        
    except ImportError as e:
        print(f"❌ GP endpoints import failed: {e}")
        return False


def test_processor_import():
    """Test that GP processor can be imported"""
    print("\n🧪 Testing GP Processor Import...")
    
    try:
        from app.services.gp_processor import GPDocumentProcessor
        print("✅ GPDocumentProcessor imported successfully")
        
        # Try to create instance (will fail without API key, but import should work)
        try:
            os.environ["VISION_AGENT_API_KEY"] = "test_key"
            processor = GPDocumentProcessor()
            print("✅ GPDocumentProcessor instance created (with test key)")
        except Exception as e:
            print(f"⚠️  GPDocumentProcessor instance creation failed (expected): {e}")
            print("   This is expected without a real LandingAI API key")
        
        return True
        
    except ImportError as e:
        print(f"❌ GP processor import failed: {e}")
        return False


def check_patient_file():
    """Check if patient file exists and get info"""
    print("\n🧪 Checking Patient File...")
    
    file_path = "Patient file.pdf"
    
    if os.path.exists(file_path):
        size_kb = os.path.getsize(file_path) / 1024
        print(f"✅ Patient file found: {file_path}")
        print(f"   Size: {size_kb:.1f} KB")
        
        # Check if it's readable
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header == b'%PDF':
                    print("✅ File is a valid PDF")
                else:
                    print("⚠️  File may not be a valid PDF")
        except Exception as e:
            print(f"⚠️  Could not read file: {e}")
            
        return True
    else:
        print(f"❌ Patient file not found: {file_path}")
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("🏥 GP INTEGRATION - SIMPLE TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("Schema Imports", test_schema_imports),
        ("Schema Creation", test_schema_creation), 
        ("API Endpoints Import", test_api_endpoints_import),
        ("GP Processor Import", test_processor_import),
        ("Patient File Check", check_patient_file)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
    
    print("\n" + "=" * 70)
    print("📊 FINAL RESULTS")
    print("=" * 70)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ GP Integration Status:")
        print("  - All schemas working correctly")
        print("  - API endpoints properly defined")
        print("  - GP processor can be imported")
        print("  - Patient file is available for testing")
        print("\n🚀 Next Steps:")
        print("  1. Set VISION_AGENT_API_KEY environment variable")
        print("  2. Start FastAPI server: python app/main.py")
        print("  3. Test API endpoints with curl or Postman")
        print("  4. Process the Patient file.pdf with GP endpoints")
    else:
        print(f"\n⚠️  {total-passed} tests failed. Review errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)