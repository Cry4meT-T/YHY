/**
 * 电路图生成器（纯手写 SVG，不依赖任何绘图库）
 * 运行：node tools/draw-circuits.mjs
 * 输出：assets/*.svg
 *
 * 画的是标准符号：电阻用矩形（IEC）、电容用两条平行板、MOS 用简化符号、
 * 地用一个三横线符号。想换成手绘照片，直接替换 assets 里的同名文件即可。
 */
import fs from 'node:fs';
import path from 'node:path';

const OUT = path.join(process.cwd(), 'assets');
fs.mkdirSync(OUT, { recursive: true });

const WIRE = '#1f2328';
const ACC = '#0969da';

const svg = (w, h, body, title) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" font-family="Microsoft YaHei, SimHei, sans-serif">
  <rect width="${w}" height="${h}" fill="#ffffff"/>
  <text x="${w / 2}" y="26" text-anchor="middle" font-size="15" fill="${WIRE}">${title}</text>
${body}
</svg>
`;

// ---------- 基本图元 ----------
const wire = (x1, y1, x2, y2, color = WIRE, w = 2) =>
  `  <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${w}" stroke-linecap="round"/>`;

const dot = (x, y) => `  <circle cx="${x}" cy="${y}" r="3.2" fill="${WIRE}"/>`;
const nodeDot = (x, y) => `  <circle cx="${x}" cy="${y}" r="4" fill="${ACC}"/>`;

const label = (x, y, t, size = 13, color = WIRE, anchor = 'start') =>
  `  <text x="${x}" y="${y}" font-size="${size}" fill="${color}" text-anchor="${anchor}">${t}</text>`;

/** 水平电阻（矩形） */
function resH(cx, cy, text) {
  return [
    `  <rect x="${cx - 34}" y="${cy - 12}" width="68" height="24" fill="#fff3cd" stroke="${WIRE}" stroke-width="2"/>`,
    label(cx, cy - 20, text, 12.5, WIRE, 'middle'),
  ].join('\n');
}
/** 垂直电阻 */
function resV(cx, cy, text) {
  return [
    `  <rect x="${cx - 12}" y="${cy - 34}" width="24" height="68" fill="#fff3cd" stroke="${WIRE}" stroke-width="2"/>`,
    label(cx + 20, cy + 5, text, 12.5),
  ].join('\n');
}
/** 电容（垂直放置：上板/下板） */
function capV(cx, cy, text) {
  return [
    `  <line x1="${cx - 22}" y1="${cy - 6}" x2="${cx + 22}" y2="${cy - 6}" stroke="${WIRE}" stroke-width="2.6"/>`,
    `  <line x1="${cx - 22}" y1="${cy + 6}" x2="${cx + 22}" y2="${cy + 6}" stroke="${WIRE}" stroke-width="2.6"/>`,
    label(cx + 30, cy + 4, text, 12.5),
  ].join('\n');
}
/** 电容（水平放置：左板/右板） */
function capH(cx, cy, text) {
  return [
    `  <line x1="${cx - 6}" y1="${cy - 22}" x2="${cx - 6}" y2="${cy + 22}" stroke="${WIRE}" stroke-width="2.6"/>`,
    `  <line x1="${cx + 6}" y1="${cy - 22}" x2="${cx + 6}" y2="${cy + 22}" stroke="${WIRE}" stroke-width="2.6"/>`,
    label(cx - 6, cy - 30, text, 12.5, WIRE, 'middle'),
  ].join('\n');
}
/** 地 */
function gnd(x, y) {
  return [
    wire(x, y, x, y + 8),
    `  <line x1="${x - 16}" y1="${y + 8}" x2="${x + 16}" y2="${y + 8}" stroke="${WIRE}" stroke-width="2.6"/>`,
    `  <line x1="${x - 10}" y1="${y + 14}" x2="${x + 10}" y2="${y + 14}" stroke="${WIRE}" stroke-width="2.2"/>`,
    `  <line x1="${x - 4}" y1="${y + 20}" x2="${x + 4}" y2="${y + 20}" stroke="${WIRE}" stroke-width="1.8"/>`,
  ].join('\n');
}
/** 独立电压源（圆 + 正弦） */
function vsrcV(cx, cy, text) {
  return [
    `  <circle cx="${cx}" cy="${cy}" r="20" fill="#e7f5ff" stroke="${WIRE}" stroke-width="2"/>`,
    `  <path d="M ${cx - 9} ${cy} q 4.5 -9 9 0 q 4.5 9 9 0" fill="none" stroke="${WIRE}" stroke-width="1.6"/>`,
    label(cx - 26, cy + 5, text, 12.5, WIRE, 'end'),
  ].join('\n');
}
/** 直流电压源（圆 + 正负号） */
function vdcV(cx, cy, text) {
  return [
    `  <circle cx="${cx}" cy="${cy}" r="20" fill="#fff3cd" stroke="${WIRE}" stroke-width="2"/>`,
    `  <line x1="${cx - 8}" y1="${cy - 5}" x2="${cx + 8}" y2="${cy - 5}" stroke="${WIRE}" stroke-width="2"/>`,
    `  <line x1="${cx}" y1="${cy + 3}" x2="${cx}" y2="${cy + 13}" stroke="${WIRE}" stroke-width="2"/>`,
    label(cx - 26, cy + 5, text, 12.5, WIRE, 'end'),
  ].join('\n');
}
/** NMOS（简化符号：栅极竖线 + 沟道三段 + 箭头） */
function nmos(cx, cy, text = 'NMOS') {
  const g = cx - 26, ch = cx - 12;
  return [
    // 栅极引线与栅极板
    wire(g - 26, cy, g, cy),
    `  <line x1="${g}" y1="${cy - 26}" x2="${g}" y2="${cy + 26}" stroke="${WIRE}" stroke-width="2.6"/>`,
    // 沟道三段
    `  <line x1="${ch}" y1="${cy - 26}" x2="${ch}" y2="${cy - 12}" stroke="${WIRE}" stroke-width="2.6"/>`,
    `  <line x1="${ch}" y1="${cy - 8}" x2="${ch}" y2="${cy + 8}" stroke="${WIRE}" stroke-width="2.6"/>`,
    `  <line x1="${ch}" y1="${cy + 12}" x2="${ch}" y2="${cy + 26}" stroke="${WIRE}" stroke-width="2.6"/>`,
    // 漏极（上）与源极（下）
    wire(ch, cy - 26, cx + 18, cy - 26),
    wire(ch, cy + 26, cx + 18, cy + 26),
    wire(ch, cy, cx + 18, cy),
    // 衬底箭头（源极侧）
    `  <path d="M ${ch + 2} ${cy + 2} l 10 -6 l 0 12 z" fill="${WIRE}"/>`,
    label(cx + 26, cy + 5, text, 12.5),
  ].join('\n');
}
function terminal(x, y, t, anchor = 'start') {
  return [dot(x, y), label(x + (anchor === 'start' ? 10 : -10), y + 5, t, 12.5, ACC, anchor)].join('\n');
}

/* =====================================================================
   ① RC 低通滤波
   ===================================================================== */
{
  const w = 460, h = 250;
  const b = [];
  b.push(vsrcV(70, 130, 'Vi'));
  b.push(wire(70, 110, 70, 70), wire(70, 150, 70, 190));
  b.push(wire(70, 70, 140, 70));
  b.push(resH(175, 70, 'R = 1kΩ'));
  b.push(wire(210, 70, 400, 70));
  b.push(nodeDot(300, 70));
  b.push(wire(300, 70, 300, 105));
  b.push(capV(300, 118, 'C = 100nF'));
  b.push(wire(300, 131, 300, 190));
  b.push(wire(70, 190, 400, 190));
  b.push(gnd(200, 190));
  b.push(terminal(400, 70, 'Vo'));
  b.push(terminal(400, 190, 'GND', 'end'));
  fs.writeFileSync(path.join(OUT, 'rc_circuit.svg'),
    svg(w, h, b.join('\n'), '① RC 低通滤波电路（R=1kΩ, C=100nF）'));
}

/* =====================================================================
   ② 戴维南：含源二端网络（标注端口）
   ===================================================================== */
{
  const w = 460, h = 260;
  const b = [];
  b.push(vdcV(80, 140, 'Vs = 12V'));
  b.push(wire(80, 120, 80, 70), wire(80, 160, 80, 210));
  b.push(wire(80, 70, 200, 70));
  b.push(resH(200, 70, 'R1 = 1kΩ'));
  b.push(wire(234, 70, 400, 70));
  b.push(nodeDot(340, 70));
  b.push(resV(340, 140, 'R2 = 1kΩ'));
  b.push(wire(340, 70, 340, 106));
  b.push(wire(340, 174, 340, 210));
  b.push(wire(80, 210, 400, 210));
  b.push(terminal(400, 70, 'A'));
  b.push(terminal(400, 210, 'B (GND)', 'end'));
  b.push(label(230, 245, '端口 A-B：对它做戴维南等效 → Vth=6V 串 Rth=500Ω', 12.5, '#cf222e', 'middle'));
  fs.writeFileSync(path.join(OUT, 'thevenin_circuit.svg'),
    svg(w, h, b.join('\n'), '② 含源二端网络（端口 A-B 已标注）'));
}

/* =====================================================================
   ② 补充：等效电路替换后接负载
   ===================================================================== */
{
  const w = 460, h = 230;
  const b = [];
  b.push(vdcV(80, 130, 'Vth = 6V'));
  b.push(wire(80, 110, 80, 70), wire(80, 150, 80, 190));
  b.push(wire(80, 70, 150, 70));
  b.push(resH(184, 70, 'Rth = 500Ω'));
  b.push(wire(218, 70, 400, 70));
  b.push(nodeDot(310, 70));
  b.push(resV(310, 130, 'RL'));
  b.push(wire(310, 70, 310, 96));
  b.push(wire(310, 164, 310, 190));
  b.push(wire(80, 190, 400, 190));
  b.push(gnd(200, 190));
  b.push(terminal(400, 70, 'Vo'));
  fs.writeFileSync(path.join(OUT, 'thevenin_equivalent.svg'),
    svg(w, h, b.join('\n'), '② 戴维南等效电路（接负载 RL 验证）'));
}

/* =====================================================================
   ③ NMOS 共源放大（完整电路）
   ===================================================================== */
{
  const w = 520, h = 300;
  const b = [];
  b.push(label(260, 52, 'VDD = 5V', 13, WIRE, 'middle'));
  b.push(wire(260, 60, 260, 78));
  b.push(nodeDot(260, 78));
  b.push(wire(140, 78, 400, 78));
  // Rg1
  b.push(resV(140, 130, 'Rg1 = 60kΩ'));
  b.push(wire(140, 78, 140, 96));
  b.push(wire(140, 164, 140, 205));
  // Rd
  b.push(resV(400, 130, 'Rd = 2kΩ'));
  b.push(wire(400, 78, 400, 96));
  b.push(wire(400, 164, 400, 179));
  // 栅极节点
  b.push(nodeDot(140, 205));
  b.push(resV(140, 250, 'Rg2 = 40kΩ'));
  b.push(wire(140, 205, 140, 216));
  b.push(wire(140, 284, 140, 288));
  b.push(gnd(140, 288));
  // MOS
  b.push(nmos(300, 205, 'M1'));
  b.push(wire(140, 205, 300 - 52, 205));
  b.push(wire(300 + 18, 179, 400, 179));
  b.push(nodeDot(400, 179));
  b.push(terminal(455, 179, 'Vout'));
  b.push(wire(300 + 18, 231, 300 + 18, 288));
  b.push(gnd(300 + 18, 288));
  // 输入耦合
  b.push(vsrcV(60, 205, 'Vi'));
  b.push(label(60, 240, '10mV / 1kHz', 11.5, '#8b949e', 'middle'));
  b.push(wire(80, 205, 108, 205));
  b.push(capH(108, 205, 'Cb1 = 10µF'));
  b.push(wire(114, 205, 140, 205));
  fs.writeFileSync(path.join(OUT, 'mos_circuit.svg'),
    svg(w, h, b.join('\n'), '③ NMOS 共源级放大电路（VDD=5V, Rg1=60k, Rg2=40k, Rd=2k）'));
}

/* =====================================================================
   ③ 补充：直流通路（电容开路）
   ===================================================================== */
{
  const w = 460, h = 260;
  const b = [];
  b.push(label(230, 52, 'VDD = 5V', 13, WIRE, 'middle'));
  b.push(wire(230, 60, 230, 78));
  b.push(nodeDot(230, 78));
  b.push(wire(140, 78, 360, 78));
  b.push(resV(140, 130, 'Rg1 = 60kΩ'));
  b.push(wire(140, 78, 140, 96));
  b.push(wire(140, 164, 140, 195));
  b.push(resV(360, 130, 'Rd = 2kΩ'));
  b.push(wire(360, 78, 360, 96));
  b.push(wire(360, 164, 360, 195));
  b.push(nodeDot(140, 195));
  b.push(wire(140, 195, 300, 195));
  b.push(label(210, 186, 'V_G = 2V', 12, '#cf222e', 'middle'));
  b.push(resV(140, 240, 'Rg2 = 40kΩ'));
  b.push(wire(140, 195, 140, 206));
  b.push(wire(140, 274, 140, 262));
  b.push(gnd(140, 274));
  // 直流通路里 MOS 的输入只剩 V_GS
  b.push(label(300, 200, 'V_GS = V_G = 2V', 12.5, '#cf222e'));
  b.push(wire(300, 195, 300, 210));
  b.push(nmos(300, 230, 'M1'));
  b.push(wire(300 + 18, 256, 360, 256));
  b.push(wire(360, 195, 360, 256));
  b.push(nodeDot(360, 195));
  b.push(terminal(410, 195, 'V_DS'));
  b.push(gnd(300 + 18, 282));
  b.push(wire(300 + 18, 256, 300 + 18, 282));
  b.push(label(230, 246, '（Cb1 在直流下开路 → 输入回路断开）', 11.5, '#8b949e', 'middle'));
  fs.writeFileSync(path.join(OUT, 'mos_dc_path.svg'),
    svg(w, h, b.join('\n'), '③ 直流通路（耦合电容视为开路）'));
}

/* =====================================================================
   ③ 补充：小信号等效模型
   ===================================================================== */
{
  const w = 520, h = 290;
  const b = [];
  // 输入侧
  b.push(terminal(50, 150, 'vi'));
  b.push(wire(50, 150, 120, 150));
  b.push(nodeDot(120, 150));
  b.push(resV(120, 205, 'Rg1∥Rg2'));
  b.push(wire(120, 150, 120, 171));
  b.push(wire(120, 239, 120, 265));
  b.push(gnd(120, 265));
  // 受控源 gm*vgs
  b.push(wire(200, 150, 250, 150));
  b.push(`  <circle cx="272" cy="150" r="22" fill="#e7f5ff" stroke="${WIRE}" stroke-width="2"/>`);
  b.push(`  <path d="M 262 150 l 8 -6 l 0 12 z" fill="${WIRE}"/>`);
  b.push(label(272, 128, "gm·vgs", 12, WIRE, 'middle'));
  b.push(wire(294, 150, 380, 150));
  b.push(nodeDot(380, 150));
  b.push(terminal(450, 150, 'vo'));
  // ro 与 Rd 并联
  b.push(wire(380, 150, 380, 175));
  b.push(resV(380, 210, 'Rd∥ro'));
  b.push(wire(380, 244, 380, 265));
  b.push(wire(120, 265, 380, 265));
  b.push(gnd(250, 265));
  // vgs 标注
  b.push(label(150, 143, 'vgs', 12.5, '#cf222e'));
  b.push(`  <path d="M 176 150 l 12 -4 l 0 8 z" fill="#cf222e"/>`);
  b.push(label(260, 285, 'Av = vo/vi = -gm·(Rd∥ro) ≈ -3.30', 13, '#cf222e', 'middle'));
  fs.writeFileSync(path.join(OUT, 'mos_small_signal.svg'),
    svg(w, h, b.join('\n'), '③ 小信号等效模型（中频：Cb1 短路、VDD 交流接地）'));
}

/* =====================================================================
   贪吃蛇：哈密顿回路示意（20×20 棋盘上的回路走向）
   ===================================================================== */
{
  const N = 20, S = 22, PAD = 24;
  const w = N * S + PAD * 2, h = N * S + PAD * 2 + 20;
  const cycle = [];
  const push = (x, y) => cycle.push({ x, y });
  for (let y = 0; y < N; y++) {
    if (y === 0) { for (let x = 0; x < N; x++) push(x, y); }
    else if (y === N - 1) { for (let x = N - 1; x >= 0; x--) push(x, y); }
    else if (y % 2 === 1) { for (let x = N - 1; x >= 1; x--) push(x, y); }
    else { for (let x = 1; x < N; x++) push(x, y); }
  }
  for (let y = N - 2; y >= 1; y--) push(0, y);
  const cx = (p) => PAD + p.x * S + S / 2;
  const cy = (p) => PAD + p.y * S + S / 2;
  const b = [];
  b.push(`  <rect x="${PAD}" y="${PAD}" width="${N * S}" height="${N * S}" fill="#f6f8fa" stroke="#d0d7de"/>`);
  b.push(`  <polyline fill="none" stroke="${ACC}" stroke-width="2.2" points="${cycle.map(p => `${cx(p)},${cy(p)}`).join(' ')} ${cx(cycle[0])},${cy(cycle[0])}"/>`);
  // 起点/终点标注
  b.push(dot(cx(cycle[0]), cy(cycle[0])));
  b.push(label(cx(cycle[0]) + 8, cy(cycle[0]) - 8, '起点=终点（回路闭环）', 11.5, '#cf222e'));
  b.push(label(w / 2, h - 12, '蛇只要沿着这条回路前进，下一格永远是蛇尾刚离开的格子 → 不可能撞到自己', 12.5, WIRE, 'middle'));
  fs.writeFileSync(path.join(OUT, 'snake_hamiltonian.svg'),
    svg(w, h, b.join('\n'), '贪吃蛇 AI 的哈密顿回路（20×20 = 400 格，每格恰好经过一次）'));
}

console.log('已生成：');
fs.readdirSync(OUT).forEach(f => console.log('  assets/' + f));
