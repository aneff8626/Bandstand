# How Bandstand learns across participants

## Three data paths

**Private local learning:** Each installation keeps continuous EEG, typing/edit events, text, semantic embeddings, questionnaire answers and personal checkpoints in its private application-data directory. The writing model learns cumulatively within that participant. Session boundaries, acquisition schema and time-block evaluation splits are retained. The public text encoder is fixed; it runs locally. A user's text must never become a shared retrieval library.

**Opt-in ERP sharing:** Supabase Auth identifies the account. Versioned consent and row-level policies authorize numeric ERP uploads through bounded RPCs. The outbox retries safely and records delivery. Share only the declared numeric data and protocol metadata; exclude participant names and typed answers. Keep the ability to withdraw, cancel queued uploads and delete owned records. EEG should not be described as inherently anonymous.

**Protected writing-model learning:** Clients download the same signed model/round manifest, train a bounded local update, clip it and participate in secure aggregation. The coordinator receives masked protocol messages and releases only a sufficiently large cohort aggregate under an agreed privacy mechanism. Raw text, EEG, embeddings and individual plaintext updates are never uploaded. Downloaded models initialize a shared prior; personal adaptation stays local. A complex temporal model can replace the current small baseline under a new schema without changing these privacy boundaries.

## What runs where

| Component | Location | Stored data |
|---|---|---|
| Acquisition, encoder, personal training | Participant desktop | EEG, text, embeddings, private model, local split membership |
| Accounts, consent, ERP API | Supabase | Account identities, consent receipts, opted-in ERP records |
| Round registry and model registry | Supabase | Public protocol/model hashes, lifecycle state, aggregate release metadata, signed aggregate artifacts |
| Secure aggregation coordinator | Separate always-on compute service | Short-lived masked round messages; no plaintext individual-update inbox |
| Model release signer | Controlled release environment | Private signing key, aggregate validation and signing workflow |

Supabase remains the database/auth/storage system. A persistent aggregation process needs separate compute; a university-managed host is a plausible pilot home if access, administration and TLS are available. Great Lakes access/hosting suitability is not verified. Do not promise a permanently free service or use a sleeping free web service for multi-party rounds without testing reconnection and deadlines.

## Round contract and release gates

1. Publish immutable model hash, encoder revision, feature schema, learning parameters, clipping/noise mechanism, cohort floor, deadline and privacy cost. Every client verifies it and rejects replays or incompatible models.
2. Authenticate distinct enrolled contributors and check specific current consent. An announced cohort count alone does not protect against coordinator-created fake clients; membership and non-collusion assumptions need review.
3. Train in a separate low-priority process with a resource deadline; acquisition and autosave continue. At most one contribution per participant per round. No contribution is sent to the ordinary ERP endpoint.
4. Run the reviewed secure-aggregation protocol; abort undersized/dropout rounds. Persist only what is required for recovery, with a short retention period and no body logging.
5. Enforce a participant-level privacy budget across rounds. The current Gaussian simulation is not a deployed DP guarantee; quantization, honest contributor count, collusion and poisoning are unresolved.
6. Evaluate aggregate candidates on held-out participants, against no-EEG/time/context baselines. Publish only signed, compatible versions with evaluation metadata; retain rollback.
7. Withdrawal prevents future participation. Deleting an account removes identifiable server records; it does not automatically undo influence in previously released models. State that clearly.

## Implementation status

PR #1 supplies numeric update serialization, isolated training, signed model validation and a Flower SecAgg+ synthetic rehearsal. The app does not call a real upload transport and trusts no model-signing keys yet. This is useful groundwork, not a finished federation deployment. There must be no UI claim that opting in currently improves the global decoder.

Next deployable increment: staging round/consent registry plus synthetic-only coordinator; test restart/dropout/replay and two-account authorization. Next: independent review of cohort authentication, privacy mechanism and poisoned clients, establish signed-release trust, then an explicitly consented limited pilot. Only after those gates should production contribution controls become active.
