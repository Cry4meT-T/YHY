/** 极限测试：AI 能不能把 20×20 棋盘吃满（吃满即通关） */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(__dirname, '..', 'snake', 'index.html'), 'utf8');
const m = html.match(/<script id="snake-core">([\s\S]*?)<\/script>/);
const sandbox = { module: { exports: {} }, Uint8Array, Int32Array, Math, console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(m[1], sandbox);
const SnakeCore = sandbox.module.exports;

function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

const N = Number(process.argv[2] || 10);
let win = 0, best = 0, sum = 0;
for (let i = 0; i < N; i++) {
  const r = SnakeCore.runHeadless({ maxFood: 397, maxSteps: 2000000, rng: rng(500 + i) });
  if (r.won) win++;
  best = Math.max(best, r.foods);
  sum += r.foods;
}
console.log('目标 = 吃满整个 20×20 棋盘（共 397 个食物）');
console.log(`  通关 ${win}/${N} 局，平均吃到 ${(sum / N).toFixed(1)} 个，最多 ${best} 个`);
