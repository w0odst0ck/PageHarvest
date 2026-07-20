/**
 * 1688 (Alibaba) 搜索页 + 详情页解析器
 *
 * 纯 DOM 解析，不加载外部资源。
 * 支持原始 1688 HTML 以及浏览器保存的 SingleFile / 完整页面。
 *
 * 搜索页输出: 商品列表 [{ title, price, sales, link, images, ... }]
 * 详情页输出: 单品详情 { title, price_min, price_max, brand, attributes, ... }
 */

'use strict';

const AlibabaParser = (() => {

  // ── 平台检测 ──

  function detect(html) {
    return html.includes('detail.1688.com/offer/') ||
           html.includes('cbu01.alicdn.com') ||
           html.includes('s.1688.com/selloffer') ||
           html.includes('1688.com') && (
             html.includes('offer-list-item-wrap') ||
             html.includes('search-offer-item') ||
             html.includes('module-od-product-attributes')
           );
  }

  function isSearchPage(html) {
    return html.includes('s.1688.com/selloffer') ||
           html.includes('offer_search.htm') ||
           html.includes('class="offer-list-item-wrap"') ||
           html.includes('class="search-offer-item"') ||
           html.includes('goods-item-wrap-new');
  }

  function isDetailPage(html) {
    return html.includes('detail.1688.com/offer/') &&
           !isSearchPage(html);
  }

  function detectPageType(html) {
    if (isSearchPage(html)) return 'search';
    if (isDetailPage(html)) return 'detail';
    return 'unknown';
  }

  // ── HTML 工具 ──

  function parseHtml(html) {
    const parser = new DOMParser();
    return parser.parseFromString(html, 'text/html');
  }

  function text(el) {
    return el ? el.textContent.trim() : '';
  }

  function attr(el, name) {
    return el ? (el.getAttribute(name) || '').trim() : '';
  }

  // ── 通用图片提取 ──
  // 尝试多个属性依次回退，兼容各种保存格式
  function extractImages(container, selector, attrPriority) {
    // attrPriority: ['data-sf-original-src', 'data-lazyload', 'data-src', 'src']
    const imgs = container.querySelectorAll(selector);
    return Array.from(imgs).map(img => {
      for (const attr of attrPriority) {
        const url = img.getAttribute(attr);
        if (url && url.trim()) return url.trim();
      }
      return '';
    }).filter(Boolean);
  }

  // ── 搜索页解析 ──
  // 兼容两种结构：
  //   A) 新版: .offer-list-item-wrap
  //   B) 旧版: .search-offer-item (来自 Python 解析器)

  function parseSearch(html) {
    const doc = parseHtml(html);
    const results = [];

    // 尝试两种容器选择器
    let items = doc.querySelectorAll('.offer-list-item-wrap, [class*="offer-list-item"], .search-offer-item, [class*="search-offer-item"]');
    // 兜底：找含有 "offer" 关键词的商品容器 div
    if (items.length === 0) {
      items = doc.querySelectorAll('div[class*="offer"]');
      // 进一步过滤：至少包含标题元素
      items = Array.from(items).filter(el =>
        el.querySelector('a[href*="offer"]') ||
        el.querySelector('[class*="title"]')
      );
    }

    for (const item of items) {
      try {
        const p = {};

        // 标题
        const titleEl = item.querySelector('.offer-title-row a, .title a, [class*="title"] a, [class*="title"]');
        p.title = text(titleEl || item.querySelector('a[href*="offer/"]'));

        // 价格
        const priceEl = item.querySelector('.offer-price-row, .price, [class*="price"]');
        let priceText = text(priceEl);
        const priceMatch = priceText.replace(/,/g, '').match(/[\d]+(?:\.[\d]+)?/);
        p.price = priceMatch ? parseFloat(priceMatch[0]) : 0;
        p.price_range = priceText.trim();

        // 销量
        const saleEl = item.querySelector('.sale, [class*="sale"], .desc-text');
        p.sales = text(saleEl);
        // 从 desc-text 中找销量/成交
        if (!p.sales || p.sales.length === 0) {
          const descTexts = item.querySelectorAll('.desc-text');
          for (const dt of descTexts) {
            const t = text(dt);
            if (t.includes('成交') || t.includes('销量')) {
              p.sales = t;
              break;
            }
          }
        }

        // 链接
        const linkEl = item.querySelector('.offer-title-row a, .title a, a[href*="offer/"]');
        p.link = attr(linkEl || item.querySelector('a[href*="detail.1688.com"]'), 'href') || '';

        // 图片（增强：尝试多个属性回退）
        const attrPriority = ['data-sf-original-src', 'data-lazyload', 'data-src', 'src'];
        const imgSelectors = '.main-img, img[class*="img"], img[src*="alicdn"], img[data-sf-original-src], img[data-lazyload]';
        p.images = extractImages(item, imgSelectors, attrPriority)
          .filter(url => !url.startsWith('data:'));

        // 店铺
        const shopEl = item.querySelector('.offer-shop-row, [class*="shop"] a');
        p.shop_name = text(shopEl);

        if (p.title) {
          results.push(p);
        }
      } catch (e) {
        // skip invalid items
      }
    }

    return results;
  }

  // ── 详情页解析 ──

  function parseDetail(html) {
    const doc = parseHtml(html);
    const detail = {};

    // 1. 商品ID
    detail.product_id = extractProductId(html);

    // 2. 标题
    detail.title = extractTitle(doc, html);

    // 3. 价格
    const [pmin, pmax] = extractPrice(html);
    detail.price_min = pmin;
    detail.price_max = pmax;

    // 4. 品牌/型号
    detail.brand = '';
    detail.spec = '';

    // 5. 属性
    detail.attributes = extractAttributes(doc, html);

    // 从属性中提取品牌和型号
    for (const [k, v] of Object.entries(detail.attributes)) {
      if (k === '品牌' && !detail.brand) detail.brand = v;
      if ((k === '货号' || k === '型号' || k === '制造商型号') && !detail.spec) detail.spec = v;
    }

    // 6. SKU
    detail.sku_variants = extractSkuVariants(doc, html);
    detail.sku_count = detail.sku_variants.length;

    // 7. 主图
    detail.main_images = extractMainImages(doc, html);

    // 8. 详情图
    detail.detail_images = extractDetailImages(doc, html);

    // 9. 描述
    detail.description = extractDescription(doc, html);

    return detail;
  }

  // ── 提取辅助 ──

  function extractProductId(html) {
    const m = html.match(/detail\.1688\.com\/offer\/(\d+)/);
    if (m) return m[1];
    const m2 = html.match(/"offerId"\s*:\s*(\d+)/);
    if (m2) return m2[1];
    return '';
  }

  function extractTitle(doc, html) {
    // 1. 找 h1 标签
    const h1s = doc.querySelectorAll('h1');
    for (const h1 of h1s) {
      const t = text(h1);
      if (t.length >= 8 && !t.includes('经营部') && !t.includes('公司') && !t.includes('验货报告')) {
        return t;
      }
    }
    // 2. 兜底 title 标签
    const m = html.match(/<title>([^<]+)<\/title>/);
    if (m) {
      return m[1].replace(/\s*[-–—]\s*阿里巴巴.*$/, '').trim();
    }
    return '';
  }

  function extractPrice(html) {
    // 从 <span class="currency"> 提取价格
    const prices = [];
    const currencyRe = /<span\s+class="currency">([\d.]+)<\/span>/g;
    let m;
    while ((m = currencyRe.exec(html)) !== null) {
      prices.push(m[1]);
    }

    if (prices.length === 0) return [0, 0];

    // 拼接连续的价格片段
    const parsed = [];
    let buf = '';
    for (const p of prices) {
      if (p.startsWith('.')) {
        buf += p;
      } else if (buf) {
        parsed.push(parseFloat(buf));
        buf = p;
      } else {
        buf = p;
      }
    }
    if (buf) parsed.push(parseFloat(buf));

    if (parsed.length === 0) return [0, 0];
    return [Math.min(...parsed), Math.max(...parsed)];
  }

  function extractAttributes(doc, html) {
    const attrs = {};

    // 策略1: ant-design 属性表
    const rows = doc.querySelectorAll('.ant-descriptions-row, .ant-descriptions-item');
    if (rows.length > 0) {
      const labels = doc.querySelectorAll('th.ant-descriptions-item-label span');
      const values = doc.querySelectorAll('td.ant-descriptions-item-content span span.field-value');
      for (let i = 0; i < labels.length && i < values.length; i++) {
        const name = text(labels[i]);
        const value = text(values[i]);
        if (name && value) attrs[name] = value;
      }
    }

    // 策略2: 正则 fallback
    if (Object.keys(attrs).length === 0) {
      const pattern = /<th[^>]*class="ant-descriptions-item-label"[^>]*>\s*<span>([^<]+)<\/span>\s*<\/th>\s*<td[^>]*class="ant-descriptions-item-content"[^>]*>\s*<span>\s*<span[^>]*class="field-value"[^>]*>([^<]+)<\/span>/g;
      let m;
      while ((m = pattern.exec(html)) !== null) {
        attrs[m[1].trim()] = m[2].trim();
      }
    }

    // 策略3: 通用 dl/dt/dd 属性表
    if (Object.keys(attrs).length === 0) {
      const dtElements = doc.querySelectorAll('.mod-detail dt, [class*="attribute"] dt, .prop-item dt');
      dtElements.forEach(dt => {
        const dd = dt.nextElementSibling;
        if (dd) {
          attrs[text(dt)] = text(dd);
        }
      });
    }

    return attrs;
  }

  function extractSkuVariants(doc, html) {
    const variants = [];

    // 策略1: sku-filter-button
    const skuButtons = doc.querySelectorAll('.sku-filter-button span.label-name');
    skuButtons.forEach(el => {
      const t = text(el);
      if (t) variants.push({ spec: t, price: 0, spec_type: '规格' });
    });

    // 策略2: item-label + item-price 组合
    const itemLabelRe = /<span[^>]*class="item-label"[^>]*title="([^"]*)"[^>]*>.*?<\/span>\s*<span[^>]*class="item-price[^"]*"[^>]*>(.*?)<\/span>/g;
    let m;
    while ((m = itemLabelRe.exec(html)) !== null) {
      const label = m[1].trim();
      const priceHtml = m[2];
      const prices = priceHtml.match(/<span class="currency">([\d.]+)<\/span>/g);
      let price = 0;
      if (prices) {
        const joined = prices.map(p => p.replace(/<[^>]+>/g, '')).join('');
        price = parseFloat(joined) || 0;
      }
      if (label && !variants.some(v => v.spec === label)) {
        variants.push({ spec: label, price, spec_type: '价格' });
      }
    }

    return variants;
  }

  function reconstructCdnUrl(src) {
    if (!src) return '';
    if (src.startsWith('http://') || src.startsWith('https://')) return src;
    if (src.startsWith('data:')) return '';

    // 浏览器保存页面时会把图片路径改成 _files/xxx
    const filename = src.replace(/^.*[\\/]/, '').replace(/[\\/]/g, '');

    // 去掉 _.webp / _.jpg 等后缀
    let clean = filename.replace(/_(?:\.webp|\.jpg|\.jpeg|\.png)$/, '');

    // ibank 格式
    if (/^[A-Za-z0-9_!-]+\.[a-z]+$/.test(clean) && !clean.includes('_files')) {
      return `https://cbu01.alicdn.com/img/ibank/${clean}`;
    }

    return src;
  }

  function extractMainImages(doc, html) {
    const seen = new Set();
    const images = [];

    // 策略1: preview-img (尝试多种属性回退)
    const attrPriority = ['data-sf-original-src', 'data-lazyload', 'src', 'data-src'];
    const previewImgs = doc.querySelectorAll('img.ant-image-img.preview-img, img.preview-img, img[class*="preview"], img[class*="gallery"]');
    previewImgs.forEach(img => {
      for (const attrName of attrPriority) {
        const src = img.getAttribute(attrName);
        if (src && src.trim()) {
          const url = reconstructCdnUrl(src.trim());
          if (url && !seen.has(url)) {
            seen.add(url);
            images.push(url);
          }
          break;
        }
      }
    });

    // 策略2: cbu01.alicdn.com 图片（从 HTML 正则）
    if (images.length === 0) {
      const re = /src="(https?:\/\/cbu01\.alicdn\.com\/img\/ibank\/[^"]+)"/g;
      let m;
      while ((m = re.exec(html)) !== null) {
        const url = m[1];
        if (!url.includes('_88x88') && !seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    // 策略3: data-sf-original-src 中的 alicdn 链接（SingleFile 保存时常见）
    if (images.length === 0) {
      const re = /data-sf-original-src="(https?:\/\/[^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"/g;
      let m;
      while ((m = re.exec(html)) !== null) {
        const url = m[1];
        if (!seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    return images;
  }

  function extractDetailImages(doc, html) {
    const seen = new Set();
    const images = [];

    // 策略1: html-description 容器
    const descMatch = html.match(/<v-detail-c\s+class="html-description"[^>]*>(.*?)<\/v-detail-c>/s);
    if (descMatch) {
      const descHtml = descMatch[1];
      const re = /src="(https?:\/\/[^"]+\.(?:jpg|jpeg|png|webp))"/g;
      let m;
      while ((m = re.exec(descHtml)) !== null) {
        const url = m[1];
        if (!seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    // 策略2: #offer-template-0 容器
    if (images.length === 0) {
      const templateMatch = html.match(/<div[^>]*id="offer-template-0"[^>]*>(.*?)(?:<\/div>\s*<\/div>|<v-detail-c)/s);
      if (templateMatch) {
        const tmplHtml = templateMatch[1];
        const re = /src="(https?:\/\/[^"]+\.(?:jpg|jpeg|png|webp))"/g;
        let m;
        while ((m = re.exec(tmplHtml)) !== null) {
          const url = m[1];
          if (!seen.has(url) && url.includes('ibank')) {
            seen.add(url);
            images.push(url);
          }
        }
      }
    }

    return images;
  }

  function extractDescription(doc, html) {
    const m = html.match(/<v-detail-c\s+class="html-description"[^>]*>(.*?)<\/v-detail-c>/s);
    if (m) {
      return m[1].substring(0, 1000);
    }
    return '';
  }

  // ── 统一输出 ──

  function toSearchRows(results) {
    return results.map(p => ({
      '标题': p.title || '',
      '价格': p.price || 0,
      '价格区间': p.price_range || '',
      '销量': p.sales || '',
      '链接': p.link || '',
      '图片': (p.images || []).join('\n'),
      '店铺': p.shop_name || '',
    }));
  }

  function toDetailRows(results) {
    const rows = [];
    for (const d of results) {
      const baseRow = {
        '商品ID': d.product_id || '',
        '标题': d.title || '',
        '品牌': d.brand || '',
        '型号': d.spec || '',
        '最低价': d.price_min || 0,
        '最高价': d.price_max || 0,
        '属性数': Object.keys(d.attributes || {}).length,
        'SKU数': d.sku_count || 0,
        '主图数': (d.main_images || []).length,
        '主图链接': (d.main_images || []).join('\n'),
      };
      rows.push(baseRow);
    }
    return rows;
  }

  // ── 公共 API ──

  return {
    detect,
    detectPageType,
    isSearchPage,
    isDetailPage,
    parseSearch,
    parseDetail,
    toSearchRows,
    toDetailRows,
  };

})();
