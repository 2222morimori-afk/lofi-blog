"""
Lo-Hi Music — 毎日記事自動生成スクリプト
GitHub Actions から呼び出される。
Claude が新しいLo-Fi音楽記事を生成し、index.html を更新する。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

client = anthropic.Anthropic()

BLOG_ROOT   = Path(__file__).parent.parent
ARTICLES    = BLOG_ROOT / "articles"
INDEX_HTML  = BLOG_ROOT / "index.html"
INSERT_MARK = "<!-- AUTO_INSERT_HERE -->"


# ──────────────────────────────────────────
# 1. 既存記事の一覧を取得
# ──────────────────────────────────────────

def get_existing_topics() -> list[str]:
    return [f.stem for f in ARTICLES.glob("*.html")]


# ──────────────────────────────────────────
# 2. Claude にトピックを決めてもらう
# ──────────────────────────────────────────

def pick_topic(existing: list[str]) -> dict:
    prompt = f"""あなたはLo-Fi/Hi-Fi音楽ブログ「Lo-Hi Music」のライターです。

すでに書かれた記事ファイル名：
{json.dumps(existing, ensure_ascii=False)}

まだカバーされていない、新しい記事のトピックを1つ提案してください。
以下のジャンルから選んでください：
- Lo-Fi Hip Hop / チルビート
- アンビエント / ドローン
- ジャズヒップホップ / ネオソウル
- シティポップ / ヴェイパーウェイブ
- 音楽制作 / サンプリング技術
- アーティスト紹介 / レーベル紹介
- 機材 / プラグイン紹介
- 音楽心理学 / 集中と音楽

必ず以下のJSON形式だけで回答してください（他の文章不要）：
{{
  "filename": "kebab-case-英語ファイル名（例: ambient-music-guide）",
  "title": "日本語タイトル（魅力的に）",
  "emoji": "記事に合う絵文字1つ",
  "tags": ["タグ1", "タグ2", "タグ3"],
  "excerpt": "記事の概要（80〜100文字）"
}}"""

    res = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in res.content if b.type == "text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"JSON が取得できませんでした: {text}")
    return json.loads(match.group())


# ──────────────────────────────────────────
# 3. Claude に記事本文を書いてもらう
# ──────────────────────────────────────────

def write_article_body(meta: dict) -> str:
    prompt = f"""Lo-Fi/Hi-Fi音楽ブログ「Lo-Hi Music」の記事を日本語で書いてください。

タイトル：{meta['title']}
タグ：{', '.join(meta['tags'])}

条件：
- HTML タグのみ（DOCTYPE・head・body 不要）
- <h2>、<h3>、<p>、<ul>/<li>、<blockquote>、<strong>、<code> を適切に使用
- 1800〜2200 文字程度
- Lo-Fi 音楽ファンが「へえ、そうなんだ」と思える内容
- 最後に「まとめ」セクションを入れる
- ブロッククオートは印象的な一文を1つ入れる"""

    res = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return next(b.text for b in res.content if b.type == "text")


# ──────────────────────────────────────────
# 4. 記事 HTML ファイルを生成
# ──────────────────────────────────────────

def build_article_html(meta: dict, body: str, date: str) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in meta["tags"])
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{meta['title']} — Lo-Hi Music</title>
  <meta name="description" content="{meta['excerpt']}" />
  <link rel="stylesheet" href="../style.css" />
</head>
<body>

<header>
  <nav class="container">
    <a href="../index.html" class="nav-logo">Lo<span>-</span>Hi<span> ♪</span></a>
    <ul class="nav-links">
      <li><a href="../index.html">ホーム</a></li>
      <li><a href="../index.html#articles">記事</a></li>
      <li><a href="../index.html#about">このブログについて</a></li>
    </ul>
  </nav>
</header>

<main>
  <div class="container">
    <article class="article-hero">
      <a href="../index.html" class="back-link">← ホームに戻る</a>
      <div class="article-tags">{tags_html}</div>
      <h1 class="article-title">{meta['title']}</h1>
      <div class="article-meta">
        <span>{date}</span>
        <span>·</span>
        <span>5 min read</span>
      </div>
      <div class="article-cover">{meta['emoji']}</div>
    </article>
    <div class="article-body">
{body}
    </div>
  </div>
</main>

<footer>
  <div class="container">
    <p>© 2025 <span>Lo-Hi Music</span> — Made with 🎵 &amp; ☕</p>
  </div>
</footer>

<div class="player-bar">
  <div class="player-info">
    <div class="player-thumb">{meta['emoji']}</div>
    <div class="player-text">
      <div class="player-track">lo-fi beats</div>
      <div class="player-artist">Lo-Hi Music</div>
    </div>
  </div>
  <div class="player-controls">
    <button class="player-btn">⏮</button>
    <button class="player-btn play">▶</button>
    <button class="player-btn">⏭</button>
  </div>
  <div class="player-progress">
    <span class="player-time">0:00</span>
    <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
    <span class="player-time">3:30</span>
  </div>
</div>

</body>
</html>
"""


# ──────────────────────────────────────────
# 5. index.html にカードを追加
# ──────────────────────────────────────────

def insert_card(meta: dict, date: str, filename: str) -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")

    if INSERT_MARK not in content:
        print(f"警告: '{INSERT_MARK}' が index.html に見つかりません", file=sys.stderr)
        return

    card = f"""
        <a href="articles/{filename}.html" class="card">
          <span class="card-emoji">{meta['emoji']}</span>
          <span class="card-tag">{meta['tags'][0]}</span>
          <h3 class="card-title">{meta['title']}</h3>
          <p class="card-excerpt">{meta['excerpt']}</p>
          <div class="card-meta">
            <span>{date}</span>
            <span class="dot">·</span>
            <span>5 min read</span>
          </div>
        </a>"""

    updated = content.replace(INSERT_MARK, INSERT_MARK + card)
    INDEX_HTML.write_text(updated, encoding="utf-8")


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main() -> None:
    today = datetime.now().strftime("%Y年%-m月%-d日")

    print("📝 トピックを選定中...")
    existing = get_existing_topics()
    meta = pick_topic(existing)
    print(f"✅ トピック決定: {meta['title']}")

    print("✍️  記事本文を生成中...")
    body = write_article_body(meta)
    print(f"✅ 本文生成完了 ({len(body)} 文字)")

    filename = meta["filename"]
    article_path = ARTICLES / f"{filename}.html"
    html = build_article_html(meta, body, today)
    article_path.write_text(html, encoding="utf-8")
    print(f"✅ 記事保存: articles/{filename}.html")

    insert_card(meta, today, filename)
    print("✅ index.html 更新完了")

    print(f"\n🎵 本日の記事: {meta['title']}")


if __name__ == "__main__":
    main()
