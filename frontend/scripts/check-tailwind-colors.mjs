#!/usr/bin/env node
/**
 * 디자인 시스템 색상 가드
 * --------------------------------------------------------------------------
 * 계약똑똑은 중립색으로 `slate-*`, 브랜드 강조색으로 `brand-*`(딥 네이비),
 * 포인트로 `accent-*`(골드)를 사용한다. 레거시 `gray-*` 나 비브랜드 임의
 * 색상이 다시 섞이면 화면 간 톤이 어긋나므로, CI/로컬에서 이를 차단한다.
 *
 * 금지: gray-, indigo-, emerald-   (전 영역)
 * 제한: blue-                       (아래 ALLOWLIST 파일에서만 허용)
 *
 * 예외가 꼭 필요한 줄에는 동일 줄에 `color-guard-ignore` 주석을 달면 통과한다.
 *
 * 사용: node scripts/check-tailwind-colors.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = join(__dirname, '..', 'src');

// blue-* 가 의미상 정당한 파일(정보 토스트, 토스페이/카카오 브랜드, 개발 패널 등)
const BLUE_ALLOWLIST = new Set([
  'components/Toast.tsx',      // info 토스트 = 파랑(시맨틱)
  'components/DevPanel.tsx',   // 개발 전용 패널
  'pages/PaymentPage.tsx',     // 토스페이 브랜드 칩
  'pages/MarketPage.tsx',      // 월세 '저렴' 정보 상태
]);
// 개발 전용 파일은 색상 가드 전체 면제
const FILE_ALLOWLIST = new Set(['components/DevPanel.tsx']);

const BANNED = [/\bgray-\d/, /\bindigo-\d/, /\bemerald-\d/];
const RESTRICTED_BLUE = /\bblue-\d/;

const exts = new Set(['.ts', '.tsx', '.css']);
const violations = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full);
    else if (exts.has(extname(name))) scan(full);
  }
}

function scan(file) {
  const rel = file.slice(SRC.length + 1).replace(/\\/g, '/');
  if (FILE_ALLOWLIST.has(rel)) return;
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    if (line.includes('color-guard-ignore')) return;
    for (const re of BANNED) {
      if (re.test(line)) violations.push(`${rel}:${i + 1}  ${re.source}  →  ${line.trim()}`);
    }
    if (RESTRICTED_BLUE.test(line) && !BLUE_ALLOWLIST.has(rel)) {
      violations.push(`${rel}:${i + 1}  blue-* (허용 목록 외)  →  ${line.trim()}`);
    }
  });
}

walk(SRC);

if (violations.length) {
  console.error(`\n❌ 디자인 시스템 색상 가드 위반 ${violations.length}건:\n`);
  for (const v of violations) console.error('  ' + v);
  console.error('\n→ gray-*는 slate-*, 비브랜드 강조색은 brand-*/accent-* 로 교체하세요.');
  console.error('  (정당한 예외는 해당 줄에 `color-guard-ignore` 주석을 추가)\n');
  process.exit(1);
}

console.log('✅ 색상 가드 통과 — 레거시/비브랜드 색상 없음');
