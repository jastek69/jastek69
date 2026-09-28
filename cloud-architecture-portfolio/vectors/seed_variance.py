"""seed_variance.py — measure how strongly a prompt constrains its output.

There is no way to predict prompt strength from the text. But you can measure
it: generate several samples from one prompt at different seeds, and see how
much they disagree. A prompt that pins the result produces samples that agree;
a weak or ambiguous one produces samples that scatter, because the model is
filling the gaps from its priors rather than from your text.

Two things get measured, and they fail independently:

  APPEARANCE  how much the samples differ from each other visually.
              High spread means the prompt underspecifies what the shot
              looks like.

  MOTION      for video, whether the samples agree on what MOVED and which
              way. Measured as the divergence of the optical flow field:
              positive means the scene is expanding (subject approaching),
              negative means contracting (receding). If half your seeds
              expand and half contract, the model is guessing direction --
              which is exactly the failure that looks like "it walks
              backwards sometimes."

Usage:

    # one prompt, several seeds
    python3 seed_variance.py analyze --clips runs/promptA/*.mp4

    # still images work too
    python3 seed_variance.py analyze --frames runs/promptA/*.png

    # is prompt B more constraining than prompt A?
    python3 seed_variance.py compare --a runs/promptA/*.mp4 \
                                     --b runs/promptB/*.mp4

Generating the samples is not this tool's job. Queue the same prompt N times
with the seed set to randomize -- 5 to 8 samples is enough to see the pattern.

Optional dependencies, both degrade gracefully:
    opencv-python     optical flow; without it, motion direction is estimated
                      from the spatial spread of edge energy instead
    open_clip_torch   semantic appearance comparison; without it, appearance
                      falls back to downsampled pixel correlation
"""
import argparse
import glob
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

# Below this, samples agree enough that the prompt is doing its job.
APPEARANCE_TIGHT = 0.12
APPEARANCE_LOOSE = 0.25


# --------------------------------------------------------------- extraction

def read_frames(path, n=9):
    """Evenly spaced frames from a clip, as grayscale float arrays plus the
    first and last as RGB (for appearance embedding)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "f%03d.png"
        total = frame_count(path)
        step = max(1, total // n)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path),
             "-vf", f"select='not(mod(n\\,{step}))',scale=320:-2",
             "-vsync", "0", "-y", str(out)], check=True)
        files = sorted(Path(td).glob("f*.png"))[:n]
        if len(files) < 2:
            raise SystemExit(f"could not read frames from {path}")
        rgb = [Image.open(f).convert("RGB").copy() for f in files]
    gray = [np.asarray(im.convert("L"), dtype=np.float32) for im in rgb]
    return rgb, gray


def frame_count(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
         str(path)], capture_output=True, text=True, check=True)
    return int(r.stdout.strip() or 0)


# -------------------------------------------------------------- appearance

class Appearance:
    """CLIP embedding if available, else a downsampled pixel signature. The
    fallback is much weaker -- it sees layout and color, not content -- but it
    still distinguishes "these samples look alike" from "these don't"."""

    def __init__(self):
        self.mode = "pixel"
        try:
            import open_clip
            import torch
            self.torch = torch
            self.model, _, self.pre = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="laion2b_s34b_b79k")
            self.model.eval()
            self.mode = "clip"
        except Exception as exc:
            print(f"[appearance: pixel fallback ({exc})]", file=sys.stderr)

    def embed(self, img):
        if self.mode == "clip":
            with self.torch.no_grad():
                v = self.model.encode_image(self.pre(img).unsqueeze(0))
                return (v / v.norm(dim=-1, keepdim=True)).squeeze(0).numpy()
        a = np.asarray(img.resize((32, 32), Image.LANCZOS),
                       dtype=np.float32).ravel()
        a -= a.mean()
        n = np.linalg.norm(a)
        return a / n if n else a


def pairwise_spread(vecs):
    """Mean pairwise cosine DISTANCE. 0 = identical, larger = more scatter."""
    v = np.stack(vecs)
    sim = v @ v.T
    iu = np.triu_indices(len(v), k=1)
    d = 1.0 - sim[iu]
    return float(d.mean()), float(d.min()), float(d.max())


# ------------------------------------------------------------------ motion

def flow_divergence(gray):
    """Mean divergence of the optical flow across a clip.

    Positive means the field points outward on average -- the scene is
    expanding, which is what an approaching subject looks like. Negative means
    contraction. This is the direct measurement of the thing that was
    failing: "does it come toward the camera or go away."
    """
    try:
        import cv2
    except ImportError:
        return None, spread_proxy(gray)

    divs = []
    mags = []
    for a, b in zip(gray[:-1], gray[1:]):
        f = cv2.calcOpticalFlowFarneback(
            a.astype(np.uint8), b.astype(np.uint8), None,
            0.5, 3, 21, 3, 5, 1.2, 0)
        fx, fy = f[..., 0], f[..., 1]
        # divergence = d(fx)/dx + d(fy)/dy
        div = np.gradient(fx, axis=1) + np.gradient(fy, axis=0)
        divs.append(float(div.mean()))
        mags.append(float(np.hypot(fx, fy).mean()))
    return float(np.mean(divs)), float(np.mean(mags))


def spread_proxy(gray):
    """Fallback when opencv is absent: how far edge energy sits from the
    frame center, first frame vs last. Growing subject pushes detail outward.
    Cruder than flow and easily fooled by smoke or camera moves, but it is
    better than reporting nothing."""
    def spread(g):
        gy, gx = np.gradient(g)
        e = np.hypot(gx, gy)
        tot = e.sum()
        if tot <= 0:
            return 0.0
        ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
        cy = (e * ys).sum() / tot
        cx = (e * xs).sum() / tot
        r2 = ((ys - cy) ** 2 + (xs - cx) ** 2)
        return float(np.sqrt((e * r2).sum() / tot))
    return (spread(gray[-1]) - spread(gray[0])) / max(spread(gray[0]), 1e-6)


# ---------------------------------------------------------------- analysis

def analyse(paths, is_video, app):
    rows = []
    for p in paths:
        if is_video:
            rgb, gray = read_frames(p)
            div, mag = flow_divergence(gray)
            rows.append({
                "path": Path(p).name,
                "vec": app.embed(rgb[len(rgb) // 2]),
                "first": app.embed(rgb[0]),
                "last": app.embed(rgb[-1]),
                "divergence": div,
                "magnitude": mag,
            })
        else:
            im = Image.open(p).convert("RGB")
            rows.append({"path": Path(p).name, "vec": app.embed(im),
                         "divergence": None, "magnitude": None})
    return rows


def report(rows, is_video, label=""):
    n = len(rows)
    head = f"{n} samples" + (f" — {label}" if label else "")
    print(f"\n{head}")
    print("=" * max(52, len(head)))

    mean_d, min_d, max_d = pairwise_spread([r["vec"] for r in rows])
    print(f"\nAPPEARANCE  mean pairwise distance  {mean_d:.4f}"
          f"   (range {min_d:.4f} to {max_d:.4f})")
    if mean_d < APPEARANCE_TIGHT:
        print("            tight — the prompt is pinning the look")
    elif mean_d < APPEARANCE_LOOSE:
        print("            moderate — some drift between seeds")
    else:
        print("            LOOSE — the model is filling gaps from its priors,")
        print("            not from your text. Add specifics.")

    if not is_video:
        return {"appearance": mean_d}

    divs = [r["divergence"] for r in rows]
    if divs[0] is None:
        print("\nMOTION      [opencv absent — using edge-spread proxy]")
        proxies = [r["magnitude"] for r in rows]
        agree = max(sum(p > 0 for p in proxies),
                    sum(p < 0 for p in proxies)) / n
        print(f"            spread change per sample: "
              f"{[round(p, 3) for p in proxies]}")
        print(f"            direction agreement: {100 * agree:.0f}%")
        return {"appearance": mean_d, "agreement": agree}

    pos = sum(d > 0 for d in divs)
    agree = max(pos, n - pos) / n
    consensus = "expanding (approaching)" if pos > n / 2 else \
                "contracting (receding)"

    print(f"\nMOTION      mean flow divergence per sample")
    for r in rows:
        arrow = "expand  " if r["divergence"] > 0 else "contract"
        print(f"            {r['path'][:28]:<30} {r['divergence']:>+9.5f} "
              f"{arrow}  mag {r['magnitude']:.3f}")

    print(f"\n            consensus: {consensus}")
    print(f"            direction agreement: {100 * agree:.0f}% "
          f"({max(pos, n - pos)}/{n} samples)")

    if agree < 0.7:
        print("\n            DIRECTION IS NOT CONTROLLED. The seeds disagree")
        print("            about which way the scene moves, which means the")
        print("            model is sampling direction from its priors. No")
        print("            prompt rewrite fixes this — supply the direction")
        print("            structurally (FLF2V with two anchors) instead.")
    elif agree < 1.0:
        print("\n            mostly consistent, with outliers. Usable if you")
        print("            are willing to discard a sample now and then.")
    else:
        print("\n            all samples agree on direction.")

    mags = [r["magnitude"] for r in rows]
    cv = float(np.std(mags) / max(np.mean(mags), 1e-9))
    print(f"\n            motion magnitude  mean {np.mean(mags):.3f}  "
          f"coefficient of variation {cv:.2f}")
    if cv > 0.4:
        print("            amount of motion varies a lot between seeds too.")

    return {"appearance": mean_d, "agreement": agree,
            "divergence": float(np.mean(divs)), "magnitude_cv": cv}


def expand(patterns):
    out = []
    for p in patterns:
        hits = sorted(glob.glob(p))
        out.extend(hits if hits else [p])
    missing = [p for p in out if not Path(p).exists()]
    if missing:
        raise SystemExit(f"not found: {missing}")
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="one prompt, several seeds")
    a.add_argument("--clips", nargs="+")
    a.add_argument("--frames", nargs="+")

    c = sub.add_parser("compare", help="two prompts, head to head")
    c.add_argument("--a", nargs="+", required=True)
    c.add_argument("--b", nargs="+", required=True)
    c.add_argument("--labels", nargs=2, default=["prompt A", "prompt B"])

    args = ap.parse_args()
    app = Appearance()

    if args.cmd == "analyze":
        if not (args.clips or args.frames):
            raise SystemExit("need --clips or --frames")
        is_video = bool(args.clips)
        paths = expand(args.clips or args.frames)
        if len(paths) < 3:
            print("[fewer than 3 samples — the numbers will be noisy]",
                  file=sys.stderr)
        report(analyse(paths, is_video, app), is_video)
        return

    pa, pb = expand(args.a), expand(args.b)
    ra = report(analyse(pa, True, app), True, args.labels[0])
    rb = report(analyse(pb, True, app), True, args.labels[1])

    print("\n" + "=" * 52)
    print("VERDICT")
    print("=" * 52)
    better = args.labels[0] if ra["appearance"] < rb["appearance"] \
        else args.labels[1]
    print(f"\nappearance spread   {args.labels[0]}: {ra['appearance']:.4f}   "
          f"{args.labels[1]}: {rb['appearance']:.4f}")
    print(f"                    tighter: {better}")
    if "agreement" in ra and "agreement" in rb:
        print(f"direction agreement {args.labels[0]}: "
              f"{100 * ra['agreement']:.0f}%   "
              f"{args.labels[1]}: {100 * rb['agreement']:.0f}%")
    print("\nTighter is better only if the samples are also CORRECT. A prompt")
    print("that reliably produces the wrong thing scores well here. Look at")
    print("the outputs before acting on the numbers.")


if __name__ == "__main__":
    main()
