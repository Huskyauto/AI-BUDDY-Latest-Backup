/**
 * PWA Form Handler for AI-BUDDY
 * 
 * Ensures form submissions work correctly in PWA context, especially with custom domains.
 * Handles CSRF token refreshing and proper form submission in standalone mode.
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('PWA Form Handler initialized');
    setupPWAFormHandlers();
    
    // Listen for messages from service worker
    if (navigator.serviceWorker) {
        navigator.serviceWorker.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'WELLNESS_CHECKIN_SSL_ERROR') {
                console.log('Received SSL error message from service worker:', event.data);
                
                // Find the wellness check-in form
                const form = document.getElementById('wellness-check-in-form');
                if (form) {
                    // Show SSL error message
                    const alertContainer = document.createElement('div');
                    alertContainer.className = 'alert alert-danger alert-dismissible fade show mt-3';
                    alertContainer.role = 'alert';
                    alertContainer.innerHTML = `
                        <strong>Security Error!</strong> There was an SSL error while submitting your check-in. 
                        <p>The web app is trying to use secure connections, but there's a certificate issue.</p>
                        <p>You can:</p>
                        <ul>
                            <li>Try submitting again</li>
                            <li>Use the web browser version instead of the PWA</li>
                            <li>Use our alternative submission method below</li>
                        </ul>
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    
                    // Add Try API mode button
                    const tryApiButton = document.createElement('button');
                    tryApiButton.className = 'btn btn-primary mt-2 me-2';
                    tryApiButton.textContent = 'Try Alternative Method';
                    tryApiButton.addEventListener('click', function() {
                        // This will use a form fallback
                        const formData = new FormData(form);
                        const formElement = document.createElement('form');
                        formElement.method = 'post';
                        formElement.action = '/self-care/wellness-check-in';
                        formElement.enctype = 'multipart/form-data';
                        
                        formData.forEach((value, key) => {
                            const input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = key;
                            input.value = value;
                            formElement.appendChild(input);
                        });
                        
                        document.body.appendChild(formElement);
                        formElement.submit();
                    });
                    alertContainer.appendChild(tryApiButton);
                    
                    // Add Browser mode button
                    const browserButton = document.createElement('button');
                    browserButton.className = 'btn btn-secondary mt-2';
                    browserButton.textContent = 'Open in Browser';
                    browserButton.addEventListener('click', function() {
                        // Open the same page in browser tab
                        window.open(window.location.href, '_blank');
                    });
                    alertContainer.appendChild(browserButton);
                    
                    // Add to the form
                    form.prepend(alertContainer);
                    
                    // Reset submission UI
                    const submitBtn = document.getElementById('submit-btn');
                    const submitText = document.getElementById('submit-text');
                    const loadingSpinner = document.getElementById('loading-spinner');
                    resetSubmitButton(submitBtn, submitText, loadingSpinner);
                    
                    // Hide processing modal if open
                    const processingModal = document.getElementById('processingModal');
                    hideProcessingModal(processingModal);
                }
            }
        });
    }
});

/**
 * Setup handlers for all forms in the PWA context
 */
function setupPWAFormHandlers() {
    // Apply to all forms, with special handling for wellness check-in
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        // Ensure CSRF token is present
        ensureFormHasCSRFToken(form);
        
        // Skip wellness check-in form - it has its own handler in the template
        if (form.id === 'wellness-check-in-form') {
            console.log('Wellness check-in form found - skipping PWA handler, using template handler');
            return;
        }
    });
    
    // Set up periodic CSRF token refresh
    refreshCSRFTokenIfNeeded();
    
    // Set up interval to periodically check if tokens need refreshing
    setInterval(refreshCSRFTokenIfNeeded, 60000); // Check every minute
}

/**
 * Ensure the form has a valid CSRF token
 */
function ensureFormHasCSRFToken(form) {
    // Check if we're in standalone/PWA mode
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                         window.navigator.standalone || 
                         document.referrer.includes('android-app://');
    
    if (isStandalone) {
        // Get existing token if available
        let csrfToken = document.querySelector('meta[name="csrf-token"]');
        
        if (!csrfToken) {
            // If no meta tag exists, check for hidden input in the form
            const hiddenTokenInput = form.querySelector('input[name="csrf_token"]');
            if (hiddenTokenInput) {
                // Create meta tag with the token value
                const meta = document.createElement('meta');
                meta.name = 'csrf-token';
                meta.content = hiddenTokenInput.value;
                document.head.appendChild(meta);
            } else {
                console.warn('No CSRF token found in form:', form.id || form.action);
                
                // Request a new token through API
                fetch('/get-csrf-token', {
                    method: 'GET',
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.csrf_token) {
                        // Add token to form
                        const tokenInput = document.createElement('input');
                        tokenInput.type = 'hidden';
                        tokenInput.name = 'csrf_token';
                        tokenInput.value = data.csrf_token;
                        form.appendChild(tokenInput);
                        
                        // Add meta tag
                        const meta = document.createElement('meta');
                        meta.name = 'csrf-token';
                        meta.content = data.csrf_token;
                        document.head.appendChild(meta);
                    }
                })
                .catch(error => {
                    console.error('Error fetching CSRF token:', error);
                });
            }
        }
    }
}

/**
 * Refresh CSRF token if it's older than 30 minutes
 */
function refreshCSRFTokenIfNeeded() {
    const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfTokenTimeMeta = document.querySelector('meta[name="csrf-token-time"]');
    
    if (csrfTokenMeta && csrfTokenTimeMeta) {
        const tokenTime = parseInt(csrfTokenTimeMeta.content, 10);
        const currentTime = Date.now();
        
        // If token is older than 30 minutes, refresh it
        if (currentTime - tokenTime > 1800000) { // 30 minutes in milliseconds
            fetch('/get-csrf-token', {
                method: 'GET',
                credentials: 'include'
            })
            .then(response => response.json())
            .then(data => {
                if (data.csrf_token) {
                    // Update all CSRF tokens in forms
                    document.querySelectorAll('input[name="csrf_token"]').forEach(input => {
                        input.value = data.csrf_token;
                    });
                    
                    // Update meta tags
                    csrfTokenMeta.content = data.csrf_token;
                    csrfTokenTimeMeta.content = currentTime.toString();
                }
            })
            .catch(error => {
                console.error('Error refreshing CSRF token:', error);
            });
        }
    }
}

/**
 * Add special handling for wellness check-in form
 */
function addWellnessSuccessHandler(form) {
    form.addEventListener('submit', function(event) {
        console.log('Wellness check-in form submission - using standard form submission');
        
        // Show processing modal but don't prevent form submission
        const processingModal = document.getElementById('processingModal');
        if (processingModal) {
            const bsModal = new bootstrap.Modal(processingModal);
            bsModal.show();
        }
        
        // Let the form submit normally - don't prevent default
        // This ensures mobile compatibility and eliminates endpoint conflicts
        
        // Show loading spinner on button
        const submitBtn = document.getElementById('submit-btn');
        const submitText = document.getElementById('submit-text');
        const loadingSpinner = document.getElementById('loading-spinner');
        
        if (submitBtn && submitText && loadingSpinner) {
            submitBtn.disabled = true;
            submitText.textContent = 'Submitting...';
            loadingSpinner.classList.remove('d-none');
        }
        
        // Mark PWA mode if needed
        const isPwaField = document.getElementById('is_pwa');
        if (isPwaField) {
            const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                                window.navigator.standalone || 
                                document.referrer.includes('android-app://');
            isPwaField.value = isStandalone ? 'true' : 'false';
        }
        
        // In PWA mode, use a direct form submission to our specialized PWA endpoint
        // This works around SSL and JSON parsing issues in PWA mode
        if (isStandalone) {
            console.log('Using simple form submission for PWA mode');
            
            // Try the simplest possible approach - POST directly to the standard endpoint
            console.log('Creating direct form for PWA submission - May 6 2025 update');
            const directForm = document.createElement('form');
            directForm.method = 'POST';
            directForm.action = '/self-care/wellness-check-in'; // Use standard endpoint for reliability
            directForm.enctype = 'multipart/form-data'; // Use multipart for better compatibility
            
            // First, make sure we're explicitly setting is_pwa to true
            const isPwaInput = document.createElement('input');
            isPwaInput.type = 'hidden';
            isPwaInput.name = 'is_pwa';
            isPwaInput.value = 'true';
            directForm.appendChild(isPwaInput);
            console.log('Added is_pwa=true to form');
            
            // Add a descriptive note to flag that this is coming from the companion app
            const notesInput = document.createElement('input');
            notesInput.type = 'hidden';
            notesInput.name = 'notes';
            
            // Get any existing notes from the form
            let existingNotes = '';
            const notesField = form.querySelector('[name="notes"]');
            if (notesField && notesField.value) {
                existingNotes = notesField.value + ' ';
            }
            
            // Append companion app marker to notes
            notesInput.value = existingNotes + '[Submitted via companion app]';
            directForm.appendChild(notesInput);
            console.log('Added companion app marker to notes field');
            
            // Copy all form fields with improved handling for empty or missing values
            const formDataObj = new FormData(form);
            const formDataForLogging = {};
            
            formDataObj.forEach((value, key) => {
                // Skip the notes field since we've already handled it
                if (key === 'notes') {
                    return;
                }
                
                // For empty numeric fields, set them to an empty string
                // The server code will now handle these properly
                // We still include all fields, even empty ones
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = key;
                
                // Convert null to empty string
                if (value === null || value === undefined) {
                    input.value = '';
                    formDataForLogging[key] = '(empty)';
                } else {
                    input.value = value;
                    if (key === 'csrf_token') {
                        formDataForLogging[key] = value.substring(0, 10) + '...';
                    } else {
                        formDataForLogging[key] = value;
                    }
                }
                
                directForm.appendChild(input);
            });
            
            // Log the data we're sending to help debug
            console.log('Form data being submitted:', formDataForLogging);
            
            // Show the processing indicator before submitting if it exists
            const processingIndicator = document.getElementById('processingIndicator');
            if (processingIndicator) {
                console.log('Showing processing indicator');
                const bsModal = new bootstrap.Modal(processingIndicator);
                bsModal.show();
            }
            
            // Add to document and submit with extra safeguards
            document.body.appendChild(directForm);
            console.log('Form added to document, submitting now...');
            
            // Double timeout to ensure form submission works even with slow mobile processors
            setTimeout(() => {
                try {
                    console.log('Submitting form after first timeout');
                    
                    // Try-catch within the timeout for extra safety
                    try {
                        directForm.submit();
                        console.log('Form submitted successfully in first attempt');
                    } catch(innerError) {
                        console.error('First attempt failed:', innerError);
                        
                        // Second attempt with a different approach
                        setTimeout(() => {
                            console.log('Trying second submission attempt...');
                            try {
                                // Try a different submission technique if the first one failed
                                const submitEvent = document.createEvent('Event');
                                submitEvent.initEvent('submit', true, true);
                                directForm.dispatchEvent(submitEvent);
                                console.log('Form dispatched submit event');
                                
                                // Also try direct submission again
                                directForm.submit();
                                console.log('Second form.submit() called');
                            } catch(e2) {
                                console.error('Second submission attempt also failed:', e2);
                                // Last resort - redirect to regular form
                                window.location.href = '/self-care/wellness-check-in?is_pwa=true';
                            }
                        }, 200);
                    }
                } catch(e) {
                    console.error('Error in submission wrapper:', e);
                    // Fall back to the regular wellness check-in page
                    window.location.href = '/self-care/wellness-check-in?is_pwa=true';
                }
            }, 200); // Longer delay to ensure everything is ready
            return;
        }
        
        // Normal mode (browser): Use the API endpoint with JSON
        const apiUrl = '/self-care/api/wellness-check-in';
            
        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                ...sanitizedFormData,
                csrf_token: csrfToken,
                is_pwa: isStandalone
            }),
            credentials: 'include',
            mode: 'cors'
        })
        .catch(error => {
            console.error('Fetch error during wellness check-in:', error);
            throw error; // Re-throw to be caught by the main error handler
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Redirect to self-care index page on success
                window.location.href = '/self-care/';
            } else {
                console.error('Error submitting wellness check-in:', data.message);
                if (processingModal) {
                    const bsModal = bootstrap.Modal.getInstance(processingModal);
                    bsModal.hide();
                }
                
                if (submitBtn && submitText && loadingSpinner) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Submit Check-In';
                    loadingSpinner.classList.add('d-none');
                }
                
                // Show error alert
                const alertContainer = document.createElement('div');
                alertContainer.className = 'alert alert-danger alert-dismissible fade show mt-3';
                alertContainer.role = 'alert';
                alertContainer.innerHTML = `
                    <strong>Error!</strong> ${data.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                form.prepend(alertContainer);
            }
        })
        .catch(error => {
            console.error('Network error:', error);
            
            if (processingModal) {
                const bsModal = bootstrap.Modal.getInstance(processingModal);
                bsModal.hide();
            }
            
            if (submitBtn && submitText && loadingSpinner) {
                submitBtn.disabled = false;
                submitText.textContent = 'Submit Check-In';
                loadingSpinner.classList.add('d-none');
            }
            
            // Special handling for PWA connection issues
            if (isStandalone) {
                // Try one more time with a fallback approach for PWA mode
                console.log('Attempting fallback submission method for PWA');
                
                const formElement = document.createElement('form');
                formElement.method = 'post';
                formElement.action = '/self-care/api/wellness-check-in';
                formElement.style.display = 'none';
                
                // Add all form fields as hidden inputs with improved empty value handling
                for (const [key, value] of Object.entries(sanitizedFormData)) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    
                    // Convert null or undefined to empty string
                    if (value === null || value === undefined) {
                        input.value = '';
                    } else {
                        input.value = value;
                    }
                    
                    formElement.appendChild(input);
                }
                
                // Add CSRF token
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken;
                formElement.appendChild(csrfInput);
                
                // Add to document and submit
                document.body.appendChild(formElement);
                
                // We'll attempt this after showing the error and letting the user decide
                const alertContainer = document.createElement('div');
                alertContainer.className = 'alert alert-danger alert-dismissible fade show mt-3';
                alertContainer.role = 'alert';
                alertContainer.innerHTML = `
                    <strong>Network Error in PWA Mode!</strong> The app may be having trouble 
                    connecting to the server in standalone mode. You can try again or use the web browser instead.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Add retry button
                const retryButton = document.createElement('button');
                retryButton.className = 'btn btn-sm btn-primary mt-2';
                retryButton.textContent = 'Try Alternative Submission';
                retryButton.addEventListener('click', function() {
                    formElement.submit();
                });
                alertContainer.appendChild(retryButton);
                
                form.prepend(alertContainer);
            } else {
                // Regular browser mode error handling
                const alertContainer = document.createElement('div');
                alertContainer.className = 'alert alert-danger alert-dismissible fade show mt-3';
                alertContainer.role = 'alert';
                alertContainer.innerHTML = `
                    <strong>Network Error!</strong> Please check your connection and try again.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                form.prepend(alertContainer);
            }
        });
    });
}

/**
 * Makes an API request with CSRF token
 * This can be used for any API call needing CSRF protection
 */
function apiRequestWithCSRF(url, method, data) {
    return new Promise((resolve, reject) => {
        // Get CSRF token
        const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenMeta ? csrfTokenMeta.content : 
                         document.querySelector('input[name="csrf_token"]')?.value;
        
        if (!csrfToken) {
            reject(new Error('No CSRF token available. Please refresh the page.'));
            return;
        }
        
        // Add CSRF token to data
        const requestData = {
            ...data,
            csrf_token: csrfToken
        };
        
        // Make request
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => resolve(data))
        .catch(error => reject(error));
    });
}

/**
 * Display an error message on the form
 */
function showFormError(form, message) {
    // Remove any existing alerts
    const existingAlerts = form.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Add new alert
    const alertContainer = document.createElement('div');
    alertContainer.className = 'alert alert-danger alert-dismissible fade show mt-3';
    alertContainer.role = 'alert';
    alertContainer.innerHTML = `
        <strong>Error!</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    form.prepend(alertContainer);
}

/**
 * Reset the submit button state
 */
function resetSubmitButton(submitBtn, submitText, loadingSpinner) {
    if (submitBtn && submitText) {
        submitBtn.disabled = false;
        submitText.textContent = 'Submit Check-In';
    }
    
    if (loadingSpinner) {
        loadingSpinner.classList.add('d-none');
    }
}

/**
 * Hide the processing modal
 */
function hideProcessingModal(processingModal) {
    if (processingModal) {
        const bsModal = bootstrap.Modal.getInstance(processingModal);
        if (bsModal) {
            bsModal.hide();
        }
    }
}

/**
 * Setup wellness check-in form with mobile-friendly JSON API submission
 * Follows the same successful pattern as stress level check-in
 */
// Removed conflicting wellness check-in handlers to allow template handler to work