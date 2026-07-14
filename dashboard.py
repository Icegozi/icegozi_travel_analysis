"""Sinh dashboard HTML tĩnh (CSS/JS thuần) từ kết quả phân tích HTML."""

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "data" / "analysis"
OUTPUT_FILE = ROOT_DIR / "docs" / "index.html"
DATA_EXPORTS = [
    ("VNTRIP — dữ liệu bài viết thô", "data/VNTRIP/rawdata.csv", "rawdata_vntrip.csv", "Bài viết HTML đã parse từ VNTRIP."),
    ("VNTRIP — danh sách liên kết", "data/VNTRIP/links_vntrip.csv", "links_vntrip.csv", "Các URL bài viết phát hiện từ trang danh mục."),
    ("VNTRIP — lịch sử snapshot", "data/VNTRIP/article_snapshots.csv", "article_snapshots.csv", "Lượt xem theo từng lần thu thập."),
    ("Vietnam.travel — dữ liệu bài viết thô", "data/VIETNAM_TRAVEL/rawdata.csv", "rawdata_vietnam_travel.csv", "Bài viết và trang điểm đến đã parse."),
    ("Vietnam.travel — danh sách liên kết", "data/VIETNAM_TRAVEL/links_vietnam_travel.csv", "links_vietnam_travel.csv", "Các URL công khai đã phát hiện."),
    ("Dữ liệu đã chuẩn hóa", "data/analysis/normalized_articles.csv", "normalized_articles.csv", "Nội dung đã làm sạch, khử trùng và gán nhãn."),
    ("Báo cáo điểm cơ hội", "data/analysis/destination_opportunity_scores.csv", "destination_opportunity_scores.csv", "Xếp hạng điểm đến và khuyến nghị hành động."),
    ("Thống kê mùa vụ", "data/analysis/destination_season_stats.csv", "destination_season_stats.csv", "Lượt xem/ngày theo điểm đến và mùa."),
    ("Rà soát nhãn", "data/analysis/label_review.csv", "label_review.csv", "Nhãn tự động, bằng chứng từ khóa và trạng thái kiểm tra."),
]


def read_csv(name, columns):
    path = ANALYSIS_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)


def build_dashboard():
    scores = read_csv("destination_opportunity_scores.csv", ["destination"])
    seasons = read_csv("destination_season_stats.csv", ["destination", "season", "median_views_per_day"])
    articles = read_csv("normalized_articles.csv", ["source", "collected_at"])
    validation = read_csv("label_validation_summary.csv", ["article_count", "duplicate_removed", "destination_needs_review", "theme_needs_review"])
    scores = scores.fillna(0).sort_values("opportunity_score", ascending=False)
    data = scores.to_dict(orient="records")
    season_data = seasons.fillna(0).to_dict(orient="records")
    metrics = {
        "destinations": len(scores),
        "articles": int(pd.to_numeric(scores.get("article_count", pd.Series(dtype=float)), errors="coerce").sum()),
        "views": float(pd.to_numeric(scores.get("total_views", pd.Series(dtype=float)), errors="coerce").sum()),
        "growth": float(pd.to_numeric(scores.get("latest_views_growth", pd.Series(dtype=float)), errors="coerce").sum()),
    }
    source_rows = []
    source_summary = pd.DataFrame(columns=["source", "article_count", "latest_collected_at"])
    if not articles.empty and "source" in articles:
        source_summary = articles.groupby("source", as_index=False).agg(
            article_count=("source", "size"), latest_collected_at=("collected_at", "max")
        )
    source_lookup = source_summary.set_index("source").to_dict("index") if not source_summary.empty else {}
    for source, label in {"VNTRIP": "VNTRIP", "VIETNAM_TRAVEL": "Vietnam.travel"}.items():
        row = source_lookup.get(source, {"article_count": 0, "latest_collected_at": None})
        collected = pd.to_datetime(row["latest_collected_at"], errors="coerce", utc=True)
        if row["article_count"]:
            collected_text = collected.strftime("%d/%m/%Y %H:%M UTC") if not pd.isna(collected) else "không xác định"
            source_rows.append(
                f'<div class="source-card"><b>{html.escape(label)}</b>'
                f'<span>{int(row["article_count"])} bài đã parse</span><small>Cập nhật: {collected_text}</small></div>'
            )
        else:
            source_rows.append(
                f'<div class="source-card"><b>{html.escape(label)}</b>'
                '<span>0 bài đã parse</span><small>Chưa có dữ liệu trong lần chạy này</small></div>'
            )
    source_cards = "".join(source_rows) or '<p class="note">Chưa có dữ liệu nguồn.</p>'
    checks = validation.iloc[0].to_dict() if not validation.empty else {}
    check_text = (
        f'{int(checks.get("article_count", 0))} bài hợp lệ; '
        f'{int(checks.get("duplicate_removed", 0))} bản ghi trùng đã loại; '
        f'{int(checks.get("destination_needs_review", 0))} nhãn điểm đến và '
        f'{int(checks.get("theme_needs_review", 0))} nhãn chủ đề cần rà soát.'
    )
    export_dir = OUTPUT_FILE.parent / "data"
    export_dir.mkdir(parents=True, exist_ok=True)
    downloads = []
    for title, relative_source, filename, description in DATA_EXPORTS:
        source = ROOT_DIR / relative_source
        if source.exists():
            destination = export_dir / filename
            shutil.copy2(source, destination)
            downloads.append({
                "title": title, "file": f"data/{filename}", "description": description,
                "size_kb": round(destination.stat().st_size / 1024, 1),
            })
    generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    page = f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Du lịch Việt Nam | Bảng điều hành nội dung</title>
<style>
:root{{--navy:#102a43;--blue:#1479c9;--teal:#00a99d;--orange:#f59e0b;--bg:#f4f7fb;--ink:#243b53;--muted:#627d98;--line:#d9e2ec}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{background:linear-gradient(125deg,#0b2943,#17699e);color:#fff;padding:38px max(22px,calc((100% - 1180px)/2)) 32px}} h1{{margin:0;font-size:clamp(25px,4vw,38px)}} header p{{margin:7px 0 0;opacity:.85}}
main{{max-width:1180px;margin:26px auto 52px;padding:0 18px}} .cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}} .card,.panel{{background:#fff;border-radius:14px;box-shadow:0 4px 18px #102a4310;padding:20px}}
.metric{{font-size:28px;font-weight:800;color:var(--navy)}} .muted,.note{{color:var(--muted);font-size:13px}} .grid{{display:grid;grid-template-columns:1.1fr .9fr;gap:18px;margin-top:18px}} h2{{margin:0 0 14px;font-size:19px}}
.actions{{display:grid;gap:10px}} .action{{border:1px solid var(--line);border-left:5px solid var(--teal);border-radius:9px;padding:12px 14px}} .action strong{{display:block}} .action p{{margin:3px 0 0;color:var(--muted)}}
.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}} button{{border:1px solid var(--line);background:#fff;border-radius:20px;padding:6px 12px;color:var(--ink);cursor:pointer}} button.active{{background:var(--navy);border-color:var(--navy);color:#fff}}
.chart{{min-height:320px;display:grid;gap:10px;align-content:start}} .bar-row{{display:grid;grid-template-columns:115px 1fr 58px;gap:10px;align-items:center}} .label{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} .track{{height:13px;background:#e7eef5;border-radius:20px;overflow:hidden}} .bar{{height:100%;border-radius:20px;background:linear-gradient(90deg,var(--blue),var(--teal));transition:width .35s}}
.heatmap{{display:grid;grid-template-columns:120px repeat(4,1fr);gap:5px;align-items:center;font-size:13px}} .cell{{min-height:34px;padding:7px;border-radius:5px;text-align:center}} .head{{font-weight:700;color:var(--muted)}}
.filter{{width:100%;border:1px solid var(--line);border-radius:8px;padding:9px 11px;font:inherit;margin:0 0 12px}} .scroll{{overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:820px}} th{{text-align:left;color:var(--muted);font-size:12px;text-transform:uppercase}} td,th{{padding:11px 8px;border-bottom:1px solid #e8eef5;vertical-align:top}} .pill{{font-size:12px;border-radius:20px;padding:3px 8px;background:#e6fffb;color:#087e78;white-space:nowrap}} footer{{text-align:center;color:var(--muted);padding:14px}}
.sources{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}} .source-card{{position:relative;overflow:hidden;background:linear-gradient(135deg,#f7fafc,#edf7ff);border:1px solid var(--line);border-radius:11px;padding:14px}} .source-card:before{{content:'⌁';position:absolute;right:12px;top:-8px;font-size:46px;color:#1479c91c}} .source-card b,.source-card span,.source-card small{{display:block;position:relative}} .source-card span{{font-size:18px;font-weight:800;margin:4px 0;color:var(--navy)}} .source-card small{{color:var(--muted)}} .provenance ul{{margin:14px 0;padding-left:20px}} .provenance li{{margin:7px 0}} .glossary{{margin-top:18px;padding-top:18px;border-top:1px solid var(--line)}} .glossary h3{{margin:0 0 10px;font-size:16px}} .term-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .term{{background:#fbfdff;border:1px solid #dcebf7;border-radius:10px;padding:12px}} .term b{{display:block;color:#086a8f;margin-bottom:3px}} .term p{{margin:0;color:var(--muted);font-size:13px}} .term .icon{{font-size:19px;margin-right:5px}} .download-list{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,1fr);gap:10px}} .download-item{{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdff}} .download-item b,.download-item small{{display:block}} .download-item small{{color:var(--muted)}} .download-button{{flex:none;background:var(--navy);color:#fff;border:0;border-radius:7px;padding:8px 10px;font:inherit;font-size:13px}} .download-button:hover{{background:var(--blue)}}
@media(max-width:780px){{.cards{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}.term-grid,.download-list{{grid-template-columns:1fr 1fr}}}} @media(max-width:420px){{.cards,.term-grid,.download-list{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Bảng điều hành nội dung du lịch</h1><p>Tín hiệu từ bài viết HTML công khai · ưu tiên hành động theo mức độ quan tâm trực tuyến.</p></header>
<main>
<section class="cards"><div class="card"><div class="muted">Điểm đến phân tích</div><div class="metric" id="m-dest"></div></div><div class="card"><div class="muted">Bài viết hợp lệ</div><div class="metric" id="m-articles"></div></div><div class="card"><div class="muted">Tổng lượt xem</div><div class="metric" id="m-views"></div></div><div class="card"><div class="muted">Tăng lượt xem snapshot mới nhất</div><div class="metric" id="m-growth"></div></div></section>
<section class="grid"><article class="panel"><h2>Việc cần làm ngay</h2><div id="actions" class="actions"></div></article><article class="panel"><h2>Cách đọc kết quả</h2><p>Điểm cơ hội gồm <b>70% lượt xem/ngày</b> và <b>30% số bài viết</b>, chuẩn hóa trong tập dữ liệu hiện có.</p><p class="note">Tăng trưởng là tổng lượt xem/ngày tăng thêm ở snapshot mới nhất. Đây là tín hiệu quan tâm tới nội dung, không phải dự báo số khách hoặc doanh thu.</p></article></section>
<section class="grid"><article class="panel"><h2>Biểu đồ điểm cơ hội</h2><div class="tabs"><button class="active" data-mode="score">Điểm cơ hội</button><button data-mode="growth">Tăng trưởng snapshot</button></div><div id="bar-chart" class="chart"></div></article><article class="panel"><h2>Heatmap mùa vụ</h2><div id="heatmap" class="heatmap"></div></article></section>
<section class="panel" style="margin-top:18px"><h2>Danh sách ưu tiên</h2><input id="search" class="filter" placeholder="Lọc theo điểm đến hoặc khuyến nghị…"><div class="scroll"><table><thead><tr><th>#</th><th>Điểm đến</th><th>Điểm cơ hội</th><th>Lượt xem/ngày</th><th>Tăng snapshot</th><th>Hành động đề xuất</th></tr></thead><tbody id="ranking"></tbody></table></div></section>
<section class="panel provenance" style="margin-top:18px"><h2>Nguồn dữ liệu &amp; mức độ tin cậy</h2><div class="sources">{source_cards}</div><ul><li><b>Phạm vi:</b> bài viết/trang điểm đến HTML công khai từ VNTRIP và Vietnam.travel; crawler kiểm tra `robots.txt`, không đăng nhập và không thu thập dữ liệu cá nhân.</li><li><b>Kiểm soát chất lượng:</b> {check_text}</li><li><b>Kiểm chứng:</b> xem `duplicate_articles.csv`, `label_review.csv` và `label_validation_summary.csv` trong thư mục `data/analysis/` để truy vết từng bước làm sạch/gán nhãn.</li><li><b>Giới hạn:</b> lượt xem là chỉ báo mức độ quan tâm tới nội dung trực tuyến, không phải số khách, doanh thu hoặc thị phần.</li></ul><div class="glossary"><h3>Giải thích thuật ngữ</h3><div class="term-grid"><div class="term"><b><span class="icon">⌘</span>Bài đã parse</b><p>Trang HTML đã được crawler đọc, trích xuất tiêu đề, ngày đăng, nội dung và lượt xem.</p></div><div class="term"><b><span class="icon">◷</span>Lượt xem/ngày</b><p>Lượt xem chia cho số ngày từ lúc bài đăng đến lúc thu thập; dùng để so sánh công bằng giữa bài cũ và mới.</p></div><div class="term"><b><span class="icon">↗</span>Snapshot</b><p>Bản ghi lượt xem của cùng một bài tại một thời điểm. So sánh snapshot cho biết mức tăng quan tâm.</p></div><div class="term"><b><span class="icon">★</span>Điểm cơ hội</b><p>Điểm 0–100, gồm 70% lượt xem/ngày và 30% số bài viết, dùng để xếp thứ tự ưu tiên nội dung.</p></div><div class="term"><b><span class="icon">▦</span>Heatmap mùa vụ</b><p>Ô màu càng đậm nghĩa là lượt xem/ngày của điểm đến trong mùa đó càng cao.</p></div><div class="term"><b><span class="icon">✓</span>Gán nhãn &amp; kiểm tra</b><p>Hệ thống gán địa danh/chủ đề theo từ khóa; các nhãn chưa chắc chắn được đưa vào tệp rà soát thủ công.</p></div></div></div></section>
<section class="panel" style="margin-top:18px"><h2>Tải dữ liệu CSV</h2><p class="note">Chọn bộ dữ liệu cần dùng. Tệp được xuất cùng dashboard để có thể tải trực tiếp trên GitHub Pages.</p><ul id="download-list" class="download-list"></ul></section>
</main><footer>Icegozi © 2026 · Tạo lúc {generated_at}</footer>
<script>
const scores={json.dumps(data, ensure_ascii=False)};
const seasons={json.dumps(season_data, ensure_ascii=False)};
const metrics={json.dumps(metrics, ensure_ascii=False)};
const downloads={json.dumps(downloads, ensure_ascii=False)};
const fmt=(n,d=0)=>new Intl.NumberFormat('vi-VN',{{maximumFractionDigits:d}}).format(Number(n||0));
document.querySelector('#m-dest').textContent=fmt(metrics.destinations);
document.querySelector('#m-articles').textContent=fmt(metrics.articles);
document.querySelector('#m-views').textContent=fmt(metrics.views);
document.querySelector('#m-growth').textContent='+'+fmt(metrics.growth,1);
function renderActions(){{const target=document.querySelector('#actions'); target.innerHTML=scores.slice(0,3).map((r,i)=>`<div class="action"><strong>${{i+1}}. ${{r.destination}} <span class="pill">${{fmt(r.opportunity_score,1)}} điểm</span></strong><p>${{r.recommendation}} Tăng snapshot: +${{fmt(r.latest_views_growth,1)}} lượt xem/ngày.</p></div>`).join('')||'<p class="note">Chưa có dữ liệu.</p>';}}
function renderBars(mode='score'){{const field=mode==='score'?'opportunity_score':'latest_views_growth';const rows=[...scores].sort((a,b)=>Number(b[field]||0)-Number(a[field]||0)).slice(0,10);const max=Math.max(...rows.map(r=>Number(r[field]||0)),1);document.querySelector('#bar-chart').innerHTML=rows.map(r=>`<div class="bar-row"><div class="label">${{r.destination}}</div><div class="track"><div class="bar" style="width:${{Number(r[field]||0)/max*100}}%"></div></div><b>${{mode==='score'?fmt(r[field],1):'+'+fmt(r[field],1)}}</b></div>`).join('')||'<p class="note">Chưa có dữ liệu.</p>';}}
function renderHeatmap(){{const months=['Xuân','Hè','Thu','Đông'];const destinations=[...new Set(seasons.map(x=>x.destination))].slice(0,10);const max=Math.max(...seasons.map(x=>Number(x.median_views_per_day||0)),1);let out='<div class="cell head">Điểm đến</div>'+months.map(m=>`<div class="cell head">${{m}}</div>`).join('');destinations.forEach(d=>{{out+=`<div class="cell head">${{d}}</div>`;months.forEach(m=>{{const row=seasons.find(x=>x.destination===d&&x.season===m);const value=Number(row?.median_views_per_day||0);const alpha=.12+.78*value/max;out+=`<div class="cell" style="background:rgba(0,169,157,${{alpha}});color:${{alpha>.55?'white':'#243b53'}}">${{fmt(value,1)}}</div>`;}})}});document.querySelector('#heatmap').innerHTML=out;}}
function renderTable(query=''){{const q=query.toLowerCase();const rows=scores.filter(r=>`${{r.destination}} ${{r.recommendation}}`.toLowerCase().includes(q));document.querySelector('#ranking').innerHTML=rows.map((r,i)=>`<tr><td>${{i+1}}</td><td><b>${{r.destination}}</b></td><td>${{fmt(r.opportunity_score,1)}}</td><td>${{fmt(r.median_views_per_day,2)}}</td><td>+${{fmt(r.latest_views_growth,1)}}</td><td>${{r.recommendation}}</td></tr>`).join('')||'<tr><td colspan="6" class="note">Không có kết quả phù hợp.</td></tr>';}}
async function downloadCsv(file,name){{try{{const response=await fetch(file);if(!response.ok)throw new Error('Không tải được tệp');const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);}}catch(error){{window.location.href=file;}}}}
function renderDownloads(){{document.querySelector('#download-list').innerHTML=downloads.map(item=>`<li class="download-item"><div><b>${{item.title}}</b><small>${{item.description}} · ${{fmt(item.size_kb,1)}} KB</small></div><button class="download-button" data-file="${{item.file}}" data-name="${{item.file.split('/').pop()}}">Tải CSV</button></li>`).join('')||'<li class="note">Chưa có tệp dữ liệu để tải.</li>';document.querySelectorAll('.download-button').forEach(button=>button.onclick=()=>downloadCsv(button.dataset.file,button.dataset.name));}}
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('[data-mode]').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderBars(b.dataset.mode);}});document.querySelector('#search').oninput=e=>renderTable(e.target.value);renderActions();renderBars();renderHeatmap();renderTable();renderDownloads();
</script></body></html>'''
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(page, encoding="utf-8")
    print(f"Đã tạo dashboard: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_dashboard()
