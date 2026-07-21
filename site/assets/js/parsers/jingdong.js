/**
 * 京东 (jd.com) 详情页解析器
 *
 * 纯 DOM 解析，不加载外部资源。
 * 兼容浏览器保存的 SingleFile / 完整页面。
 *
 * DOM 选择器源于 Python 解析器 (src/platforms/jingdong/) 的实际页面结构，
 * 适配新版（React 2025+）和旧版页面。
 *
 * 搜索页: 简易抽取商品列表卡片
 * 详情页: 商品ID / 标题 / 品牌 / 价格 / 店铺 / 主图 / 属性 / 销量
 */

'use strict';

const JDParser = (() => {

  // ══════════════════════════════════════════════════════════
  //  平台检测
  // ══════════════════════════════════════════════════════════

  /**
   * 是否为京东页面（详情页或搜索页）
   */
  function detect(html) {
    // URL 模式
    if (/item\.jd\.com\/(\d+)/.test(html)) return true;
    if (/search\.jd\.com\/Search/.test(html)) return true;

    // DOM 特征（独立于 URL）
    if (html.includes('jd.com') && (
      html.includes('sku-name') ||
      html.includes('summary-price') ||
      html.includes('pageConfig') ||
      html.includes('parameter2 p-parameter-list') ||
      html.includes('choose-attr-') ||
      html.includes('goods-item-wrap-new')
    )) return true;

    // 无 jd.com 时的兜底检测（离线保存的页面可能无源 URL）
    if (html.includes('pageConfig') && html.includes('"sku"') && html.includes('"product"')) return true;
    if (html.includes('sku-name') && (html.includes('p-price') || html.includes('summary-price'))) return true;
    if (html.includes('parameter2 p-parameter-list') && html.includes('itemInfo-wrap')) return true;

    return false;
  }

  function isDetailPage(html) {
    // 详情页特征
    if (/item\.jd\.com\/(\d+)/.test(html)) return true;
    if (html.includes('.sku-name')) return true;
    if (html.includes('summary-price') && html.includes('choose-attr-')) return true;
    if (html.includes('parameter2 p-parameter-list') && html.includes('itemInfo-wrap')) return true;
    // 新版 JD (React)
    if (/class="?attrs[\s>]/.test(html) && /class="?top-name[\s>]/.test(html)) return true;
    // 排除搜索页
    if (/search\.jd\.com\/Search/.test(html)) return false;
    if (html.includes('plugin_goodsCardWrapper')) return false;
    return false;
  }

  function isSearchPage(html) {
    if (/search\.jd\.com\/Search/.test(html)) return true;
    if (html.includes('plugin_goodsCardWrapper') || html.includes('search-discover')) return true;
    return false;
  }

  // ══════════════════════════════════════════════════════════
  //  详情页解析
  // ══════════════════════════════════════════════════════════

  function parseDetail(html) {
    const detail = {
      product_id: '',
      title: '',
      brand: '',
      model: '',
      price_min: 0,
      price_max: 0,
      shop_name: '',
      shop_type: '',
      main_images: [],
      attributes: {},
      sales_count: '',
      rating: '',
      tags: [],
    };

    // ── 1. product_id ──
    detail.product_id = extractProductId(html);

    // ── 2. title ──
    detail.title = extractTitle(html);

    // ── 3. brand ──
    detail.brand = extractBrand(html, detail);

    // ── 4. price ──
    const prices = extractPrice(html);
    detail.price_min = prices.min;
    detail.price_max = prices.max;

    // ── 5. shop ──
    const shop = extractShop(html);
    detail.shop_name = shop.name;
    detail.shop_type = shop.type;

    // ── 6. main_images ──
    detail.main_images = extractImages(html);

    // ── 7. attributes ──
    const attrs = extractAttributes(html);
    detail.attributes = attrs;

    // 从属性表补充品牌和型号
    if (!detail.brand && attrs['品牌']) detail.brand = attrs['品牌'];
    if (!detail.model && attrs['商品编号']) detail.model = attrs['商品编号'];
    if (!detail.product_id && attrs['商品编号']) detail.product_id = attrs['商品编号'];

    // 新版高亮属性
    const hlAttrs = extractHighlightAttrs(html);
    Object.assign(detail.attributes, hlAttrs);

    // ── 8. sales / rating ──
    detail.sales_count = extractSales(html);
    detail.rating = extractRating(html);

    // ── 9. tags ──
    detail.tags = extractTags(html);

    return detail;
  }

  // ══════════════════════════════════════════════════════════
  //  搜索页简易解析
  // ══════════════════════════════════════════════════════════

  function parseSearch(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const items = [];

    // 搜索页商品卡片选择器（多版本兼容）
    const cards = doc.querySelectorAll(
      '.gl-item, [class*="goods-item"], .search_result_item, [class*="product-item"]'
    );

    for (const card of cards) {
      const p = {};

      // 标题
      const titleEl = card.querySelector('.p-name a, [class*="title"] a, .goods-name a');
      p.title = titleEl ? titleEl.textContent.trim() : '';

      // 价格
      const priceEl = card.querySelector('.p-price, .jd-price, [class*="price"]');
      if (priceEl) {
        const text = priceEl.textContent.trim();
        const nums = text.match(/[\d.]+/g);
        if (nums && nums.length > 0) {
          p.price_min = parseFloat(nums[0]) || 0;
          p.price_max = nums.length > 1 ? parseFloat(nums[1]) : p.price_min;
        }
      } else {
        p.price_min = 0;
        p.price_max = 0;
      }

      // 链接
      const linkEl = card.querySelector('.p-name a, a[href*="item.jd.com"]');
      p.link = linkEl ? linkEl.getAttribute('href') || '' : '';
      if (p.link && !p.link.startsWith('http')) {
        p.link = 'https:' + p.link;
      }

      // 图片
      const imgEl = card.querySelector('.p-img img, [class*="img"] img, .goods-img img');
      if (imgEl) {
        p.image = imgEl.getAttribute('data-sf-original-src') ||
                  imgEl.getAttribute('data-lazy-img') ||
                  imgEl.getAttribute('src') || '';
        if (p.image && !p.image.startsWith('http')) {
          p.image = 'https:' + p.image;
        }
      } else {
        p.image = '';
      }

      // 店铺
      const shopEl = card.querySelector('.p-shop, .shop-name, [class*="shop"]');
      p.shop_name = shopEl ? shopEl.textContent.trim() : '';

      // 评价数
      const commitEl = card.querySelector('.p-commit, .comment, [class*="commit"]');
      p.sales = commitEl ? commitEl.textContent.trim() : '';

      // 商品ID
      p.product_id = '';
      if (p.link) {
        const m = p.link.match(/item\.jd\.com\/(\d+)/);
        if (m) p.product_id = m[1];
      }

      if (p.title) items.push(p);
    }

    return items;
  }

  // ══════════════════════════════════════════════════════════
  //  表格行转换
  // ══════════════════════════════════════════════════════════

  function toSearchRows(results) {
    return results.map(p => ({
      '标题': p.title || '',
      '价格': p.price_min || 0,
      '链接': p.link || '',
      '图片': p.image || '',
      '店铺': p.shop_name || '',
      '评价': p.sales || '',
      '商品ID': p.product_id || '',
    }));
  }

  function toDetailRows(results) {
    return results.map(d => ({
      '商品ID': d.product_id || '',
      '标题': d.title || '',
      '品牌': d.brand || '',
      '型号': d.model || '',
      '最低价': d.price_min || 0,
      '最高价': d.price_max || 0,
      '店铺': d.shop_name || '',
      '店铺类型': d.shop_type || '',
      '属性数': Object.keys(d.attributes || {}).length || 0,
      '主图数': (d.main_images || []).length || 0,
      '已售': d.sales_count || '',
      '好评率': d.rating || '',
      '标签': (d.tags || []).join(', '),
    }));
  }

  // ══════════════════════════════════════════════════════════
  //  字段提取函数
  // ══════════════════════════════════════════════════════════

  function extractProductId(html) {
    // window.pageConfig
    let m = html.match(/window\.pageConfig\s*=\s*({.*?"product"\s*:\s*{.*?});/);
    if (m) {
      try {
        const config = JSON.parse(m[1]);
        if (config.product && config.product.sku) return config.product.sku;
      } catch (e) { /* ignore */ }
    }
    // "sku":"12345"
    m = html.match(/"sku"\s*:\s*"(\d+)"/);
    if (m) return m[1];
    // item.jd.com/12345
    m = html.match(/item\.jd\.com\/(\d+)/);
    if (m) return m[1];
    return '';
  }

  function extractTitle(html) {
    // pageConfig
    let m = html.match(/window\.pageConfig\s*=\s*({.*?"product"\s*:\s*{.*?});/);
    if (m) {
      try {
        const config = JSON.parse(m[1]);
        if (config.product && config.product.name) {
          return config.product.name.trim();
        }
      } catch (e) { /* ignore */ }
    }
    // .sku-name
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const skuName = doc.querySelector('.sku-name');
    if (skuName) return skuName.textContent.trim();
    // <title> 标签
    m = html.match(/<title>([^<]+)<\/title>/);
    if (m) {
      let title = m[1].trim();
      title = title.replace(/\s*【行情 报价 价格 评测】.*/, '');
      title = title.replace(/\s*[-–—]\s*京东$/, '');
      return title.trim();
    }
    return '';
  }

  function extractBrand(html, detail) {
    // 参数表
    const attrs = extractAttributes(html);
    if (attrs['品牌']) return attrs['品牌'];
    // 标题关键词
    const title = detail.title || '';
    const knownBrands = [
      '松下', 'Panasonic', '雷士', 'NVC', '欧普', 'OPPLE',
      '佛山照明', 'FSL', '飞利浦', 'Philips', '小米', '米家',
      '美的', 'Midea', '公牛', 'Honeywell', '霍尼韦尔',
    ];
    for (const brand of knownBrands) {
      if (title.includes(brand)) return brand;
    }
    return '';
  }

  function extractPrice(html) {
    let min = 0, max = 0;

    // 新版: <div class=price><div class=value>79</div></div>
    let m = html.match(/class="?price[^>"]*[\s>][\s\S]*?class="?value[^>"]*[\s>]([\d.]+)<\/div>/);
    if (m) {
      const v = parseFloat(m[1]);
      if (v > 0.01 && v < 100000) {
        min = v;
        return { min, max };
      }
    }

    // jdPrice JSON
    m = html.match(/"jdPrice"\s*:\s*"([\d.]+)"/);
    if (m) {
      min = parseFloat(m[1]);
      return { min, max };
    }

    // DOM 价格选择器
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    for (const sel of ['.summary-price .price', '.p-price .price', '.summary-wrap .p-price',
                       '.p-price', '[class*="price"]']) {
      const el = doc.querySelector(sel);
      if (el) {
        const text = el.textContent.trim();
        const prices = text.match(/[\d.]+/g);
        if (prices) {
          const floats = prices.map(parseFloat).filter(v => v > 0.01 && v < 100000);
          if (floats.length > 0) {
            min = Math.min(...floats);
            max = Math.max(...floats);
            return { min, max };
          }
        }
      }
    }

    // 正则全文兜底
    const allPrices = html.match(/¥?(\d+\.\d{2})/g);
    if (allPrices) {
      const floats = allPrices.map(s => parseFloat(s.replace('¥', '')))
        .filter(v => v > 0.1 && v < 100000);
      if (floats.length > 0) {
        min = Math.min(...floats);
        max = Math.max(...floats);
      }
    }

    return { min, max };
  }

  function extractShop(html) {
    let name = '';
    let type = '';

    // 新版: class="top-name"
    let m = html.match(/class="?top-name[^>"]*[\s>][^>]*title="?([^">]*)"?/);
    if (m) name = m[1].trim();

    // 旧版: .J-hove-wrap .name a
    if (!name) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      for (const sel of ['.J-hove-wrap .name a', '.shop .name a', '.shop-name a',
                         '.J-shop-name', '[class*="shop-name"]']) {
        const el = doc.querySelector(sel);
        if (el) {
          const t = el.textContent.trim();
          if (t && t.length > 1) {
            name = t;
            break;
          }
        }
      }
    }

    // 兜底: waist-shop-title
    if (!name) {
      m = html.match(/waist-shop-title[\s\S]*?class="?shop-name[^>"]*"?[^>]*>([^<]+)/);
      if (m) name = m[1].trim();
    }

    if (html.includes('自营')) type = '自营';
    else if (name.includes('旗舰店')) type = '旗舰店';
    else if (name.includes('专卖店')) type = '专卖店';
    else if (name.includes('专营店')) type = '专营店';
    else type = '第三方';

    return { name, type };
  }

  function extractImages(html) {
    const seen = new Set();
    const images = [];

    /**
     * 判断是否为京东商品图 CDN 路径（排除 UI 图标）
     */
    function isProductCdnUrl(url) {
      const m = url.match(/https?:\/\/img\d+\.360buyimg\.com(\/[^\s"'<>]+)/);
      if (!m) return false;
      const path = m[1];
      for (const prefix of ['/n1/', '/n0/', '/n5/', '/s1/', '/s0/', '/pcpubliccms/s1440x1440']) {
        if (path.startsWith(prefix)) {
          const fn = url.split('/').pop().toLowerCase();
          if (fn.includes('icon')) return false;
          return true;
        }
      }
      return false;
    }

    // 从 #spec-n1 提取
    const specN1Re = /<div[^>]*id="?spec-n1"?[^>]*>([\s\S]*?)<\/div>/i;
    const specMatch = html.match(specN1Re);
    if (specMatch) {
      const imgRe = /<img[^>]+(?:src|data-sf-original-src)="([^"]+)"[^>]*>/g;
      let m;
      while ((m = imgRe.exec(specMatch[1])) !== null) {
        const src = m[1];
        if (!seen.has(src)) {
          seen.add(src);
          images.push(src);
        }
      }
    }

    // 从全文提取 CDN URL
    if (images.length === 0) {
      const cdnRe = /https?:\/\/img\d+\.360buyimg\.com[^\s"'<>]+/g;
      let m;
      while ((m = cdnRe.exec(html)) !== null) {
        const url = m[0];
        if (isProductCdnUrl(url) && !seen.has(url)) {
          seen.add(url);
          images.push(url);
        }
      }
    }

    return images.slice(0, 10);
  }

  function extractAttributes(html) {
    const attrs = {};

    // 旧版: .parameter2.p-parameter-list li
    const oldRe = /<li[^>]*>([^<]*(?:品牌|型号|商品编号|材质|规格|尺寸|颜色|功率|电压|重量)[^<]*)<\/li>/gi;
    let m;
    while ((m = oldRe.exec(html)) !== null) {
      const text = m[1].trim();
      const parts = text.split(/[：:]/);
      if (parts.length === 2) {
        const key = parts[0].trim();
        const val = parts[1].trim();
        if (key && val && key.length < 20) attrs[key] = val;
      }
    }

    // 新版: <div class=attrs> <div class=item> <div class=label><span class=text>品牌</span> <div class=value><div class=text title="松下">松下</div>
    const newRe = /<div\s+class="?item[^>"]*[\s>][\s\S]*?<div\s+class="?label[^>"]*[\s>][\s\S]*?<span\s+class="?text[^>"]*[\s>]\s*([^<]+)\s*<\/span>[\s\S]*?<div\s+class="?value[^>"]*[\s>][\s\S]*?<div\s+class="?text[^>"]*[\s>]\s*title="?([^">]*)"?[^>]*>/g;
    while ((m = newRe.exec(html)) !== null) {
      const name = m[1].trim();
      const value = m[2].trim();
      if (name && value) attrs[name] = value;
    }

    return attrs;
  }

  function extractHighlightAttrs(html) {
    const attrs = {};
    const hlRe = /class="?highlight-attrs[^>"]*[\s>]([\s\S]*?)(?:class="?attrs[\s>]|$)/;
    const hlMatch = html.match(hlRe);
    if (!hlMatch) return attrs;

    const itemRe = /<div\s+class="?item[^>"]*[\s>][\s\S]*?<div\s+class="?title[^>"]*[\s>][^>]*title="?([^">]*)"?[^>]*>[\s\S]*?<div\s+class="?desc[^>"]*[\s>][\s\S]*?<div\s+class="?text[^>"]*[\s>][^>]*title="?([^">]*)"?[^>]*>/g;
    let m;
    while ((m = itemRe.exec(hlMatch[1])) !== null) {
      const value = m[1].trim();
      const name = m[2].trim();
      if (name && value) attrs[name] = value;
    }
    return attrs;
  }

  function extractSales(html) {
    let m = html.match(/累计评价[^\d]*([\d.万+]+)/);
    if (m) return m[1];
    m = html.match(/买家评价\((\d+万?\+?)\)/);
    if (m) return m[1];
    // DOM
    const selRe = /class="[^"]*(?:J-sale-data|sale-data|comment-count|sales-volume)[^"]*"[^>]*>([^<]+)/;
    m = html.match(selRe);
    if (m) {
      const text = m[1].trim();
      if (/[\d.万+]+/.test(text)) return text;
    }
    return '';
  }

  function extractRating(html) {
    let m = html.match(/超(\d+%)[^。]*赞/);
    if (m) return m[1];
    m = html.match(/class="[^"]*(?:good-rate|good-comment-percent|percent-con|comment-percent)[^"]*"[^>]*>([^<]+)/);
    if (m) {
      const rm = m[1].match(/(\d+%)/);
      if (rm) return rm[1];
    }
    return '';
  }

  function extractTags(html) {
    const tags = [];
    const keywords = ['自营', '百亿补贴', '政府补贴', '明日达',
                      '京东秒杀', '京东超市', '仅换不修', '包邮',
                      '品质认证', '放心购', '企业价'];
    for (const kw of keywords) {
      if (html.includes(kw) && !tags.includes(kw)) tags.push(kw);
    }
    return tags;
  }

  // ══════════════════════════════════════════════════════════
  //  公共 API
  // ══════════════════════════════════════════════════════════

  return {
    detect,
    isDetailPage,
    isSearchPage,
    parseDetail,
    parseSearch,
    toDetailRows,
    toSearchRows,
  };

})();
