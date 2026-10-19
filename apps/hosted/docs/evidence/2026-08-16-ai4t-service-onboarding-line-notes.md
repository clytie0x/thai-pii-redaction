# AI4T Service Onboarding LINE chat notes

Observed: 2026-08-16 (Asia/Bangkok)

Source: the LINE group `AI4T Service Onboarding`, read from the earliest item
the desktop client made available through the latest visible item. The
accessible range began on 2026-07-18 and ended on 2026-08-14. The earliest
items were membership and room-image events; the first substantive exchange
observed was on 2026-07-21. The latest substantive message observed was on
2026-08-11, followed by a member-join event on 2026-08-14.

## Evidence boundary

This is a read-only observation log of third-party chat content. It is not an
official specification and does not override the Participant Guide, event
agenda, submission form, repository contracts, or a later organizer
announcement. Links, QR codes, and attachments were not opened; files were not
downloaded; and no LINE message, reaction, or other state-changing action was
sent.

Personal names, schools, team names, team-level headcounts, email addresses,
phone numbers, access codes, QR payloads, API keys, and service credentials
have deliberately been omitted. Accounts were presented in the room as
organizer or NECTEC staff accounts, but their identities were not independently
authenticated during this observation.

The 2026 dates below are inferred from the repository/event calendar and the
2026-08-16 observation date. LINE displayed only day and month in the observed
history.

This room is separate from `AI4TH Onboarding (Deployment)`. Deployment-form,
GitLab, public-route, slide-deadline, and seven-minute-pitch observations from
that other room are recorded in
`docs/evidence/2026-08-16-ai4th-onboarding-line-notes.md`.

## Event and attendance facts reported in the room

| Item | Chat-reported information | Confidence or limitation |
|---|---|---|
| Technical workshop | The `AI Service Deployment for the AI for Thai platform` hands-on workshop was scheduled for 2026-07-22, 17:00-19:00, online. Participants were asked to check in and have every team listen. | Message from an account presented as organizer staff; meeting and onboarding links were not opened |
| Who should attend the workshop | Everyone was welcome if convenient; otherwise at least one member able to develop should attend. | Reply from an account presented as organizer staff |
| Final event | 2026-08-19 at the Mandarin Grand Ballroom, Mandarin Hotel Bangkok. Registration/check-in and presentation-order allocation were stated as 08:30-09:00. | Messages from accounts presented as organizer staff; the map link was not opened |
| Final system state | Staff said the system must be usable and that the presentation would be used by judges for scoring. | Reply from an account presented as organizer staff; this room did not state a presentation duration |
| Travel and accommodation | Staff first said support was still being discussed, then stated on 2026-07-27 that the competition budget did not cover contestant travel or accommodation. | Latest visible answer from an account presented as organizer staff; confirm that the policy has not changed |
| Invitation letters | Named attendance letters were offered for participants who needed to notify a school or affiliation. Roster details were requested by 2026-08-06; after that, staff warned that a letter might not name individual people. On 2026-08-07, letters were reported sent to the first-listed coordinator for each team. | Messages from accounts presented as organizer staff; delivery was handled by email and was not independently verified |
| Prize paperwork | Each team was asked to have one representative on 2026-08-19 with an original national ID and a bank-account book for receiving prize money. Staff clarified that the account should belong to the person receiving the money and replied that a copy could be used when a physical account book was unavailable. | Replies from an account presented as organizer staff; confirm the current requirement and safe handling of sensitive documents through an authorized organizer channel before the event |

The room also contained links or QR codes for the online meeting, onboarding,
venue map, and event forms. They are intentionally not reproduced here because
they were not opened or authenticated and some functioned as access material.

## Technical service report observed on 2026-08-05

A participant reported testing the supplied OpenAI-compatible service. This
was a participant report, not a test performed during this observation:

- `GET /v1/models` returned HTTP 200 and listed `thailm-8b`, `ptm-asr-1`, and
  `ptm-tts-1`.
- `POST /v1/chat/completions` with `thailm-8b` returned HTTP 200 and generated
  Thai responses. The reporter therefore believed the base URL and credential
  were accepted.
- `POST /v1/audio/transcriptions` with `ptm-asr-1` returned HTTP 500 with a
  `litellm.InternalServerError` that named the `ptm-asr-1` model group.
- `POST /v1/audio/speech` with `ptm-tts-1` also returned HTTP 500. The reporter
  tried input-only, input plus voice, and input plus voice and response format.
- The ASR and TTS calls were each retried four times with exponential backoff
  and continued to fail. The participant inferred a server-side deployment or
  model-group problem because the responses were 5xx rather than request-level
  4xx errors, and asked the backend operator to inspect them.

No organizer resolution to that ASR/TTS report was visible in the observed
history. It does not establish the current service state and must not replace a
fresh acceptance test. No base URL, API key, request credential, or user data
from the report is recorded here.

## Chronological notes

### 2026-07-18 to 2026-07-20: room setup

- The earliest accessible items were members and staff joining the room.
- Staff changed the room image on 2026-07-20.
- No substantive instruction was visible before 2026-07-21.

### 2026-07-21 to 2026-07-22: workshop coordination

- A participant asked whether the technical meeting ran from 15:00 to 19:00;
  staff corrected the start time to 17:00.
- Staff said all members could attend, but at minimum a member capable of
  development should represent the team.
- An agenda image was shared. The room then carried the 2026-07-22 workshop
  announcement, check-in request, meeting access, and onboarding QR/form.
- Teams were asked to have a representative submit the requested details.
- A participant asked what was in or out of scope. No answer to that question
  was visible in the observed history.

### 2026-07-23 to 2026-07-30: event support and official letters

- Participants asked whether the 2026-08-19 final event included travel or
  accommodation support. Staff first described the matter as pending budget
  discussion. The latest visible answer, on 2026-07-27, said that neither
  expense was covered; the current policy still needs confirmation.
- A participant requested an official project or invitation letter because
  the final event fell on a school day. Staff later confirmed that letters
  could be prepared for people who needed to notify their affiliation.

### 2026-08-03 to 2026-08-04: final-day logistics

- Staff identified the Mandarin Grand Ballroom at the Mandarin Hotel Bangkok
  as the venue and stated an 08:30-09:00 registration/check-in period for
  reporting attendance and determining presentation order.
- A participant asked whether the final was a pitch or a live system
  operation. Staff later answered that the system needed to be usable and that
  the presentation was for judging.

### 2026-08-05: provider testing

- The participant report described the successful models and chat-completion
  checks, and the repeated ASR/TTS HTTP 500 failures summarized above.
- No follow-up resolution was visible in this room.

### 2026-08-06 to 2026-08-07: rosters, letters, and prize documents

- Staff collected names and contact details for named invitation letters. The
  latest consolidated roster visible in the room reported ten teams and 36
  participants. Team and individual breakdowns are intentionally omitted.
- Staff warned that individually named letters could not be guaranteed after
  the roster cut-off.
- Staff posted the one-representative prize-document requirement and clarified
  the recipient-account and copy questions recorded above.
- On 2026-08-07, staff said invitation letters had been emailed to the first
  listed coordinator for each team. One team reported missing mail, supplied
  an alternate address, and staff confirmed a resend. The address is omitted.

### 2026-08-11 to 2026-08-14: unresolved delivery question

- A participant asked what form, properties, and purpose the Git deliverable
  should have and requested a document describing it.
- No reply to that question was visible before the latest accessible event, a
  member joining the room on 2026-08-14.

## Items not established by this observation

- The answer to the 2026-07-22 scope-and-limits question.
- The required Git repository shape, properties, documentation, or delivery
  objective asked about on 2026-08-11.
- Any organizer resolution of the 2026-08-05 ASR/TTS HTTP 500 report.
- A final event agenda beyond the venue, 08:30-09:00 registration, working
  system requirement, and presentation-for-scoring statement.
- Whether messages older than 2026-07-18 exist but were unavailable in this
  LINE client.
- Whether any requirement changed after the latest visible 2026-08-14 event.

Before acting on a deadline-sensitive, deliverable-sensitive, financial, or
platform-sensitive item, verify the current Participant Guide, submission
form, event agenda, and an authorized organizer announcement directly.
