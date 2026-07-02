// ==UserScript==
// @name         震坤行 HTML下载器
// @namespace    http://tampermonkey.net/
// @version      8.0
// @description  震坤行：手动设定起始页，然后自动翻页下载
// @match        https://www.zkh.com/search*
// @grant        GM_notification
// @grant        GM_getValue
// @grant        GM_setValue
// ==/UserScript==

(function() {
    'use strict';

    console.log('[ZKH-DL] 加载', location.href);

    const TOTAL = 20;        // 震坤行只有 20 页
    const PRE_WAIT = 20000;         // 开始前等你手选页面
    const SCROLL_INTERVAL = 1200;
    const STUCK_LIMIT = 5;
    const RENDER_WAIT = 3000;
    const PAGE_CHANGE_TIMEOUT = 12000;

    const keyword = new URL(location.href).searchParams.get('keywords') || 'unknown';
    const kwName = keyword.replace(/[%\/\\?&]/g, '_');
    const stateKey = 'zkh_auto_' + keyword;

    // ===== 主流程 =====
    (async function() {
        let currentPage = parseInt(GM_getValue(stateKey, '0'));

        if (currentPage > TOTAL) {
            console.log('[ZKH-DL] ★ 已完成 ' + TOTAL + ' 页');
            return;
        }

        // 首次运行：等20秒让你手选页面，再输入页码
        if (currentPage === 0) {
            console.log('[ZKH-DL] ⏳ 等 ' + (PRE_WAIT / 1000) + ' 秒，请先手动翻到起始页...');
            for (let i = PRE_WAIT / 1000; i > 0; i--) {
                if (i % 5 === 0 || i <= 3) console.log('[ZKH-DL] ⏳ ' + i + 's');
                await sleep(1000);
            }

            const input = prompt(
                '【震坤行 自动下载】\n\n' +
                '关键词: ' + decodeURIComponent(keyword) + '\n' +
                '请确认当前页面是第几页：\n' +
                '(脚本将从这一页开始，自动翻到第 ' + TOTAL + ' 页)',
                '1'
            );
            if (!input) { console.log('[ZKH-DL] 取消'); return; }
            currentPage = parseInt(input);
            if (isNaN(currentPage) || currentPage <= 0) { console.log('[ZKH-DL] 无效'); return; }
            GM_setValue(stateKey, '' + currentPage);
        } else {
            console.log('[ZKH-DL] 继续第 ' + currentPage + ' 页');
        }

        // ===== 主循环 =====
        for (let page = currentPage; page <= TOTAL; page++) {
            GM_setValue(stateKey, '' + page);
            console.log('[ZKH-DL] --- 第 ' + page + '/' + TOTAL + ' 页 ---');

            // 1. 等商品
            await withTimeout(waitCards(page === currentPage), 20000);

            // 2. 自适应滚动到底
            await scrollBottom();

            // 3. 等渲染
            await sleep(RENDER_WAIT);

            // 4. 保存
            await saveHTML(page);
            console.log('[ZKH-DL] ✅ 第' + page + '页已保存');

            // 最后一页
            if (page >= TOTAL) break;

            // 5. 点击翻页
            const clicked = clickNext(page);
            if (!clicked) {
                console.log('[ZKH-DL] ⚠️ 无翻页按钮，结束');
                break;
            }
            console.log('[ZKH-DL] 👆 翻页');

            // 6. 等新商品
            const changed = await withTimeout(waitPageChange(), PAGE_CHANGE_TIMEOUT);
            if (!changed) {
                console.log('[ZKH-DL] ⚠️ 翻页超时（可能被反爬跳转），等待重试');
                // 超时 → 中断循环，下次刷新页面会继续
                break;
            }
        }

        console.log('[ZKH-DL] ★ 完成，共 ' + TOTAL + ' 页');

        // 如果正常结束，标记完成
        if (GM_getValue(stateKey, '0') >= TOTAL) {
            GM_setValue(stateKey, '' + (TOTAL + 1));
        }
        // 如果中途中断（反爬），不标记完成，刷新后从当前页继续
    })();

    // ===== 辅助 =====

    function waitCards(isFirst) {
        return new Promise(resolve => {
            const timer = setInterval(() => {
                if (document.querySelectorAll('.goods-item-wrap-new').length >= 2) {
                    clearInterval(timer);
                    resolve();
                }
            }, 500);
            setTimeout(() => { clearInterval(timer); resolve(); }, isFirst ? 25000 : 15000);
        });
    }

    function waitPageChange() {
        return new Promise(resolve => {
            let prev = document.querySelectorAll('.goods-item-wrap-new').length;
            const timer = setInterval(() => {
                const cur = document.querySelectorAll('.goods-item-wrap-new').length;
                if (cur !== prev && cur >= 2) {
                    clearInterval(timer);
                    resolve(true);
                }
                prev = cur;
            }, 500);
            setTimeout(() => { clearInterval(timer); resolve(false); }, PAGE_CHANGE_TIMEOUT);
        });
    }

    function scrollBottom() {
        return new Promise(async resolve => {
            let last = 0, stuck = 0;
            while (stuck < STUCK_LIMIT) {
                window.scrollTo(0, document.body.scrollHeight);
                await sleep(SCROLL_INTERVAL);
                const h = document.body.scrollHeight;
                if (h === last) stuck++;
                else { stuck = 0; last = h; }
            }
            window.scrollTo(0, 0);
            resolve();
        });
    }

    function clickNext(page) {
        const btns = document.querySelectorAll('.numberbtn');
        for (const btn of btns) {
            if (parseInt(btn.textContent) === page + 1) {
                btn.click(); return true;
            }
        }
        const next = document.querySelector('.nextbtn:not(.disabled)');
        if (next) { next.click(); return true; }
        return false;
    }

    function saveHTML(page) {
        return new Promise(resolve => {
            const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
            const filename = kwName + '_zkh_page' + page + '.html';
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(resolve, 1500);
        });
    }

    function withTimeout(promise, ms) {
        return Promise.race([
            promise,
            new Promise(r => setTimeout(() => r(false), ms))
        ]);
    }

    function sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    }

})();
