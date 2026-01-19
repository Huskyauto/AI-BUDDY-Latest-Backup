// Mobile wellness check-in using JSON format (like working stress logging)
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 Mobile wellness JSON handler loaded');
    
    // Only show debug elements on mobile devices
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth <= 768;
    
    let debugDiv = null;
    if (isMobile) {
        // Add a bright visual indicator ONLY for mobile
        debugDiv = document.createElement('div');
        debugDiv.style.cssText = `
            background: linear-gradient(45deg, #ff6b6b, #ffa500);
            color: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            font-weight: bold;
            text-align: center;
            border: 3px solid #fff;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        `;
        debugDiv.innerHTML = '📱 MOBILE JSON: Page loaded with JSON stress-logging pattern!';
    }
    
    const form = document.querySelector('#wellness-form');
    if (form) {
        // Only add debug div to mobile devices
        if (isMobile && debugDiv) {
            form.parentNode.insertBefore(debugDiv, form);
        }
        
        // Add JSON submit handler (like stress logging)
        function submitWellnessJSON() {
            if (isMobile && debugDiv) {
                debugDiv.innerHTML = '🚀 MOBILE JSON: Collecting form data...';
                debugDiv.style.background = 'linear-gradient(45deg, #4CAF50, #45a049)';
            }
            
            // Get all the form values
            const formData = new FormData(form);
            const jsonData = {};
            
            // Convert FormData to JSON object (like stress logging does)
            for (let [key, value] of formData.entries()) {
                jsonData[key] = parseInt(value) || 5; // Convert to integers
            }
            
            console.log('📊 Wellness data to send:', jsonData);
            if (isMobile && debugDiv) {
                debugDiv.innerHTML = '📊 MOBILE JSON: Sending data to /self-care/api/wellness-check-in';
            }
            
            // Send JSON request (exactly like stress logging)
            fetch('/self-care/api/wellness-check-in', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
                },
                body: JSON.stringify(jsonData)
            })
            .then(response => {
                console.log('📡 Response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('✅ Success response:', data);
                if (data.status === 'success') {
                    if (isMobile && debugDiv) {
                        debugDiv.innerHTML = '✅ MOBILE JSON: Wellness check-in saved successfully!';
                        debugDiv.style.background = 'linear-gradient(45deg, #28a745, #20c997)';
                    }
                    
                    // Redirect after success
                    setTimeout(() => {
                        window.location.href = '/self-care/';
                    }, 2000);
                } else {
                    throw new Error(data.message || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('❌ Error:', error);
                debugDiv.innerHTML = '❌ MOBILE JSON: Error - ' + error.message;
                debugDiv.style.background = 'linear-gradient(45deg, #dc3545, #bd2130)';
            });
        }
        
        // Override form submission
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            submitWellnessJSON();
        });
        
        // Add mobile-friendly touch button
        const touchButton = document.createElement('button');
        touchButton.type = 'button';
        touchButton.className = 'btn btn-success btn-lg w-100 mt-3';
        touchButton.innerHTML = '🎯 Mobile JSON Submit (Stress Pattern)';
        touchButton.style.cssText = `
            background: linear-gradient(45deg, #28a745, #20c997) !important;
            border: none !important;
            font-size: 18px !important;
            padding: 15px !important;
            margin-top: 15px !important;
        `;
        
        touchButton.addEventListener('click', submitWellnessJSON);
        touchButton.addEventListener('touchstart', submitWellnessJSON);
        touchButton.addEventListener('touchend', function(e) {
            e.preventDefault();
        });
        
        form.appendChild(touchButton);
        
        debugDiv.innerHTML = '✅ MOBILE JSON: Ready to submit using stress logging pattern!';
        debugDiv.style.background = 'linear-gradient(45deg, #17a2b8, #138496)';
    }
});