/**
 * Mobile Wellness Check-in Fix
 * Simplified handler that works exactly like desktop
 */

document.addEventListener('DOMContentLoaded', function() {
    const wellnessForm = document.getElementById('wellness-check-in-form');
    
    if (wellnessForm) {
        console.log('Mobile wellness fix: Form found, setting up simple handler');
        
        // Remove any existing handlers
        const newForm = wellnessForm.cloneNode(true);
        wellnessForm.parentNode.replaceChild(newForm, wellnessForm);
        
        // Add simple submit handler
        newForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            console.log('Mobile wellness fix: Form submitted');
            
            // Show loading
            const submitBtn = document.getElementById('submit-btn');
            const submitText = document.getElementById('submit-text');
            const loadingSpinner = document.getElementById('loading-spinner');
            
            if (submitBtn && submitText && loadingSpinner) {
                submitBtn.disabled = true;
                submitText.textContent = 'Submitting...';
                loadingSpinner.classList.remove('d-none');
            }
            
            // Submit to PWA endpoint with form data (not JSON)
            const formData = new FormData(newForm);
            
            fetch('/self-care/pwa/wellness-check-in', {
                method: 'POST',
                body: formData,
                credentials: 'include'
            })
            .then(response => response.json())
            .then(result => {
                if (result.status === 'success') {
                    // Show success
                    const alert = document.createElement('div');
                    alert.className = 'alert alert-success mt-3';
                    alert.innerHTML = '<strong>Success!</strong> Your wellness check-in has been recorded.';
                    newForm.prepend(alert);
                    
                    // Reset form
                    newForm.reset();
                    
                    // Reload page after delay
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    throw new Error(result.message || 'Submission failed');
                }
            })
            .catch(error => {
                console.error('Mobile wellness fix error:', error);
                
                // Show error
                const alert = document.createElement('div');
                alert.className = 'alert alert-danger mt-3';
                alert.innerHTML = '<strong>Error!</strong> Please try again.';
                newForm.prepend(alert);
            })
            .finally(() => {
                // Reset button
                if (submitBtn && submitText && loadingSpinner) {
                    submitBtn.disabled = false;
                    submitText.textContent = 'Submit Check-in';
                    loadingSpinner.classList.add('d-none');
                }
            });
        });
        
        console.log('Mobile wellness fix: Handler attached successfully');
    }
});