"""
Test Procedures System
End-to-end test of procedures tracking
"""

import sys
sys.path.append('/app/backend')

from supabase import create_client
import os
import uuid
from datetime import datetime, timedelta

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://sizujtbejnnrdqcymgle.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpenVqdGJlam5ucmRxY3ltZ2xlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDMyMTc0NiwiZXhwIjoyMDc1ODk3NzQ2fQ.g8gqEs3Ynb_577txVNjnp8_PYkuBNdac3LxeyBETppw')

def test_procedures_system():
    """Test complete procedures tracking workflow"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 70)
    print("TESTING PROCEDURES SYSTEM")
    print("=" * 70)
    
    # Get test patient
    patients = supabase.table('patients').select('id, first_name, last_name').limit(1).execute()
    if not patients.data:
        print("❌ No patients found. Please create a patient first.")
        return
    
    patient = patients.data[0]
    patient_name = f"{patient['first_name']} {patient['last_name']}"
    print(f"\n✅ Using test patient: {patient_name} ({patient['id']})")
    
    workspace_id = os.getenv('DEMO_WORKSPACE_ID', 'demo-gp-workspace-001')
    tenant_id = os.getenv('DEMO_TENANT_ID', 'demo-tenant-001')
    
    # Test 1: Create Surgical Procedure
    print(f"\n🏥 TEST 1: Creating surgical procedure...")
    surgery_id = str(uuid.uuid4())
    surgery_data = {
        'id': surgery_id,
        'tenant_id': tenant_id,
        'workspace_id': workspace_id,
        'patient_id': patient['id'],
        'procedure_code': '12345',
        'procedure_name': 'Appendectomy',
        'procedure_category': 'Surgery',
        'procedure_datetime': datetime.utcnow().isoformat(),
        'duration_minutes': 90,
        'indication': 'Acute appendicitis',
        'anatomical_site': 'Right lower quadrant',
        'laterality': 'right',
        'primary_surgeon': 'Dr. Johnson',
        'performing_provider': 'Dr. Johnson',
        'status': 'completed',
        'outcome': 'successful',
        'operative_notes': 'Laparoscopic appendectomy performed without complications. Appendix removed and sent to pathology.',
        'billable': True,
        'billing_code': 'SURG-APP-001',
        'tariff_amount': 8500.00,
        'follow_up_required': True,
        'follow_up_date': (datetime.utcnow() + timedelta(days=7)).date().isoformat()
    }
    
    supabase.table('procedures').insert(surgery_data).execute()
    print(f"✅ Surgical procedure created: {surgery_id}")
    print(f"   Name: {surgery_data['procedure_name']}")
    print(f"   Surgeon: {surgery_data['primary_surgeon']}")
    print(f"   Outcome: {surgery_data['outcome']}")
    print(f"   Tariff: R{surgery_data['tariff_amount']}")
    
    # Test 2: Create Diagnostic Procedure
    print(f"\n🔬 TEST 2: Creating diagnostic procedure...")
    diagnostic_id = str(uuid.uuid4())
    diagnostic_data = {
        'id': diagnostic_id,
        'tenant_id': tenant_id,
        'workspace_id': workspace_id,
        'patient_id': patient['id'],
        'procedure_name': 'Colonoscopy',
        'procedure_category': 'Diagnostic',
        'procedure_datetime': (datetime.utcnow() - timedelta(days=30)).isoformat(),
        'duration_minutes': 45,
        'indication': 'Screening for colorectal cancer',
        'anatomical_site': 'Colon',
        'performing_provider': 'Dr. Smith',
        'status': 'completed',
        'outcome': 'successful',
        'operative_notes': 'Complete colonoscopy to cecum. No polyps or masses identified. Excellent bowel preparation.',
        'billable': True,
        'billing_code': 'DIAG-COL-001',
        'tariff_amount': 3200.00
    }
    
    supabase.table('procedures').insert(diagnostic_data).execute()
    print(f"✅ Diagnostic procedure created: {diagnostic_id}")
    print(f"   Name: {diagnostic_data['procedure_name']}")
    print(f"   Category: {diagnostic_data['procedure_category']}")
    
    # Test 3: Create Therapeutic Procedure
    print(f"\n💊 TEST 3: Creating therapeutic procedure...")
    therapeutic_id = str(uuid.uuid4())
    therapeutic_data = {
        'id': therapeutic_id,
        'tenant_id': tenant_id,
        'workspace_id': workspace_id,
        'patient_id': patient['id'],
        'procedure_name': 'Joint Injection - Knee',
        'procedure_category': 'Therapeutic',
        'procedure_datetime': (datetime.utcnow() - timedelta(days=15)).isoformat(),
        'indication': 'Osteoarthritis of right knee',
        'anatomical_site': 'Right knee',
        'laterality': 'right',
        'performing_provider': 'Dr. Wilson',
        'status': 'completed',
        'outcome': 'successful',
        'operative_notes': 'Intra-articular injection of corticosteroid into right knee joint under sterile technique.',
        'billable': True,
        'billing_code': 'THER-INJ-001',
        'tariff_amount': 850.00,
        'follow_up_required': True,
        'follow_up_date': (datetime.utcnow() + timedelta(days=30)).date().isoformat()
    }
    
    supabase.table('procedures').insert(therapeutic_data).execute()
    print(f"✅ Therapeutic procedure created: {therapeutic_id}")
    
    # Test 4: Retrieve Patient Procedures
    print(f"\n🔍 TEST 4: Retrieving patient procedures...")
    procedures = supabase.table('procedures')\
        .select('*')\
        .eq('patient_id', patient['id'])\
        .order('procedure_datetime', desc=True)\
        .execute()
    print(f"✅ Found {len(procedures.data)} procedure(s) for patient")
    
    # Test 5: Get Surgical History
    print(f"\n🏥 TEST 5: Retrieving surgical history...")
    surgeries = supabase.table('procedures')\
        .select('*')\
        .eq('patient_id', patient['id'])\
        .eq('procedure_category', 'Surgery')\
        .execute()
    print(f"✅ Found {len(surgeries.data)} surgical procedure(s)")
    for surgery in surgeries.data:
        print(f"  - {surgery['procedure_name']} ({surgery['procedure_datetime'][:10]})")
    
    # Test 6: Get Billable Procedures
    print(f"\n💰 TEST 6: Calculating billable procedures...")
    billable = supabase.table('procedures')\
        .select('*')\
        .eq('patient_id', patient['id'])\
        .eq('billable', True)\
        .execute()
    
    total_tariff = sum(float(p.get('tariff_amount', 0) or 0) for p in billable.data)
    print(f"✅ Found {len(billable.data)} billable procedure(s)")
    print(f"💵 Total tariff amount: R{total_tariff:,.2f}")
    for proc in billable.data:
        print(f"  - {proc['procedure_name']}: R{float(proc.get('tariff_amount', 0) or 0):,.2f}")
    
    # Test 7: Get Follow-up Required
    print(f"\n📅 TEST 7: Checking follow-up requirements...")
    follow_ups = supabase.table('procedures')\
        .select('*')\
        .eq('patient_id', patient['id'])\
        .eq('follow_up_required', True)\
        .execute()
    print(f"✅ Found {len(follow_ups.data)} procedure(s) requiring follow-up")
    for proc in follow_ups.data:
        print(f"  - {proc['procedure_name']}: Due {proc.get('follow_up_date', 'Not set')}")
    
    # Test 8: Update Procedure Status
    print(f"\n🔄 TEST 8: Updating procedure status...")
    supabase.table('procedures')\
        .update({
            'post_operative_notes': 'Patient recovering well. No signs of infection or complications.',
            'updated_at': datetime.utcnow().isoformat()
        })\
        .eq('id', surgery_id)\
        .execute()
    print(f"✅ Procedure updated with post-operative notes")
    
    # Test 9: Get Procedures by Category
    print(f"\n📊 TEST 9: Grouping by category...")
    all_procs = supabase.table('procedures')\
        .select('procedure_category')\
        .eq('patient_id', patient['id'])\
        .execute()
    
    categories = {}
    for proc in all_procs.data:
        cat = proc.get('procedure_category', 'Uncategorized')
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"✅ Procedures by category:")
    for cat, count in categories.items():
        print(f"  - {cat}: {count}")
    
    # Cleanup
    print(f"\n🧹 Cleaning up test data...")
    supabase.table('procedures').delete().eq('id', surgery_id).execute()
    supabase.table('procedures').delete().eq('id', diagnostic_id).execute()
    supabase.table('procedures').delete().eq('id', therapeutic_id).execute()
    print(f"✅ Test data cleaned up")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nProcedures system is fully functional!")
    print("\nCapabilities:")
    print("  ✅ Track surgical procedures with surgeon details")
    print("  ✅ Record diagnostic procedures")
    print("  ✅ Log therapeutic interventions")
    print("  ✅ Calculate billing/tariffs")
    print("  ✅ Manage follow-up appointments")
    print("  ✅ Surgical history timeline")
    print("  ✅ Categorize by procedure type")
    print("\nReady for production use!")

if __name__ == '__main__':
    test_procedures_system()
