/**
 * EHRValidationPanel.jsx
 * Drop-in replacement for ValidationPanel.jsx
 *
 * Props (same contract as ValidationPanel + onFieldFocus):
 *   docId         {string}  - document ID
 *   chunks        {array}   - ADE parse chunks from App.jsx
 *   onFieldFocus  {fn}      - (fieldPath) => void  bridged to PDF highlight in App.jsx
 *   onSaveSuccess {fn}      - (validatedData) => void
 *
 * API: POST /api/extract?doc_id={docId}  same as ValidationPanel
 *      POST /api/validate?doc_id={docId} same as ValidationPanel
 *      GET  /api/icd10/validate?code=X   new — ICD-10 validation
 *      GET  /api/nappi/lookup?drug_name=X new — NAPPI lookup
 */

import React, { useState, useEffect, useCallback } from 'react';
import api from './api';
import { useFieldMetadata, useFieldOriginal } from './FieldMetadataContext';
import {
  User, Heart, Activity, Stethoscope, Pill, Image,
  FileText, FlaskConical, ArrowUpRight,
  Check, Edit3, AlertCircle, ChevronDown, ChevronUp,
  Save, AlertTriangle, Loader, ShieldCheck, ShieldAlert, Brain
} from 'lucide-react';
import './EHRValidationPanel.css';
import RiskScoreBadge from './RiskScoreBadge';
import DrugInteractionAlert from './DrugInteractionAlert';
import LabAnomalyTable from './LabAnomalyTable';
import XrayAnalysisPanel from './XrayAnalysisPanel';

const API_BASE = '/api';

const TABS = [
  { id: 'demographics', label: 'Demographics',  icon: User,         color: '#2563EB' },
  { id: 'history',      label: 'Hx & History',  icon: Heart,        color: '#7C3AED' },
  { id: 'vitals',       label: 'Vitals',         icon: Activity,     color: '#059669' },
  { id: 'diagnoses',    label: 'Diagnoses',      icon: Stethoscope,  color: '#DC2626' },
  { id: 'medications',  label: 'Medications',    icon: Pill,         color: '#D97706' },
  { id: 'notes',        label: 'Progress Notes', icon: FileText,     color: '#0891B2' },
  { id: 'labs',         label: 'Labs',           icon: FlaskConical, color: '#4F46E5' },
  { id: 'referrals',    label: 'Referrals',      icon: ArrowUpRight, color: '#BE185D' },
  { id: 'imaging',      label: 'X-ray',          icon: Image,        color: '#475569' },
];

function ICD10Badge({ code, result }) {
  if (!code) return null;
  if (!result) return <span className="icd-badge icd-pending"><Loader size={9} className="spinning-tiny" /> {code}</span>;
  if (result.valid && result.hipaa_valid) return <span className="icd-badge icd-valid" title={result.description}><ShieldCheck size={10} /> {code}</span>;
  if (result.valid && !result.hipaa_valid) return <span className="icd-badge icd-category" title="Too broad — needs more specific code"><ShieldAlert size={10} /> {code} (broad)</span>;
  return <span className="icd-badge icd-invalid" title="Not found in ICD-10"><AlertCircle size={10} /> {code} (invalid)</span>;
}

function NAPPIBadge({ drug, result }) {
  if (!drug || !result) return null;
  if (!result.found) return <span className="nappi-badge nappi-not-found">No NAPPI</span>;
  // Curated rows use a CURATED-XXX synthetic id — show the slug, not the
  // full code; flag as "curated" so reviewers know it's not a real NAPPI yet.
  const isCurated = typeof result.nappi_code === 'string' && result.nappi_code.startsWith('CURATED-');
  const label = isCurated
    ? <>CURATED <span style={{ opacity: 0.7 }}>(NAPPI pending)</span></>
    : <>NAPPI {result.nappi_code}</>;
  return (
    <span className="nappi-badge-group" style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
      <span className={isCurated ? 'nappi-badge nappi-curated' : 'nappi-badge nappi-found'}>{label}</span>
      {result.schedule && (
        <span className="nappi-badge nappi-schedule" title="South African medicine schedule">{result.schedule}</span>
      )}
      {result.atc_code && (
        <span
          className="nappi-badge nappi-atc"
          title={result.atc_class_desc ? `${result.atc_code} — ${result.atc_class_desc}` : result.atc_code}
        >
          ATC {result.atc_code}
          {result.atc_class_desc && <span style={{ opacity: 0.75, marginLeft: 4 }}>{result.atc_class_desc}</span>}
        </span>
      )}
    </span>
  );
}

function ConfBadge({ score }) {
  if (score == null) return <span className="conf-badge conf-missing">–</span>;
  if (score >= 0.9)  return <span className="conf-badge conf-high">{Math.round(score*100)}%</span>;
  if (score >= 0.7)  return <span className="conf-badge conf-med">{Math.round(score*100)}%</span>;
  return               <span className="conf-badge conf-low">{Math.round(score*100)}%</span>;
}

function EHRField({ label, fieldPath, value, confidence, required, multiline, onEdit, onFocus, readOnly, children }) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(value ?? '');
  const [accepted, setAccepted] = useState(false);
  useEffect(() => { setLocal(value ?? ''); }, [value]);

  // Live grounding metadata from LandingAI ADE (when available). When provided,
  // overrides the panel's hardcoded `confidence` prop so doctors see the real
  // grounding signal instead of a placeholder. The badge provenance also drives
  // an "inferred" tooltip so reviewers know to double-check ungrounded values.
  const meta = useFieldMetadata(fieldPath);
  const liveConfidence = meta ? meta.confidence : confidence;
  const provenance     = meta ? meta.provenance : null;
  const refCount       = meta && Array.isArray(meta.references) ? meta.references.length : null;

  // AI baseline caption — when "Show AI baseline" is toggled in the
  // ValidationHistoryDrawer AND the original AI value differs from the current
  // (post-edit) value, surface a tiny "AI: ..." caption so the reviewer can see
  // what was changed. Returns null when toggle is off or values match.
  const originalAiValue = useFieldOriginal(fieldPath, value);

  const confClass = liveConfidence == null ? 'field-missing' : liveConfidence >= 0.9 ? 'field-high' : liveConfidence >= 0.7 ? 'field-med' : 'field-low';
  const save = () => { setEditing(false); setAccepted(true); onEdit?.(fieldPath, local); };
  return (
    <div className={`ehr-field ${confClass} ${accepted ? 'ehr-field-accepted' : ''}`} onClick={() => onFocus?.(fieldPath)}>
      <div className="ehr-field-header">
        <span className="ehr-field-label">{label}{required && <span className="ehr-required">*</span>}</span>
        <div className="ehr-field-controls">
          {provenance === 'inferred' && (
            <span
              className="conf-badge conf-med"
              title="AI-inferred — not grounded in any source chunk. Verify against the PDF."
              style={{ marginRight: 2 }}
            >
              <AlertTriangle size={9} /> AI
            </span>
          )}
          {provenance === 'grounded' && refCount > 0 && (
            <span
              className="conf-badge conf-high"
              title={`Grounded in ${refCount} source chunk${refCount === 1 ? '' : 's'}. Click the field to view.`}
              style={{ marginRight: 2 }}
            >
              <ShieldCheck size={9} /> {refCount}
            </span>
          )}
          <ConfBadge score={liveConfidence} />
          {!readOnly && !editing && !accepted && (<>
            <button className="btn-icon btn-accept" onClick={e=>{e.stopPropagation();setAccepted(true);onEdit?.(fieldPath,local);}}><Check size={11}/></button>
            <button className="btn-icon btn-edit" onClick={e=>{e.stopPropagation();setEditing(true);}}><Edit3 size={11}/></button>
          </>)}
          {!readOnly && accepted && <button className="btn-icon btn-accepted" onClick={e=>{e.stopPropagation();setAccepted(false);setEditing(true);}}><Check size={11}/></button>}
        </div>
      </div>
      {editing && !readOnly
        ? multiline
          ? <textarea className="ehr-input ehr-textarea" value={local} onChange={e=>setLocal(e.target.value)} onBlur={save} autoFocus onClick={e=>e.stopPropagation()} rows={3}/>
          : <input className="ehr-input" value={local} onChange={e=>setLocal(e.target.value)} onBlur={save} onKeyDown={e=>e.key==='Enter'&&save()} autoFocus onClick={e=>e.stopPropagation()}/>
        : <div className="ehr-field-value">{local ? <span className={accepted?'value-accepted':''}>{local}</span> : <span className="value-empty">—</span>}{children}</div>
      }
      {originalAiValue != null && (
        <div
          className="ehr-ai-baseline"
          title="The AI's original value before the reviewer edited it. Toggle off in the History drawer."
          style={{
            marginTop: 4,
            paddingLeft: 8,
            borderLeft: '2px solid #d97706',
            fontSize: 11,
            color: '#92400e',
            lineHeight: 1.4,
          }}
        >
          <span style={{ fontWeight: 700, marginRight: 4 }}>AI:</span>
          <span style={{ fontFamily: 'monospace' }}>
            {typeof originalAiValue === 'object' ? JSON.stringify(originalAiValue) : String(originalAiValue)}
          </span>
        </div>
      )}
    </div>
  );
}

const Row = ({children}) => <div className="ehr-row">{children}</div>;
const SH  = ({label, top}) => <div className="ehr-section-header" style={top?{}:{marginTop:14}}>{label}</div>;

function ArraySection({ title, icon: Icon, color, items, emptyMsg, renderItem }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="ehr-array-section">
      <div className="ehr-array-header" style={{borderLeftColor:color}} onClick={()=>setOpen(o=>!o)}>
        <div className="ehr-array-title"><Icon size={14} style={{color}}/><span>{title}</span><span className="ehr-array-count">{items?.length??0}</span></div>
        {open ? <ChevronUp size={13}/> : <ChevronDown size={13}/>}
      </div>
      {open && (
        <div className="ehr-array-body">
          {items?.length > 0
            ? items.map((item,i) => (
                <div key={i} className="ehr-array-item">
                  <div className="ehr-item-index">{i+1}</div>
                  <div className="ehr-item-content">{renderItem(item,i)}</div>
                </div>
              ))
            : <p className="ehr-empty">{emptyMsg}</p>}
        </div>
      )}
    </div>
  );
}

function DemographicsTab({data, onEdit, onFocus, readOnly}) {
  const d=data?.patient_demographics??{}, aid=data?.medical_aid??{}, kin=data?.next_of_kin??{}, dep=data?.dependents??[];
  return (
    <div className="tab-content">
      <SH label="Patient Details" top/>
      <EHRField label="File / Computer No." fieldPath="patient_demographics.file_number" value={d.file_number} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <Row><EHRField label="First Names" fieldPath="patient_demographics.full_names" value={d.full_names} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Surname" fieldPath="patient_demographics.surname" value={d.surname} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <Row><EHRField label="ID Number" fieldPath="patient_demographics.id_number" value={d.id_number} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Date of Birth" fieldPath="patient_demographics.date_of_birth" value={d.date_of_birth} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <Row><EHRField label="Cell / Tel." fieldPath="patient_demographics.telephone_cell" value={d.telephone_cell} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Email" fieldPath="patient_demographics.email" value={d.email} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <EHRField label="Address" fieldPath="patient_demographics.address" value={d.address} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <SH label="Medical Aid"/>
      <Row><EHRField label="Scheme" fieldPath="medical_aid.scheme_name" value={aid.scheme_name} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Member No." fieldPath="medical_aid.member_number" value={aid.member_number} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <Row><EHRField label="Plan" fieldPath="medical_aid.plan" value={aid.plan} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Main Member" fieldPath="medical_aid.main_member_name" value={aid.main_member_name} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <SH label="Next of Kin"/>
      <Row><EHRField label="Name" fieldPath="next_of_kin.name" value={kin.name} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Relationship" fieldPath="next_of_kin.relationship" value={kin.relationship} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
      <EHRField label="Contact Number" fieldPath="next_of_kin.telephone_cell" value={kin.telephone_cell} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      {dep.length>0 && (<><SH label="Dependents"/>{dep.map((d,i)=>(<div key={i} className="ehr-dep-row"><span className="dep-index">{i+1}</span><div style={{flex:1,display:'flex',flexDirection:'column',gap:5}}><EHRField label="Name" fieldPath={`dependents[${i}].name`} value={d.name} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><Row><EHRField label="DOB" fieldPath={`dependents[${i}].date_of_birth`} value={d.date_of_birth} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Allergies" fieldPath={`dependents[${i}].allergies`} value={d.allergies} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row></div></div>))}</>)}
    </div>
  );
}

function HistoryTab({data, onEdit, onFocus, readOnly}) {
  const hx=data?.clinical_history??{}, arr=v=>Array.isArray(v)?v.join(', '):(v??'');
  return (
    <div className="tab-content">
      <SH label="Allergies" top/><EHRField label="Known Allergies" fieldPath="clinical_history.known_allergies" value={arr(hx.known_allergies)} required multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <SH label="Chronic Conditions"/><EHRField label="Chronic Conditions" fieldPath="clinical_history.chronic_conditions" value={arr(hx.chronic_conditions)} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <SH label="Medical History"/>
      <EHRField label="Past Medical History (PMHx)" fieldPath="clinical_history.past_medical_history" value={hx.past_medical_history} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <EHRField label="Surgical History" fieldPath="clinical_history.surgical_history" value={hx.surgical_history} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <EHRField label="Family History (FHx)" fieldPath="clinical_history.family_history" value={hx.family_history} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
      <EHRField label="Social History (SHx)" fieldPath="clinical_history.social_history" value={hx.social_history} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
    </div>
  );
}

function VitalsTab({data, onEdit, onFocus, readOnly}) {
  const v=data?.vitals_history??[];
  return (
    <div className="tab-content">
      {v.length===0 && <p className="ehr-empty" style={{marginTop:20}}>No vitals extracted</p>}
      {v.map((v,i)=>(
        <div key={i} className="ehr-vitals-card">
          <div className="vitals-date">{v.consultation_date??`Visit ${i+1}`}</div>
          <div className="vitals-grid">
            <EHRField label="Temp (°C)" fieldPath={`vitals_history[${i}].temperature_c`} value={v.temperature_c} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="HR (bpm)" fieldPath={`vitals_history[${i}].heart_rate`} value={v.heart_rate} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="BP Sys." fieldPath={`vitals_history[${i}].bp_systolic`} value={v.bp_systolic} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="BP Dias." fieldPath={`vitals_history[${i}].bp_diastolic`} value={v.bp_diastolic} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="O₂ Sat" fieldPath={`vitals_history[${i}].oxygen_saturation`} value={v.oxygen_saturation} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="Weight (kg)" fieldPath={`vitals_history[${i}].weight_kg`} value={v.weight_kg} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="BMI" fieldPath={`vitals_history[${i}].bmi`} value={v.bmi} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="HbA1c" fieldPath={`vitals_history[${i}].hba1c`} value={v.hba1c} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="FBS (mmol/L)" fieldPath={`vitals_history[${i}].blood_glucose_fasting`} value={v.blood_glucose_fasting} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
          </div>
        </div>
      ))}
    </div>
  );
}

function DiagnosesTab({data, onEdit, onFocus, readOnly, icd10Cache}) {
  const dx=data?.diagnoses??[];
  return (
    <div className="tab-content">
      <ArraySection title="Diagnoses" icon={Stethoscope} color="#DC2626" items={dx} emptyMsg="No diagnoses extracted"
        renderItem={(d,i)=>(
          <div style={{display:'flex',flexDirection:'column',gap:5}}>
            <Row>
              <EHRField label="Date" fieldPath={`diagnoses[${i}].consultation_date`} value={d.consultation_date} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
              <div className="ehr-field field-high" style={{flex:1}}>
                <div className="ehr-field-header"><span className="ehr-field-label">ICD-10 Code</span><ConfBadge score={0.92}/></div>
                <div className="ehr-field-value">
                  <ICD10Badge code={d.icd10_code} result={icd10Cache?.[d.icd10_code]}/>
                  {d.icd10_code && icd10Cache?.[d.icd10_code]?.description && <span className="icd-desc">{icd10Cache[d.icd10_code].description}</span>}
                </div>
              </div>
            </Row>
            <EHRField label="Description" fieldPath={`diagnoses[${i}].description`} value={d.description} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="Status" fieldPath={`diagnoses[${i}].status`} value={d.status} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
          </div>
        )}
      />
    </div>
  );
}

function MedicationsTab({data, onEdit, onFocus, readOnly, nappiCache}) {
  const meds=data?.medications??[];
  return (
    <div className="tab-content">
      <ArraySection title="Medications" icon={Pill} color="#D97706" items={meds} emptyMsg="No medications extracted"
        renderItem={(m,i)=>(
          <div style={{display:'flex',flexDirection:'column',gap:5}}>
            <Row><EHRField label="Date" fieldPath={`medications[${i}].consultation_date`} value={m.consultation_date} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Status" fieldPath={`medications[${i}].status`} value={m.status} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
            <div className="ehr-field field-high">
              <div className="ehr-field-header"><span className="ehr-field-label">Drug Name<span className="ehr-required">*</span></span><ConfBadge score={0.92}/></div>
              <div className="ehr-field-value"><span>{m.drug_name||<span className="value-empty">—</span>}</span><NAPPIBadge drug={m.drug_name} result={nappiCache?.[m.drug_name]}/></div>
            </div>
            <Row><EHRField label="Dosage" fieldPath={`medications[${i}].dosage`} value={m.dosage} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Frequency" fieldPath={`medications[${i}].frequency`} value={m.frequency} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Duration" fieldPath={`medications[${i}].duration`} value={m.duration} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
            <EHRField label="Instructions" fieldPath={`medications[${i}].instructions`} value={m.instructions} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
          </div>
        )}
      />
    </div>
  );
}

function ProgressNotesTab({data, onEdit, onFocus, readOnly}) {
  const notes=data?.progress_notes??[];
  return (
    <div className="tab-content">
      {notes.length===0 && <p className="ehr-empty" style={{marginTop:20}}>No consultation notes extracted</p>}
      {notes.map((note,i)=>(
        <div key={i} className="ehr-soap-card">
          <div className="soap-date">{note.consultation_date??`Consultation ${i+1}`}</div>
          <div className="soap-row soap-s"><span className="soap-lbl soap-lbl-s">S</span><EHRField label="Subjective" fieldPath={`progress_notes[${i}].subjective`} value={note.subjective} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></div>
          <div className="soap-row soap-o"><span className="soap-lbl soap-lbl-o">O</span><EHRField label="Objective" fieldPath={`progress_notes[${i}].objective`} value={note.objective} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></div>
          <div className="soap-row soap-a"><span className="soap-lbl soap-lbl-a">A</span><EHRField label="Assessment" fieldPath={`progress_notes[${i}].assessment`} value={note.assessment} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></div>
          <div className="soap-row soap-p"><span className="soap-lbl soap-lbl-p">P</span><EHRField label="Plan" fieldPath={`progress_notes[${i}].plan`} value={note.plan} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></div>
        </div>
      ))}
    </div>
  );
}

function LabsTab({data, onEdit, onFocus, readOnly}) {
  const inv=data?.investigations??[];
  return (
    <div className="tab-content">
      <ArraySection title="Investigations" icon={FlaskConical} color="#4F46E5" items={inv} emptyMsg="No lab results extracted"
        renderItem={(item,i)=>(
          <div style={{display:'flex',flexDirection:'column',gap:5}}>
            <Row><EHRField label="Date" fieldPath={`investigations[${i}].consultation_date`} value={item.consultation_date} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Status" fieldPath={`investigations[${i}].status`} value={item.status} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
            <EHRField label="Test Name" fieldPath={`investigations[${i}].test_name`} value={item.test_name} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <Row><EHRField label="Result" fieldPath={`investigations[${i}].result_value`} value={item.result_value} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Unit" fieldPath={`investigations[${i}].result_unit`} value={item.result_unit} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Ref. Range" fieldPath={`investigations[${i}].reference_range`} value={item.reference_range} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
            <EHRField label="Interpretation" fieldPath={`investigations[${i}].result_interpretation`} value={item.result_interpretation} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
          </div>
        )}
      />
    </div>
  );
}

function ReferralsTab({data, onEdit, onFocus, readOnly}) {
  const refs=data?.referrals??[];
  return (
    <div className="tab-content">
      <ArraySection title="Referrals" icon={ArrowUpRight} color="#BE185D" items={refs} emptyMsg="No referrals extracted"
        renderItem={(ref,i)=>(
          <div style={{display:'flex',flexDirection:'column',gap:5}}>
            <Row><EHRField label="Date" fieldPath={`referrals[${i}].referral_date`} value={ref.referral_date} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Urgency" fieldPath={`referrals[${i}].urgency`} value={ref.urgency} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/><EHRField label="Status" fieldPath={`referrals[${i}].status`} value={ref.status} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/></Row>
            <EHRField label="Referred To" fieldPath={`referrals[${i}].referred_to`} value={ref.referred_to} required onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="Reason" fieldPath={`referrals[${i}].reason`} value={ref.reason} multiline onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
            <EHRField label="Outcome" fieldPath={`referrals[${i}].outcome`} value={ref.outcome} onEdit={onEdit} onFocus={onFocus} readOnly={readOnly}/>
          </div>
        )}
      />
    </div>
  );
}

const DOC_TYPE_OPTIONS = [
  { value: '', label: 'Auto-detect' },
  { value: 'gp_patient_record', label: 'GP Patient Record' },
  { value: 'lab_result', label: 'Lab Result' },
  { value: 'soap_note', label: 'SOAP Note' },
  { value: 'referral_letter', label: 'Referral Letter' },
  { value: 'prescription', label: 'Prescription' },
  { value: 'medical_certificate', label: 'Medical Certificate' },
];

const EHRValidationPanel = ({ docId, docType: initialDocType, chunks, onFieldFocus, onSaveSuccess, isRecord }) => {
  const [activeTab,    setActiveTab]    = useState('demographics');
  const [editedData,   setEditedData]   = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving,     setIsSaving]     = useState(false);
  const [saveStatus,   setSaveStatus]   = useState(null);
  const [error,        setError]        = useState('');
  const [currentDocId, setCurrentDocId] = useState(null);
  const [hasExtracted, setHasExtracted] = useState(false);
  const [icd10Cache,   setIcd10Cache]   = useState({});
  const [nappiCache,   setNappiCache]   = useState({});
  const [docTypeOverride, setDocTypeOverride] = useState('');
  const [mlResults,    setMlResults]    = useState(null);
  const [mlLoading,    setMlLoading]    = useState(false);

  useEffect(() => {
    setDocTypeOverride(initialDocType || '');
  }, [initialDocType]);

  useEffect(() => {
    if (docId && (!hasExtracted || docId !== currentDocId)) {
      extractData();
      setCurrentDocId(docId);
    }
  }, [docId]);

  const extractData = async () => {
    setIsExtracting(true); setError(''); setSaveStatus(null);
    try {
      const params = { doc_id: docId };
      if (docTypeOverride) params.doc_type = docTypeOverride;
      const res = await api.post(`${API_BASE}/extract`, null, { params });
      const data = res.data;
      const extracted = data.extracted_data || {};
      setEditedData(JSON.parse(JSON.stringify(extracted)));
      setHasExtracted(true);
      validateICD10Codes(extracted);
      lookupNAPPICodes(extracted);
    } catch (err) {
      setError(err.message || 'Failed to extract data');
    } finally {
      setIsExtracting(false);
    }
  };

  const validateICD10Codes = async (data) => {
    const codes = [...new Set((data?.diagnoses??[]).map(d=>d.icd10_code).filter(Boolean))];
    if (!codes.length) return;
    const results = {};
    await Promise.all(codes.map(async code => {
      try {
        const r = await api.get(`${API_BASE}/icd10/validate`, { params: { code } });
        const d = r.data;
        results[code] = d ? { valid: d.found, hipaa_valid: d.valid_for_hipaa, description: d.description } : { valid: false, hipaa_valid: false, description: null };
      } catch { results[code] = { valid: false, hipaa_valid: false, description: null }; }
    }));
    setIcd10Cache(prev => ({ ...prev, ...results }));
  };

  const lookupNAPPICodes = async (data) => {
    const drugs = [...new Set((data?.medications??[]).map(m=>m.drug_name).filter(Boolean))];
    if (!drugs.length) return;
    const results = {};
    await Promise.all(drugs.map(async drug => {
      try {
        const r = await api.get(`${API_BASE}/nappi/lookup`, { params: { drug_name: drug } });
        const d = r.data;
        results[drug] = d ? {
          found:          d.found,
          nappi_code:     d.nappi_code,
          schedule:       d.schedule,
          atc_code:       d.atc_code,
          atc_class_desc: d.atc_class_desc,
        } : { found: false, nappi_code: null };
      } catch { results[drug] = { found: false, nappi_code: null }; }
    }));
    setNappiCache(prev => ({ ...prev, ...results }));
  };

  const handleEdit = useCallback((fieldPath, newValue) => {
    setEditedData(prev => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev));
      const parts = fieldPath.replace(/\[(\d+)\]/g, '.$1').split('.');
      let obj = next;
      for (let i = 0; i < parts.length - 1; i++) { if (obj[parts[i]] === undefined) obj[parts[i]] = {}; obj = obj[parts[i]]; }
      obj[parts[parts.length - 1]] = newValue;
      return next;
    });
  }, []);

  const handleFocus = useCallback((fieldPath) => { onFieldFocus?.(fieldPath); }, [onFieldFocus]);

  const handleSave = async () => {
    setIsSaving(true); setSaveStatus(null);
    try {
      await api.post(`${API_BASE}/validate`, editedData, { params: { doc_id: docId } });
      setSaveStatus('success');
      onSaveSuccess?.(editedData);
    } catch (err) {
      setSaveStatus('error'); setError(err.message || 'Save failed');
    } finally {
      setIsSaving(false);
    }
  };

  const runMLAnalysis = async () => {
    if (!docId) return;
    setMlLoading(true);
    try {
      const res = await api.post(`${API_BASE}/ml/risk/batch`, { doc_id: docId, validated_data: editedData });
      setMlResults(res.data?.results || null);
    } catch (err) {
      setError('ML analysis failed: ' + (err.response?.data?.detail || err.message));
      setMlResults(null);
    } finally {
      setMlLoading(false);
    }
  };

  const renderTab = () => {
    const p = { data: editedData, onEdit: handleEdit, onFocus: handleFocus, readOnly: isRecord };
    switch (activeTab) {
      case 'demographics': return <DemographicsTab {...p}/>;
      case 'history':      return <HistoryTab {...p}/>;
      case 'vitals':       return <><VitalsTab {...p}/>{mlResults?.diabetes && <RiskScoreBadge score={mlResults.diabetes.risk_score} label={mlResults.diabetes.risk_label} modelName="Diabetes Risk" factors={mlResults.diabetes.contributing_factors||[]}/>}{mlResults?.cardiovascular && <RiskScoreBadge score={mlResults.cardiovascular.risk_score} label={mlResults.cardiovascular.risk_label} modelName="CVD Risk" factors={mlResults.cardiovascular.contributing_factors||[]}/>}</>;
      case 'diagnoses':    return <DiagnosesTab {...p} icd10Cache={icd10Cache}/>;
      case 'medications':  return <><MedicationsTab {...p} nappiCache={nappiCache}/>{mlResults?.drug_interactions && <DrugInteractionAlert interactions={mlResults.drug_interactions.interactions||[]} disclaimer={mlResults.drug_interactions.disclaimer}/>}</>;
      case 'notes':        return <ProgressNotesTab {...p}/>;
      case 'labs':         return <><LabsTab {...p}/>{mlResults?.lab_anomalies && <LabAnomalyTable results={mlResults.lab_anomalies.results||[]} disclaimer={mlResults.lab_anomalies.disclaimer}/>}</>;
      case 'referrals':    return <ReferralsTab {...p}/>;
      case 'imaging':      return <XrayAnalysisPanel />;
      default: return null;
    }
  };

  if (isExtracting) return <div className="ehr-panel ehr-state-center"><Loader className="spinning" size={28}/><p>Extracting clinical data...</p></div>;
  if (!editedData && error) return <div className="ehr-panel ehr-state-center"><AlertCircle size={28} color="#DC2626"/><p style={{color:'#DC2626'}}>{error}</p><button className="btn-retry" onClick={extractData}>Retry</button></div>;
  if (!editedData) return <div className="ehr-panel ehr-state-center"><FileText size={36} color="#9CA3AF"/><p style={{color:'#9CA3AF'}}>Select a document to begin</p></div>;

  const demo = editedData?.patient_demographics ?? {};

  return (
    <div className="ehr-panel">
      <div className="ehr-identity-strip">
        <div className="ehr-identity-row">
          <div className="patient-name">{demo.full_names||demo.surname ? `${demo.full_names??''} ${demo.surname??''}`.trim() : 'Unknown Patient'}</div>
          <div className="doc-type-selector">
            <select value={docTypeOverride} onChange={e => setDocTypeOverride(e.target.value)} className="doc-type-select">
              {DOC_TYPE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button className="btn-re-extract" onClick={extractData} disabled={isExtracting} title="Re-extract with selected doc type">
              {isExtracting ? <Loader size={11} className="spinning-tiny"/> : <Edit3 size={11}/>} Re-extract
            </button>
          </div>
        </div>
        <div className="patient-meta">
          <span>File: {demo.file_number??'—'}</span>
          <span>ID: {demo.id_number??'—'}</span>
          <span style={{color: editedData?.medical_aid?.scheme_name ? '#6EE7B7' : '#6B7280'}}>{editedData?.medical_aid?.scheme_name??'No medical aid'}</span>
        </div>
      </div>

      <div className="ehr-tab-bar">
        {TABS.map(tab => {
          const Icon = tab.icon; const active = activeTab === tab.id;
          return <button key={tab.id} className={`ehr-tab ${active?'ehr-tab-active':''}`} style={active?{borderBottomColor:tab.color,color:tab.color}:{}} onClick={()=>setActiveTab(tab.id)} title={tab.label}><Icon size={12}/><span>{tab.label}</span></button>;
        })}
      </div>

      {saveStatus==='success' && <div className="ehr-status ehr-status-success"><Check size={13}/> Record saved successfully</div>}
      {saveStatus==='error'   && <div className="ehr-status ehr-status-error"><AlertCircle size={13}/> {error||'Save failed'}</div>}

      <div className="ehr-content-area">{renderTab()}</div>

      {!isRecord && (
        <div className="ehr-save-bar">
          <div className="save-hint"><AlertTriangle size={12}/><span>Review flagged fields before saving</span></div>
          <div className="save-actions">
            <button className="btn-analyze" onClick={runMLAnalysis} disabled={mlLoading} title="Run AI risk analysis">
              {mlLoading ? <Loader size={13} className="spinning-tiny"/> : <Brain size={13}/>}
              {mlLoading ? 'Analyzing...' : 'Analyze'}
            </button>
            <button className="btn-save-secondary" onClick={handleSave} disabled={isSaving}>Save with Deficiencies</button>
            <button className="btn-save-primary" onClick={handleSave} disabled={isSaving}>
              {isSaving ? <Loader size={13} className="spinning"/> : <Save size={13}/>}
              {isSaving ? 'Saving...' : 'Save & Accept'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EHRValidationPanel;
