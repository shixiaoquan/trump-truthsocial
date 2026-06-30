import hashlib
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DATA_FILE = os.path.join(DATA_DIR, 'posts.json')
AVATARS_DIR = os.path.join(DATA_DIR, 'media', 'avatars')
IMAGES_DIR = os.path.join(DATA_DIR, 'media', 'images')
VIDEOS_DIR = os.path.join(DATA_DIR, 'media', 'videos')
USERNAME = 'realDonaldTrump'
MAX_SCROLLS = 800
SCROLL_PAUSE = 2.5
NO_NEW_THRESHOLD = 20


def ensure_dirs():
    for d in [AVATARS_DIR, IMAGES_DIR, VIDEOS_DIR]:
        os.makedirs(d, exist_ok=True)


def load_posts():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_posts(posts):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def download_file(url, save_path):
    if os.path.exists(save_path):
        return True
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(save_path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception:
        return False


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def download_avatar(url):
    if not url:
        return None
    ext = os.path.splitext(url.split('?')[0])[1] or '.jpeg'
    filename = f'avatar_{url_hash(url)}{ext}'
    save_path = os.path.join(AVATARS_DIR, filename)
    if download_file(url, save_path):
        return f'media/avatars/{filename}'
    return None


def download_media_file(url, is_video=False):
    if not url:
        return None
    ext = os.path.splitext(url.split('?')[0])[1] or ('.mp4' if is_video else '.jpg')
    prefix = 'vid_' if is_video else 'img_'
    filename = f'{prefix}{url_hash(url)}{ext}'
    save_dir = VIDEOS_DIR if is_video else IMAGES_DIR
    save_path = os.path.join(save_dir, filename)
    if download_file(url, save_path):
        return f'media/{"videos" if is_video else "images"}/{filename}'
    return None


def process_account(account):
    avatar_url = account.get('avatar', '')
    local_avatar = download_avatar(avatar_url)
    return {
        'username': account.get('username', USERNAME),
        'display_name': account.get('display_name', ''),
        'avatar': avatar_url,
        'local_avatar': local_avatar,
    }


def process_media(attachments):
    result = []
    for att in attachments:
        url = att.get('url', '')
        preview = att.get('preview_url', '')
        is_video = att.get('type') == 'video'
        local = download_media_file(url, is_video) or download_media_file(preview, False)
        result.append({
            'type': att.get('type', 'image'),
            'url': url,
            'preview_url': preview,
            'local_file': local,
            'description': att.get('description', ''),
        })
    return result


def simplify_post(post):
    media = process_media(post.get('media_attachments', []))
    account = process_account(post.get('account', {}))

    quote = None
    qd = post.get('quote')
    if qd and isinstance(qd, dict):
        quote = {
            'id': qd.get('id', ''),
            'content': qd.get('content', ''),
            'created_at': qd.get('created_at', ''),
            'media': process_media(qd.get('media_attachments', [])),
            'account': process_account(qd.get('account', {})),
        }

    return {
        'id': post['id'],
        'content': post.get('content', ''),
        'created_at': post.get('created_at', ''),
        'media': media,
        'reblogs_count': post.get('reblogs_count', 0),
        'favourites_count': post.get('favourites_count', 0),
        'replies_count': post.get('replies_count', 0),
        'quote': quote,
        'account': account,
    }


def merge_posts(existing, new_posts):
    seen = {p['id'] for p in existing}
    merged = list(existing)
    for p in new_posts:
        if p['id'] not in seen:
            merged.append(p)
            seen.add(p['id'])
    merged.sort(key=lambda p: p['created_at'], reverse=True)
    return merged


def wait_for_cloudflare(page, timeout=90):
    for i in range(timeout // 2):
        time.sleep(2)
        title = page.title()
        if 'Just a moment' not in title and title:
            return True
    return False


def scrape_posts():
    stealth = Stealth()
    all_posts = []
    seen_ids = set()

    def on_response(response):
        url = response.url
        if '/api/v1/accounts/' in url and '/statuses' in url and 'pinned=' not in url:
            try:
                data = response.json()
                if isinstance(data, list):
                    for post in data:
                        if post['id'] not in seen_ids:
                            seen_ids.add(post['id'])
                            all_posts.append(post)
            except Exception:
                pass

    with sync_playwright() as p:
        stealth.use_sync(p)
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = ctx.new_page()
        page.on('response', on_response)

        page.goto(f'https://truthsocial.com/@{USERNAME}', timeout=120000, wait_until='domcontentloaded')

        if not wait_for_cloudflare(page):
            print('Cloudflare blocked')
            browser.close()
            return []

        time.sleep(3)
        no_new = 0

        for i in range(MAX_SCROLLS):
            prev = len(all_posts)
            try:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            except Exception:
                break
            time.sleep(SCROLL_PAUSE)

            if len(all_posts) > prev:
                no_new = 0
            else:
                no_new += 1

            if (i + 1) % 20 == 0:
                print(f'  Scroll {i+1} | {len(all_posts)} posts')

            if no_new >= NO_NEW_THRESHOLD:
                print(f'  End of timeline reached')
                break

        browser.close()

    return all_posts


def main():
    ensure_dirs()
    print('Trump Truth Social Scraper')

    existing = load_posts()
    existing_ids = {p['id'] for p in existing}
    print(f'Existing: {len(existing)} posts')

    raw = scrape_posts()
    if not raw:
        print('Cloudflare blocked - will retry on next GitHub Actions run')
        return

    new_raw = [p for p in raw if p['id'] not in existing_ids]
    print(f'New: {len(new_raw)} posts')

    if new_raw:
        new_posts = [simplify_post(p) for p in new_raw]
        merged = merge_posts(existing, new_posts)
        save_posts(merged)
        print(f'Saved: {len(merged)} total')
    else:
        print('No new posts')

    data = load_posts()
    if data:
        print(f'Range: {data[-1]["created_at"][:10]} ~ {data[0]["created_at"][:10]}')


if __name__ == '__main__':
    main()
