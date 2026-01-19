document.addEventListener('DOMContentLoaded', async function() {
    // Prevent auto-scrolling when the page loads
    if (window.history.scrollRestoration) {
        window.history.scrollRestoration = 'manual';
    }
    
    // Track the scroll position before starting the exercise
    let scrollPositionBeforeExercise = 0;
    
    const startBreathingBtn = document.getElementById('start-breathing');
    const stopBreathingBtn = document.getElementById('stop-breathing');
    const exerciseTypeSelect = document.getElementById('breathing-exercise-type');
    const durationSelect = document.getElementById('breathing-duration');
    const breathingDisplay = document.querySelector('.breathing-display');
    const breathingInstruction = document.getElementById('breathing-instruction');
    const progressBar = document.querySelector('.breathing-display .progress-bar');
    let currentExercise = null;
    let isExerciseRunning = false;
    let timerInterval = null;
    let startTime = null;
    let endTime = null;
    let exerciseDuration = 5; // Default 5 minutes
    
    // Timer display elements
    let timerDisplay = null;

    // Volume control
    const volumeControl = document.getElementById('breathing-volume');
    let speechSynthesis = window.speechSynthesis;
    let currentUtterance = null;
    
    // Notification function
    function showNotification(message, type = 'success') {
        // Create notification element if it doesn't exist
        let notification = document.getElementById('breathing-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'breathing-notification';
            notification.className = 'alert';
            notification.style.position = 'fixed';
            notification.style.top = '20px';
            notification.style.right = '20px';
            notification.style.maxWidth = '300px';
            notification.style.zIndex = '9999';
            notification.style.transition = 'all 0.3s ease-in-out';
            notification.style.opacity = '0';
            document.body.appendChild(notification);
        }
        
        // Set type-specific styles
        notification.className = 'alert alert-' + (type === 'error' ? 'danger' : 'success');
        notification.textContent = message;
        
        // Show notification
        notification.style.opacity = '1';
        
        // Hide after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }

    // Description toggle
    exerciseTypeSelect.addEventListener('change', function() {
        const boxDesc = document.getElementById('box-description');
        const desc478 = document.getElementById('478-description');

        if (this.value === 'box') {
            boxDesc.style.display = 'block';
            desc478.style.display = 'none';
        } else {
            boxDesc.style.display = 'none';
            desc478.style.display = 'block';
        }
    });

    // Speech synthesis setup
    function speak(text, options = {}) {
        if (currentUtterance) {
            speechSynthesis.cancel();
        }

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = options.rate || 0.9;
        utterance.pitch = options.pitch || 1.0;
        utterance.volume = volumeControl.value;

        // Prevent scrolling on speech
        utterance.onboundary = (event) => {
            event.preventDefault();
            return false;
        };

        currentUtterance = utterance;
        speechSynthesis.speak(utterance);

        return new Promise((resolve) => {
            utterance.onend = resolve;
        });
    }

    // Progress bar animation
    function updateProgress(percent) {
        progressBar.style.width = `${percent}%`;
    }

    // Initialize breathing display
    function initializeBreathingDisplay() {
        if (!breathingDisplay) return;

        // Make breathing display visible
        breathingDisplay.classList.remove('d-none');
        // Position it properly
        breathingDisplay.style.right = '20px';
        breathingDisplay.style.left = 'auto';
        breathingDisplay.style.transform = 'translateY(-50%)';
    }

    // Prevent scroll during exercise
    function preventScroll(e) {
        e.preventDefault();
    }

    // Create a timer promise
    function timer(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Create a function to format time (mm:ss)
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    }
    
    // Update the timer display
    function updateTimerDisplay() {
        if (!timerDisplay) return;
        
        const now = new Date().getTime();
        const timeLeft = Math.max(0, Math.floor((endTime - now) / 1000));
        
        // Format time as mm:ss
        const formattedTime = formatTime(timeLeft);
        timerDisplay.textContent = formattedTime;
        
        // Update progress bar
        const totalDuration = exerciseDuration * 60; // Total seconds
        const progress = Math.min(100, Math.max(0, (timeLeft / totalDuration) * 100));
        progressBar.style.width = `${progress}%`;
        
        // If time is up, we'll set a flag but not stop immediately
        // This allows the current breathing cycle to complete
        if (timeLeft <= 0 && isExerciseRunning) {
            // Just set a flag to indicate time is up, but let the current cycle finish
            window.shouldEndAfterCurrentCycle = true;
        }
    }
    
    async function startBreathingExercise() {
        try {
            // Store current scroll position before starting
            // No longer saving scroll position to prevent auto-scrolling
            console.log('Auto-scrolling disabled - not saving position');
            console.log("Saving scroll position:", scrollPositionBeforeExercise);
            
            const exerciseType = exerciseTypeSelect.value;
            exerciseDuration = parseInt(durationSelect.value, 10);
            
            // Get the exercise data with duration parameter
            const response = await fetch(`/api/breathing/guidance/${exerciseType}?duration=${exerciseDuration}`);
            const data = await response.json();

            if (data.status === 'success') {
                currentExercise = data.exercise;
                isExerciseRunning = true;
                startBreathingBtn.disabled = true;
                stopBreathingBtn.disabled = false;

                // Initialize display position
                initializeBreathingDisplay();
                
                // Set up timer display but don't start countdown yet
                timerDisplay = document.getElementById('breathing-time-remaining');
                // Initialize with formatted time
                timerDisplay.textContent = formatTime(exerciseDuration * 60);
                // Show timer but we'll start it after introduction
                const timerContainer = document.querySelector('.timer-display');
                timerContainer.style.opacity = '1';

                // Prevent scrolling during exercise
                document.body.style.overflow = 'hidden';
                window.addEventListener('scroll', preventScroll, { passive: false });

                // Start the exercise
                console.debug('Starting breathing exercise:', exerciseType, 'for', exerciseDuration, 'minutes');

                // Play concise introduction based on exercise type
                await speak("Welcome to your breathing exercise.", { rate: 0.8 });
                await timer(1000);
                await speak("Find a comfortable position and we'll begin shortly.", { rate: 0.8 });
                await timer(1500);
                
                if (exerciseType === 'box') {
                    // Box breathing (4-4-4-4) introduction - shortened
                    await speak("Box Breathing uses a simple 4-4-4-4 pattern to reduce stress and improve focus.", { rate: 0.8 });
                    await timer(1000);
                    await speak("You'll inhale for 4, hold for 4, exhale for 4, and hold empty for 4 seconds.", { rate: 0.8 });
                    await timer(2000);
                } else {
                    // 4-7-8 breathing introduction - shortened
                    await speak("The 4-7-8 Breathing technique helps with stress reduction and better sleep.", { rate: 0.8 });
                    await timer(1000);
                    await speak("You'll inhale for 4, hold for 7, and exhale for 8 seconds, creating a natural calming effect.", { rate: 0.8 });
                    await timer(2000);
                }
                
                await speak(`This session will last for ${exerciseDuration} minutes. Let your eyes close or maintain a soft gaze, and follow my guidance through each breath cycle.`, { rate: 0.8 });
                await timer(2000);
                await speak("We'll begin in a few seconds. Remember to breathe deeply but comfortably, never straining.", { rate: 0.8 });
                await timer(3000);

                // Now start the timer after the introduction
                startTime = new Date().getTime();
                endTime = startTime + (exerciseDuration * 60 * 1000); // Convert minutes to milliseconds
                
                // Start timer updates
                if (timerInterval) {
                    clearInterval(timerInterval);
                }
                timerInterval = setInterval(updateTimerDisplay, 1000);
                updateTimerDisplay(); // Initial update

                // Start main exercise loop after intro is complete
                runBreathingCycle();
            }
        } catch (error) {
            console.error('Error starting breathing exercise:', error);
            showNotification('Failed to start breathing exercise', 'error');
        }
    }

    async function runBreathingCycle() {
        if (!isExerciseRunning || !currentExercise) return;

        // Make sure shouldEndAfterCurrentCycle is reset
        window.shouldEndAfterCurrentCycle = false;
        
        const cycle = currentExercise.steps.main;
        // Log the exercise details to help with debugging
        console.log("Breathing exercise details:", {
            type: currentExercise.type,
            name: currentExercise.name,
            isTypeField478: currentExercise.type === '478',
            isNameField478: currentExercise.name && currentExercise.name.includes('4-7-8')
        });
        
        // Multiple detection methods for 4-7-8 breathing pattern:
        // 1. Check the type field (primary method)
        // 2. Check if name includes "4-7-8" (backup method)
        // 3. Check if repeat_interval is 19 (fallback based on timing)
        const is478 = currentExercise.type === '478' || 
                     (currentExercise.name && currentExercise.name.includes('4-7-8')) ||
                     (currentExercise.steps && currentExercise.steps.main && 
                      currentExercise.steps.main.repeat_interval === 19);

        // Begin with a first cycle announcement
        if (is478) {
            console.log("Starting exercise: 4-7-8 breathing pattern");
            await speak("Starting your 4-7-8 breathing cycle now.", { rate: 0.8 });
        } else {
            console.log("Starting exercise: box breathing pattern");
            await speak("Starting your box breathing cycle now.", { rate: 0.8 });
        }
        await timer(1000);

        let cycleCount = 0;
        
        while (isExerciseRunning) {
            cycleCount++;
            
            if (is478) {
                // 4-7-8 Breathing Pattern with precise timing and more guidance
                breathingInstruction.textContent = "Inhale through your nose - 4 seconds";
                await speak("Inhale slowly through your nose, filling your lungs from bottom to top", { rate: 0.8 });
                await timer(4000); // 4 second inhale

                breathingInstruction.textContent = "Hold your breath - 7 seconds";
                await speak("Hold your breath gently, feeling the oxygen nourish your body", { rate: 0.8 });
                await timer(7000); // 7 second hold

                breathingInstruction.textContent = "Exhale completely through mouth - 8 seconds";
                await speak("Exhale completely through your mouth with a whooshing sound, releasing all tension", { rate: 0.8 });
                await timer(8000); // 8 second exhale

                await timer(1000); // Brief pause between cycles
                
                // Every few cycles, provide encouraging feedback
                if (cycleCount % 3 === 0 && isExerciseRunning) {
                    breathingInstruction.textContent = "Continue the rhythm";
                    await speak("You're doing great. Feel your body becoming more relaxed with each cycle.", { rate: 0.8 });
                    await timer(2000);
                }
            } else {
                // Box Breathing (4-4-4-4) with enhanced guidance
                breathingInstruction.textContent = "Inhale through your nose - 4 seconds";
                await speak("Inhale deeply through your nose, expanding your diaphragm", { rate: 0.8 });
                await timer(4000);

                breathingInstruction.textContent = "Hold your breath - 4 seconds";
                await speak("Hold your breath comfortably, maintaining steady pressure", { rate: 0.8 });
                await timer(4000);

                breathingInstruction.textContent = "Exhale through your mouth - 4 seconds";
                await speak("Exhale slowly through your mouth, releasing all the air", { rate: 0.8 });
                await timer(4000);

                breathingInstruction.textContent = "Hold empty - 4 seconds";
                await speak("Hold with empty lungs, staying relaxed", { rate: 0.8 });
                await timer(4000);
                
                // Every few cycles, provide encouraging feedback and technique reminders
                if (cycleCount % 3 === 0 && isExerciseRunning) {
                    breathingInstruction.textContent = "Continue the square pattern";
                    await speak("Excellent. With each cycle, your mind becomes more focused and your body more calm.", { rate: 0.8 });
                    await timer(2000);
                }
            }

            // Update progress (optional, can be removed if not needed)
            updateProgress(50); // Simplified progress indication
            
            // After completing a full cycle, check if we should end
            if (window.shouldEndAfterCurrentCycle) {
                // Add a closing message
                breathingInstruction.textContent = "Completing exercise";
                await speak("You've completed your breathing exercise. Take a moment to notice how you feel now.", { rate: 0.8 });
                await timer(2000);
                await speak("When you're ready, you can open your eyes and gently return to your surroundings.", { rate: 0.8 });
                await timer(2000);
                
                // Stop the exercise now that we've completed this cycle
                stopBreathingExercise();
                break;
            }
        }
    }

    function stopBreathingExercise() {
        isExerciseRunning = false;
        
        // Clear the timer interval
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        
        // Reset timer display
        if (timerDisplay) {
            timerDisplay.textContent = '';
            const timerContainer = document.querySelector('.timer-display');
            timerContainer.style.opacity = '0';
        }
        
        // Stop speech synthesis
        if (currentUtterance) {
            speechSynthesis.cancel();
        }
        
        breathingDisplay.classList.add('d-none');
        startBreathingBtn.disabled = false;
        stopBreathingBtn.disabled = true;
        updateProgress(0);
        breathingInstruction.textContent = '';

        // Show completion message if exercise wasn't canceled early
        if (endTime && new Date().getTime() >= endTime) {
            // Exercise completed successfully
            showNotification('Breathing exercise completed successfully!', 'success');
        }
        
        // Reset timer variables
        startTime = null;
        endTime = null;

        // Re-enable scrolling without forcing scroll position
        document.body.style.overflow = '';
        window.removeEventListener('scroll', preventScroll);

        // No longer restoring scroll position to prevent auto-scrolling
        console.log("Auto-scrolling disabled - not restoring scroll position");
    }

    // Event listeners
    startBreathingBtn.addEventListener('click', startBreathingExercise);
    stopBreathingBtn.addEventListener('click', stopBreathingExercise);

    volumeControl.addEventListener('input', function() {
        if (currentUtterance) {
            currentUtterance.volume = this.value;
        }
    });
});