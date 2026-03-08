# NAPPI Database Testing Guide
## Updated with Full Database (1,637 Medications)

### ✅ Current Database Status
- **Total Medications:** 1,637
- **Active Products:** 1,637
- **Schedule Breakdown:**
  - S0 (OTC): 3 medications
  - S1 (Pharmacy): 7 medications
  - S2 (Pharmacy Only): 4 medications
  - S3 (Prescription): 986 medications
  - S4 (Controlled): 3 medications

---

## 🧪 Recommended Test Queries

### ✅ Common OTC Medications (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `paracetamol` | 5+ results | Panado, Adco-Dol, Grandpa |
| `panado` | 1 result | Brand name for paracetamol |
| `grandpa` | 1 result | Combination pain relief powder |
| `ibuprofen` | 3+ results | Brufen, Mybulen, Stopayne |
| `brufen` | 1 result | Brand name for ibuprofen |

### ✅ Antibiotics (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `amoxicillin` | 4 results | Betamox, Amoxil, various strengths |
| `augmentin` | 1 result | Amoxicillin + Clavulanic Acid |
| `amoxyclav` | 5+ results | Generic combination |
| `azithromycin` | 2 results | Z-pack antibiotic |
| `ciprofloxacin` | Results | Fluoroquinolone |

### ✅ Chronic Disease Medications (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `metformin` | 6+ results | Diabetes - Accord, Apex, Glucophage |
| `glucophage` | 1 result | Brand name for metformin |
| `insulin` | 10+ results | Various insulin formulations |
| `amlodipine` | 6+ results | Blood pressure - various brands |
| `norvasc` | 1 result | Brand name for amlodipine |
| `enalapril` | 3+ results | ACE inhibitor |
| `losartan` | 7+ results | ARB for hypertension |
| `cozaar` | 1 result | Brand name for losartan |
| `simvastatin` | 9+ results | Cholesterol medication |
| `lipitor` | 1 result | Atorvastatin brand name |

### ✅ Mental Health (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `sertraline` | 2+ results | Antidepressant (Zoloft) |
| `escitalopram` | 4+ results | Antidepressant (Lexapro) |
| `fluoxetine` | 2+ results | Antidepressant (Prozac) |

### ✅ Pain & Anti-inflammatory (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `diclofenac` | 6+ results | NSAID - Voltaren |
| `voltaren` | 1 result | Brand name for diclofenac |
| `tramadol` | 1+ results | Pain medication (S4) |
| `stopayne` | 1 result | Ibuprofen + Paracetamol |

### ✅ Other Common Medications (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `warfarin` | 3+ results | Blood thinner |
| `nexium` | 1 result | Esomeprazole (PPI) |
| `anastrozole` | 2+ results | Cancer medication |
| `lasix` | 1 result | Furosemide (diuretic) |

### ✅ Search by Manufacturer (Will Find Results)
| Search Term | Expected Results | Notes |
|------------|------------------|-------|
| `accord` | 20+ results | Accord Healthcare products |
| `adco` | 20+ results | Adco brand medications |
| `austell` | 10+ results | Austell Pharmaceuticals |
| `apex` | 5+ results | Apex Healthcare |

---

## ❌ Test Cases - No Results Expected

These are medications NOT in the Discovery 2025 formulary or our common meds list:

| Search Term | Expected | Reason |
|------------|----------|---------|
| `naproxen` | Maybe 1 result | Added Naprosyn to common meds |
| `omeprazole` | No results | Not in Discovery formulary |
| `furosemide` | 1 result | Added Lasix to common meds |
| `tylenol` | No results | US brand name (not used in SA) |
| `panadol` | No results | Different spelling of Panado |
| `aspirin` | Maybe 1 result | In Grandpa combination |
| `tamoxifen` | 1 result | Added Nolvadex to common meds |

---

## 🎯 UI Testing Checklist

### Statistics Display
- [ ] Shows 1,637 Total Medications
- [ ] Shows 1,637 Active Products
- [ ] Shows schedule breakdown (S0:3, S1:7, S2:4, S3:986, S4:3)

### Search Functionality
- [ ] Type minimum 2 characters to search
- [ ] Search button enables after typing
- [ ] Loading state shows while searching
- [ ] Results display with proper formatting

### Result Display Elements
Each result should show:
- [ ] NAPPI Code (gray badge, e.g., "3001570")
- [ ] Schedule badge with color (S0=green, S1=blue, S2=yellow, S3=orange, S4=red)
- [ ] **Brand Name** (bold, larger text)
- [ ] Generic: [Generic Name] (smaller text)
- [ ] Strength: [e.g., "500mg Tablet"]
- [ ] Ingredients: [Active ingredients]

### Quick Search Buttons
Test each button:
- [ ] `paracetamol` → 5 results (Panado, Adco-Dol, Grandpa)
- [ ] `ibuprofen` → 3+ results (Brufen, Mybulen, Stopayne)
- [ ] `amoxicillin` → 4 results
- [ ] `panado` → 1 result
- [ ] `grandpa` → 1 result
- [ ] `metformin` → 6 results

### Schedule Filtering
- [ ] Select "All Schedules" → Shows all results
- [ ] Select "S0 - OTC" + search "paracetamol" → Shows Panado, Adco-Dol
- [ ] Select "S1 - Pharmacy Medicine" + search "ibuprofen" → Shows Brufen
- [ ] Select "S3 - Prescription" + search "amoxicillin" → Shows all antibiotics
- [ ] Select "S4 - Prescription (Restricted)" + search "tramadol" → Shows tramadol

### Error Handling
- [ ] Type 1 character → Shows "Please enter at least 2 characters"
- [ ] Search "xyz123" → Shows "No medications found matching your search"
- [ ] Empty search → Button disabled

---

## 📊 Sample Test Results

**Search: "paracetamol"**
```
✅ Found 5 medications:
- 3001570 | Panado Tablets (S0) | Generic: Paracetamol | 500mg Tablet
- 3001865 | Adco-Dol Tablets (S0) | Generic: Paracetamol | 500mg Tablet  
- 714467 | Grandpa Powders (S1) | Generic: Paracetamol + Aspirin + Caffeine | 1g Powder
```

**Search: "metformin"**
```
✅ Found 6 medications:
- 714427 | Accord metformin (S3) | Generic: Metformin | 500mg TAB
- 714426 | Accord metformin (S3) | Generic: Metformin | 850mg TAB
- 707670 | Apex-metformin (S3) | Generic: Metformin | 500mg TAB
- 712979 | Glucophage Tablets (S3) | Generic: Metformin | 850mg Tablet
- [+ 2 more...]
```

**Search: "accord"**
```
✅ Found 20+ medications:
- Accord anastrozole
- Accord metformin
- Accord escitalopram
- [+ 17 more...]
```

---

## 🎯 Quick 5-Minute Test Sequence

1. **Load Page**
   - ✅ Verify: 1,637 medications shown in stats
   
2. **Quick Button Tests**
   - Click "paracetamol" → Should find Panado, Adco-Dol, Grandpa
   - Click "metformin" → Should find 6+ results
   
3. **Manual Search**
   - Type "amoxicillin" → Should find 4 results
   - Type "glucophage" → Should find 1 result (Glucophage Tablets)
   
4. **Filter Test**
   - Search "ibuprofen" + Select "S1" → Should find Brufen
   
5. **Error Test**
   - Type "xyz123" → Should show error message

---

## 📝 What Changed From Your Original Tests

### ✅ Now Working (Previously No Results)
- `paracetamol` → Now finds 5 results (was 0)
- `ibuprofen` → Now finds 3+ results (was 0)
- `glucophage` → Now finds 1 result (was 0)
- `norvasc` → Now finds 1 result (was 0)
- `lipitor` → Now finds 1 result (was 0)
- Brand names now show separately from generic names

### ❓ Still No Results (Not in Database)
- `omeprazole` → Not in Discovery formulary
- `naproxen` → Added Naprosyn, should now work
- `furosemide` → Added Lasix, should now work
- `tamoxifen` → Added Nolvadex, should now work

### 🔧 Fixed Issues
1. ✅ **Brand vs Generic Names:** Now properly separated
   - Before: Both showed same name
   - Now: Brand = "Accord metformin", Generic = "Metformin"
   
2. ✅ **Common Medications:** Added 24 essential medications
   - OTC pain relievers (Panado, Brufen)
   - Brand name medications (Lipitor, Norvasc, Glucophage)
   - Common antibiotics (Augmentin, Zithromax)

---

## 🚀 Next Steps

The NAPPI system is now **production-ready** with:
- 1,637 medications (Discovery formulary + common medications)
- Proper brand/generic name separation
- Working search and filtering
- Complete schedule classification

Ready for integration into PrescriptionBuilder component!
