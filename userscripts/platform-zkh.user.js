// ==UserScript==
// @name         震坤行 HTML下载器
// @namespace    http://tampermonkey.net/
// @version      9.2
// @description  震坤行：手动设定起始页，自动翻页下载（随机停顿 ≤5s + 手动救援）
// @match        https://www.zkh.com/search*
// @grant        GM_notification
// @grant        GM_getValue
// @grant        GM_setValue
// ==/UserScript==

(function() {
    'use strict';

    console.log('[ZKH-DL] 加载', location.href);

    const TOTAL = 20;
    const PRE_WAIT = 20000;           // 开始前等待（手动定位到起始页）
    const SCROLL_INTERVAL = 1200;
    const STUCK_LIMIT = 5;
    const RENDER_WAIT = 3000;
    const PAGE_CHANGE_TIMEOUT = 20000; // 翻页等待上限

    const keyword = new URL(location.href).searchParams.get('keywords') || 'unknown';
    const kwName = keyword.replace(/[%\/\\?&]/g, '_');
    const stateKey = 'zkh_auto_' + keyword;

    // ===== 主流程 =====
    (async function() {
        const lastPage = parseInt(GM_getValue(stateKey, '0'));

        if (lastPage > TOTAL) {
            GM_notification({ text: '震坤行 "' + decodeURIComponent(keyword) + '" 已完成所有页面', timeout: 5000 });
            console.log('[ZKH-DL] ★ 已完成 ' + TOTAL + ' 页');
            return;
        }

        // 等待用户手动定位到起始页
        console.log('[ZKH-DL] ⏳ 等 ' + (PRE_WAIT / 1000) + ' 秒，请先手动翻到起始页...');
        for (let i = PRE_WAIT / 1000; i > 0; i--) {
            if (i % 5 === 0 || i <= 3) console.log('[ZKH-DL] ⏳ ' + i + 's');
            await sleep(1000);
        }

        const defaultPage = lastPage > 0 ? '' + lastPage : '1';
        const hint = lastPage > 0
            ? '(上次采集到第 ' + lastPage + ' 页，请手动翻到当前页面后输入页码)'
            : '(脚本将从这一页开始，自动翻到第 ' + TOTAL + ' 页)';

        const input = prompt(
            '【震坤行 自动下载】\n\n' +
            '关键词: ' + decodeURIComponent(keyword) + '\n' +
            '请确认当前页面是第几页：\n' +
            hint,
            defaultPage
        );
        if (!input) { console.log('[ZKH-DL] 取消'); return; }
        let currentPage = parseInt(input);
        if (isNaN(currentPage) || currentPage <= 0) { console.log('[ZKH-DL] 无效'); return; }
        GM_setValue(stateKey, '' + currentPage);

        // ===== 主循环 =====
        for (let page = currentPage; page <= TOTAL; page++) {
            GM_setValue(stateKey, '' + page);
            console.log('[ZKH-DL] --- 第 ' + page + '/' + TOTAL + ' 页 ---');

            // 1. 等商品卡片加载
            await withTimeout(waitCards(page === currentPage), 20000);

            // 2. 自适应滚动到底（懒加载）
            await scrollBottom();

            // 3. 等渲染稳定
            await sleep(RENDER_WAIT);

            // 4. 保存当前页 HTML
            await saveHTML(page);
            console.log('[ZKH-DL] ✅ 第' + page + '页已保存');
            GM_notification({ text: '已保存第 ' + page + '/' + TOTAL + ' 页', timeout: 2000 });

            // 最后一页 → 结束
            if (page >= TOTAL) break;

            // ========== 5. 翻页（随机停顿 + 手动救援） ==========
            // 翻页前随机停顿 0~5 秒（模拟人类浏览节奏）
            const pause = Math.random() * 5000;
            console.log('[ZKH-DL] ⏳ 随机停顿 ' + (pause / 1000).toFixed(1) + 's 后翻页...');
            await sleep(pause);

            const clicked = clickNext(page);
            if (!clicked) {
                console.log('[ZKH-DL] ⚠️ 无翻页按钮，结束');
                break;
            }
            console.log('[ZKH-DL] 👆 翻页');

            const pageChanged = await withTimeout(waitPageChange(page + 1), PAGE_CHANGE_TIMEOUT);

            if (!pageChanged) {
                console.log('[ZKH-DL] ⚠️ 翻页超时，请求手动救援');

                const curDomPage = detectCurrentPageFromDOM();
                let extraMsg = '';
                if (curDomPage !== null && curDomPage !== page + 1) {
                    extraMsg = '\n⚠️ 当前 DOM 页码: ' + curDomPage + ' (预期: ' + (page + 1) + '，可能被跳转)';
                }

                const retryConfirm = confirm(
                    '『震坤行 手动救援』\n\n' +
                    '第 ' + page + ' 页已保存 ✅\n' +
                    '自动翻到第 ' + (page + 1) + ' 页失败 ❌' + extraMsg + '\n\n' +
                    '请手动操作：\n' +
                    '1) 如果被跳回前面页码 → 手动翻到第 ' + (page + 1) + ' 页\n' +
                    '2) 如果弹出验证码 → 完成验证后翻到第 ' + (page + 1) + ' 页\n' +
                    '3) 如果页面加载异常 → F5 刷新后再翻\n\n' +
                    '操作完成后点【确定】继续\n' +
                    '点【取消】暂停（进度已保存，下次刷新从第 ' + (page + 1) + ' 页继续）'
                );

                if (retryConfirm) {
                    console.log('[ZKH-DL] 用户确认手动翻页完成，继续采集');
                    continue;
                } else {
                    console.log('[ZKH-DL] 用户暂停');
                    GM_notification({
                        text: '已暂停，下次从第 ' + (page + 1) + ' 页继续',
                        timeout: 5000
                    });
                    break;
                }
            }
        }

        console.log('[ZKH-DL] ★ 完成');

        if (GM_getValue(stateKey, '0') >= TOTAL) {
            GM_setValue(stateKey, '' + (TOTAL + 1));
            GM_notification({ text: decodeURIComponent(keyword) + ' 全部 ' + TOTAL + ' 页采集完成!', timeout: 5000 });
        }
    })();

    // ===== 辅助函数 =====

    /** 等商品卡片出现 */
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

    /** 等翻页完成：检测商品数变化 + 分页按钮状态（SPA 版） */
    function waitPageChange(expectedPage) {
        return new Promise(resolve => {
            let prev = document.querySelectorAll('.goods-item-wrap-new').length;
            const timer = setInterval(() => {
                const cur = document.querySelectorAll('.goods-item-wrap-new').length;
                if (cur !== prev && cur >= 2) {
                    // 商品数变了 → 再用 DOM 分页按钮确认是否到了目标页
                    const domPage = detectCurrentPageFromDOM();
                    if (domPage !== null) {
                        if (domPage === expectedPage) {
                            clearInterval(timer);
                            resolve(true);
                            return;
                        }
                        // DOM 页码不对 → 可能被跳转，但商品数确实变了
                        // 不 resolve，等超时返回 false
                    } else {
                        // 拿不到 DOM 页码 → 保守认为翻页成功
                        clearInterval(timer);
                        resolve(true);
                        return;
                    }
                }
                prev = cur;
            }, 500);
            setTimeout(() => { clearInterval(timer); resolve(false); }, PAGE_CHANGE_TIMEOUT);
        });
    }

    /** 从 DOM 分页按钮推断当前页码（适配 SPA） */
    function detectCurrentPageFromDOM() {
        try {
            // 优先找 active/cur 类
            const active = document.querySelector('.numberbtn.active, .numberbtn.cur, .numberbtn.on');
            if (active) {
                const n = parseInt(active.textContent);
                if (!isNaN(n)) return n;
            }

            // 没有 active 类 → 找所有数字按钮，看哪个在可视区域有高亮
            const btns = document.querySelectorAll('.numberbtn');
            for (const btn of btns) {
                const n = parseInt(btn.textContent);
                if (!isNaN(n)) {
                    // 检查是否有选中样式
                    if (btn.classList.contains('active') || btn.classList.contains('cur') ||
                        btn.classList.contains('selected') || btn.classList.contains('on')) {
                        return n;
                    }
                }
            }

            // 实在找不到 → 看看是否有分页总页数/当前页文本，如 "第 3/20 页"
            const pageInfo = document.body.textContent.match(/第\s*(\d+)\s*\/\s*(\d+)\s*页/);
            if (pageInfo) return parseInt(pageInfo[1]);

            return null;
        } catch (e) {
            return null;
        }
    }

    /** 自适应滚动到底（触发懒加载） */
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

    /** 点击下一页按钮 */
    function clickNext(page) {
        // 优先找标有 page+1 的数字按钮
        const btns = document.querySelectorAll('.numberbtn');
        for (const btn of btns) {
            if (parseInt(btn.textContent) === page + 1) {
                btn.click(); return true;
            }
        }

        // 兜底：点击未禁用的「下一页」
        const next = document.querySelector('.nextbtn:not(.disabled)');
        if (next) { next.click(); return true; }
        return false;
    }

    /** 触发浏览器下载 HTML */
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
