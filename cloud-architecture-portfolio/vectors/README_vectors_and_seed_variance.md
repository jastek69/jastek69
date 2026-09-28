# vectors.py and seed_variance.py

Two standalone tools. One teaches the mathematics behind embeddings and
optimization; the other measures how strongly a prompt constrains its output.
They share no code — they are together because the second is what the first is
for.

| | |
| --- | --- |
| `vectors.py` | Eleven lessons. Every numeric claim is verified in front of you, not asserted |
| `seed_variance.py` | Generate N samples from one prompt at N seeds, measure how much they disagree |

---

# Install

## vectors.py

```bash
pip install numpy matplotlib
```

That is all that is required. Two lessons use optional packages and degrade
cleanly without them:

- `hvp` uses `torch` for the autograd version of Pearlmutter's trick; without
  it, the same identity is demonstrated with finite differences.
- `polarity` uses `sentence-transformers` to recompute its numbers live;
  without it, it runs on values measured from `all-MiniLM-L6-v2` and recorded
  in the file. The lesson is identical either way — only the provenance of the
  numbers changes.

```bash
pip install sentence-transformers        # optional: recompute polarity live
```

## seed_variance.py

```bash
pip install numpy pillow                 # required
pip install opencv-python                # motion direction — strongly recommended
pip install open_clip_torch              # semantic appearance — recommended
```

`ffmpeg` and `ffprobe` must be on PATH for video input.

Both optional packages degrade gracefully, but the fallbacks are much weaker:

| Missing | Fallback | Consequence |
| --- | --- | --- |
| `opencv-python` | Edge-spread proxy | Direction estimate is crude and easily fooled by smoke, fire, or camera moves |
| `open_clip_torch` | Downsampled pixel correlation | Sees layout and colour, not content. Inflated spread numbers on scenes with fire or moving backgrounds |

## Where to run them

**`vectors.py` belongs on your laptop.** No GPU, no models, and the slider
demos need a display. Nothing about it benefits from the instance.

**`seed_variance.py` belongs on the instance**, beside the outputs it reads.
Run it in ComfyUI's venv so torch and opencv are already there:

```bash
cd ~/ComfyUI && source venv/bin/activate
python3 ~/seed_variance.py analyze --clips output/video/*.mp4
```

Per the invariant, anything hand-installed on the instance dies with it. These
belong in the repo and arrive via `provision.sh` or `bootstrap.sh.tpl` like
everything else, not via `scp`.

---

# vectors.py

## Running lessons

```bash
python3 vectors.py lessons              # list them
python3 vectors.py run dot              # one lesson
python3 vectors.py run all              # all ten, in order
python3 vectors.py run hessian --save plots/    # write PNGs, no display needed
python3 vectors.py run cosine --interactive     # matplotlib sliders
```

`--save` switches matplotlib to the Agg backend, so `run all --save plots/`
works over SSH with no display at all.

## Interactive demos on a headless box

Three options, best first.

**1. Run it locally.** Copy the file to your own machine. Sliders just work.

**2. Serve it over an SSH tunnel.** Built in:

```bash
# on the instance
python3 vectors.py serve --port 8765

# from your machine
ssh -L 8765:localhost:8765 ubuntu@<instance>
# then open http://localhost:8765
```

Binds to `127.0.0.1` only — the tunnel is what carries it to you, so no
security group change and nothing exposed. The page is 7.4 KB, fully inline, no
CDN, so it works regardless of egress rules. Two demos: the cosine/tangent
slider, and an interactive Lie bracket where dragging η shows the two training
orders separating, with measured separation and η²·|bracket| side by side.

**3. X11 forwarding.** `ssh -X` plus XQuartz. Works, but a network round-trip
per slider frame makes it unpleasant.

## The lessons

Ordered so each builds on the last. Running them out of order works, but the
arc is deliberate.

| # | Lesson | What it establishes |
| --- | --- | --- |
| 1 | `vector` | A vector is a point. Normalizing discards length and keeps direction — which is why your stored embeddings live on a sphere |
| 2 | `dot` | Cosine **is** the dot product for unit vectors. No trigonometry, no division. This is why vector search is fast |
| 3 | `cosine` | Ranking needs a monotonic score. Cosine has one; tangent is disqualified by shape, not convention |
| 4 | `highdim` | At 1024 dimensions random vectors are nearly perpendicular, always. **Run this one first if you only run one** |
| 5 | `taylor` | Halve the step: linear error falls 4×, quadratic falls 8×. That gap is why second-order effects exist and why they are invisible to first-order methods |
| 6 | `jacobian` | The derivative of a vector field. When the field is −∇L, its Jacobian is −H — the hinge of everything after |
| 7 | `hessian` | Curvature, eigenvalues, definiteness, conditioning. Symmetry is the property that does the most work |
| 8 | `hvp` | Pearlmutter's trick: H·v in two gradient passes, never building H |
| 9 | `bracket` | Why training order matters, verified to machine precision, with accuracy degrading as step size grows |
| 10 | `ablation` | Which parts of an input carry weight — and the honest limits of measuring that in embedding space |
| 11 | `polarity` | The property cosine cannot measure: a claim and its exact negation sit almost on top of each other |

## What makes it a teaching tool rather than a lecture

Every equality is computed both ways and the error printed:

```
  OK numpy agrees: max abs difference 0.000e+00
  OK <u, Hv> == <Hu, v>: max abs difference 0.000e+00
  OK displacement == eta^2 * [fA, fB]: max abs difference 8.327e-17
```

That last line is the Lie-bracket identity holding to floating-point precision.
You should not have to take any of it on faith, and you don't.

## Findings worth carrying out of it

**`highdim`** — two random unit vectors at 1024 dimensions sit within a couple
of degrees of perpendicular, essentially always. Consequences for asset search:
a cosine of 0.0 means "unrelated", not "opposite"; real scores cluster roughly
0.3–0.9, so the far half of the theoretical range never appears; and there is
therefore **no universal good-score threshold to look up**. You calibrate on
your own corpus or not at all.

**`bracket`** — sign accuracy runs 98.7% at η=0.05 and 82.2% at η=0.7. Same
shape as the paper's 98% at k=1 versus 73% at k=20, and the same cause: the
bracket is the leading term of an expansion, so walking further grows what it
ignores.

Also: if two tasks' Hessians commute, the bracket reduces to `H_A H_B (b − a)`
— **still nonzero**. It vanishes only when the tasks share an optimum.
Order-independence is about the tasks wanting the same thing, not about their
curvatures aligning.

**`ablation`** — the honest bridge to prompt work, and its own disclaimer. It
measures movement in embedding space, not change in the generated image. A
clause can move the embedding a lot and change the output little. It is a
screen, not a verdict — which is what `seed_variance.py` is for.

**`polarity`** — the other half of that honesty, and the lesson with the most
direct operational consequence. A claim and its exact negation score **0.8407**
against each other, where genuinely unrelated text scores **0.229**. That puts
a negation **79% of the way from unrelated to identical**.

"the district failed to assess Student" and "the district assessed Student" are
nearly the same point. So are "denied a FAPE" and "offered a FAPE". A semantic
search for a denial retrieves the cases where the district succeeded just as
readily.

Three things the lesson is careful to separate:

- **Not a cosine bug.** Cosine reports the angle it is handed, correctly.
- **Not high-dimensional crowding.** Lesson 4's effect pushes unrelated things
  *apart*, and unrelated text does sit at 0.229 — comfortably separated.
- **It is the vectors.** The training objective rewards *topical* similarity,
  and the two sentences share nearly every content word. "failed to" is one
  token against a dozen that match.

Two corollaries ride along, both about inherited defaults:

*Reciprocal Rank Fusion's k=60.* That default assumes the two systems largely
agree — true for two web rankers, false for a keyword system and a vector
system deliberately chosen to be good at different things. At k=60 a chunk both
systems rate mediocre outranks a chunk one system is certain about. Measured: a
citation query BM25 answered at rank 1 came back at rank 10 after fusion;
k=5 restored it.

*What a green test cannot see.* Embedding a chunk's own text and searching for
it returns cosine 1.0 at rank 1 — and cannot detect that 27% of every chunk was
missing, because the model truncated at 256 tokens and both vectors were built
from the same first 256. Decisive about model mismatch, silent about window
size, with nothing in the output distinguishing the two.

---

# seed_variance.py

## What it is actually measuring

There is no way to predict prompt strength from the text. There is no function
of a prompt, or of its embedding, that forecasts whether the output will be
what you wanted — the only thing that knows is the model.

But you can measure it. Generate several samples from one prompt at different
seeds and see how much they disagree. A prompt that pins the result produces
samples that agree; a weak or ambiguous one produces scatter, because the model
is filling gaps from its priors rather than from your text.

Two things get measured, and they fail independently:

**APPEARANCE** — how much the samples differ visually. High spread means the
prompt underspecifies what the shot looks like.

**MOTION** — whether the samples agree on which way the scene moves. Measured
as the divergence of the optical flow field: positive means expanding (subject
approaching), negative means contracting (receding). If half your seeds expand
and half contract, the model is sampling direction from its priors — which is
exactly the failure that looks like "it walks backwards sometimes."

## Generating the samples

Not this tool's job. Queue the same prompt N times with the seed set to
randomize. **5 to 8 samples** is enough to see the pattern; fewer than 3 and it
warns you the numbers are noise.

## Running it

```bash
# one prompt, several seeds
python3 seed_variance.py analyze --clips runs/promptA/*.mp4

# stills work too
python3 seed_variance.py analyze --frames runs/promptA/*.png

# did the rewrite actually help?
python3 seed_variance.py compare --a runs/terse/*.mp4 \
                                 --b runs/detailed/*.mp4 \
                                 --labels terse detailed
```

`compare` is the mode that settles arguments. Eyeballing two clips does not.

## Reading the output

```
MOTION      mean flow divergence per sample
            LTX-2_5_i2v_00009_.mp4          +0.00979 expand    mag 0.622
            LTX-2_5_i2v_00012_.mp4          -0.00997 contract  mag 0.455
            LTX-2_5_i2v_00015_.mp4          +0.01063 expand    mag 0.533
            LTX-2_5_i2v_00037_.mp4          -0.02699 contract  mag 1.201

            consensus: expanding (approaching)
            direction agreement: 50% (2/4 samples)
```

**Direction agreement is the number that matters.** Thresholds:

| Agreement | Reading |
| --- | --- |
| 100% | Direction is controlled |
| 70–99% | Mostly consistent; usable if you will discard the occasional sample |
| < 70% | **Not controlled.** The model is sampling direction from priors. No prompt rewrite fixes this — supply direction structurally, with FLF2V's two anchors |

Baselines measured on this project's existing clips: **WAN 67%, LTX 50%.**

Appearance thresholds are 0.12 (tight) and 0.25 (loose) in cosine distance,
but treat them as rough — they are scene-dependent, and much more so on the
pixel fallback.

## The caveat that matters most

**Tight agreement only means the samples are consistent, not correct.** A
prompt that reliably produces exactly the wrong thing scores beautifully here.
This is the same failure as lesson 11's green test that could not see a
truncated chunk — consistency and correctness are different measurements.
Look at the outputs before acting on the numbers. The tool prints this itself
in `compare` mode, for good reason.

## Where it fits in practice

Run it *before* rewriting a prompt for the fifth time. If direction agreement
is under 70%, the prompt is not the problem and no wording will fix it — that
is the diagnosis, and it points at FLF2V rather than at your adjectives.

It also has a second use: as a gate on prompt changes generally. Change
something, generate 6 samples, compare against the old prompt's 6. If nothing
moved, the change did nothing, whatever it felt like.

---

# Related tools

| Script | Purpose |
| --- | --- |
| `chain_metrics.py` | Degradation across a *sequence* — sharpness, contrast, colour drift, CLIP identity. `seed_variance.py` compares samples of one prompt; this compares clips along a chain |
| `sequence_runner.py` | Runs a keyframe-anchored FLF2V sequence end to end |
| `make_end_frame.py` | Subject-only scale composite for a single approach shot |
| `bracket_2d.py` | Standalone version of lesson 9, with a plot and a sweep |

`vectors.py` explains what `seed_variance.py` and `chain_metrics.py` are
computing — cosine, embedding spread, high-dimensional geometry. If a number in
either of those tools looks arbitrary, the lesson that explains it is usually
lesson 2 or lesson 4.

Lessons 4 and 11 together are the argument for **hybrid retrieval** in any
corpus work: lesson 4 says rare literal tokens get blurred by dimensionality,
lesson 11 says polarity gets lost entirely. Both are fixed by the same thing —
a keyword system running alongside the vector one, because "failed", "denied"
and "did not" are ordinary tokens BM25 matches exactly. That is a concrete
argument for BM25 that has nothing to do with the usual rare-token reasoning.
