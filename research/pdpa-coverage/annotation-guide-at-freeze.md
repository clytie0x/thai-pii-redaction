# PDPA context corpus annotation guide

Independently author fictional Thai/English/mixed documents. Do not inspect
detectors, prototypes, old gold/blind data, results or developer examples.
No real people, contact details or medical/genetic records are sourced.

Canonical sensitive categories: RACE, ETHNICITY, POLITICAL_OPINION, BELIEF,
SEXUAL_BEHAVIOR, CRIMINAL_RECORD, HEALTH, DISABILITY, LABOR_UNION, GENETIC_DATA,
BIOMETRIC_IDENTITY. BELIEF covers cult/doctrine, religion and philosophy.
Nationality alone is not race/ethnicity. Gender alone is not sexual behaviour.
Biometric identity requires technical identification-related context; an
ordinary photograph or audio clip is general media, not automatically sensitive.
Genetic testing results/data differ from a general biology article.

General families (navigation groups, not a statutory exhaustive list): IDENTITY,
CONTACT, LOCATION, FINANCIAL, EDUCATION, EMPLOYMENT, ONLINE, ACTIVITY,
RELATIONSHIPS, MEDIA, QUASI_IDENTIFIERS. Identity means explicit personal
identifiers, not every pronoun. Online includes attributable IP/MAC/device/
cookie/account IDs; location/behaviour alone needs linkage context. Combinations
can indirectly identify. Do not equate a company with a natural person.

One UTF-8 JSON object per physical LF line:
`{doc_id,family_id,split,scope,text,targets,modality}`.
`targets` is a list of `{category,attribution}`. Attribution is `personal`,
`topic` or `ambiguous`. Scope is `sensitive`, `general` or `modality`.
Modality is `text`, `image`, `audio`, `video` or `genetic_binary`.

Personal: an explicit/linked assertion about an identifiable or potentially
identifiable subject (including speaker, pseudonymous record, indirect linkage).
Negative tests, historical assertions and quotes can remain personal: annotate
what information concerns whom, not whether it is affirmative or true.
Topic: generic/academic/public-policy discussion without personal attribution.
Ambiguous: context genuinely does not settle linkage/attribution. Do not decide
from stereotypes, institutional names, nationality, attendance or model guesses.

Annotate every explicit category within the declared scope. General identifiers
in sensitive documents are outside that record's scored scope (they will be
assessed but not claimed independently adjudicated by this label set). Use the
narrow explicit statutory type; do not infer HEALTH for every GENETIC_DATA or
DISABILITY mention unless another health assertion is explicitly present.
Different categories in a document can have different attribution states.

Composition: sensitive16 records per category =176. Per category8personal,
5topic,3ambiguous. Calibration4 =2personal/1topic/1ambiguous; evaluation12 =
6personal/4topic/2ambiguous. General8 per family =88:4personal/2topic/2ambiguous;
calibration2 =1personal/1topic; evaluation6 =3personal/1topic/2ambiguous.
Raw modalities4 records each for image/audio/video/genetic_binary =16:
one calibration and three evaluation each, empty targets, scope modality.
Total280, calibration70, evaluation210. Modality cases describe fictional raw
payloads but do not contain or generate actual media/biological data.

No paraphrase or shared template/value family crosses splits; family_id makes
this auditable. Prefer one family per independently written document. Minimum
diversity: fields, first-person prose, roles/record references, negation, quotes,
history, general education, multiple subjects, indirect linkage, mixed language,
and some formatting noise. Avoid formulaic negative disclaimers, a diagnostic
keyword in every positive, or global keyword negation as a shortcut. Evaluation
must be harder than simply copying synonym lists. Use truthful fictional
within-document ground truth; do not rewrite difficult cases after detector runs.

Independent reviewer checks every document against this guide, corrects only
annotation/rule violations, reports aggregate edit reasons and label counts.
Neither author nor reviewer runs detectors. Preserve original drafts externally.
Final evaluation text and key never enter developer context or ordinary logs.
