import json
import os
import sys
import time

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'posts.json')
USERNAME = 'realDonaldTrump'
MAX_POSTS = 200


def load_existing_posts():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_posts(posts):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def simplify_post(post):
    media = []
    for att in post.get('media_attachments', []):
        media.append({
            'type': att.get('type', 'image'),
            'url': att.get('url', ''),
            'preview_url': att.get('preview_url', ''),
            'description': att.get('description', ''),
        })

    account = post.get('account', {})

    return {
        'id': post['id'],
        'content': post.get('content', ''),
        'created_at': post.get('created_at', ''),
        'media': media,
        'reblogs_count': post.get('reblogs_count', 0),
        'favourites_count': post.get('favourites_count', 0),
        'replies_count': post.get('replies_count', 0),
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
    return merged[:MAX_POSTS]


def fetch_with_playwright():
    stealth = Stealth()
    captured = {'statuses': None}

    def on_response(response):
        url = response.url
        if '/api/v1/accounts/' in url and '/statuses' in url and 'pinned=' not in url and captured['statuses'] is None:
            try:
                captured['statuses'] = response.json()
                print(f'Captured statuses from: {url[:80]}...')
            except Exception:
                pass

    with sync_playwright() as p:
        stealth.use_sync(p)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        page.on('response', on_response)

        print(f'Loading Truth Social profile for {USERNAME}...')
        page.goto(f'https://truthsocial.com/@{USERNAME}', timeout=90000)

        for _ in range(15):
            time.sleep(1)
            if captured['statuses'] is not None:
                break

        browser.close()

    return captured


def main():
    try:
        captured = fetch_with_playwright()

        raw_posts = captured.get('statuses')
        if not raw_posts:
            print('No statuses captured', file=sys.stderr)
            sys.exit(1)

        print(f'Captured {len(raw_posts)} posts')
        new_posts = [simplify_post(p) for p in raw_posts]

        existing = load_existing_posts()
        merged = merge_posts(existing, new_posts)

        save_posts(merged)
        print(f'Saved {len(merged)} posts to {DATA_FILE}')

    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
