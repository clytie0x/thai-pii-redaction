# YRSS evaluation v2: methods, results and synthesis

Every number here is read from the run files in this folder
(`test-nonllm.json`, `test-llm-typhoon4b-seed{1..5}.json`, and the `dev-*.json`
files for dev-only context). The protocol and its addenda are in
`docs/decisions/2026-11-13-yrss-eval-v2.md`; citation limits are in
`research/yrss2026/CLAIM-MAP.md`.

## 1. Questions

- **Q1.** How well does AI Guard find Thai personal data in documents it was
  not developed on?
- **Q2.** Is the hybrid design better than rules alone, NER alone, an existing
  PII tool, and a local LLM?
- **Q3.** Does each detection layer earn its place?

## 2. Design

| Step | What was done |
|---|---|
| Pre-registration | Questions, 11-type scheme, metric (entity F2), family bootstrap, Holm correction and comparators written down before any data. |
| Development | 300 dev documents (100 families × 3) used to find and fix detector faults. Dev numbers are never reported as accuracy. |
| Freeze | Detector frozen and its content hash recorded (`pii_redactor/` tree `2860184`) before any test document existed. |
| Test authoring | 200 template families × 4 variants = 800 documents, written by two AI model families (Claude Sonnet, DeepSeek V4 Pro) from the annotation guide only, then reviewed by the other family under fix-only rules. Both reviewers fixed 9 of 9 planted faults in a check set. |
| Sealing | Templates hashed and encrypted; the plain draft was deleted. |
| Scoring | Every system scored once on the sealed split. The LLM comparator used five seeds; its requests ran on a Colab L4 GPU into cache files, and scoring ran locally from those files. |

**Metric.** Entity-level micro F2 (recall weighted twice), type-aware overlap
matching, unrestricted "all" view as primary. Intervals are 95% percentile
intervals from 1,000 bootstrap resamples of whole template families (seed 0),
because the 4 variants of a family share wording. Paired differences use the
same resamples; Holm correction over the five registered comparisons.

## 3. Data

| Property | Value |
|---|---|
| Documents | 800 (200 families), 160 negative documents with look-alike values only |
| Entities | 2,168 across 11 types; every type ≥ 180 entities from ≥ 45 families (NAME 316 from 73) |
| Genres | 18 genres, 44 to 48 documents each |
| Values | Generated; Thai ID and card numbers pass their checksums; decoys (bad-checksum 13-digit numbers, order codes, tracking codes) in negatives |

**Is it enough?** For the headline it is: the all-view F2 interval is ±0.014,
every non-LLM comparator gap is more than 30 times that, and the Typhoon gap
(+0.031 to +0.041) is still clear of zero in every seed. Per type, a recall of
1.000 on 180 entities has a 95% Wilson lower bound near 0.98, but variants of a
family are not independent, so the real lower bound is lower; per-type rows
are descriptive. The data are synthetic and AI-written, so they show how the
detector behaves on constructed Thai documents, not on real ones.

## 4. Systems

| System | What it is |
|---|---|
| AI Guard | Format and checksum rules, PyThaiNLP thainer CRF, Thai context rules, span merging (frozen) |
| Regex | Cue-and-pattern baseline with a licence pattern |
| PyThaiNLP CRF NER | thainer CRF alone, mapped tags only |
| WangchanBERTa NER | PyThaiNLP thainer-v2 (WangchanBERTa), mapped tags only; long documents tagged in pieces |
| Presidio | presidio-analyzer 2.2.360 with spaCy en_core_web_sm 3.8.0 |
| Typhoon 2.1 4B | `scb10x/typhoon2.1-gemma3-4b`, Q4_K_M, Ollama 0.40.16, digest `8cfab909…`, five seeds, prompt `yrss-v2-llm-openai-1` |

## 5. Results

### Q1. AI Guard on the sealed test set

| View | P | R | F1 | F2 [95% CI] |
|---|---:|---:|---:|---:|
| All 11 types (primary) | 0.703 | 0.990 | 0.822 | 0.916 [0.901, 0.929] |
| Structured (8 types) | | | | 0.993 |
| Contextual (name, address, birth date) | | | | 0.912 |

Recall is 1.000 on 8 of 11 types. Of 2,168 entities, 21 were missed: 16 names
(300/316), 4 birth dates (180/184) and 1 plate (183/184). Of 906 false
positives, 615 are labels outside the 11 types (dates, places, organisations,
reference numbers); without them precision would be 0.881. Only 4 of 160
negative documents came back untouched. Median 6.9 ms per document on a laptop
CPU.

### Q2. Against the comparators (same 800 documents)

| System | P | R | F2 [95% CI] | Structured F2 | Contextual F2 | Clean negatives /160 | p50 per doc |
|---|---:|---:|---:|---:|---:|---:|---:|
| **AI Guard** | 0.703 | 0.990 | **0.916** [0.901, 0.929] | 0.993 | 0.912 | 4 | 6.9 ms |
| Typhoon 2.1 4B (mean of 5 seeds, range) | 0.762 | 0.916 | 0.881 (0.874 to 0.885) | 0.891 | 0.902 | 10 to 19 | about 7 s (GPU, shared) |
| Presidio | 0.387 | 0.499 | 0.472 [0.440, 0.506] | 0.689 | 0.187 | 11 | 8.2 ms |
| Regex | 0.972 | 0.389 | 0.442 [0.407, 0.478] | 0.556 | 0.181 | 156 | <0.1 ms |
| WangchanBERTa NER | 0.149 | 0.314 | 0.257 [0.231, 0.283] | 0.241 | 0.461 | 1 | 81.0 ms |
| PyThaiNLP CRF NER | 0.157 | 0.125 | 0.131 [0.108, 0.152] | 0.008 | 0.412 | 56 | 2.6 ms |

Typhoon 2.1 4B entity-level micro F1 is 0.832 (seed range 0.825 to 0.837).
That figure is the arithmetic mean of the five per-seed F1 values in
`systems.llm.views.all`, the same field as the AI Guard row.

Paired F2 difference, AI Guard minus comparator (family bootstrap):

| Comparator | All | Structured | Contextual |
|---|---:|---:|---:|
| Typhoon 2.1 4B (5 seeds) | +0.031 to +0.041; every CI above zero (lowest bound +0.013) | +0.097 to +0.110 | +0.008 to +0.012; every CI spans zero |
| Presidio | +0.444 [0.408, 0.477] | +0.304 | +0.725 |
| Regex | +0.473 [0.433, 0.511] | +0.437 | +0.732 |
| WangchanBERTa NER | +0.659 [0.629, 0.688] | +0.752 | +0.451 |
| PyThaiNLP CRF NER | +0.785 [0.758, 0.812] | +0.985 | +0.500 |

Every bootstrap p is at the floor (1/1001). The run files store a four-way
Holm (0.004) for the non-LLM runs and none that spans both runs; recomputed
over the five registered comparisons (the LLM entered with its largest p over
the five seeds), Holm gives 5 × 0.000999 = 0.005 for all five.

Typhoon ran on a Colab L4 GPU with five seeds sharing it, so its time per
document is not single-user latency (one stream on the laptop CPU took a mean
of 18.2 s per document in a six-document dev smoke run); either way it is seconds, against milliseconds for
AI Guard on a laptop CPU. In seed 1 its weakest types were card
numbers (recall 0.745) and Thai IDs (0.870); AI Guard found every one of both.

### Q3. Layer ablations

| Removed layer | F2 | ΔF2 [95% CI] | What changes |
|---|---:|---:|---|
| Format and checksum rules | 0.385 | −0.531 [−0.562, −0.500] | Structured F2 falls from 0.993 to 0.216 |
| Thai context rules | 0.846 | −0.069 [−0.089, −0.050] | Contextual F2 falls from 0.912 to 0.589; precision rises to 0.825 |
| Address merging | 0.835 | −0.081 [−0.098, −0.064] | Address fragments become extra false positives (906 → 1,990); precision falls to 0.518 |

## 6. Synthesis

1. **The two halves cover each other.** Rules alone are precise but blind to
   names (regex contextual F2 0.181); NER alone sees some names but cannot
   label IDs (CRF structured F2 0.008). Combined, AI Guard reaches 0.993 on
   structured and 0.912 on contextual types. The ablations show the same
   thing from the inside: each layer removed costs F2, and each costs it in
   the group it was built for.
2. **AI Guard is built for recall, and the test shows it.** Recall 0.990 with
   precision 0.703: the system would rather mask a date or a place than leak a
   name. That is a design choice (kept on 2026-11-14), and its cost is visible:
   4 of 160 negative documents are untouched, against 156 for regex.
3. **Generic tools do not transfer to Thai.** Presidio's English NLP finds
   almost no Thai names (contextual F2 0.187), and the Thai NER models alone
   find names but not identifiers.
4. **A small Thai LLM is the closest competitor, and the gap is in IDs.**
   Typhoon 2.1 4B reaches F2 0.881 (five-seed mean), far above the other
   tools, and AI Guard's lead over it (+0.031 to +0.041) is real but small.
   The lead comes almost entirely from structured identifiers (+0.10), where
   checksums and fixed formats beat a language model that misreads or drops
   long digit strings. On names, addresses and birth dates the two are level:
   every interval spans zero, so no difference is shown. The LLM is more
   precise (0.762 against 0.703) and leaves more negative documents untouched
   (10 to 19 against 4), but it misses about 8% of personal data against
   AI Guard's 1%, and it needs a GPU and seconds per document.
5. **Speed and deployment.** AI Guard needs no GPU and no network and runs in
   milliseconds, which is what makes on-device masking before an AI request
   practical.

## 7. Limits and threats to validity

- Synthetic, AI-written documents; not real-document accuracy.
- Human review of 80 test docs (10%): AI pre-annotation reviewed by the first author; agreement with gold κ = 1.00 (not an independent annotator). Source: `research/yrss2026/v2/results/human-check-report.json`.
- independent inter-annotator agreement: NOT claimed.
- The test authors are AI models; their style may differ from real users.
  Two families and a cross-review reduce, but do not remove, this risk.
- The precision figure depends on the product's choice to mask generic
  labels; the shared-11 view (F2 0.966) shows the effect of that choice.
- Per-type intervals ignore within-family dependence and are optimistic.
- Hosted LLMs (gpt-6-luna, psu-gemma) were only run on dev, where they matched
  or beat AI Guard (dev F2 0.954 and 0.994) at about 1 to 4 s per document;
  they were not scored on the test set, so no test claim is made about them.
