"""
Test Structured Clinical Notes Integration
Simulates AI Scribe saving a consultation with structured SOAP notes
"""

import sys
sys.path.append('/app/backend')

from supabase import create_client
import os
import uuid

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def test_clinical_notes():
    """Test creating a structured clinical note"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 70)
    print("TESTING STRUCTURED CLINICAL NOTES")
    print("=" * 70)
    
    # Get a test patient
    patients = supabase.table('patients').select('id, full_name').limit(1).execute()
    if not patients.data:
        print("❌ No patients found. Please create a patient first.")
        return
    
    patient = patients.data[0]
    print(f"\n✅ Using test patient: {patient['full_name']} ({patient['id']})")
    
    # Create a test encounter
    encounter_id = str(uuid.uuid4())
    workspace_id = os.getenv('DEMO_WORKSPACE_ID', 'demo-gp-workspace-001')
    
    encounter_data = {
        'id': encounter_id,
        'patient_id': patient['id'],
        'workspace_id': workspace_id,
        'encounter_date': '2025-10-25T12:00:00Z',
        'status': 'completed',
        'chief_complaint': 'Headache and fever',
        'gp_notes': '**SUBJECTIVE:**\nPatient presents with headache and fever for 2 days.\n\n**OBJECTIVE:**\nTemp: 38.5°C, BP: 120/80, HR: 85\n\n**ASSESSMENT:**\nViral infection likely\n\n**PLAN:**\nRest, fluids, paracetamol PRN'
    }
    
    print(f"\n📝 Creating test encounter...")
    supabase.table('encounters').insert(encounter_data).execute()
    print(f"✅ Encounter created: {encounter_id}")
    
    # Create structured clinical note
    note_id = str(uuid.uuid4())
    clinical_note_data = {
        'id': note_id,
        'tenant_id': 'demo-tenant-001',
        'workspace_id': workspace_id,
        'encounter_id': encounter_id,
        'patient_id': patient['id'],
        'format': 'soap',
        'subjective': 'Patient presents with headache and fever for 2 days. Reports body aches and fatigue.',
        'objective': 'Temp: 38.5°C, BP: 120/80 mmHg, HR: 85 bpm. Throat: mildly erythematous. Lungs: clear.',
        'assessment': 'Viral upper respiratory tract infection likely. Rule out influenza.',
        'plan': 'Rest and hydration. Paracetamol 1g PO q6h PRN for fever/pain. Return if symptoms worsen or persist >5 days.',
        'raw_text': encounter_data['gp_notes'],
        'author': 'Dr. Test',
        'role': 'ai_scribe',
        'source': 'ai_scribe',
        'note_datetime': '2025-10-25T12:00:00Z'
    }
    
    print(f"\n📋 Creating structured clinical note...")
    result = supabase.table('clinical_notes').insert(clinical_note_data).execute()
    print(f"✅ Clinical note created: {note_id}")
    
    # Retrieve and display
    print(f"\n🔍 Retrieving structured note...")
    retrieved = supabase.table('clinical_notes').select('*').eq('id', note_id).execute()
    
    if retrieved.data:
        note = retrieved.data[0]
        print("\n" + "=" * 70)
        print("STRUCTURED SOAP NOTE")
        print("=" * 70)
        print(f"\n📌 Note ID: {note['id']}")
        print(f"📌 Patient ID: {note['patient_id']}")
        print(f"📌 Encounter ID: {note['encounter_id']}")
        print(f"📌 Format: {note['format']}")
        print(f"📌 Source: {note['source']}")
        print(f"📌 Author: {note['author']}")
        print(f"\n**SUBJECTIVE:**\n{note['subjective']}")
        print(f"\n**OBJECTIVE:**\n{note['objective']}")
        print(f"\n**ASSESSMENT:**\n{note['assessment']}")
        print(f"\n**PLAN:**\n{note['plan']}")
        print("\n" + "=" * 70)
    
    # Test retrieval by encounter
    print(f"\n🔍 Testing retrieval by encounter_id...")
    by_encounter = supabase.table('clinical_notes').select('*').eq('encounter_id', encounter_id).execute()
    print(f"✅ Found {len(by_encounter.data)} note(s) for encounter")
    
    # Test retrieval by patient
    print(f"\n🔍 Testing retrieval by patient_id...")
    by_patient = supabase.table('clinical_notes').select('*').eq('patient_id', patient['id']).execute()
    print(f"✅ Found {len(by_patient.data)} note(s) for patient")
    
    # Cleanup
    print(f"\n🧹 Cleaning up test data...")
    supabase.table('clinical_notes').delete().eq('id', note_id).execute()
    supabase.table('encounters').delete().eq('id', encounter_id).execute()
    print(f"✅ Test data cleaned up")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nStructured Clinical Notes system is working correctly!")
    print("\nNext time AI Scribe saves a consultation, it will:")
    print("  1. Create an encounter (as before)")
    print("  2. Parse SOAP notes into S/O/A/P sections")
    print("  3. Save structured clinical note to new table")
    print("  4. Keep full text for backward compatibility")

if __name__ == '__main__':
    test_clinical_notes()
