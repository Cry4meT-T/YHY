# -*- coding: utf-8 -*-
"""
② 戴维南定理验证 —— 手算 + PySpice 仿真对比
================================================

【含源二端网络】（端口 A - B，B 为地）
        +----[ R1 = 1kΩ ]----+---------o  A
        |                    |
     [ Vs = 12V ]         [ R2 = 1kΩ ]
        |                    |
        +--------------------+---------o  B (GND)

【待验证结论】任何线性含源二端网络，对外都可等效成
        Vth（开路电压）串联 Rth（等效内阻）的一个电压源。

【本脚本做四件事】
 1. 手算：Vth（开路电压）、Isc（短路电流）、Rth（= Vth/Isc = R1∥R2）；
 2. 仿真一：开路仿真量 V_oc；仿真二：短路仿真量 I_sc（用 0V 电压源当电流表）；
 3. 仿真三：原网络接负载 RL，量 V_L / I_L；再用「等效电路 + 同一负载」再仿真一次，
    两次结果对比，验证等效替换成立；
 4. 打印「理论值 vs 仿真值」对比表，写入 out/thevenin_report.md。

【需要环境】pip install PySpice numpy matplotlib
"""

import os
import sys

# Windows 控制台默认 GBK，统一改成 UTF-8 输出（终端乱码就先 chcp 65001）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

VS = 12.0        # V
R1 = 1e3         # Ω（单位就是欧姆，下面用 R1 @ u_Ohm）
R2 = 1e3         # Ω
RL_LIST = [500.0, 1500.0]   # 两个验证负载

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- 手算
VTH = VS * R2 / (R1 + R2)          # 分压：开路时 A 点电压
RTH = R1 * R2 / (R1 + R2)          # 把电压源短路后从端口看进去的电阻
ISC = VS / R1                       # 短路时 R2 被短路，只剩 Vs 串 R1


def load_result(rl, vth=VTH, rth=RTH):
    """等效电路的负载解"""
    il = vth / (rth + rl)
    return vth * rl / (rth + rl), il


# ---------------------------------------------------------------- 仿真
def run_pyspice():
    lib = os.environ.get("NGSPICE_LIB")
    if lib:
        import PySpice.Spice.NgSpice.Shared as _shared
        _shared.NgSpiceShared.LIBRARY_PATH = lib

    from PySpice.Spice.Netlist import Circuit
    from PySpice.Unit import u_V, u_Ohm

    def op(circuit):
        sim = circuit.simulator(temperature=25, nominal_temperature=25)
        return sim.operating_point()

    def val(analysis, node):
        return float(np.array(analysis[node]).astype(float).ravel()[-1])

    def branch(analysis, name):
        """取电压源支路电流。PySpice 里分支名是设备名小写（V('s') → 'vs'），
        这里对 'vs' / 's' 两种写法都做兼容，避免不同版本取不到。
        符号约定：0V 电压源当电流表时，读数为正 = 电流从它的正端流出。"""
        keys = list(analysis.branches.keys())
        for cand in ("v" + name, name):
            for k in keys:
                if k.lower() == cand.lower():
                    return float(np.array(analysis.branches[k]).astype(float).ravel()[-1])
        raise KeyError("找不到支路 %s，可用：%s" % (name, keys))

    res = {}

    # ---- 1) 原网络：开路电压 ----
    c = Circuit("Thevenin - open circuit")
    c.V("s", "n1", c.gnd, VS @ u_V)
    c.R(1, "n1", "a", R1 @ u_Ohm)
    c.R(2, "a", c.gnd, R2 @ u_Ohm)
    an = op(c)
    res["voc"] = val(an, "a")

    # ---- 2) 原网络：短路电流（0V 电压源串在端口里 = 理想电流表） ----
    c = Circuit("Thevenin - short circuit")
    c.V("s", "n1", c.gnd, VS @ u_V)
    c.R(1, "n1", "a", R1 @ u_Ohm)
    c.R(2, "a", c.gnd, R2 @ u_Ohm)
    c.V("ammeter", "a", c.gnd, 0 @ u_V)
    an = op(c)
    res["isc"] = branch(an, "ammeter")          # 正号即「从端口 A 流向地」的电流

    # ---- 3) 原网络 + 负载（负载支路里串一个 0V 电源当电流表，直接测 I_L） ----
    res["orig"] = {}
    for rl in RL_LIST:
        c = Circuit("Thevenin - original with load %g" % rl)
        c.V("s", "n1", c.gnd, VS @ u_V)
        c.R(1, "n1", "a", R1 @ u_Ohm)
        c.R(2, "a", c.gnd, R2 @ u_Ohm)
        c.V("amm", "a", "l", 0 @ u_V)           # 理想电流表（0V）
        c.R("L", "l", c.gnd, rl @ u_Ohm)
        an = op(c)
        res["orig"][rl] = (val(an, "l"), branch(an, "amm"))

    # ---- 4) 等效电路（Vth + Rth）+ 同一负载 ----
    res["eqv"] = {}
    for rl in RL_LIST:
        c = Circuit("Thevenin - equivalent with load %g" % rl)
        c.V("th", "a", c.gnd, VTH @ u_V)
        c.R("th", "a", "out", RTH @ u_Ohm)
        c.R("L", "out", c.gnd, rl @ u_Ohm)
        an = op(c)
        # 电源支路电流为负（电流从 + 端流出），取负号得到负载电流
        res["eqv"][rl] = (val(an, "out"), -branch(an, "th"))

    return res


# ---------------------------------------------------------------- 画图
def plot_network(path):
    """画出「自己画的含源二端网络图（标注端口）」"""
    fig, ax = plt.subplots(figsize=(6.6, 4.2), dpi=130)
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)

    def wire(p, q):
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#333", lw=1.6, zorder=1)

    def box(cx, cy, label, w=1.5, h=0.85, color="#fff"):
        ax.add_patch(plt.Rectangle((cx - w / 2, cy - h / 2), w, h, fill=True,
                                   facecolor=color, edgecolor="#333", lw=1.6, zorder=2))
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9, zorder=3)

    box(1.6, 3.5, "Vs\n12V", 1.6, 1.2, "#fff3cd")
    wire((1.6, 4.1), (1.6, 5.4))
    wire((1.6, 5.4), (4.0, 5.4))
    box(5.0, 5.4, "R1 = 1kΩ", 1.9, 0.85, "#d1ecf1")
    wire((5.95, 5.4), (8.2, 5.4))
    ax.plot([8.6], [5.4], "o", color="#333")
    ax.text(8.75, 5.45, "A", fontsize=11)
    wire((1.6, 2.9), (1.6, 1.6))
    wire((1.6, 1.6), (8.2, 1.6))
    ax.plot([8.6], [1.6], "o", color="#333")
    ax.text(8.75, 1.55, "B (GND)", fontsize=10)
    wire((7.6, 5.4), (7.6, 4.6))
    box(7.6, 4.1, "R2 = 1kΩ", 1.9, 0.85, "#d1ecf1")
    wire((7.6, 3.65), (7.6, 1.6))
    ax.set_title("含源二端网络（端口 A-B）\nVth=%.0fV, Rth=%.0fΩ, Isc=%.0fmA" %
                 (VTH, RTH, ISC * 1e3), fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- 主流程
def main():
    print("=" * 74)
    print("② 戴维南定理验证  |  Vs=%.0fV, R1=%.0fΩ, R2=%.0fΩ" % (VS, R1, R2))
    print("=" * 74)
    print("\n【手算过程】")
    print("  Vth = Vs·R2/(R1+R2) = %.0f×%.0f/(%.0f+%.0f) = %.2f V" % (VS, R2, R1, R2, VTH))
    print("  Rth = R1∥R2 = %.0f×%.0f/(%.0f+%.0f) = %.2f Ω" % (R1, R2, R1, R2, RTH))
    print("  Isc = Vs/R1 = %.0f/%.0f = %.1f mA （短路时 R2 被短接）" % (VS, R1, ISC * 1e3))
    print("  校验：Rth = Vth/Isc = %.2f/%.4f = %.2f Ω ✔" % (VTH, ISC, VTH / ISC))
    for rl in RL_LIST:
        v, i = load_result(rl)
        print("  负载 %.0fΩ 手算：V_L = %.4f V，I_L = %.4f mA" % (rl, v, i * 1e3))

    sim = None
    try:
        sim = run_pyspice()
    except Exception as e:  # noqa: BLE001
        print("\n[!] PySpice/ngspice 不可用：%s: %s" % (type(e).__name__, e))
        print("    已降级为只输出理论值。")

    rows = [("开路电压 V_oc", "%.4f V" % VTH, "%.4f V" % sim["voc"] if sim else None),
            ("短路电流 I_sc", "%.4f mA" % (ISC * 1e3), "%.4f mA" % (sim["isc"] * 1e3) if sim else None),
            ("等效内阻 Rth = Voc/Isc", "%.2f Ω" % RTH,
             "%.2f Ω" % (sim["voc"] / sim["isc"]) if sim else None)]

    p = plot_network(os.path.join(OUT_DIR, "thevenin_network.png"))
    if sim:
        print("\n电路图已保存：%s" % p)
        for rl in RL_LIST:
            vo, io = sim["orig"][rl]
            ve, ie = sim["eqv"][rl]
            vt, it = load_result(rl)
            rows.append(("RL=%.0fΩ 原网络 V_L" % rl, "%.4f V" % vt, "%.4f V" % vo))
            rows.append(("RL=%.0fΩ 原网络 I_L" % rl, "%.4f mA" % (it * 1e3), "%.4f mA" % (io * 1e3)))
            rows.append(("RL=%.0fΩ 等效电路替换后 V_L" % rl, "%.4f V" % vt, "%.4f V" % ve))
            rows.append(("RL=%.0fΩ 等效电路替换后 I_L" % rl, "%.4f mA" % (it * 1e3), "%.4f mA" % (ie * 1e3)))
            print("  负载 %.0fΩ：原网络 %.4fV / %.4fmA ，等效电路 %.4fV / %.4fmA ，电压差 %.2e V"
                  % (rl, vo, io * 1e3, ve, ie * 1e3, abs(vo - ve)))

    md = ["| 指标 | 理论值（手算） | 仿真值（PySpice） |", "| --- | --- | --- |"]
    for n, t, s in rows:
        md.append("| %s | %s | %s |" % (n, t, s if s else "（待运行仿真填入）"))
    md = "\n".join(md)
    print("\n【理论值 vs 仿真值 对比表】\n" + md)
    with open(os.path.join(OUT_DIR, "thevenin_report.md"), "w", encoding="utf-8") as f:
        f.write("# ② 戴维南定理验证 —— 理论 vs 仿真\n\n" + md + "\n")
    print("\n对比表已写入 out/thevenin_report.md")


if __name__ == "__main__":
    main()
