# -*- coding: utf-8 -*-
"""
① RC 低通滤波电路 —— 手算 + PySpice 仿真对比
================================================

【电路】一阶 RC 低通
         o----[ R = 1kΩ ]----+----o  out
         |                   |
       Vin                   C = 100nF
         |                   |
         o-------------------+----o  GND

【本脚本做四件事】
 1. 打印手算公式与结果：时间常数 τ、截止频率 fc（-3dB 点）、增益与相移公式；
 2. 用 PySpice 跑两次仿真：
      · 瞬态分析（Transient）：输入 1kHz 方波，看电容充放电的指数曲线；
      · 交流分析（AC / Bode）：扫频 10Hz~1MHz，画幅频 + 相频，找 -3dB 点；
 3. 画出波形图与波特图，保存到 out/rc_transient.png、out/rc_bode.png；
 4. 打印「理论值 vs 仿真值」对比表（Markdown），直接复制进 README。

【需要环境】pip install PySpice numpy matplotlib ；PySpice 底层还需要 ngspice。
    Windows 安装 ngspice 后，如果 PySpice 找不到库，可设置环境变量：
        set NGSPICE_LIB=C:\\ngspice\\Spice64_dll\\dll-vs\\ngspice.dll
    没装 ngspice 也能跑：脚本会自动降级为「只输出理论值」。
"""

import math
import os
import sys

# Windows 控制台默认是 GBK，中文 + µ/τ 这类符号会直接抛 UnicodeEncodeError。
# 统一把输出改成 UTF-8（终端若乱码，先执行 chcp 65001 或设 PYTHONUTF8=1）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import matplotlib
matplotlib.use("Agg")                      # 不需要弹窗，直接存图片
import matplotlib.pyplot as plt

# 中文标签不乱码（Windows 自带微软雅黑）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ----------------------------------------------------------------------------
# 一、元件参数（①② 题参数自定，这里选一组好算的整数）
# ----------------------------------------------------------------------------
R = 1e3         # 1 kΩ（单位就是欧姆，下面直接用 R @ u_Ohm，别再乘 u_kOhm！）
C = 100e-9      # 100 nF
VIN_HIGH = 5.0  # 方波高电平 5 V
F_SQUARE = 1e3  # 方波频率 1 kHz（周期 1ms，高电平 0.5ms）
F_TEST = 1e3    # 看增益用的正弦频率 1 kHz

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# 二、手算（公式 + 数值）
# ----------------------------------------------------------------------------
tau = R * C                              # τ = RC
fc = 1.0 / (2.0 * math.pi * tau)         # fc = 1 / (2πRC)


def gain(f):
    """一阶低通幅频特性 |H(f)| = 1 / sqrt(1 + (f/fc)^2)（标量用）"""
    return 1.0 / math.sqrt(1.0 + (f / fc) ** 2)


def phase_deg(f):
    """相频特性 φ(f) = -arctan(f/fc)"""
    return -math.degrees(math.atan(f / fc))


def gain_np(f):
    """同一个公式的 numpy 版本，用来画理论曲线"""
    return 1.0 / np.sqrt(1.0 + (np.asarray(f, dtype=float) / fc) ** 2)


# ----------------------------------------------------------------------------
# 三、PySpice 仿真
# ----------------------------------------------------------------------------
def run_pyspice():
    """返回 dict；ngspice 不可用时抛异常，由 main 捕获降级。"""
    # 允许用环境变量指定 ngspice 动态库位置（Windows 常见坑）
    lib = os.environ.get("NGSPICE_LIB")
    if lib:
        import PySpice.Spice.NgSpice.Shared as _shared
        _shared.NgSpiceShared.LIBRARY_PATH = lib

    from PySpice.Spice.Netlist import Circuit
    from PySpice.Unit import u_V, u_Hz, u_s, u_us, u_ms, u_Ohm, u_nF, u_ns

    result = {}

    # ---------- 电路 A：瞬态（方波输入） ----------
    c1 = Circuit("RC low pass - transient")
    c1.PulseVoltageSource(
        "in", "vin", c1.gnd,
        initial_value=0 @ u_V, pulsed_value=VIN_HIGH @ u_V,
        pulse_width=0.5 @ u_ms, period=1 @ u_ms,
        rise_time=1 @ u_ns, fall_time=1 @ u_ns, delay_time=0 @ u_s,
    )
    c1.R(1, "vin", "vout", R @ u_Ohm)
    c1.C(1, "vout", c1.gnd, (C * 1e9) @ u_nF)
    sim1 = c1.simulator(temperature=25, nominal_temperature=25)
    an1 = sim1.transient(step_time=1 @ u_us, end_time=5 @ u_ms)
    result["t"] = np.array(an1.time).astype(float)
    result["vin"] = np.array(an1["vin"]).astype(float)
    result["vout"] = np.array(an1["vout"]).astype(float)

    # ---------- 电路 B：交流扫频（波特图） ----------
    c2 = Circuit("RC low pass - ac")
    c2.SinusoidalVoltageSource("in", "vin", c2.gnd, amplitude=1 @ u_V, frequency=F_TEST @ u_Hz)
    c2.R(1, "vin", "vout", R @ u_Ohm)
    c2.C(1, "vout", c2.gnd, (C * 1e9) @ u_nF)
    sim2 = c2.simulator(temperature=25, nominal_temperature=25)
    an2 = sim2.ac(start_frequency=10 @ u_Hz, stop_frequency=1 @ u_Hz * 1e6,
                  number_of_points=20, variation="dec")
    f = np.array(an2.frequency).astype(float)
    h = np.array(an2["vout"]).astype(complex) / np.array(an2["vin"]).astype(complex)
    result["f"] = f
    result["mag_db"] = 20 * np.log10(np.abs(h))
    result["phase"] = np.degrees(np.angle(h))

    # 从仿真曲线上找 -3dB 点
    idx = int(np.argmin(np.abs(result["mag_db"] + 3.0)))
    result["fc_sim"] = f[idx]
    result["gain_1k_sim"] = float(np.interp(F_TEST, f, np.abs(h)))
    result["phase_1k_sim"] = float(np.interp(F_TEST, f, result["phase"]))

    # 瞬态里量一下充电时间常数：对第一段上升沿做线性拟合
    t, vo = result["t"], result["vout"]
    seg = (t >= 0.0) & (t <= 0.5e-3)
    t_seg, v_seg = t[seg], vo[seg]
    ok = v_seg > 1e-3
    if ok.sum() > 5:
        # ln(1 - v/5) = -t/τ  →  线性拟合斜率即 -1/τ
        k = np.polyfit(t_seg[ok], np.log(1 - v_seg[ok] / VIN_HIGH), 1)
        result["tau_sim"] = -1.0 / k[0]
    else:
        result["tau_sim"] = float("nan")
    return result


# ----------------------------------------------------------------------------
# 四、画图
# ----------------------------------------------------------------------------
def plot_transient(r):
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
    ax.plot(r["t"] * 1e3, r["vin"], "--", lw=1.4, label="输入方波 Vin (0/5V, 1kHz)")
    ax.plot(r["t"] * 1e3, r["vout"], lw=2.0, label="输出 Vout（RC 充放电）")
    ax.axhline(VIN_HIGH, color="gray", ls=":", lw=1)
    ax.set_xlabel("时间 t (ms)")
    ax.set_ylabel("电压 (V)")
    ax.set_title("RC 低通滤波：方波输入的瞬态响应（τ=%.0fµs, fc=%.0fHz）" % (tau * 1e6, fc))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "rc_transient.png")
    fig.savefig(p)
    plt.close(fig)
    return p


def plot_bode(r):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.5), dpi=130, sharex=True)
    ff = np.logspace(1, 6, 400)
    ax1.semilogx(r["f"], r["mag_db"], lw=2, label="仿真幅频 (dB)")
    ax1.semilogx(ff, 20 * np.log10(gain_np(ff)), "--", lw=1.4, label="理论 20log|H| (dB)")
    ax1.axvline(fc, color="crimson", ls=":", lw=1.4)
    ax1.axhline(-3.0103, color="crimson", ls=":", lw=1.4)
    ax1.annotate("fc = %.0f Hz (-3dB)" % fc, xy=(fc, -3.01), xytext=(fc * 3, -12),
                 arrowprops=dict(arrowstyle="->", color="crimson"), color="crimson")
    ax1.set_ylabel("增益 (dB)")
    ax1.grid(alpha=0.3, which="both")
    ax1.legend()
    ax1.set_title("RC 低通滤波：波特图（理论 vs 仿真）")

    ax2.semilogx(r["f"], r["phase"], lw=2, color="darkorange", label="仿真相频 (°)")
    ax2.semilogx(ff, -np.degrees(np.arctan(ff / fc)), "--", lw=1.4, color="gray",
                 label="理论 -arctan(f/fc)")
    ax2.axvline(fc, color="crimson", ls=":", lw=1.4)
    ax2.axhline(-45, color="crimson", ls=":", lw=1.4)
    ax2.set_xlabel("频率 f (Hz)")
    ax2.set_ylabel("相位 (°)")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend()
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "rc_bode.png")
    fig.savefig(p)
    plt.close(fig)
    return p


# ----------------------------------------------------------------------------
# 五、主流程：打印对比表 + 生成 Markdown
# ----------------------------------------------------------------------------
def main():
    print("=" * 74)
    print("① RC 低通滤波电路  |  R = %.0f Ω  C = %.1f nF" % (R, C * 1e9))
    print("=" * 74)
    print("\n【手算过程】")
    print("  τ  = R·C = %.0f × %.1e = %.1f µs" % (R, C, tau * 1e6))
    print("  fc = 1/(2πRC) = 1/(2π×%.1e) = %.2f Hz" % (tau, fc))
    print("  |H(f)| = 1/√(1+(f/fc)²) ， φ(f) = -arctan(f/fc)")
    print("  1 kHz 处：|H| = %.4f (%.3f dB)，φ = %.2f°" %
          (gain(F_TEST), 20 * math.log10(gain(F_TEST)), phase_deg(F_TEST)))

    sim = None
    try:
        sim = run_pyspice()
    except Exception as e:  # noqa: BLE001
        print("\n[!] PySpice/ngspice 不可用，原因：%s: %s" % (type(e).__name__, e))
        print("    本脚本已降级为「只输出理论值」。装好 ngspice 后再运行即可自动补全仿真列。")

    if sim:
        p1 = plot_transient(sim)
        p2 = plot_bode(sim)
        rows = [
            ("时间常数 τ", "%.1f µs" % (tau * 1e6), "%.1f µs" % (sim["tau_sim"] * 1e6)),
            ("截止频率 fc(-3dB)", "%.1f Hz" % fc, "%.1f Hz" % sim["fc_sim"]),
            ("1kHz 增益 |H|", "%.4f (%.3f dB)" % (gain(F_TEST), 20 * math.log10(gain(F_TEST))),
             "%.4f (%.3f dB)" % (sim["gain_1k_sim"], 20 * math.log10(sim["gain_1k_sim"]))),
            ("1kHz 相移 φ", "%.2f°" % phase_deg(F_TEST), "%.2f°" % sim["phase_1k_sim"]),
        ]
        print("\n【波形与波特图已保存】\n  %s\n  %s" % (p1, p2))
        print("  仿真实测：τ = %.1f µs，fc = %.1f Hz，1kHz |H| = %.4f，φ = %.2f°"
              % (sim["tau_sim"] * 1e6, sim["fc_sim"], sim["gain_1k_sim"], sim["phase_1k_sim"]))
    else:
        rows = [
            ("时间常数 τ", "%.1f µs" % (tau * 1e6), None),
            ("截止频率 fc(-3dB)", "%.1f Hz" % fc, None),
            ("1kHz 增益 |H|", "%.4f (%.3f dB)" % (gain(F_TEST), 20 * math.log10(gain(F_TEST))), None),
            ("1kHz 相移 φ", "%.2f°" % phase_deg(F_TEST), None),
        ]

    md = ["| 指标 | 理论值（手算） | 仿真值（PySpice） |", "| --- | --- | --- |"]
    for n, t, s in rows:
        md.append("| %s | %s | %s |" % (n, t, s if s else "（待运行仿真填入）"))
    md = "\n".join(md)
    print("\n【理论值 vs 仿真值 对比表】\n" + md)
    with open(os.path.join(OUT_DIR, "rc_report.md"), "w", encoding="utf-8") as f:
        f.write("# ① RC 低通滤波 —— 理论 vs 仿真\n\n" + md + "\n")
    print("\n对比表已写入 out/rc_report.md")


if __name__ == "__main__":
    main()
