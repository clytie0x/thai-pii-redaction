# AI4TH onboarding LINE chat notes

Observed: 2026-08-16 (Asia/Bangkok)

Source: the LINE group `AI4TH Onboarding (Deployment)`, read from the earliest
message the desktop client made available through the latest visible message.
The accessible range began on 2026-07-24 and ended on 2026-08-15. LINE showed
the final day's divider as `เมื่อวาน` (yesterday) on the 2026-08-16 observation.

## Evidence boundary

This is a read-only observation log of third-party chat content. It is not an
official specification and does not override the Participant Guide, the
deployment form, repository contracts, or a later organizer announcement.
Links and attachments were not opened, files were not downloaded, and no LINE
message was sent. Personal email addresses, GitLab user IDs, API keys,
passwords, and test credentials have deliberately been omitted.

Accounts were presented in the group as organizer or NECTEC staff accounts,
but their identities were not independently authenticated during this
read-only observation.

The 2026 dates below are inferred from the repository/event calendar and the
current observation date. LINE displayed only day and month in the observed
history.

## Current action items reported in the chat

| Item | Chat-reported requirement | Interpreted calendar time | Confidence |
|---|---|---:|---|
| Deployment checklist | Complete eight items with explanations and image or file evidence. Completed items may be submitted first and the remainder updated later. | Organizer wording: “midnight Monday,” associated with 2026-08-17. The exact instant is unconfirmed; submit earlier rather than relying on an interpretation. | Message from an account presented as organizer staff; exact form contents were not opened |
| Test access | If the deployed product requires access control, put a dedicated evaluation credential in the Google Form for the technical committee's initial check. The organizer used generic user/password wording. | With the deployment checklist | Direct organizer reply |
| Presentation slides | Submit no later than Tuesday evening. | 2026-08-18 evening; no exact clock time was stated | Direct organizer reply |
| Pitch | Present as an on-stage pitch. The duration stated in chat was seven minutes. | 2026-08-19 | Direct organizer replies |
| Booth | No booth is planned because of space constraints. | Event day | Direct organizer reply |
| Equipment/setup arrival | Venue staff were still coordinating when teams could enter and prepare equipment. | Not confirmed in the observed messages | Explicitly provisional |

The pinned announcement at the top of the group repeats the eight-item
deployment-checklist request, asks teams to attach detailed evidence, permits
incremental updates, and directs blocked teams to contact the technical team.
The form link was visible in the chat but was not opened or validated during
this read-only review.

Before supplying test access, validate the form destination through a trusted
organizer channel. Never place a production credential in the form,
repository, chat, or screenshot, and rotate or revoke the evaluation
credential afterward. AI Guard has no per-user account or role model; its
bounded mechanism is a shared access-code gate. For evaluation, generate a
separate shared evaluation access code and rotate it after the review instead
of inventing a user-account or least-privilege capability.

## Chronological notes

### 2026-07-24 to 2026-07-26: accounts and GitLab access

- Organizer staff sent or resent GitLab/onboarding invitations to team
  coordinators. Several teams reported missing mail, expired initial reset
  links, or a coordinator address mismatch.
- Teams were initially given one GitLab user and could request additional users.
- A team that received a 404 under the expected hackathon namespace first
  needed membership in its team group. Once access was added, the team could
  create its own repository inside that group.
- The chat consistently treated the coordinator email from the application
  form as the primary delivery address.

### 2026-07-25 to 2026-07-27: guides and model access

- Organizer staff said the installation guide and Pathumma LLM usage survey
  had been emailed to coordinators.
- Pathumma keys for text, ASR, and TTS were reported as sent by email. The
  service was described as OpenAI-compatible.
- The chat confirmed the model names `ptm-tts-1` and `ptm-asr-1` and provided
  examples using:
  - `https://tokenmind.pathumma.in.th/v1/audio/speech` for TTS;
  - `https://tokenmind.pathumma.in.th/v1/audio/transcriptions` for ASR.
- A TTS example used voice `pop`, WAV output, and bearer authentication. An ASR
  example used a file upload, Thai language selection, and JSON output.
- No credential value from the chat is recorded here.

### 2026-08-05 to 2026-08-06: deployment route

- More missing GitLab invitations were checked and resent. Participants were
  directed to join the assigned group and then create their repository.
- The public team route was stated as
  `https://teamXX.aiforthai.in.th/`, replacing `XX` with the team number.
- Organizer staff said each team had assigned ports and that exposing the
  assigned port mapped the service to the public route.
- A Participant Guide hosted in Notion was shared, with deployment information
  under its third topic.

### 2026-08-09 to 2026-08-12: product shape, GPU, and event format

- A participant asked whether the deployment could be an application. Staff
  clarified whether it was a web application and whether it also exposed an
  API; the observed thread does not establish a new universal requirement from
  that exchange.
- Teams intending to use GPU capacity were directed to a GPU Guide and warned
  to read its usage limits. One participant reported a 4 GB VRAM need.
- A participant asked whether a different TTS provider could be used. Staff
  replied that it was allowed, but the committee might ask why because AI-model
  usage contributed to evaluation.
- The presentation format was confirmed as an on-stage pitch. Venue access for
  equipment preparation remained under coordination.
- Organizer staff said a deployment-status form would collect technical
  information for the judging committee and asked blocked teams to contact the
  technical team.

### 2026-08-14 to 2026-08-15: checklist, access recovery, and test evidence

- The organizer posted the eight-item deployment checklist and Monday-midnight
  cut-off, allowing incremental completion.
- A participant asking about a booth was told there would be no booth because
  of space constraints.
- One team reported its application working completely, then needed help
  finding its team number and GitLab group. Staff identified the team, added
  group access, and confirmed that the participant could create the repository
  inside the assigned team group.
- `Dozzle` was shared as a container log viewer. The same team later reported
  that its backend had passed and that it was moving on to log and frontend
  checks.
- In response to a testing question, organizer staff used generic
  user/password wording and said test access should be supplied in the Google
  Form so the technical committee could perform an initial inspection. For AI
  Guard, this maps to a separately generated shared evaluation access code,
  not a per-user account.
- On 2026-08-15, the latest visible exchange restated the deadlines:
  deployment evidence by Monday midnight, presentation slides by Tuesday
  evening, and unfinished checklist items updated by Monday midnight.

## Items not established by this observation

- The exact contents, validation rules, or submission state of the Google Form.
- An exact Tuesday slide-submission clock time beyond "Tuesday evening."
- Final venue access/setup time, rehearsal arrangements, or a replacement for
  the cancelled booth.
- Whether messages older than 2026-07-24 exist but were unavailable in this
  LINE client.
- Whether any organizer requirement changed after the latest visible
  2026-08-15 message.

Before acting on a deadline-sensitive or platform-sensitive item, verify the
pinned announcement, Participant Guide, and deployment form directly through
the authorized organizer channel.
