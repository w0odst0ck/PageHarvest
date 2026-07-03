// ==UserScript==
// @name         京东 HTML下载器 (SPA + 分类页)
// @namespace    http://tampermonkey.net/
// @version      3.1
// @description  京东搜索页 (re.jd.com/search SPA) + 分类页 (list.jd.com/list.html 传统页)
// @match        https://re.jd.com/search*
// @match        https://search.jd.com/Search*
// @match        https://list.jd.com/list.html*
// @grant        GM_notification
// @grant        GM_getValue
// @grant        GM_setValue
// ==/UserScript==

(function() {
    'use strict';

    const currentUrl = location.href;
    console.log('[JD-DL] 加载', currentUrl);

    // ====================================================================
    // 路由：判断是搜索 SPA 模式还是分类页传统模式
    // ====================================================================
    if (currentUrl.includes('re.jd.com/search') || currentUrl.includes('search.jd.com/Search')) {
        runSPAMode();
    } else if (currentUrl.includes('list.jd.com/list.html')) {
        runCategoryMode();
    }

    // ====================================================================
    // SPA 模式（原有逻辑）
    // ====================================================================
    function runSPAMode() {
        console.log('[JD-DL] ⚡ SPA 模式');

        const MAX_PAGES = 10;
        const SCROLL_INTERVAL = 1200;
        const SCROLL_STUCK_LIMIT = 5;
        const SAVE_COOLDOWN = 12000;

        const url = new URL(location.href);
        const keyword = url.searchParams.get('keyword') || 'unknown';
        const kwName = keyword.replace(/[%\/\\?&]/g, '_');
        const stateKey = 'jd_spa_' + keyword;

        const currentPage = parseInt(url.searchParams.get('page') || '1');
        if (currentPage !== 1) {
            console.log('[JD-DL] 非首页，跳过');
            return;
        }

        const state = parseInt(GM_getValue(stateKey, '0'));
        if (state > MAX_PAGES) {
            console.log('[JD-DL] 已完成');
            return;
        }
        const ok = confirm('【京东 SPA下载器】\n关键词: ' + decodeURIComponent(keyword) +
            '\n共 ' + MAX_PAGES + ' 页\n单页内连续翻页+保存\n\n确认？');
        if (!ok) return;

        GM_setValue(stateKey, '1');
        console.log('[JD-DL] ✅ 开始');

        let savedPages = new Set();
        let isCollecting = false;

        const observer = new MutationObserver(() => {
            if (!isCollecting) checkAndSave();
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: false,
        });

        setTimeout(() => collect(), 2000);

        async function collect() {
            for (let page = 1; page <= MAX_PAGES; page++) {
                isCollecting = true;

                await waitForProducts();
                await humanScroll();
                await saveHTML(page, kwName);
                savedPages.add(page);
                console.log('[JD-DL] ✅ 第' + page + '页 (' + savedPages.size + '/' + MAX_PAGES + ')');

                if (page >= MAX_PAGES) break;

                GM_setValue(stateKey, '' + (page + 1));

                const clicked = findAndClickNext();
                if (clicked) {
                    console.log('[JD-DL] 👆 翻页到第' + (page + 1) + '页');
                    isCollecting = false;
                    await waitForPageChange(page);
                } else {
                    console.log('[JD-DL] ⚠️ 无翻页按钮，结束');
                    break;
                }
            }
            console.log('[JD-DL] ★ 完成，共 ' + savedPages.size + ' 页');
            GM_setValue(stateKey, MAX_PAGES + 999);
        }

        function waitForProducts() {
            return new Promise(resolve => {
                const timer = setInterval(() => {
                    if (document.querySelectorAll('[data-sku]').length >= 2 ||
                        document.querySelectorAll('[class*="goods"]').length >= 2 ||
                        document.querySelectorAll('[class*="item"]').length >= 3) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 300);
                setTimeout(() => { clearInterval(timer); resolve(); }, 8000);
            });
        }

        function waitForPageChange(prevPage) {
            return new Promise(resolve => {
                let waited = 0;
                const timer = setInterval(() => {
                    const cards = Math.max(
                        document.querySelectorAll('[data-sku]').length,
                        document.querySelectorAll('[class*="goods"]').length,
                        document.querySelectorAll('[class*="item"]').length,
                        document.querySelectorAll('[class*="card"]').length
                    );
                    if (cards >= 3) {
                        clearInterval(timer);
                        resolve();
                    }
                    waited += 500;
                    if (waited > SAVE_COOLDOWN) {
                        console.log('[JD-DL] ⏰ 翻页等待超时');
                        clearInterval(timer);
                        resolve();
                    }
                }, 500);
            });
        }

        function humanScroll() {
            return new Promise(async resolve => {
                let lastHeight = 0;
                let stuckCount = 0;
                while (stuckCount < SCROLL_STUCK_LIMIT) {
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise(r => setTimeout(r, SCROLL_INTERVAL));
                    const newHeight = document.body.scrollHeight;
                    if (newHeight === lastHeight) {
                        stuckCount++;
                    } else {
                        stuckCount = 0;
                        lastHeight = newHeight;
                    }
                }
                window.scrollTo(0, 0);
                await new Promise(r => setTimeout(r, 500));
                resolve();
            });
        }

        function saveHTML(page, name) {
            return new Promise(resolve => {
                const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
                const filename = name + '_jd_page' + page + '.html';
                const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
                const urlObj = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = urlObj;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                setTimeout(() => { URL.revokeObjectURL(urlObj); resolve(); }, 1000);
            });
        }

        function checkAndSave() {
            // MutationObserver 后备
        }
    }

    // ====================================================================
    // 分类页模式（list.jd.com/list.html — 支持传统多页 + SPA 变体）
    // ====================================================================
    function runCategoryMode() {
        console.log('[JD-DL] ⚡ 分类页模式');

        const url = new URL(location.href);

        // cat 参数（用于文件名和状态追踪）
        const catRaw = url.searchParams.get('cat') || 'unknown';
        const catName = 'cat_' + catRaw.replace(/[%,\/\\?&]/g, '_').replace(/_+/g, '_');

        // 当前页码
        const currentPage = parseInt(url.searchParams.get('page') || '1');
        const stateKey = 'jd_list_' + catName;

        // 检测页面类型
        const isSPA = !document.querySelector('li.gl-item');

        if (isSPA) {
            console.log('[JD-DL] 🔍 检测为 SPA 类型分类页');
            runCategorySPAMode(catName, stateKey, currentPage);
        } else {
            console.log('[JD-DL] 🔍 检测为传统 SSR 分类页');
            runCategoryTradMode(catName, stateKey, currentPage);
        }
    }

    // ── 传统 SSR 分类页（URL 翻页） ──
    function runCategoryTradMode(catName, stateKey, currentPage) {
        console.log('[JD-DL] ⚡ 分类页（传统 SSR）');

        const MAX_PAGES = 10;
        const catDisplay = decodeURIComponent(catName.replace(/^cat_/, '').replace(/_/g, ','));

        let expectedPage = parseInt(GM_getValue(stateKey, '0'));
        console.log('[JD-DL] 当前第 ' + currentPage + ' 页，期望第 ' + expectedPage + ' 页');

        if (expectedPage === 0) {
            const ok = confirm(
                '【京东 分类页下载器】\n' +
                'cat: ' + catDisplay + '\n' +
                '模式: 传统 SSR（URL翻页）\n' +
                '共 ' + MAX_PAGES + ' 页\n' +
                '当前第 ' + currentPage + ' 页\n' +
                '将从当前页开始，自动翻页保存\n\n' +
                '⚠️ 点击确定后，你有 10秒 时间设置筛选条件\n' +
                '（品牌、价格区间、发货地等）\n' +
                '确认？'
            );
            if (!ok) return;
            expectedPage = currentPage;
            GM_setValue(stateKey, '' + expectedPage);
        }

        if (currentPage !== expectedPage) {
            console.log('[JD-DL] 页数不匹配，跳过');
            return;
        }

        if (expectedPage > MAX_PAGES) {
            console.log('[JD-DL] ★ 已完成');
            return;
        }

        (async function() {
            const page = currentPage;
            console.log('[JD-DL] --- 第 ' + page + '/' + MAX_PAGES + ' 页 ---');

            if (page === currentPage && expectedPage === currentPage) {
                console.log('[JD-DL] ⏳ 等待 10 秒，请设置筛选条件...');
                GM_notification({ text: '你有 10 秒设置筛选条件', timeout: 3000 });
                for (let i = 10; i > 0; i--) {
                    console.log('[JD-DL] ⏳ ' + i + 's...');
                    await sleep(1000);
                }
                console.log('[JD-DL] 🚀 开始采集');
            }

            await waitCategoryProducts('li.gl-item[data-sku]');
            await categoryScroll(5);
            await saveCategoryHTML(page, catName);
            console.log('[JD-DL] ✅ 第' + page + '页已保存');

            if (page >= MAX_PAGES) {
                console.log('[JD-DL] ★ 完成');
                GM_setValue(stateKey, '' + (MAX_PAGES + 999));
                return;
            }

            const nextPage = page + 1;
            GM_setValue(stateKey, '' + nextPage);

            const nextUrl = new URL(location.href);
            nextUrl.searchParams.set('page', '' + nextPage);

            console.log('[JD-DL] ▶ 跳转到第 ' + nextPage + ' 页...');
            await sleep(1500);
            location.href = nextUrl.toString();
        })();
    }

    // ── SPA 分类页（列表页也可能是 SPA，如 fiveCity/event 入口） ──
    async function runCategorySPAMode(catName, stateKey, currentPage) {
        console.log('[JD-DL] ⚡ 分类页（SPA）');

        const MAX_PAGES = 10;
        const SAVE_COOLDOWN = 12000;
        const catDisplay = decodeURIComponent(catName.replace(/^cat_/, '').replace(/_/g, ','));

        if (currentPage !== 1) {
            console.log('[JD-DL] 非首页，SPA模式只从首页开始');
            return;
        }

        const state = parseInt(GM_getValue(stateKey, '0'));
        if (state > MAX_PAGES) {
            console.log('[JD-DL] ★ 已完成');
            return;
        }

        const ok = confirm(
            '【京东 分类页 SPA下载器】\n' +
            'cat: ' + catDisplay + '\n' +
            '模式: SPA（页面内翻页）\n' +
            '共 ' + MAX_PAGES + ' 页\n' +
            '与搜索页 SPA 同样方式，单页内连续翻页+保存\n\n' +
            '⚠️ 点击确定后，你有 10秒 时间设置筛选条件\n' +
            '（品牌、价格区间、发货地等）\n' +
            '确认？'
        );
        if (!ok) return;

        GM_setValue(stateKey, '1');
        console.log('[JD-DL] ✅ 开始 SPA 分类页采集');
        console.log('[JD-DL] ⏳ 等待 10 秒，请设置筛选条件...');

        GM_notification({ text: '你有 10 秒设置筛选条件', timeout: 3000 });

        for (let i = 10; i > 0; i--) {
            console.log('[JD-DL] ⏳ ' + i + 's...');
            await sleep(1000);
        }
        console.log('[JD-DL] 🚀 开始采集');

        let savedPages = new Set();
        let isCollecting = false;
        let prevSkuCount = 0;

        const observer = new MutationObserver(() => {
            if (!isCollecting && !hasNewSkuChanged()) {
                // 新商品可能加载了
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });

        collectSPA();

        async function collectSPA() {
            for (let page = 1; page <= MAX_PAGES; page++) {
                isCollecting = true;

                await waitCategoryProducts('[data-sku]');
                await categoryScroll(5);
                await saveCategoryHTML(page, catName);
                savedPages.add(page);
                console.log('[JD-DL] ✅ 第' + page + '页 (' + savedPages.size + '/' + MAX_PAGES + ')');

                if (page >= MAX_PAGES) break;

                const nextPage = page + 1;
                GM_setValue(stateKey, '' + nextPage);

                // 策略 A：点击翻页按钮（SPA 内翻页）
                prevSkuCount = document.querySelectorAll('[data-sku]').length;
                const clicked = findAndClickNext();
                if (clicked) {
                    console.log('[JD-DL] 👆 点击翻页到第' + nextPage + '页');
                    isCollecting = false;
                    await waitForSPAPageChange();
                    continue;
                }

                // 策略 B：URL 翻页（页面重载）
                console.log('[JD-DL] ⚠️ 无翻页按钮，尝试 URL 翻页...');
                const nextUrl = new URL(location.href);
                nextUrl.searchParams.set('page', '' + nextPage);
                console.log('[JD-DL] ▶ 跳转 URL: ' + nextUrl.toString());
                await sleep(1500);
                location.href = nextUrl.toString();
                return;
            }
            console.log('[JD-DL] ★ SPA完成，共 ' + savedPages.size + ' 页');
            GM_setValue(stateKey, MAX_PAGES + 999);
        }

        function hasNewSkuChanged() {
            const cur = document.querySelectorAll('[data-sku]').length;
            return cur !== prevSkuCount && cur >= 2;
        }

        function waitForSPAPageChange() {
            return new Promise(resolve => {
                let waited = 0;
                const timer = setInterval(() => {
                    const curSku = document.querySelectorAll('[data-sku]').length;
                    if (curSku !== prevSkuCount && curSku >= 2) {
                        clearInterval(timer);
                        resolve();
                    }
                    waited += 500;
                    if (waited > SAVE_COOLDOWN) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 500);
            });
        }
    }

    // ====================================================================
    // 共享辅助函数
    // ====================================================================

    function waitCategoryProducts(selector) {
        return new Promise(resolve => {
            const timer = setInterval(() => {
                const cards = document.querySelectorAll(selector);
                if (cards.length >= 2) {
                    clearInterval(timer);
                    resolve();
                }
            }, 400);
            setTimeout(() => { clearInterval(timer); resolve(); }, 10000);
        });
    }

    function categoryScroll(stuckLimit) {
        const limit = stuckLimit || 5;
        return new Promise(async resolve => {
            let lastHeight = 0;
            let stuck = 0;
            while (stuck < limit) {
                window.scrollTo(0, document.body.scrollHeight);
                await sleep(1200);
                const h = document.body.scrollHeight;
                if (h === lastHeight) stuck++;
                else { stuck = 0; lastHeight = h; }
            }
            window.scrollTo(0, 0);
            await sleep(500);
            resolve();
        });
    }

    function saveCategoryHTML(page, name) {
        return new Promise(resolve => {
            const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
            const filename = name + '_jd_page' + page + '.html';
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const u = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = u;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => { URL.revokeObjectURL(u); resolve(); }, 1000);
        });
    }

    function sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    }

    function findAndClickNext() {
        // ── 策略 A：文本匹配 —— 精确匹配"下一页" ──
        // 只匹配元素文本刚好是"下一页"的元素，避免 textContent 拼接出长文本
        const tags = ['a', 'button', 'span', 'em', 'i', 'b', 'strong'];
        for (const tag of tags) {
            const els = document.querySelectorAll(tag);
            for (const el of els) {
                if (!el.offsetHeight) continue;
                const txt = (el.textContent || '').trim();
                // 精确/前缀匹配，长度限制避免匹配到搜索框等
                if ((txt === '下一页' || txt === '下一页>' || txt.startsWith('下一页>') || txt.indexOf('下一页') === 0) && txt.length < 20) {
                    console.log('[JD-DL] 🔍 文本匹配翻页: <' + tag + '> "' + txt + '"');
                    el.click();
                    return true;
                }
            }
        }

        // ── 策略 B：选择器匹配 ──
        const selectors = [
            'a.fp-next',
            '.f-pager a.fp-next',
            '#J_bottomPage a.fp-next',
            '#J_bottomPage .pn-next:not(.disabled)',
            '#J_bottomPage a.pn-next',
            '.page-wrap .next:not(.disabled)',
            '.J-pagination a:last-child:not(.current)',
            'a.pn-next:not(.disabled):not(.pn-next-disabled)',
            '.pn-next:not(.disabled):not(.pn-next-disabled)',
            'a[class*="next"]:not(.disabled)',
            '[class*="pagination"] button:last-child:not([disabled])',
            '.numberbtn.active + .numberbtn',
        ];
        for (const sel of selectors) {
            try {
                const el = document.querySelector(sel);
                if (el && el.offsetHeight > 0) {
                    console.log('[JD-DL] 🔍 选择器匹配: ' + sel);
                    el.click();
                    return true;
                }
            } catch(e) {}
        }

        // ── 策略 C：找可见页码数字 ──
        const pageZones = document.querySelectorAll('[class*="page"], [class*="pager"], [id*="page"]');
        for (const zone of pageZones) {
            const links = zone.querySelectorAll('a, span, em');
            for (const link of links) {
                const num = parseInt(link.textContent.trim());
                if (!isNaN(num) && link.offsetHeight > 0) {
                    // 点最小的非当前页页码（通常就是第2页）
                    const cur = parseInt(document.querySelector('.current')?.textContent || '0');
                    if (num > 1 && (!cur || num === cur + 1 || num > cur)) {
                        console.log('[JD-DL] 🔍 页码匹配: 第' + num + '页');
                        link.click();
                        return true;
                    }
                }
            }
        }

        // ── 都没找到，打印页面底部分页区域帮调试 ──
        console.log('[JD-DL] 🔍 所有策略未命中，打印页面底部元素...');
        const allBottom = document.querySelectorAll('body > :last-child, body > :nth-last-child(2), body > :nth-last-child(3)');
        for (const el of allBottom) {
            const tag = el.tagName + (el.className ? '.' + el.className.slice(0, 40) : '');
            console.log('[JD-DL]   <' + tag + '> 文本: "' + (el.textContent || '').trim().slice(0, 100) + '"');
        }
        // 打印所有包含页码或翻页文字的元素
        document.querySelectorAll('*').forEach(el => {
            if (!el.offsetHeight) return;
            const t = (el.textContent || '').trim();
            if (/[\d]+页/.test(t) && t.length < 30) {
                console.log('[JD-DL]   📄 分页元素: <' + el.tagName + (el.className ? '.' + el.className.slice(0, 30) : '') + '> 文本: "' + t + '"');
            }
        });

        return false;
    }

})();
