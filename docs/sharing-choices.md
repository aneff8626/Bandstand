# Sharing choices

The versioned choices are:
- Keep everything on this device.
- Everything but typing.
- Everything, including typing decoder.

Existing ERP permission is not upgraded to blanket sharing. The new choice must be selected explicitly. Selecting an option and pressing Save records consent to its displayed scope and risk notice; there is no second checkbox.

## Writing boundary

Writing, semantic embeddings and decoder EEG remain local. Local training uses these records to improve an EEG-to-semantic model. The planned shared contribution is a masked model update, not masked embeddings or text. Secure aggregation should reveal only a group update; participant-level differential privacy should limit participant disclosure. Neither mechanism is currently enabled, and neither offers an absolute anonymity guarantee. The inclusive choice records a preference until the implemented protections are reviewed and the participant confirms activation.

## Current capability

Only allowlisted ERP trials upload today. The broader labels do not turn on nonexistent transports. Other experiments, questionnaires and decoder contributions remain local. Non-typing responses can still be sensitive. No current uploader reads arbitrary participant files.

Preferences are stored locally and, when signed in, in Supabase account metadata. ERP uploads additionally require the existing server-side ERP consent. Saving “Keep everything on this device” withdraws ERP consent and cancels pending uploads; previously shared copies have a separate deletion action. Passwords and authentication tokens are never research contributions.

The app continues to use its strict numeric ERP payload allowlist and has no decoder-upload endpoint. Do not implement a generic file uploader under these broad labels.
