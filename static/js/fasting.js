// Fasting session management
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const fastingContainer = document.getElementById('fasting-container');
    const programsDiv = document.getElementById('fasting-programs');
    const extendedProgramsDiv = document.getElementById('extended-fasting-programs');
    const intermittentProgramsDiv = document.getElementById('intermittent-fasting-programs');
    const activeSessionDiv = document.getElementById('active-fasting-session');
    const activeIntermittentSessionDiv = document.getElementById('active-intermittent-session');
    const checkinForm = document.getElementById('checkin-form');

    // Function to update history display
    async function updateHistoryDisplay() {
        try {
            const historyResponse = await fetch('/api/fasting/history');
            const historyData = await historyResponse.json();
            console.log('Received history data:', historyData);

            const historyContainer = document.querySelector('.check-in-history');
            if (historyContainer) {
                historyContainer.innerHTML = '';  // Clear existing history

                if (historyData.check_ins && historyData.check_ins.length > 0) {
                    historyData.check_ins.forEach(checkIn => {
                        const checkInElement = document.createElement('div');
                        checkInElement.className = 'card mb-3';
                        const checkInDate = new Date(checkIn.check_in_time);
                        checkInElement.innerHTML = `
                            <div class="card-body">
                                <h6 class="card-title">Day ${checkIn.day_number} Check-in</h6>
                                <div class="row">
                                    <div class="col-md-6">
                                        <p><strong>Time:</strong> ${checkInDate.toLocaleString()}</p>
                                        <p><strong>Mood:</strong> ${checkIn.mood}</p>
                                        <p><strong>Energy Level:</strong> ${checkIn.energy_level}</p>
                                    </div>
                                    <div class="col-md-6">
                                        ${checkIn.weight ? `<p><strong>Weight:</strong> ${checkIn.weight}</p>` : ''}
                                        <p><strong>Symptoms:</strong> ${checkIn.symptoms && checkIn.symptoms.length > 0 ? checkIn.symptoms.join(', ') : 'None reported'}</p>
                                        ${checkIn.notes ? `<p><strong>Notes:</strong> ${checkIn.notes}</p>` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                        historyContainer.appendChild(checkInElement);
                    });
                } else {
                    historyContainer.innerHTML = '<div class="alert alert-info">No check-in history available yet.</div>';
                }
            }
        } catch (error) {
            console.error('Error updating history:', error);
            showNotification('Error loading history data', 'error');
        }
    }

    // Add event listeners to all start-fast buttons
    document.querySelectorAll('.start-fast').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const programId = this.dataset.programId;
            console.log('Starting fasting program:', programId);

            try {
                const response = await fetch('/api/fasting/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ program_id: programId })
                });

                const data = await response.json();
                console.log('Start fasting response:', data);

                if (data.status === 'success') {
                    // Show active session view and hide programs and tabs
                    document.getElementById('fasting-tabs').classList.add('d-none');
                    document.getElementById('fasting-tab-content').classList.add('d-none');
                    activeSessionDiv.classList.remove('d-none');

                    // Update program details
                    const programNameElement = activeSessionDiv.querySelector('.current-program-name');
                    if (programNameElement) {
                        programNameElement.textContent = data.program.name;
                    }

                    // Update day count
                    const currentDayElement = activeSessionDiv.querySelector('.current-day');
                    const totalDaysElement = activeSessionDiv.querySelector('.total-days');
                    if (currentDayElement && totalDaysElement) {
                        currentDayElement.textContent = data.program.current_day;
                        totalDaysElement.textContent = data.program.duration_days;
                    }

                    // Show check-in form for initial entry
                    if (checkinForm) {
                        checkinForm.classList.remove('d-none');
                    }

                    // Update history display
                    await updateHistoryDisplay();

                    showNotification('Fasting program started successfully! Please complete your first check-in.');
                } else {
                    showNotification(data.message || 'Failed to start fasting program', 'error');
                }
            } catch (error) {
                console.error('Error starting fasting program:', error);
                showNotification('An error occurred while starting the program', 'error');
            }
        });
    });

    // Single-click reset functionality
    const resetButton = document.getElementById('reset-fasting');
    if (resetButton) {
        resetButton.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/fasting/reset', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();
                if (data.status === 'success') {
                    // Show programs and tabs, hide active session immediately
                    document.getElementById('fasting-tabs').classList.remove('d-none');
                    document.getElementById('fasting-tab-content').classList.remove('d-none');
                    activeSessionDiv.classList.add('d-none');

                    // Clear form if it exists
                    if (checkinForm) {
                        checkinForm.reset();
                        checkinForm.classList.add('d-none');
                    }

                    // Clear history container
                    const historyContainer = document.querySelector('.check-in-history');
                    if (historyContainer) {
                        historyContainer.innerHTML = '';
                    }

                    // Remove any completion messages
                    const completionMessages = document.querySelectorAll('.completion-message');
                    completionMessages.forEach(msg => msg.remove());

                    showNotification('Fasting session reset successfully');

                    // Reload the page to ensure a clean state
                    window.location.reload();
                } else {
                    showNotification(data.message || 'Failed to reset fasting session', 'error');
                }
            } catch (error) {
                console.error('Error resetting fasting session:', error);
                showNotification('An error occurred while resetting the session', 'error');
            }
        });
    }

    // Handle check-in form submission
    if (checkinForm) {
        checkinForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            console.log('Submitting check-in form');

            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Submitting...';
            }

            try {
                const formData = {
                    mood: this.querySelector('select[name="mood"]').value,
                    energy_level: this.querySelector('select[name="energy_level"]').value,
                    weight: parseFloat(this.querySelector('input[name="weight"]').value) || null,
                    symptoms: Array.from(this.querySelectorAll('input[name="symptoms[]"]:checked'))
                        .map(cb => cb.value),
                    notes: this.querySelector('textarea[name="notes"]').value
                };

                console.log('Check-in form data:', formData);

                const response = await fetch('/api/fasting/checkin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();
                console.log('Check-in response:', data);

                if (data.status === 'success') {
                    // Hide form after successful submission
                    this.classList.add('d-none');

                    // Update history immediately with the received data
                    const historyContainer = document.querySelector('.check-in-history');
                    if (historyContainer && data.history) {
                        historyContainer.innerHTML = '';
                        data.history.forEach(checkIn => {
                            const checkInElement = document.createElement('div');
                            checkInElement.className = 'card mb-3';
                            const checkInDate = new Date(checkIn.check_in_time);
                            checkInElement.innerHTML = `
                                <div class="card-body">
                                    <h6 class="card-title">Day ${checkIn.day_number} Check-in</h6>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <p><strong>Time:</strong> ${checkInDate.toLocaleString()}</p>
                                            <p><strong>Mood:</strong> ${checkIn.mood}</p>
                                            <p><strong>Energy Level:</strong> ${checkIn.energy_level}</p>
                                        </div>
                                        <div class="col-md-6">
                                            ${checkIn.weight ? `<p><strong>Weight:</strong> ${checkIn.weight}</p>` : ''}
                                            <p><strong>Symptoms:</strong> ${checkIn.symptoms && checkIn.symptoms.length > 0 ? checkIn.symptoms.join(', ') : 'None reported'}</p>
                                            ${checkIn.notes ? `<p><strong>Notes:</strong> ${checkIn.notes}</p>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `;
                            historyContainer.appendChild(checkInElement);
                        });
                    }

                    // First remove any existing completion message
                    const existingMessage = document.querySelector('.completion-message');
                    if (existingMessage) {
                        existingMessage.remove();
                    }
                    
                    // Show completion message
                    const messageContainer = document.createElement('div');
                    messageContainer.className = 'completion-message';
                    
                    const completedMessageDiv = document.createElement('div');
                    completedMessageDiv.className = 'alert alert-success mt-3';
                    
                    if (data.next_day) {
                        // Not the last day
                        completedMessageDiv.innerHTML = `
                            <i class="fas fa-check-circle me-2"></i>
                            <strong>Day ${data.day_completed} completed!</strong> Return tomorrow for Day ${data.next_day}.
                        `;
                    } else {
                        // Last day completed
                        completedMessageDiv.innerHTML = `
                            <i class="fas fa-check-circle me-2"></i>
                            <strong>Congratulations!</strong> You've completed your fasting program!
                        `;
                    }
                    
                    messageContainer.appendChild(completedMessageDiv);
                    
                    // Insert message before history section
                    const historySection = document.querySelector('.check-in-history');
                    if (historySection && historySection.parentNode) {
                        historySection.parentNode.insertBefore(messageContainer, historySection);
                    } else {
                        // Fallback insertion
                        this.parentNode.appendChild(messageContainer);
                    }

                    showNotification('Check-in recorded successfully!');
                } else {
                    showNotification(data.message || 'Failed to record check-in', 'error');
                }
            } catch (error) {
                console.error('Error submitting check-in:', error);
                showNotification('An error occurred while submitting check-in', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Complete Today\'s Check-in';
                }
            }
        });
    }

    // Function to show notifications
    function showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        if (notification) {
            notification.textContent = message;
            notification.className = `alert alert-${type} fade show`;

            setTimeout(() => {
                notification.className = 'alert d-none';
            }, 5000);
        }
    }

    // Handle starting intermittent fasting
    document.querySelectorAll('.start-intermittent-fast').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const programId = this.dataset.programId;
            console.log('Starting intermittent fasting program:', programId);

            try {
                const response = await fetch('/api/fasting/intermittent/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ program_id: programId })
                });

                const data = await response.json();
                console.log('Start intermittent fasting response:', data);

                if (data.status === 'success') {
                    // Show active session view and hide programs and tabs
                    document.getElementById('fasting-tabs').classList.add('d-none');
                    document.getElementById('fasting-tab-content').classList.add('d-none');
                    activeIntermittentSessionDiv.classList.remove('d-none');

                    // Update program details
                    const programNameElement = activeIntermittentSessionDiv.querySelector('.current-intermittent-program-name');
                    if (programNameElement) {
                        programNameElement.textContent = data.program.name;
                    }

                    // Initialize timer
                    initializeIntermittentTimer(data.session.start_date, data.program.name);

                    showNotification('Intermittent fasting started successfully!');
                } else {
                    showNotification(data.message || 'Failed to start intermittent fasting', 'error');
                }
            } catch (error) {
                console.error('Error starting intermittent fasting:', error);
                showNotification('An error occurred while starting the program', 'error');
            }
        });
    });

    // Initialize intermittent fasting timer
    function initializeIntermittentTimer(startDateStr, programName) {
        const startDate = new Date(startDateStr);
        
        // Extract hours from program name more robustly (e.g., "16-Hour Fast" or "16 Hour Fast" or just "16")
        let targetHours = 16; // Default to 16 hours if parsing fails
        const hourMatch = programName.match(/(\d+)/);
        if (hourMatch && hourMatch[1]) {
            targetHours = parseInt(hourMatch[1]);
        }
        console.log(`Starting ${targetHours}-hour fast from ${startDate.toLocaleString()}`);
        
        const endDate = new Date(startDate.getTime() + (targetHours * 60 * 60 * 1000));
        
        // Update start and end time displays
        const startTimeElement = activeIntermittentSessionDiv.querySelector('.intermittent-start-time');
        const endTimeElement = activeIntermittentSessionDiv.querySelector('.intermittent-end-time');
        
        if (startTimeElement) {
            startTimeElement.textContent = startDate.toLocaleString();
        }
        if (endTimeElement) {
            endTimeElement.textContent = endDate.toLocaleString();
        }
        
        // Benefits text based on stage
        updateIntermittentBenefits(0); // Initialize with 0 hours
        
        // Start the timer and store it globally
        // First clear any existing timer
        if (window.intermittentTimerInterval) {
            clearInterval(window.intermittentTimerInterval);
        }
        
        window.intermittentTimerInterval = setInterval(() => {
            const now = new Date();
            let timeRemaining = endDate - now;
            
            if (timeRemaining <= 0) {
                // Timer completed
                clearInterval(window.intermittentTimerInterval);
                document.getElementById('intermittent-hours-remaining').textContent = "00:00:00";
                document.getElementById('intermittent-progress-bar').style.width = "100%";
                document.querySelector('.intermittent-progress-percent').textContent = "100%";
                showNotification('Your intermittent fast is complete! You can now end your session.');
                return;
            }
            
            // Calculate hours, minutes, seconds
            const hours = Math.floor(timeRemaining / (1000 * 60 * 60));
            timeRemaining -= hours * (1000 * 60 * 60);
            const minutes = Math.floor(timeRemaining / (1000 * 60));
            timeRemaining -= minutes * (1000 * 60);
            const seconds = Math.floor(timeRemaining / 1000);
            
            // Format time remaining
            const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            document.getElementById('intermittent-hours-remaining').textContent = timeString;
            
            // Calculate progress
            const elapsedTime = now - startDate;
            const totalTime = targetHours * 60 * 60 * 1000;
            const progressPercent = Math.min(100, Math.round((elapsedTime / totalTime) * 100));
            
            document.getElementById('intermittent-progress-bar').style.width = `${progressPercent}%`;
            document.querySelector('.intermittent-progress-percent').textContent = `${progressPercent}%`;
            
            // Update benefits based on elapsed hours
            const elapsedHours = elapsedTime / (1000 * 60 * 60);
            updateIntermittentBenefits(elapsedHours);
            
        }, 1000);
    }
    
    // Update benefits text based on fasting duration
    function updateIntermittentBenefits(elapsedHours) {
        const benefitsElement = document.getElementById('intermittent-benefits-text');
        if (!benefitsElement) return;
        
        if (elapsedHours < 4) {
            benefitsElement.textContent = "Your body is using up stored sugars (glycogen). Blood sugar and insulin levels are starting to drop.";
        } else if (elapsedHours < 8) {
            benefitsElement.textContent = "Your body is beginning to shift into fat-burning mode. Insulin levels are dropping significantly.";
        } else if (elapsedHours < 12) {
            benefitsElement.textContent = "Fat burning increases. Your body is producing ketones for energy.";
        } else if (elapsedHours < 16) {
            benefitsElement.textContent = "Autophagy (cellular cleanup) begins to increase. Significant fat-burning and ketone production.";
        } else if (elapsedHours < 20) {
            benefitsElement.textContent = "Enhanced autophagy and cellular repair. Growth hormone levels increase. Maximum fat burning.";
        } else {
            benefitsElement.textContent = "Maximum autophagy benefits. Human growth hormone levels significantly increased. Extended cellular repair.";
        }
    }
    
    // Handle starting the intermittent fasting timer
    const startIntermittentTimerButton = document.getElementById('start-intermittent-timer');
    if (startIntermittentTimerButton) {
        startIntermittentTimerButton.addEventListener('click', async function() {
            try {
                // First, fetch the active session data to get the start date
                const response = await fetch('/api/fasting/intermittent/active');
                const data = await response.json();
                
                if (data.status !== 'success' || !data.session) {
                    console.error('No active intermittent fasting session found');
                    showNotification('No active fasting session found', 'error');
                    return;
                }
                
                // Get the program name from the UI
                const programName = document.querySelector('.current-intermittent-program-name').textContent;
                
                // Use the start date from the API response
                const startDateStr = data.session.start_date;
                
                if (!startDateStr) {
                    console.error('Start date not found in API response');
                    showNotification('Cannot start timer: session start date not found', 'error');
                    return;
                }
                
                // Initialize the timer with the program name and start time from API
                initializeIntermittentTimer(startDateStr, programName);
                
                // Show notification
                showNotification('Fasting timer started! Your countdown has begun.');
                
                // Disable the start button after clicking
                this.disabled = true;
            } catch (error) {
                console.error('Error starting intermittent fasting timer:', error);
                showNotification('An error occurred while starting the timer', 'error');
            }
        });
    }
    
    // Handle ending intermittent fasting
    const endIntermittentButton = document.getElementById('end-intermittent-fast');
    if (endIntermittentButton) {
        endIntermittentButton.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/fasting/intermittent/end', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                console.log('End intermittent fasting response:', data);
                
                // Clear any active timer
                if (window.intermittentTimerInterval) {
                    clearInterval(window.intermittentTimerInterval);
                    window.intermittentTimerInterval = null;
                }
                
                if (data.status === 'success') {
                    showNotification(`Intermittent fasting completed! You fasted for ${data.session.hours_fasted} hours (${data.session.completion_percent}% of your goal).`);
                    
                    // Create completion message
                    const completionMsg = document.createElement('div');
                    completionMsg.className = 'alert alert-success mt-3';
                    completionMsg.innerHTML = `
                        <h4>Fast Completed!</h4>
                        <p>You fasted for ${data.session.hours_fasted} hours (${data.session.completion_percent}% of your ${data.session.target_hours}-hour goal).</p>
                        <p>Your body has experienced cellular cleanup and repair benefits during this time.</p>
                        <button class="btn btn-primary mt-2" id="return-to-programs">Start Another Fast</button>
                    `;
                    
                    // Replace timer display with completion message
                    const timerDisplay = document.querySelector('.time-remaining-display').closest('.card-body');
                    if (timerDisplay) {
                        timerDisplay.innerHTML = '';
                        timerDisplay.appendChild(completionMsg);
                        
                        // Add event listener to return button
                        document.getElementById('return-to-programs').addEventListener('click', function() {
                            // Show tabs and content first, then reload
                            document.getElementById('fasting-tabs').classList.remove('d-none');
                            document.getElementById('fasting-tab-content').classList.remove('d-none');
                            activeIntermittentSessionDiv.classList.add('d-none');
                            window.location.reload();
                        });
                    }
                } else {
                    showNotification(data.message || 'Failed to end intermittent fasting session', 'error');
                }
            } catch (error) {
                console.error('Error ending intermittent fasting:', error);
                showNotification('An error occurred while ending the session', 'error');
            }
        });
    }
    
    // Handle reset intermittent fasting
    const resetIntermittentButton = document.getElementById('reset-intermittent-fasting');
    if (resetIntermittentButton) {
        resetIntermittentButton.addEventListener('click', async function() {
            if (confirm('Are you sure you want to cancel your current intermittent fasting session?')) {
                try {
                    const response = await fetch('/api/fasting/intermittent/reset', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    // Clear any active timer
                    if (window.intermittentTimerInterval) {
                        clearInterval(window.intermittentTimerInterval);
                        window.intermittentTimerInterval = null;
                    }
                    
                    if (data.status === 'success') {
                        // Show fasting tabs and content
                        document.getElementById('fasting-tabs').classList.remove('d-none');
                        document.getElementById('fasting-tab-content').classList.remove('d-none');
                        activeIntermittentSessionDiv.classList.add('d-none');
                        
                        showNotification('Intermittent fasting session cancelled successfully');
                        window.location.reload();
                    } else {
                        showNotification(data.message || 'Failed to cancel intermittent fasting session', 'error');
                    }
                } catch (error) {
                    console.error('Error cancelling intermittent fasting session:', error);
                    showNotification('An error occurred while cancelling the session', 'error');
                }
            }
        });
    }
    
    // Function to check and show active sessions
    async function checkActiveSessions() {
        try {
            // Check for active extended fasting session
            const extendedResponse = await fetch('/api/fasting/active');
            const extendedData = await extendedResponse.json();
            
            if (extendedData.status === 'success' && extendedData.has_active_session && extendedData.session) {
                // Show active extended fasting session
                document.getElementById('fasting-tabs').classList.add('d-none');
                document.getElementById('fasting-tab-content').classList.add('d-none');
                activeSessionDiv.classList.remove('d-none');
                
                // Update program details
                const programNameElement = activeSessionDiv.querySelector('.current-program-name');
                if (programNameElement) {
                    programNameElement.textContent = extendedData.session.program.name;
                }
                
                // Update day count
                const currentDayElement = activeSessionDiv.querySelector('.current-day');
                const totalDaysElement = activeSessionDiv.querySelector('.total-days');
                if (currentDayElement && totalDaysElement) {
                    currentDayElement.textContent = extendedData.session.current_day;
                    totalDaysElement.textContent = extendedData.session.total_days;
                }
                
                // Log data for debugging
                console.log("Active session data:", extendedData);
                
                // Update history display
                await updateHistoryDisplay();
                
                // If check-in not done for today, show form 
                // extendedData.checkin_today is a flag that's true if check-in is done, false otherwise
                console.log("Check-in status for today:", extendedData.checkin_today);
                
                // First, remove any existing completion message to avoid duplicates
                const existingMessage = document.querySelector('.completion-message');
                if (existingMessage) {
                    existingMessage.remove();
                }
                
                if (checkinForm) {
                    if (extendedData.checkin_today === true) {
                        // Check-in is done, hide the form
                        checkinForm.classList.add('d-none');
                        
                        // Show a message that today's check-in is complete
                        const completedMessageDiv = document.createElement('div');
                        completedMessageDiv.className = 'alert alert-success mt-3 completion-message';
                        const nextDay = extendedData.session.current_day + 1;
                        const isLastDay = nextDay > extendedData.session.total_days;
                        
                        // Different message if this is the last day
                        if (isLastDay) {
                            completedMessageDiv.innerHTML = `
                                <i class="fas fa-check-circle me-2"></i>
                                <strong>Congratulations!</strong> You've completed your fasting program!
                            `;
                        } else {
                            completedMessageDiv.innerHTML = `
                                <i class="fas fa-check-circle me-2"></i>
                                <strong>Day ${extendedData.session.current_day} completed!</strong> Return tomorrow for Day ${nextDay}.
                            `;
                        }
                        
                        // Insert message before history section
                        const historySection = document.querySelector('.check-in-history');
                        if (historySection && historySection.parentNode) {
                            historySection.parentNode.insertBefore(completedMessageDiv, historySection);
                        } else {
                            // Fallback insertion
                            checkinForm.parentNode.insertBefore(completedMessageDiv, checkinForm.nextSibling);
                        }
                    } else {
                        // Check-in not done, show the form
                        checkinForm.classList.remove('d-none');
                    }
                }
                
                return true;
            }
            
            // Check for active intermittent fasting session
            const intermittentResponse = await fetch('/api/fasting/intermittent/active');
            const intermittentData = await intermittentResponse.json();
            
            if (intermittentData.status === 'success' && intermittentData.has_active_session && intermittentData.session) {
                // Show active intermittent fasting session
                document.getElementById('fasting-tabs').classList.add('d-none');
                document.getElementById('fasting-tab-content').classList.add('d-none');
                activeIntermittentSessionDiv.classList.remove('d-none');
                
                // Update program details
                const programNameElement = activeIntermittentSessionDiv.querySelector('.current-intermittent-program-name');
                if (programNameElement) {
                    programNameElement.textContent = intermittentData.session.program.name;
                }
                
                // Log data for debugging
                console.log("Active intermittent session data:", intermittentData);
                console.log("Intermittent fasting check-in status:", intermittentData.checkin_today);
                
                // Initialize timer
                initializeIntermittentTimer(intermittentData.session.start_date, intermittentData.session.program.name);
                
                // If it's already completed, show a message
                if (intermittentData.checkin_today === true) {
                    const completedMessageDiv = document.createElement('div');
                    completedMessageDiv.className = 'alert alert-success mt-3';
                    completedMessageDiv.textContent = 'Today\'s fast is completed! Great job!';
                    activeIntermittentSessionDiv.appendChild(completedMessageDiv);
                }
                
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Error checking active sessions:', error);
            return false;
        }
    }

    // Check for active session and load history on page load
    checkActiveSessions();
});