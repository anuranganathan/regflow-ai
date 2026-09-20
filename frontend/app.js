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
    const metaConfidence = document.getElementById('meta-confidence');
    const metaReview = document.getElementById('meta-review');
    const metaSources = document.getElementById('meta-sources');
    
    const taxTaxable = document.getElementById('tax-taxable');
    const taxCgst = document.getElementById('tax-cgst');
    const taxSgst = document.getElementById('tax-sgst');
    const taxIgst = document.getElementById('tax-igst');
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
        metaConfidence.textContent = '-';
        metaReview.textContent = '-';
        metaSources.textContent = '-';
        taxTaxable.textContent = '₹0.00';
        taxCgst.textContent = '₹0.00';
        taxSgst.textContent = '₹0.00';
        taxIgst.textContent = '₹0.00';
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
        addLog('Step 1: Uploading PDF to storage...', 'process');
        addLog('Step 2: Extracting text with PyMuPDF...', 'process');

        progressFill.style.width = '30%';

        // Upload via Form Data
        const formData = new FormData();
        formData.append('file', file);

        fetch('/documents/upload', {
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
            const doc = data.document;
            addLog(`Stored as ${doc.object_key} (${doc.storage_mode === 's3' ? 'AWS S3' : 'local disk'}).`, 'success');
            addLog(`Text extracted with PyMuPDF; fields read by ${data.result.extraction.method}.`, 'success');
            step2.classList.add('completed');
            step3.classList.add('active');

            addLog('Step 3: Python checks + GST rules (RAG) + Gemini review...', 'process');
            renderData(data.result);
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

    const rupees = value => `₹${(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

    // Render results on screen
    function renderData(result) {
        setTimeout(() => {
            progressFill.style.width = '100%';

            extractedTextView.textContent = result.extracted_text || "[Empty document content]";

            const info = result.invoice || {};
            const compliance = result.compliance;
            const filing = result.filing_summary;
            metaInvNum.textContent = info.invoice_number || "Not found";
            metaSupplier.textContent = info.supplier_name || "Not found";
            metaGstin.textContent = info.supplier_gstin || "Not found";
            metaConfidence.textContent = compliance.confidence;
            metaReview.textContent = compliance.requires_human_review ? 'Required' : 'Not required';
            metaSources.textContent = compliance.sources_used.join(', ') || 'None';

            taxTaxable.textContent = rupees(filing.total_taxable_value);
            taxCgst.textContent = rupees(filing.total_cgst);
            taxSgst.textContent = rupees(filing.total_sgst);
            taxIgst.textContent = rupees(filing.total_igst);
            taxTotalTax.textContent = rupees(filing.total_tax);
            taxTotalAmount.textContent = rupees(info.total_amount);

            const badges = {
                COMPLIANT: ['compliant', 'Compliant', 'success'],
                NON_COMPLIANT: ['non-compliant', 'Non-Compliant', 'error'],
                NEEDS_REVIEW: ['needs-review', 'Needs Review', 'process'],
            };
            const [cls, label, logType] = badges[compliance.status];
            complianceBadge.className = `badge ${cls}`;
            complianceBadge.textContent = label;
            addLog(`Compliance: ${label} (${compliance.confidence} confidence). ${compliance.explanation}`, logType);

            const items = [
                ...compliance.issues,
                ...compliance.review_reasons.map(r => `Review: ${r}`),
                ...compliance.recommendations.map(r => `Recommendation: ${r}`),
            ];
            if (items.length > 0) {
                issuesList.innerHTML = '';
                items.forEach(text => {
                    const li = document.createElement('li');
                    li.textContent = text;
                    issuesList.appendChild(li);
                });
            } else {
                issuesList.innerHTML = '<li class="no-issues">No validation errors or issues detected.</li>';
            }

            addLog(`Step 4: GSTR-3B summary. ${filing.note}`, filing.ready_to_file ? 'success' : 'process');

            step3.classList.add('completed');
            step4.classList.add('active');
            step4.classList.add('completed');
        }, 300);
    }
});
