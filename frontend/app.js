// Frontend Logic for RegFlow AI

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const logsContainer = document.getElementById('logs-container');
    const progressWrapper = document.getElementById('progress-wrapper');
    const progressFill = document.getElementById('progress-fill');
    
    // Steps
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');
    const step4 = document.getElementById('step-4');

    // Results elements
    const resultsCard = document.getElementById('results-card');
    const complianceBadge = document.getElementById('compliance-badge');
    const extractedTextView = document.getElementById('extracted-text-view');
    const metaInvNum = document.getElementById('meta-inv-num');
    const metaSupplier = document.getElementById('meta-supplier');
    const metaGstin = document.getElementById('meta-gstin');
    
    const taxTaxable = document.getElementById('tax-taxable');
    const taxCgst = document.getElementById('tax-cgst');
    const taxSgst = document.getElementById('tax-sgst');
    const taxTotalTax = document.getElementById('tax-total-tax');
    const taxTotalAmount = document.getElementById('tax-total-amount');
    
    const issuesList = document.getElementById('issues-list');

    // Utility: add logs
    function addLog(message, type = 'system') {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${time}] ${message}`;
        logsContainer.appendChild(entry);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    // Reset UI state
    function resetResults() {
        complianceBadge.className = 'badge';
        complianceBadge.textContent = 'Analyzing...';
        extractedTextView.textContent = 'Processing PDF...';
        metaInvNum.textContent = '-';
        metaSupplier.textContent = '-';
        metaGstin.textContent = '-';
        taxTaxable.textContent = '₹0.00';
        taxCgst.textContent = '₹0.00';
        taxSgst.textContent = '₹0.00';
        taxTotalTax.textContent = '₹0.00';
        taxTotalAmount.textContent = '₹0.00';
        issuesList.innerHTML = '<li class="no-issues">No validation errors or issues detected.</li>';
        
        step2.classList.remove('active', 'completed');
        step3.classList.remove('active', 'completed');
        step4.classList.remove('active', 'completed');
    }

    // Drag over styling
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        }, false);
    });

    // File dropping
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // Manual click browse
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    // Main file handler
    function handleFile(file) {
        if (file.type !== 'application/pdf') {
            addLog(`Error: File "${file.name}" is not a PDF! Please upload a PDF.`, 'error');
            return;
        }

        // Start workflow UI
        resetResults();
        progressWrapper.classList.remove('hidden');
        progressFill.style.width = '10%';
        
        step1.classList.add('completed');
        step2.classList.add('active');

        addLog(`Selected file: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`, 'system');
        addLog('Step 1 complete: PDF uploaded to memory.', 'success');
        addLog('Step 2: Processing PDF content & running OCR...', 'process');

        progressFill.style.width = '30%';

        // Upload via Form Data
        const formData = new FormData();
        formData.append('file', file);

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Upload failed') });
            }
            return response.json();
        })
        .then(data => {
            progressFill.style.width = '70%';
            addLog('PDF text extraction and OCR complete.', 'success');
            step2.classList.add('completed');
            step3.classList.add('active');
            
            addLog('Step 3: Validating GST compliance & formatting metadata...', 'process');
            renderData(data);
        })
        .catch(error => {
            progressFill.style.width = '0%';
            addLog(`Processing failed: ${error.message}`, 'error');
            complianceBadge.className = 'badge non-compliant';
            complianceBadge.textContent = 'Failed';
            extractedTextView.textContent = `Error details:\n${error.message}`;
            
            step2.classList.remove('active');
        });
    }

    // Render results on screen
    function renderData(data) {
        setTimeout(() => {
            progressFill.style.width = '100%';
            
            // Raw text
            extractedTextView.textContent = data.extracted_text || "[Empty document content]";

            // Meta
            const info = data.invoice_data || {};
            metaInvNum.textContent = info.invoice_number || "N/A";
            metaSupplier.textContent = info.supplier || "N/A";
            metaGstin.textContent = info.gstin || "N/A";

            // Tax Summary
            taxTaxable.textContent = `₹${(info.taxable_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            taxCgst.textContent = `₹${(info.cgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            taxSgst.textContent = `₹${(info.sgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            
            const totalTax = (info.cgst || 0) + (info.sgst || 0);
            taxTotalTax.textContent = `₹${totalTax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            taxTotalAmount.textContent = `₹${(info.total_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            // Compliance Badge
            const status = (info.compliance_status || 'compliant').toLowerCase();
            if (status.includes('non-compliant') || status.includes('non_compliant')) {
                complianceBadge.textContent = 'Non-Compliant';
                complianceBadge.className = 'badge non-compliant';
                addLog('GST Compliance Audit: FAILED compliance parameters.', 'error');
            } else {
                complianceBadge.textContent = 'Compliant';
                complianceBadge.className = 'badge compliant';
                addLog('GST Compliance Audit: PASSED compliance parameters.', 'success');
            }

            // Issues list
            const issues = info.issues || [];
            if (issues.length > 0) {
                issuesList.innerHTML = '';
                issues.forEach(issue => {
                    const li = document.createElement('li');
                    li.textContent = issue;
                    issuesList.appendChild(li);
                });
            } else {
                issuesList.innerHTML = '<li class="no-issues">No validation errors or issues detected.</li>';
            }

            addLog('Step 4: Audit dashboard aggregated. Filing ready!', 'success');
            
            step3.classList.add('completed');
            step4.classList.add('active');
            step4.classList.add('completed');
        }, 800);
    }
});
