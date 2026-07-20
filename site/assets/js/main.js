/* ═══════════════════════════════════════════
   PageHarvest — 官网轻量交互脚本
   ═══════════════════════════════════════════ */

(function () {
  'use strict';

  // ── 移动端导航切换 ──
  var toggleBtn = document.getElementById('navToggle');
  var navLinks = document.getElementById('navLinks');

  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener('click', function () {
      navLinks.classList.toggle('open');
    });

    // 点击导航链接后自动收起菜单
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        navLinks.classList.remove('open');
      });
    });
  }

  // ── 当前页面高亮（在已展开的 nav 中确认 active） ──
  var currentPath = window.location.pathname.split('/').pop() || 'index.html';
  navLinks.querySelectorAll('a').forEach(function (link) {
    var href = link.getAttribute('href');
    if (href === currentPath) {
      link.classList.add('active');
    } else {
      // 移除可能残留的 active
      if (href.indexOf('://') === -1 && href !== '#') {
        link.classList.remove('active');
      }
    }
  });

  // ── 平滑滚动（对页内锚点） ──
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

})();
