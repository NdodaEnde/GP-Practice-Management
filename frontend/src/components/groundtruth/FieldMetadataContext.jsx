/**
 * FieldMetadataContext — surfaces the extraction engine's per-field grounding into
 * the lifted EHRValidationPanel without touching its render shape.
 *
 * The panel calls EHRField for every leaf value with a `fieldPath` like
 * "patient_demographics.full_names" or "diagnoses[0].icd10_code". We flatten
 * the API's `extraction_metadata` into the same fieldPath keys so EHRField
 * can look up real {value, references, confidence, provenance} on render.
 *
 * Confidence derivation:
 *   references.length > 0   →  0.95   provenance='grounded'
 *   value present, no refs  →  0.65   provenance='inferred'
 *   value null / empty      →  null   provenance='missing'
 */

import React, { createContext, useContext, useMemo } from 'react';

const FieldMetadataContext = createContext({
  map:           {},
  hasMetadata:   false,
  originalMap:   {},
  showOriginal:  false,
});

export const useFieldMetadata = (fieldPath) => {
  const { map, hasMetadata } = useContext(FieldMetadataContext);
  if (!hasMetadata || !fieldPath) return null;
  return map[fieldPath] || null;
};

// Returns null when (a) showOriginal is off, (b) no original value exists for
// this fieldPath, or (c) the original value matches the current value.
// When non-null, returns the original AI value the panel should caption.
export const useFieldOriginal = (fieldPath, currentValue) => {
  const { originalMap, showOriginal } = useContext(FieldMetadataContext);
  if (!showOriginal || !fieldPath) return null;
  const original = originalMap[fieldPath];
  if (original === undefined || original === null) return null;
  // Compare via JSON stringification to handle objects/arrays cleanly
  if (JSON.stringify(original) === JSON.stringify(currentValue ?? null)) return null;
  return original;
};

// Walk an extraction_metadata tree and emit (fieldPath, leaf) for every
// {value, references} leaf node. Lists become indexed paths like
// "diagnoses[0].icd10_code".
function flattenMetadata(node, path = '', out = {}) {
  if (node == null || typeof node !== 'object') return out;
  // Leaf: { value, references }
  if (Object.prototype.hasOwnProperty.call(node, 'value') &&
      Object.prototype.hasOwnProperty.call(node, 'references')) {
    out[path] = node;
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((child, idx) => {
      flattenMetadata(child, `${path}[${idx}]`, out);
    });
    return out;
  }
  // Object: recurse
  Object.entries(node).forEach(([key, child]) => {
    const subPath = path ? `${path}.${key}` : key;
    flattenMetadata(child, subPath, out);
  });
  return out;
}

// Convert raw {value, references} → {value, references, confidence, provenance}
function enrichLeaf(leaf) {
  if (!leaf) return null;
  const refs = Array.isArray(leaf.references) ? leaf.references : [];
  const hasValue = leaf.value !== null && leaf.value !== undefined && leaf.value !== '';
  if (!hasValue) {
    return { value: null, references: refs, confidence: null, provenance: 'missing' };
  }
  if (refs.length > 0) {
    return { value: leaf.value, references: refs, confidence: 0.95, provenance: 'grounded' };
  }
  return { value: leaf.value, references: refs, confidence: 0.65, provenance: 'inferred' };
}

// Flatten a plain extractions tree (no {value, references} wrapper — just
// raw values) into {fieldPath: value}. Used for the AI-baseline overlay.
function flattenPlain(node, path = '', out = {}) {
  if (node == null || typeof node !== 'object') {
    if (path) out[path] = node;
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((child, idx) => flattenPlain(child, `${path}[${idx}]`, out));
    return out;
  }
  Object.entries(node).forEach(([k, v]) => {
    flattenPlain(v, path ? `${path}.${k}` : k, out);
  });
  return out;
}

export const FieldMetadataProvider = ({
  extractionMetadata,
  originalExtractions = null,   // raw {section: {...}} from /history.original
  showOriginal = false,
  children,
}) => {
  const map = useMemo(() => {
    if (!extractionMetadata || typeof extractionMetadata !== 'object') return {};
    const flat = flattenMetadata(extractionMetadata);
    const enriched = {};
    for (const [key, leaf] of Object.entries(flat)) {
      enriched[key] = enrichLeaf(leaf);
    }
    return enriched;
  }, [extractionMetadata]);

  const originalMap = useMemo(() => {
    if (!originalExtractions || typeof originalExtractions !== 'object') return {};
    return flattenPlain(originalExtractions);
  }, [originalExtractions]);

  const value = useMemo(
    () => ({
      map,
      hasMetadata:  Object.keys(map).length > 0,
      originalMap,
      showOriginal,
    }),
    [map, originalMap, showOriginal],
  );

  return (
    <FieldMetadataContext.Provider value={value}>
      {children}
    </FieldMetadataContext.Provider>
  );
};

export default FieldMetadataContext;
