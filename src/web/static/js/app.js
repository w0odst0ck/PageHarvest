// PageHarvest — 前端通用逻辑

// 自动关闭 flash 消息
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => { el.style.opacity = '0'; }, 3000);
  });
});
