"""
Generate 9 PNG visualizations for clustering algorithm comparison.

Source of experimental numbers:
- reports/exp01/exp01_baseline_summary.csv (EXP-01 baseline, 5 runs)
- reports/exp03/exp03_selected_configurations.csv (EXP-03 working selection)
- reports/exp05/exp05_reproducibility_aggregate.csv (Block R)

This is documentation/visualization task only:
- No code change to clustering implementation
- No methodology change
- No rerun of experiments
- No ranking/winner/best/optimal claims
"""

import os

import matplotlib.pyplot as plt
from matplotlib.patches import (
    Circle,
    Ellipse,
    FancyArrowPatch,
    FancyBboxPatch,
    Rectangle,
)
import numpy as np
from scipy.spatial import cKDTree

OUT = "/home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml/reports/algorithm_comparison"

# Common visual style — academic / scientific
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.bbox": "tight",
    "savefig.dpi": 160,
    "figure.dpi": 120,
})

COLORS = {
    "kmeans": "#1f77b4",
    "agglomerative": "#2ca02c",
    "dbscan_core": "#1f77b4",
    "dbscan_border": "#9467bd",
    "dbscan_noise": "#7f7f7f",
    "gmm": "#d62728",
    "fcm": "#ff7f0e",
    "text_muted": "#555555",
}

ALG_ORDER = ["kmeans", "agglomerative", "dbscan_core", "gmm", "fcm"]
ALG_COLOR_MAP = {
    "kmeans": "#1f77b4",
    "agglomerative": "#2ca02c",
    "dbscan_core": "#1f77b4",
    "gmm": "#d62728",
    "fcm": "#ff7f0e",
}
ALG_COLOR = [ALG_COLOR_MAP[k] for k in ALG_ORDER]

ALG_TITLE = {
    "kmeans": "K-Means",
    "agglomerative": "Agglomerative",
    "dbscan": "DBSCAN",
    "gmm": "Gaussian Mixture",
    "fcm": "Fuzzy C-Means",
}

DATA_SOURCE_EXP01 = (
    "Nguồn số liệu EXP-01: reports/exp01/exp01_baseline_summary.csv. "
    "5 thuật toán × cùng input (4,371 khách hàng × 14 features, FE-06 C7, seed=42)."
)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def set_axis_clean(ax, xlim=(0, 1), ylim=(0, 1)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")


def title_only(fig, title, y=0.96):
    fig.suptitle(title, fontsize=15, fontweight="bold", y=y)


def footer_source(fig, txt, y=0.02):
    fig.text(0.5, y, txt, ha="center", fontsize=8.5,
             color=COLORS["text_muted"], style="italic")


# =============================================================================
# 01 — Algorithm Taxonomy (5 algorithms card grid)
# =============================================================================

def make_01_taxonomy():
    fig = plt.figure(figsize=(14.0, 6.5))
    fig.suptitle("Taxonomy 5 thuật toán clustering trong nghiên cứu",
                 fontsize=15, fontweight="bold", y=0.965)

    # sub-title in its own axes
    ax_meta = fig.add_axes([0.0, 0.88, 1.0, 0.05])
    ax_meta.axis("off")
    ax_meta.text(0.5, 0.5,
                 "K-Medoids không thuộc phạm vi (ADR-0003 — OUT OF SCOPE cho phase hiện tại).",
                 ha="center", va="center", fontsize=10,
                 color=COLORS["text_muted"])

    ax = fig.add_axes([0.02, 0.08, 0.96, 0.78])
    set_axis_clean(ax, (0, 14.0), (0, 7.0))

    cards = [
        {"key": "kmeans", "alg": "K-Means", "tag": "Centroid-based",
         "rows": [
             ("Paradigm", "Phân hoạch centroid cứng"),
             ("Yêu cầu K", "Bắt buộc K trước"),
             ("Noise", "Không có noise flag"),
             ("Membership", "Hard"),
             ("Cơ chế", "Assign → Update (Euclidean)"),
         ]},
        {"key": "agglomerative", "alg": "Agglomerative", "tag": "Bottom-up hierarchical",
         "rows": [
             ("Paradigm", "Phân cấp bottom-up"),
             ("Yêu cầu K", "Cắt dendrogram ở K"),
             ("Noise", "Không có noise flag"),
             ("Membership", "Hard (sau khi cắt)"),
             ("Cơ chế", "Greedy merge theo linkage"),
         ]},
        {"key": "dbscan", "alg": "DBSCAN", "tag": "Density-based",
         "rows": [
             ("Paradigm", "Dựa trên mật độ"),
             ("Yêu cầu K", "Không cần (realized K)"),
             ("Noise", "Có (label = -1)"),
             ("Membership", "Hard + noise flag"),
             ("Cơ chế", "Core/border/noise qua eps"),
         ]},
        {"key": "gmm", "alg": "GMM", "tag": "Probabilistic",
         "rows": [
             ("Paradigm", "Mô hình xác suất (mixture)"),
             ("Yêu cầu K", "n_components = K"),
             ("Noise", "Không có noise flag"),
             ("Membership", "Soft (responsibility)"),
             ("Cơ chế", "EM log-likelihood Gaussian"),
         ]},
        {"key": "fcm", "alg": "Fuzzy C-Means", "tag": "Soft / Fuzzy",
         "rows": [
             ("Paradigm", "Phân hoạch fuzzy"),
             ("Yêu cầu K", "n_clusters = K"),
             ("Noise", "Không có noise flag"),
             ("Membership", "Soft (U ∈ [0,1])"),
             ("Cơ chế", "Bezdek update với m"),
         ]},
    ]

    box_w = 2.62
    box_h = 5.6
    y0 = 0.6
    gap = 0.13
    total_w = 5 * box_w + 4 * gap
    x0 = (14.0 - total_w) / 2

    for i, c in enumerate(cards):
        x = x0 + i * (box_w + gap)
        color = ALG_COLOR[i]
        # outer
        outer = FancyBboxPatch(
            (x, y0), box_w, box_h,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            linewidth=1.4, edgecolor=color, facecolor="white",
        )
        ax.add_patch(outer)
        # header
        ax.text(x + box_w / 2, y0 + box_h - 0.32, c["alg"],
                ha="center", va="center", fontsize=12.5, fontweight="bold",
                color=color)
        ax.text(x + box_w / 2, y0 + box_h - 0.78, c["tag"],
                ha="center", va="center", fontsize=9, color="#666",
                style="italic")

        rows_top = y0 + box_h - 1.30
        n_rows = len(c["rows"])
        row_h = (rows_top - y0 - 0.15) / n_rows
        for r_i, (label, val) in enumerate(c["rows"]):
            ry = rows_top - (r_i + 1) * row_h
            ax.text(x + 0.15, ry + row_h * 0.65, label,
                    ha="left", va="center", fontsize=9,
                    fontweight="bold", color=COLORS["text_muted"])
            ax.text(x + 0.15, ry + row_h * 0.22, val,
                    ha="left", va="center", fontsize=10, color="#222")

    fig.text(0.5, 0.02, DATA_SOURCE_EXP01, ha="center", fontsize=8.5,
             color=COLORS["text_muted"], style="italic")
    save(fig, "01_algorithm_taxonomy.png")


# =============================================================================
# 02 — K-Means principle (5-panel mechanism)
# =============================================================================

def make_02_kmeans():
    rng = np.random.default_rng(42)
    n = 80
    centers = np.array([[-3, -1.5], [3, -1.5], [-3, 1.5], [3, 1.5]], dtype=float)
    X = np.vstack([c + rng.normal(scale=0.85, size=(n // 4, 2)) for c in centers])

    def assign(X, mu):
        d = np.linalg.norm(X[:, None, :] - mu[None, :, :], axis=2)
        return np.argmin(d, axis=1)

    fig = plt.figure(figsize=(16.0, 4.6))
    fig.suptitle("K-Means — Nguyên lý hoạt động (Lloyd's algorithm)",
                 fontsize=14, fontweight="bold", y=0.97)
    fig.subplots_adjust(top=0.84, bottom=0.20, left=0.04, right=0.98, wspace=0.25)

    axes = [fig.add_subplot(1, 5, i + 1) for i in range(5)]
    cmap = ["#1f77b4", "#2ca02c", "#d62728", "#ff7f0e"]

    # Panel 1: raw
    ax = axes[0]
    ax.scatter(X[:, 0], X[:, 1], s=14, c="#444", alpha=0.7, edgecolors="none")
    ax.set_title("1. Dữ liệu 4,371 khách hàng\n(R¹⁴ minh họa 2D)",
                 fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # Panel 2: init centroids
    ax = axes[1]
    initial_centers = X[rng.choice(len(X), 4, replace=False)]
    ax.scatter(X[:, 0], X[:, 1], s=14, c="#aaa", alpha=0.6, edgecolors="none")
    ax.scatter(initial_centers[:, 0], initial_centers[:, 1],
               s=180, c=cmap,
               marker="X", edgecolors="black", linewidths=1)
    ax.set_title("2. Khởi tạo 4 centroid\n(k-means++, n_init=10)", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # Panel 3: assignment
    ax = axes[2]
    lbls = assign(X, initial_centers)
    for k in range(4):
        ax.scatter(X[lbls == k, 0], X[lbls == k, 1], s=14, c=cmap[k],
                   alpha=0.7, edgecolors="none")
    for k, c in enumerate(initial_centers):
        ax.scatter([c[0]], [c[1]], s=180, c=cmap[k], marker="X",
                   edgecolors="black", linewidths=1)
    ax.set_title("3. Assignment\nđiểm → centroid gần nhất", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # Panel 4: centroid update
    ax = axes[3]
    new_centers = np.array([X[lbls == k].mean(axis=0) for k in range(4)])
    for k in range(4):
        ax.scatter(X[lbls == k, 0], X[lbls == k, 1], s=14, c=cmap[k],
                   alpha=0.6, edgecolors="none")
    for k in range(4):
        ax.annotate("", xy=new_centers[k], xytext=initial_centers[k],
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.4))
    ax.scatter(initial_centers[:, 0], initial_centers[:, 1],
               s=120, c=cmap, marker="X", alpha=0.4,
               edgecolors="black", linewidths=1)
    ax.scatter(new_centers[:, 0], new_centers[:, 1],
               s=200, c=cmap, marker="X", edgecolors="black", linewidths=1)
    ax.set_title("4. Update\ncentroid ← mean(cluster)", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # Panel 5: converged
    ax = axes[4]
    final_centers = np.array([[-3, -1.5], [3, -1.5], [-3, 1.5], [3, 1.5]],
                             dtype=float)
    final_lbls = assign(X, final_centers)
    for k in range(4):
        ax.scatter(X[final_lbls == k, 0], X[final_lbls == k, 1], s=14,
                   c=cmap[k], alpha=0.75, edgecolors="none")
        ax.scatter([final_centers[k, 0]], [final_centers[k, 1]],
                   s=180, c=cmap[k], marker="X", edgecolors="black", linewidths=1)
    ax.set_title("5. Hội tụ\n4 cluster cuối cùng", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    fig.text(0.5, 0.10,
             "Objective: WCSS = Σₖ Σ_{x∈Cₖ} ‖x − μₖ‖²  ·  Working config: n_init=10, init=k-means++, max_iter=300, tol=1e-4.",
             ha="center", fontsize=9, color=COLORS["text_muted"])
    fig.text(0.5, 0.02,
             "Nguồn: docs/research/ML02_KMeans.md; reports/exp01/exp01_baseline_summary.csv "
             "(K-Means baseline K=4: silhouette=0.5681, DBI=0.6128, CH=4819.08).",
             ha="center", fontsize=8.5, color=COLORS["text_muted"],
             style="italic")
    save(fig, "02_kmeans_principle.png")


# =============================================================================
# 03 — Agglomerative principle
# =============================================================================

def make_03_agglomerative():
    X = np.array([
        [-3.0, -1.5],
        [-2.8, -1.2],
        [-2.5, -1.6],
        [3.0, -1.5],
        [2.8, -1.2],
        [-3.0, 1.5],
        [3.0, 1.5],
    ])

    fig = plt.figure(figsize=(15.0, 7.5))
    fig.suptitle("Agglomerative Clustering — Bottom-up hierarchical merging",
                 fontsize=15, fontweight="bold", y=0.985)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.1, 1.0], hspace=0.40, wspace=0.30)

    cmap = ["#1f77b4", "#2ca02c", "#d62728", "#ff7f0e"]

    # Panel A: points
    axA = fig.add_subplot(gs[0, 0])
    axA.scatter(X[:, 0], X[:, 1], s=140, c="white", edgecolors="black", linewidths=1.8)
    for i, (x, y) in enumerate(X):
        axA.text(x + 0.12, y + 0.05, f"x{i + 1}", fontsize=10)
    axA.set_title("1. Khởi tạo — mỗi điểm = 1 cluster", fontsize=11)
    axA.set_xticks([]); axA.set_yticks([])

    # Panel B: pairwise merging
    axB = fig.add_subplot(gs[0, 1])
    groups_B = [(0, 1, 2), (3, 4), (5,), (6,)]
    for gi, grp in enumerate(groups_B):
        axB.scatter(X[list(grp), 0], X[list(grp), 1], s=180,
                    c=cmap[gi], edgecolors="black", linewidths=1.2)
    merges = [((-2.9, -1.35), (-2.6, -1.4)), ((2.9, -1.35), (2.9, -1.32))]
    for (x1, y1), (x2, y2) in merges:
        axB.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle="->", color="#444", lw=1.2))
    axB.set_title("2. Greedy merge theo linkage criterion", fontsize=11)
    axB.set_xticks([]); axB.set_yticks([])

    # Panel C: dendrogram (drawn manually for clarity)
    axD = fig.add_subplot(gs[0, 2])
    leaf_pos = [0.5, 1.0, 1.5, 2.5, 3.0, 4.5, 5.5]
    leaf_labels = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
    # stems
    for i, x in enumerate(leaf_pos):
        axD.plot([x, x], [0, 0.25], color="#222", lw=1)
        axD.text(x, -0.10, leaf_labels[i], ha="center", va="top", fontsize=10)
    # merge1 x1,x2 at h=0.30
    axD.plot([leaf_pos[0], leaf_pos[1]], [0.30, 0.30], color="#222", lw=1)
    axD.plot([leaf_pos[0], leaf_pos[0]], [0.25, 0.30], color="#222", lw=1)
    axD.plot([leaf_pos[1], leaf_pos[1]], [0.25, 0.30], color="#222", lw=1)
    # merge2 x4,x5 at h=0.45
    axD.plot([leaf_pos[3], leaf_pos[4]], [0.45, 0.45], color="#222", lw=1)
    axD.plot([leaf_pos[3], leaf_pos[3]], [0.25, 0.45], color="#222", lw=1)
    axD.plot([leaf_pos[4], leaf_pos[4]], [0.25, 0.45], color="#222", lw=1)
    # merge3 (x1,x2) with x3 at h=0.75
    cx12 = (leaf_pos[0] + leaf_pos[1]) / 2
    axD.plot([cx12, leaf_pos[2]], [0.75, 0.75], color="#222", lw=1)
    axD.plot([leaf_pos[2], leaf_pos[2]], [0.25, 0.75], color="#222", lw=1)
    axD.plot([cx12, cx12], [0.30, 0.75], color="#222", lw=1)
    # merge4 x6 with x7 at h=1.20
    axD.plot([leaf_pos[5], leaf_pos[6]], [1.20, 1.20], color="#222", lw=1)
    axD.plot([leaf_pos[5], leaf_pos[5]], [0.25, 1.20], color="#222", lw=1)
    axD.plot([leaf_pos[6], leaf_pos[6]], [0.25, 1.20], color="#222", lw=1)
    # merge5 (x4,x5) with (x6,x7) at h=1.95
    cx45 = (leaf_pos[3] + leaf_pos[4]) / 2
    cx67 = (leaf_pos[5] + leaf_pos[6]) / 2
    axD.plot([cx45, cx67], [1.95, 1.95], color="#222", lw=1)
    axD.plot([cx45, cx45], [0.45, 1.95], color="#222", lw=1)
    axD.plot([cx67, cx67], [1.20, 1.95], color="#222", lw=1)

    axD.set_xlim(0, 6.5); axD.set_ylim(-0.30, 2.20)
    axD.set_xticks([]); axD.set_yticks([0, 0.30, 0.75, 1.20, 1.95])
    axD.set_yticklabels(["0", "0.30", "0.75", "1.20", "1.95"], fontsize=9)
    axD.set_ylabel("Khoảng cách\nlinkage", fontsize=9)
    axD.spines["bottom"].set_visible(False)
    axD.spines["left"].set_visible(True)
    axD.set_title("3. Dendrogram (linkage height)", fontsize=11)

    # Panel D: cut at K=3
    axC = fig.add_subplot(gs[1, 0])
    cut_groups = [(0, 1, 2, 5), (3, 4), (6,)]
    for gi, grp in enumerate(cut_groups):
        axC.scatter(X[list(grp), 0], X[list(grp), 1], s=180,
                    c=cmap[gi], edgecolors="black", linewidths=1.2)
    axC.text(-3.5, 2.40, "Cắt tại K=3 → 3 cluster",
             color="red", fontsize=10.5, fontweight="bold")
    axC.set_xlim(-3.7, 3.6); axC.set_ylim(-2.05, 2.55)
    axC.set_xticks([]); axC.set_yticks([])
    axC.set_title("4. Cắt dendrogram tại K=3", fontsize=11, pad=10)

    # Panel E: linkage explanation (better spacing)
    axE = fig.add_subplot(gs[1, 1])
    axE.axis("off")
    axE.text(0.05, 0.92, "Linkage rules:", fontsize=12, fontweight="bold",
             transform=axE.transAxes)
    linkages = [
        ("Ward",     "Δ(ESS) — minimize variance sau merge"),
        ("Average",  "Trung bình khoảng cách pairwise"),
        ("Complete", "Max khoảng cách giữa 2 điểm"),
        ("Single",   "Min khoảng cách giữa 2 điểm"),
    ]
    for i, (name, desc) in enumerate(linkages):
        y = 0.78 - i * 0.15
        axE.text(0.04, y, f"• {name}:", fontsize=10.5, fontweight="bold",
                 transform=axE.transAxes)
        axE.text(0.42, y, desc, fontsize=10, transform=axE.transAxes)
    axE.text(0.5, 0.08,
             "EXP-03 working selection: linkage=average, K=3 → silhouette=0.8033.",
             fontsize=9.5, ha="center", color=COLORS["text_muted"],
             style="italic", transform=axE.transAxes)
    axE.set_title("5. Ảnh hưởng của linkage rule", fontsize=11)

    # Panel F: final clusters
    axF = fig.add_subplot(gs[1, 2])
    final_groups = [(0, 1, 2, 5), (3, 4), (6,)]
    for gi, grp in enumerate(final_groups):
        axF.scatter(X[list(grp), 0], X[list(grp), 1], s=180,
                    c=cmap[gi], edgecolors="black", linewidths=1.2)
    axF.set_xlim(-3.7, 3.6); axF.set_ylim(-1.9, 1.9)
    axF.set_xticks([]); axF.set_yticks([])
    axF.set_title("6. Cluster cuối cùng (K=3)", fontsize=11)

    fig.text(0.5, 0.01,
             "Nguồn: docs/research/ML03_Hierarchical_Clustering.md; "
             "reports/exp03/exp03_selected_configurations.csv. "
             "Working config: linkage=ward, metric=euclidean, n_clusters=4. "
             "Linkage rất ảnh hưởng: ward K=4 → silhouette=0.5657, average K=3 → silhouette=0.8033.",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "03_agglomerative_principle.png")


# =============================================================================
# 04 — DBSCAN principle
# =============================================================================

def make_04_dbscan():
    rng = np.random.default_rng(11)
    cluster_a = rng.normal(loc=[-2.5, 1.0], scale=[0.8, 0.5], size=(35, 2))
    cluster_b = rng.normal(loc=[2.2, -1.5], scale=[0.6, 0.7], size=(28, 2))
    cluster_c = rng.normal(loc=[3.5, 2.8], scale=[0.4, 0.3], size=(20, 2))
    sparse = rng.normal(loc=[0.0, 0.0], scale=[2.0, 2.0], size=(20, 2))
    X = np.vstack([cluster_a, cluster_b, cluster_c, sparse])

    eps = 0.85
    min_samples = 5
    tree = cKDTree(X)
    n_in_eps = np.array([len(tree.query_ball_point(p, eps)) - 1 for p in X])

    is_core = n_in_eps >= min_samples
    is_border = np.zeros(len(X), dtype=bool)
    for i, p in enumerate(X):
        if is_core[i]:
            continue
        nbrs = tree.query_ball_point(p, eps)
        if any(is_core[j] for j in nbrs):
            is_border[i] = True
    is_noise = (~is_core) & (~is_border)

    fig = plt.figure(figsize=(15.0, 6.8))
    fig.suptitle("DBSCAN — Density-based clustering (Ester et al., 1996)",
                 fontsize=15, fontweight="bold", y=1.00)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.5, 1.0], wspace=0.25)

    # Left: scatter with eps circles
    axA = fig.add_subplot(gs[0, 0])
    for i, p in enumerate(X):
        if is_core[i]:
            axA.add_patch(Circle(p, eps, fill=False, edgecolor="#888",
                                 linewidth=0.6, alpha=0.4, zorder=1))
    axA.scatter(X[is_core, 0], X[is_core, 1], s=55,
                c=COLORS["dbscan_core"], edgecolors="black", linewidths=0.5,
                label="Core point", zorder=3)
    axA.scatter(X[is_border, 0], X[is_border, 1], s=70, marker="o",
                c=COLORS["dbscan_border"], edgecolors="black", linewidths=0.5,
                label="Border point", zorder=3)
    axA.scatter(X[is_noise, 0], X[is_noise, 1], s=70, marker="X",
                c=COLORS["dbscan_noise"], edgecolors="black", linewidths=0.5,
                label="Noise point (label = -1)", zorder=3)
    axA.set_xticks([]); axA.set_yticks([])
    axA.set_title(f"Phân loại điểm (eps={eps:.2f}, min_samples={min_samples})",
                  fontsize=11)
    axA.legend(loc="upper left", frameon=True, fontsize=9.5)

    # Right: definitions table
    axB = fig.add_subplot(gs[0, 1])
    axB.axis("off")
    axB.set_xlim(0, 1); axB.set_ylim(0, 1)

    axB.text(0.5, 0.96, "Khái niệm cốt lõi", ha="center", fontsize=13,
             fontweight="bold", transform=axB.transAxes)

    defs = [
        ("eps\nNEIGHBOR",
         f"N_eps(x) = {{ x_j | d(x, x_j) ≤ {eps:.2f} }}"),
        ("CORE\npoint",
         f"|N_eps(x)| ≥ min_samples = {min_samples}"),
        ("BORDER\npoint",
         "|N_eps(x)| < min_samples ở trong N_eps của core"),
        ("NOISE\npoint",
         "Không phải core, không phải border → label = -1"),
        ("DENSITY\n-connect",
         "Chuỗi core nối qua N_eps lẫn nhau"),
        ("REALIZED\nK",
         "Không cố định trước — là output thuật toán"),
    ]
    for i, (k, v) in enumerate(defs):
        y = 0.86 - i * 0.13
        axB.add_patch(Rectangle((0.02, y - 0.045), 0.26, 0.10,
                                facecolor="#e9eef6", edgecolor="#aac",
                                linewidth=0.6))
        axB.text(0.15, y + 0.005, k, ha="center", va="center", fontsize=8.5,
                 fontweight="bold", transform=axB.transAxes)
        axB.text(0.30, y + 0.005, v, ha="left", va="center", fontsize=10,
                 transform=axB.transAxes)

    axB.text(0.5, 0.04,
             "Observed evidence (EXP-01): DBSCAN trên RFM Extended (4,371×14, "
             "FE-06 C7) cho 17 cluster và 72.7% noise.",
             ha="center", fontsize=9.5, style="italic",
             color=COLORS["text_muted"], transform=axB.transAxes)
    fig.text(0.5, 0.02,
             "Nguồn: docs/research/ML04_DBSCAN.md; "
             "reports/exp01/exp01_baseline_summary.csv (DBSCAN row). "
             "Silhouette không nên dùng để đánh giá DBSCAN (AGENTS.md §3).",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "04_dbscan_principle.png")


# =============================================================================
# 05 — GMM principle
# =============================================================================

def make_05_gmm():
    rng = np.random.default_rng(123)
    A = rng.normal(loc=[-2.2, -1.0], scale=[1.0, 0.4], size=(220, 2))
    B = rng.normal(loc=[2.2, -1.2], scale=[0.5, 0.8], size=(180, 2))
    C = rng.normal(loc=[0.0, 1.6], scale=[1.3, 0.3], size=(140, 2))
    X = np.vstack([A, B, C])

    fig = plt.figure(figsize=(15.0, 6.8))
    fig.suptitle("Gaussian Mixture Model — Probabilistic clustering (EM algorithm)",
                 fontsize=15, fontweight="bold", y=1.00)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.4, 1.0], wspace=0.30)

    # Left: 3 Gaussians + data
    axA = fig.add_subplot(gs[0, 0])
    axA.scatter(X[:, 0], X[:, 1], s=12, c="#444", alpha=0.4, edgecolors="none",
                zorder=1)
    centers = [(-2.2, -1.0), (2.2, -1.2), (0.0, 1.6)]
    covs = [[[1.0, 0.0], [0.0, 0.16]],
            [[0.25, 0.0], [0.0, 0.64]],
            [[1.69, 0.0], [0.0, 0.09]]]
    colors = ["#1f77b4", "#d62728", "#2ca02c"]
    for c, cov, col in zip(centers, covs, colors):
        eigvals, eigvecs = np.linalg.eigh(np.array(cov))
        order = eigvals.argsort()[::-1]
        eigvals, eigvecs = eigvals[order], eigvecs[:, order]
        a = 2 * np.sqrt(eigvals[0])
        b = 2 * np.sqrt(eigvals[1])
        angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
        for mult in [1, 2, 3]:
            ell = Ellipse(c, a * mult, b * mult, angle=angle,
                          facecolor=col, alpha=0.08, edgecolor=col,
                          linewidth=0.9, zorder=2)
            axA.add_patch(ell)
        axA.scatter([c[0]], [c[1]], s=180, c=col, marker="X",
                    edgecolors="black", linewidths=1, zorder=4)
        axA.text(c[0], c[1] - 0.60, "μₖ", fontsize=12, ha="center",
                 color=col, fontweight="bold")

    axA.set_title("K Gaussian component: p(x) = Σₖ πₖ · N(x | μₖ, Σₖ)",
                  fontsize=11)
    axA.set_xticks([]); axA.set_yticks([])
    axA.set_xlim(-5, 5); axA.set_ylim(-3.5, 3.5)

    # Right: responsibilities + convention
    axB = fig.add_subplot(gs[0, 1])
    axB.axis("off")
    axB.set_xlim(0, 1); axB.set_ylim(0, 1)

    axB.text(0.5, 0.95, "Responsibility matrix γ(z_ik)",
             ha="center", fontsize=13, fontweight="bold",
             transform=axB.transAxes)
    axB.text(0.5, 0.88,
             "γ(z_ik) = πₖ N(x_i | μₖ, Σₖ) / Σⱼ πⱼ N(x_i | μⱼ, Σⱼ)",
             ha="center", fontsize=10, style="italic",
             transform=axB.transAxes)

    n_demo, k_demo = 5, 3
    rng2 = np.random.default_rng(2)
    R = rng2.dirichlet(np.ones(k_demo) * 2, size=n_demo)
    cell_w, cell_h = 0.12, 0.06
    bx, by = 0.20, 0.42
    for i in range(n_demo):
        for k in range(k_demo):
            v = R[i, k]
            axB.add_patch(Rectangle(
                (bx + k * cell_w, by + (n_demo - 1 - i) * cell_h),
                cell_w * 0.95, cell_h * 0.85,
                facecolor=plt.cm.Reds(0.15 + 0.75 * v),
                edgecolor="white"))
            axB.text(bx + k * cell_w + cell_w * 0.5,
                     by + (n_demo - 1 - i) * cell_h + cell_h * 0.42,
                     f"{v:.2f}", ha="center", va="center", fontsize=8,
                     transform=axB.transAxes)
    for k in range(k_demo):
        axB.text(bx + k * cell_w + cell_w * 0.5,
                 by + n_demo * cell_h + 0.015,
                 f"k={k + 1}", ha="center", va="bottom", fontsize=9,
                 transform=axB.transAxes, fontweight="bold")
    axB.text(bx - 0.04, by + n_demo * cell_h / 2,
             "khách hàng i", ha="right", va="center", fontsize=9.5,
             transform=axB.transAxes, rotation=90)

    axB.text(0.5, 0.24,
             "Soft: mỗi x_i có responsibility cho mọi k (Σₖ γ(z_ik) = 1)",
             ha="center", fontsize=10, transform=axB.transAxes)
    axB.text(0.5, 0.18,
             "Hard convention trong project:\nhard_label(i) = argmaxₖ γ(z_ik)",
             ha="center", fontsize=10.5, fontweight="bold",
             color="#9c2a2a", transform=axB.transAxes)
    axB.text(0.5, 0.06,
             "Covariance types: full / tied / diag / spherical. "
             "EXP-03 working: tied, n_components=4 → silhouette=0.5702.",
             ha="center", fontsize=9.5, style="italic",
             color=COLORS["text_muted"], transform=axB.transAxes)
    fig.text(0.5, 0.02,
             "Nguồn: docs/research/ML05_GMM.md; reports/exp01/exp01_baseline_summary.csv; "
             "reports/exp03/exp03_selected_configurations.csv (GMM row).",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "05_gmm_principle.png")


# =============================================================================
# 06 — Fuzzy C-Means principle
# =============================================================================

def make_06_fuzzy():
    rng = np.random.default_rng(31)
    A = rng.normal(loc=[-2.0, -1.0], scale=[0.9, 0.5], size=(140, 2))
    B = rng.normal(loc=[2.0, -1.0], scale=[0.7, 0.6], size=(130, 2))
    X = np.vstack([A, B])
    centroids = np.array([[-1.95, -0.95], [1.95, -0.95]])

    n_demo, k_demo = 6, 3
    rng2 = np.random.default_rng(99)
    U_demo = rng2.dirichlet(np.ones(k_demo) * 1.8, size=n_demo)

    fig = plt.figure(figsize=(15.0, 6.8))
    fig.suptitle("Fuzzy C-Means — Soft partition với fuzziness parameter m",
                 fontsize=15, fontweight="bold", y=1.00)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.4, 1.0], wspace=0.30)

    axA = fig.add_subplot(gs[0, 0])
    cmap_p = ["#1f77b4", "#d62728", "#2ca02c"]
    d1 = np.linalg.norm(X - centroids[0], axis=1)
    d2 = np.linalg.norm(X - centroids[1], axis=1)
    dom = (d1 < d2).astype(int)
    mixed = 0.4 < (1 - np.abs(d1 - d2) / (d1 + d2 + 1e-9))
    for k in range(2):
        axA.scatter(X[dom == k, 0], X[dom == k, 1], s=14,
                    c=cmap_p[k], alpha=0.4, edgecolors="none")
    axA.scatter(X[mixed, 0], X[mixed, 1], s=24,
                c="#bdb76b", alpha=0.7, edgecolors="black", linewidths=0.4,
                label="Mixed membership")
    axA.scatter(centroids[:, 0], centroids[:, 1], s=200, c=cmap_p[:2],
                marker="X", edgecolors="black", linewidths=1.2,
                label="Centroid cₖ")
    axA.legend(loc="lower left", fontsize=9.5)
    idx_mixed = np.where(mixed)[0][:8]
    for i in idx_mixed:
        for k in range(2):
            w = 1.0 if k == dom[i] else 0.35
            axA.annotate("", xy=centroids[k], xytext=X[i],
                         arrowprops=dict(arrowstyle="-",
                                         color=cmap_p[k], lw=w, alpha=0.45))
    axA.set_xticks([]); axA.set_yticks([])
    axA.set_title("Mỗi điểm ∈ tất cả cluster với membership degree",
                  fontsize=11)
    axA.set_xlim(-5, 5); axA.set_ylim(-3.5, 3.5)

    axB = fig.add_subplot(gs[0, 1])
    axB.axis("off")
    axB.set_xlim(0, 1); axB.set_ylim(0, 1)

    axB.text(0.5, 0.95, "Ma trận membership U ∈ [0,1]^(N×K)",
             ha="center", fontsize=13, fontweight="bold",
             transform=axB.transAxes)
    axB.text(0.5, 0.88,
             "Σₖ U[i, k] = 1,  ∀ i;    U[i, k] ≥ 0,  ∀ (i, k)",
             ha="center", fontsize=10, style="italic",
             transform=axB.transAxes)

    cell_w, cell_h = 0.10, 0.052
    bx, by = 0.25, 0.42
    for i in range(n_demo):
        for k in range(k_demo):
            v = U_demo[i, k]
            axB.add_patch(Rectangle(
                (bx + k * cell_w, by + (n_demo - 1 - i) * cell_h),
                cell_w * 0.95, cell_h * 0.85,
                facecolor=plt.cm.YlOrRd(0.15 + 0.75 * v),
                edgecolor="white"))
            axB.text(bx + k * cell_w + cell_w * 0.5,
                     by + (n_demo - 1 - i) * cell_h + cell_h * 0.42,
                     f"{v:.2f}", ha="center", va="center", fontsize=8,
                     transform=axB.transAxes)
    for k in range(k_demo):
        axB.text(bx + k * cell_w + cell_w * 0.5,
                 by + n_demo * cell_h + 0.015,
                 f"k={k + 1}", ha="center", va="bottom", fontsize=9,
                 transform=axB.transAxes, fontweight="bold")
    axB.text(bx - 0.04, by + n_demo * cell_h / 2,
             "khách hàng i", ha="right", va="center", fontsize=9.5,
             transform=axB.transAxes, rotation=90)

    axB.text(0.5, 0.30,
             "J_m = Σᵢ Σₖ (U[i,k])^m · ‖x_i − cₖ‖²       (m > 1)",
             ha="center", fontsize=10, transform=axB.transAxes)
    axB.text(0.5, 0.22, "Bezdek update:",
             ha="center", fontsize=10.5, fontweight="bold",
             transform=axB.transAxes)
    axB.text(0.5, 0.18,
             "U[i,k] = 1 / Σⱼ (‖x_i − cₖ‖ / ‖x_i − cⱼ‖)^(2/(m−1))",
             ha="center", fontsize=10, style="italic",
             transform=axB.transAxes)
    axB.text(0.5, 0.10,
             "Hard convention trong project:\nhard_label(i) = argmaxₖ U[i, k]",
             ha="center", fontsize=10.5, fontweight="bold",
             color="#9c2a2a", transform=axB.transAxes)
    fig.text(0.5, 0.04,
             "EXP-03 working: K=3, m=1.5 → silhouette=0.6296. "
             "Custom NumPy impl, m∈{1.5,2.0,2.5,3.0} explored.",
             ha="center", fontsize=9.5, color=COLORS["text_muted"], style="italic")
    fig.text(0.5, 0.02,
             "Nguồn: docs/research/ML06_Fuzzy_CMeans.md; reports/exp01/exp01_baseline_summary.csv; "
             "reports/exp03/exp03_selected_configurations.csv (FCM row).",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "06_fuzzy_cmeans_principle.png")


# =============================================================================
# 07 — Customer segmentation pipeline
# =============================================================================

def make_07_pipeline():
    fig = plt.figure(figsize=(17.0, 7.8))
    fig.suptitle("Pipeline Customer Segmentation trong nghiên cứu",
                 fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.945,
             "FE-02 → FE-04 → FE-05 → FE-06 C7 → 5 algorithms (EPIC-06) → "
             "EPIC-07 (185 runs) → EPIC-08 → EPIC-09",
             ha="center", fontsize=10, color=COLORS["text_muted"])

    ax = fig.add_axes([0.02, 0.08, 0.96, 0.82])
    set_axis_clean(ax, (0, 17.0), (0, 6.6))

    stages = [
        {"x": 0.20, "title": "1. Dữ liệu", "color": "#a6cee3",
         "steps": ["UCI Online Retail\nADR-0001",
                   "FE-02 cleaning\n(invalid, duplicate)"],
         "label": "DS-05 / FE-01 / FE-02"},
        {"x": 3.50, "title": "2. Customer-level aggregation", "color": "#1f78b4",
         "steps": ["FE-04 customer\naggregation",
                   "FE-05 RFM +\nextended features"],
         "label": "FE-04 / FE-05"},
        {"x": 6.80, "title": "3. 14-feature RFM Extended", "color": "#b2df8a",
         "steps": ["Recency / Frequency /\nMonetary + 11 metrics",
                   "median imputation\n(không đủ NaN)"],
         "label": "FE-05"},
        {"x": 10.10, "title": "4. FE-06 C7 (Preprocessing)", "color": "#33a02c",
         "steps": ["Yeo-Johnson\ntransformation",
                   "RobustScaler\n(IQR = 1)"],
         "label": "FE-06 C7 · 4,371×14"},
        {"x": 13.40, "title": "5. 5 Clustering algorithms", "color": "#fb9a99",
         "steps": ["K-Means", "Agglomerative", "DBSCAN", "GMM", "Fuzzy C-Means"],
         "label": "EPIC-06", "vertical": True},
    ]

    sub_w = 2.95
    sub_h = 3.3

    for s in stages:
        x0 = s["x"]
        # header band
        ax.add_patch(FancyBboxPatch((x0, 5.20), sub_w, 0.50,
                                    boxstyle="round,pad=0.02,rounding_size=0.06",
                                    facecolor=s["color"],
                                    edgecolor="#222", linewidth=1.2))
        ax.text(x0 + sub_w / 2, 5.45, s["title"],
                ha="center", va="center", fontsize=11, fontweight="bold",
                color="white")
        # label placed below header but above content boxes
        ax.text(x0 + sub_w / 2, 4.90, s["label"],
                ha="center", va="center", fontsize=9, color=COLORS["text_muted"])

        for j, st in enumerate(s["steps"]):
            if s.get("grid"):
                col = j % 5
                bx = x0 + 0.06 + col * (sub_w - 0.12) / 5
                by = 3.20
                bh = 1.50
                bbw = (sub_w - 0.12) / 5 - 0.04
            elif s.get("vertical"):
                # 5 algorithms stacked vertically with adequate width
                # Available vertical space: from 4.20 down to 1.65
                # (= 2.55 total), 5 boxes of height 0.48 + gap 0.04
                n = len(s["steps"])
                y_top = 4.20
                box_h = 0.48
                gap = 0.04
                by = y_top - j * (box_h + gap)
                bx = x0 + 0.15
                bh = box_h
                bbw = sub_w - 0.30
            else:
                bx = x0 + 0.10
                by = 3.60 - j * 1.65
                bh = 1.40
                bbw = sub_w - 0.20
            box = FancyBboxPatch(
                (bx, by), bbw, bh,
                boxstyle="round,pad=0.02,rounding_size=0.05",
                facecolor="white", edgecolor=s["color"],
                linewidth=1.2,
            )
            ax.add_patch(box)
            # shrink fontsize for tight algorithm boxes
            fs = 8.5 if (s.get("grid") or s.get("vertical")) else 9.2
            ax.text(bx + bbw / 2, by + bh / 2, st,
                    ha="center", va="center", fontsize=fs)

    for i, s in enumerate(stages[:-1]):
        x1 = s["x"] + sub_w
        x2 = stages[i + 1]["x"]
        ar = FancyArrowPatch((x1, 5.45), (x2, 5.45),
                             arrowstyle="-|>", mutation_scale=14,
                             color="#333", linewidth=1.4)
        ax.add_patch(ar)

    # Down arrow from "5 algorithms" stage to EPIC-07 banner
    ar = FancyArrowPatch((15.85, 5.20), (15.85, 1.10),
                         arrowstyle="-|>", mutation_scale=14,
                         color="#333", linewidth=1.4)
    ax.add_patch(ar)

    # EPIC-07 banner — moved further down to avoid label overlap
    extra_w = sub_w * 5 + 4 * 0.30
    ax.add_patch(FancyBboxPatch(
        (0.20, 0.40), extra_w, 0.55,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor="#fff7bc", edgecolor="#222", linewidth=1.2))
    ax.text(extra_w / 2 + 0.50, 0.68,
            "EPIC-07 (185 runs: EXP-01..05) → EPIC-08 (evaluation) → EPIC-09 (segment profiling)",
            ha="center", va="center", fontsize=10.5, fontweight="bold")

    fig.text(0.5, 0.02,
             "Số liệu khóa: 4,371 khách hàng × 14 features; "
             "input SHA ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c. "
             "Algorithm scope = 5 (per ADR-0003); K-Medoids OUT OF SCOPE.",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "07_customer_segmentation_pipeline.png")


# =============================================================================
# 08 — Algorithm theory comparison
# =============================================================================

def make_08_theory_comparison():
    rows = [
        ("paradigm",
         "Centroid\nphân hoạch",
         "Phân cấp\nbottom-up",
         "Mật độ",
         "Mô hình\nxác suất",
         "Phân hoạch\nfuzzy"),
        ("yêu cầu K",
         "Bắt buộc K",
         "Cắt dendrogram\nở K",
         "Không cần\n(realized K)",
         "n_components\n= K",
         "n_clusters\n= K"),
        ("noise",
         "Không có\nnoise flag",
         "Không có\nnoise flag",
         "Có\n(label = -1)",
         "Không\n(soft)",
         "Không\n(soft)"),
        ("membership",
         "Hard",
         "Hard\n(sau cắt)",
         "Hard + noise",
         "Soft\n(responsibility)",
         "Soft\n(U ∈ [0,1])"),
        ("cluster\nshape",
         "Isotropic\n(Euclidean)",
         "Tùy linkage",
         "Bất kỳ\n(density)",
         "Ellipsoidal",
         "Isotropic"),
        ("strength",
         "Nhanh; tốt\ncho cluster\nspherical",
         "Dendrogram\nminh họa trực\nquan",
         "Phát hiện\ncluster không\nconvex + noise",
         "Soft probability;\nmodel-based",
         "Soft\nmembership;\nbezdek"),
        ("limitation",
         "Nhạy outlier;\nkhông có soft",
         "O(N²);\nnhạy linkage",
         "Nhạy eps/\nmin_samples;\ncurse of D",
         "Full covariance\nquá nhiều param",
         "Custom impl;\nnhạy m"),
    ]

    cols = ["K-Means", "Agglomerative", "DBSCAN", "GMM", "Fuzzy C-Means"]

    n_rows = len(rows) + 1
    col0_w = 1.6
    data_w = 2.42

    fig = plt.figure(figsize=(15.5, 8.4))
    fig.suptitle("So sánh 5 thuật toán — theoretical dimensions",
                 fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.94,
             "Không có ranking. Mỗi algorithm có giả định và hành vi riêng; "
             "so sánh chỉ ở mức observation.",
             ha="center", fontsize=10, color=COLORS["text_muted"])

    ax = fig.add_axes([0.04, 0.05, 0.92, 0.87])
    ax.axis("off")
    ax.set_xlim(0, col0_w + data_w * len(cols))
    ax.set_ylim(0, n_rows)

    ax.add_patch(Rectangle((0, n_rows - 1), col0_w, 1,
                           facecolor="#222", edgecolor="white"))
    ax.text(col0_w / 2, n_rows - 0.5, "Tiêu chí",
            ha="center", va="center", fontsize=11, color="white",
            fontweight="bold")

    for i, c in enumerate(cols):
        x = col0_w + i * data_w
        ax.add_patch(Rectangle((x, n_rows - 1), data_w, 1,
                               facecolor=ALG_COLOR[i],
                               edgecolor="white"))
        ax.text(x + data_w / 2, n_rows - 0.5, c,
                ha="center", va="center", fontsize=11, color="white",
                fontweight="bold")

    for r, row in enumerate(rows):
        y_top = n_rows - 2 - r
        ax.add_patch(Rectangle((0, y_top), col0_w, 1,
                               facecolor="#dde6ef", edgecolor="white"))
        ax.text(col0_w / 2, y_top + 0.5, row[0],
                ha="center", va="center", fontsize=10.5, fontweight="bold")
        for i, val in enumerate(row[1:]):
            x = col0_w + i * data_w
            bg = "#ffffff" if r % 2 == 0 else "#f3f3f3"
            ax.add_patch(Rectangle((x, y_top), data_w, 1,
                                   facecolor=bg, edgecolor="#bbb"))
            ax.text(x + data_w / 2, y_top + 0.5, val,
                    ha="center", va="center", fontsize=9.5)

    fig.text(0.5, 0.02,
             "Nguồn: docs/research/ALGORITHM_THEORY_AND_EXPERIMENTAL_COMPARISON.md §10; "
             "ADR-0003 (algorithm scope). K-Medoids không nằm trong bảng này.",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "08_algorithm_theory_comparison.png")


# =============================================================================
# 09 — Experimental comparison
# =============================================================================

def make_09_experimental_comparison():
    algorithms = ["K-Means\n(K=4)",
                  "Agglomerative\n(ward, K=4)",
                  "DBSCAN\n(eps=0.5)",
                  "GMM\n(full, K=4)",
                  "Fuzzy C-Means\n(m=2.0, K=4)"]
    silhouette = np.array([0.5681, 0.5657, -0.1041, 0.1843, 0.2691])
    dbi = np.array([0.6128, 0.7360, 0.7721, 3.7486, 1.3709])
    ch = np.array([4819.08, 4578.83, 49.18, 131.73, 3869.05])
    wcss = np.array([179858.91, 187019.54, 2125.13, 710957.20, 211949.22])
    runtime = np.array([0.0476, 0.5663, 0.1083, 0.5189, 0.0658])
    colors_bar = ALG_COLOR

    fig = plt.figure(figsize=(16.5, 12.5))
    fig.suptitle("Experimental comparison — 5 thuật toán trên 4,371 khách hàng × 14 features",
                 fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.955,
             "Số liệu từ EXP-01 baseline (K-Means/Agglomerative/GMM/FCM dùng K=4 working config; "
             "DBSCAN dùng working hyperparameters eps=0.5, min_samples=5).",
             ha="center", fontsize=10, color=COLORS["text_muted"])

    # Bigger vertical separation to prevent title vs xlabel overlap
    axes = [fig.add_subplot(2, 3, i + 1) for i in range(6)]
    plt.subplots_adjust(left=0.07, right=0.96, top=0.90, bottom=0.10,
                        hspace=0.65, wspace=0.32)

    def bar_with_labels(ax, values, ylabel, title, ymin=None, ymax=None,
                        fmt="{:.4f}", fmt_mult=1.05):
        ax.bar(algorithms, values, color=colors_bar, edgecolor="black", linewidth=0.5)
        rng = (max(values) - min(values)) if not ymin else max(values) - ymin
        head = max(rng * 0.10, 0.02 * (max(values) if max(values) > 0 else 1))
        for i, v in enumerate(values):
            ax.text(i, v + head * (1 if v >= 0 else -1), fmt.format(v),
                    ha="center", fontsize=9)
        ax.set_ylabel(ylabel, labelpad=10)
        ax.set_title(title, fontsize=11, pad=12)
        if ymin is not None:
            ax.set_ylim(ymin, ymax)
        ax.tick_params(axis="x", labelsize=8.5)

    # 1: silhouette
    bar_with_labels(axes[0], silhouette,
                    "Silhouette (cao = tốt hơn)",
                    "Silhouette Score\n(internal quality, hard label)",
                    ymin=-0.20, ymax=0.75)
    axes[0].axhline(0, color="black", lw=0.5)

    # 2: DBI
    bar_with_labels(axes[1], dbi,
                    "DBI (thấp = tốt hơn)",
                    "Davies-Bouldin Index",
                    ymin=0, ymax=max(dbi) * 1.20,
                    fmt="{:.4f}", fmt_mult=1.05)

    # 3: CH
    bar_with_labels(axes[2], ch,
                    "CH (cao = tốt hơn)",
                    "Calinski-Harabasz Index",
                    ymin=0, ymax=max(ch) * 1.20,
                    fmt="{:.1f}", fmt_mult=1.05)

    # 4: runtime log
    ax = axes[3]
    ax.bar(algorithms, runtime, color=colors_bar, edgecolor="black", linewidth=0.5)
    ax.set_yscale("log")
    for i, v in enumerate(runtime):
        ax.text(i, v * 1.20, f"{v:.4f}s", ha="center", fontsize=9)
    ax.set_ylabel("Runtime log scale (giây)", labelpad=10)
    ax.set_title("Runtime — algorithm execution time\n(EXP-01 baseline, n_repeat=5)",
                 fontsize=11, pad=12)
    ax.tick_params(axis="x", labelsize=8.5)

    # 5: WCSS
    bar_with_labels(axes[4], wcss,
                    "WCSS (diagnostic only)",
                    "WCSS (diagnostic only — applied per\nalgorithm's own logic)",
                    ymin=0, ymax=max(wcss) * 1.20,
                    fmt="{:.0f}", fmt_mult=1.05)

    # 6: cluster structure
    realized_k = [4, 4, 17, 4, 4]
    noise_pct = [0.0, 0.0, 0.7268 * 100, 0.0, 0.0]
    x_pos = np.arange(len(algorithms))
    w = 0.4
    ax = axes[5]
    ax.bar(x_pos - w / 2, realized_k, width=w, color="#1f77b4",
           edgecolor="black", linewidth=0.5, label="Realized K (cluster)")
    ax62 = ax.twinx()
    ax62.bar(x_pos + w / 2, noise_pct, width=w, color="#888",
             edgecolor="black", linewidth=0.5, label="Noise (% customers)")
    ax.set_ylabel("Realized K (count)", color="#1f77b4", labelpad=10)
    ax62.set_ylabel("Noise ratio (%)", color="#444", labelpad=10)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(algorithms, fontsize=8.5)
    ax.set_title("Cluster structure / noise\nDBSCAN: K=17 realized, noise ≈72.7%",
                 fontsize=11, pad=12)
    ax.legend(loc="upper left", fontsize=8.5)
    ax62.legend(loc="upper right", fontsize=8.5)
    ax.set_ylim(0, max(realized_k) * 1.30)
    ax62.set_ylim(0, max(noise_pct) * 1.30 + 5)

    fig.text(0.5, 0.045,
             "KHÔNG có overall ranking — mỗi panel là observed evidence. "
             "Silhouette không nên dùng để đánh giá DBSCAN (AGENTS.md §3). "
             "WCSS không phù hợp cho GMM (GMM tối ưu log-likelihood).",
             ha="center", fontsize=9.5, color=COLORS["text_muted"], style="italic")
    fig.text(0.5, 0.02,
             "Nguồn: reports/exp01/exp01_baseline_summary.csv "
             "(silhouette/DBI/CH/WCSS/runtime cho 5 algorithm); "
             "DBSCAN noise_ratio=0.7268, noise_count=3177, realized K=17 cùng nguồn.",
             ha="center", fontsize=8.5, color=COLORS["text_muted"], style="italic")
    save(fig, "09_algorithm_experimental_comparison.png")


if __name__ == "__main__":
    make_01_taxonomy()
    make_02_kmeans()
    make_03_agglomerative()
    make_04_dbscan()
    make_05_gmm()
    make_06_fuzzy()
    make_07_pipeline()
    make_08_theory_comparison()
    make_09_experimental_comparison()
    print("All 9 PNG files generated in:", OUT)
