// Meditation audio controller
document.addEventListener('DOMContentLoaded', async function() {
    let audioContext;
    let soundInterval;
    let remainingTime;
    let timerInterval;
    let guidanceTimeouts = [];
    let toneInitialized = false;
    let selectedVoice = null;
    let meditationActive = false;
    let originalScrollPosition = 0;
    let isScrollLocked = false;
    
    // Helper function to get CSRF token from meta tag
    function getCsrfToken() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        return csrfToken ? csrfToken.getAttribute('content') : '';
    }
    
    // Load current stress level data from the API
    async function loadStressLevelData() {
        try {
            const stressLevelElement = document.getElementById('current-stress-level');
            if (stressLevelElement) {
                console.debug('Fetching current stress level from API...');
                const response = await fetch('/api/meditation/stress');
                const data = await response.json();
                
                if (data.status === 'success' && data.current_stress !== null) {
                    stressLevelElement.textContent = Math.round(data.current_stress);
                    
                    // Add data source as a title attribute for tooltip
                    if (data.data_source) {
                        stressLevelElement.title = `Data source: ${data.data_source}`;
                    }
                    
                    console.debug('Stress level data loaded successfully:', data.current_stress);
                } else {
                    console.debug('No stress level data available:', data.message || 'Unknown error');
                    stressLevelElement.textContent = '--';
                    stressLevelElement.title = 'No stress data available';
                }
            }
        } catch (error) {
            console.error('Error loading stress level data:', error);
            const stressLevelElement = document.getElementById('current-stress-level');
            if (stressLevelElement) {
                stressLevelElement.textContent = '--';
                stressLevelElement.title = 'Failed to load stress data';
            }
        }
    }
    
    // Load initial stress level data
    loadStressLevelData();
    
    // Add functionality for reset stats button
    const resetStatsBtn = document.getElementById('reset-stats');
    if (resetStatsBtn) {
        resetStatsBtn.addEventListener('click', async function() {
            if (confirm('Are you sure you want to reset your meditation stats? This cannot be undone.')) {
                try {
                    const response = await fetch('/api/meditation/stats/reset', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        // Update the stats display with zeros
                        const totalSessionsEl = document.getElementById('total-sessions');
                        const totalMinutesEl = document.getElementById('total-minutes');
                        
                        if (totalSessionsEl) totalSessionsEl.textContent = '0';
                        if (totalMinutesEl) totalMinutesEl.textContent = '0';
                        
                        showNotification('Meditation stats have been reset', 'success');
                    } else {
                        console.error('Error resetting stats:', data.message);
                        showNotification('Error resetting meditation stats', 'error');
                    }
                } catch (error) {
                    console.error('Error in resetStats:', error);
                    showNotification('Error resetting meditation stats', 'error');
                }
            }
        });
    }

    // Scroll Lock Implementation
    function lockScroll() {
        if (!isScrollLocked) {
            // Save current scroll position so we can maintain it
            originalScrollPosition = window.pageYOffset || document.documentElement.scrollTop;
            console.debug('Saving scroll position:', originalScrollPosition);

            // Keep scrollbar visible but prevent scrolling while maintaining position
            document.documentElement.style.overflow = 'hidden';
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            
            // Set top position to current scroll position to avoid jumping
            document.body.style.top = `-${originalScrollPosition}px`;

            // Add a class to handle scrollbar visibility
            document.body.classList.add('scroll-locked');

            isScrollLocked = true;
            console.debug('Scroll locked - position preserved at:', originalScrollPosition);
        }
    }

    function unlockScroll() {
        if (isScrollLocked) {
            // Remove all scroll lock styles
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
            document.body.style.top = '';
            document.body.classList.remove('scroll-locked');

            // Reset the overflow on html element as well
            document.documentElement.style.overflow = '';

            // Restore scroll position 
            console.debug('Restoring scroll position to:', originalScrollPosition);
            
            // Check if we're using the global scroll manager to avoid conflicts
            if (window.ScrollManager) {
                console.log('Using global scroll manager to avoid auto-scrolling issues');
                // Don't try to restore position ourselves, let it respect the global settings
            } else {
                // Only if ScrollManager isn't present, restore the scroll position manually
                window.scrollTo({
                    top: originalScrollPosition,
                    behavior: 'auto' // Use 'auto' instead of 'smooth' to prevent visible scrolling
                });
            }
            
            isScrollLocked = false;
            console.debug('Scroll unlocked and position restored');
        }
    }

    // Initialize voice settings
    async function initializeVoice() {
        return new Promise((resolve) => {
            // First attempt to get voices
            const voices = window.speechSynthesis.getVoices();
            if (voices && voices.length > 0) {
                selectedVoice = selectPreferredVoice(voices);
                resolve(selectedVoice);
                return;
            }

            // If no voices initially, wait for them to load
            window.speechSynthesis.onvoiceschanged = () => {
                const voices = window.speechSynthesis.getVoices();
                selectedVoice = selectPreferredVoice(voices);
                resolve(selectedVoice);
            };
            
            // Trigger a getVoices call to start loading process
            window.speechSynthesis.getVoices();
        });
    }
    
    // Helper to select the preferred voice from available options
    function selectPreferredVoice(voices) {
        if (!voices || voices.length === 0) return null;
        
        // Try to find a female or British English voice first
        return voices.find(voice =>
            voice.name.toLowerCase().includes('female') ||
            voice.name.toLowerCase().includes('samantha') ||
            voice.lang.startsWith('en-GB')
        ) || voices.find(voice => voice.lang.startsWith('en-')) || voices[0];
    }

    // Function to speak text
    async function speakText(text, rate = 0.9, pitch = 1.0) {
        return new Promise((resolve) => {
            try {
                console.debug('Speaking text:', text);
                
                // Reset any ongoing speech to prevent conflicts
                if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
                    window.speechSynthesis.cancel();
                    // Small delay to ensure cancellation completes
                    setTimeout(() => processSpeech(), 100);
                } else {
                    processSpeech();
                }
                
                function processSpeech() {
                    try {
                        const utterance = new SpeechSynthesisUtterance(text);
                        
                        // Set properties
                        if (selectedVoice) utterance.voice = selectedVoice;
                        utterance.rate = rate;
                        utterance.pitch = pitch;
                        utterance.volume = 0.9; // Slightly louder
                        
                        // Show guidance in right panel
                        const guidanceArea = document.getElementById('meditation-guidance');
                        if (guidanceArea) {
                            guidanceArea.textContent = text;
                            guidanceArea.style.opacity = '1';
                            
                            // Add fade-in animation for smoother transitions
                            guidanceArea.style.transition = 'opacity 0.5s ease-in';
                        }
                        
                        // Calculate reasonable timeout based on text length (avg reading speed)
                        // Average reading speed is about 150-160 words per minute
                        const wordCount = text.split(/\s+/).length;
                        const estimatedDuration = Math.max(4000, wordCount * 600); // Min 4 seconds, ~600ms per word
                        
                        // Create a safety timeout that's more generous
                        let safetyTimeout = setTimeout(() => {
                            console.warn('Speech may have stalled, resolving promise and continuing...');
                            fadeOutGuidance();
                            resolve();
                        }, estimatedDuration); // Dynamic timeout based on text length
                        
                        // Handle speech end event
                        utterance.onend = () => {
                            clearTimeout(safetyTimeout);
                            console.debug('Speech completed:', text);
                            
                            // Add slight delay before fading out text for better readability
                            setTimeout(() => {
                                fadeOutGuidance();
                                resolve();
                            }, 300);
                        };
                        
                        // Handle speech errors with retry mechanism
                        utterance.onerror = (event) => {
                            clearTimeout(safetyTimeout);
                            console.error('Speech error:', event);
                            
                            // If meditation has been stopped, just clean up
                            if (!meditationActive) {
                                fadeOutGuidance();
                                resolve();
                                return;
                            }
                            
                            // Wait briefly and try again with a simpler approach
                            setTimeout(() => {
                                try {
                                    // Create new utterance with simplified settings
                                    const retryUtterance = new SpeechSynthesisUtterance(text);
                                    retryUtterance.rate = 0.9;
                                    retryUtterance.volume = 1.0;
                                    
                                    // Don't set voice on retry - use default
                                    retryUtterance.onend = () => {
                                        setTimeout(() => {
                                            fadeOutGuidance();
                                            resolve();
                                        }, 300);
                                    };
                                    
                                    retryUtterance.onerror = () => {
                                        // Give up after retry
                                        fadeOutGuidance();
                                        resolve();
                                    };
                                    
                                    window.speechSynthesis.speak(retryUtterance);
                                } catch (retryError) {
                                    console.error('Error in speech retry:', retryError);
                                    fadeOutGuidance();
                                    resolve();
                                }
                            }, 300);
                        };
                        
                        // Start speaking
                        window.speechSynthesis.speak(utterance);
                    } catch (innerError) {
                        console.error('Error in processSpeech:', innerError);
                        fadeOutGuidance();
                        resolve();
                    }
                }
                
                // Helper function to fade out guidance text
                function fadeOutGuidance() {
                    const guidanceArea = document.getElementById('meditation-guidance');
                    if (guidanceArea) {
                        // Ensure smooth fade-out animation
                        guidanceArea.style.transition = 'opacity 0.5s ease-out';
                        guidanceArea.style.opacity = '0';
                    }
                }
                
            } catch (error) {
                console.error('Error in speakText:', error);
                const guidanceArea = document.getElementById('meditation-guidance');
                if (guidanceArea) {
                    guidanceArea.style.opacity = '0';
                }
                resolve();
            }
        });
    }

    // Timer display update
    function updateTimerDisplay() {
        if (remainingTime !== undefined) {
            const minutes = Math.floor(remainingTime / 60);
            const seconds = remainingTime % 60;
            const timeDisplay = document.getElementById('time-remaining');
            if (timeDisplay) {
                timeDisplay.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                const timerDisplay = document.querySelector('.timer-display');
                if (timerDisplay) {
                    timerDisplay.style.opacity = '1';
                }
            }
        }
    }

    // Initialize audio context and components
    async function initializeAudio() {
        try {
            // Create audio context if not already initialized
            if (!audioContext) {
                console.debug('Creating new AudioContext in initializeAudio');
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // Resume audio context if suspended
            if (audioContext.state === 'suspended') {
                console.debug('Resuming audio context in initializeAudio');
                await audioContext.resume();
            }
            
            // Initialize Tone.js if not already done
            if (!toneInitialized) {
                console.debug('Initializing Tone.js in initializeAudio');
                // Make sure Tone uses our AudioContext
                Tone.setContext(audioContext);
                await Tone.start();
                console.debug('Tone.js initialized with context:', Tone.getContext().state);
                toneInitialized = true;
            }

            console.debug('Creating Tone.js components');
            
            // Create and configure reverb
            const reverb = new Tone.Reverb({
                decay: 8,
                wet: 0.6,
                preDelay: 0.2
            }).toDestination();
            
            // Make sure reverb is ready before continuing
            await reverb.generate();
            console.debug('Reverb generated successfully');

            // Create and connect delay
            const delay = new Tone.FeedbackDelay({
                delayTime: "8n",
                feedback: 0.4,
                wet: 0.2
            }).connect(reverb);

            // Create and connect chorus
            const chorus = new Tone.Chorus({
                frequency: 0.5,
                delayTime: 3.5,
                depth: 0.7,
                wet: 0.5
            }).connect(delay);

            // Create noise and filter
            const noise = new Tone.Noise("brown").connect(reverb);
            const filter = new Tone.Filter({
                type: "lowpass",
                frequency: 800
            }).connect(reverb);

            // Create synth for ambient sounds
            const ambientSynth = new Tone.PolySynth(Tone.Synth, {
                volume: -15,
                oscillator: {
                    type: "triangle"
                },
                envelope: {
                    attack: 0.5,
                    decay: 0.5,
                    sustain: 0.8,
                    release: 2.0
                }
            }).connect(chorus);

            console.debug('Audio components initialized successfully');
            
            return {
                reverb,
                delay,
                chorus,
                noise,
                filter,
                ambientSynth
            };

        } catch (error) {
            console.error('Error initializing audio:', error);
            return null;
        }
    }

    // Initialize meditation session
    try {
        console.debug('Starting meditation initialization');
        await initializeVoice();
        const audioComponents = await initializeAudio();

        if (audioComponents) {
            const {ambientSynth, noise, reverb, filter} = audioComponents;

            // Sound generators with improved error handling
            const soundGenerators = {
                rain: function() {
                    try {
                        console.debug('Starting rain sound');
                        // First try to stop if it's already running
                        if (noise.state === 'started') {
                            noise.stop();
                        }
                        // Reset any existing connections
                        noise.disconnect();
                        // Configure noise type and filter
                        noise.type = "pink";
                        filter.frequency.value = 2000;
                        // Connect and start
                        noise.connect(filter);
                        noise.start();
                        console.debug('Rain sound started successfully');
                    } catch (error) {
                        console.error('Error starting rain sound:', error);
                    }
                },
                
                wind: function() {
                    try {
                        console.debug('Starting wind sound');
                        // First try to stop if it's already running
                        if (noise.state === 'started') {
                            noise.stop();
                        }
                        // Reset any existing connections
                        noise.disconnect();
                        // Configure noise type and filter
                        noise.type = "white";
                        filter.frequency.value = 400;
                        // Connect and start
                        noise.connect(filter);
                        noise.start();
                        console.debug('Wind sound started successfully');
                    } catch (error) {
                        console.error('Error starting wind sound:', error);
                    }
                },
                
                water: function() {
                    try {
                        console.debug('Starting water sound');
                        // First try to stop if it's already running
                        if (noise.state === 'started') {
                            noise.stop();
                        }
                        // Reset any existing connections
                        noise.disconnect();
                        // Configure noise type and filter
                        noise.type = "brown";
                        filter.frequency.value = 800;
                        // Connect and start
                        noise.connect(filter);
                        noise.start();
                        console.debug('Water sound started successfully');
                    } catch (error) {
                        console.error('Error starting water sound:', error);
                    }
                },
                
                brown: function() {
                    try {
                        console.debug('Starting brown noise');
                        // First try to stop if it's already running
                        if (noise.state === 'started') {
                            noise.stop();
                        }
                        // Reset any existing connections
                        noise.disconnect();
                        // Configure noise type
                        noise.type = "brown";
                        filter.frequency.value = 400;
                        // Connect and start
                        noise.connect(reverb);
                        noise.start();
                        console.debug('Brown noise started successfully');
                    } catch (error) {
                        console.error('Error starting brown noise:', error);
                    }
                },
                
                ambient: function() {
                    console.debug('Starting ambient pad sound');
                    playAmbientPad();
                }
            };

            function playAmbientPad() {
                try {
                    // Make sure Tone.js is running
                    if (Tone.Transport.state !== 'started') {
                        console.debug('Starting Tone.js transport for ambient pad');
                        Tone.Transport.start();
                    }
                    
                    // Get current time reference from Tone.js
                    const now = Tone.now();
                    
                    // Use a simple chord for the ambient pad
                    const notes = ["C4", "E4", "G4"];
                    console.debug('Playing ambient notes:', notes);
                    
                    // Clear any existing interval to prevent multiple sounds
                    if (soundInterval) {
                        clearInterval(soundInterval);
                        soundInterval = null;
                    }
                    
                    // Create a safety check to make sure synth is available
                    if (!ambientSynth || typeof ambientSynth.triggerAttackRelease !== 'function') {
                        console.error('Ambient synth not properly initialized');
                        return;
                    }
                    
                    // Play initial chord
                    ambientSynth.triggerAttackRelease(notes, "4n", now);
                    
                    // Set up interval to continue playing the chord
                    soundInterval = setInterval(() => {
                        try {
                            ambientSynth.triggerAttackRelease(notes, "4n", Tone.now());
                        } catch (error) {
                            console.error('Error in ambient pad interval:', error);
                            // Don't clear interval, let it try again
                        }
                    }, 2000);
                    
                    console.debug('Ambient pad playing successfully');
                } catch (error) {
                    console.error('Error playing ambient pad:', error);
                }
            }

            // Stop current sound
            function stopCurrentSound() {
                console.debug('Stopping current sound');
                // Clear any running interval for ambient sounds
                if (soundInterval) {
                    clearInterval(soundInterval);
                    soundInterval = null;
                }
                
                // Stop all synth sounds
                try {
                    if (ambientSynth && typeof ambientSynth.releaseAll === 'function') {
                        console.debug('Releasing all synth notes');
                        ambientSynth.releaseAll();
                    }
                } catch (error) {
                    console.error('Error releasing synth notes:', error);
                }
                
                // Stop noise generator
                try {
                    if (noise && typeof noise.stop === 'function') {
                        console.debug('Stopping noise generator');
                        // Check if noise is already stopped to avoid errors
                        if (noise.state === 'started') {
                            noise.stop();
                        }
                    }
                } catch (error) {
                    console.error('Error stopping noise generator:', error);
                }
            }

            // Add event listeners for test sound buttons
            document.querySelectorAll('.test-sound').forEach(button => {
                button.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const soundType = e.target.getAttribute('data-sound');
                    console.debug(`Testing sound: ${soundType}`);
                    
                    try {
                        // Make sure audio is initialized and tone.js is ready
                        if (audioContext && audioContext.state === 'suspended') {
                            console.debug('Resuming audio context for test sound');
                            await audioContext.resume();
                        }
                        
                        if (!toneInitialized) {
                            console.debug('Initializing Tone.js for test sound');
                            await Tone.start();
                            toneInitialized = true;
                        }
                        
                        if (Tone.Transport.state !== 'started') {
                            console.debug('Starting Tone.js transport for test sound');
                            Tone.Transport.start();
                        }
                        
                        // Stop any current sound first
                        stopCurrentSound();
                        
                        // Play the requested sound
                        if (soundGenerators[soundType]) {
                            // Add small delay to ensure everything is ready
                            setTimeout(() => {
                                soundGenerators[soundType]();
                                
                                // Auto-stop test sound after 3 seconds
                                setTimeout(() => {
                                    console.debug('Auto-stopping test sound');
                                    stopCurrentSound();
                                }, 3000);
                            }, 100);
                        } else {
                            console.error(`Sound generator not found for: ${soundType}`);
                        }
                    } catch (error) {
                        console.error('Error testing sound:', error);
                    }
                });
            });
            
            // Start meditation session
            async function startMeditation(duration) {
                try {
                    console.debug('Starting meditation setup for duration:', duration);
                    meditationActive = true;
                    lockScroll();  // Lock scroll at start

                    if (audioContext && audioContext.state === 'suspended') {
                        console.debug('Resuming audio context');
                        await audioContext.resume();
                    }

                    if (!toneInitialized) {
                        console.debug('Initializing Tone.js');
                        await Tone.start();
                        toneInitialized = true;
                    }

                    // Setup UI
                    const startBtn = document.getElementById('start-meditation');
                    const stopBtn = document.getElementById('stop-meditation');
                    
                    if (startBtn) startBtn.disabled = true;
                    if (stopBtn) stopBtn.disabled = false;

                    // Start backend session
                    console.debug('Starting backend session');
                    const startResponse = await fetch('/api/meditation/start', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            duration: duration,
                            type: 'vipassana'
                        })
                    });

                    const startData = await startResponse.json();
                    if (startData.status !== 'success') {
                        throw new Error('Failed to start meditation session');
                    }

                    console.debug('Backend session started:', startData);

                    // Start background sound
                    console.debug('Starting background sound');
                    let selectedSound = 'brown'; // Default to brown noise
                    
                    const selectedRadio = document.querySelector('input[name="background-sound"]:checked');
                    if (selectedRadio) {
                        selectedSound = selectedRadio.value;
                        console.debug('Selected sound from radio:', selectedSound);
                    } else {
                        console.debug('No sound selected, using default:', selectedSound);
                    }
                    
                    try {
                        if (soundGenerators[selectedSound]) {
                            console.debug('Starting sound generator for:', selectedSound);
                            // Force a small wait before starting sound to ensure audio context is ready
                            await new Promise(resolve => setTimeout(resolve, 300));
                            
                            // Make sure Tone.js is properly initialized before playing sounds
                            if (!toneInitialized) {
                                console.debug('Reinitializing Tone.js before playing sound');
                                await Tone.start();
                                toneInitialized = true;
                            }
                            
                            if (Tone.Transport.state !== 'started') {
                                console.debug('Starting Tone.js transport');
                                Tone.Transport.start();
                            }
                            
                            // Now try to play the sound
                            soundGenerators[selectedSound]();
                            console.debug('Sound generator started successfully');
                        } else {
                            console.error('Sound generator not found for:', selectedSound);
                        }
                    } catch (error) {
                        console.error('Error starting sound generator:', error);
                        // Continue with meditation even if sound fails
                    }

                    // Play initial guidance with improved reliability
                    console.debug('Starting initial guidance');
                    const initialGuidance = [
                        "Welcome to your meditation session. Find a comfortable seated position.",
                        "Take a moment to settle in, allowing your body to be at ease.",
                        "Gently close your eyes and bring your attention to your breath.",
                        "Notice the natural rhythm of your breathing, without trying to change it.",
                        "Throughout this session, I'll provide gentle reminders to help maintain your focus.",
                        "If you notice your mind wandering, that's perfectly normal.",
                        "Simply acknowledge any thoughts and gently return your attention to your breath.",
                        "Let's begin our practice together."
                    ];

                    // Create a more reliable intro guidance experience
                    for (let i = 0; i < initialGuidance.length; i++) {
                        if (!meditationActive) {
                            console.debug('Meditation stopped during intro');
                            return;
                        }
                        
                        const text = initialGuidance[i];
                        console.debug(`Playing intro guidance (${i+1}/${initialGuidance.length}): ${text}`);
                        
                        try {
                            // Make sure speech synthesis is ready
                            if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
                                console.debug('Cancelling previous speech before new intro phrase');
                                window.speechSynthesis.cancel();
                                // Wait a moment for cancellation to complete
                                await new Promise(resolve => setTimeout(resolve, 300));
                            }
                            
                            // Pre-display the text with fade-in to ensure text appears even if speech fails
                            const guidanceArea = document.getElementById('meditation-guidance');
                            if (guidanceArea) {
                                // Ensure any previous fade-out is complete
                                guidanceArea.style.transition = 'opacity 0.5s ease-in';
                                guidanceArea.textContent = text;
                                guidanceArea.style.opacity = '1';
                            }
                            
                            // Use a simpler approach for important intro guidance
                            const utterance = new SpeechSynthesisUtterance(text);
                            
                            // Use more reliable default settings for intro
                            utterance.rate = 0.9;
                            utterance.volume = 1.0;
                            
                            // Only use selected voice if it has been verified to work
                            if (selectedVoice && selectedVoice.localService) {
                                utterance.voice = selectedVoice;
                            }
                            
                            // Calculate a reasonable duration based on text length
                            const wordCount = text.split(/\s+/).length;
                            const phraseDuration = Math.max(2000, wordCount * 600);
                            
                            // Use a Promise race to ensure we continue even if speech fails
                            await Promise.race([
                                // Promise for the speech to complete normally
                                new Promise(resolve => {
                                    utterance.onend = () => {
                                        console.debug(`Intro phrase ${i+1} completed successfully`);
                                        resolve();
                                    };
                                    
                                    utterance.onerror = (event) => {
                                        console.error(`Intro phrase ${i+1} speech error:`, event);
                                        resolve(); // Resolve anyway to continue
                                    };
                                    
                                    window.speechSynthesis.speak(utterance);
                                }),
                                
                                // Backup timeout promise to ensure we don't get stuck
                                new Promise(resolve => setTimeout(() => {
                                    console.debug(`Intro phrase ${i+1} timeout safety triggered`);
                                    resolve();
                                }, phraseDuration + 1000))
                            ]);
                            
                            // Allow a brief pause for the text to be visible before fading
                            await new Promise(resolve => setTimeout(resolve, 500));
                            
                            // Fade out text
                            if (guidanceArea) {
                                guidanceArea.style.transition = 'opacity 0.5s ease-out';
                                guidanceArea.style.opacity = '0';
                            }
                            
                            // Small gap between phrases
                            await new Promise(resolve => setTimeout(resolve, 300));
                            
                        } catch (error) {
                            console.error(`Error in intro guidance phrase ${i+1}:`, error);
                            // Continue with next phrase regardless of error
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                    }

                    // Start timer AFTER intro completes
                    console.debug('Starting meditation timer after intro');
                    const startTime = new Date();
                    
                    // Clear any existing timer first
                    if (timerInterval) {
                        console.debug('Clearing existing timer interval');
                        clearInterval(timerInterval);
                        timerInterval = null;
                    }
                    
                    // Set the initial timer value
                    remainingTime = duration * 60;
                    
                    // Update the display immediately to show the correct time
                    updateTimerDisplay();
                    
                    // Show the timer display
                    const timerDisplay = document.querySelector('.timer-display');
                    if (timerDisplay) {
                        timerDisplay.style.opacity = '1';
                    }
                    
                    console.debug('Creating new timer interval with duration:', duration, 'minutes');
                    // Create a new timer interval
                    timerInterval = setInterval(() => {
                        // Decrement time and update display
                        remainingTime--;
                        updateTimerDisplay();
                        
                        // Check if time is up
                        if (remainingTime <= 0) {
                            console.debug('Timer reached zero, completing meditation');
                            completeMeditation(startTime, duration);
                        }
                    }, 1000);

                    // Schedule periodic guidance (every 2.5 minutes)
                    const periodicGuidance = [
                        "Gently return your attention to your breath",
                        "Notice the sensation of breathing in and out",
                        "Let thoughts come and go, maintaining your awareness",
                        "Feel the rise and fall of your chest",
                        "Observe any tension in your body and let it soften",
                        "Stay present with each breath",
                        "If your mind has wandered, gently bring it back",
                        "Continue breathing mindfully"
                    ];

                    const intervalMs = 150000; // 2.5 minutes
                    let currentTime = intervalMs;

                    console.debug('Scheduling periodic guidance');
                    while (currentTime < (duration * 60 * 1000) - 30000) {
                        const timeoutDuration = currentTime;
                        const timeout = setTimeout(async () => {
                            try {
                                if (!meditationActive) return;
                                
                                // Select a random guidance phrase
                                const phrase = periodicGuidance[
                                    Math.floor(Math.random() * periodicGuidance.length)
                                ];
                                console.debug(`Playing periodic guidance: ${phrase}`);
                                
                                // Use more reliable approach for periodic guidance too
                                // Make sure speech synthesis is ready
                                if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
                                    console.debug('Cancelling previous speech before periodic guidance');
                                    window.speechSynthesis.cancel();
                                    await new Promise(resolve => setTimeout(resolve, 300));
                                }
                                
                                // Pre-display the text with fade-in
                                const guidanceArea = document.getElementById('meditation-guidance');
                                if (guidanceArea) {
                                    guidanceArea.style.transition = 'opacity 0.5s ease-in';
                                    guidanceArea.textContent = phrase;
                                    guidanceArea.style.opacity = '1';
                                }
                                
                                // Use simpler approach for reliability
                                const utterance = new SpeechSynthesisUtterance(phrase);
                                utterance.rate = 0.9;
                                utterance.volume = 1.0;
                                
                                // Calculate reasonable duration
                                const wordCount = phrase.split(/\s+/).length;
                                const phraseDuration = Math.max(2000, wordCount * 600);
                                
                                // Use Promise.race for reliability
                                await Promise.race([
                                    new Promise(resolve => {
                                        utterance.onend = () => {
                                            console.debug('Periodic guidance completed successfully');
                                            resolve();
                                        };
                                        
                                        utterance.onerror = (event) => {
                                            console.error('Periodic guidance speech error:', event);
                                            resolve(); // Resolve anyway to continue
                                        };
                                        
                                        window.speechSynthesis.speak(utterance);
                                    }),
                                    
                                    // Backup timeout
                                    new Promise(resolve => setTimeout(() => {
                                        console.debug('Periodic guidance timeout safety triggered');
                                        resolve();
                                    }, phraseDuration + 1000))
                                ]);
                                
                                // Allow text to be visible before fading
                                await new Promise(resolve => setTimeout(resolve, 600));
                                
                                // Fade out text
                                if (guidanceArea) {
                                    guidanceArea.style.transition = 'opacity 0.5s ease-out';
                                    guidanceArea.style.opacity = '0';
                                }
                                
                            } catch (error) {
                                console.error('Error playing periodic guidance:', error);
                            }
                        }, timeoutDuration);

                        guidanceTimeouts.push(timeout);
                        currentTime += intervalMs;
                    }

                    // Schedule ending guidance (30 seconds before end)
                    const totalDurationMs = duration * 60 * 1000;

                    const endingGuidance = [
                        "We're approaching the end of our meditation.",
                        "Take a few deep breaths, noticing how your body feels now.",
                        "Begin to bring gentle movement back to your fingers and toes.",
                        "When you're ready, slowly open your eyes.",
                        "Take a moment to appreciate the peace you've created."
                    ];

                    const endingTimeout = setTimeout(async () => {
                        try {
                            if (!meditationActive) return;
                            console.debug('Playing ending guidance');
                            
                            // Use the same reliable approach for ending guidance
                            for (let i = 0; i < endingGuidance.length; i++) {
                                if (!meditationActive) return;
                                
                                const text = endingGuidance[i];
                                console.debug(`Playing ending guidance (${i+1}/${endingGuidance.length}): ${text}`);
                                
                                // Make sure speech synthesis is ready
                                if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
                                    console.debug('Cancelling previous speech before new ending phrase');
                                    window.speechSynthesis.cancel();
                                    await new Promise(resolve => setTimeout(resolve, 300));
                                }
                                
                                // Pre-display the text to ensure it appears even if speech fails
                                const guidanceArea = document.getElementById('meditation-guidance');
                                if (guidanceArea) {
                                    guidanceArea.style.transition = 'opacity 0.5s ease-in';
                                    guidanceArea.textContent = text;
                                    guidanceArea.style.opacity = '1';
                                }
                                
                                // Use simpler approach for reliability
                                const utterance = new SpeechSynthesisUtterance(text);
                                utterance.rate = 0.9;
                                utterance.volume = 1.0;
                                
                                // Calculate reasonable duration based on text length
                                const wordCount = text.split(/\s+/).length;
                                const phraseDuration = Math.max(2000, wordCount * 600);
                                
                                // Use Promise.race to ensure we continue even if speech fails
                                await Promise.race([
                                    new Promise(resolve => {
                                        utterance.onend = () => {
                                            console.debug(`Ending phrase ${i+1} completed successfully`);
                                            resolve();
                                        };
                                        
                                        utterance.onerror = (event) => {
                                            console.error(`Ending phrase ${i+1} speech error:`, event);
                                            resolve(); // Resolve anyway to continue
                                        };
                                        
                                        window.speechSynthesis.speak(utterance);
                                    }),
                                    
                                    // Backup timeout
                                    new Promise(resolve => setTimeout(() => {
                                        console.debug(`Ending phrase ${i+1} timeout safety triggered`);
                                        resolve();
                                    }, phraseDuration + 1000))
                                ]);
                                
                                // Allow text to be visible before fading
                                await new Promise(resolve => setTimeout(resolve, 500));
                                
                                // Fade out text
                                if (guidanceArea) {
                                    guidanceArea.style.transition = 'opacity 0.5s ease-out';
                                    guidanceArea.style.opacity = '0';
                                }
                                
                                // Small gap between phrases
                                await new Promise(resolve => setTimeout(resolve, 300));
                            }
                        } catch (error) {
                            console.error('Error playing ending guidance:', error);
                        }
                    }, totalDurationMs - 30000);

                    guidanceTimeouts.push(endingTimeout);

                } catch (error) {
                    console.error('Error starting meditation:', error);
                    showNotification('Failed to start meditation session', 'error');
                    meditationActive = false;
                    unlockScroll();  // Ensure scroll is unlocked on error
                }
            }

            // Stop meditation session
            function stopMeditation() {
                console.debug('Stopping meditation session');
                if (!meditationActive) return;
                
                meditationActive = false;
                unlockScroll();
                
                // Cancel speech synthesis
                window.speechSynthesis.cancel();
                
                // Clear timer interval
                if (timerInterval) {
                    clearInterval(timerInterval);
                    timerInterval = null;
                }
                
                // Clear all guidance timeouts
                guidanceTimeouts.forEach(timeout => clearTimeout(timeout));
                guidanceTimeouts = [];
                
                // Stop current sound
                stopCurrentSound();
                
                // Reset UI
                const startBtn = document.getElementById('start-meditation');
                const stopBtn = document.getElementById('stop-meditation');
                
                if (startBtn) startBtn.disabled = false;
                if (stopBtn) stopBtn.disabled = true;
                
                // Hide timer
                const timerDisplay = document.querySelector('.timer-display');
                if (timerDisplay) {
                    timerDisplay.style.opacity = '0';
                }
                
                // Clear guidance text
                const guidanceArea = document.getElementById('meditation-guidance');
                if (guidanceArea) {
                    guidanceArea.textContent = '';
                    guidanceArea.style.opacity = '0';
                }
            }
            
            async function completeMeditation(startTime, duration) {
                console.debug('Completing meditation session');
                meditationActive = false;
                clearInterval(timerInterval);
                stopCurrentSound();
                window.speechSynthesis.cancel();

                // Reset UI elements
                const startBtn = document.getElementById('start-meditation');
                const stopBtn = document.getElementById('stop-meditation');
                
                if (startBtn) startBtn.disabled = false;
                if (stopBtn) stopBtn.disabled = true;
                
                const timerDisplay = document.querySelector('.timer-display');
                if (timerDisplay) {
                    timerDisplay.style.opacity = '0';
                }
                
                const guidanceArea = document.getElementById('meditation-guidance');
                if (guidanceArea) {
                    guidanceArea.textContent = '';
                    guidanceArea.style.opacity = '0';
                }

                try {
                    const endTime = new Date();
                    const actualDurationMs = endTime - startTime;
                    const actualDurationMin = Math.max(1, Math.round(actualDurationMs / (60 * 1000)));

                    console.debug(`Meditation completed - Duration: ${actualDurationMin} minutes`);

                    // Complete meditation session and update stats
                    const response = await fetch('/api/meditation/complete', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            duration: actualDurationMin,
                            start_time: startTime.toISOString(),
                            end_time: endTime.toISOString()
                        })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        console.debug('Session completed successfully', data);
                        
                        // Update stats display
                        if (data.stats) {
                            const totalSessionsEl = document.getElementById('total-sessions');
                            const totalMinutesEl = document.getElementById('total-minutes');
                            
                            if (totalSessionsEl) totalSessionsEl.textContent = data.stats.total_sessions || '0';
                            if (totalMinutesEl) totalMinutesEl.textContent = data.stats.total_minutes || '0';
                        }
                        
                        // Show completion notification
                        showNotification(`Meditation completed (${actualDurationMin} minutes)`, 'success');
                    } else {
                        console.error('Error completing session:', data.message);
                        showNotification('Error saving meditation session', 'error');
                    }
                } catch (error) {
                    console.error('Error in completeMeditation:', error);
                    showNotification('Error saving meditation session', 'error');
                } finally {
                    unlockScroll();  // Ensure scroll is unlocked
                }
            }

            // Shows notification
            function showNotification(message, type = 'info') {
                console.debug(`Showing notification: ${message} (${type})`);
                // Create notification container if it doesn't exist
                let notificationsContainer = document.getElementById('notifications-container');
                if (!notificationsContainer) {
                    notificationsContainer = document.createElement('div');
                    notificationsContainer.id = 'notifications-container';
                    notificationsContainer.style.position = 'fixed';
                    notificationsContainer.style.top = '20px';
                    notificationsContainer.style.right = '20px';
                    notificationsContainer.style.zIndex = '9999';
                    document.body.appendChild(notificationsContainer);
                }
                
                // Create notification element
                const notification = document.createElement('div');
                notification.className = `alert alert-${type} alert-dismissible fade show`;
                notification.innerHTML = `
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Add to container
                notificationsContainer.appendChild(notification);
                
                // Auto-dismiss after 5 seconds
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 5000);
            }

            // Set up event listeners
            const startButton = document.getElementById('start-meditation');
            if (startButton) {
                startButton.addEventListener('click', () => {
                    const durationSelect = document.getElementById('meditation-duration');
                    const duration = parseInt(durationSelect?.value || 20, 10);
                    startMeditation(duration);
                });
            } else {
                console.warn('Start meditation button not found');
            }

            const stopButton = document.getElementById('stop-meditation');
            if (stopButton) {
                stopButton.addEventListener('click', stopMeditation);
            } else {
                console.warn('Stop meditation button not found');
            }

            // Cleanup function for when component unmounts
            function cleanup() {
                console.debug('Cleaning up meditation resources');
                stopMeditation();
                if (audioContext) {
                    audioContext.close().catch(e => console.error('Error closing audio context:', e));
                }
            }

            // Add cleanup to window unload event
            window.addEventListener('beforeunload', cleanup);
        } else {
            console.error('Failed to initialize audio components');
        }
    } catch (error) {
        console.error('Error in meditation initialization:', error);
    }
});