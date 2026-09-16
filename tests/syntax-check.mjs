/** 语法自检：把 HTML 里两个 <script> 块抽出来，交给 Node 的解析器检查语法 */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const file = process.argv[2] || path.join(__dirname, '..', 'snake', 'index.html');
const html = fs.readFileSync(file, 'utf8');
const blocks = [...html.matchAll(/<script(?:\s+id="([^"]*)")?>([\s\S]*?)<\/script>/g)];
let bad = 0;
for (const [, id, code] of blocks) {
  try { new vm.Script(code, { filename: (id || 'inline') + '.js' }); console.log('✅ 语法通过:', id || '(无名 script)'); }
  catch (e) { bad++; console.log('❌ 语法错误:', id || '(无名 script)', '→', e.message); }
}
console.log(bad ? `共 ${bad} 个脚本有语法错误` : '全部脚本语法正确');
process.exit(bad ? 1 : 0);
