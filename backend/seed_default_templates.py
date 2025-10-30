"""
Seed Default Extraction Templates
Creates pre-configured templates for common medical document types
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

# Demo workspace
DEMO_TENANT_ID = 'demo-tenant-001'
DEMO_WORKSPACE_ID = 'demo-gp-workspace-001'

def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        sys.exit(1)
    
    print("🌱 Seeding default extraction templates...")
    print(f"📍 Workspace: {DEMO_WORKSPACE_ID}")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Check if templates already exist
    existing = supabase.table('extraction_templates')\
        .select('*')\
        .eq('workspace_id', DEMO_WORKSPACE_ID)\
        .execute()
    
    if existing.data:
        print(f"ℹ️  Found {len(existing.data)} existing templates. Skipping seed.")
        print("   Delete existing templates if you want to re-seed.")
        return
    
    templates_created = 0
    mappings_created = 0
    
    # ===========================================
    # TEMPLATE 1: Standard GP Medical Record
    # ===========================================
    
    print("\n📄 Creating: Standard GP Medical Record Template...")
    
    template_1_id = str(uuid.uuid4())
    template_1 = {
        'id': template_1_id,
        'tenant_id': DEMO_TENANT_ID,
        'workspace_id': DEMO_WORKSPACE_ID,
        'template_name': 'Standard GP Medical Record',
        'template_description': 'Standard medical records from GP practices with immunization history, chronic medications, and vital signs',
        'document_type': 'medical_record',
        'is_active': True,
        'is_default': True,  # This is the default template
        'auto_populate': True,
        'require_validation': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('extraction_templates').insert(template_1).execute()
    templates_created += 1
    print(f"   ✅ Template created: {template_1_id}")
    
    # Mappings for Template 1: Immunizations
    immunization_mappings = [
        {
            'id': str(uuid.uuid4()),
            'template_id': template_1_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'immunisation_history',
            'source_field': 'vaccine',
            'target_table': 'immunizations',
            'target_field': 'vaccine_name',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 10,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_1_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'immunisation_history',
            'source_field': 'date',
            'target_table': 'immunizations',
            'target_field': 'administration_date',
            'field_type': 'date',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 11,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_1_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'immunisation_history',
            'source_field': 'dose',
            'target_table': 'immunizations',
            'target_field': 'dose_number',
            'field_type': 'number',
            'transformation_type': 'split',
            'transformation_config': {'delimiter': '/', 'index': 0},
            'is_required': False,
            'processing_order': 12,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
    ]
    
    # Mappings for chronic medications
    medication_mappings = [
        {
            'id': str(uuid.uuid4()),
            'template_id': template_1_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'chronic_medication_list',
            'source_field': 'medication_name',
            'target_table': 'prescriptions',
            'target_field': 'medication_name',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 20,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_1_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'chronic_medication_list',
            'source_field': 'dosage',
            'target_table': 'prescriptions',
            'target_field': 'dosage',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': False,
            'processing_order': 21,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
    ]
    
    all_mappings = immunization_mappings + medication_mappings
    
    if all_mappings:
        supabase.table('extraction_field_mappings').insert(all_mappings).execute()
        mappings_created += len(all_mappings)
        print(f"   ✅ Created {len(all_mappings)} field mappings")
    
    # ===========================================
    # TEMPLATE 2: Lab Report
    # ===========================================
    
    print("\n🧪 Creating: Lab Report Template...")
    
    template_2_id = str(uuid.uuid4())
    template_2 = {
        'id': template_2_id,
        'tenant_id': DEMO_TENANT_ID,
        'workspace_id': DEMO_WORKSPACE_ID,
        'template_name': 'Lab Report',
        'template_description': 'Laboratory test results from PathCare, Lancet, Ampath, etc.',
        'document_type': 'lab_report',
        'is_active': True,
        'is_default': False,
        'auto_populate': True,
        'require_validation': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('extraction_templates').insert(template_2).execute()
    templates_created += 1
    print(f"   ✅ Template created: {template_2_id}")
    
    # Mappings for Lab Results
    lab_mappings = [
        {
            'id': str(uuid.uuid4()),
            'template_id': template_2_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'laboratory_results',
            'source_field': 'test_name',
            'target_table': 'lab_results',
            'target_field': 'test_name',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 10,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_2_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'laboratory_results',
            'source_field': 'result_value',
            'target_table': 'lab_results',
            'target_field': 'result_value',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 11,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_2_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'laboratory_results',
            'source_field': 'units',
            'target_table': 'lab_results',
            'target_field': 'units',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': False,
            'processing_order': 12,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_2_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'laboratory_results',
            'source_field': 'reference_range',
            'target_table': 'lab_results',
            'target_field': 'reference_range',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': False,
            'processing_order': 13,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
    ]
    
    if lab_mappings:
        supabase.table('extraction_field_mappings').insert(lab_mappings).execute()
        mappings_created += len(lab_mappings)
        print(f"   ✅ Created {len(lab_mappings)} field mappings")
    
    # ===========================================
    # TEMPLATE 3: Immunization Card
    # ===========================================
    
    print("\n💉 Creating: Immunization Card Template...")
    
    template_3_id = str(uuid.uuid4())
    template_3 = {
        'id': template_3_id,
        'tenant_id': DEMO_TENANT_ID,
        'workspace_id': DEMO_WORKSPACE_ID,
        'template_name': 'Immunization Card',
        'template_description': 'Vaccination cards and immunization records',
        'document_type': 'immunization_card',
        'is_active': True,
        'is_default': False,
        'auto_populate': True,
        'require_validation': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('extraction_templates').insert(template_3).execute()
    templates_created += 1
    print(f"   ✅ Template created: {template_3_id}")
    
    # Similar mappings to Template 1 but more focused on immunizations
    immunization_card_mappings = [
        {
            'id': str(uuid.uuid4()),
            'template_id': template_3_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'vaccination_records',
            'source_field': 'vaccine_type',
            'target_table': 'immunizations',
            'target_field': 'vaccine_name',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 10,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_3_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'vaccination_records',
            'source_field': 'administered',
            'target_table': 'immunizations',
            'target_field': 'administration_date',
            'field_type': 'date',
            'transformation_type': 'direct',
            'is_required': True,
            'processing_order': 11,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': str(uuid.uuid4()),
            'template_id': template_3_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'source_section': 'vaccination_records',
            'source_field': 'lot_number',
            'target_table': 'immunizations',
            'target_field': 'lot_number',
            'field_type': 'text',
            'transformation_type': 'direct',
            'is_required': False,
            'processing_order': 12,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
    ]
    
    if immunization_card_mappings:
        supabase.table('extraction_field_mappings').insert(immunization_card_mappings).execute()
        mappings_created += len(immunization_card_mappings)
        print(f"   ✅ Created {len(immunization_card_mappings)} field mappings")
    
    # ===========================================
    # SUMMARY
    # ===========================================
    
    print(f"\n✅ Seed complete!")
    print(f"📊 Created {templates_created} templates")
    print(f"📊 Created {mappings_created} field mappings")
    print(f"\n🎯 Templates available:")
    print(f"   1. Standard GP Medical Record (DEFAULT)")
    print(f"   2. Lab Report")
    print(f"   3. Immunization Card")
    print(f"\n💡 These templates are now ready to use with template-driven extraction!")

if __name__ == '__main__':
    main()
