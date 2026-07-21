/**
 * PageHarvest 核心解析调度器
 *
 * 功能:
 *   1. 平台检测
 *   2. ZIP 解压 + 解析调度
 *   3. CSV / JSON / XLSX / TXT 生成
 *
 * 依赖: AlibabaParser (parsers/alibaba.js), ZKHParser (parsers/zkh.js), JDParser (parsers/jingdong.js), JSZip, XLSX
 */

'use strict';

const PageHarvestParser = (() => {

  // ── 平台检测 ──

  function detectPlatform(html) {
    if (AlibabaParser.detect(html)) return 'alibaba';
    if (ZKHParser.detect(html)) return 'zkh';
    if (JDParser.detect(html)) return 'jingdong';
    return 'unknown';
  }

  // ── ZIP 快速扫描（提前检测平台，不等全量解析） ──

  async function quickScan(zipFile) {
    if (!window.JSZip) {
      throw new Error('JSZip 库未加载');
    }

    const zip = await JSZip.loadAsync(zipFile);

    // 找第一个 HTML 文件
    let firstHtml = null;
    let totalHtml = 0;
    zip.forEach((relativePath, entry) => {
      if (!entry.dir && /\.html?$/i.test(relativePath)) {
        totalHtml++;
        if (!firstHtml) firstHtml = { path: relativePath, entry };
      }
    });

    if (!firstHtml) {
      return { platform: 'unknown', totalHtml: 0, totalFiles: Object.keys(zip.files).length };
    }

    const content = await firstHtml.entry.async('string');
    const platform = detectPlatform(content);

    return {
      platform,
      totalHtml,
      totalFiles: Object.keys(zip.files).length,
      sampleFile: firstHtml.path,
    };
  }

  // ── ZIP 解析 ──

  async function parseZip(zipFile, mode) {
    if (!window.JSZip) {
      throw new Error('JSZip 库未加载');
    }

    // 1. 读 ZIP
    const zip = await JSZip.loadAsync(zipFile);

    // 2. 筛选 HTML 文件
    const htmlFiles = [];
    zip.forEach((relativePath, entry) => {
      if (!entry.dir && /\.html?$/i.test(relativePath)) {
        htmlFiles.push({ path: relativePath, entry });
      }
    });

    if (htmlFiles.length === 0) {
      throw new Error('ZIP 中未找到 HTML 文件');
    }

    // 3. 解析每个 HTML
    const results = [];
    for (const { path, entry } of htmlFiles) {
      const content = await entry.async('string');
      const platform = detectPlatform(content);

      let parsedData = null;
      if (platform === 'alibaba') {
        if (mode === 'search') {
          parsedData = AlibabaParser.parseSearch(content);
        } else if (mode === 'detail') {
          const detail = AlibabaParser.parseDetail(content);
          if (detail && detail.title) {
            parsedData = detail;
          }
        }
      } else if (platform === 'zkh') {
        if (mode === 'search') {
          parsedData = ZKHParser.parseSearch(content);
        } else if (mode === 'detail') {
          const detail = ZKHParser.parseDetail(content);
          if (detail && detail.title) {
            parsedData = detail;
          }
        }
      } else if (platform === 'jingdong') {
        if (mode === 'search') {
          parsedData = JDParser.parseSearch(content);
        } else if (mode === 'detail') {
          const detail = JDParser.parseDetail(content);
          if (detail && detail.title) {
            parsedData = detail;
          }
        }
      }

      results.push({
        file: path,
        platform,
        status: parsedData ? 'success' : 'failed',
        data: parsedData,
      });
    }

    // 4. 生成输出
    const platformSet = new Set(results.map(r => r.platform));
    const successCount = results.filter(r => r.status === 'success').length;

    const output = {
      results,
      platform: platformSet.size === 1 ? [...platformSet][0] : 'mixed',
      total: results.length,
      success: successCount,
      failed: results.length - successCount,
    };

    // 5. 生成报告文本
    if (mode === 'search') {
      const allRows = [];
      for (const r of results) {
        if (r.data && Array.isArray(r.data)) {
          const toRows = (r.platform === 'zkh') ? ZKHParser.toSearchRows :
                          (r.platform === 'jingdong') ? JDParser.toSearchRows : AlibabaParser.toSearchRows;
          allRows.push(...toRows(r.data));
        }
      }
      output.rows = allRows;
      output.csv = generateCSV(allRows);
      output.json = JSON.stringify(results, null, 2);
      output.txt = generateSearchTXT(results);
    } else if (mode === 'detail') {
      const alibabaDetails = [];
      const zkhDetails = [];
      const jdDetails = [];
      for (const r of results) {
        if (r.data && r.data.title) {
          if (r.platform === 'zkh') {
            zkhDetails.push(r.data);
          } else if (r.platform === 'jingdong') {
            jdDetails.push(r.data);
          } else {
            alibabaDetails.push(r.data);
          }
        }
      }
      output.rows = [
        ...AlibabaParser.toDetailRows(alibabaDetails),
        ...ZKHParser.toDetailRows(zkhDetails),
        ...JDParser.toDetailRows(jdDetails),
      ];
      output.csv = generateCSV(output.rows);
      output.json = JSON.stringify(results, null, 2);
      output.txt = generateDetailTXT(results);
    }

    // 6. XLSX
    if (output.rows && output.rows.length > 0 && window.XLSX) {
      output.xlsx = generateXLSX(output.rows);
    }

    return output;
  }

  // ── CSV 生成 ──

  function escapeCSV(val) {
    if (val == null) return '';
    const s = String(val);
    if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function generateCSV(rows) {
    if (!rows || rows.length === 0) return '';

    const headers = Object.keys(rows[0]);
    const lines = [];

    // header
    lines.push(headers.map(h => escapeCSV(h)).join(','));

    // data
    for (const row of rows) {
      lines.push(headers.map(h => escapeCSV(row[h])).join(','));
    }

    return '\uFEFF' + lines.join('\n'); // BOM for Excel
  }

  // ── JSON 生成 ──

  function generateJSON(results) {
    return JSON.stringify(results, null, 2);
  }

  // ── XLSX 生成 ──

  function generateXLSX(rows) {
    if (!window.XLSX) return null;

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '解析结果');

    // 自动列宽
    const cols = Object.keys(rows[0] || {});
    const colWidths = cols.map(col => {
      let maxLen = col.length;
      for (const row of rows) {
        const val = String(row[col] || '');
        // 取前几行估算
        maxLen = Math.max(maxLen, Math.min(val.length, 50));
      }
      return { wch: Math.min(maxLen + 2, 60) };
    });
  ws['!cols'] = colWidths;

    return XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
  }

  // ── TXT 报告生成 ──

  function generateTXT(results, mode) {
    if (mode === 'search') {
      return generateSearchTXT(results);
    }
    return generateDetailTXT(results);
  }

  function generateSearchTXT(results) {
    const lines = [];
    lines.push('PageHarvest 搜索页解析报告');
    lines.push('='.repeat(50));
    lines.push(`总文件: ${results.length}`);
    lines.push(`成功: ${results.filter(r => r.status === 'success').length}`);
    lines.push(`失败: ${results.filter(r => r.status === 'failed').length}`);
    lines.push('');

    for (const r of results) {
      const fileLabel = `[${r.file}]`;
      lines.push(fileLabel);
      lines.push('-'.repeat(fileLabel.length));

      if (r.status === 'failed') {
        lines.push('  ❌ 解析失败');
        lines.push('');
        continue;
      }

      if (Array.isArray(r.data)) {
        for (const item of r.data) {
          lines.push(`  ${item.title || '?'}`);
          lines.push(`    价格: ${item.price || '-'}`);
          lines.push(`    销量: ${item.sales || '-'}`);
          if (item.link) lines.push(`    链接: ${item.link}`);
          lines.push('');
        }
      }
    }

    return lines.join('\n');
  }

  function generateDetailTXT(results) {
    const lines = [];
    lines.push('PageHarvest 详情页解析报告');
    lines.push('='.repeat(50));
    const ok = results.filter(r => r.status === 'success');
    const fail = results.filter(r => r.status === 'failed');
    lines.push(`总文件: ${results.length}`);
    lines.push(`成功: ${ok.length}`);
    lines.push(`失败: ${fail.length}`);
    lines.push('');

    for (const r of ok) {
      const d = r.data;
      lines.push(`✅ ${d.brand || '-'}  ¥${d.price_min || 0}  ${d.sku_count || 0} SKU  ${Object.keys(d.attributes || {}).length} 属性  ${(d.main_images || []).length} 图`);
      lines.push(`   ${d.title || ''}`);
      lines.push('');
    }

    for (const r of fail) {
      lines.push(`❌ ${r.file} — 解析失败`);
    }

    return lines.join('\n');
  }

  // ── 工具函数 ──

  function getFilename(mode) {
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}`;
    return `PageHarvest_${mode}_${ts}`;
  }

  // ── 公共 API ──

  return {
    detectPlatform,
    quickScan,
    parseZip,
    generateCSV,
    generateJSON,
    generateXLSX,
    generateTXT,
    getFilename,
  };

})();
