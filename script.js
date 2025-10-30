document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const uploadSection = document.getElementById('upload-section');
    const loadingState = document.getElementById('loading-state');
    const resultsSection = document.getElementById('results-section');
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');

    // Results containers
    const summaryContent = document.getElementById('summary-content');
    const flagsContainer = document.getElementById('flags-container');
    const lineItemsTbody = document.getElementById('line-items-tbody');
    
    // Action buttons
    const explainBtn = document.getElementById('explain-btn');
    const appealBtn = document.getElementById('appeal-btn');

    // Modal elements
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalSpinner = document.getElementById('modal-spinner');
    const modalText = document.getElementById('modal-text');
    const copyBtn = document.getElementById('copy-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');

    // Template for flag cards
    const flagCardTemplate = document.getElementById('flag-card-template');
    
    // Store the full validation result to use with LLM endpoints
    let validationResultData = null;

    // --- Event Listeners ---
    uploadForm.addEventListener('submit', handleUpload);
    explainBtn.addEventListener('click', handleExplain);
    appealBtn.addEventListener('click', handleAppeal);
    closeModalBtn.addEventListener('click', () => modal.classList.add('hidden'));
    copyBtn.addEventListener('click', copyModalText);

    // --- Functions ---
    async function handleUpload(event) {
        event.preventDefault();
        
        if (!fileInput.files.length) {
            alert('Please select a file to upload.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        // Switch to loading view
        uploadSection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        loadingState.classList.remove('hidden');
        
        try {
            const response = await fetch('/validate-bill/', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to analyze bill.');
            }
            
            const data = await response.json();
            validationResultData = data; // Store the data
            displayResults(data);

        } catch (error) {
            alert(`An error occurred: ${error.message}`);
            // Reset view
            uploadSection.classList.remove('hidden');
        } finally {
            loadingState.classList.add('hidden');
        }
    }

    function displayResults(data) {
        // 1. Populate Summary
        const summary = data.parsed_data;
        summaryContent.innerHTML = `
            <div><strong>Provider</strong> ${summary.provider || 'N/A'}</div>
            <div><strong>Patient</strong> ${summary.patient_name || 'N/A'}</div>
            <div><strong>Date of Service</strong> ${summary.date_of_service || 'N/A'}</div>
            <div><strong>Total Billed</strong> $${summary.total_billed?.toFixed(2) || '0.00'}</div>
        `;

        // 2. Populate Flags
        flagsContainer.innerHTML = ''; // Clear previous flags
        if (data.flags && data.flags.length > 0) {
            data.flags.forEach(flag => {
                const card = flagCardTemplate.content.cloneNode(true).firstElementChild;
                card.classList.add(flag.flag_type);
                
                const flagTypeEl = card.querySelector('.flag-type');
                flagTypeEl.textContent = flag.flag_type;
                flagTypeEl.classList.add(flag.flag_type);

                card.querySelector('.flag-message').textContent = flag.message;

                const confidence = (flag.final_confidence || flag.rule_confidence) * 100;
                card.querySelector('.confidence-bar').style.width = `${confidence}%`;
                card.querySelector('.confidence-text').textContent = `Confidence: ${confidence.toFixed(0)}%`;
                
                flagsContainer.appendChild(card);
            });
        } else {
            flagsContainer.innerHTML = '<p>No issues or flags were found in our automated review.</p>';
        }

        // 3. Populate Line Items
        lineItemsTbody.innerHTML = ''; // Clear previous items
        summary.line_items.forEach(item => {
            const row = lineItemsTbody.insertRow();
            row.innerHTML = `
                <td>${item.cpt_code || ''}</td>
                <td>${item.description || ''}</td>
                <td>$${item.billed_amount?.toFixed(2) || ''}</td>
                <td>${item.national_average_price ? '$' + item.national_average_price.toFixed(2) : 'N/A'}</td>
            `;
        });
        
        // Show the results
        const rawTextContent = document.getElementById('raw-text-content');
        rawTextContent.textContent = summary.raw_text || 'No raw text was extracted.';
        resultsSection.classList.remove('hidden');
}

    async function handleExplain() {
        if (!validationResultData) return;
        
        showModal('Bill Explanation');
        
        try {
            const response = await fetch('/explain-bill/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(validationResultData)
            });
            if (!response.ok) throw new Error('Failed to get explanation.');
            
            const data = await response.json();
            showModalText(data.explanation_text);

        } catch (error) {
            showModalText(`Error: ${error.message}`);
        }
    }

    async function handleAppeal() {
        if (!validationResultData) return;
        
        showModal('Appeal Letter Draft');
        
        try {
            const response = await fetch('/draft-appeal/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(validationResultData)
            });
            if (!response.ok) throw new Error('Failed to draft appeal.');
            
            const data = await response.json();
            showModalText(data.appeal_draft_text);

        } catch (error) {
            showModalText(`Error: ${error.message}`);
        }
    }

    function showModal(title) {
        modalTitle.textContent = title;
        modalText.classList.add('hidden');
        modalSpinner.classList.remove('hidden');
        modal.classList.remove('hidden');
    }

    function showModalText(text) {
        modalText.textContent = text;
        modalSpinner.classList.add('hidden');
        modalText.classList.remove('hidden');
    }
    
    function copyModalText() {
        navigator.clipboard.writeText(modalText.textContent).then(() => {
            alert('Text copied to clipboard!');
        }, () => {
            alert('Failed to copy text.');
        });
    }
});