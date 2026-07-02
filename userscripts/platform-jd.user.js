// ==UserScript==
// @name         京东 HTML下载器 (SPA模式)
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  京东 re.jd.com SPA：单页内监听翻页，连续保存所有页
// @match        https://re.jd.com/search*
// @match        https://search.jd.com/Search*
// @grant        GM_notification
// @grant        GM_getValue
// @grant        GM_setValue
// ==/UserScript==

(function() {
    'use strict';

    console.log('[JD-DL] 加载', location.href);

    const MAX_PAGES = 10;        // 单次最多10页，避免风控。跑完改到11继续
    const SCROLL_INTERVAL = 1200;   // 每次滚动间隔(ms)
    const SCROLL_STUCK_LIMIT = 5;   // 连续多少次高度不变视为到底（多等会儿懒加载）
    const SAVE_COOLDOWN = 12000;    // 翻页后等待新商品出现的最长时间

    const url = new URL(location.href);
    const keyword = url.searchParams.get('keyword') || 'unknown';
    const kwName = keyword.replace(/[%\/\\?&]/g, '_');
    const stateKey = 'jd_spa_' + keyword;

    // ===== 只在第 1 页运行 =====
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

    // ===== 主流程 =====
    let savedPages = new Set();   // 已保存的页码
    let isCollecting = false;

    // 监听 DOM 变化
    const observer = new MutationObserver(() => {
        if (!isCollecting) checkAndSave();
    });
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: false,
    });

    // 启动采集
    setTimeout(() => collect(), 2000);

    async function collect() {
        for (let page = 1; page <= MAX_PAGES; page++) {
            isCollecting = true;

            // 等待商品出现
            await waitForProducts();

            // 滚动
            await humanScroll();

            // 保存
            await saveHTML(page);
            savedPages.add(page);
            console.log('[JD-DL] ✅ 第' + page + '页已保存 (' + savedPages.size + '/' + MAX_PAGES + ')');

            if (page >= MAX_PAGES) break;

            GM_setValue(stateKey, '' + (page + 1));

            // 找翻页按钮
            const clicked = findAndClickNext();
            if (clicked) {
                console.log('[JD-DL] 👆 点击翻页到第' + (page + 1) + '页');
                isCollecting = false;
                // 等新商品出现（MutationObserver 会触发下一轮）
                await waitForPageChange(page);
            } else {
                console.log('[JD-DL] ⚠️ 无翻页按钮，结束');
                break;
            }
        }

        console.log('[JD-DL] ★ 完成，共 ' + savedPages.size + ' 页');
        GM_setValue(stateKey, MAX_PAGES + 999);
    }

    // ===== 辅助 =====

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
                // 多种选择器判断新商品加载
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
            // 回顶部
            window.scrollTo(0, 0);
            await new Promise(r => setTimeout(r, 500));
            resolve();
        });
    }

    function findAndClickNext() {
        // 尝试各类翻页按钮
        const selectors = [
            'a.pn-next:not(.disabled):not(.pn-next-disabled)',
            '.pn-next:not(.disabled):not(.pn-next-disabled)',
            '[class*="next"]:not(.disabled)',
            '[class*="pagination"] button:last-child:not([disabled])',
            '.numberbtn.active + .numberbtn',  // 当前页的下一个页码
        ];
        for (const sel of selectors) {
            try {
                const el = document.querySelector(sel);
                if (el) { el.click(); return true; }
            } catch(e) {}
        }
        // 遍历找包含 下一页 文字的元素
        const allEls = document.querySelectorAll('a, button, span, div');
        for (const el of allEls) {
            if (el.textContent && el.textContent.includes('下一页') && el.offsetHeight > 0) {
                el.click();
                return true;
            }
        }
        return false;
    }

    function saveHTML(page) {
        return new Promise(resolve => {
            const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
            const filename = kwName + '_jd_page' + page + '.html';
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

    // 后备：detect checkAndSave
    function checkAndSave() {
        // 这个方法留给 MutationObserver 监听用
        // 但目前 collect() 的 for 循环已经处理了流程
    }

})();
