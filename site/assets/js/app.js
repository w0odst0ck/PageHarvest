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
      if (files.length > 0) {
        const file = files[0];
        if (!file.name.endsWith('.zip')) {
          showError('请拖拽 ZIP 格式的文件，当前文件类型不是 ZIP');
          return;
        }
        if (file.size > 100 * 1024 * 1024) {
          showError('文件过大（超过 100MB），建议不超过 50MB');
          return;
        }
        handleFileSelect(file);
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
    // 文件校验
    if (!file) return;
    if (!file.name.endsWith('.zip') && !file.name.endsWith('.ZIP')) {
      showError('请选择 ZIP 格式的文件，选中的文件不是 ZIP 压缩包');
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      showError('文件过大（超过 100MB），建议不超过 50MB');
      return;
    }

    currentFile = file;
    updateParseButton();

    // 更新拖拽区文案
    const dropText = dropZone.querySelector('.drop-text');
    const dropHint = dropZone.querySelector('.drop-hint');
    if (dropText) dropText.textContent = `📦 ${file.name}`;
    if (dropHint) dropHint.textContent = `(${(file.size / 1024).toFixed(1)} KB) 点击重新选择`;

    // 选中反馈：拖拽区闪烁提示
    dropZone.classList.remove('file-selected');
    void dropZone.offsetWidth; // 强制重排触发动画重播
    dropZone.classList.add('file-selected');

    hideError();
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
    if (!currentFile) {
      showError('请先选择一个 ZIP 文件');
      return;
    }

    const mode = modeSelect ? modeSelect.value : 'search';

    // 重置 UI
    hideError();
    hideElement(resultsArea);
    showElement(progressArea);
    setProgress(0, '准备就绪...');
    parseBtn.disabled = true;

    try {
      setProgress(5, '正在加载 JSZip...');

      // 确保 JSZip 已加载
      if (!window.JSZip) {
        // 尝试动态加载
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js');
        if (!window.JSZip) {
          showError('JSZip 库加载失败，请刷新页面后重试');
          return;
        }
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

      setProgress(15, '正在解压 ZIP 文件...');

      // 快速扫描：提前检测平台和文件数量
      setProgress(20, '正在检测页面平台...');
      const scan = await PageHarvestParser.quickScan(currentFile);

      // 防御：quickScan 异常返回
      if (!scan) {
        showError('扫描 ZIP 文件失败，文件格式可能不正确，请确认后重试');
        return;
      }

      if (scan.totalHtml === 0) {
        const fileCount = scan.totalFiles != null ? scan.totalFiles + ' 个文件，但' : '';
        showError('ZIP 中没有找到 HTML 文件' + (fileCount ? '，该压缩包包含 ' + fileCount : '') + '没有 .html 网页文件。请确认压缩包内包含网页截图');
        return;
      }

      if (scan.platform === 'unknown') {
        showError('无法识别页面平台，目前支持 1688、震坤行和京东。请确认 ZIP 中包含对应平台的 HTML 文件（扫描样本: ' + scan.sampleFile + '）');
        return;
      }

      setProgress(25, '检测到 ' + scan.totalHtml + ' 个 HTML 文件，平台: ' + (scan.platform === 'alibaba' ? '1688' : (scan.platform === 'zkh' ? '震坤行' : '京东')) + '，开始解析...');

      // 执行解析
      const output = await PageHarvestParser.parseZip(currentFile, mode);
      currentOutput = output;

      // 检查解析结果
      if (output.total === 0) {
        showError('未能提取到商品数据，ZIP 中可能不包含支持的页面内容，请确认后重试');
        return;
      }

      // 检查平台识别情况
      if (output.platform === 'unknown') {
        showError('无法识别页面平台，目前支持 1688、震坤行和京东。请确认 ZIP 中包含对应平台的 HTML 文件');
        return;
      }

      // 检查数据是否为空
      if (!output.rows || output.rows.length === 0) {
        showError('未能提取到商品数据，请确认 HTML 内容完整包含商品信息');
        return;
      }

      setProgress(80, `解析完成: ${output.success}/${output.total} 成功`);

      // 渲染结果
      renderResults(output, mode);

      setProgress(100, '解析完成 ✓');
      await sleep(500);
      hideElement(progressArea);

    } catch (err) {
      console.error('解析失败:', err);
      const msg = err.message || '';
      if (msg.includes('JSZip') || msg.includes('loadAsync') || msg.includes('corrupt') || msg.includes('invalid')) {
        showError('ZIP 文件无法打开，可能已损坏。请重新保存 HTML 后打包再试');
      } else {
        showError(msg || '解析过程中发生未知错误，请重试');
      }
      hideElement(progressArea);
    } finally {
      parseBtn.disabled = false;
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
      showError('解析成功但没有提取到任何数据。请确认 ZIP 中包含正确的 1688、震坤行或京东 HTML 文件。');
      return;
    }

    // 摘要
    const summaryParts = [];
    summaryParts.push(`📊 共解析 ${output.total} 个文件`);
    summaryParts.push(`✅ ${output.success} 个成功`);
    if (output.failed > 0) summaryParts.push(`❌ ${output.failed} 个失败`);
    summaryParts.push(`📋 ${output.rows.length} 条数据记录`);
    resultSummary.textContent = summaryParts.join(' | ');

    // 失败文件明细
    renderFailedFiles(output.results);

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

    // 判断哪些列是图片列
    const imageKeys = ['图片', '主图链接', '主图', 'images', 'main_images', 'mainImages'];

    // Tbody
    resultTbody.innerHTML = '';
    for (const row of rows) {
      const tr = document.createElement('tr');
      for (const h of headers) {
        const td = document.createElement('td');
        const val = row[h];

        // 图片列 — 渲染为可点击的缩略图链接
        if (imageKeys.includes(h) && val) {
          let urls = [];
          if (typeof val === 'string') {
            urls = val.split(/\n|,\s*/).filter(Boolean);
          } else if (Array.isArray(val)) {
            urls = val;
          }
          if (urls.length > 0) {
            // 安全构建链接（防止 javascript: XSS）
            const container = document.createDocumentFragment();
            urls.forEach((url, i) => {
              if (i > 0) container.appendChild(document.createTextNode(' '));
              const a = document.createElement('a');
              a.href = url;
              a.target = '_blank';
              a.title = url;
              a.className = 'img-link';
              a.textContent = '图' + (i + 1);
              container.appendChild(a);
            });
            td.appendChild(container);
          } else {
            td.textContent = '-';
          }
        }
        // 长文本截断显示
        else if (typeof val === 'string' && val.length > 100) {
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

  // ── 失败文件明细 ──

  function renderFailedFiles(results) {
    const failedFilesEl = document.getElementById('failedFiles');
    const failedFilesList = document.getElementById('failedFilesList');
    if (!failedFilesEl || !failedFilesList) return;

    const failed = results.filter(r => r.status === 'failed');
    if (failed.length === 0) {
      hideElement(failedFilesEl);
      return;
    }

    showElement(failedFilesEl);
    failedFilesList.innerHTML = '';
    for (const r of failed) {
      const li = document.createElement('li');
      const reason = r.platform === 'unknown'
        ? '未识别的平台'
        : '未提取到商品数据';
      li.textContent = r.file + ' — ' + reason;
      failedFilesList.appendChild(li);
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
    if (!currentOutput) {
      showError('请先完成解析再下载报告');
      return;
    }

    try {
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
            showError('Excel 生成失败（缺少 xlsx 库），请尝试 CSV 格式');
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

    } catch (err) {
      console.error('下载失败:', err);
      showError('报告生成失败，请重试');
    }
  }

  // ── 错误显示 ──

  function showError(msg) {
    if (errorText) errorText.textContent = msg;
    showElement(errorArea);
    hideElement(resultsArea);
    hideElement(progressArea);
    parseBtn.disabled = false;
    updateParseButton();
  }

  function hideError() {
    hideElement(errorArea);
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
