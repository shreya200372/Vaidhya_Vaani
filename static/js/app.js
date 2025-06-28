// Global variables
let socket;
let currentUser = null;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
});

function initializeApp() {
    // Initialize Socket.IO if not already connected
    if (typeof io !== 'undefined' && !socket) {
        socket = io();
        setupSocketListeners();
    }
    
    // Check for user session
    checkUserSession();
    
    // Initialize tooltips and popovers
    initializeBootstrapComponents();
    
    // Setup form validations
    setupFormValidations();
}

function setupEventListeners() {
    // Global logout function
    window.logout = async function() {
        try {
            const response = await fetch('/api/logout', { method: 'POST' });
            if (response.ok) {
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Logout error:', error);
        }
    };
    
    // Handle responsive navigation
    const navbarToggler = document.querySelector('.navbar-toggler');
    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            const navbarCollapse = document.querySelector('.navbar-collapse');
            navbarCollapse.classList.toggle('show');
        });
    }
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const alertInstance = new bootstrap.Alert(alert);
            alertInstance.close();
        }, 5000);
    });
}

function setupSocketListeners() {
    if (!socket) return;
    
    socket.on('connect', function() {
        console.log('Connected to server');
        showNotification('Connected to server', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        showNotification('Connection lost. Attempting to reconnect...', 'warning');
    });
    
    socket.on('consultation_request', function(data) {
        showConsultationRequest(data);
    });
    
    socket.on('notification', function(data) {
        showNotification(data.message, data.type || 'info');
    });
}

function checkUserSession() {
    // This would typically check if user is logged in
    // For now, we'll rely on server-side session management
}

function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

function setupFormValidations() {
    // Add Bootstrap validation classes
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Password confirmation validation
    const passwordConfirmInputs = document.querySelectorAll('input[id*="confirmPassword"]');
    passwordConfirmInputs.forEach(input => {
        input.addEventListener('input', function() {
            const password = document.querySelector('input[id*="password"]:not([id*="confirm"])');
            if (password && this.value !== password.value) {
                this.setCustomValidity('Passwords do not match');
            } else {
                this.setCustomValidity('');
            }
        });
    });
}

// Utility functions
function showNotification(message, type = 'info', duration = 5000) {
    const alertTypes = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    };
    
    const alertClass = alertTypes[type] || 'alert-info';
    const iconClass = {
        'success': 'fas fa-check-circle',
        'error': 'fas fa-exclamation-circle',
        'warning': 'fas fa-exclamation-triangle',
        'info': 'fas fa-info-circle'
    }[type] || 'fas fa-info-circle';
    
    const alertHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
            <i class="${iconClass} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHTML);
    
    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            const alerts = document.querySelectorAll('.alert.position-fixed');
            if (alerts.length > 0) {
                const alertInstance = new bootstrap.Alert(alerts[alerts.length - 1]);
                alertInstance.close();
            }
        }, duration);
    }
}

function showConsultationRequest(data) {
    const modal = new bootstrap.Modal(document.createElement('div'));
    const modalHTML = `
        <div class="modal fade" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-video me-2"></i>New Consultation Request
                        </h5>
                    </div>
                    <div class="modal-body">
                        <h6>Patient: ${data.patient_name}</h6>
                        <p><strong>Symptoms:</strong> ${data.symptoms}</p>
                        <p class="text-muted">Would you like to accept this consultation?</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Decline</button>
                        <button type="button" class="btn btn-primary" onclick="acceptConsultation('${data.consultation_id}')">Accept</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    const modalElement = document.body.lastElementChild;
    const modalInstance = new bootstrap.Modal(modalElement);
    modalInstance.show();
    
    // Remove modal from DOM when hidden
    modalElement.addEventListener('hidden.bs.modal', function() {
        modalElement.remove();
    });
}

function acceptConsultation(consultationId) {
    window.open(`/consultation/${consultationId}`, '_blank', 'width=1200,height=800');
}

// Loading utilities
function showLoading(element) {
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    if (element) {
        element.innerHTML = `
            <div class="text-center p-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading...</p>
            </div>
        `;
    }
}

function hideLoading(element, content = '') {
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    if (element) {
        element.innerHTML = content;
    }
}

// API utilities
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showNotification('An error occurred. Please try again.', 'error');
        throw error;
    }
}

// Local storage utilities
function saveToStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
        console.error('Failed to save to localStorage:', error);
    }
}

function getFromStorage(key) {
    try {
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : null;
    } catch (error) {
        console.error('Failed to get from localStorage:', error);
        return null;
    }
}

// Date utilities
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function formatDuration(startTime, endTime) {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const diff = end - start;
    const minutes = Math.floor(diff / 60000);
    return `${minutes} minutes`;
}

// Export functions for global access
window.showNotification = showNotification;
window.apiCall = apiCall;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.formatDate = formatDate;
window.formatDuration = formatDuration;
