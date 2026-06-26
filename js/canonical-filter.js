/* ═══════════════════════════════════════════════════════════════
 *  캐노니컬(캠페인 유형) 필터 해석기 (canonical-filter.js)
 *  Com2uS R팀 소재 분석 대시보드 — step1_integrated.html 공유
 *
 *  목적: 선택된 캐노니컬 값(ua_type/country/os/media/product) → 통과 campaign_name
 *        판정기. 차원 간 AND, 차원 내 OR. 활성 차원 없으면 null(필터 미적용).
 *  노출: window 전역(인라인 bare 참조 호환) + window.CanonicalFilter,
 *        Node(module.exports) 단위테스트 호환.
 * ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var DIMS = ['ua_type', 'country', 'os', 'media', 'product'];

  // 선택된 캐노니컬 값 → 통과 판정기. 차원 간 AND, 차원 내 OR. 활성 차원 없으면 null.
  // 반환: null | { has(raw): boolean }  ('미상' 버킷 = 맵의 빈 필드값)
  //
  // 맵에 없는 raw(예: campaign_name 이 비어 channel 로 라벨된 MMP 캠페인)는
  // 라이브(live-dashboard.js)의 cv 의미론대로 전 차원 '미상' 버킷으로 취급 →
  // 활성 차원이 모두 '미상'을 포함할 때만 통과(allowUnknown). 그래야 무관한
  // 차원 선택만으로 조용히 누락되지 않는다(설계: "누락값은 미상 버킷, 절대 제외 안 함").
  function resolveCanonicalAllowed(map, currentCanonical) {
    map = map || {};
    var active = DIMS.filter(function (d) {
      return currentCanonical[d] && currentCanonical[d].size;
    });
    if (!active.length) return null;
    var allowed = new Set();
    for (var cn in map) {
      var f = map[cn] || {};
      if (active.every(function (d) { return currentCanonical[d].has(f[d] || '미상'); })) {
        allowed.add(cn);
      }
    }
    var allowUnknown = active.every(function (d) { return currentCanonical[d].has('미상'); });
    var hasOwn = Object.prototype.hasOwnProperty;
    return {
      has: function (raw) {
        return hasOwn.call(map, raw) ? allowed.has(raw) : allowUnknown;
      },
    };
  }

  var _exports = { resolveCanonicalAllowed };
  if (typeof module !== 'undefined' && module.exports) module.exports = _exports;
  if (typeof window !== 'undefined') {
    Object.assign(window, _exports);
    window.CanonicalFilter = Object.assign(window.CanonicalFilter || {}, _exports);
  }
})();
