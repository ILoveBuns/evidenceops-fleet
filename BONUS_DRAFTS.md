# Optional contribution drafts

These drafts prepare the two publication-based optional contributions without
claiming they have been published. Publication changes external state and must
be performed only with explicit authorization. Replace the placeholders only
after each URL is publicly accessible.

- Public build story: `ADD_PUBLIC_BUILD_STORY_URL`
- Public social post: `ADD_PUBLIC_SOCIAL_POST_URL`

## Public build story draft

### EvidenceOps Fleet: from observed GitHub CI to evidence-bound approval

I created this article for the purpose of entering the All Things Agentic
Hackathon.

Release and compliance work often lands on a small operations team carrying
enterprise-sized risk. Before an irreversible action, they have to reconcile a
commit, CI results, an artifact, and human approval across disconnected tools.
A fluent summary is not enough: one missing or contradictory receipt must stop
the workflow.

EvidenceOps Fleet is a governed multi-agent system for that narrow boundary. It
autonomously retrieves an observed GitHub commit and its CI state before its
intake agent structures evidence, its policy agent identifies omissions and
conflicts, its deterministic verifier binds the decision to a canonical SHA-256
digest, and its supervisor explains the result. Gemini can structure and
explain, but it cannot change the authoritative decision or digest.

The most important engineering choice was separating probabilistic reasoning
from authority. Raw reviewer labels and notes are hashed immediately. Gemini
receives only the persisted decision, digest, missing fields, conflicts, and
trace summaries. Human approval is stored as an idempotent receipt bound to the
same digest, so a changed evidence set cannot reuse an earlier approval.

Background execution also had to survive real delivery semantics. Firestore
stores durable operation receipts. Cloud Tasks uses deterministic per-attempt
task IDs: repeated dispatch of one attempt deduplicates, while a failed attempt
can advance safely. A transactional five-minute lease prevents overlapping
workers and permits recovery after a crash. The queue is bounded to five
attempts over fifteen minutes, and Firestore mode fails closed instead of
silently falling back to an in-process task.

To remove manual evidence copying, a fixed-host GitHub adapter fetches an exact
commit and its check runs. It forwards only the observed SHA, successful-check
summary, and source URLs. Missing, pending, or failed checks become missing
evidence; they are never converted into a success claim.

The agent catalog makes ownership and authority inspectable across departments.
Each specialist publishes its lifecycle, version, capabilities, approved
consumers, data classifications, and allowed regions. A cross-session memory
endpoint reconstructs only IDs, timestamps, statuses, and digests, explicitly
excluding raw evidence.

The project includes local and Google Cloud setup instructions, an architecture
diagram, automated tests, a public-deployment verifier, and a fail-closed
submission audit. Synthetic dashboard examples are clearly labeled; they are
not customer, revenue, or production evidence. Live-cloud claims are added only
after the verifier observes Cloud Run, Firestore, Cloud Tasks, and Gemini.

The lesson is simple: trustworthy agents need a narrow authority boundary more
than another chat surface. Durable state, deterministic policy, redaction,
idempotency, and evidence binding make autonomous work inspectable before it
becomes irreversible.

Repository: https://github.com/ILoveBuns/evidenceops-fleet

## Public social post draft

I built EvidenceOps Fleet for the All Things Agentic Hackathon: a governed
multi-agent workflow that fetches commit and CI evidence, fails closed on missing
or conflicting receipts, binds decisions to a canonical digest, and requires an
evidence-bound human approval before irreversible action.

Gemini explains; deterministic policy owns authority. Firestore, Cloud Tasks,
retry-safe execution leases, redacted cross-session memory, and a public
verification receipt make the action auditable rather than merely plausible.

Built for the small release and compliance teams carrying enterprise-sized
risk. Repository: https://github.com/ILoveBuns/evidenceops-fleet

#AllThingsAgenticHackathon
