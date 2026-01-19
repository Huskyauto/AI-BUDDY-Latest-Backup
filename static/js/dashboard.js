document.addEventListener('DOMContentLoaded', function() {
    // CRITICAL: Completely prevent any auto-scrolling whatsoever
    if (window.history.scrollRestoration) {
        window.history.scrollRestoration = 'manual';
    }
    
    // IMPORTANT: Check for flag from CBT/therapy pages to prevent auto-scrolling
    const preventAutoScroll = sessionStorage.getItem('preventAutoScroll');
    if (preventAutoScroll === 'true') {
        console.log('Auto-scrolling explicitly prevented - maintaining user scroll position');
        // Clear the flag after using it
        sessionStorage.removeItem('preventAutoScroll');
    }
    
    // Emergency fix for auto-scroll issue
    // Do NOT automatically scroll to top - let user control their own scrolling
    // Critical issue reported by users - April 2025 update
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Mood selection handling
    const moodOptions = document.querySelectorAll('.mood-option');
    const saveMoodBtn = document.querySelector('#moodSaveBtn'); // Update selector to match the button
    const moodNotes = document.getElementById('moodNotes');
    const successMessage = document.getElementById('moodSaveSuccess');

    // Add click handlers for mood options
    moodOptions.forEach(option => {
        option.addEventListener('click', function() {
            moodOptions.forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');
        });
    });

    // Save mood handling
    if (saveMoodBtn) {
        saveMoodBtn.addEventListener('click', async function() {
            try {
                const selectedMood = document.querySelector('.mood-option.selected');
                if (!selectedMood) {
                    alert('Please select a mood before saving');
                    return;
                }

                // Get the mood label text
                const mood = selectedMood.querySelector('.mood-label').textContent;

                // Show loading state
                saveMoodBtn.disabled = true;
                const originalText = saveMoodBtn.textContent;
                saveMoodBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';

                // Send mood data to server
                const response = await fetch('/api/save-mood', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        mood: mood,
                        notes: moodNotes.value || ''
                    })
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    // Clear form
                    moodNotes.value = '';
                    moodOptions.forEach(opt => opt.classList.remove('selected'));

                    // Show success message
                    successMessage.classList.remove('d-none');
                    setTimeout(() => {
                        successMessage.classList.add('d-none');
                    }, 3000);

                    // Update mood visualization if we're on the analytics tab
                    const moodChart = document.getElementById('moodPatternChart');
                    if (moodChart) {
                        // Reinitialize the chart to show new data
                        createMoodChart();
                    }
                } else {
                    throw new Error(data.message || 'Failed to save mood');
                }
            } catch (error) {
                console.error('Error saving mood:', error);
                alert('Error saving mood: ' + error.message);
            } finally {
                // Reset button state
                saveMoodBtn.disabled = false;
                saveMoodBtn.textContent = 'Save Mood';
            }
        });
    }

    // Location tracking
    const locationTrackingBtn = document.querySelector('.location-status button');
    if (locationTrackingBtn) {
        locationTrackingBtn.addEventListener('click', function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    position => {
                        fetch('/api/start-location-tracking', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                this.textContent = 'Location Tracking Active';
                                this.classList.remove('btn-primary');
                                this.classList.add('btn-success');
                            }
                        })
                        .catch(error => console.error('Error:', error));
                    },
                    error => {
                        console.error('Error getting location:', error);
                        window.alert('Error accessing location. Please enable location services.');
                    }
                );
            } else {
                window.alert('Geolocation is not supported by this browser.');
            }
        });
    }
});