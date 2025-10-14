-- Seed data for medications database
-- Common medications used in GP practices

INSERT INTO medications (id, name, generic_name, brand_names, category, common_dosages, common_frequencies, route, contraindications, side_effects, pregnancy_category) VALUES

-- Analgesics
('med-001', 'Paracetamol', 'Acetaminophen', ARRAY['Panado', 'Tylenol'], 'Analgesic', ARRAY['500mg', '1g'], ARRAY['Every 4-6 hours', 'Three times daily', 'Four times daily'], 'Oral', 'Severe liver disease', 'Rare: liver toxicity with overdose', 'A'),
('med-002', 'Ibuprofen', 'Ibuprofen', ARRAY['Brufen', 'Nurofen'], 'NSAID/Analgesic', ARRAY['200mg', '400mg', '600mg'], ARRAY['Every 6-8 hours', 'Three times daily'], 'Oral', 'Active peptic ulcer, severe heart failure', 'Gastric irritation, nausea, headache', 'C'),

-- Antibiotics
('med-003', 'Amoxicillin', 'Amoxicillin', ARRAY['Amoxil', 'Moxicure'], 'Antibiotic', ARRAY['250mg', '500mg', '875mg'], ARRAY['Three times daily', 'Twice daily'], 'Oral', 'Penicillin allergy', 'Diarrhea, nausea, rash', 'B'),
('med-004', 'Azithromycin', 'Azithromycin', ARRAY['Zithromax', 'Azimed'], 'Antibiotic', ARRAY['250mg', '500mg'], ARRAY['Once daily'], 'Oral', 'Severe liver disease', 'Nausea, diarrhea, abdominal pain', 'B'),
('med-005', 'Ciprofloxacin', 'Ciprofloxacin', ARRAY['Ciprobay', 'Ciproflox'], 'Antibiotic', ARRAY['250mg', '500mg', '750mg'], ARRAY['Twice daily'], 'Oral', 'Children under 18, pregnancy', 'Nausea, diarrhea, tendon problems', 'C'),

-- Antihypertensives
('med-006', 'Amlodipine', 'Amlodipine', ARRAY['Norvasc', 'Amlopin'], 'Antihypertensive (CCB)', ARRAY['5mg', '10mg'], ARRAY['Once daily'], 'Oral', 'Severe hypotension', 'Ankle swelling, headache, flushing', 'C'),
('med-007', 'Enalapril', 'Enalapril', ARRAY['Renitec', 'Enalapril'], 'Antihypertensive (ACE inhibitor)', ARRAY['5mg', '10mg', '20mg'], ARRAY['Once daily', 'Twice daily'], 'Oral', 'Pregnancy, bilateral renal artery stenosis', 'Dry cough, dizziness, hyperkalemia', 'D'),
('med-008', 'Hydrochlorothiazide', 'Hydrochlorothiazide', ARRAY['HCT', 'Ridaq'], 'Diuretic/Antihypertensive', ARRAY['12.5mg', '25mg'], ARRAY['Once daily'], 'Oral', 'Anuria, severe renal failure', 'Hypokalemia, dizziness, photosensitivity', 'B'),

-- Diabetes medications
('med-009', 'Metformin', 'Metformin', ARRAY['Glucophage', 'Metfin'], 'Antidiabetic (Biguanide)', ARRAY['500mg', '850mg', '1000mg'], ARRAY['Once daily', 'Twice daily', 'Three times daily'], 'Oral', 'Severe renal impairment, metabolic acidosis', 'Nausea, diarrhea, lactic acidosis (rare)', 'B'),
('med-010', 'Glimepiride', 'Glimepiride', ARRAY['Amaryl', 'Glimepiride'], 'Antidiabetic (Sulfonylurea)', ARRAY['1mg', '2mg', '4mg'], ARRAY['Once daily'], 'Oral', 'Diabetic ketoacidosis', 'Hypoglycemia, weight gain, nausea', 'C'),

-- Respiratory
('med-011', 'Salbutamol', 'Salbutamol', ARRAY['Ventolin', 'Asthavent'], 'Bronchodilator', ARRAY['2mg', '4mg', '100mcg (inhaler)'], ARRAY['Three times daily', 'As needed'], 'Oral/Inhaled', 'None significant', 'Tremor, tachycardia, headache', 'C'),
('med-012', 'Prednisone', 'Prednisone', ARRAY['Meticorten', 'Deltasone'], 'Corticosteroid', ARRAY['5mg', '10mg', '20mg'], ARRAY['Once daily', 'Tapering dose'], 'Oral', 'Systemic fungal infections', 'Weight gain, mood changes, osteoporosis', 'C'),

-- Gastrointestinal
('med-013', 'Omeprazole', 'Omeprazole', ARRAY['Losec', 'Omeprazole'], 'Proton Pump Inhibitor', ARRAY['20mg', '40mg'], ARRAY['Once daily'], 'Oral', 'None significant', 'Headache, diarrhea, abdominal pain', 'C'),
('med-014', 'Metoclopramide', 'Metoclopramide', ARRAY['Maxolon', 'Pramin'], 'Antiemetic', ARRAY['10mg'], ARRAY['Three times daily'], 'Oral/IV', 'GI obstruction, pheochromocytoma', 'Drowsiness, restlessness, dystonia', 'B'),

-- Antihistamines
('med-015', 'Cetirizine', 'Cetirizine', ARRAY['Zyrtec', 'Cetrin'], 'Antihistamine', ARRAY['5mg', '10mg'], ARRAY['Once daily'], 'Oral', 'None significant', 'Drowsiness, dry mouth, headache', 'B'),
('med-016', 'Loratadine', 'Loratadine', ARRAY['Clarityne', 'Lorano'], 'Antihistamine', ARRAY['10mg'], ARRAY['Once daily'], 'Oral', 'None significant', 'Minimal drowsiness, headache', 'B'),

-- Antidepressants/Anxiety
('med-017', 'Fluoxetine', 'Fluoxetine', ARRAY['Prozac', 'Nuzac'], 'SSRI Antidepressant', ARRAY['10mg', '20mg', '40mg'], ARRAY['Once daily'], 'Oral', 'MAOI use, mania', 'Nausea, insomnia, anxiety, sexual dysfunction', 'C'),
('med-018', 'Alprazolam', 'Alprazolam', ARRAY['Xanax', 'Alprax'], 'Benzodiazepine', ARRAY['0.25mg', '0.5mg', '1mg'], ARRAY['Twice daily', 'Three times daily'], 'Oral', 'Acute narrow-angle glaucoma', 'Drowsiness, dependence, withdrawal', 'D'),

-- Cholesterol
('med-019', 'Atorvastatin', 'Atorvastatin', ARRAY['Lipitor', 'Atorvastatin'], 'Statin', ARRAY['10mg', '20mg', '40mg'], ARRAY['Once daily (evening)'], 'Oral', 'Active liver disease, pregnancy', 'Myalgia, elevated liver enzymes', 'X'),
('med-020', 'Simvastatin', 'Simvastatin', ARRAY['Zocor', 'Simvastatin'], 'Statin', ARRAY['10mg', '20mg', '40mg'], ARRAY['Once daily (evening)'], 'Oral', 'Active liver disease, pregnancy', 'Myalgia, elevated liver enzymes', 'X');
