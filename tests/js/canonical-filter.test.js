/* ═══════════════════════════════════════════════════════════════
 *  canonical-filter.js 단위테스트 (Node 내장 test runner, 의존 0)
 *  실행: node --test tests/js/canonical-filter.test.js
 *
 *  대상: resolveCanonicalAllowed(map, currentCanonical)
 *    step1_integrated.html 의 resolveCanonicalCampaigns 핵심 로직.
 *    라이브(live-dashboard.js)의 cv 미상-버킷 의미론과 정합되어야 함:
 *      맵에 없는 campaign_name(예: channel-only MMP)은 전 차원 '미상' 버킷 →
 *      활성 차원이 모두 '미상'을 포함할 때만 통과, 아니면 제외.
 * ═══════════════════════════════════════════════════════════════ */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { resolveCanonicalAllowed } = require('../../js/canonical-filter.js');

const DIMS = ['ua_type', 'country', 'os', 'media', 'product'];

// 선택값 객체({dim: [values]}) → currentCanonical 형태({dim: Set})
function mkCanon(sel) {
  const out = {};
  for (const d of DIMS) out[d] = new Set((sel && sel[d]) || []);
  return out;
}

// Google Ads 캠페인 — 맵에 캐노니컬 필드 보유
const GA = 'HQ_HQ_PH_US-EN_GA_NU-Pre_iOS_ACp_260429';
const MAP = {
  [GA]: { ua_type: 'NU-Pre', country: 'US', os: 'iOS', media: 'GA', product: 'ACp' },
};
// channel-only MMP 캠페인의 raw 값 — campaign_name 이 비어 channel 로 라벨됨 → 맵에 없음
const CHANNEL_ONLY = 'Facebook Ads';

test('활성 차원이 없으면 null (필터 미적용)', () => {
  assert.strictEqual(resolveCanonicalAllowed(MAP, mkCanon({})), null);
});

test('맵 보유 캠페인은 일치하는 차원 값에서 통과/제외', () => {
  assert.strictEqual(resolveCanonicalAllowed(MAP, mkCanon({ country: ['US'] })).has(GA), true);
  assert.strictEqual(resolveCanonicalAllowed(MAP, mkCanon({ country: ['JP'] })).has(GA), false);
});

// ── 재현 테스트 (이 버그) ──────────────────────────────────────
// channel-only MMP 캠페인은 맵에 없어 전 차원 '미상'. 활성 차원이 '미상'을
// 선택하면 라이브와 동일하게 포함되어야 하는데, 버그는 무조건 제외했다.
test('맵에 없는 channel-only 캠페인: 활성 차원이 미상을 선택하면 포함', () => {
  const allowed = resolveCanonicalAllowed(MAP, mkCanon({ ua_type: ['미상'] }));
  assert.strictEqual(allowed.has(CHANNEL_ONLY), true);
});

test('맵에 없는 channel-only 캠페인: 활성 차원이 실값만 선택하면 제외 (라이브 일치)', () => {
  const allowed = resolveCanonicalAllowed(MAP, mkCanon({ ua_type: ['NU-Pre'] }));
  assert.strictEqual(allowed.has(CHANNEL_ONLY), false);
});

test('맵에 없는 캠페인: 차원 간 AND — 모든 활성 차원이 미상을 포함해야 통과', () => {
  // 한 차원만 미상이고 다른 차원은 실값 → 제외
  assert.strictEqual(
    resolveCanonicalAllowed(MAP, mkCanon({ ua_type: ['미상'], country: ['US'] })).has(CHANNEL_ONLY),
    false,
  );
  // 모든 활성 차원이 미상 → 통과
  assert.strictEqual(
    resolveCanonicalAllowed(MAP, mkCanon({ ua_type: ['미상'], country: ['미상'] })).has(CHANNEL_ONLY),
    true,
  );
});
