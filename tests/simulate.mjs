/**
 * 贪吃蛇 AI 无头仿真测试（Node 直接运行，不需要浏览器）
 *
 * 用法：node tests/simulate.mjs [局数] [每局目标食物数]
 *
 * 原理：从 snake/index.html 里抽出「核心逻辑层」那段 <script id="snake-core">，
 * 在 Node 的 vm 沙箱里执行，得到和浏览器里完全相同的一份 SnakeCore，
 * 然后不带任何渲染地疯狂跑，统计 AI 能不能「连续吃 15 个食物不死」。
 */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(__dirname, '..', 'snake', 'index.html'), 'utf8');

const m = html.match(/<script id="snake-core">([\s\S]*?)<\/script>/);
if (!m) { console.error('没找到 <script id="snake-core">，HTML 结构被改动了？'); process.exit(1); }

const sandbox = { module: { exports: {} }, Uint8Array, Int32Array, Math, console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(m[1], sandbox, { filename: 'snake-core.js' });
const SnakeCore = sandbox.module.exports;

const GAMES = Number(process.argv[2] || 200);
const TARGET = Number(process.argv[3] || 15);

/* ---------- 0. 先验证哈密顿回路本身是对的 ---------- */
const cycle = SnakeCore.buildHamiltonianCycle(20, 20);
const seen = new Set();
let adjacencyOk = true;
for (let i = 0; i < cycle.length; i++) {
  const a = cycle[i], b = cycle[(i + 1) % cycle.length];
  seen.add(a.x + ',' + a.y);
  if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) !== 1) adjacencyOk = false;
}
console.log('【回路校验】格子数 =', cycle.length, '（应为 400）；去重后 =', seen.size,
  '；首尾相邻且每步位移为 1 =', adjacencyOk ? '通过 ✅' : '失败 ❌');
if (cycle.length !== 400 || seen.size !== 400 || !adjacencyOk) process.exit(1);

/* ---------- 1. 可复现的伪随机数（线性同余），保证结果可重跑 ---------- */
function makeRng(seed) {
  let s = seed >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/* ---------- 2. 跑正式目标：连续吃 TARGET 个不死 ---------- */
let pass = 0, fail = 0, minFoods = Infinity, sumSteps = 0, worst = [];
for (let i = 0; i < GAMES; i++) {
  const r = SnakeCore.runHeadless({ maxFood: TARGET, rng: makeRng(1000 + i) });
  sumSteps += r.steps;
  if (r.success) pass++;
  else { fail++; minFoods = Math.min(minFoods, r.foods); worst.push({ game: i + 1, foods: r.foods, steps: r.steps }); }
}
console.log(`\n【阶段二硬指标】目标 = 连续吃 ${TARGET} 个食物不死`);
console.log(`  通过 ${pass}/${GAMES} 局，失败 ${fail} 局`);
console.log(`  平均每局步数 = ${Math.round(sumSteps / GAMES)}`);
if (fail) console.log('  失败样本：', worst.slice(0, 5));

/* ---------- 3. 再压一轮远超标：连续吃 60 个 / 150 个 ---------- */
for (const t of [60, 150]) {
  let p = 0, mn = Infinity;
  const N = Math.max(20, Math.round(GAMES / 4));
  for (let i = 0; i < N; i++) {
    const r = SnakeCore.runHeadless({ maxFood: t, rng: makeRng(90000 + i) });
    if (r.success) p++; else mn = Math.min(mn, r.foods);
  }
  console.log(`\n【加压测试】目标 = 连续吃 ${t} 个：通过 ${p}/${N}` + (p < N ? `，最少吃到 ${mn} 个` : ' ✅'));
}

/* ---------- 4. 不吃食物时也要能一直活着（纯回路巡航 5 万步） ---------- */
{
  const g = new SnakeCore(20, 20, makeRng(7));
  let alive = true;
  for (let i = 0; i < 50000; i++) {
    g.setDirection(g.aiDirection());
    const ev = g.step();
    if (ev === 'dead') { alive = false; break; }
  }
  console.log('\n【生存测试】无食物干扰巡航 50000 步：' + (alive ? '存活 ✅' : '死亡 ❌'));
}

const verdict = fail === 0 ? '✅ 全部通过' : '❌ 存在失败，需要调参';
console.log('\n结论：' + verdict);
process.exit(fail === 0 ? 0 : 1);
