(function () {
    const postsContainer = document.getElementById('posts-container');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const refreshBtn = document.getElementById('refresh-btn');
    const translationCache = {};

    function loadCache() {
        try {
            const raw = localStorage.getItem('translation_cache');
            if (raw) Object.assign(translationCache, JSON.parse(raw));
        } catch (e) {}
    }

    function saveCache() {
        try {
            localStorage.setItem('translation_cache', JSON.stringify(translationCache));
        } catch (e) {}
    }

    function getCacheKey(text) {
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash |= 0;
        }
        return 't_' + hash;
    }

    function stripHtml(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }

    function formatTime(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);

        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
        if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
        if (diff < 604800) return Math.floor(diff / 86400) + '天前';

        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return y + '年' + m + '月' + d + '日';
    }

    function formatCount(n) {
        if (n === 0) return '';
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return String(n);
    }

    async function translateText(text) {
        if (!text.trim()) return text;
        const key = getCacheKey(text);
        if (translationCache[key]) return translationCache[key];

        try {
            const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=' + encodeURIComponent(text);
            const resp = await fetch(url);
            const data = await resp.json();
            const translated = data[0].map(function (s) { return s[0]; }).join('');
            translationCache[key] = translated;
            saveCache();
            return translated;
        } catch (e) {
            return text;
        }
    }

    function createPostCard(post, index) {
        var card = document.createElement('div');
        card.className = 'post-card';
        card.setAttribute('data-index', index);

        var contentText = stripHtml(post.content);

        var mediaHtml = '';
        if (post.media && post.media.length > 0) {
            mediaHtml = '<div class="post-media">';
            post.media.forEach(function (m) {
                if (m.type === 'video') {
                    mediaHtml += '<video controls preload="metadata"><source src="' + m.url + '" type="video/mp4"></video>';
                } else {
                    var imgUrl = m.preview_url || m.url;
                    mediaHtml += '<img src="' + imgUrl + '" alt="' + (m.description || 'media') + '" loading="lazy">';
                }
            });
            mediaHtml += '</div>';
        }

        var avatarUrl = post.account.avatar || 'https://media.truthsocial.com/accounts/avatars/000/000/001/original/avatar.png';

        card.innerHTML =
            '<div class="post-header">' +
                '<img class="post-avatar" src="' + avatarUrl + '" alt="avatar">' +
                '<div class="post-body">' +
                    '<div class="post-user-info">' +
                        '<span class="post-display-name">' + (post.account.display_name || 'Donald J. Trump') + '</span>' +
                        '<span class="post-username">@' + post.account.username + '</span>' +
                        '<span class="post-time">' + formatTime(post.created_at) + '</span>' +
                    '</div>' +
                    '<div class="post-content translated-content" data-index="' + index + '">' + contentText + '</div>' +
                    '<div class="post-content original-content" data-index="' + index + '" style="display:none;">' + post.content + '</div>' +
                    mediaHtml +
                    '<div class="post-actions">' +
                        '<button class="post-action">' +
                            '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>' +
                            '<span>' + formatCount(post.reblogs_count) + '</span>' +
                        '</button>' +
                        '<button class="post-action">' +
                            '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M16.69 15.49A6.993 6.993 0 0112 17c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7c0 1.57-.52 3.02-1.4 4.18l.4.32H19l-2.31-2.31z"/></svg>' +
                            '<span>' + formatCount(post.favourites_count) + '</span>' +
                        '</button>' +
                        '<button class="post-action">' +
                            '<svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.04 2 11c0 2.72 1.47 5.14 3.78 6.71-.13.47-.49 1.75-.56 2.03-.09.35.13.35.27.25.11-.08 1.72-1.17 2.44-1.67.78.21 1.61.33 2.46.38A7.46 7.46 0 0012 18c5.52 0 10-4.04 10-9S17.52 2 12 2z"/></svg>' +
                            '<span>' + formatCount(post.replies_count) + '</span>' +
                        '</button>' +
                    '</div>' +
                    '<button class="translate-btn" data-index="' + index + '">显示原文</button>' +
                '</div>' +
            '</div>';

        return card;
    }

    function renderPosts(posts) {
        postsContainer.innerHTML = '';
        if (!posts || posts.length === 0) {
            postsContainer.innerHTML = '<div class="empty-state">暂无帖子数据<br>请等待定时抓取任务运行</div>';
            return;
        }
        posts.forEach(function (post, i) {
            postsContainer.appendChild(createPostCard(post, i));
        });
    }

    async function translateAllVisible(posts) {
        for (var i = 0; i < posts.length; i++) {
            var el = document.querySelector('.translated-content[data-index="' + i + '"]');
            if (el) {
                var text = stripHtml(posts[i].content);
                var translated = await translateText(text);
                el.textContent = translated;
            }
        }
    }

    function setupTranslateButtons() {
        postsContainer.addEventListener('click', function (e) {
            var btn = e.target.closest('.translate-btn');
            if (!btn) return;

            var index = btn.getAttribute('data-index');
            var translatedEl = document.querySelector('.translated-content[data-index="' + index + '"]');
            var originalEl = document.querySelector('.original-content[data-index="' + index + '"]');

            if (!translatedEl || !originalEl) return;

            var isShowingOriginal = originalEl.style.display !== 'none';

            if (isShowingOriginal) {
                originalEl.style.display = 'none';
                translatedEl.style.display = '';
                btn.textContent = '显示原文';
            } else {
                translatedEl.style.display = 'none';
                originalEl.style.display = '';
                btn.textContent = '显示翻译';
            }
        });
    }

    async function loadPosts() {
        loadingEl.style.display = 'flex';
        errorEl.style.display = 'none';
        postsContainer.innerHTML = '';

        try {
            var basePath = '';
            if (window.location.pathname.indexOf('/trump-truthsocial/') !== -1) {
                basePath = '/trump-truthsocial';
            }
            var resp = await fetch(basePath + '/data/posts.json');
            if (!resp.ok) throw new Error('加载数据失败');
            var posts = await resp.json();

            loadingEl.style.display = 'none';
            renderPosts(posts);
            await translateAllVisible(posts);
        } catch (err) {
            loadingEl.style.display = 'none';
            errorEl.textContent = '加载失败: ' + err.message;
            errorEl.style.display = 'block';
        }
    }

    refreshBtn.addEventListener('click', function () {
        loadPosts();
    });

    loadCache();
    setupTranslateButtons();
    loadPosts();
})();
