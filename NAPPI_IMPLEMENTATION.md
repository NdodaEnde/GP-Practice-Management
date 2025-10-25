# NAPPI Codes Implementation - Phase 2

## Overview
NAPPI (National Pharmaceutical Product Interface) codes are South Africa's standard medication coding system for pharmaceutical product identification and medical aid claims processing.

## Implementation Status

### ✅ Completed
1. **Database Schema** (`/app/backend/database/nappi_codes_migration.sql`)
   - Table: `nappi_codes`
   - Fields: NAPPI Code, Brand Name, Generic Name, Schedule, Strength, Dosage Form, Ingredients
   - Full-text search indexes for fast lookups
   - Schedule-based filtering support

2. **Backend API** (`/app/backend/api/nappi.py`)
   - GET `/api/nappi/stats` - Database statistics
   - GET `/api/nappi/search` - Search by brand, generic, or ingredient
   - GET `/api/nappi/code/{nappi_code}` - Get specific medication
   - GET `/api/nappi/by-generic/{generic_name}` - Find all brands for generic
   - GET `/api/nappi/by-schedule/{schedule}` - Filter by schedule

3. **CSV Loader** (`/app/backend/load_nappi_codes.py`)
   - Flexible column mapping
   - Batch insertion (1000 records per batch)
   - Duplicate handling
   - Progress reporting

4. **Frontend Test Page** (`/app/frontend/src/pages/NAPPITestPage.jsx`)
   - Real-time search interface
   - Schedule filtering
   - Database statistics display
   - Quick search examples
   - Schedule badge color coding

5. **Sample Data** (`/app/backend/nappi_sample_data.csv`)
   - 20 common South African medications
   - Includes various schedules (S0-S4)
   - Ready for testing

## Setup Instructions

### Step 1: Create Database Table
1. Open Supabase Dashboard: https://supabase.com/dashboard
2. Navigate to: SQL Editor
3. Copy the contents of `/app/backend/database/nappi_codes_migration.sql`
4. Paste and execute in SQL Editor
5. Verify: Table `nappi_codes` should now exist

### Step 2: Verify Table Creation
```bash
cd /app/backend
python init_nappi_table.py
```
Expected output: ✅ nappi_codes table exists!

### Step 3: Load Sample Data (For Testing)
```bash
cd /app/backend
python load_nappi_codes.py nappi_sample_data.csv
```
This loads 20 sample medications for testing.

### Step 4: Load Full NAPPI Database
When you have the full NAPPI data extracted from the PDF:

**Option A: If you have CSV file**
```bash
python load_nappi_codes.py /path/to/nappi-formulary-2025.csv
```

**Option B: If you have Excel file**
First convert to CSV, then:
```bash
python load_nappi_codes.py /path/to/nappi-codes.csv
```

**Expected CSV Format:**
```csv
NAPPI Code,Brand Name,Generic Name,Schedule,Strength/Dosage Form,Ingredients
3001570,Panado Tablets,Paracetamol,S0,500mg Tablet,Paracetamol 500mg
714467,Grandpa Powders,Paracetamol + Aspirin + Caffeine,S1,1g Powder,Paracetamol 320mg + Aspirin 400mg + Caffeine 64mg
...
```

The loader handles variations in column names:
- NAPPI Code → nappi_code, NAPPI, Code
- Brand Name → brand_name, Brand, Trade Name
- Generic Name → generic_name, Generic, Active Ingredient
- Schedule → schedule, Medicine Schedule, Class
- Strength/Dosage Form → Strength, Dosage Form, strength
- Ingredients → ingredients, Active Ingredients, Composition

## Testing

### Backend API Testing
```bash
# Check stats
curl http://localhost:8001/api/nappi/stats

# Search medications
curl "http://localhost:8001/api/nappi/search?query=paracetamol&limit=10"

# Get specific code
curl http://localhost:8001/api/nappi/code/3001570

# Filter by schedule
curl "http://localhost:8001/api/nappi/search?query=antibiotic&schedule=S3"
```

### Frontend Testing
1. Navigate to: http://localhost:3000/nappi-test
2. View database statistics
3. Try quick searches: paracetamol, ibuprofen, amoxicillin
4. Test schedule filtering
5. Verify search results display correctly

## South African Medicine Schedules

| Schedule | Description | Dispensing |
|----------|-------------|------------|
| **S0** | Over-the-Counter (OTC) | Any retail outlet |
| **S1** | Pharmacy Medicine | Pharmacy only, no prescription |
| **S2** | Pharmacy Only Medicine | Pharmacy only, pharmacist supervision |
| **S3** | Prescription Only | Requires prescription |
| **S4** | Prescription (Restricted) | Requires prescription, controlled |
| **S5** | Controlled Substance | Strict prescription controls |
| **S6** | Highly Restricted | Hospital/specialist use only |

## Next Steps

### Phase 2.1: Integration with Prescription Builder
- [ ] Add NAPPI code search to PrescriptionBuilder component
- [ ] Auto-populate medication details from NAPPI code
- [ ] Display schedule warnings
- [ ] Link with allergy checking system

### Phase 2.2: Medical Aid Claims
- [ ] Add NAPPI code to prescription records
- [ ] Include in billing/claims export
- [ ] Validate NAPPI codes before submission

### Phase 2.3: Inventory Management (Future)
- [ ] Link NAPPI codes to stock levels
- [ ] Track medication usage
- [ ] Automatic reorder alerts

## Data Extraction from PDF

### Manual Extraction
If you need to extract data from `nappi-formulary-and-benchmarks-2025.pdf`:

1. **Using Adobe Acrobat:**
   - Open PDF
   - File → Export To → Spreadsheet → Excel
   - Save as CSV

2. **Using Tabula (Free):**
   ```bash
   # Install Tabula
   pip install tabula-py
   
   # Extract tables
   python -c "import tabula; tabula.convert_into('nappi-formulary-2025.pdf', 'nappi-output.csv', output_format='csv', pages='all')"
   ```

3. **Using Online Tools:**
   - https://www.ilovepdf.com/pdf_to_excel
   - https://www.pdftoexcel.com/

After extraction, ensure CSV has these columns:
- NAPPI Code (required)
- Brand Name (required)
- Generic Name (required)
- Schedule
- Strength/Dosage Form
- Ingredients

## Files Created

### Backend
- `/app/backend/database/nappi_codes_migration.sql` - Database schema
- `/app/backend/api/nappi.py` - API endpoints
- `/app/backend/load_nappi_codes.py` - CSV loader script
- `/app/backend/init_nappi_table.py` - Table verification script
- `/app/backend/nappi_sample_data.csv` - Sample data for testing

### Frontend
- `/app/frontend/src/pages/NAPPITestPage.jsx` - Test page component

### Modified Files
- `/app/backend/server.py` - Added NAPPI router
- `/app/frontend/src/App.js` - Added NAPPI test route
- `/app/frontend/src/components/Layout.jsx` - Added navigation link

## API Documentation

### GET /api/nappi/stats
Returns database statistics including total codes and breakdown by schedule.

**Response:**
```json
{
  "total_codes": 20000,
  "active_codes": 19500,
  "by_schedule": {
    "S0": 3500,
    "S1": 2800,
    "S2": 2100,
    "S3": 8500,
    "S4": 2600
  }
}
```

### GET /api/nappi/search
Search medications by brand name, generic name, or ingredients.

**Parameters:**
- `query` (required): Search term (min 2 characters)
- `limit` (optional): Max results (default 20, max 100)
- `schedule` (optional): Filter by schedule (S0-S6)
- `active_only` (optional): Only active medications (default true)

**Example:**
```bash
GET /api/nappi/search?query=paracetamol&schedule=S0&limit=10
```

**Response:**
```json
{
  "results": [
    {
      "nappi_code": "3001570",
      "brand_name": "Panado Tablets",
      "generic_name": "Paracetamol",
      "schedule": "S0",
      "strength": "500mg Tablet",
      "dosage_form": "500mg Tablet",
      "ingredients": "Paracetamol 500mg",
      "status": "active"
    }
  ],
  "count": 1,
  "query": "paracetamol"
}
```

### GET /api/nappi/code/{nappi_code}
Get specific medication by NAPPI code.

**Example:**
```bash
GET /api/nappi/code/3001570
```

## Support

For issues or questions:
1. Check backend logs: `tail -f /var/log/supervisor/backend.err.log`
2. Verify table exists: `python init_nappi_table.py`
3. Test API directly: Use curl commands above
4. Frontend console: Check browser DevTools

## Known Limitations

1. **Database not initialized**: Table must be created manually in Supabase Dashboard
2. **PDF extraction**: Requires manual conversion to CSV format
3. **No auto-pricing**: Pricing is medical-aid specific (as per user requirement)
4. **Basic search**: Full-text search, no fuzzy matching yet

## Future Enhancements

- AI-powered medication suggestions
- Integration with medical aid formularies
- Automatic updates from official NAPPI database
- Barcode scanning for NAPPI codes
- Drug interaction checking
- Prescription verification against NAPPI
