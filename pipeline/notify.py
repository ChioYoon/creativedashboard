"""
배치 알림 모듈 — Stage 4.

목적:
- nightly batch 결과를 이메일로 발송 (성공/부분실패/실패 모두)
- SMTP 미설정 시 로그 파일 폴백
- HTML + 플레인 본문 동시 발송 (메일 클라이언트 호환)

설정 (.env):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=youraccount@gmail.com
    SMTP_PASSWORD=app-password-here   ← Gmail 앱 비밀번호 또는 Office 365 비밀번호
    SMTP_FROM=youraccount@gmail.com
    NOTIFY_TO=chioyoon@com2us.com

문제 해결:
- Gmail: 2FA 활성화 → 앱 비밀번호 발급 (https://myaccount.google.com/apppasswords)
- Office 365: SMTP AUTH 가 도메인 관리자에 의해 허용된 경우만 작동
- 둘 다 안 되면: NOTIFY_TO 만 설정하고 SMTP_* 비워두면 로그 파일에만 기록
"""

from __future__ import annotations

import os
import smtplib
import socket
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

KST = timezone(timedelta(hours=9))
LOG_DIR = Path("logs")


# ─────────────────────────────────────────────────────────────
# 1. 본문 빌더
# ─────────────────────────────────────────────────────────────
def _status_label(s: str) -> str:
    return {
        "success": "✅ 성공",
        "partial": "⚠️ 부분 실패",
        "empty": "📭 대상 없음",
        "skipped": "⏭ 건너뜀",
        "dry_run": "🔧 DRY-RUN",
        "config_error": "❌ 설정 오류",
        "exception": "💥 예외 발생",
    }.get(s, f"❓ {s}")


def _overall_status(results: list[dict]) -> tuple[str, str]:
    """전체 상태 → (subject_prefix, summary_label)."""
    if not results:
        return ("[CLOOP]", "결과 없음")
    statuses = {r.get("status", "?") for r in results}
    bad = {"partial", "config_error", "exception"}
    if statuses & bad:
        return ("[CLOOP ⚠️]", "일부 실패")
    if statuses == {"success"}:
        return ("[CLOOP ✅]", "전부 성공")
    return ("[CLOOP ℹ️]", "혼합 결과")


def _build_subject(batch_result: dict) -> str:
    results = batch_result.get("results", [])
    prefix, label = _overall_status(results)
    now = datetime.now(KST).strftime("%Y-%m-%d")
    return f"{prefix} 야간 태깅 — {label} ({now})"


def _build_plain_body(batch_result: dict) -> str:
    results = batch_result.get("results", [])
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    lines = [
        f"Com2uS R팀 CLOOP 야간 자동 태깅 결과",
        f"실행 시각: {now_str}",
        f"총 소요: {batch_result.get('batch_duration_sec', 0):.1f}초",
        f"타이틀 수: {batch_result.get('title_count', 0)}",
        "",
        "─" * 60,
        "타이틀별 결과",
        "─" * 60,
    ]
    for r in results:
        lines.append(f"")
        lines.append(f"▸ {r.get('title', '?')}")
        lines.append(f"    상태:        {_status_label(r.get('status', '?'))}")
        lines.append(f"    스캔 폴더:    {r.get('scanned_folders', 0)}")
        lines.append(f"    태깅 완료:    {r.get('tagged_records', 0)}")
        lines.append(f"    캐시 히트:    {r.get('cache_hits', 0)}")
        lines.append(f"    Gemini 호출:  {r.get('cache_misses', 0)}")
        lines.append(f"    실패:        {r.get('failures', 0)}")
        if r.get("fallback_used"):
            lines.append(f"    폴백 모델:    ✅ gemini-2.5-flash-lite")
        if r.get("daily_quota_exhausted"):
            lines.append(f"    quota 한도:   ⚠️ 폴백 모델도 한도 도달")
        kpi_status = r.get("kpi_status")
        if kpi_status and kpi_status != "skipped":
            kpi_label = {
                "success": f"✅ 성공 ({r.get('kpi_rows_fetched', 0)}행, {r.get('kpi_creatives_matched', 0)}개 소재 매칭)",
                "failed": "❌ 실패 (태깅만 진행, KPI=0)",
                "auth_failed": "🔑 인증 만료 — refresh token 재발급 필요",
            }.get(kpi_status, kpi_status)
            lines.append(f"    KPI fetch:   {kpi_label}")
        if r.get("output_path"):
            lines.append(f"    산출:        {r['output_path']}")
        errors = r.get("errors", [])
        if errors:
            lines.append(f"    오류:")
            for e in errors[:5]:
                lines.append(f"      - {e[:150]}")

    lines.append("")
    lines.append("─" * 60)
    lines.append("대시보드: https://chioyoon.github.io/creativedashboard/step1_integrated.html")
    lines.append("로그: 본인 PC C:\\claude\\cloop_dashboard\\logs\\")
    lines.append("")
    return "\n".join(lines)


def _build_html_body(batch_result: dict) -> str:
    results = batch_result.get("results", [])
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    _, summary_label = _overall_status(results)

    rows = []
    for r in results:
        status = r.get("status", "?")
        color = {
            "success": "#10b981",
            "partial": "#f59e0b",
            "empty": "#6b7280",
            "skipped": "#6b7280",
            "config_error": "#ef4444",
            "exception": "#ef4444",
        }.get(status, "#9ca3af")
        fallback_badge = ""
        if r.get("fallback_used"):
            fallback_badge = ' <span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:6px;font-size:11px;">flash-lite 폴백</span>'
        quota_badge = ""
        if r.get("daily_quota_exhausted"):
            quota_badge = ' <span style="background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:6px;font-size:11px;">quota 한도</span>'
        kpi_badge = ""
        kpi_status = r.get("kpi_status", "skipped")
        if kpi_status == "success":
            rows = r.get("kpi_rows_fetched", 0)
            kpi_badge = f' <span style="background:#dcfce7;color:#166534;padding:2px 6px;border-radius:6px;font-size:11px;">KPI {rows}행</span>'
        elif kpi_status == "failed":
            kpi_badge = ' <span style="background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:6px;font-size:11px;">KPI 실패</span>'
        elif kpi_status == "auth_failed":
            kpi_badge = ' <span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:6px;font-size:11px;">🔑 KPI 인증 만료</span>'
        errors_html = ""
        if r.get("errors"):
            error_items = "".join(
                f"<li style='font-size:11px;color:#7f1d1d;'>{e[:200]}</li>"
                for e in r["errors"][:3]
            )
            errors_html = f"<ul style='margin:4px 0;padding-left:20px;'>{error_items}</ul>"

        rows.append(f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:10px;"><strong>{r.get('title', '?')}</strong>{fallback_badge}{quota_badge}{kpi_badge}</td>
          <td style="padding:10px;"><span style="background:{color};color:white;padding:3px 10px;border-radius:12px;font-size:12px;">{_status_label(status)}</span></td>
          <td style="padding:10px;text-align:right;">{r.get('tagged_records', 0)} / {r.get('scanned_folders', 0)}</td>
          <td style="padding:10px;text-align:right;">{r.get('cache_misses', 0)}</td>
          <td style="padding:10px;text-align:right;color:{'#ef4444' if r.get('failures', 0) else '#10b981'};">{r.get('failures', 0)}</td>
        </tr>
        {f'<tr><td colspan="5" style="padding:0 10px 10px;">{errors_html}</td></tr>' if errors_html else ''}
        """)

    body = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
</head>
<body style="font-family:'Malgun Gothic',-apple-system,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
  <div style="max-width:680px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08);">
    <div style="background:linear-gradient(135deg,#E84855,#ff6b6b);color:white;padding:24px;">
      <div style="font-size:13px;opacity:.85;letter-spacing:2px;text-transform:uppercase;">Com2uS R-Team CLOOP</div>
      <h1 style="margin:8px 0 0;font-size:22px;">야간 자동 태깅 — {summary_label}</h1>
      <div style="font-size:13px;opacity:.9;margin-top:6px;">{now_str}</div>
    </div>

    <div style="padding:20px 24px;background:#fafafa;border-bottom:1px solid #e5e7eb;display:flex;gap:24px;font-size:13px;">
      <div><strong style="color:#6b7280;">타이틀 수</strong> {batch_result.get('title_count', 0)}</div>
      <div><strong style="color:#6b7280;">총 소요</strong> {batch_result.get('batch_duration_sec', 0):.1f}초</div>
    </div>

    <div style="padding:0;">
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">
            <th style="padding:12px 10px;text-align:left;color:#6b7280;">타이틀</th>
            <th style="padding:12px 10px;text-align:left;color:#6b7280;">상태</th>
            <th style="padding:12px 10px;text-align:right;color:#6b7280;">태깅/스캔</th>
            <th style="padding:12px 10px;text-align:right;color:#6b7280;">호출</th>
            <th style="padding:12px 10px;text-align:right;color:#6b7280;">실패</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows) if rows else '<tr><td colspan="5" style="padding:24px;text-align:center;color:#9ca3af;">결과 없음</td></tr>'}
        </tbody>
      </table>
    </div>

    <div style="padding:20px 24px;background:#fafafa;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
      <div style="margin-bottom:6px;">📊 <a href="https://chioyoon.github.io/creativedashboard/step1_integrated.html" style="color:#E84855;text-decoration:none;">대시보드 열기</a></div>
      <div>📁 로그: <code style="background:#fff;padding:2px 6px;border-radius:4px;">C:\\claude\\cloop_dashboard\\logs\\</code></div>
    </div>
  </div>
</body>
</html>
"""
    return body


# ─────────────────────────────────────────────────────────────
# 2. SMTP 발송
# ─────────────────────────────────────────────────────────────
def _send_via_smtp(subject: str, plain: str, html: str) -> bool:
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587") or "587")
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM", user).strip()
    to_addr = os.environ.get("NOTIFY_TO", "").strip()

    if not (host and user and password and to_addr):
        return False  # SMTP 미설정 → 폴백

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=context)
                s.login(user, password)
                s.send_message(msg)
        print(f"📧 이메일 발송 완료 → {to_addr}")
        return True
    except (smtplib.SMTPException, socket.error, OSError) as e:
        print(f"⚠️  SMTP 발송 실패: {type(e).__name__}: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# 3. 로그 파일 폴백
# ─────────────────────────────────────────────────────────────
def _write_log_fallback(subject: str, plain: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fname = datetime.now(KST).strftime("nightly_%Y%m%d_%H%M%S.log")
    path = LOG_DIR / fname
    path.write_text(
        f"Subject: {subject}\n\n{plain}\n",
        encoding="utf-8",
    )
    print(f"📁 로그 파일 기록 → {path}")
    return path


# ─────────────────────────────────────────────────────────────
# 4. 외부 엔트리
# ─────────────────────────────────────────────────────────────
def send_batch_notification(batch_result: dict) -> None:
    """배치 결과를 이메일 또는 로그 파일로 알림.

    SMTP 설정이 완전하면 이메일, 아니면 logs/ 디렉토리에 기록.
    실패해도 예외를 raise 하지 않음 (호출자가 무시 가능하게).
    """
    subject = _build_subject(batch_result)
    plain = _build_plain_body(batch_result)
    html = _build_html_body(batch_result)

    # 1차 시도: SMTP
    if _send_via_smtp(subject, plain, html):
        # 로그도 보존 (메일 못 받은 경우 대비)
        _write_log_fallback(subject, plain)
        return

    # 폴백: 로그 파일만
    _write_log_fallback(subject, plain)
    print(
        "ℹ️  SMTP 미설정 또는 발송 실패 → 로그 파일만 기록되었습니다. "
        "이메일 알림이 필요하면 .env 의 SMTP_* 항목을 설정하세요."
    )


def send_test_email(to_addr: str | None = None) -> bool:
    """테스트 이메일 발송. setup-email.ps1 에서 호출."""
    test_addr = to_addr or os.environ.get("NOTIFY_TO", "")
    if not test_addr:
        print("❌ NOTIFY_TO 가 설정되지 않았습니다.")
        return False

    fake_batch = {
        "title_count": 1,
        "batch_duration_sec": 0.5,
        "results": [
            {
                "title": "test-title",
                "status": "success",
                "scanned_folders": 5,
                "tagged_records": 5,
                "cache_hits": 3,
                "cache_misses": 2,
                "failures": 0,
                "output_path": "public/data/test.json",
                "errors": [],
            }
        ],
    }
    subject = "[CLOOP 테스트] SMTP 설정 검증"
    plain = _build_plain_body(fake_batch)
    html = _build_html_body(fake_batch)
    return _send_via_smtp(subject, plain, html)


if __name__ == "__main__":
    # 디버그용: 직접 실행 시 테스트 메일 발송
    load_dotenv_if_available = True
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    ok = send_test_email()
    if not ok:
        import sys
        sys.exit(1)
