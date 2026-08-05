/* ──────────────────────────────────────
   접근 고지 게이트 (access-gate.js)
   목적: 접근 차단이 아니라 "내부 자료 무단 유출·공유 금지" 고지 확인 장치.
   - 세션당 1회 노출 (sessionStorage) — 새 브라우저 세션마다 경고 재노출
   - 접근 코드는 배포 통제 수단(심리적 장벽)일 뿐 보안 수단 아님
   - 대행(인크로스) 계약 종료 시 ACCESS_CODE 교체로 기존 코드 무효화
────────────────────────────────────── */
(function () {
  var ACCESS_CODE = 'com2us2026';        // 외부 공유용 접근 코드 — 종료 시 교체
  var SESSION_KEY = 'cloop_access_ok';

  if (sessionStorage.getItem(SESSION_KEY) === '1') return;

  function buildOverlay() {
    var ov = document.createElement('div');
    ov.id = 'accessGateOverlay';
    ov.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:rgba(20,19,18,.97);display:flex;align-items:center;justify-content:center;padding:20px;font-family:"Noto Sans KR","Pretendard",sans-serif;';
    ov.innerHTML =
      '<div style="max-width:460px;width:100%;background:#FEFDFA;border-radius:14px;padding:30px 30px 26px;box-shadow:0 8px 40px rgba(0,0,0,.4);">' +
        '<div style="font-size:17px;font-weight:800;color:#191919;margin-bottom:14px;">소재 분석 대시보드 접근 안내</div>' +
        '<div style="font-size:13px;line-height:1.75;color:#4C4C4C;background:#F7F4EE;border-left:3px solid #DC2828;padding:12px 14px;margin-bottom:18px;">' +
          '본 대시보드는 <b>컴투스 내부 자료</b>입니다. 승인된 인원 외 접근을 금하며, ' +
          '자료(화면·데이터·보고서 포함)의 <b style="color:#DC2828;">외부 유출·공유·캡처 배포</b>는 ' +
          '관련 법령 및 계약에 따라 책임을 물을 수 있습니다.<br>' +
          '아래 확인 버튼 클릭 시 위 내용에 동의한 것으로 간주합니다.' +
        '</div>' +
        '<div style="font-size:12px;font-weight:700;color:#191919;margin-bottom:6px;">접근 코드</div>' +
        '<div style="display:flex;gap:8px;">' +
          '<input id="accessGateInput" type="password" autocomplete="off" placeholder="전달받은 접근 코드를 입력하세요" ' +
            'style="flex:1;font-size:14px;padding:10px 12px;border:1px solid #E4E1DC;border-radius:8px;outline:none;box-sizing:border-box;">' +
          '<button id="accessGateBtn" style="font-size:14px;font-weight:700;padding:10px 18px;border:none;background:#DC2828;color:#fff;border-radius:8px;cursor:pointer;white-space:nowrap;">확인</button>' +
        '</div>' +
        '<div id="accessGateErr" style="font-size:12px;color:#DC2828;margin-top:8px;min-height:16px;"></div>' +
        '<div style="font-size:11px;color:#9ca3af;margin-top:10px;">Com2uS R Marketing Team · 내부 참고용</div>' +
      '</div>';
    document.body.appendChild(ov);
    document.body.style.overflow = 'hidden';

    var input = document.getElementById('accessGateInput');
    var btn = document.getElementById('accessGateBtn');
    var err = document.getElementById('accessGateErr');
    function submit() {
      if ((input.value || '').trim() === ACCESS_CODE) {
        sessionStorage.setItem(SESSION_KEY, '1');
        document.body.style.overflow = '';
        ov.remove();
      } else {
        err.textContent = '접근 코드가 올바르지 않습니다.';
        input.value = '';
        input.focus();
      }
    }
    btn.addEventListener('click', submit);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    setTimeout(function () { input.focus(); }, 50);
  }

  if (document.body) buildOverlay();
  else document.addEventListener('DOMContentLoaded', buildOverlay);
})();
