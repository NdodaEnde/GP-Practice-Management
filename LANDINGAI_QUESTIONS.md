# Questions for the LandingAI team

Running list of things to raise on the next call. Add as they come up.

## Extraction latency & 504s on `/v1/ade/extract`

**Observed (dev, May 2026):** the `parse` step is consistently fast, but the
`extract` step (`POST /v1/ade/extract`, rich one-call schema) frequently returns
**HTTP 504 Gateway Timeout**, and the SDK then auto-retries. On a 3-page GP
patient file we've seen total processing times swing from **~110s to ~530s
(~9 min)** purely because of these 504 + retry cycles. The parse itself and the
eventual extract response are fine — it's the gateway timing out before the
extract completes, then succeeding on retry.

**Questions:**
1. Is the 504 on `/v1/ade/extract` expected under normal load, or a sign we're
   doing something wrong (payload size, schema complexity, region)?
2. What is the **expected/SLA latency** for `extract` with a rich (~13-section)
   schema on a 3–6 page document? Is there a documented timeout we should design
   around?
3. Is there a **synchronous timeout ceiling** on the gateway we keep hitting?
   Should we be using an **async / job-based extract API** (submit → poll) for
   multi-page documents instead of the synchronous call?
4. Does **schema size** (number of fields / nesting) materially affect extract
   latency? Would splitting into smaller schemas be faster or slower overall?
5. Any **region / endpoint** (`api.va.landing.ai`) considerations — is there a
   closer or higher-capacity endpoint for production traffic from South Africa?
6. Recommended **client retry/backoff** config, and do retries count against
   our **rate limits / billing** (i.e., are we charged per attempt or per
   successful extract)?
7. For production scale (many concurrent docs), what **throughput / concurrency**
   should we plan for, and is there a batch extract API?

**Why it matters for us:** doctors validate scanned records right after upload;
a 9-minute extract is a poor UX. We've added our own retry backstop, but we need
to know the realistic latency envelope to set user expectations (and decide
whether to move to an async submit-and-poll model).
