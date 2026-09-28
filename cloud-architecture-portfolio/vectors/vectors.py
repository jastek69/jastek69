"""vectors.py — a teaching module for the mathematics behind embeddings,
optimization, and sequential training.

Every claim here is verified numerically in front of you. Where a lesson says
two quantities are equal, it computes both and prints the error. That is the
point: you should not have to take any of it on faith.

    python3 vectors.py lessons                  list them
    python3 vectors.py run dot                  one lesson
    python3 vectors.py run cosine --interactive slider demo (needs a display)
    python3 vectors.py run hessian --save out/  write plots instead of showing
    python3 vectors.py run all --save out/      everything, headless

Requires numpy and matplotlib. The `hvp` lesson additionally uses torch if it
is installed, to show the autograd version alongside the manual one; it falls
back gracefully.

The arc:

    vector    -> what a vector is, and what "normalize" buys you
    dot       -> the dot product, and why cosine is a dot product
    cosine    -> why cosine ranks and tangent cannot
    highdim   -> how 1024-dimensional space differs from your intuition
    taylor    -> local approximation, the engine under everything below
    jacobian  -> the derivative of a vector field
    hessian   -> curvature, eigenvalues, conditioning
    hvp       -> Pearlmutter's trick: Hv without ever building H
    bracket   -> Lie brackets and why training order matters
    ablation  -> measuring which parts of an input are doing work
    polarity  -> the property cosine does not measure, and what to do
"""
import argparse
import sys
from pathlib import Path

import numpy as np

SAVE_DIR = None
INTERACTIVE = False


# ----------------------------------------------------------------- plumbing

def plt_setup():
    import matplotlib
    if SAVE_DIR is not None and not INTERACTIVE:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def finish(fig, name):
    plt = plt_setup()
    if SAVE_DIR is not None:
        p = Path(SAVE_DIR) / f"{name}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=140, bbox_inches="tight")
        print(f"\n  [plot: {p}]")
        plt.close(fig)
    else:
        plt.show()


def head(title, subtitle=""):
    print()
    print("=" * 72)
    print(title)
    if subtitle:
        print(subtitle)
    print("=" * 72)


def para(text):
    print()
    for line in text.strip().split("\n"):
        print("  " + line.strip())


def check(label, a, b, tol=1e-9):
    """Print two quantities and their agreement. The teaching device of this
    whole module: assertions are cheap, verified computations are not."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    err = np.abs(a - b).max()
    mark = "OK " if err < tol else "XX "
    print(f"  {mark}{label}: max abs difference {err:.3e}")
    return err < tol


# ------------------------------------------------------------------ lessons

def lesson_vector():
    head("VECTOR", "a point, a direction, and what normalizing does")
    para("""
    A vector is an ordered list of numbers. Geometrically it is a point, or
    equivalently an arrow from the origin to that point. Your prompt
    embeddings are vectors with 1024 entries; nothing about them is different
    in kind from the two-entry ones below, only in dimension.
    """)

    v = np.array([3.0, 4.0])
    print(f"\n  v            = {v}")
    print(f"  norm ||v||   = {np.linalg.norm(v):.4f}   (sqrt(3^2 + 4^2))")

    u = v / np.linalg.norm(v)
    print(f"  v normalized = {u.round(4)}")
    print(f"  its norm     = {np.linalg.norm(u):.4f}")

    para("""
    Normalizing throws away length and keeps direction. Your asset indexer
    passes normalize=True to Titan, so every stored embedding has length 1 and
    lives on the surface of a 1024-dimensional sphere. Only direction carries
    meaning, which is exactly why an angle-based comparison is the right one.
    """)

    w = np.array([6.0, 8.0])
    print(f"\n  w = 2v       = {w}")
    print(f"  w normalized = {(w / np.linalg.norm(w)).round(4)}"
          "   <- identical to v normalized")

    para("""
    Two vectors pointing the same way normalize to the same point. After
    normalization, "twice as much of the same thing" and "the thing" are
    indistinguishable. For text embeddings that is desirable: a long prompt
    and a short one about the same subject should land together.
    """)


def lesson_dot():
    head("DOT PRODUCT", "multiply pairwise, add up, and you have an angle")
    para("""
    The dot product of two vectors is the sum of their pairwise products.
    One line of arithmetic, no trigonometry:
    """)

    a = np.array([2.0, 1.0])
    b = np.array([1.0, 3.0])
    manual = sum(x * y for x, y in zip(a, b))
    print(f"\n  a = {a},  b = {b}")
    print(f"  a . b = 2*1 + 1*3 = {manual}")
    check("numpy agrees", manual, np.dot(a, b))

    para("""
    The geometric identity is where it becomes useful:

        a . b = ||a|| ||b|| cos(theta)

    so cosine is the dot product divided by the two lengths. Verify it:
    """)

    cos_via_dot = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    theta = np.arccos(np.clip(cos_via_dot, -1, 1))
    print(f"\n  cos(theta) from the dot product = {cos_via_dot:.10f}")
    print(f"  theta                           = {np.degrees(theta):.4f} deg")
    check("cos(arccos(x)) == x", np.cos(theta), cos_via_dot)

    para("""
    And for UNIT vectors the denominator is 1, so cosine IS the dot product.
    That is the whole reason vector search is fast: comparing two normalized
    embeddings is 1024 multiplications and a sum. No trigonometry, no
    division, and it maps directly onto SIMD instructions.
    """)

    au, bu = a / np.linalg.norm(a), b / np.linalg.norm(b)
    check("unit dot product == cosine", np.dot(au, bu), cos_via_dot)

    para("""
    Note the ordering, which is easy to get backwards: the embedding model
    produces the vectors, and cosine consumes two of them. One vector alone
    has no cosine. Cosine is a comparison, not a property.
    """)


def lesson_cosine():
    head("COSINE VS TANGENT", "why one can rank results and the other cannot")
    para("""
    Ranking needs a score that moves steadily in one direction as two vectors
    separate. If it doubles back, "sort by score" is meaningless.
    """)

    for deg in (0, 30, 45, 60, 85, 89, 90, 91, 120, 180):
        r = np.radians(deg)
        t = np.tan(r)
        ts = "undefined" if abs(t) > 1e12 else f"{t:>12.4f}"
        print(f"  {deg:>4} deg   cos {np.cos(r):>8.4f}   tan {ts}")

    para("""
    Cosine falls from 1 to -1, monotonically, with every angle getting its own
    value. Tangent blows up at 90 degrees, is undefined there, returns from
    minus infinity, and hits the same value at two different angles. It is
    disqualified by shape, not by convention.
    """)

    if INTERACTIVE:
        _cosine_interactive()
    else:
        _cosine_plot()


def _cosine_plot():
    plt = plt_setup()
    deg = np.linspace(0, 180, 721)
    rad = np.radians(deg)
    tan = np.tan(rad)
    tan[np.abs(deg - 90) < 1.2] = np.nan

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(deg, np.cos(rad), color="#2a78d6", lw=2, label="cos")
    ax.plot(deg, np.clip(tan, -5, 5), color="#eb6834", lw=2, ls="--",
            label="tan (clipped)")
    ax.axhline(0, color="#c3c2b7", lw=0.7)
    ax.axvline(90, color="#e34948", lw=0.7, ls=":")
    ax.set_ylim(-5, 5)
    ax.set_xlim(0, 180)
    ax.set_xlabel("angle between vectors (degrees)")
    ax.set_title("cosine ranks; tangent cannot")
    ax.legend(frameon=False)
    finish(fig, "cosine_vs_tangent")


def _cosine_interactive():
    plt = plt_setup()
    from matplotlib.widgets import Slider

    fig, (axc, axp) = plt.subplots(1, 2, figsize=(11, 5))
    plt.subplots_adjust(bottom=0.2)

    axc.add_patch(plt.Circle((0, 0), 1, fill=False, color="#c3c2b7"))
    axc.plot([0, 1], [0, 0], color="#2a78d6", lw=2.5)
    (arrow,) = axc.plot([0, 1], [0, 0], color="#eb6834", lw=2.5)
    (dot,) = axc.plot([1], [0], "o", color="#eb6834", ms=7)
    axc.set_xlim(-1.3, 1.3)
    axc.set_ylim(-1.3, 1.3)
    axc.set_aspect("equal")
    axc.axis("off")
    title = axc.set_title("")

    deg = np.linspace(0, 180, 721)
    rad = np.radians(deg)
    tan = np.tan(rad)
    tan[np.abs(deg - 90) < 1.2] = np.nan
    axp.plot(deg, np.cos(rad), color="#2a78d6", lw=2)
    axp.plot(deg, np.clip(tan, -5, 5), color="#eb6834", lw=2, ls="--")
    (pc,) = axp.plot([35], [np.cos(np.radians(35))], "o",
                     color="#2a78d6", ms=8)
    (pt,) = axp.plot([35], [np.tan(np.radians(35))], "o",
                     color="#eb6834", ms=8)
    axp.set_ylim(-5, 5)
    axp.set_xlim(0, 180)
    axp.axhline(0, color="#c3c2b7", lw=0.7)
    axp.set_xlabel("degrees")

    slider = Slider(plt.axes([0.15, 0.06, 0.7, 0.03]),
                    "angle", 0, 180, valinit=35, valstep=1)

    def update(val):
        d = slider.val
        r = np.radians(d)
        arrow.set_data([0, np.cos(r)], [0, np.sin(r)])
        dot.set_data([np.cos(r)], [np.sin(r)])
        t = np.tan(r)
        ts = "undefined" if abs(t) > 1e6 else f"{t:.3f}"
        title.set_text(f"cos {np.cos(r):.3f}    tan {ts}")
        pc.set_data([d], [np.cos(r)])
        pt.set_data([d], [np.nan if abs(d - 90) < 1.2 else np.clip(t, -5, 5)])
        fig.canvas.draw_idle()

    slider.on_changed(update)
    update(35)
    plt.show()


def lesson_highdim():
    head("HIGH DIMENSIONS", "why 1024-space does not behave like 2-space")
    para("""
    Intuition built in two or three dimensions misleads badly at 1024. The
    single most important effect: random vectors in high dimensions are
    almost always nearly perpendicular.
    """)

    rng = np.random.default_rng(0)
    print(f"\n  {'dim':>6} {'mean |cos|':>12} {'max |cos|':>11} "
          f"{'mean angle':>12}")
    print("  " + "-" * 45)
    for d in (2, 3, 10, 100, 1024):
        a = rng.normal(size=(2000, d))
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        b = rng.normal(size=(2000, d))
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        cos = np.einsum("ij,ij->i", a, b)
        ang = np.degrees(np.arccos(np.clip(cos, -1, 1)))
        print(f"  {d:>6} {np.abs(cos).mean():>12.4f} "
              f"{np.abs(cos).max():>11.4f} {ang.mean():>11.1f} deg")

    para("""
    At 1024 dimensions two random unit vectors sit within a couple of degrees
    of perpendicular, essentially always. Consequences for your asset search:

      * A cosine of 0.0 means "unrelated", not "opposite". Opposite is
        vanishingly rare in real embeddings.
      * Real similarity scores cluster in a narrow band, roughly 0.3 to 0.9.
        The far half of the theoretical range never appears, which is why
        there is no universal "good score" threshold to look up.
      * There is enormous room for distinct concepts to coexist without
        interfering. That is what makes the space useful.
    """)

    plt = plt_setup()
    fig, ax = plt.subplots(figsize=(8, 4))
    for d, c in ((2, "#2a78d6"), (10, "#1baf7a"), (100, "#eb6834"),
                 (1024, "#8b5cf6")):
        a = rng.normal(size=(20000, d))
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        b = rng.normal(size=(20000, d))
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        cos = np.einsum("ij,ij->i", a, b)
        ax.hist(cos, bins=120, histtype="step", density=True,
                color=c, label=f"d = {d}")
    ax.set_xlabel("cosine between two random unit vectors")
    ax.set_title("dimension concentrates cosine near zero")
    ax.legend(frameon=False)
    finish(fig, "highdim_concentration")


def lesson_taylor():
    head("TAYLOR EXPANSION", "the local approximation everything else rests on")
    para("""
    Near a point, a smooth function looks like a polynomial. The gradient
    gives the best linear fit; the Hessian gives the best quadratic one.

        f(x0 + p) = f(x0) + <grad, p> + (1/2) p^T H p + O(|p|^3)

    Watch the error shrink as the step shrinks, and shrink FASTER for the
    quadratic fit. That rate difference is the whole reason second-order
    terms matter.
    """)

    def f(x):
        return np.sin(x[0]) * np.exp(0.3 * x[1])

    x0 = np.array([0.7, -0.4])
    g = np.array([np.cos(x0[0]) * np.exp(0.3 * x0[1]),
                  0.3 * np.sin(x0[0]) * np.exp(0.3 * x0[1])])
    H = np.array([
        [-np.sin(x0[0]) * np.exp(0.3 * x0[1]),
         0.3 * np.cos(x0[0]) * np.exp(0.3 * x0[1])],
        [0.3 * np.cos(x0[0]) * np.exp(0.3 * x0[1]),
         0.09 * np.sin(x0[0]) * np.exp(0.3 * x0[1])]])

    d = np.array([1.0, -0.6])
    d /= np.linalg.norm(d)

    print(f"\n  {'step t':>9} {'linear err':>13} {'quadratic err':>15} "
          f"{'lin ratio':>10} {'quad ratio':>11}")
    print("  " + "-" * 62)
    prev = None
    for t in (0.4, 0.2, 0.1, 0.05, 0.025):
        p = t * d
        true = f(x0 + p)
        lin = f(x0) + g @ p
        quad = lin + 0.5 * p @ H @ p
        e1, e2 = abs(true - lin), abs(true - quad)
        r1 = f"{prev[0] / e1:>10.2f}" if prev else " " * 10
        r2 = f"{prev[1] / e2:>11.2f}" if prev else " " * 11
        print(f"  {t:>9.3f} {e1:>13.3e} {e2:>15.3e} {r1} {r2}")
        prev = (e1, e2)

    para("""
    Halve the step and the linear error falls about 4x (it is O(t^2)); the
    quadratic error falls about 8x (it is O(t^3)). This is exactly the
    structure the Lie-bracket estimator exploits: the order effect lives at
    O(t^2), so it is invisible to any first-order method, and the neglected
    remainder is O(t^3), which is why prediction accuracy degrades as the
    step size grows.
    """)


def lesson_jacobian():
    head("JACOBIAN", "the derivative of a vector field")
    para("""
    A vector field assigns a vector to every point. Gradient descent on a loss
    is a vector field: at each parameter value it says which way to move.

    The Jacobian is its derivative -- a matrix whose (i,j) entry is how
    component i of the field changes as coordinate j moves. It tells you how
    the field BENDS as you travel through it.
    """)

    def field(x):
        return np.array([x[0] ** 2 - x[1], np.sin(x[0]) + 3 * x[1]])

    def jac_exact(x):
        return np.array([[2 * x[0], -1.0], [np.cos(x[0]), 3.0]])

    x0 = np.array([1.2, -0.5])
    J = jac_exact(x0)
    print(f"\n  at x0 = {x0}")
    print(f"  J =\n{np.array2string(J, prefix='      ')}")

    eps = 1e-6
    Jn = np.zeros((2, 2))
    for j in range(2):
        e = np.zeros(2)
        e[j] = eps
        Jn[:, j] = (field(x0 + e) - field(x0 - e)) / (2 * eps)
    check("finite differences match the analytic Jacobian", J, Jn, tol=1e-6)

    para("""
    When the field is the NEGATIVE gradient of a loss, its Jacobian is the
    negative Hessian of that loss:

        f = -grad L    =>    Df = -H

    So the Hessian is not a separate object bolted on. It is what you get when
    you differentiate the descent direction. That identity is the hinge of the
    Lie-bracket derivation.
    """)


def lesson_hessian():
    head("HESSIAN", "curvature, eigenvalues, and conditioning")
    para("""
    The Hessian holds all second partial derivatives. Three equivalent
    readings: the derivative of the gradient, the quadratic coefficient in a
    Taylor expansion, and the curvature of the surface.
    """)

    H = np.array([[4.0, 1.0], [1.0, 1.0]])
    print(f"\n  H =\n{np.array2string(H, prefix='      ')}")
    check("symmetric (Schwarz's theorem)", H, H.T)

    para("""
    Symmetry is the property that does the most work in practice. It lets you
    move H across an inner product:  <u, Hv> = <Hu, v>.  That identity is
    precisely what collapses the bracket tournament from O(N^2) Hessian-vector
    products to N.
    """)

    rng = np.random.default_rng(1)
    u, v = rng.normal(size=2), rng.normal(size=2)
    check("<u, Hv> == <Hu, v>", u @ (H @ v), (H @ u) @ v)

    w, V = np.linalg.eigh(H)
    print(f"\n  eigenvalues  {w.round(4)}")
    print(f"  eigenvectors\n{np.array2string(V, prefix='      ')}")
    print(f"  condition number  kappa = {w.max() / w.min():.3f}")

    para("""
    Eigenvectors are the principal curvature axes; eigenvalues are the
    curvature along them. Directional curvature in any direction v is the
    Rayleigh quotient v^T H v, maximized by the top eigenvector and minimized
    by the bottom one. Verify by brute force:
    """)

    angles = np.linspace(0, np.pi, 2000)
    dirs = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    curv = np.einsum("ij,jk,ik->i", dirs, H, dirs)
    print(f"\n  max curvature over all directions  {curv.max():.6f} "
          f"(top eigenvalue {w.max():.6f})")
    print(f"  min curvature over all directions  {curv.min():.6f} "
          f"(bottom eigenvalue {w.min():.6f})")

    para("""
    Definiteness classifies critical points: all eigenvalues positive means a
    local minimum, all negative a maximum, mixed signs a saddle. In deep
    networks the spectrum is indefinite and dominated by near-zero values, so
    most critical points reached in training are saddles rather than minima.

    The condition number kappa is the ratio of steepest to shallowest
    curvature. Large kappa means elongated level sets, and gradient descent
    zigzags: step size is capped by the largest eigenvalue while progress
    along the shallowest direction is governed by the smallest.
    """)

    plt = plt_setup()
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    xs = np.linspace(-2, 2, 300)
    X, Y = np.meshgrid(xs, xs)
    Z = 0.5 * (H[0, 0] * X ** 2 + 2 * H[0, 1] * X * Y + H[1, 1] * Y ** 2)
    ax[0].contour(X, Y, Z, levels=20, colors="#c3c2b7", linewidths=0.7)
    for i, c in enumerate(("#2a78d6", "#eb6834")):
        ax[0].arrow(0, 0, V[0, i] * w[i] / w.max() * 1.6,
                    V[1, i] * w[i] / w.max() * 1.6,
                    color=c, width=0.02, length_includes_head=True)
    ax[0].set_aspect("equal")
    ax[0].set_title("level sets and principal axes")

    ax[1].plot(np.degrees(angles), curv, color="#2a78d6")
    for val in w:
        ax[1].axhline(val, color="#eb6834", ls="--", lw=0.8)
    ax[1].set_xlabel("direction (degrees)")
    ax[1].set_ylabel("v^T H v")
    ax[1].set_title("directional curvature, bounded by the eigenvalues")
    finish(fig, "hessian_curvature")


def lesson_hvp():
    head("PEARLMUTTER'S TRICK", "Hv without ever building H")
    para("""
    A model with P parameters has a P x P Hessian. At 7 billion parameters
    that is about 5e19 entries -- unstorable by many orders of magnitude.

    But almost nothing needs H itself. It needs H times a vector. And for a
    CONSTANT v:

        H v = grad_theta < grad_theta L(theta), v >

    Differentiating a scalar returns a vector of the right size, and the chain
    rule drops the Hessian onto v exactly. Cost: about two gradients,
    regardless of dimension.
    """)

    rng = np.random.default_rng(4)
    d = 6
    A = rng.normal(size=(d, d))
    Hm = A @ A.T + 2 * np.eye(d)
    c = rng.normal(size=d)

    def loss(x):
        return 0.5 * x @ Hm @ x + c @ x

    def grad(x):
        return Hm @ x + c

    x0 = rng.normal(size=d)
    v = rng.normal(size=d)

    print(f"\n  explicit H @ v (only possible because d = {d})")
    hv_explicit = Hm @ v

    eps = 1e-6
    hv_fd = (grad(x0 + eps * v) - grad(x0 - eps * v)) / (2 * eps)
    check("finite-difference directional derivative of the gradient",
          hv_explicit, hv_fd, tol=1e-6)

    try:
        import torch

        def tloss(x):
            return 0.5 * x @ torch.tensor(Hm) @ x + torch.tensor(c) @ x

        xt = torch.tensor(x0, requires_grad=True)
        vt = torch.tensor(v)
        g = torch.autograd.grad(tloss(xt), xt, create_graph=True)[0]
        hv = torch.autograd.grad((g * vt).sum(), xt)[0]
        check("autograd double-backward (Pearlmutter)",
              hv_explicit, hv.detach().numpy())

        para("""
        Note what the second call differentiates: the SCALAR <grad, v>, not
        the gradient itself. That is the trick. And v must be detached -- if
        it carries gradient history you silently pick up an extra
        (dv/dtheta)^T grad term and compute something that is not an HVP.
        """)
    except ImportError:
        para("""
        [torch not installed -- the autograd version is skipped. The
        finite-difference check above demonstrates the same identity; the
        autograd version is exact rather than approximate, and is what you
        would actually use.]
        """)

    para("""
    One more caution for real use: create_graph=True roughly doubles
    activation memory. On a 24 GB card with a 12B model that is out of reach
    for full-model parameters, but fine when restricted to LoRA parameters --
    which is the only case where you would want this anyway.
    """)


def lesson_bracket():
    head("LIE BRACKET", "why the order of training matters")
    para("""
    Training on dataset A then B is composing two flows. Nonlinear flows do
    not generally commute, so the two orders land in different places.

    Expanding both compositions to second order:

        theta_AB = theta0 + t(fA + fB) + (t^2/2)(DfA fA + DfB fB) + t^2 DfB fA
        theta_BA = theta0 + t(fA + fB) + (t^2/2)(DfA fA + DfB fB) + t^2 DfA fB

    The first-order term is a plain SUM over both tasks -- addition commutes,
    so order cannot appear there. The self-interaction terms are identical.
    Subtracting leaves only:

        theta_AB - theta_BA = t^2 (DfB fA - DfA fB) = t^2 [fA, fB]

    which in loss terms is  H_B g_A - H_A g_B.  For quadratics the gradient
    field is affine, so this is EXACT rather than approximate. Verify it:
    """)

    rng = np.random.default_rng(7)

    def spd(cond=8.0):
        a = rng.uniform(0, np.pi)
        R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return R @ np.diag([1.0, 1.0 / cond]) @ R.T

    HA, HB, HT = spd(), spd(), spd()
    oA = np.array([2.0, 1.0])
    oB = np.array([-1.5, 2.5])
    oT = np.array([0.5, -1.0])
    th0 = np.zeros(2)
    eta = 0.35

    gA = lambda x: HA @ (x - oA)          # noqa: E731
    gB = lambda x: HB @ (x - oB)          # noqa: E731
    gT = lambda x: HT @ (x - oT)          # noqa: E731
    lT = lambda x: 0.5 * (x - oT) @ HT @ (x - oT)   # noqa: E731

    ab = th0 - eta * gA(th0)
    ab = ab - eta * gB(ab)
    ba = th0 - eta * gB(th0)
    ba = ba - eta * gA(ba)

    bracket = HB @ gA(th0) - HA @ gB(th0)
    print(f"\n  after A then B   {ab.round(6)}")
    print(f"  after B then A   {ba.round(6)}")
    check("displacement == eta^2 * [fA, fB]", ab - ba, eta ** 2 * bracket,
          tol=1e-12)

    score = gT(th0) @ bracket
    winner = "A then B" if lT(ab) < lT(ba) else "B then A"
    called = "A then B" if score < 0 else "B then A"
    print(f"\n  target loss  A->B {lT(ab):.6f}   B->A {lT(ba):.6f}")
    print(f"  actual winner     {winner}")
    print(f"  score <gT, b_AB>  {score:+.6f}  -> predicts {called}")

    para("""
    The score projects the bracket displacement onto the target's downhill
    direction. Negative means A before B gives lower target loss.

    Now sweep step size. The bracket is the LEADING term of an expansion, so
    accuracy degrades as you walk further -- the same reason the paper reports
    98% at k=1 steps and 73% at k=20.
    """)

    print(f"\n  {'eta':>8} {'sign accuracy':>16} {'median |loss gap|':>20}")
    print("  " + "-" * 46)
    accs = []
    etas = [0.05, 0.1, 0.2, 0.35, 0.5, 0.7]
    for e in etas:
        hits, gaps = 0, []
        r2 = np.random.default_rng(11)
        for _ in range(1500):
            def s():
                a = r2.uniform(0, np.pi)
                R = np.array([[np.cos(a), -np.sin(a)],
                              [np.sin(a), np.cos(a)]])
                return R @ np.diag([1.0, 0.125]) @ R.T
            ha, hb, ht = s(), s(), s()
            pa, pb, pt = (r2.normal(size=2) * 2 for _ in range(3))
            p0 = r2.normal(size=2)
            ga, gb = ha @ (p0 - pa), hb @ (p0 - pb)
            x = p0 - e * ga
            x = x - e * (hb @ (x - pb))
            y = p0 - e * gb
            y = y - e * (ha @ (y - pa))
            la = 0.5 * (x - pt) @ ht @ (x - pt)
            lb = 0.5 * (y - pt) @ ht @ (y - pt)
            sc = (ht @ (p0 - pt)) @ (hb @ ga - ha @ gb)
            hits += (la < lb) == (sc < 0)
            gaps.append(abs(la - lb))
        acc = 100 * hits / 1500
        accs.append(acc)
        print(f"  {e:>8.2f} {acc:>15.1f}% {np.median(gaps):>20.4f}")

    para("""
    One structural fact worth carrying: if HA and HB commute, the bracket
    reduces to HA HB (oB - oA) -- still nonzero. It vanishes only when the two
    tasks share an optimum. Order-independence is about the tasks wanting the
    same thing, not about their curvatures aligning.
    """)

    commuting = HA @ HB - HB @ HA
    print(f"\n  ||HA HB - HB HA|| = {np.linalg.norm(commuting):.4f} "
          "(nonzero here: they do not commute)")

    plt = plt_setup()
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    xs = np.linspace(-3, 3.5, 300)
    X, Y = np.meshgrid(xs, xs)
    Z = np.array([lT(p) for p in np.stack([X.ravel(), Y.ravel()], 1)])
    ax[0].contour(X, Y, Z.reshape(X.shape), levels=18,
                  colors="#c3c2b7", linewidths=0.6)
    p1 = np.array([th0, th0 - eta * gA(th0), ab])
    p2 = np.array([th0, th0 - eta * gB(th0), ba])
    ax[0].plot(*p1.T, "-o", color="#2a78d6", lw=2, ms=5, label="A then B")
    ax[0].plot(*p2.T, "-o", color="#eb6834", lw=2, ms=5, label="B then A")
    ax[0].annotate("", xy=ab, xytext=ba,
                   arrowprops=dict(arrowstyle="<->", color="#52514e", lw=1.2))
    ax[0].set_aspect("equal")
    ax[0].legend(frameon=False)
    ax[0].set_title("same two steps, opposite order")

    ax[1].plot(etas, accs, "-o", color="#1baf7a")
    ax[1].axhline(50, color="#e34948", ls="--", lw=0.8)
    ax[1].set_ylim(45, 100)
    ax[1].set_xlabel("step size eta")
    ax[1].set_ylabel("sign accuracy (%)")
    ax[1].set_title("prediction degrades as you walk further")
    finish(fig, "lie_bracket")


def lesson_ablation():
    head("ABLATION", "measuring which parts of an input are doing work")
    para("""
    This is the honest bridge from the geometry above to a practical question:
    given a prompt, which parts of it actually matter?

    The method needs no gradients and no training. Embed the full input, then
    embed it again with one clause removed, and measure how far the embedding
    moved. A clause whose removal barely moves the point is contributing
    little; one whose removal moves it a lot is load-bearing.

    Below, synthetic clause vectors stand in for a real text encoder so the
    mechanics are visible. Applied for real, you would swap in the same
    encoder your model uses.
    """)

    rng = np.random.default_rng(5)
    names = ["subject", "action", "camera", "lighting", "style", "filler"]
    weights = [1.0, 0.9, 0.6, 0.4, 0.3, 0.05]

    d = 64
    basis = rng.normal(size=(len(names), d))
    basis /= np.linalg.norm(basis, axis=1, keepdims=True)
    clauses = {n: w * basis[i] for i, (n, w) in enumerate(zip(names, weights))}

    def combine(keys):
        v = sum(clauses[k] for k in keys)
        return v / np.linalg.norm(v)

    full = combine(names)

    print(f"\n  {'removed clause':>16} {'cosine to full':>16} "
          f"{'displacement':>14}")
    print("  " + "-" * 48)
    rows = []
    for n in names:
        rest = [k for k in names if k != n]
        v = combine(rest)
        cos = float(np.dot(full, v))
        rows.append((n, cos, np.linalg.norm(full - v)))
    for n, cos, disp in sorted(rows, key=lambda r: r[1]):
        print(f"  {n:>16} {cos:>16.4f} {disp:>14.4f}")

    para("""
    The ordering recovers the weights we planted. Read it as: clauses at the
    top are carrying the prompt; clauses at the bottom are nearly free to cut.

    Two honest limits before you trust this on real prompts.

    First, it measures movement in EMBEDDING space, not change in the
    generated image. A clause can shift the embedding a lot and change the
    output little, or the reverse. It is a screen, not a verdict.

    Second, and more important: nothing here predicts whether a prompt will
    WORK. It tells you which parts of your text the encoder distinguishes.
    The only reliable measure of prompt strength is empirical -- generate
    several samples at different seeds and measure how much the OUTPUTS vary.
    A prompt that pins the result produces low variance across seeds; a weak
    or ambiguous one produces high variance. That requires generating, and
    there is no shortcut around it.
    """)



# ---------------------------------------------------------------------------
# Lesson 11 — polarity
#
# Same topic, opposite claim. A model that distinguishes them scores these
# LOW. One that cannot will retrieve either when asked for the other.
# Sentences are from California special-education hearing decisions.
# ---------------------------------------------------------------------------

NEGATION_PAIRS = [
    ("the district failed to assess Student in occupational therapy",
     "the district assessed Student in occupational therapy"),
    ("the district did not provide the speech therapy required by the IEP",
     "the district provided the speech therapy required by the IEP"),
    ("the district failed to implement the IEP",
     "the district implemented the IEP as written"),
    ("Student was denied a free appropriate public education",
     "Student was offered a free appropriate public education"),
    ("the IEP team predetermined the placement before the meeting",
     "the IEP team considered placement options at the meeting"),
    ("the district never referred Student for special education assessment",
     "the district referred Student for special education assessment"),
    ("the goals were inappropriate and did not address Student's needs",
     "the goals were appropriate and addressed Student's needs"),
    ("Parents were denied meaningful participation in the IEP process",
     "Parents meaningfully participated in the IEP process"),
]

# Genuinely different topics. These establish what "unrelated" scores on THIS
# model and THIS corpus. Without them a 0.88 has no meaning — lesson 4 already
# said there is no universal good-score threshold to look up.
CONTROLS = [
    ("the district failed to assess Student in occupational therapy",
     "the hearing was held by videoconference over four days"),
    ("the district failed to implement the IEP",
     "Parent requested reimbursement for a private school placement"),
    ("Student was denied a free appropriate public education",
     "the witness has been a credentialed teacher for thirty years"),
    ("the IEP team predetermined the placement before the meeting",
     "the parties stipulated to the admission of exhibits"),
]

# Measured on all-MiniLM-L6-v2 against this corpus, so the lesson runs with no
# model, no download and no network — the same promise as every other lesson
# here. Install sentence-transformers and it recomputes live instead.
MEASURED_MINILM = {
    "negation": [0.8794, 0.8898, 0.8332, 0.8505, 0.9075,
                 0.7200, 0.7600, 0.8855],
    "control": [0.1756, 0.1960, 0.3340, 0.2100],
}


def position_between(value, floor, ceiling=1.0):
    """Where `value` sits between floor and ceiling, as a fraction.

    THE POINT OF THE LESSON. A raw cosine is uninterpretable on its own;
    lesson 4 establishes that the usable range is narrow and corpus-specific.
    What IS interpretable is position relative to a MEASURED floor.

        0.0 = indistinguishable from unrelated text
        1.0 = identical
    """
    span = ceiling - floor
    return (value - floor) / span if span else 0.0


def _polarity_scores(model_name):
    """Live scores if sentence-transformers is installed, else the recorded
    ones. Returns (negation, control, label, measured_live)."""
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        return (MEASURED_MINILM["negation"], MEASURED_MINILM["control"],
                "all-MiniLM-L6-v2 (recorded)", False)

    model = SentenceTransformer(model_name)
    print(f"\n  model: {model_name}  max_seq_length={model.max_seq_length}")

    def score(a, b):
        va, vb = model.encode([a, b])
        return float(util.cos_sim(va, vb)[0][0])

    neg = [score(a, b) for a, b in NEGATION_PAIRS]
    ctl = [score(a, b) for a, b in CONTROLS]
    return neg, ctl, model_name, True


def lesson_polarity(model_name="all-MiniLM-L6-v2"):
    head("POLARITY", "the property cosine does not measure")
    para("""
    Lessons 1-4 establish the geometry: a vector is a point, normalizing keeps
    direction, cosine is the dot product for unit vectors, and at high
    dimension everything is nearly perpendicular. Lesson 10 measured movement
    in embedding space and was honest that movement is not the same as effect.

    This is the other half of that honesty. Lesson 10 said the measurement is
    a screen, not a verdict. This one names a specific thing the screen cannot
    see, and it is not subtle: a claim and its exact negation sit almost on top
    of each other.
    """)

    neg, ctl, label, live = _polarity_scores(model_name)
    if not live:
        print("\n  [sentence-transformers not installed — using recorded "
              "values.\n   pip install sentence-transformers to recompute "
              "live.]")

    print("\n  NEGATION PAIRS — same topic, opposite claim")
    for (a, b), s in zip(NEGATION_PAIRS, neg):
        flag = "  <-- indistinguishable" if s > 0.85 else ""
        print(f"\n  {s:.4f}{flag}")
        print(f"     A: {a}")
        print(f"     B: {b}")

    print("\n  CONTROLS — different topics (the measured floor)")
    for (a, b), s in zip(CONTROLS, ctl):
        print(f"  {s:.4f}   {a[:38]}... / {b[:34]}...")

    neg_avg = float(np.mean(neg))
    ctl_avg = float(np.mean(ctl))
    pos = position_between(neg_avg, ctl_avg)

    print(f"\n  RESULT — {label}")
    print(f"  {'-' * 60}")
    print(f"  unrelated text (measured floor)   {ctl_avg:.4f}")
    print(f"  claim vs its own negation         {neg_avg:.4f}")
    print(f"  identical text                    1.0000")
    print(f"\n  a negation sits {100 * pos:.0f}% of the way from UNRELATED "
          f"to IDENTICAL\n")

    width = 56
    for name, val in (("unrelated", ctl_avg), ("negation", neg_avg),
                      ("identical", 1.0)):
        filled = max(0, min(width, int(round(
            position_between(val, ctl_avg) * width))))
        print(f"  {name:<10} |{'#' * filled}{'.' * (width - filled)}| "
              f"{val:.3f}")

    if pos > 0.6:
        para(f"""
        VERDICT: the model does not encode polarity.

        Note what this is NOT. It is not a bug in cosine — cosine reports the
        angle between the vectors it is handed, correctly. It is not
        high-dimensional crowding either; lesson 4's effect pushes unrelated
        things APART, and here unrelated text sits at {ctl_avg:.3f},
        comfortably separated.

        The vectors themselves place a claim and its negation together,
        because the training objective rewards TOPICAL similarity and the two
        sentences share nearly every content word. "failed to" is one token
        against a dozen that match.
        """)
    else:
        para("VERDICT: this model separates claim from negation adequately.")

    para("""
    Why it matters outside this file. Measured on a corpus of California
    special-education hearing decisions — a body of text almost entirely about
    failures. Failure to assess, failure to implement, failure to offer. A
    semantic search for a denial retrieves the decisions where the district
    SUCCEEDED just as readily.

    The same shape appears anywhere the interesting cases are negative:
    incident reports, audit findings, medical contraindications, compliance
    exceptions. If your corpus is about things going wrong, this lesson is
    about your corpus.
    """)

    _polarity_rrf()
    _polarity_blind_test()

    para("""
    WHAT TO DO ABOUT IT

    1. Put the polarity word where a keyword system can see it. "failed",
       "denied", "did not" are ordinary tokens and BM25 matches them exactly.
       A concrete argument for hybrid retrieval that has nothing to do with
       the usual rare-token reasoning.

    2. Prefer text that already states the claim. In the legal corpus, ISSUE
       statements are phrased "Did the District deny Student a FAPE by
       FAILING to ..." -- the polarity is in the words. Narrative body text
       describes what happened and often carries the opposite sign.
       Retrieving over issue statements sidesteps the problem instead of
       fighting it.

    3. Do not expect a larger model to fix it. Negation is a known weakness
       across dense retrievers, not a property of this one. Pass another model
       name to recompute, but treat improvement as a bonus rather than a plan.

    4. Measure your own floor. Lesson 4 said there is no universal good-score
       threshold to look up. This is that principle with teeth: 0.8407 reads
       as acceptable against a guessed bar of 0.85, and as severe against a
       measured floor of 0.235. Same number, opposite conclusion, and only one
       of the two reference points was real.
    """)

    _polarity_plot(neg, ctl, label)


def _polarity_rrf():
    """Why the default RRF constant misfires when systems disagree.

    Not about embeddings, but it belongs here: the same error of inheriting a
    constant whose assumptions do not hold for your data.
    """
    print("\n  " + "=" * 68)
    print("  COROLLARY — a default that assumes agreement")
    print("  " + "=" * 68)
    para("""
    Reciprocal Rank Fusion combines two rankings:  score = sum 1/(k + rank)

    The constant k defaults to 60 nearly everywhere, and that default assumes
    the two systems LARGELY AGREE -- true for two web-search rankers, false
    for a keyword system and a vector system deliberately chosen to be good at
    different things.

      A: ranked 1st by ONE system, absent from the other  (specific, correct)
      B: ranked 25th by BOTH                              (generic, mediocre)
    """)
    for k in (60, 30, 10, 5, 2):
        a, b = 1 / (k + 1), 2 / (k + 25)
        print(f"    k={k:<3}  A={a:.4f}  B={b:.4f}   -> "
              f"{'A wins (specific)' if a > b else 'B wins (generic)'}")
    para("""
    At the default, a chunk both systems find mediocre OUTRANKS a chunk one
    system is certain about. Measured consequence on a legal corpus: a
    citation query BM25 answered at rank 1 came back at rank 10 after fusion.
    Lowering k to 5 restored it.

    The lesson generalizes past RRF. A constant carries the assumptions of
    wherever it was tuned. If your two systems were chosen BECAUSE they
    disagree, a parameter that rewards agreement is working against you.
    """)


def _polarity_blind_test():
    """A passing test that cannot see the failure it is asked about."""
    print("\n  " + "=" * 68)
    print("  COROLLARY — what a green test cannot see")
    print("  " + "=" * 68)
    para("""
    To check a vector index, embed a chunk's own text and search for it. It
    should return itself at rank 1 with cosine 1.0. Run on a real index:

        cosine(stored, fresh) = 1.0000   -> SAME model
        self kNN rank = 1

    Perfect. And it could not detect that 27% of every chunk was missing.

    The model truncates at 256 tokens; the chunks ran ~350. Both the stored
    vector and the fresh one were built from the same first 256 tokens, so
    they matched exactly -- while representing less than three quarters of the
    text.

    The test was decisive about MODEL MISMATCH and silent about WINDOW SIZE,
    and nothing in its output distinguished the two.

    This is seed_variance.py's warning in another domain: tight agreement
    means the samples are consistent, not correct. A prompt that reliably
    produces the wrong thing scores beautifully there; a test that
    consistently measures the wrong half of a chunk scores beautifully here.

    The habit worth keeping: ask what a passing test CANNOT see, not only what
    it reports.
    """)


def _polarity_plot(neg, ctl, label):
    plt = plt_setup()
    ctl_avg = float(np.mean(ctl))
    neg_avg = float(np.mean(neg))

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2),
                                  gridspec_kw={"width_ratios": [1, 1.3]})

    bars = ["unrelated", "negation", "identical"]
    vals = [ctl_avg, neg_avg, 1.0]
    pos = [position_between(v, ctl_avg) for v in vals]
    ax.barh(bars, pos, color=["#1baf7a", "#e34948", "#898781"], height=0.5)
    for i, (p, v) in enumerate(zip(pos, vals)):
        ax.text(p + 0.02, i, f"{v:.3f}", va="center", fontsize=10)
    ax.set_xlim(0, 1.18)
    ax.set_xlabel("position from measured floor to identical")
    ax.set_title("a negation is not far from identical")

    idx = np.arange(len(neg))
    ax2.scatter(idx, neg, color="#e34948", s=45, label="claim vs negation",
                zorder=3)
    ax2.axhline(ctl_avg, color="#1baf7a", ls="--", lw=1.2,
                label=f"unrelated floor ({ctl_avg:.3f})")
    ax2.axhline(1.0, color="#898781", ls=":", lw=1.0, label="identical")
    ax2.set_ylim(0, 1.05)
    ax2.set_xticks(idx)
    ax2.set_xlabel("negation pair")
    ax2.set_ylabel("cosine similarity")
    ax2.set_title(label)
    ax2.legend(frameon=False, fontsize=9, loc="lower right")

    fig.tight_layout()
    finish(fig, "polarity")


# ------------------------------------------------- browser-served demos
# For headless machines. Serves a self-contained page on localhost that you
# reach through an SSH tunnel:
#
#     ssh -L 8765:localhost:8765 ubuntu@<instance>
#     python3 vectors.py serve --port 8765
#     # then open http://localhost:8765 in your own browser
#
# No CDN, no external assets — everything is inline, so this works on a box
# with restricted egress.

PAGE = """<!doctype html><meta charset="utf-8">
<title>vectors.py — interactive</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;
      padding:0 1rem;color:#1a1a18;background:#faf9f7}
 h1{font-size:1.3rem;font-weight:600}
 h2{font-size:1.05rem;font-weight:600;margin:2.4rem 0 .4rem}
 .panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
        gap:18px;align-items:center}
 .row{display:flex;gap:12px;align-items:center;margin:.8rem 0}
 input[type=range]{flex:1}
 .val{font-variant-numeric:tabular-nums;min-width:74px;text-align:right;
      font-weight:600}
 .stat{background:#fff;border:1px solid #e6e4df;border-radius:8px;
       padding:10px 12px}
 .stat .k{font-size:12px;color:#6b6a66}
 .stat .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
 .grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 p.note{color:#52514e;font-size:14px}
 code{background:#f0eeea;padding:1px 5px;border-radius:4px}
</style>
<h1>vectors.py — interactive demos</h1>

<h2>1. Cosine ranks; tangent cannot</h2>
<p class="note">Drag through the full range. Cosine falls steadily from 1 to
&minus;1, so sorting by it is meaningful. Tangent blows up at 90&deg;, is
undefined there, and returns the same value at two different angles.</p>
<div class="row"><label>angle</label>
 <input type="range" id="ang" min="0" max="180" step="1" value="35">
 <span class="val" id="angv">35&deg;</span></div>
<div class="panel">
 <svg viewBox="0 0 300 300" id="circ">
  <circle cx="150" cy="150" r="110" fill="none" stroke="#d8d6d0"/>
  <line x1="30" y1="150" x2="270" y2="150" stroke="#e6e4df"/>
  <line x1="150" y1="30" x2="150" y2="270" stroke="#e6e4df"/>
  <line x1="150" y1="150" x2="260" y2="150" stroke="#2a78d6" stroke-width="2.5"/>
  <circle cx="260" cy="150" r="4.5" fill="#2a78d6"/>
  <line id="av" x1="150" y1="150" x2="260" y2="150" stroke="#eb6834"
        stroke-width="2.5"/>
  <circle id="ad" cx="260" cy="150" r="4.5" fill="#eb6834"/>
 </svg>
 <div>
  <div class="grid2">
   <div class="stat"><div class="k">cos &theta;</div>
     <div class="v" id="cosv">0.819</div></div>
   <div class="stat"><div class="k">tan &theta;</div>
     <div class="v" id="tanv">0.700</div></div>
  </div>
  <svg viewBox="0 0 320 200" id="plot" style="margin-top:10px">
   <line x1="20" y1="100" x2="310" y2="100" stroke="#e6e4df"/>
   <path id="cosp" fill="none" stroke="#2a78d6" stroke-width="2"/>
   <path id="tanp" fill="none" stroke="#eb6834" stroke-width="2"
         stroke-dasharray="5 4"/>
   <circle id="pc" r="4" fill="#2a78d6"/>
   <circle id="pt" r="4" fill="#eb6834"/>
  </svg>
 </div>
</div>

<h2>2. Lie bracket: same two steps, opposite order</h2>
<p class="note">Two quadratic tasks. Blue takes a gradient step on A then B;
orange takes B then A. Same start, same steps. The gap between the endpoints
is exactly <code>&eta;&sup2;(H<sub>B</sub>g<sub>A</sub> &minus;
H<sub>A</sub>g<sub>B</sub>)</code>. Raise &eta; and watch the separation grow
as the square.</p>
<div class="row"><label>step size &eta;</label>
 <input type="range" id="eta" min="1" max="80" step="1" value="35">
 <span class="val" id="etav">0.35</span></div>
<div class="panel">
 <svg viewBox="0 0 320 300" id="brk">
  <path id="pA" fill="none" stroke="#2a78d6" stroke-width="2.5"/>
  <path id="pB" fill="none" stroke="#eb6834" stroke-width="2.5"/>
  <line id="gap" stroke="#52514e" stroke-width="1.2" stroke-dasharray="3 3"/>
  <circle id="e1" r="5" fill="#2a78d6"/>
  <circle id="e2" r="5" fill="#eb6834"/>
  <circle id="o" r="4" fill="#52514e"/>
 </svg>
 <div class="grid2">
  <div class="stat"><div class="k">separation</div>
    <div class="v" id="sep">0.000</div></div>
  <div class="stat"><div class="k">&eta;&sup2;&middot;|bracket|</div>
    <div class="v" id="pred">0.000</div></div>
 </div>
</div>

<script>
const R=110,CX=150,CY=150,rad=d=>d*Math.PI/180;
function pathFor(fn,clip){let s="",first=true;
 for(let d=0;d<=180;d+=1){const y=fn(rad(d));
  if(clip&&(Math.abs(d-90)<2)){first=true;continue;}
  const yy=Math.max(-5,Math.min(5,y));
  const X=20+d*(290/180), Y=100-yy*18;
  s+=(first?"M":"L")+X.toFixed(1)+" "+Y.toFixed(1);first=false;}
 return s;}
document.getElementById("cosp").setAttribute("d",pathFor(Math.cos,false));
document.getElementById("tanp").setAttribute("d",pathFor(Math.tan,true));
const ang=document.getElementById("ang");
function upd1(){const d=+ang.value,r=rad(d),t=Math.tan(r);
 document.getElementById("angv").innerHTML=d+"&deg;";
 document.getElementById("cosv").textContent=Math.cos(r).toFixed(3);
 document.getElementById("tanv").textContent=
   (Math.abs(d-90)<0.5||Math.abs(t)>1e6)?"undefined":t.toFixed(3);
 const x=CX+R*Math.cos(r),y=CY-R*Math.sin(r);
 const av=document.getElementById("av");
 av.setAttribute("x2",x.toFixed(1));av.setAttribute("y2",y.toFixed(1));
 const ad=document.getElementById("ad");
 ad.setAttribute("cx",x.toFixed(1));ad.setAttribute("cy",y.toFixed(1));
 const px=20+d*(290/180);
 const pc=document.getElementById("pc");
 pc.setAttribute("cx",px);pc.setAttribute("cy",100-Math.cos(r)*18);
 const pt=document.getElementById("pt");
 const tv=Math.max(-5,Math.min(5,t));
 pt.setAttribute("cx",px);
 pt.setAttribute("cy",Math.abs(d-90)<2?-99:100-tv*18);}
ang.addEventListener("input",upd1);upd1();

// --- bracket -------------------------------------------------------------
function rot(a){return [[Math.cos(a),-Math.sin(a)],[Math.sin(a),Math.cos(a)]];}
function spd(a,c){const R=rot(a),D=[[1,0],[0,1/c]];
 const RD=[[R[0][0]*D[0][0],R[0][1]*D[1][1]],[R[1][0]*D[0][0],R[1][1]*D[1][1]]];
 return [[RD[0][0]*R[0][0]+RD[0][1]*R[0][1],RD[0][0]*R[1][0]+RD[0][1]*R[1][1]],
         [RD[1][0]*R[0][0]+RD[1][1]*R[0][1],RD[1][0]*R[1][0]+RD[1][1]*R[1][1]]];}
const HA=spd(0.6,8),HB=spd(2.1,8),oA=[2,1],oB=[-1.5,2.5];
const mv=(M,v)=>[M[0][0]*v[0]+M[0][1]*v[1],M[1][0]*v[0]+M[1][1]*v[1]];
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]];
const step=(H,o,x,e)=>{const g=mv(H,sub(x,o));return [x[0]-e*g[0],x[1]-e*g[1]];};
const SC=46,OX=160,OY=170;
const px=p=>[OX+p[0]*SC,OY-p[1]*SC];
const eta=document.getElementById("eta");
function upd2(){const e=+eta.value/100;
 document.getElementById("etav").textContent=e.toFixed(2);
 const z=[0,0];
 const a1=step(HA,oA,z,e), a2=step(HB,oB,a1,e);
 const b1=step(HB,oB,z,e), b2=step(HA,oA,b1,e);
 const P=[z,a1,a2].map(px), Q=[z,b1,b2].map(px);
 document.getElementById("pA").setAttribute("d",
  `M${P[0][0]} ${P[0][1]}L${P[1][0]} ${P[1][1]}L${P[2][0]} ${P[2][1]}`);
 document.getElementById("pB").setAttribute("d",
  `M${Q[0][0]} ${Q[0][1]}L${Q[1][0]} ${Q[1][1]}L${Q[2][0]} ${Q[2][1]}`);
 const g=document.getElementById("gap");
 g.setAttribute("x1",P[2][0]);g.setAttribute("y1",P[2][1]);
 g.setAttribute("x2",Q[2][0]);g.setAttribute("y2",Q[2][1]);
 document.getElementById("e1").setAttribute("cx",P[2][0]);
 document.getElementById("e1").setAttribute("cy",P[2][1]);
 document.getElementById("e2").setAttribute("cx",Q[2][0]);
 document.getElementById("e2").setAttribute("cy",Q[2][1]);
 document.getElementById("o").setAttribute("cx",OX);
 document.getElementById("o").setAttribute("cy",OY);
 const d=sub(a2,b2), sep=Math.hypot(d[0],d[1]);
 const gA=mv(HA,sub(z,oA)), gB=mv(HB,sub(z,oB));
 const br=sub(mv(HB,gA),mv(HA,gB));
 document.getElementById("sep").textContent=sep.toFixed(4);
 document.getElementById("pred").textContent=
   (e*e*Math.hypot(br[0],br[1])).toFixed(4);}
eta.addEventListener("input",upd2);upd2();
</script>
"""


def serve(port):
    import http.server
    import socketserver

    body = PAGE.encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    # Bind to loopback only. Reach it through an SSH tunnel, not by opening
    # a security group rule.
    with socketserver.TCPServer(("127.0.0.1", port), H) as srv:
        print(f"\n  serving on http://127.0.0.1:{port}  (loopback only)")
        print(f"\n  From your own machine:")
        print(f"    ssh -L {port}:localhost:{port} ubuntu@<instance>")
        print(f"    then open http://localhost:{port}")
        print("\n  Ctrl-C to stop.\n")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("  stopped.")


LESSONS = {
    "vector": (lesson_vector, "what a vector is; normalizing"),
    "dot": (lesson_dot, "dot product, and cosine as a dot product"),
    "cosine": (lesson_cosine, "why cosine ranks and tangent cannot"),
    "highdim": (lesson_highdim, "how 1024-space defies intuition"),
    "taylor": (lesson_taylor, "local approximation and error rates"),
    "jacobian": (lesson_jacobian, "derivative of a vector field"),
    "hessian": (lesson_hessian, "curvature, eigenvalues, conditioning"),
    "hvp": (lesson_hvp, "Pearlmutter's trick: Hv without H"),
    "bracket": (lesson_bracket, "Lie brackets and training order"),
    "ablation": (lesson_ablation, "which parts of an input do work"),
    "polarity": (lesson_polarity, "the property cosine cannot measure"),
}

ORDER = ["vector", "dot", "cosine", "highdim", "taylor",
         "jacobian", "hessian", "hvp", "bracket", "ablation", "polarity"]


def main():
    global SAVE_DIR, INTERACTIVE
    ap = argparse.ArgumentParser(
        description="Teaching module for the vector calculus behind "
                    "embeddings and training dynamics.")
    ap.add_argument("command", choices=["lessons", "run", "serve"])
    ap.add_argument("name", nargs="?", default="all")
    ap.add_argument("--save", metavar="DIR",
                    help="write plots here instead of showing them")
    ap.add_argument("--interactive", action="store_true",
                    help="matplotlib slider demos; needs a display")
    ap.add_argument("--port", type=int, default=8765,
                    help="with serve: loopback port (default 8765)")
    args = ap.parse_args()

    SAVE_DIR = args.save
    INTERACTIVE = args.interactive

    if args.command == "serve":
        return serve(args.port)

    if args.command == "lessons":
        print("\n  lessons, in the order they build on each other:\n")
        for i, k in enumerate(ORDER, 1):
            print(f"   {i:>2}. {k:<10} {LESSONS[k][1]}")
        print("\n  python3 vectors.py run <name>")
        print("  python3 vectors.py run cosine --interactive")
        print("  python3 vectors.py run all --save plots/\n")
        return

    names = ORDER if args.name == "all" else [args.name]
    for n in names:
        if n not in LESSONS:
            raise SystemExit(f"unknown lesson '{n}'. "
                             f"Try: python3 vectors.py lessons")
        LESSONS[n][0]()
    print()


if __name__ == "__main__":
    sys.exit(main())
