import React, { useEffect, useMemo, useState } from 'react';
import { Search, ChevronRight, FileText, Sparkles, AlertCircle, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import fdAPI from '@/services/fd';

/**
 * FinancialDisclosureCopilot — the demo surface for the Mining-gateway /
 * Financial-Disclosure module. Implements spec §7.5 Demos 1+2 (Demo 3 is
 * a separate ingest page, step 8).
 *
 * Layout: left rail = 6 suggested prompts; right pane = open search + answer.
 *
 * The answer-rendering rules are NOT in this component — the backend's
 * fd_answer_contract has already enforced spec §7.4 (every figure has a
 * span, derived figures carry their arithmetic, strategically_attributed
 * rows carry the constrained §7.3 prose). This file just renders what the
 * server emits, verbatim.
 */

// Suggested-prompt defaults — params the rail-safe path needs.
const PROMPT_DEFAULTS = {
  Q1:           { fiscal_year: 2024 },
  Q2:           {},
  Q3:           { source_asset_id: 'GROOT-001', destination_id: 'CENNERGI-001' },
  Q4:           {},
  Q_COMPLIANCE: {},
  Q_DELTA:      { prev: 2023, curr: 2024 },
};

export default function FinancialDisclosureCopilot() {
  const [prompts, setPrompts] = useState([]);
  const [questionText, setQuestionText] = useState('');
  const [activePromptId, setActivePromptId] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [openEvidence, setOpenEvidence] = useState({}); // { rowIdx: bool }

  // Pull the suggested-prompt catalogue once.
  useEffect(() => {
    let cancelled = false;
    fdAPI.prompts()
      .then((res) => { if (!cancelled) setPrompts(res.data.prompts || []); })
      .catch((e) => { if (!cancelled) setError(`Failed to load prompts: ${e.message}`); });
    return () => { cancelled = true; };
  }, []);

  const runQuery = async ({ queryId, question }) => {
    setLoading(true);
    setError(null);
    setAnswer(null);
    setOpenEvidence({});
    try {
      const params = queryId ? (PROMPT_DEFAULTS[queryId] || {}) : {};
      const res = await fdAPI.query({ queryId, question, params });
      setAnswer(res.data);
      setActivePromptId(queryId || null);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Query failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    const q = questionText.trim();
    if (!q) return;
    setActivePromptId(null);
    runQuery({ question: q });
  };

  return (
    <TooltipProvider>
      <div className="container mx-auto px-4 py-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-indigo-700" />
              <h1 className="text-2xl font-semibold text-slate-900">Financial-Disclosure Copilot</h1>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Grounded answers about Exxaro's capital-transition story — every figure cites its source
              and labels how certain it is.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* Left rail — suggested prompts */}
          <div className="col-span-12 lg:col-span-4 space-y-3">
            <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">Suggested prompts</h2>
            <div className="space-y-2">
              {prompts.map((p) => (
                <button
                  key={p.query_id}
                  onClick={() => runQuery({ queryId: p.query_id })}
                  className={`w-full text-left p-3 rounded-md border transition
                    ${activePromptId === p.query_id
                      ? 'border-indigo-300 bg-indigo-50'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-xs font-medium text-slate-400">{p.query_id}</div>
                      <div className="text-sm text-slate-900 mt-0.5">{p.label}</div>
                    </div>
                    <ChevronRight className="h-4 w-4 mt-1 text-slate-300" />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Right pane — search + answer */}
          <div className="col-span-12 lg:col-span-8 space-y-4">
            <form onSubmit={onSubmit} className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  className="pl-10"
                  placeholder="Ask anything in scope of the public reports…"
                  value={questionText}
                  onChange={(e) => setQuestionText(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={loading || !questionText.trim()}>
                {loading ? 'Asking…' : 'Ask'}
              </Button>
            </form>

            {error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="py-3 flex items-start gap-2 text-red-800">
                  <AlertCircle className="h-4 w-4 mt-0.5" />
                  <div className="text-sm">{error}</div>
                </CardContent>
              </Card>
            )}

            {loading && !answer && (
              <Card><CardContent className="py-6 text-slate-500 text-sm">Querying the graph…</CardContent></Card>
            )}

            {answer && <AnswerPanel
              answer={answer}
              openEvidence={openEvidence}
              setOpenEvidence={setOpenEvidence}
              onRunPrompt={(qid) => runQuery({ queryId: qid })}
            />}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

function AnswerPanel({ answer, openEvidence, setOpenEvidence, onRunPrompt }) {
  // Refusal path — spec §7.1 layer-4.
  if (answer.refusal) {
    return (
      <Card className="border-amber-200 bg-amber-50">
        <CardHeader>
          <CardTitle className="text-amber-900 text-base flex items-center gap-2">
            <Info className="h-4 w-4" />
            Out of scope
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-amber-900">{answer.refusal}</p>
          <div className="space-y-2">
            {(answer.in_scope_capabilities || []).map((p) => (
              <button
                key={p.query_id}
                onClick={() => onRunPrompt(p.query_id)}
                className="block w-full text-left text-sm text-amber-900 hover:underline"
              >
                <span className="font-medium">{p.query_id}</span> &mdash; {p.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{answer.title}</CardTitle>
        {answer.notes && <p className="text-xs text-slate-500 mt-1">{answer.notes}</p>}
      </CardHeader>
      <CardContent className="space-y-3">
        {(answer.rows || []).length === 0 && (
          <p className="text-sm text-slate-500">No rows returned.</p>
        )}
        {(answer.rows || []).map((row, idx) => (
          <AnswerRow
            key={`${row.label}-${idx}`}
            row={row}
            isOpen={!!openEvidence[idx]}
            onToggleEvidence={() => setOpenEvidence((m) => ({ ...m, [idx]: !m[idx] }))}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function AnswerRow({ row, isOpen, onToggleEvidence }) {
  const chip = row.chip;
  return (
    <div className="rounded-md border border-slate-200 p-3 bg-white space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-sm font-medium text-slate-900">{row.label}</div>
          {row.value_display && (
            <div className="text-lg font-semibold text-slate-900">{row.value_display}</div>
          )}
        </div>
        {chip && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span><AssertionChip label={chip.label} color={chip.color} /></span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-xs">
              {chip.tooltip}
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      {/* Derived: show the arithmetic */}
      {row.derivation && (
        <div className="text-xs text-slate-600 font-mono bg-slate-50 px-2 py-1 rounded border border-slate-100">
          {row.derivation}
        </div>
      )}

      {/* Strategically attributed: render the constrained §7.3 prose verbatim */}
      {row.prose && (
        <p className="text-xs text-slate-700 leading-relaxed italic">{row.prose}</p>
      )}

      {/* Evidence list — collapsed by default */}
      {row.evidence && row.evidence.length > 0 && (
        <div>
          <button
            type="button"
            onClick={onToggleEvidence}
            className="text-xs text-indigo-700 hover:underline flex items-center gap-1"
          >
            <FileText className="h-3 w-3" />
            {isOpen ? 'Hide evidence' : `${row.evidence.length} source${row.evidence.length > 1 ? 's' : ''}`}
          </button>
          {isOpen && (
            <ul className="mt-2 space-y-2">
              {row.evidence.map((e, i) => (
                <li key={i} className="text-xs border-l-2 border-slate-200 pl-3 py-1">
                  <div className="text-slate-500">[{e.citation}]</div>
                  <div className="text-slate-800 italic">&ldquo;{e.quote_short}&rdquo;</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function AssertionChip({ label, color }) {
  // Amber border + amber text for strategically_attributed — visually distinct
  // per spec §7.4 (2). Default = subtle neutral.
  if (color === 'amber') {
    return (
      <Badge
        variant="outline"
        className="border-amber-400 bg-amber-50 text-amber-900 text-[10px] uppercase tracking-wide"
      >
        {label.replace(/_/g, ' ')}
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
      {label}
    </Badge>
  );
}
