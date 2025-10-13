from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema
from app.schemas.gp_demographics import PatientDemographics
import os
import json
from io import BytesIO

# Initialize client
client = LandingAIADE(apikey=os.environ.get("VISION_AGENT_API_KEY"))

# Simple test markdown
test_markdown = """
1 PATIENT DETAILS

Surname: MOTSOENENG
First Names: MAMELLO
Date of Birth: 1991.02.03
I.D. Number: 9102030347687
Cell: 071 4519723
Email: Mamellomotsoeneng6@gmail.com

Medical Aid: TANZANITE Gems
Number: 01384786
"""

print("Testing extraction...")
print("=" * 60)

try:
    # Test schema generation
    print("\n1. Testing schema generation...")
    schema = pydantic_to_json_schema(PatientDemographics)
    print("✅ Schema generated successfully")
    
    # Convert string to bytes (file-like)
    print("\n2. Converting markdown to file-like object...")
    markdown_bytes = BytesIO(test_markdown.encode('utf-8'))
    print("✅ Converted to bytes")
    
    # Test extraction
    print("\n3. Testing extraction...")
    result = client.extract(schema=schema, markdown=markdown_bytes)
    
    print("✅ Extraction successful!")
    print("\nExtracted data:")
    print(json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2))
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    print("\nFull traceback:")
    print(traceback.format_exc())