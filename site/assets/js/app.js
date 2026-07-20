/**
 * PageHarvest 在线解析 — UI 交互逻辑
 *
 * 功能:
 *   1. 拖拽上传 / 点击选择 ZIP 文件
 *   2. 读 ZIP → JSZip → 解析
 *   3. 进度显示
 *   4. 结果表格渲染
 *   5. 下载 CSV / Excel / TXT / JSON
 */

'use strict';

(function() {

  // ── DOM 引用 ──
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const modeSelect = document.getElementById('modeSelect');
  const parseBtn = document.getElementById('parseBtn');
  const progressArea = document.getElementById('progressArea');
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  const resultsArea = document.getElementById('resultsArea');
  const resultSummary = document.getElementById('resultSummary');
  const resultThead = document.getElementById('resultThead');
  const resultTbody = document.getElementById('resultTbody');
  const downloadCsvBtn = document.getElementById('downloadCsvBtn');
  const downloadXlsxBtn = document.getElementById('downloadXlsxBtn');
  const downloadTxtBtn = document.getElementById('downloadTxtBtn');
  const downloadJsonBtn = document.getElementById('downloadJsonBtn');
  const errorArea = document.getElementById('errorArea');
  const errorText = document.getElementById('errorText');

  // ── 状态 ──
  let currentFile = null;       // 当前选择的 ZIP File
  let currentOutput = null;     // 最近一次解析输出

  // ── 初始化 ──
  function init() {
    setupDragDrop();
    setupFileInput();
    setupParseButton();
    setupDownloadButtons();

    // 初始状态
    updateParseButton();
    hideElement(progressArea);
    hideElement(resultsArea);
    hideElement(errorArea);
  }

  // ── 显示/隐藏 ──
  function showElement(el) {
    if (el) el.hidden = false;
  }

  function hideElement(el) {
    if (el) el.hidden = true;
  }

  // ── 拖拽上传 ──

  function setupDragDrop() {
    if (!dropZone) return;

    // 点击触发文件选择
    dropZone.addEventListener('click', () => {
      if (fileInput) fileInput.click();
    });

    // 拖拽事件
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');

      const files = e.dataTransfer.files;
      if (files.length > 0 && files[0].name.endsWith('.zip')) {
        handleFileSelect(files[0]);
      } else {
        showError('请拖拽一个 ZIP 文件');
      }
    });
  }

  // ── 文件输入 ──

  function setupFileInput() {
    if (!fileInput) return;

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });
  }

  function handleFileSelect(file) {
    currentFile = file;
    updateParseButton();

    // 更新拖拽区文案
    const dropText = dropZone.querySelector('.drop-text');
    const dropHint = dropZone.querySelector('.drop-hint');
    if (dropText) dropText.textContent = `📦 ${file.name}`;
    if (dropHint) dropHint.textContent = `(${(file.size / 1024).toFixed(1)} KB) 点击重新选择`;

    hideElement(errorArea);
    hideElement(resultsArea);
  }

  // ── 解析按钮 ──

  function setupParseButton() {
    if (!parseBtn) return;
    parseBtn.addEventListener('click', startParsing);
  }

  function updateParseButton() {
    if (!parseBtn) return;
    parseBtn.disabled = !currentFile;
  }

  // ── 开始解析 ──

  async function startParsing() {
    if (!currentFile) return;

    const mode = modeSelect ? modeSelect.value : 'search';

    // 重置 UI
    hideElement(errorArea);
    hideElement(resultsArea);
    showElement(progressArea);
    setProgress(0, '准备就绪...');
    parseBtn.disabled = true;

    try {
      setProgress(10, '正在加载 JSZip...');

      // 确保 JSZip 已加载
      if (!window.JSZip) {
        // 尝试动态加载
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js');
        if (!window.JSZip) throw new Error('JSZip 加载失败，请刷新页面重试');
      }

      // 确保 XLSX 已加载 (用于 Excel)
      if (!window.XLSX) {
        try {
          await loadScript('https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js');
        } catch (e) {
          // XLSX 加载失败不影响 CSV/TXT/JSON 下载
          console.warn('XLSX not loaded, Excel download unavailable');
        }
      }

      setProgress(20, '正在解压 ZIP 文件...');

      // 执行解析
      const output = await PageHarvestParser.parseZip(currentFile, mode);
      currentOutput = output;

      setProgress(70, `解析完成: ${output.success}/${output.total} 成功`);

      // 渲染结果
      renderResults(output, mode);

      setProgress(100, '解析完成 ✓');
      await sleep(500);
      hideElement(progressArea);

    } catch (err) {
      console.error('解析失败:', err);
      showError(err.message || '解析过程中发生未知错误');
      hideElement(progressArea);
    } finally {
      parseBtn.disabled = false;
      updateParseButton();
    }
  }

  // ── 进度条 ──

  function setProgress(percent, text) {
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = text;
  }

  // ── 渲染结果 ──

  function renderResults(output, mode) {
    if (!output.rows || output.rows.length === 0) {
      showError('解析成功但没有提取到任何数据。请确认 ZIP 中包含正确的 1688 HTML 文件。');
      return;
    }

    // 摘要
    const summaryParts = [];
    summaryParts.push(`📊 共解析 ${output.total} 个文件`);
    summaryParts.push(`✅ ${output.success} 个成功`);
    if (output.failed > 0) summaryParts.push(`❌ ${output.failed} 个失败`);
    summaryParts.push(`📋 ${output.rows.length} 条数据记录`);
    resultSummary.textContent = summaryParts.join(' | ');

    // 表格
    const headers = Object.keys(output.rows[0]);
    renderTable(headers, output.rows);

    // 显示结果区
    showElement(resultsArea);
  }

  function renderTable(headers, rows) {
    if (!resultThead || !resultTbody) return;

    // Thead
    resultThead.innerHTML = '';
    const tr = document.createElement('tr');
    for (const h of headers) {
      const th = document.createElement('th');
      th.textContent = h;
      tr.appendChild(th);
    }
    resultThead.appendChild(tr);

    // Tbody
    resultTbody.innerHTML = '';
    for (const row of rows) {
      const tr = document.createElement('tr');
      for (const h of headers) {
        const td = document.createElement('td');
        const val = row[h];
        // 长文本截断显示
        if (typeof val === 'string' && val.length > 100) {
          td.textContent = val.substring(0, 100) + '...';
          td.title = val;
        } else {
          td.textContent = val != null ? val : '';
        }
        tr.appendChild(td);
      }
      resultTbody.appendChild(tr);
    }
  }

  // ── 下载按钮 ──

  function setupDownloadButtons() {
    if (downloadCsvBtn) downloadCsvBtn.addEventListener('click', () => download('csv'));
    if (downloadXlsxBtn) downloadXlsxBtn.addEventListener('click', () => download('xlsx'));
    if (downloadTxtBtn) downloadTxtBtn.addEventListener('click', () => download('txt'));
    if (downloadJsonBtn) downloadJsonBtn.addEventListener('click', () => download('json'));
  }

  function download(format) {
    if (!currentOutput) return;

    const mode = modeSelect ? modeSelect.value : 'search';
    const baseName = PageHarvestParser.getFilename(mode);

    let blob, filename;

    switch (format) {
      case 'csv': {
        const content = PageHarvestParser.generateCSV(currentOutput.rows || []);
        blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        filename = `${baseName}.csv`;
        break;
      }
      case 'xlsx': {
        if (!currentOutput.xlsx) {
          // 尝试用 XLSX 生成（如果之前没成功）
          if (window.XLSX && currentOutput.rows) {
            currentOutput.xlsx = PageHarvestParser.generateXLSX(currentOutput.rows);
          }
        }
        if (currentOutput.xlsx) {
          blob = new Blob([new Uint8Array(currentOutput.xlsx)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
          filename = `${baseName}.xlsx`;
        } else {
          showError('Excel 生成失败（缺少 xlsx 库）');
          return;
        }
        break;
      }
      case 'txt': {
        const content = PageHarvestParser.generateTXT(currentOutput.results || [], mode);
        blob = new Blob([content], { type: 'text/plain;charset=utf-8;' });
        filename = `${baseName}.txt`;
        break;
      }
      case 'json': {
        const content = currentOutput.json || JSON.stringify(currentOutput.results, null, 2);
        blob = new Blob([content], { type: 'application/json;charset=utf-8;' });
        filename = `${baseName}.json`;
        break;
      }
      default:
        return;
    }

    // 触发下载
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── 错误显示 ──

  function showError(msg) {
    if (errorText) errorText.textContent = msg;
    showElement(errorArea);
    hideElement(resultsArea);
    hideElement(progressArea);
  }

  // ── 工具函数 ──

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`加载脚本失败: ${url}`));
      document.head.appendChild(script);
    });
  }

  // ── 启动 ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
