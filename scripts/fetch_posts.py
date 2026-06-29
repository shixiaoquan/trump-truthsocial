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
IMAGES_DIR = os.path.join(DATA_DIR, 'media', 'images')
VIDEOS_DIR = os.path.join(DATA_DIR, 'media', 'videos')
USERNAME = 'realDonaldTrump'
MAX_SCROLLS = 500
SCROLL_PAUSE = 2.0
NO_NEW_THRESHOLD = 15


def ensure_dirs():
    for d in [IMAGES_DIR, VIDEOS_DIR]:
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
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(save_path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception:
        return False


def url_to_filename(url, prefix=''):
    ext = os.path.splitext(url.split('?')[0])[1] or '.dat'
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f'{prefix}{h}{ext}'


def download_media(media_list):
    saved = []
    for att in media_list:
        url = att.get('url') or att.get('preview_url', '')
        if not url:
            continue
        is_video = att.get('type') == 'video'
        save_dir = VIDEOS_DIR if is_video else IMAGES_DIR
        prefix = 'vid_' if is_video else 'img_'
        filename = url_to_filename(url, prefix)
        save_path = os.path.join(save_dir, filename)
        if download_file(url, save_path):
            saved.append({
                'type': att.get('type', 'image'),
                'url': url,
                'local_file': f'media/{"videos" if is_video else "images"}/{filename}',
            })
    return saved


def simplify_post(post):
    account = post.get('account', {})
    media = download_media(post.get('media_attachments', []))

    quote = None
    quote_data = post.get('quote')
    if quote_data and isinstance(quote_data, dict):
        q_account = quote_data.get('account', {})
        q_media = download_media(quote_data.get('media_attachments', []))
        quote = {
            'id': quote_data.get('id', ''),
            'content': quote_data.get('content', ''),
            'created_at': quote_data.get('created_at', ''),
            'media': q_media,
            'account': {
                'username': q_account.get('username', ''),
                'display_name': q_account.get('display_name', ''),
                'avatar': q_account.get('avatar', ''),
            },
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
        'account': {
            'username': account.get('username', USERNAME),
            'display_name': account.get('display_name', 'Donald J. Trump'),
            'avatar': account.get('avatar', ''),
        },
    }


def merge_posts(existing, new_posts):
    seen_ids = {p['id'] for p in existing}
    merged = list(existing)
    for post in new_posts:
        if post['id'] not in seen_ids:
            merged.append(post)
            seen_ids.add(post['id'])
    merged.sort(key=lambda p: p['created_at'], reverse=True)
    return merged


def try_scrape():
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

    try:
        with sync_playwright() as p:
            stealth.use_sync(p)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            page.on('response', on_response)

            print('Loading Truth Social...')
            page.goto(f'https://truthsocial.com/@{USERNAME}', timeout=120000, wait_until='domcontentloaded')

            for i in range(30):
                time.sleep(2)
                title = page.title()
                if 'Just a moment' not in title and title:
                    print(f'Cloudflare passed at {i * 2}s')
                    break
            else:
                print('Cloudflare challenge not passed after 60s')
                browser.close()
                return []

            time.sleep(3)
            print(f'Page loaded: {page.title()[:50]}')

            no_new = 0
            for i in range(MAX_SCROLLS):
                prev_count = len(all_posts)
                try:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                except Exception:
                    print(f'Page error at scroll {i + 1}, stopping')
                    break
                time.sleep(SCROLL_PAUSE)

                if (i + 1) % 10 == 0:
                    print(f'Scroll {i + 1} | Posts: {len(all_posts)}')

                if len(all_posts) == prev_count:
                    no_new += 1
                else:
                    no_new = 0

                if no_new >= NO_NEW_THRESHOLD:
                    print(f'No new posts for {NO_NEW_THRESHOLD} scrolls. Done.')
                    break

            browser.close()

    except Exception as e:
        print(f'Scrape error: {e}')

    return all_posts


def main():
    ensure_dirs()
    print('=' * 50)
    print('Trump Truth Social Scraper')
    print('=' * 50)

    existing = load_posts()
    existing_ids = {p['id'] for p in existing}
    print(f'Existing posts: {len(existing)}')

    raw_posts = try_scrape()
    if not raw_posts:
        print('No posts fetched (Cloudflare may be blocking)')
        return

    new_raw = [p for p in raw_posts if p['id'] not in existing_ids]
    print(f'New posts: {len(new_raw)}')

    if new_raw:
        new_posts = [simplify_post(p) for p in new_raw]
        merged = merge_posts(existing, new_posts)
        save_posts(merged)
        print(f'Total saved: {len(merged)}')
    else:
        print('No new posts to add')

    all_data = load_posts()
    if all_data:
        print(f'Range: {all_data[-1]["created_at"][:10]} ~ {all_data[0]["created_at"][:10]}')


if __name__ == '__main__':
    main()
