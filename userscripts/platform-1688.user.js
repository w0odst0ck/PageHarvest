// ==UserScript==
// @name         1688 自动翻页+保存
// @namespace    http://tampermonkey.net/
// @version      1.4
// @description  每页滚动后下载HTML，翻页
// @match        *://s.1688.com/selloffer/offer_search.htm*
// @license      MIT
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const kwMatch = location.href.match(/[?&]keywords=([^&]+)/);
    if (!kwMatch) return;
    const kwEncoded = kwMatch[1];
    const currentPage = parseInt(location.href.match(/beginPage=(\d+)/)?.[1] || '1');

    const stateKey = '1688dl_p_' + kwEncoded;
    const expectedPage = parseInt(sessionStorage.getItem(stateKey) || '1');
    console.log('[1688DL] 第' + currentPage + '页');

    if (currentPage !== expectedPage) return;

    if (currentPage === 1 && !confirm('下载全部34页?\n第一次Chrome会提示允许下载，点"允许"即可')) {
        sessionStorage.setItem(stateKey, '999');
        return;
    }

    // 滚动加载
    let scrollCount = 0;
    const scrollTimer = setInterval(() => {
        scrollCount++;
        window.scrollTo(0, document.body.scrollHeight);
        if (scrollCount >= 12) { clearInterval(scrollTimer); clearTimeout(fallbackTimer); save(); }
    }, 1500);

    const fallbackTimer = setTimeout(() => { clearInterval(scrollTimer); save(); }, 25000);

    function save() {
        window.scrollTo(0, 0);
        setTimeout(() => {
            const html = document.documentElement.outerHTML;
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = kwEncoded + '_page' + currentPage + '.html';
            a.click();
            setTimeout(() => { URL.revokeObjectURL(url); }, 5000);
            console.log('[1688DL] ✓ 第' + currentPage + '页已保存');

            const nextPage = currentPage + 1;
            if (nextPage > 34) {
                console.log('[1688DL] 全部完成!');
                return;
            }
            sessionStorage.setItem(stateKey, '' + nextPage);
            console.log('[1688DL] 跳转第' + nextPage + '页...');
            setTimeout(() => {
                location.href = 'https://s.1688.com/selloffer/offer_search.htm?keywords=' + kwEncoded + '&beginPage=' + nextPage;
            }, 2000);
        }, 1000);
    }
})();
