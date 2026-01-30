// GitHub AI Editor - Frontend JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize connection status
    checkConnections();
    
    // Form submission
    document.getElementById('editForm').addEventListener('submit', handleSubmit);
    
    // Preview button
    document.getElementById('previewBtn').addEventListener('click', handlePreview);
    
    // Example click handlers
    document.querySelectorAll('.example').forEach(example => {
        example.addEventListener('click', function() {
            useExample(this);
        });
    });
});

// Check API connections
async function checkConnections() {
    try {
        // Check GitHub connection
        const githubResponse = await fetch('/api/github/test');
        const githubData = await githubResponse.json();
        
        const githubStatus = document.querySelector('#github-status .status-text');
        if (githubData.success) {
            githubStatus.textContent = 'Connected ✓';
            githubStatus.style.color = '#10b981';
            document.querySelector('#github-status i').style.color = '#10b981';
        } else {
            githubStatus.textContent = 'Error ✗';
            githubStatus.style.color = '#ef4444';
        }
        
        // Check AI connection
        const aiResponse = await fetch('/api/ai/test');
        const aiData = await aiResponse.json();
        
        const aiStatus = document.querySelector('#ai-status .status-text');
        if (aiData.success) {
            aiStatus.textContent = 'Connected ✓';
            aiStatus.style.color = '#10b981';
            document.querySelector('#ai-status i').style.color = '#10b981';
        } else {
            aiStatus.textContent = 'Error ✗';
            aiStatus.style.color = '#ef4444';
        }
        
    } catch (error) {
        console.error('Connection check failed:', error);
        document.querySelectorAll('.status-text').forEach(el => {
            el.textContent = 'Connection failed';
            el.style.color = '#ef4444';
        });
    }
}

// Handle form submission
async function handleSubmit(event) {
    event.preventDefault();
    
    const repoUrl = document.getElementById('repoUrl').value;
    const request = document.getElementById('request').value;
    const branchName = document.getElementById('branchName').value || undefined;
    const createPR = document.getElementById('createPR').checked;
    const previewFirst = document.getElementById('previewFirst').checked;
    
    // Validate inputs
    if (!isValidGitHubUrl(repoUrl)) {
        showError('Please enter a valid GitHub repository URL');
        return;
    }
    
    if (!request.trim()) {
        showError('Please describe what you want to change');
        return;
    }
    
    // Show results section
    const resultsSection = document.getElementById('results');
    const resultsTitle = document.getElementById('results-title');
    const resultsContent = document.getElementById('results-content');
    const resultsSpinner = document.getElementById('results-spinner');
    
    resultsSection.style.display = 'block';
    resultsTitle.textContent = 'Making Changes...';
    resultsSpinner.className = 'fas fa-spinner fa-spin';
    resultsContent.innerHTML = '<div class="spinner"></div>';
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
    
    try {
        const data = {
            repo_url: repoUrl,
            request: request,
            branch_name: branchName,
            create_pr: createPR
        };
        
        const response = await fetch('/api/edits/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        // Update UI with results
        if (result.success) {
            showSuccess(result);
        } else {
            showError(result.error || 'An unknown error occurred', result);
        }
        
    } catch (error) {
        console.error('Error:', error);
        showError('Network error: ' + error.message);
    }
}

// Handle preview
async function handlePreview() {
    event.preventDefault();
    
    const repoUrl = document.getElementById('repoUrl').value;
    const request = document.getElementById('request').value;
    
    if (!isValidGitHubUrl(repoUrl)) {
        showError('Please enter a valid GitHub repository URL');
        return;
    }
    
    if (!request.trim()) {
        showError('Please describe what you want to change');
        return;
    }
    
    // Show results section
    const resultsSection = document.getElementById('results');
    const resultsTitle = document.getElementById('results-title');
    const resultsContent = document.getElementById('results-content');
    const resultsSpinner = document.getElementById('results-spinner');
    
    resultsSection.style.display = 'block';
    resultsTitle.textContent = 'Generating Preview...';
    resultsSpinner.className = 'fas fa-spinner fa-spin';
    resultsContent.innerHTML = '<div class="spinner"></div>';
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
    
    try {
        const data = {
            repo_url: repoUrl,
            request: request
        };
        
        const response = await fetch('/api/edits/preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        // Update UI with preview results
        if (result.success) {
            showPreview(result);
        } else {
            showError(result.error || 'Preview failed', result);
        }
        
    } catch (error) {
        console.error('Error:', error);
        showError('Network error: ' + error.message);
    }
}

// Show success results
function showSuccess(result) {
    const resultsTitle = document.getElementById('results-title');
    const resultsContent = document.getElementById('results-content');
    const resultsSpinner = document.getElementById('results-spinner');
    
    resultsTitle.textContent = 'Success!';
    resultsSpinner.className = 'fas fa-check-circle';
    resultsSpinner.style.color = '#10b981';
    
    let html = '<div class="result-success fade-in">';
    html += '<div class="result-title"><i class="fas fa-check-circle"></i> Changes Applied Successfully</div>';
    
    if (result.pull_request) {
        html += `<p><strong>Pull Request Created:</strong> <a href="${result.pull_request.url}" target="_blank">${result.pull_request.url}</a></p>`;
    }
    
    html += `<p><strong>Branch:</strong> ${result.branch_name || 'Not specified'}</p>`;
    html += `<p><strong>Total Changes:</strong> ${result.summary?.successful_changes || 0} files</p>`;
    
    if (result.changes_preview && result.changes_preview.length > 0) {
        html += '<div class="result-details">';
        html += '<p><strong>Changed Files:</strong></p>';
        result.changes_preview.forEach(change => {
            const emoji = {
                'modified': '📝',
                'created': '✨',
                'deleted': '🗑️'
            }[change.change_type] || '❓';
            
            html += `<div class="detail-item">${emoji} ${change.file_path} (${change.change_type})</div>`;
        });
        html += '</div>';
    }
    
    if (result.warnings && result.warnings.length > 0) {
        html += '<div class="result-info">';
        html += '<p><strong>Warnings:</strong></p>';
        result.warnings.forEach(warning => {
            html += `<div class="detail-item">⚠️ ${warning}</div>`;
        });
        html += '</div>';
    }
    
    html += '</div>';
    
    resultsContent.innerHTML = html;
}

// Show preview results
function showPreview(result) {
    const resultsTitle = document.getElementById('results-title');
    const resultsContent = document.getElementById('results-content');
    const resultsSpinner = document.getElementById('results-spinner');
    
    resultsTitle.textContent = 'Preview Generated';
    resultsSpinner.className = 'fas fa-eye';
    resultsSpinner.style.color = '#3b82f6';
    
    let html = '<div class="result-info fade-in">';
    html += '<div class="result-title"><i class="fas fa-eye"></i> Preview of Planned Changes</div>';
    
    html += `<p><strong>Total Files to Modify:</strong> ${result.plan_summary?.total_instructions || 0}</p>`;
    html += `<p><strong>Confidence:</strong> ${(result.plan_summary?.confidence * 100 || 0).toFixed(1)}%</p>`;
    html += `<p><strong>Estimated Complexity:</strong> ${result.plan_summary?.estimated_time || 'medium'}</p>`;
    
    if (result.preview_changes && result.preview_changes.length > 0) {
        html += '<div class="result-details">';
        html += '<p><strong>Sample Changes:</strong></p>';
        
        result.preview_changes.forEach(preview => {
            html += `<div class="detail-item">`;
            html += `<p><strong>${preview.file_path}</strong> (${preview.language})</p>`;
            
            if (preview.diff) {
                html += `<details style="margin-top: 10px;">`;
                html += `<summary>View Diff</summary>`;
                html += `<pre style="background: #f8fafc; padding: 10px; border-radius: 5px; overflow-x: auto; font-size: 0.9em;">${escapeHtml(preview.diff)}</pre>`;
                html += `</details>`;
            }
            
            html += `</div>`;
        });
        html += '</div>';
    }
    
    html += '<div style="margin-top: 20px; padding: 15px; background: #f0f9ff; border-radius: 10px;">';
    html += '<p><strong>Ready to apply changes?</strong></p>';
    html += '<button onclick="document.getElementById(\'submitBtn\').click()" class="btn btn-primary" style="margin-top: 10px;">';
    html += '<i class="fas fa-magic"></i> Apply Changes Now';
    html += '</button>';
    html += '</div>';
    
    html += '</div>';
    
    resultsContent.innerHTML = html;
}

// Show error results
function showError(message, result = null) {
    const resultsTitle = document.getElementById('results-title');
    const resultsContent = document.getElementById('results-content');
    const resultsSpinner = document.getElementById('results-spinner');
    
    resultsTitle.textContent = 'Error';
    resultsSpinner.className = 'fas fa-exclamation-circle';
    resultsSpinner.style.color = '#ef4444';
    
    let html = '<div class="result-error fade-in">';
    html += '<div class="result-title"><i class="fas fa-exclamation-circle"></i> Error Occurred</div>';
    html += `<p>${escapeHtml(message)}</p>`;
    
    if (result && result.errors && result.errors.length > 0) {
        html += '<div class="result-details">';
        html += '<p><strong>Details:</strong></p>';
        result.errors.forEach(error => {
            html += `<div class="detail-item">❌ ${escapeHtml(error)}</div>`;
        });
        html += '</div>';
    }
    
    if (result && result.request_id) {
        html += `<p style="margin-top: 10px; font-size: 0.9em; color: #666;">Request ID: ${result.request_id}</p>`;
    }
    
    html += '</div>';
    
    resultsContent.innerHTML = html;
}

// Use example text
function useExample(exampleElement) {
    const requestText = exampleElement.querySelector('p').textContent;
    document.getElementById('request').value = requestText;
    
    // Auto-generate branch name from example
    const words = requestText.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(' ').slice(0, 3);
    const branchName = 'ai-edit-' + words.join('-');
    document.getElementById('branchName').value = branchName;
    
    // Highlight the example
    exampleElement.style.animation = 'none';
    setTimeout(() => {
        exampleElement.style.animation = 'pulse 0.5s ease';
    }, 10);
}

// Modal functions
function showApiDocs() {
    document.getElementById('apiDocsModal').style.display = 'block';
}

function showAbout() {
    document.getElementById('aboutModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modals when clicking outside
window.onclick = function(event) {
    if (event.target.className === 'modal') {
        event.target.style.display = 'none';
    }
}

// Utility functions
function isValidGitHubUrl(url) {
    const pattern = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(\.git)?$/;
    return pattern.test(url);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .pulse {
        animation: pulse 0.5s ease;
    }
`;
document.head.appendChild(style);
