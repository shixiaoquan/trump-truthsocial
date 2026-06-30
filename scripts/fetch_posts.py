import hashlib
import json
import os
import sys
import time

from curl_cffi import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DATA_FILE = os.path.join(DATA_DIR, 'posts.json')
AVATARS_DIR = os.path.join(DATA_DIR, 'media', 'avatars')
IMAGES_DIR = os.path.join(DATA_DIR, 'media', 'images')
VIDEOS_DIR = os.path.join(DATA_DIR, 'media', 'videos')
API_BASE = 'https://truthsocial.com/api/v1'
USERNAME = 'realDonaldTrump'
PAGE_SIZE = 40


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
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def create_session():
    return requests.Session(impersonate='chrome110')


def download_file(session, url, save_path):
    if os.path.exists(save_path):
        return True
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def process_media(session, attachments):
    result = []
    for att in attachments:
        url = att.get('url', '')
        is_video = att.get('type') == 'video'
        ext = '.mp4' if is_video else '.jpg'
        prefix = 'vid_' if is_video else 'img_'
        filename = f"{prefix}{url_hash(url)}{ext}"
        save_dir = VIDEOS_DIR if is_video else IMAGES_DIR
        save_path = os.path.join(save_dir, filename)

        local_file = None
        if download_file(session, url, save_path):
            local_file = f'media/{"videos" if is_video else "images"}/{filename}'
            print(f'    Downloaded: {filename}')

        result.append({
            'type': att.get('type', 'image'),
            'url': url,
            'preview_url': att.get('preview_url', ''),
            'local_file': local_file,
        })
    return result


def process_account(session, account):
    avatar_url = account.get('avatar', '')
    local_avatar = None
    if avatar_url:
        ext = os.path.splitext(avatar_url.split('?')[0])[1] or '.jpg'
        filename = f"avatar_{url_hash(avatar_url)}{ext}"
        save_path = os.path.join(AVATARS_DIR, filename)
        if download_file(session, avatar_url, save_path):
            local_avatar = f'media/avatars/{filename}'
    return {
        'username': account.get('username', USERNAME),
        'display_name': account.get('display_name', ''),
        'avatar': avatar_url,
        'local_avatar': local_avatar,
    }


def simplify_post(session, post):
    media = process_media(session, post.get('media_attachments', []))
    account = process_account(session, post.get('account', {}))

    quote = None
    qd = post.get('quote')
    if qd and isinstance(qd, dict):
        quote = {
            'id': qd.get('id', ''),
            'content': qd.get('content', ''),
            'created_at': qd.get('created_at', ''),
            'media': process_media(session, qd.get('media_attachments', [])),
            'account': process_account(session, qd.get('account', {})),
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


def main():
    ensure_dirs()
    print('=' * 50)
    print('Trump Truth Social - Full Scraper')
    print('=' * 50)

    existing = load_posts()
    existing_ids = {p['id'] for p in existing}
    print(f'Existing posts: {len(existing)}')

    session = create_session()

    # Step 1: Get account ID
    print(f'\nLooking up account: {USERNAME}')
    resp = session.get(f'{API_BASE}/accounts/lookup?acct={USERNAME}', timeout=15)
    if resp.status_code != 200:
        print(f'Failed to get account: {resp.status_code}')
        return
    account_id = resp.json()['id']
    print(f'Account ID: {account_id}')

    # Step 2: Fetch all posts with pagination
    all_raw = []
    max_id = None
    page = 0
    consecutive_errors = 0

    while True:
        page += 1
        url = f'{API_BASE}/accounts/{account_id}/statuses?limit=40&with_muted=true'
        if max_id:
            url += f'&max_id={max_id}'

        print(f'\nFetching page {page}...')
        resp = session.get(url, timeout=15)

        if resp.status_code == 429:
            consecutive_errors += 1
            wait = min(30, 5 * consecutive_errors)
            print(f'  Rate limited, waiting {wait}s...')
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f'  API error: {resp.status_code}')
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print('  Too many errors, stopping')
                break
            time.sleep(3)
            continue

        consecutive_errors = 0
        posts = resp.json()
        if not posts or len(posts) == 0:
            print('  No more posts')
            break

        all_raw.extend(posts)
        max_id = posts[-1]['id']
        print(f'  Got {len(posts)} posts (total raw: {len(all_raw)})')
        print(f'  Date range: {posts[-1]["created_at"][:10]} ~ {posts[0]["created_at"][:10]}')

        if len(posts) < 20:
            print('  Last page reached')
            break

        time.sleep(2)

    print(f'\nTotal raw posts fetched: {len(all_raw)}')

    # Step 3: Filter new posts
    new_raw = [p for p in all_raw if p['id'] not in existing_ids]
    print(f'New posts to process: {len(new_raw)}')

    # Step 4: Process and download media
    if new_raw:
        print('\nProcessing posts and downloading media...')
        new_posts = [simplify_post(session, p) for p in new_raw]
        merged = merge_posts(existing, new_posts)
        save_posts(merged)
        print(f'\nTotal posts saved: {len(merged)}')
    else:
        print('No new posts')

    data = load_posts()
    if data:
        print(f'Date range: {data[-1]["created_at"][:10]} ~ {data[0]["created_at"][:10]}')


if __name__ == '__main__':
    main()
