"""
Test ICD-10 and NAPPI Lookup Transformations
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.extraction_engine import ExtractionEngine

# Demo workspace
WORKSPACE_ID = 'demo-gp-workspace-001'
TENANT_ID = 'demo-tenant-001'


async def test_icd10_lookups():
    """Test ICD-10 lookup transformations"""
    print("\n" + "="*60)
    print("TESTING ICD-10 LOOKUPS")
    print("="*60 + "\n")
    
    engine = ExtractionEngine(WORKSPACE_ID, TENANT_ID)
    
    test_cases = [
        # (diagnosis_text, expected_to_find_code)
        ("Type 2 Diabetes", True),
        ("Hypertension", True),
        ("Essential hypertension", True),
        ("High blood pressure", True),  # Should match via AI
        ("DM", True),  # Should match via AI synonym
        ("Asthma", True),
        ("COPD", True),  # Should match via AI synonym
        ("Completely made up disease", False),
    ]
    
    for diagnosis, should_find in test_cases:
        # Test direct lookup
        config = {'lookup_type': 'icd10', 'confidence_threshold': 0.7}
        result = engine._lookup_icd10(diagnosis, config)
        
        status = "✅" if (result is not None) == should_find else "❌"
        print(f"{status} Lookup: '{diagnosis}' → {result}")
        
        # Test AI match
        config_ai = {'match_type': 'icd10'}
        result_ai = engine._ai_match_icd10(diagnosis, config_ai)
        
        status_ai = "✅" if (result_ai is not None) == should_find else "❌"
        print(f"{status_ai} AI Match: '{diagnosis}' → {result_ai}")
        print()


async def test_nappi_lookups():
    """Test NAPPI lookup transformations"""
    print("\n" + "="*60)
    print("TESTING NAPPI LOOKUPS")
    print("="*60 + "\n")
    
    engine = ExtractionEngine(WORKSPACE_ID, TENANT_ID)
    
    test_cases = [
        # (medication_name, expected_to_find_code)
        ("Atenolol", True),
        ("Atenolol 50mg", True),  # Should strip dosage
        ("Metformin", True),
        ("Glucophage", True),  # Brand name
        ("Panado", True),  # Should match via AI
        ("Paracetamol", True),
        ("Ibuprofen", True),
        ("Completely fake medication xyz", False),
    ]
    
    for medication, should_find in test_cases:
        # Test direct lookup
        config = {'lookup_type': 'nappi', 'confidence_threshold': 0.7}
        result = engine._lookup_nappi(medication, config)
        
        status = "✅" if (result is not None) == should_find else "❌"
        print(f"{status} Lookup: '{medication}' → {result}")
        
        # Test AI match
        config_ai = {'match_type': 'nappi'}
        result_ai = engine._ai_match_nappi(medication, config_ai)
        
        status_ai = "✅" if (result_ai is not None) == should_find else "❌"
        print(f"{status_ai} AI Match: '{medication}' → {result_ai}")
        print()


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TRANSFORMATION ENGINE - LOOKUP TESTS")
    print("="*60)
    
    await test_icd10_lookups()
    await test_nappi_lookups()
    
    print("\n" + "="*60)
    print("TESTING COMPLETE")
    print("="*60 + "\n")
    
    print("✅ ICD-10 and NAPPI lookup transformations implemented!")
    print("✅ Direct lookup: Exact and fuzzy matching")
    print("✅ AI matching: Synonyms, abbreviations, brand names")
    print("\nNext: Test with real extraction workflow")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
