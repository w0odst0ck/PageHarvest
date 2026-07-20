/**
 * 震坤行 (zkh.com) 搜索页 + 详情页解析器
 *
 * 纯 DOM 解析，不加载外部资源。
 * 兼容浏览器保存的 SingleFile / 完整页面以及 SPA 壳 HTML。
 *
 * DOM 选择器源于 Python 解析器 (src/platforms/zkh/) 的实际页面结构。
 *
 * 搜索页输出: 商品列表 [{ title, price, brand, model, link, image, ... }]
 * 详情页输出: 单品详情 { product_id, sku_code, title, brand, model, price, attributes, ... }
 */

'use strict';

const ZKHParser = (() => {

  // ── 平台检测 ──

  function detect(html) {
    return html.includes('zkh.com') ||
           html.includes('private.zkh.com') ||
           html.includes('震坤行') ||
           html.includes('goods-item-wrap-new') ||
           (html.includes('sku-number') && html.includes('sku-price-wrap-new'));
  }

  function isSearchPage(html) {
    return html.includes('goods-item-wrap-new') ||
           html.includes('/search?keywords=') ||
           /class="[^"]*goods-item[^"]*"/.test(html);
  }

  function isDetailPage(html) {
    return detect(html) && !isSearchPage(html) && (
      html.includes('sku-number') ||
      html.includes('sku-price-wrap-new') ||
      html.includes('gallery-slick-box')
    );
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

  // ── 搜索页解析 ──
  //
  // 震坤行搜索页商品卡片结构（来自 Python 解析器）:
  //   <div class="goods-item-wrap-new clearfix common-item-wrap">
  //     <div class="goods-name" title="商品标题 品牌/型号">...</div>
  //     <span class="integer">15</span><span class="decimal">.50</span>
  //     <img src="..." />
  //     <a href="//zkh.com/product/detail/XXX.html">...</a>
  //     制造商型号: XXX
  //     单位: 个
  //   </div>

  function parseSearch(html) {
    const doc = parseHtml(html);
    const results = [];

    // 选择商品卡片
    const items = doc.querySelectorAll(
      '.goods-item-wrap-new, ' +
      '[class*="goods-item-wrap"], ' +
      '[class*="product-item"], ' +
      '.common-item-wrap'
    );

    for (const item of items) {
      try {
        const p = {};

        // 标题：优先 title 属性，取 goods-name 的 title
        const titleEl = item.querySelector('[class*="goods-name"], [class*="goods-name"]');
        p.title = attr(titleEl, 'title') || text(titleEl);

        // 兜底：从 a 标签或 h 标签提取
        if (!p.title) {
          const fallbackEl = item.querySelector('a[href*="zkh"], a[href*="product"], h3, h4');
          p.title = text(fallbackEl);
        }

        if (!p.title) continue;

        // 价格：span.integer + span.decimal 拼接
        const intEl = item.querySelector('.integer, [class*="integer"]');
        const decEl = item.querySelector('.decimal, [class*="decimal"]');
        let priceStr = '';
        if (intEl) {
          priceStr = text(intEl);
          if (decEl) priceStr += text(decEl);
        }
        p.price = parseFloat(priceStr) || 0;

        // 兜底价格：从任何包含价格的文本中提取
        if (p.price === 0) {
          const priceMatch = item.textContent.replace(/,/g, '').match(/[¥￥]?\s*(\d+(?:\.\d+)?)/);
          p.price = priceMatch ? parseFloat(priceMatch[1]) : 0;
        }

        // 链接
        const linkEl = item.querySelector('a[href*="zkh"], a[href*="product"], a[href*="item"]');
        let link = attr(linkEl, 'href') || '';

        // 跳转页面的相对链接处理
        if (link && !link.startsWith('http')) {
          if (link.startsWith('//')) {
            link = 'https:' + link;
          } else if (link.startsWith('/')) {
            link = 'https://www.zkh.com' + link;
          }
        }
        p.link = link;

        // 商品 ID
        const idMatch = link.match(/\/item\/([^./?]+)/);
        p.product_id = idMatch ? idMatch[1] : '';

        // 图片
        const imgEl = item.querySelector('img');
        p.image = attr(imgEl, 'src') || attr(imgEl, 'data-src') || '';

        // 品牌：从标题中 "/" 后的第一个词提取
        if (p.title.includes('/')) {
          const afterSlash = p.title.split('/', 1)[1] || '';
          p.brand = afterSlash.trim().split(/\s+/)[0] || '';
        } else {
          p.brand = '';
        }

        // 制造商型号
        const allText = item.textContent;
        const modelMatch = allText.match(/制造商型号[：:]*\s*([^，,\s]+)/);
        p.model = modelMatch ? modelMatch[1].trim() : '';

        // 单位
        const unitEl = item.querySelector('[class*="unit"]');
        p.unit = text(unitEl);

        // 获取 URL 中 product_id 匹配的 tags（从页面 JSON 数据中）
        p.tags = [];

        results.push(p);
      } catch (e) {
        // skip invalid items
      }
    }

    return results;
  }

  // ── 详情页解析 ──
  //
  // 震坤行详情页结构（来自 Python 解析器）:
  //   <title>商品名称 -震坤行</title>
  //   <div class="clearfix sku-number">订货编码：AE123456</div>
  //   <div class="sku-price-wrap-new">¥15.50 / 个</div>
  //   <div class="params-wrap"><div class="params-item">品牌 ：FSL/佛山照明</div>...
  //   <div class="gallery-slick-box"><img data-sf-original-src="https://private.zkh.com/..." />
  //   <div class="sku-stock-wrap">现货，发货地：上海市</div>

  function parseDetail(html) {
    const doc = parseHtml(html);
    const detail = {};

    // 1. 标题
    detail.title = extractTitle(doc, html);

    // 2. 商品 ID
    detail.product_id = extractProductId(html);

    // 3. SKU 编码（订货编码）
    detail.sku_code = extractSkuCode(doc, html);

    // 4. 品牌
    detail.brand = extractParam(doc, '品牌');

    // 5. 型号（制造商型号）
    detail.model = extractParam(doc, '制造商型号');

    // 6. 价格
    const [priceMin, priceMax] = extractPrice(doc, html);
    detail.price_min = priceMin;
    detail.price_max = priceMax;

    // 7. 属性
    detail.attributes = extractAttributes(doc);

    // 8. SKU 变体
    detail.sku_variants = extractSkuVariants(doc, html);
    detail.sku_count = detail.sku_variants.length;

    // 9. 主图
    detail.main_images = extractMainImages(doc, html);

    // 10. 发货/配送信息
    detail.delivery_info = extractDeliveryInfo(doc);
    detail.stock_status = '';
    if (detail.delivery_info) {
      if (detail.delivery_info.includes('现货')) {
        detail.stock_status = '现货';
      } else if (detail.delivery_info.includes('预定') || detail.delivery_info.includes('预售')) {
        detail.stock_status = '预售';
      }
    }

    // 11. 发货地
    detail.ship_from = extractShipFrom(doc, html);

    // 12. 标签
    detail.tags = extractTags(html);

    // 13. 起批量
    detail.min_order = extractMinOrder(html);

    // 14. 描述
    detail.description = extractDescription(doc, html);

    return detail;
  }

  // ── 提取辅助 ──

  function extractTitle(doc, html) {
    // 1. <title> 标签
    const titleTag = doc.querySelector('title');
    if (titleTag) {
      let t = text(titleTag);
      t = t.replace(/\s*[-–—]震坤行$/, '').trim();
      if (t && t.length >= 4) return t;
    }

    // 2. 多种选择器兜底
    const selectors = [
      '.goods-title', '.name', '.item-header',
      'h1', '.product-name', '.goods-name',
      '.product-title', '[class*="detail-title"]',
      '[class*="product-name"]',
    ];
    for (const sel of selectors) {
      const el = doc.querySelector(sel);
      if (el) {
        const t = text(el);
        if (t && t.length >= 4) return t;
      }
    }

    // 3. 兜底：从页面正则提取
    const m = html.match(/"title":\s*"([^"]+)"/);
    return m ? m[1] : '';
  }

  function extractProductId(html) {
    // 从 data-sf-original-src 中的 BIG_ 文件名提取
    const m = html.match(/data-sf-original-src="[^"]*BIG_([A-Z0-9]+)_\d+/);
    if (m) return m[1];

    // 从 JSON 数据中提取
    const m2 = html.match(/"productId":\s*"([A-Z0-9]+)"/);
    if (m2) return m2[1];

    const m3 = html.match(/"proGroupNo":\s*"([A-Z0-9]+)"/);
    if (m3) return m3[1];

    // 从 URL 提取
    const m4 = html.match(/\/item\/([^./?]+)/);
    return m4 ? m4[1] : '';
  }

  function extractSkuCode(doc, html) {
    const skuEl = doc.querySelector('.clearfix.sku-number, [class*="sku-number"]');
    if (skuEl) {
      const t = text(skuEl);
      const m = t.match(/([A-Z]{2}\d+)/);
      if (m) return m[1];
    }

    // 兜底
    const m = html.match(/订货编码[：:]\s*([A-Z]{2}\d+)/);
    return m ? m[1] : '';
  }

  function extractParam(doc, key) {
    // 从 params-wrap 中查找指定 key
    const items = doc.querySelectorAll('.params-wrap .params-item, .params-item, .param-item');
    for (const item of items) {
      const t = text(item);
      if (t.startsWith(key) || t.startsWith(key + ' ')) {
        return t.replace(/^[^：:]*[：:]/, '').trim();
      }
    }
    // 纯文本查找
    const allText = doc.body ? doc.body.textContent : '';
    const re = new RegExp(key + '[：:]*\\s*([^，,\\s]+(?:[\\s/][^，,\\s]+)*)');
    const m = allText.match(re);
    return m ? m[1].trim() : '';
  }

  function extractPrice(doc, html) {
    // 1. 从 SKU 价格区提取
    const priceAreas = doc.querySelectorAll('.sku-price-wrap-new, [class*="sku-price"]');
    for (const pa of priceAreas) {
      const t = text(pa);
      const m = t.match(/[¥￥]?\s*([\d.]+)\s*\/\s*\S+/);
      if (m) {
        const val = parseFloat(m[1]);
        if (val > 0) return [val, val];
      }
    }

    // 2. 兜底：官网价
    const m = html.match(/官网价[¥￥]\s*([\d.]+)/);
    if (m) {
      const val = parseFloat(m[1]);
      if (val > 0) return [val, val];
    }

    // 3. 任何价格文本
    const priceMatch = html.replace(/,/g, '').match(/[¥￥]\s*([\d]+(?:\.[\d]+)?)/);
    if (priceMatch) {
      const val = parseFloat(priceMatch[1]);
      if (val > 0) return [val, val];
    }

    return [0, 0];
  }

  function extractAttributes(doc) {
    const attrs = {};

    // 策略1: .params-wrap .params-item
    const items = doc.querySelectorAll('.params-wrap .params-item, .params-wrap .param-item, .params-item');
    for (const item of items) {
      const t = text(item);
      const m = t.match(/^(.+?)\s*[：:]\s*(.+)$/);
      if (m) {
        const key = m[1].trim();
        const val = m[2].trim();
        if (key.length > 1 && key.length < 30 && val.length > 0) {
          attrs[key] = val;
        }
      }
    }

    // 策略2: 属性表格
    if (Object.keys(attrs).length === 0) {
      const rows = doc.querySelectorAll('.attribute-table tr, .params-table tr, [class*="attribute"] tr, .detail-params tr');
      rows.forEach(row => {
        const cells = row.querySelectorAll('th, td');
        if (cells.length >= 2) {
          const key = text(cells[0]);
          const val = text(cells[1]);
          if (key && val) attrs[key] = val;
        }
      });
    }

    return attrs;
  }

  function extractSkuVariants(doc, html) {
    const variants = [];

    // 每个 SKU 项结构: .clearfix.sku-number + .sku-price-wrap-new 配对
    const skuNumbers = doc.querySelectorAll('.clearfix.sku-number, [class*="sku-number"]');
    const skuPrices = doc.querySelectorAll('.sku-price-wrap-new, [class*="sku-price"]');

    skuNumbers.forEach((skuNum, i) => {
      const skuText = text(skuNum);
      const skuMatch = skuText.match(/订货编码[：:]\s*([A-Z]{2}\d+)/);
      const modelMatch = skuText.match(/制造商型号[：:]\s*([^，,]+)/);

      let price = 0;
      if (i < skuPrices.length) {
        const priceText = text(skuPrices[i]);
        const pMatch = priceText.match(/[¥￥]?\s*([\d.]+)\s*\/\s*(\S+)/);
        if (pMatch) {
          price = parseFloat(pMatch[1]) || 0;
        }
      }

      const skuCode = skuMatch ? skuMatch[1] : '';
      const model = modelMatch ? modelMatch[1].trim() : '';

      if (skuCode || model) {
        variants.push({
          sku_code: skuCode || '',
          model: model || '',
          price: price,
        });
      }
    });

    return variants;
  }

  function extractMainImages(doc, html) {
    const seen = new Set();
    const images = [];

    // 策略1: 从 gallery 容器提取 base64 内嵌图片（SingleFile 保存）
    const gallerySelectors = [
      '.gallery-wrap img',
      '.img-wrap img',
      '.gallery-slick-box img',
      '.img-zoom-base-wrap img',
      '.detail-gallery img',
      '.product-gallery img',
      '[class*="gallery"] img',
      '.swiper-slide img',
    ];

    for (const sel of gallerySelectors) {
      doc.querySelectorAll(sel).forEach(img => {
        let src = attr(img, 'src') || '';
        const dataSrc = attr(img, 'data-sf-original-src') || attr(img, 'data-src') || '';
        const cleanSrc = src.split('?')[0];

        // base64 图直接添加
        if (src.startsWith('data:image/') && !src.startsWith('data:image/svg')) {
          if (!seen.has(src)) {
            seen.add(src);
            images.push(src);
          }
        }

        // CDN URL 优先从 data-sf-original-src 取
        const cdnUrl = dataSrc || cleanSrc;
        if (cdnUrl && cdnUrl.startsWith('http') && !seen.has(cdnUrl) && !cdnUrl.startsWith('data:')) {
          seen.add(cdnUrl);
          images.push(cdnUrl);
        }
      });
    }

    // 策略2: 从 data-sf-original-src 属性提取 CDN URL（全文档扫描）
    if (images.filter(u => u.startsWith('http')).length === 0) {
      const re = /data-sf-original-src="(https?:\/\/[^"]+)"/g;
      let m;
      while ((m = re.exec(html)) !== null) {
        const url = m[1].split('?')[0];
        if (url.startsWith('http') && !seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    // 策略3: 兜底 — CSS 注释中的 CDN URL
    if (images.filter(u => u.startsWith('http')).length === 0) {
      const re = /\/\*\s*original URL:\s*(https?:\/\/private\.zkh\.com\/PRODUCT\/BIG\/[^\s*]+)\s*\*\//g;
      let m;
      while ((m = re.exec(html)) !== null) {
        const url = m[1].split('?')[0];
        if (!seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    // 策略4: 从纯文本提取 BIG_ 文件名并构造 CDN URL
    if (images.filter(u => u.startsWith('http')).length === 0) {
      const pid = extractProductId(html);
      const re = /BIG_([A-Z0-9]+_\d+\.\w+)/g;
      let m;
      while ((m = re.exec(html)) !== null) {
        const filename = m[0];
        if (!pid || filename.includes(pid)) {
          const cdnUrl = `https://private.zkh.com/PRODUCT/BIG/${filename}`;
          if (!seen.has(cdnUrl)) {
            seen.add(cdnUrl);
            images.push(cdnUrl);
          }
        }
      }
    }

    return images.slice(0, 20);
  }

  function extractDeliveryInfo(doc) {
    const el = doc.querySelector('.sku-stock-wrap, [class*="sku-stock"]');
    return el ? text(el) : '';
  }

  function extractShipFrom(doc, html) {
    const cityEl = doc.querySelector('#detailCity, .zkh-code, [class*="city"]');
    if (cityEl) {
      const t = text(cityEl);
      const provinces = ['北京', '上海', '天津', '重庆', '河北', '山西', '内蒙古',
        '辽宁', '吉林', '黑龙江', '江苏', '浙江', '安徽', '福建',
        '江西', '山东', '河南', '湖北', '湖南', '广东', '广西',
        '海南', '四川', '贵州', '云南', '西藏', '陕西', '甘肃',
        '青海', '宁夏', '新疆'];
      for (const p of provinces) {
        if (t.includes(p)) return p;
      }
    }

    // 从文本中找
    const m = html.match(/发货地[：:]\s*(\S+)/);
    return m ? m[1].trim() : '';
  }

  function extractTags(html) {
    const tags = [];
    if (html.includes('行家精选')) tags.push('行家精选');
    if (html.includes('行家甄选')) tags.push('行家甄选');
    if (html.includes('热销')) tags.push('热销');
    if (html.includes('新品')) tags.push('新品');
    return tags;
  }

  function extractMinOrder(html) {
    const m = html.match(/起批[量\s]*(\d+)/);
    return m ? parseInt(m[1], 10) : 1;
  }

  function extractDescription(doc, html) {
    const el = doc.querySelector('.product-introduce-wrap, #product-introduce-wrap, .detail-area-wrap');
    if (el) return text(el).substring(0, 2000);

    // 兜底
    const m = html.match(/<div[^>]*class="product-introduce-wrap"[^>]*>([\s\S]*?)<\/div>/);
    return m ? m[1].replace(/<[^>]+>/g, '').trim().substring(0, 2000) : '';
  }

  // ── 统一输出 ──

  function toSearchRows(results) {
    return results.map(p => ({
      '标题': p.title || '',
      '价格': p.price || 0,
      '品牌': p.brand || '',
      '型号': p.model || '',
      '单位': p.unit || '',
      '链接': p.link || '',
      '图片': p.image || '',
      '商品ID': p.product_id || '',
      '标签': (p.tags || []).join(', '),
    }));
  }

  function toDetailRows(results) {
    const rows = [];
    for (const d of results) {
      const row = {
        '商品ID': d.product_id || '',
        '订货编码': d.sku_code || '',
        '标题': d.title || '',
        '品牌': d.brand || '',
        '型号': d.model || '',
        '价格': d.price_min || 0,
        '库存': d.stock_status || '',
        '发货地': d.ship_from || '',
        '起批量': d.min_order || 1,
        '属性数': Object.keys(d.attributes || {}).length,
        'SKU数': d.sku_count || 0,
        '主图数': (d.main_images || []).length,
        '标签': (d.tags || []).join(', '),
        '配送信息': d.delivery_info || '',
      };
      rows.push(row);
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
