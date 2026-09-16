# -*- coding: utf-8 -*-
"""
③ NMOS 共源级放大电路 —— 手算 + PySpice 仿真对比
================================================

【题给参数（固定，不能改）】
    VDD = 5 V
    Rg1 = 60 kΩ（VDD → 栅极）      Rg2 = 40 kΩ（栅极 → 地）
    Rd  = 2 kΩ （VDD → 漏极）
    NMOS：K = 0.8 mA/V²，Vth = 1 V，λ = 0.02 /V
    输入 Vi = 10 mV / 1 kHz 正弦波，Cb1 视为足够大（本例取 10 µF，1kHz 时近似短路）

【电路】
                   VDD = 5V
                     |
          +----------+----------+
          |                     |
        Rg1=60k              Rd=2k
          |                     |
   Vi --||--+ gate              +----o Vout
      Cb1   |                  |
          Rg2=40k            [NMOS]
            |                  |
           GND --------------- GND(源极)

【本脚本做四件事】
 1. 手算静态工作点 V_GS / I_D / V_DS，并判断是否在饱和区；
 2. 手算小信号参数 gm、输出电阻 ro、电压增益 Av；
 3. PySpice 三种仿真验证：
      · 直流工作点（OP）→ 对比 I_D、V_DS；
      · 交流扫频（AC）  → 实测中频增益、相位（应为 180°，即反相）；
      · 瞬态（TRAN）    → 输入 10mV/1kHz，看输出波形，量峰峰值算增益；
 4. 画出输入/输出波形图与 AC 曲线，打印「理论值 vs 仿真值」对比表。

【两个必须注意的坑（README 里也写了）】
  坑 1：题目给的 K 定义是 I_D = K(V_GS - V_th)²（K 已含 1/2 因子）。
       而 SPICE 的 MOS1 模型用的是 I_D = ½·KP·(W/L)·(V_GS-V_th)²。
       所以要让 SPICE 复现题目，必须取 KP = 2K = 1.6 mA/V²（W/L 取 1）。
       直接把 KP 写成 0.8m，仿真电流会只有理论值的一半，对不上表。
  坑 2：单位别重复乘。电阻数值本身已经是欧姆，写 R1 @ u_kOhm 会变成 1 MΩ。
       本脚本统一用 @ u_Ohm。

【需要环境】pip install PySpice numpy matplotlib
"""

import math
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

# ---------------------------------------------------------------- 题给参数
VDD = 5.0
RG1 = 60e3        # Ω
RG2 = 40e3        # Ω
RD = 2e3          # Ω
K = 0.8e-3        # A/V²，注意：题目定义 I_D = K(Vgs-Vth)²
VTH = 1.0         # V
LAMBDA = 0.02     # 1/V
VI_AMP = 10e-3    # 10 mV 幅值
F_TEST = 1e3      # 1 kHz
CB1 = 10e-6       # 耦合电容，1kHz 时阻抗 ≈ 16 mΩ，可视为短路

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- 手算
VG = VDD * RG2 / (RG1 + RG2)      # 分压偏置，栅极直流电位（栅极不取电流）
VGS = VG                          # 源极接地 → V_GS = V_G
VOV = VGS - VTH                   # 过驱动电压

# ① 简化手算：忽略沟道长度调制（λ=0）
ID_simple = K * VOV ** 2
VDS_simple = VDD - ID_simple * RD
sat_simple = VDS_simple > VOV

# ② 精确手算：考虑 λ。I_D = K·Vov²·(1+λ·V_DS)，V_DS = VDD - I_D·Rd
#    代入整理： I_D·(1 + K·Vov²·λ·Rd) = K·Vov²·(1 + λ·VDD)
num = K * VOV ** 2 * (1 + LAMBDA * VDD)
den = 1 + K * VOV ** 2 * LAMBDA * RD
ID = num / den
VDS = VDD - ID * RD
sat = VDS > VOV

# ③ 小信号参数
gm_simple = 2 * K * VOV                        # 忽略 λ
gm = 2 * K * VOV * (1 + LAMBDA * VDS)          # 精确（SPICE 用的就是这个式子）
ro_simple = 1.0 / (LAMBDA * ID_simple)
ro = 1.0 / (LAMBDA * ID)
AV_simple = -gm_simple * RD                    # 忽略 ro 时的简化：Av = -gm·Rd
AV = -gm * (RD * ro) / (RD + ro)               # 考虑 ro：Av = -gm·(Rd∥ro)


# ---------------------------------------------------------------- 仿真
def run_pyspice():
    lib = os.environ.get("NGSPICE_LIB")
    if lib:
        import PySpice.Spice.NgSpice.Shared as _shared
        _shared.NgSpiceShared.LIBRARY_PATH = lib

    from PySpice.Spice.Netlist import Circuit
    from PySpice.Unit import u_V, u_Hz, u_F, u_ms, u_us, u_Ohm, u_um

    res = {}

    def build(name, with_source):
        c = Circuit(name)
        # SPICE 的 MOS1 模型：I_D = ½·KP·(W/L)·Vov² → 取 KP = 2K，W/L = 1
        c.model("nmos1", "NMOS", LEVEL=1, VTO=VTH, KP=2 * K, LAMBDA=LAMBDA)
        c.V("dd", "vdd", c.gnd, VDD @ u_V)
        c.R("g1", "vdd", "gate", RG1 @ u_Ohm)
        c.R("g2", "gate", c.gnd, RG2 @ u_Ohm)
        c.R("d", "vdd", "drain", RD @ u_Ohm)
        # 加 MOS 管；不同 PySpice 版本对小写 w/l 的支持略有差别，这里做兼容处理
        try:
            c.MOSFET("1", "drain", "gate", c.gnd, c.gnd, model="nmos1", w=10 @ u_um, l=10 @ u_um)
        except TypeError:
            try:
                c.MOSFET("1", "drain", "gate", c.gnd, c.gnd, model="nmos1", W=10 @ u_um, L=10 @ u_um)
            except TypeError:
                c.MOSFET("1", "drain", "gate", c.gnd, c.gnd, model="nmos1")
        if with_source:
            c.SinusoidalVoltageSource("in", "vi", c.gnd, amplitude=VI_AMP @ u_V, frequency=F_TEST @ u_Hz)
            c.C("b1", "vi", "gate", CB1 @ u_F)
        else:
            c.C("b1", "gate", c.gnd, CB1 @ u_F)   # 交流短路到地，只做直流工作点
        return c

    def flat(analysis, node):
        return float(np.array(analysis[node]).astype(float).ravel()[-1])

    def branch(analysis, name):
        """支路电流：PySpice 的分支名是设备名小写（V('dd') → 'vdd'），做兼容处理。"""
        keys = list(analysis.branches.keys())
        for cand in ("v" + name, name):
            for k in keys:
                if k.lower() == cand.lower():
                    return float(np.array(analysis.branches[k]).astype(float).ravel()[-1])
        raise KeyError("找不到支路 %s，可用：%s" % (name, keys))

    # ---- 1) 直流工作点 ----
    c1 = build("NMOS common source - operating point", with_source=False)
    sim1 = c1.simulator(temperature=25, nominal_temperature=25)
    an1 = sim1.operating_point()
    res["vgs"] = flat(an1, "gate")
    res["vds"] = flat(an1, "drain")
    # I_D 直接用漏极电阻上的压降算，避免把栅极分压电阻的电流算进去
    res["id"] = (VDD - res["vds"]) / RD
    try:
        # 电源总电流（= 栅极分压电流 + I_D），可以用来交叉验证
        res["i_supply"] = -branch(an1, "dd")
    except Exception:  # noqa: BLE001
        res["i_supply"] = float("nan")

    # ---- 2) 交流扫频：实测中频增益与相位 ----
    c2 = build("NMOS common source - ac", with_source=True)
    sim2 = c2.simulator(temperature=25, nominal_temperature=25)
    an2 = sim2.ac(start_frequency=10 @ u_Hz, stop_frequency=10 @ u_Hz * 1e6,
                  number_of_points=20, variation="dec")
    f = np.array(an2.frequency).astype(float)
    h = np.array(an2["drain"]).astype(complex) / np.array(an2["vi"]).astype(complex)
    res["f"] = f
    res["mag_db"] = 20 * np.log10(np.abs(h))
    res["phase"] = np.degrees(np.angle(h))
    res["av_sim"] = float(np.interp(F_TEST, f, np.abs(h)))
    res["phase_1k"] = float(np.interp(F_TEST, f, res["phase"]))

    # ---- 3) 瞬态：10mV/1kHz 输入，看输出波形与幅度 ----
    c3 = build("NMOS common source - transient", with_source=True)
    sim3 = c3.simulator(temperature=25, nominal_temperature=25)
    an3 = sim3.transient(step_time=1 @ u_us, end_time=5 @ u_ms)
    t = np.array(an3.time).astype(float)
    res["t"] = t
    res["vi"] = np.array(an3["vi"]).astype(float)
    res["vo"] = np.array(an3["drain"]).astype(float)
    # 取最后一个完整周期（4~5ms）算幅度
    seg = (t >= 4e-3) & (t <= 5e-3)
    res["vo_amp"] = (res["vo"][seg].max() - res["vo"][seg].min()) / 2.0
    res["vi_amp"] = (res["vi"][seg].max() - res["vi"][seg].min()) / 2.0
    res["av_tran"] = -res["vo_amp"] / res["vi_amp"]     # 反相，所以为负
    return res


# ---------------------------------------------------------------- 画图
def plot_wave(r):
    # 输出信号骑在直流工作点 V_DS≈3.29V 上，直接画会被直流抬高、看不出交流摆动，
    # 所以画「去掉直流分量后的交流波形」，并在标题里注明。
    seg = (r["t"] >= 4e-3) & (r["t"] <= 5e-3)
    dc = float(np.mean(r["vo"][seg]))
    vo_ac = (r["vo"] - dc) * 1e3
    vi_ac = r["vi"] * 1e3

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.2), dpi=130, sharex=True)
    ax1.plot(r["t"] * 1e3, vi_ac, lw=1.8, color="#0969da", label="输入 Vi（10mV 幅值，1kHz）")
    ax1.axhline(0, color="gray", lw=0.8)
    ax1.set_ylabel("输入 (mV)")
    ax1.grid(alpha=0.3)
    ax1.legend()
    ax1.set_title("NMOS 共源放大：瞬态波形（输出反相放大，已扣除直流分量 V_DS=%.3f V）" % dc)
    ax2.plot(r["t"] * 1e3, vo_ac, lw=1.8, color="#cf222e",
             label="输出交流分量（幅值 %.1f mV，与输入反相）" % np.abs(vo_ac[seg]).max())
    ax2.axhline(0, color="gray", lw=0.8)
    ax2.set_xlabel("时间 (ms)")
    ax2.set_ylabel("输出 (mV)")
    ax2.grid(alpha=0.3)
    ax2.legend()
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "mos_transient.png")
    fig.savefig(p)
    plt.close(fig)
    return p


def plot_ac(r):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.2), dpi=130, sharex=True)
    ax1.semilogx(r["f"], r["mag_db"], lw=2, color="#cf222e")
    ax1.axvline(F_TEST, ls=":", color="gray")
    ax1.axhline(20 * math.log10(abs(AV)), ls="--", color="#0969da", lw=1.3,
                label="手算 |Av| = %.2f (%.2f dB)" % (abs(AV), 20 * math.log10(abs(AV))))
    ax1.set_ylabel("|Av| (dB)")
    ax1.grid(alpha=0.3, which="both")
    ax1.legend()
    ax1.set_title("NMOS 共源放大：交流扫描（幅频 + 相频）")
    ax2.semilogx(r["f"], r["phase"], lw=2, color="darkorange")
    ax2.axvline(F_TEST, ls=":", color="gray")
    ax2.axhline(180, ls="--", color="gray", lw=1)
    ax2.set_xlabel("频率 (Hz)")
    ax2.set_ylabel("相位 (°)")
    ax2.grid(alpha=0.3, which="both")
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "mos_ac.png")
    fig.savefig(p)
    plt.close(fig)
    return p


# ---------------------------------------------------------------- 主流程
def main():
    print("=" * 74)
    print("③ NMOS 共源级放大电路 | VDD=5V Rg1=60k Rg2=40k Rd=2k K=0.8mA/V² Vth=1V λ=0.02/V")
    print("=" * 74)

    print("\n【手算 1】静态工作点")
    print("  V_G = VDD·Rg2/(Rg1+Rg2) = 5×40k/100k = %.2f V（栅极不取电流，分压公式直接可用）" % VG)
    print("  V_GS = V_G = %.2f V（源极接地）" % VGS)
    print("  V_ov = V_GS - Vth = %.2f V" % VOV)
    print("  ① 忽略 λ：I_D = K·V_ov² = %.3fmA×%.2f² = %.4f mA" % (K * 1e3, VOV, ID_simple * 1e3))
    print("            V_DS = VDD - I_D·Rd = 5 - %.4fm×2k = %.4f V" % (ID_simple * 1e3, VDS_simple))
    print("  ② 考虑 λ：解 I_D = K·V_ov²(1+λ(VDD-I_D·Rd)) → I_D = %.4f mA" % (ID * 1e3))
    print("            V_DS = %.4f V" % VDS)
    print("  饱和区判据：V_DS > V_GS - Vth → %.4f V > %.2f V → %s"
          % (VDS, VOV, "工作在饱和区（放大区）✔" if sat else "不在饱和区 ✘"))

    print("\n【手算 2】小信号参数与增益")
    print("  gm = 2K·V_ov·(1+λV_DS) = %.4f mA/V（忽略 λ 时为 %.4f mA/V）" % (gm * 1e3, gm_simple * 1e3))
    print("  ro = 1/(λ·I_D) = %.2f kΩ（忽略 λ 的简化算法为 %.2f kΩ）" % (ro / 1e3, ro_simple / 1e3))
    print("  Av = -gm·(Rd∥ro) = -%.4fm × (2k∥%.2fk) = %.4f V/V" % (gm * 1e3, ro / 1e3, AV))
    print("       忽略 ro 的简化：Av = -gm·Rd = %.4f V/V" % AV_simple)
    print("  输出幅度 = |Av| × 10mV = %.2f mV，且与输入反相（相差 180°）" % (abs(AV) * VI_AMP * 1e3))

    sim = None
    try:
        sim = run_pyspice()
    except Exception as e:  # noqa: BLE001
        print("\n[!] PySpice/ngspice 不可用：%s: %s" % (type(e).__name__, e))
        print("    已降级为只输出理论值。")

    rows = [
        ("V_GS", "%.4f V" % VGS, "%.4f V" % sim["vgs"] if sim else None),
        ("I_D", "%.4f mA（考虑 λ）/ %.4f mA（忽略 λ）" % (ID * 1e3, ID_simple * 1e3),
         "%.4f mA" % (sim["id"] * 1e3) if sim else None),
        ("V_DS", "%.4f V（考虑 λ）/ %.4f V（忽略 λ）" % (VDS, VDS_simple),
         "%.4f V" % sim["vds"] if sim else None),
        ("是否工作在饱和区", "V_DS=%.3fV > V_ov=%.1fV，饱和 ✔" % (VDS, VOV),
         ("V_DS=%.3fV > V_ov=%.1fV，饱和 ✔" % (sim["vds"], VOV)) if sim else None),
        ("gm", "%.4f mA/V" % (gm * 1e3),
         ("≈%.4f mA/V（由仿真 V_DS 反推 2K·Vov·(1+λV_DS)）"
          % (2 * K * VOV * (1 + LAMBDA * sim["vds"]) * 1e3)) if sim else None),
        ("ro", "%.2f kΩ" % (ro / 1e3),
         ("≈%.2f kΩ（1/(λ·I_D)）" % (1 / (LAMBDA * sim["id"]) / 1e3)) if sim else None),
        ("Av（AC 扫频实测）", "%.4f V/V（%.2f dB）" % (AV, 20 * math.log10(abs(AV))),
         "%.4f V/V（%.2f dB）" % (sim["av_sim"], 20 * math.log10(sim["av_sim"])) if sim else None),
        ("Av（瞬态实测）", "%.4f V/V" % AV, "%.4f V/V" % sim["av_tran"] if sim else None),
        ("输出相位", "180°（反相）", "%.1f°" % sim["phase_1k"] if sim else None),
        ("输出幅度", "%.2f mV" % (abs(AV) * VI_AMP * 1e3),
         "%.2f mV" % (sim["vo_amp"] * 1e3) if sim else None),
    ]

    if sim:
        p1 = plot_wave(sim)
        p2 = plot_ac(sim)
        print("\n波形图已保存：\n  %s\n  %s" % (p1, p2))
        print("  仿真实测：I_D=%.4f mA，V_DS=%.4f V，|Av|(AC)=%.4f，|Av|(瞬态)=%.4f，相位=%.1f°"
              % (sim["id"] * 1e3, sim["vds"], sim["av_sim"], abs(sim["av_tran"]), sim["phase_1k"]))
        print("  （交叉验证）电源总电流 %.4f mA = 栅极分压电流 %.4f mA + I_D %.4f mA"
              % (sim["i_supply"] * 1e3, (VDD - sim["vgs"]) / RG1 * 1e3, sim["id"] * 1e3))

    md = ["| 指标 | 理论值（手算） | 仿真值（PySpice） |", "| --- | --- | --- |"]
    for n, t, s in rows:
        md.append("| %s | %s | %s |" % (n, t, s if s else "（待运行仿真填入）"))
    md = "\n".join(md)
    print("\n【理论值 vs 仿真值 对比表】\n" + md)
    with open(os.path.join(OUT_DIR, "mos_report.md"), "w", encoding="utf-8") as f:
        f.write("# ③ NMOS 共源级放大 —— 理论 vs 仿真\n\n" + md + "\n")
    print("\n对比表已写入 out/mos_report.md")


if __name__ == "__main__":
    main()
