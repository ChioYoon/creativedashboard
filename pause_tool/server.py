r"""
pause_tool 로컬 웹앱(localhost 전용) — 저효율 제외 추천 소재를 승인 후 Google Ads에서 제거/복원.

흐름: 대시보드서 제외추천 CSV 내보내기 → 여기 붙여넣기 → public/data 매핑으로 asset 펼침
     → 후보 렌더 → 체크·[dry-run]로 계획 확인 → [실제 제거] 승인 실행 → 필요시 [복원].

⚠️ 실제 제거/복원은 라이브 광고 변경(비용·서빙). dry-run 기본, 사람 승인 필수. localhost만.
의존성 0(stdlib http.server). 서버측 자격증명(.secrets/google_ads.yaml) 재사용.

실행:  .\.venv\Scripts\python.exe -m pause_tool.server   (기본 http://127.0.0.1:8765)
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pause_tool import mapping
from pipeline import pause as P

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public" / "data"
HTML = Path(__file__).resolve().parent / "index.html"
HOST, PORT = "127.0.0.1", 8765

# 라이브 클라이언트는 최초 요청 때 1회 생성(자격증명 없으면 후보 조회는 되되 실행만 막힘).
_client = None


def _live():
    global _client
    if _client is None:
        client = P.load_client()
        _client = (client, client.get_service("GoogleAdsService"))
    return _client


def list_titles() -> list[str]:
    return sorted(p.stem for p in DATA.glob("*.json"))


def load_title(title: str) -> dict:
    return json.loads((DATA / f"{title}.json").read_text(encoding="utf-8"))


def do_candidates(body: dict) -> dict:
    title = body["title"]
    keys = mapping.parse_reco_csv(body.get("csv_text", ""))
    cands = mapping.build_candidates(keys, load_title(title))
    return {"title": title, "count": len(cands), "candidates": cands}


def _asset_ids_for(ga, cid, item, start, end) -> set[str]:
    """후보의 확보된 asset_id + (asset_id 없는) 이름 라이브 resolve 합집합."""
    ids = set(item.get("video_asset_ids") or [])
    for name in item.get("video_names") or []:
        ids |= P.resolve_asset_ids(ga, cid, name, start, end)
    return ids


def do_change(body: dict) -> dict:
    """items 각각을 제거(remove) 또는 복원(resume). mode: dry|apply|resume|resume-apply."""
    title = body["title"]
    mode = body.get("mode", "dry")
    resume = mode.startswith("resume")
    apply = mode.endswith("apply")
    start = body.get("start") or str(date.today() - timedelta(days=30))
    end = body.get("end") or str(date.today())
    min_keep = int(body.get("min_keep", 1))

    client, ga = _live()
    cid = P.customer_id_for_title(title)
    out = []
    for item in body.get("items") or []:
        row = {"key": item.get("key"), "asset_ids": [], "ads": []}
        try:
            ids = _asset_ids_for(ga, cid, item, start, end)
            row["asset_ids"] = sorted(ids)
            if not ids:
                row["error"] = "asset id 못 찾음(이름 매칭 실패 — nightly 후 asset_id 채워지면 해결)"
                out.append(row); continue
            ads = P.find_ads_for_assets(ga, cid, ids, start, end)
            row["ads"] = P.change_asset(client, ga, cid, ids, ads,
                                        remove=not resume, apply=apply, min_keep=min_keep)
        except Exception as e:
            row["error"] = str(e)
        out.append(row)
    return {"title": title, "mode": mode, "apply": apply, "results": out}


ROUTES = {"/api/candidates": do_candidates, "/api/change": do_change}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/titles":
            return self._send(200, {"titles": list_titles()})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        fn = ROUTES.get(self.path.split("?")[0])
        if not fn:
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, fn(body))
        except Exception as e:
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *a):  # 조용히
        pass


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"pause_tool -> http://{HOST}:{PORT}  (Ctrl+C 종료)")
    print("[주의] 실제 제거/복원은 라이브 광고 변경. dry-run으로 먼저 확인 후 승인 실행.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료.")
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
