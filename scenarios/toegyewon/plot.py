"""OSM 원본과 SUMO 네트워크 비교. 화면 캡처가 아닌 데이터 기반 정적 도면."""

import os
from pathlib import Path


def plot(out, manifest):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/toegyewon-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import sumolib
    from pyproj import Transformer

    from .network import Source

    src = Source()
    cfg = manifest["config"]
    proj = Transformer.from_crs("EPSG:4326", cfg["projection"], always_xy=True)
    ox, oy = proj.transform(*cfg["origin_lon_lat"])
    fig, axs = plt.subplots(1, 2, figsize=(15, 10), layout="constrained")
    used = {w for e in manifest["edges"].values() for w in e["ways"]}
    for w in used:
        xy = [proj.transform(*p) for p in src.part(w)]
        axs[0].plot(
            [x - ox for x, y in xy], [y - oy for x, y in xy], color="#6c7887", lw=2
        )
    net = sumolib.net.readNet(str(Path(out) / "toegyewon.net.xml"), withInternal=True)
    for e in net.getEdges(withInternal=True):
        for lane in e.getLanes():
            x, y = zip(*lane.getShape())
            axs[1].plot(x, y, color="#97a2af", lw=1)
    for route, color, ls in [("pink", "#e93ba9", "-"), ("green", "#00a85a", "--")]:
        for e in manifest["routes"][route]:
            points = net.getEdge(e).getShape()
            x, y = zip(*points)
            axs[1].plot(x, y, color=color, lw=2.5, ls=ls)
            if len(points) > 2:
                k = len(points) // 2
                axs[1].annotate(
                    "",
                    xy=points[k + 1],
                    xytext=points[k],
                    arrowprops={"arrowstyle": "->", "color": color, "lw": 2},
                )
    for key, xy in manifest["nodes"].items():
        if key in [
            "N_IN",
            "N_OUT",
            "S_IN",
            "S_OUT",
            "W_IN",
            "W_OUT",
            "E_IN",
            "E_MAIN_OUT",
            "E_RAMP_OUT",
        ]:
            for ax in axs:
                ax.scatter(*xy, color="#2255c9", s=30, zorder=4)
                ax.annotate(
                    key,
                    xy,
                    xytext=(
                        (-48, -12)
                        if key == "W_IN"
                        else (-48, 8)
                        if key == "W_OUT"
                        else (5, 8)
                        if key.endswith("IN")
                        else (5, -11)
                    ),
                    textcoords="offset points",
                    fontsize=8,
                    color="#2255c9",
                )
    for label, node in [
        ("weave (4 lanes / ~30 m)", "WEAVE_IN"),
        ("relocated W split", "W_SPLIT"),
    ]:
        axs[1].annotate(
            label,
            manifest["nodes"][node],
            xytext=(50, -35),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->"},
            fontsize=9,
        )
    axs[0].set_title("OSM source geometry (before boundary clipping)")
    axs[1].set_title("SUMO model / pink: N to E ramp / green: S to W")
    for ax in axs:
        ax.set_aspect("equal")
        ax.set_xlim(-10, 600)
        ax.set_ylim(0, 760)
        ax.grid(alpha=0.2)
        ax.set_xlabel("Easting from origin (m)")
        ax.set_ylabel("Northing from origin (m)")
    fig.suptitle(
        "Toegyewon IC — OSM-derived planar model\nSource: OpenStreetMap contributors (ODbL). Scope/relocated W split: user sketch."
    )
    fig.savefig(Path(out) / "comparison.png", dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 6), layout="constrained")
    for x in range(5):
        ax.plot([x, x], [0, 10], color="gray", ls="-" if x in [0, 4] else "--")
    for x, lane in enumerate([3, 2, 1, 0]):
        ax.text(x + 0.5, 5, "lane " + str(lane), ha="center", color="gray")
    ax.annotate(
        "",
        xy=(1.5, 9),
        xytext=(0.5, 1),
        arrowprops={"arrowstyle": "->", "color": "#e93ba9", "lw": 4},
    )
    ax.annotate(
        "",
        xy=(0.5, 9),
        xytext=(1.5, 1),
        arrowprops={"arrowstyle": "->", "color": "#00a85a", "lw": 4},
    )
    ax.text(0.5, -0.4, "Pink entry", ha="center", color="#e93ba9")
    ax.text(1.5, -0.8, "Green entry", ha="center", color="#00a85a")
    ax.text(0.5, 10.3, "Upper loop / W", ha="center")
    ax.text(2.5, 10.3, "East curve / E", ha="center")
    ax.set_title(
        "Required weaving: opposite lane changes on the SAME edge\nSchematic (not geographic scale); SUMO indices count from the right"
    )
    ax.set_xlim(-0.3, 4.3)
    ax.set_ylim(-1.4, 11)
    ax.axis("off")
    fig.savefig(Path(out) / "weave_lanes.png", dpi=170)
    plt.close(fig)
