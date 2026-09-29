# nightly 알림 경로 — 미완 2건

> 작성 2026-09-30 · CLOOP 내부 메모 (R팀 공유 문서 아님)
> 배경: 2026-09-23~29 nightly push 가 7일간 막혔는데 아무도 몰랐다. 근본 원인(`pull` 부재)은
> 해소됐으나, **실패를 알아차리는 경로**가 아직 둘 다 닫혀 있다.

---

## 무슨 일이 있었나

```
09-22 13:06  nightly 커밋·push 성공 (마지막 정상)
09-22 14:01  원격에 직접 커밋 (js/titles_overrides.json · mwlee-rep)
09-23 13:07  nightly push → ! [rejected] main -> main (fetch first)
09-28 ×2 · 09-29  동일 거부 반복
09-30       발견 — 로컬에 미푸시 nightly 커밋 4건이 쌓여 있었다
```

라이브 대시보드가 **7일간 09-22 데이터로 고정**돼 있었다. 인증 문제가 아니라
`nightly.ps1` 이 `fetch`/`pull` 없이 `push` 만 해서, 원격에 직접 커밋이 한 번
들어간 순간부터 영구히 막힌 것이다.

**근본 원인은 해소됨** — `scripts/nightly.ps1:112` 에 `git pull --rebase origin main`
선행이 추가됐다(다른 세션 작업). 충돌 시 `rebase --abort` 후 push 스킵으로 처리돼
자동 해결로 꼬일 위험도 없다.

문제는 **왜 7일이나 몰랐는가** 이고, 그 답이 아래 2건이다.

---

## 미완 1 — push 실패가 스케줄러에 성공으로 보인다

`scripts/nightly.ps1` 마지막 줄:

```powershell
exit $pipelineExitCode
```

`$pipelineExitCode` 는 **파이프라인(태깅) 결과만** 담는다. push 가 실패해도
`Write-Log ERROR` 만 찍히고 종료 코드는 0이다.

```
파이프라인 성공 → push 실패 → exit 0 → 작업 스케줄러 "성공"
```

`CLOOP-Nightly` 작업 스케줄러는 종료 코드만 본다. 7일간 매일 "성공"으로 기록됐다.

### 고칠 방향

git 단계 실패를 종료 코드에 반영한다. 스크립트 안에 플래그를 하나 두고 마지막에 합친다.

```powershell
# Step 2 안에서
$gitFailed = $false
...
if ($pullExit -ne 0)  { $gitFailed = $true; ... }
if ($pushExit -ne 0)  { $gitFailed = $true; ... }

# 마지막
exit ($(if ($pipelineExitCode -ne 0 -or $gitFailed) { 1 } else { 0 }))
```

파이프라인과 git 실패를 구분하고 싶으면 종료 코드를 나눠도 된다(예: git 실패만 2).
스케줄러에서 "마지막 실행 결과"가 0이 아니게만 되면 목적은 달성된다.

> ⚠️ `scripts/nightly.ps1` 은 다른 세션이 작업 중인 파일이다. 손대기 전에 조율할 것.
> 같은 이유로 `Write-Log ERROR "Push failed (exit=$pushExit). Check auth or network."`
> 문구도 손보면 좋다 — 이번 실패는 인증도 네트워크도 아니었고, 그 문구 때문에
> 원인을 잘못 짚기 쉬웠다. 실제 사유는 바로 윗줄 `push:` 로그에 있다.

---

## 미완 2 — SMTP 알림이 인증 실패 상태

매 실행 로그 말미에 찍힌다.

```
⚠️  SMTP 발송 실패: SMTPAuthenticationError: (535, b'5.7.8 Username and Password
    not accepted. ... BadCredentials ... - gsmtp')
ℹ️  SMTP 미설정 또는 발송 실패 → 로그 파일만 기록되었습니다.
```

`.env` 의 `SMTP_USER` · `SMTP_PASSWORD` 에 값은 있으나 Gmail 이 거부한다.
`pipeline/notify.py` 주석대로 **Gmail 앱 비밀번호**가 필요하다(계정 비밀번호로는 안 됨).

- 2단계 인증이 켜진 계정에서 앱 비밀번호를 발급해 `SMTP_PASSWORD` 에 넣는다
- Office 365 를 쓴다면 도메인 관리자가 SMTP AUTH 를 허용해야 한다
- 어느 쪽도 안 되면 `SMTP_*` 를 비우고 로그 파일만 쓰는 편이 낫다 —
  지금처럼 값이 있는데 실패하는 상태는 "알림이 가고 있다"는 오해를 만든다

**CLOOP 에서 처리 불가** — 앱 비밀번호 발급은 계정 소유자만 할 수 있다.

---

## 정리

| # | 항목 | 담당 | 상태 |
| --- | --- | --- | --- |
| — | `pull --rebase` 선행 | 다른 세션 | ✅ 반영됨 |
| 1 | push 실패 → 종료 코드 1 | `nightly.ps1` 작업 세션과 조율 | ⏳ |
| 2 | SMTP 앱 비밀번호 재발급 | 계정 소유자 | ⏳ |

1번이 들어가기 전까지는 **스케줄러 성공 표시를 신뢰할 수 없다.** 라이브 반영 여부는
`git log origin/main` 또는 대시보드의 데이터 기준일로 직접 확인해야 한다.

같은 유형의 방어를 미러 자동 동기화(②-4)에는 처음부터 넣어 뒀다 —
경로 부재·정본 결손 시 태깅은 계속하되 **종료 코드 1**로 올린다
(`pipeline/main.py` `mirror_failed`). 참고 구현으로 볼 것.
