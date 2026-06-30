(function () {
    var POSTS_PER_PAGE = 20;
    var allPosts = [];
    var renderedCount = 0;
    var isTranslating = false;

    var postsContainer = document.getElementById('posts-container');
    var loadingEl = document.getElementById('loading');
    var errorEl = document.getElementById('error');
    var refreshBtn = document.getElementById('refresh-btn');
    var translationCache = {};

    var basePath = '';
    if (window.location.pathname.indexOf('/trump-truthsocial/') !== -1) {
        basePath = '/trump-truthsocial';
    }

    var fallbackAvatar = basePath + '/data/media/avatars/default_avatar.svg';

    function loadCache() {
        try {
            var raw = localStorage.getItem('translation_cache');
            if (raw) Object.assign(translationCache, JSON.parse(raw));
        } catch (e) {}
    }

    function saveCache() {
        try {
            localStorage.setItem('translation_cache', JSON.stringify(translationCache));
        } catch (e) {}
    }

    function getCacheKey(text) {
        var hash = 0;
        for (var i = 0; i < text.length; i++) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash |= 0;
        }
        return 't_' + hash;
    }

    function stripHtml(html) {
        var div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }

    function formatTime(dateStr) {
        var date = new Date(dateStr);
        var now = new Date();
        var diff = Math.floor((now - date) / 1000);
        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
        if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
        if (diff < 604800) return Math.floor(diff / 86400) + '天前';
        var y = date.getFullYear();
        var m = String(date.getMonth() + 1).padStart(2, '0');
        var d = String(date.getDate()).padStart(2, '0');
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
        var key = getCacheKey(text);
        if (translationCache[key]) return translationCache[key];
        try {
            var url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=' + encodeURIComponent(text);
            var resp = await fetch(url);
            var data = await resp.json();
            var translated = data[0].map(function (s) { return s[0]; }).join('');
            translationCache[key] = translated;
            saveCache();
            return translated;
        } catch (e) {
            return text;
        }
    }

    function getMediaUrl(m) {
        if (m.local_file) return basePath + '/data/' + m.local_file;
        return m.url || m.preview_url || '';
    }

    function buildMediaHtml(media) {
        var html = '';
        if (media && media.length > 0) {
            html = '<div class="post-media">';
            media.forEach(function (m) {
                var src = getMediaUrl(m);
                if (!src) return;
                if (m.type === 'video') {
                    html += '<video controls preload="metadata" onerror="this.style.display=\'none\'"><source src="' + src + '" type="video/mp4"></video>';
                } else {
                    html += '<img src="' + src + '" alt="media" loading="lazy" onerror="this.style.display=\'none\'">';
                }
            });
            html += '</div>';
        }
        return html;
    }

    function buildQuoteHtml(quote, index) {
        if (!quote) return '';
        var qContent = stripHtml(quote.content);
        var qAvatar = quote.account.local_avatar ? basePath + '/data/' + quote.account.local_avatar : (quote.account.avatar || fallbackAvatar);
        var qMedia = buildMediaHtml(quote.media);
        return '<div class="quote-box">' +
            '<div class="quote-header">' +
                '<img class="quote-avatar" src="' + qAvatar + '" alt="" onerror="this.src=\'' + fallbackAvatar + '\'">' +
                '<span class="quote-name">' + (quote.account.display_name || quote.account.username || '') + '</span>' +
                '<span class="quote-time">' + formatTime(quote.created_at) + '</span>' +
            '</div>' +
            '<div class="quote-content translated-quote" data-qindex="' + index + '">' + qContent + '</div>' +
            '<div class="quote-content original-quote" data-qindex="' + index + '" style="display:none;">' + quote.content + '</div>' +
            qMedia +
        '</div>';
    }

    function createPostCard(post, index) {
        var card = document.createElement('div');
        card.className = 'post-card';
        card.setAttribute('data-index', index);

        var contentText = stripHtml(post.content);
        var mediaHtml = buildMediaHtml(post.media);
        var quoteHtml = buildQuoteHtml(post.quote, index);
        var avatarUrl = post.account.local_avatar ? basePath + '/data/' + post.account.local_avatar : fallbackAvatar;

        card.innerHTML =
            '<div class="post-header">' +
                '<img class="post-avatar" src="' + avatarUrl + '" alt="avatar" onerror="this.src=\'' + fallbackAvatar + '\'">' +
                '<div class="post-body">' +
                    '<div class="post-user-info">' +
                        '<span class="post-display-name">' + (post.account.display_name || 'Donald J. Trump') + '</span>' +
                        '<span class="post-username">@' + post.account.username + '</span>' +
                        '<span class="post-time">' + formatTime(post.created_at) + '</span>' +
                    '</div>' +
                    '<div class="post-content translated-content" data-index="' + index + '">' + contentText + '</div>' +
                    '<div class="post-content original-content" data-index="' + index + '" style="display:none;">' + post.content + '</div>' +
                    mediaHtml + quoteHtml +
                    '<div class="post-actions">' +
                        '<button class="post-action"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg><span>' + formatCount(post.reblogs_count) + '</span></button>' +
                        '<button class="post-action"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M16.69 15.49A6.993 6.993 0 0112 17c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7c0 1.57-.52 3.02-1.4 4.18l.4.32H19l-2.31-2.31z"/></svg><span>' + formatCount(post.favourites_count) + '</span></button>' +
                        '<button class="post-action"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.04 2 11c0 2.72 1.47 5.14 3.78 6.71-.13.47-.49 1.75-.56 2.03-.09.35.13.35.27.25.11-.08 1.72-1.17 2.44-1.67.78.21 1.61.33 2.46.38A7.46 7.46 0 0012 18c5.52 0 10-4.04 10-9S17.52 2 12 2z"/></svg><span>' + formatCount(post.replies_count) + '</span></button>' +
                    '</div>' +
                    '<button class="translate-btn" data-index="' + index + '">显示原文</button>' +
                '</div>' +
            '</div>';
        return card;
    }

    function renderNextPage() {
        var end = Math.min(renderedCount + POSTS_PER_PAGE, allPosts.length);
        var fragment = document.createDocumentFragment();
        for (var i = renderedCount; i < end; i++) {
            fragment.appendChild(createPostCard(allPosts[i], i));
        }
        postsContainer.appendChild(fragment);
        renderedCount = end;
        updateLoadMoreBtn();
        translateBatch(renderedCount - POSTS_PER_PAGE, end);
    }

    function updateLoadMoreBtn() {
        var btn = document.getElementById('load-more-btn');
        if (!btn) return;
        if (renderedCount >= allPosts.length) {
            btn.style.display = 'none';
        } else {
            btn.style.display = 'block';
            btn.textContent = '加载更多 (' + renderedCount + '/' + allPosts.length + ')';
        }
    }

    async function translateBatch(start, end) {
        if (isTranslating) return;
        isTranslating = true;
        for (var i = start; i < end && i < allPosts.length; i++) {
            var el = document.querySelector('.translated-content[data-index="' + i + '"]');
            if (el) {
                var text = stripHtml(allPosts[i].content);
                var translated = await translateText(text);
                el.textContent = translated;
            }
            if (allPosts[i].quote) {
                var qEl = document.querySelector('.translated-quote[data-qindex="' + i + '"]');
                if (qEl) {
                    var qText = stripHtml(allPosts[i].quote.content);
                    var qTranslated = await translateText(qText);
                    qEl.textContent = qTranslated;
                }
            }
        }
        isTranslating = false;
    }

    function setupEventListeners() {
        postsContainer.addEventListener('click', function (e) {
            var btn = e.target.closest('.translate-btn');
            if (!btn) return;
            var index = btn.getAttribute('data-index');
            var tEl = document.querySelector('.translated-content[data-index="' + index + '"]');
            var oEl = document.querySelector('.original-content[data-index="' + index + '"]');
            var tQ = document.querySelector('.translated-quote[data-qindex="' + index + '"]');
            var oQ = document.querySelector('.original-quote[data-qindex="' + index + '"]');
            if (!tEl || !oEl) return;
            var showingOriginal = oEl.style.display !== 'none';
            tEl.style.display = showingOriginal ? '' : 'none';
            oEl.style.display = showingOriginal ? 'none' : '';
            if (tQ) tQ.style.display = showingOriginal ? '' : 'none';
            if (oQ) oQ.style.display = showingOriginal ? 'none' : '';
            btn.textContent = showingOriginal ? '显示原文' : '显示翻译';
        });

        refreshBtn.addEventListener('click', function () {
            loadPosts();
        });

        var loadMoreBtn = document.getElementById('load-more-btn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', function () {
                renderNextPage();
            });
        }
    }

    async function loadPosts() {
        loadingEl.style.display = 'flex';
        errorEl.style.display = 'none';
        postsContainer.innerHTML = '';
        renderedCount = 0;

        try {
            var resp = await fetch(basePath + '/data/posts.json');
            if (!resp.ok) throw new Error('加载数据失败');
            allPosts = await resp.json();
            loadingEl.style.display = 'none';

            if (allPosts.length === 0) {
                postsContainer.innerHTML = '<div class="empty-state">暂无帖子数据<br>请等待定时抓取任务运行</div>';
                return;
            }

            var statsEl = document.getElementById('stats');
            if (statsEl) {
                statsEl.textContent = '共 ' + allPosts.length + ' 条帖子 | ' + allPosts[allPosts.length - 1].created_at.slice(0, 10) + ' ~ ' + allPosts[0].created_at.slice(0, 10);
                statsEl.style.display = 'block';
            }

            renderNextPage();
        } catch (err) {
            loadingEl.style.display = 'none';
            errorEl.textContent = '加载失败: ' + err.message;
            errorEl.style.display = 'block';
        }
    }

    loadCache();
    setupEventListeners();
    loadPosts();
})();
