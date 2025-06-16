let activeToast = null;

// Function to display toast notifications
function showToast(message, type, duration = 3000) {
    // Remove any existing toast
    if (activeToast) {
        removeToast(activeToast);
    }

    // Create toast container
    const toastContainer = document.createElement('div');
    toastContainer.className = `toast ${type}`;
    toastContainer.innerHTML = `
        <div class="toast-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-spinner fa-spin'}"></i>
            <div class="toast-message">${message}</div>
        </div>
        ${type === 'error' ? '<button class="toast-close">&times;</button>' : ''}
    `;

    // Set styles for the toast
    Object.assign(toastContainer.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        zIndex: '9999',
        padding: '12px 20px',
        borderRadius: '5px',
        color: '#fff',
        fontSize: '14px',
        maxWidth: '350px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        opacity: '0',
        transition: 'opacity 0.3s ease-in-out'
    });

    // Set background color based on toast type
    if (type === 'success') {
        toastContainer.style.backgroundColor = '#4caf50'; // Green
    } else if (type === 'error') {
        toastContainer.style.backgroundColor = '#f44336'; // Red
    } else if (type === 'loading') {
        toastContainer.style.backgroundColor = '#2196f3'; // Blue
    }

    document.body.appendChild(toastContainer);

    // Fade in animation
    setTimeout(() => {
        toastContainer.style.opacity = '1';
    }, 10);

    activeToast = { element: toastContainer, type: type };

    // Set up close button for error toasts
    if (type === 'error') {
        const closeButton = toastContainer.querySelector('.toast-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => removeToast(activeToast));
        }
    } else if (type !== 'loading') {
        // Auto-close for non-error and non-loading toasts
        setTimeout(() => removeToast(activeToast), duration);
    }

    return activeToast;
}

// Function to remove toast notifications
function removeToast(toastObject) {
    if (!toastObject || !toastObject.element) return;

    toastObject.element.style.opacity = '0';
    setTimeout(() => {
        if (document.body.contains(toastObject.element)) {
            document.body.removeChild(toastObject.element);
        }
        if (activeToast === toastObject) {
            activeToast = null;
        }
    }, 300);
}

let isAutoOrderRunning = false;

let data_for_mid_table;
// Function to handle the auto order process
function handleAutoOrder() {
    if (isAutoOrderRunning) {
        showToast('Auto order process is already running', 'error');
        return;
    }

    const dateStart = document.getElementById('dateStart').value;
    const dateEnd = document.getElementById('dateEnd').value;
    const daysOfOrder = document.getElementById('daysOfOrder').value;

    // Input validation
    if (!dateStart || !dateEnd) {
        showToast('Please select both start and end dates.', 'error');
        return;
    }

    if (!daysOfOrder || daysOfOrder < 7) {
        showToast('Days of order must be at least 7.', 'error');
        return;
    }

    const endDate = new Date($("#dateEnd").val());
    const today = new Date();
    const textElement = document.getElementById("finishDateValidation");

    endDate.setHours(0, 0, 0, 0);
    today.setHours(0, 0, 0, 0);

    if (endDate.getTime() === today.getTime()) {
        textElement.style.opacity = "1";
        textElement.style.visibility = "visible";
    } else {
        textElement.style.opacity = "0";
        textElement.style.visibility = "hidden";
    }

    isAutoOrderRunning = true;
    const startAutoOrderBtn = document.getElementById('startAutoOrderBtn');
    startAutoOrderBtn.disabled = true;
    startAutoOrderBtn.textContent = 'Processing...';

    const loadingToast = showToast('Auto order process started...', 'loading');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);
    
    // Send request to start auto order
    fetch('/start_auto_order', {
        method: 'POST',
        signal: controller.signal,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            date_start: dateStart,
            date_finish: dateEnd,
            days_of_order: parseInt(daysOfOrder)
        })
    })
    .then(response => {
        clearTimeout(timeoutId);
        removeToast(loadingToast);
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.message || `HTTP error! status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        data_for_mid_table = data;
        console.log('Raw server response:', data);
        
        if (data.status === 'error') {
            showToast(data.message || 'An error occurred', 'error');
        } else if (data.message) {
            showToast(data.message, 'success', 7500);
        }
        
        if (data.data) {
            console.log('Result data:', data.data);
            populateTable(data.data);
            
            // Update information panel
            document.getElementById('analysisTime').textContent = data.analysis_time.toFixed(2);
            document.getElementById('productCount').textContent = data.product_count;
        
            // Show the download buttons
            const downloadResultButton = document.getElementById('download-result-button');
            downloadResultButton.style.display = 'block';
            downloadResultButton.setAttribute('data-filename', data.excel_filename_main);

            const downloadMidButton = document.getElementById('download-mid-button');
            downloadMidButton.style.display = 'block';
        } else {
            console.error('No result data in the response');
            showToast('No result data received', 'error');
        }
    })
    .catch(error => {
        console.error('Fetch error:', error);
        if (error.message.includes("SQL")) {
            showToast("База данных не отвечает. Пожалуйста, попробуйте позже.", 'error');
        } else {
            showToast(`Error: ${error.message}`, 'error');
        }
    })
    .finally(() => {
        isAutoOrderRunning = false;
        startAutoOrderBtn.disabled = false;
        startAutoOrderBtn.textContent = 'Start Auto Order';
    });
}

// Function to populate table with data
function populateTable(data) {
    console.log('Data received in populateTable:', data);

    // Check if data is a string
    if (typeof data === 'string') {
        try {
            data = JSON.parse(data);
        } catch (e) {
            console.error('Error parsing data:', e);
            return;
        }
    }

    if (!data || !data.columns || !data.data) {
        console.error('Invalid data format for table');
        return;
    }

    const columns = data.columns;
    const tableData = data.data;

    console.log('Columns:', columns);
    console.log('Table data:', tableData);

    // Populate table header
    const tableHeader = document.getElementById('tableHeader');
    tableHeader.innerHTML = `
        <tr>
            ${columns.map(header => `<th>${escapeHtml(header)}</th>`).join('')}
        </tr>
    `;

    // Populate table body
    const tableBody = document.getElementById('productTable');
    tableBody.innerHTML = tableData.map(row => {
        if (Array.isArray(row)) {
            return `
                <tr>
                    ${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}
                </tr>
            `;
        } else if (typeof row === 'object') {
            return `
                <tr>
                    ${columns.map(col => `<td>${escapeHtml(row[col] || '')}</td>`).join('')}
                </tr>
            `;
        } else {
            return `<tr><td colspan="${columns.length}">${escapeHtml(row)}</td></tr>`;
        }
    }).join('');

    document.querySelector('.table-responsive').style.display = 'block';
}

// Add this function to handle the download
function downloadTable() {
    const filename = this.getAttribute('data-filename');
    if (!filename) {
        showToast('No file available for download', 'error');
        return;
    }

    // Create a new workbook
    const wb = XLSX.utils.book_new();
    
    // Get table data
    const table = document.querySelector('.table');
    const ws = XLSX.utils.table_to_sheet(table);
    
    // Add worksheet to the workbook
    XLSX.utils.book_append_sheet(wb, ws, "Auto Order Results");
    
    // Generate Excel file
    const wbout = XLSX.write(wb, {bookType:'xlsx', type:'binary'});
    
    // Convert to Blob
    const blob = new Blob([s2ab(wbout)], {type:"application/octet-stream"});
    
    // Create download link
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;  // Use the filename received from the server
    
    // Trigger download
    document.body.appendChild(a);
    a.click();
    
    // Cleanup
    setTimeout(function() {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 0);
}

function exportToExcel() {
    let jsonData = data_for_mid_table.mid_result;
    let fileName = data_for_mid_table.filename_mid;
    
    if (fileName && jsonData) {
        // Create a new workbook
        const workbook = XLSX.utils.book_new();
        
        // Convert JSON data to worksheet
        const worksheet = XLSX.utils.json_to_sheet(jsonData.data, {header: jsonData.columns});
        
        // Add the worksheet to the workbook
        XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
        
        // Generate Excel file and trigger download
        XLSX.writeFile(workbook, fileName);
        
        console.log("Excel file generated successfully");
    } else {
        console.log("Intermediate table data not available");
        showToast('Intermediate table data not available', 'error');
    }
}

// Helper function to convert string to ArrayBuffer
function s2ab(s) {
    const buf = new ArrayBuffer(s.length);
    const view = new Uint8Array(buf);
    for (let i=0; i<s.length; i++) view[i] = s.charCodeAt(i) & 0xFF;
    return buf;
}

// Function to escape HTML to prevent XSS
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) {
        return '';
    }
    if (typeof unsafe !== 'string') {
        unsafe = String(unsafe);
    }
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// Function to set up event listeners
function setupEventListeners() {
    const startAutoOrderBtn = document.getElementById('startAutoOrderBtn');
    startAutoOrderBtn.addEventListener('click', handleAutoOrder);

    const downloadButton = document.getElementById('download-result-button');
    downloadButton.addEventListener('click', downloadTable);

    const downloadMidButton = document.getElementById('download-mid-button');
    downloadMidButton.addEventListener('click', exportToExcel);
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
})

// Menu button functionality
$(document).ready(function() {
    $("#menuToggle").click(function() {
        $("#slideMenu").slideToggle();
    })
});