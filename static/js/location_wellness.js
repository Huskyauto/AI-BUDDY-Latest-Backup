// Define global constants
const SEARCH_RADIUS = 5000; // Search radius in meters (approx 3 miles)
const ALERT_RADIUS = 1000;  // Alert radius in meters (approx 0.6 miles)

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap dropdowns manually with enhanced error handling
    if (typeof bootstrap !== 'undefined') {
        console.log('Bootstrap loaded successfully, initializing dropdowns');
        
        // First, find all dropdowns
        const dropdownElementList = document.querySelectorAll('.dropdown-toggle');
        console.log('Found dropdown elements:', dropdownElementList.length);
        
        // Explicitly find and initialize the settings dropdown
        const settingsDropdown = document.getElementById('settingsDropdown');
        if (settingsDropdown) {
            console.log('Found settings dropdown, initializing explicitly');
            try {
                new bootstrap.Dropdown(settingsDropdown);
                console.log('Initialized dropdown for:', settingsDropdown.id);
            } catch (error) {
                console.error('Error initializing settings dropdown:', error);
            }
        }
        
        // Initialize any other dropdowns found
        if (dropdownElementList.length > 0) {
            dropdownElementList.forEach(function(element) {
                // Skip the settings dropdown as we already initialized it
                if (element.id !== 'settingsDropdown') {
                    try {
                        new bootstrap.Dropdown(element);
                        console.log('Initialized dropdown:', element.id || element.textContent.trim());
                    } catch (error) {
                        console.error('Error initializing dropdown:', element.id, error);
                    }
                }
            });
        }
    } else {
        console.error('Bootstrap not loaded! Dropdowns will not work properly.');
        // Add a notification to the page
        const apiKeyStatus = document.getElementById('apiKeyStatus');
        if (apiKeyStatus) {
            apiKeyStatus.innerHTML = '<div class="alert alert-warning mt-2">Bootstrap failed to load. Settings dropdown may not work.</div>';
        }
    }

    // Add API Key testing functionality
    const testApiKeyButton = document.getElementById('testApiKey');
    const apiKeyStatus = document.getElementById('apiKeyStatus');

    // Map initialization
    let map = null;
    let markers = [];

    // State variables
    let isTrackingActive = false;
    let isSystemArmed = false; // True when car reaches 10+ mph, ready for alerts
    let lastAlertTime = 0;
    let lastAlertLocation = null;
    let lastUpdateSpan = document.getElementById('location-last-update');
    let locationStatusActive = document.getElementById('location-status-active');
    let currentRestaurant = null;
    let speechSynthesisInitialized = false;
    let testAlertPlayed = false; // Flag to track if test alert has already been played
    let consecutiveHighSpeeds = 0; // Track high speed events for auto reset
    let consecutiveLowSpeeds = 0; // Track low speed events for alert trigger
    let watchId = null; // GPS watch ID for continuous tracking
    // Default location for Gurnee Mills Mall - will be updated with real location
    let userLocation = { lat: 42.3718, lng: -87.9539 };
    let nearbyFastFoodRestaurants = []; // Cache of nearby fast-food restaurants
    let lastRestaurantCheck = 0; // Timestamp of last restaurant check
    
    // Exact timing and threshold parameters
    const SEARCH_RADIUS = 5000; // 5000 meters (3 miles) - must match server-side radius
    const ALERT_COOLDOWN = 60000; // 1 minute cooldown between alerts
    const MIN_ACCURACY = 100; // Increased from 20 to 100 meters to be more lenient
    const SPEED_THRESHOLD_LOW = 16.1; // 10 mph in km/h - speed below which alert can trigger
    const SPEED_THRESHOLD_ARM = 16.1; // 10 mph in km/h - speed at which system arms
    const SPEED_THRESHOLD_RESET = 24.14; // 15 mph in km/h - speed at which system resets for next event
    const HIGH_SPEED_COUNT_THRESHOLD = 3; // Number of consecutive high speeds required to reset
    const LOW_SPEED_COUNT_THRESHOLD = 2; // Number of consecutive low speeds required to trigger alert
    const RESTAURANT_CHECK_INTERVAL = 30000; // Check for nearby restaurants every 30 seconds
    const PARKING_LOT_RADIUS = 100; // 100 meters - consider "in parking lot" if within this distance

    // Audio initialization - using Web Audio API instead of audio file
    let audioContext = null;
    let isAudioPlaying = false;
    
    // Initialize audio context
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        console.log('Audio context initialized successfully');
    } catch (e) {
        console.error('Failed to initialize audio context:', e);
    }

    // Initialize speech synthesis
    function initSpeechSynthesis() {
        if ('speechSynthesis' in window && !speechSynthesisInitialized) {
            // Force creation of speech synthesis object first
            window.speechSynthesis;
            
            // Add onvoiceschanged handler
            window.speechSynthesis.onvoiceschanged = function() {
                console.log('Speech synthesis initialized with voices loaded');
                speechSynthesisInitialized = true;
                
                // Test voice available - this helps "wake up" the speech system
                try {
                    const testUtterance = new SpeechSynthesisUtterance('');
                    const voices = window.speechSynthesis.getVoices();
                    console.log(`Available voices: ${voices.length}`);
                } catch (e) {
                    console.error('Error during speech synthesis initialization:', e);
                }
            };
            
            // Get voices to trigger the onvoiceschanged event
            window.speechSynthesis.getVoices();
        }
    }

    // Speak text function with safeguards against multiple overlapping speeches
    function speakText(text) {
        if ('speechSynthesis' in window) {
            console.log('Attempting to speak text:', text);
            
            try {
                // Cancel any pending speech first to clear the queue
                window.speechSynthesis.cancel();
                
                // Force reset the isAudioPlaying flag to ensure we start fresh
                isAudioPlaying = false;
                
                // Small delay to ensure the speech engine is reset
                setTimeout(() => {
                    try {
                        // Mark as audio playing
                        isAudioPlaying = true;
                        
                        // Create utterance with consistent settings
                        const utterance = new SpeechSynthesisUtterance(text);
                        utterance.rate = 1.0;
                        utterance.pitch = 1.0;
                        utterance.volume = 1.0;
                        
                        // Ensure text is not too long (SpeechSynthesisUtterance doesn't have maxLength property)
                        if (text.length > 1000) {
                            text = text.substring(0, 1000) + '...';
                            utterance.text = text;
                        }
                    
                        // Add event handler to reset flag when done
                        utterance.onend = function() {
                            isAudioPlaying = false;
                            console.log('Speech completed successfully');
                        };
                        
                        // Add error handler
                        utterance.onerror = function(event) {
                            isAudioPlaying = false;
                            console.error('Speech synthesis error:', event);
                        };
                        
                        // This play an audio notification sound before speaking
                        // to ensure audio system is active
                        playNotificationSound();
                        
                        // Start speaking with a slight delay to ensure notification sound finishes
                        setTimeout(() => {
                            window.speechSynthesis.speak(utterance);
                            console.log('Started speech synthesis for:', text.substring(0, 50) + '...');
                        }, 300);
                    } catch (innerError) {
                        isAudioPlaying = false;
                        console.error('Error in delayed speech synthesis:', innerError);
                    }
                }, 100);
            } catch (error) {
                isAudioPlaying = false;
                console.error('Error in speech synthesis:', error);
            }
        } else {
            console.error('Speech synthesis not available in this browser');
        }
    }

    // Helper function to update speed display on UI
    function updateSpeedDisplay(speedMph) {
        const speedDisplay = document.getElementById('current-speed-display');
        if (speedDisplay) {
            speedDisplay.innerHTML = `<strong>${speedMph.toFixed(1)} mph</strong>`;
            
            // Color code based on speed thresholds
            if (speedMph >= 15) {
                speedDisplay.className = 'badge bg-success fs-6'; // Green - reset speed
            } else if (speedMph >= 10) {
                speedDisplay.className = 'badge bg-primary fs-6'; // Blue - armed speed
            } else {
                speedDisplay.className = 'badge bg-warning text-dark fs-6'; // Yellow - alert possible
            }
        }
    }
    
    // Helper function to update system status display
    function updateSystemStatus(status, speedMph) {
        const statusDisplay = document.getElementById('system-status-display');
        const trackingStatus = document.getElementById('tracking-active-message');
        const armedBadge = document.getElementById('system-armed-badge');
        
        let statusHtml = '';
        let statusClass = '';
        let badgeText = '';
        let badgeClass = '';
        
        switch(status) {
            case 'armed':
                statusHtml = `<i class="fas fa-shield-alt me-2"></i>ARMED - Ready for alerts (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-success';
                badgeText = 'ARMED';
                badgeClass = 'badge bg-success fs-6';
                break;
            case 'checking':
                statusHtml = `<i class="fas fa-search-location me-2"></i>Checking for nearby fast-food... (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-warning';
                badgeText = 'CHECKING';
                badgeClass = 'badge bg-warning text-dark fs-6';
                break;
            case 'alert':
                statusHtml = `<i class="fas fa-exclamation-triangle me-2"></i>ALERT - Fast-food restaurant detected! (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-danger';
                badgeText = 'ALERT!';
                badgeClass = 'badge bg-danger fs-6';
                break;
            case 'reset':
                statusHtml = `<i class="fas fa-sync-alt me-2"></i>RESET - Ready for next event (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-info';
                badgeText = 'RESET';
                badgeClass = 'badge bg-info fs-6';
                break;
            case 'standby':
                statusHtml = `<i class="fas fa-pause-circle me-2"></i>Standby - Speed up to 10+ mph to arm (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-secondary';
                badgeText = 'Standby';
                badgeClass = 'badge bg-secondary fs-6';
                break;
            default:
                statusHtml = `<i class="fas fa-location-arrow me-2"></i>Tracking active (${speedMph.toFixed(1)} mph)`;
                statusClass = 'alert alert-info';
                badgeText = 'Active';
                badgeClass = 'badge bg-info fs-6';
        }
        
        if (statusDisplay) {
            statusDisplay.innerHTML = statusHtml;
            statusDisplay.className = statusClass;
        }
        
        if (armedBadge) {
            armedBadge.textContent = badgeText;
            armedBadge.className = badgeClass;
        }
        
        if (trackingStatus) {
            trackingStatus.innerHTML = statusHtml;
            trackingStatus.className = statusClass;
            trackingStatus.style.display = 'block';
        }
    }
    
    // Start automatic GPS tracking when page loads (for driving detection)
    function startAutoTracking() {
        if (!navigator.geolocation) {
            console.log('Geolocation not supported - cannot auto-track');
            return;
        }
        
        console.log('Starting automatic GPS tracking for driving detection');
        
        // Watch position continuously with high accuracy for speed detection
        watchId = navigator.geolocation.watchPosition(
            (position) => {
                // Process location update with speed-based logic
                updateLocation(position);
            },
            (error) => {
                console.error('Auto-tracking GPS error:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 1000 // Allow 1 second cache for smoother tracking
            }
        );
        
        console.log('Auto-tracking started with watchId:', watchId);
    }

    // Initialize map immediately if we're on the places page
    if (document.getElementById('map')) {
        console.log('Map element found, initializing...');
        initMap();
    }

    // Initialize speech synthesis
    initSpeechSynthesis();
    
    // NOTE: Auto-tracking is NOT started automatically on page load
    // User must click "Start Location Tracking" button to begin
    // This ensures user consent for location access
    console.log('Location wellness page loaded. Click "Start Location Tracking" to begin.');

    function initMap() {
        try {
            console.log('Starting map initialization');
            // Default to Gurnee Mills Mall in Gurnee, IL location (as a starting point)
            // These coordinates are more centrally located in Gurnee to prevent Wadsworth/Beach Park issues
            const gurneeLocation = { lat: 42.3718, lng: -87.9539 };

            map = new google.maps.Map(document.getElementById('map'), {
                center: gurneeLocation,
                zoom: 14,
                styles: [
                    {
                        featureType: "poi",
                        elementType: "labels",
                        stylers: [{ visibility: "on" }]
                    }
                ]
            });

            // Add loading indicator
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'alert alert-info';
            loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Getting your current location...';
            document.getElementById('places-list').innerHTML = '';
            document.getElementById('places-list').appendChild(loadingDiv);

            // Try to get user's current location with high accuracy
            if (navigator.geolocation) {
                const locationOptions = {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                };

                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        console.log('Got user location:', position.coords);
                        // Show exact coordinates in a user-friendly format
                        document.getElementById('places-list').innerHTML = `
                            <div class="alert alert-success mb-3">
                                <i class="fas fa-check-circle me-2"></i>
                                GPS Location found: ${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}
                                <br><small class="text-muted">Accuracy: ${Math.round(position.coords.accuracy)} meters</small>
                            </div>
                        `;
                        
                        // Update global userLocation variable
                        userLocation = {
                            lat: position.coords.latitude,
                            lng: position.coords.longitude
                        };
                        
                        console.log('Updated global userLocation to:', userLocation);

                        // Center map on user location
                        map.setCenter(userLocation);

                        // Add user marker
                        new google.maps.Marker({
                            position: userLocation,
                            map: map,
                            title: 'Your Location',
                            icon: {
                                path: google.maps.SymbolPath.CIRCLE,
                                scale: 10,
                                fillColor: '#4285F4',
                                fillOpacity: 1,
                                strokeColor: '#ffffff',
                                strokeWeight: 2
                            }
                        });

                        // Search nearby places using user's location
                        searchNearbyPlaces(userLocation);
                    },
                    (error) => {
                        console.error('Geolocation error:', error);
                        let errorMessage = 'Could not get your location. ';

                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMessage += 'Please enable location access in your browser settings.';
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMessage += 'Location information is unavailable.';
                                break;
                            case error.TIMEOUT:
                                errorMessage += 'Location request timed out.';
                                break;
                            default:
                                errorMessage += error.message;
                        }

                        document.getElementById('places-list').innerHTML = `
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                ${errorMessage}
                            </div>
                        `;
                    },
                    locationOptions
                );
            } else {
                console.error('Geolocation not supported by browser');
                document.getElementById('places-list').innerHTML = `
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Geolocation is not supported by your browser. Please use a modern browser with location support.
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error initializing map:', error);
            document.getElementById('places-list').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    Error initializing map: ${error.message}
                </div>
            `;
        }
    }

    function searchNearbyPlaces(location) {
        console.log('Searching nearby places at:', location);
        document.getElementById('places-list').innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-spinner fa-spin me-2"></i>
                Searching for nearby places...
            </div>
        `;

        // Use the proper API endpoint URL with hyphens (not underscores)
        fetch('/location-wellness/api/test-places', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                latitude: location.lat,
                longitude: location.lng,
                radius: SEARCH_RADIUS
            }),
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Places API response:', data);
            // Clear existing markers
            markers.forEach(marker => marker.setMap(null));
            markers = [];

            // Clear existing list and show search summary first
            const searchSummary = document.createElement('div');
            searchSummary.className = 'alert alert-info mb-3';
            searchSummary.innerHTML = `
                <i class="fas fa-info-circle me-2"></i>
                <strong>Search Results</strong>
                <br>Search location: ${location.lat.toFixed(6)}, ${location.lng.toFixed(6)}
                <br>Search radius: ${(SEARCH_RADIUS/1609.34).toFixed(2)} miles
                <br>Area: Gurnee, IL and surrounding areas
            `;
            document.getElementById('places-list').innerHTML = '';
            document.getElementById('places-list').appendChild(searchSummary);

            // Collect all restaurant-type places from raw results
            // This ensures we display ALL restaurants found, even if they weren't classified as "fast food"
            let allPlaces = [];
            
            if (data.status === 'success' && data.raw_results && data.raw_results.length > 0) {
                // Filter for all food-related places, not just those flagged as fast food
                allPlaces = data.raw_results.filter(place => {
                    // Include place if it has restaurant/food types or food-related keywords in name
                    const hasRestaurantTypes = place.types && (
                        place.types.includes('restaurant') || 
                        place.types.includes('food') ||
                        place.types.includes('meal_takeaway') ||
                        place.types.includes('cafe')
                    );
                    
                    const foodKeywords = ['restaurant', 'food', 'burger', 'pizza', 'taco', 
                                         'mcdonald', 'wendy', 'king', 'bell', 'dunkin', 
                                         'subway', 'chipotle', 'donut', 'ice cream'];
                    
                    const hasNameMatch = foodKeywords.some(keyword => 
                        place.name.toLowerCase().includes(keyword.toLowerCase()));
                        
                    return hasRestaurantTypes || hasNameMatch;
                });
                
                console.log(`Found ${allPlaces.length} restaurant-related places in the area`);
                
                if (allPlaces.length > 0) {
                    allPlaces.forEach(place => {
                        const location = place.geometry.location;
                        const marker = new google.maps.Marker({
                            position: location,
                            map: map,
                            title: place.name,
                            animation: google.maps.Animation.DROP
                        });
                        markers.push(marker);

                        // Add to list with distance information
                        const listItem = document.createElement('div');
                        listItem.className = 'list-group-item';
                        
                        // Calculate distance from user to this place
                        const distanceInMeters = google.maps.geometry.spherical.computeDistanceBetween(
                            new google.maps.LatLng(userLocation.lat, userLocation.lng),
                            new google.maps.LatLng(location.lat, location.lng)
                        );
                        
                        const distanceDisplay = distanceInMeters < 1000 ? 
                            `${Math.round(distanceInMeters)}m` : 
                            `${(distanceInMeters/1609.34).toFixed(2)} miles`;
                        
                        listItem.innerHTML = `
                            <h6 class="mb-1">${place.name}</h6>
                            <p class="mb-1 small">${place.vicinity || ''} (${distanceDisplay})</p>
                            ${place.types ? `<p class="mb-0 small text-muted">${place.types.join(', ')}</p>` : ''}
                        `;
                        document.getElementById('places-list').appendChild(listItem);

                        // Add click listener to marker
                        marker.addListener('click', () => {
                            map.panTo(marker.getPosition());
                        });
                    });
                } else {
                    // No restaurant places found, but show all places anyway
                    data.raw_results.forEach(place => {
                        const location = place.geometry.location;
                        const marker = new google.maps.Marker({
                            position: location,
                            map: map,
                            title: place.name,
                            animation: google.maps.Animation.DROP
                        });
                        markers.push(marker);

                        // Add to list
                        const listItem = document.createElement('div');
                        listItem.className = 'list-group-item';
                        listItem.innerHTML = `
                            <h6 class="mb-1">${place.name}</h6>
                            <p class="mb-1 small">${place.vicinity || ''}</p>
                            ${place.types ? `<p class="mb-0 small text-muted">${place.types.join(', ')}</p>` : ''}
                        `;
                        document.getElementById('places-list').appendChild(listItem);

                        // Add click listener to marker
                        marker.addListener('click', () => {
                            map.panTo(marker.getPosition());
                        });
                    });
                }
            } else {
                document.getElementById('places-list').innerHTML = `
                    <div class="alert alert-warning">
                        <i class="fas fa-info-circle me-2"></i>
                        No places found nearby
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching places:', error);
            document.getElementById('places-list').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    Error fetching nearby places: ${error.message}
                </div>
            `;
        });
    }

    // Play notification sound using Web Audio API - more reliable than audio file
    function playNotificationSound() {
        if (!audioContext) {
            try {
                // Try to initialize audio context if not already done
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log('Audio context initialized in playNotificationSound');
            } catch (e) {
                console.error('Failed to initialize audio context:', e);
                return false;
            }
        }
        
        try {
            console.log('Playing notification sound with Web Audio API');
            
            // If already playing, don't play again
            if (isAudioPlaying) {
                console.log('Sound already playing, not starting another');
                return true;
            }
            
            isAudioPlaying = true;
            
            // Create oscillator for beep sound
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            // Configure sound
            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(880, audioContext.currentTime); // Higher pitch (A5)
            gainNode.gain.setValueAtTime(0.5, audioContext.currentTime); // 50% volume
            
            // Connect nodes
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Play first beep
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.15); // 150ms beep
            
            // Play second beep after a delay
            setTimeout(() => {
                try {
                    const oscillator2 = audioContext.createOscillator();
                    oscillator2.type = 'sine';
                    oscillator2.frequency.setValueAtTime(1100, audioContext.currentTime); // Higher pitch
                    oscillator2.connect(gainNode);
                    oscillator2.start();
                    oscillator2.stop(audioContext.currentTime + 0.15); // 150ms beep
                    
                    // Reset audio playing flag after sound completes
                    setTimeout(() => {
                        isAudioPlaying = false;
                    }, 200);
                } catch (e) {
                    console.error('Error playing second beep:', e);
                    isAudioPlaying = false;
                }
            }, 200);
            
            console.log('Notification sound played successfully');
            return true;
        } catch (error) {
            console.error('Exception in playNotificationSound:', error);
            isAudioPlaying = false;
            return false;
        }
    }

    function updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        lastUpdateSpan.textContent = timeString;
    }

    function updateSuggestionsDisplay(suggestions = null, forceShow = false) {
        const mindfulEatingSuggestions = document.getElementById('mindful-eating-suggestions');
        if (mindfulEatingSuggestions) {
            if (!isTrackingActive && !forceShow) return;

            const defaultSuggestions = [
                "Take a moment to check your hunger level (1-10)",
                "Consider if you're eating from physical hunger or emotional needs",
                "Remember your health goals and values",
                "Think about how you'll feel after eating - will it align with your goals?",
                "Practice mindful eating by taking smaller bites and eating slowly",
                "Listen to your body's natural hunger and fullness signals",
                "Consider going for a short walk or drinking water first",
                "Remember that every meal is an opportunity to nourish your body"
            ];

            const suggestionsToShow = suggestions || defaultSuggestions;

            mindfulEatingSuggestions.innerHTML = `
                <div class="card-body">
                    <h5 class="card-title">Mindful Eating Suggestions</h5>
                    <ul class="list-unstyled">
                        ${suggestionsToShow.map(suggestion => `
                            <li class="mb-2">• ${suggestion}</li>
                        `).join('')}
                    </ul>
                </div>
            `;

            mindfulEatingSuggestions.style.display = 'block';
        }
    }

    function startLocationTracking() {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser');
            return;
        }

        try {
            console.log('Starting location tracking with auto-arm at 10+ mph');
            isTrackingActive = true;
            isSystemArmed = false; // Reset armed state
            consecutiveHighSpeeds = 0;
            consecutiveLowSpeeds = 0;
            lastAlertLocation = null;
            lastAlertTime = 0;

            // Announce start of tracking
            speakText("Location tracking started. System will arm when you reach 10 miles per hour. Alerts will trigger when slowing near fast-food restaurants.");
            
            // Update status to standby
            updateSystemStatus('standby', 0);

            watchId = navigator.geolocation.watchPosition(
                (position) => {
                    const location = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude
                    };

                    // Update map center and search for nearby places
                    if (map) {
                        map.setCenter(location);
                        searchNearbyPlaces(location);
                    }
                    updateLastUpdateTime();
                    updateLocation(position);
                },
                (error) => {
                    console.error('Error getting location:', error);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );

            // Update UI
            document.getElementById('start-location-tracking').style.display = 'none';
            document.getElementById('stop-location-tracking').style.display = 'block';
            document.getElementById('tracking-active-message').style.display = 'block';
            document.getElementById('location-status-active').style.display = 'block';
            document.getElementById('mindful-eating-suggestions').style.display = 'block';

            // Play initial notification
            playNotificationSound();

        } catch (error) {
            console.error('Error starting location tracking:', error);
            alert('Failed to start location tracking: ' + error.message);
        }
    }

    function updateLocation(position) {
        const currentTime = Date.now();
        updateLastUpdateTime();

        // Update global userLocation variable
        userLocation = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
        };

        // Get current speed in km/h (convert from m/s if available)
        const currentSpeed = (position.coords.speed || 0) * 3.6; // Convert m/s to km/h
        const speedMph = currentSpeed / 1.609; // Convert to mph for display
        
        console.log('Processing location update:', {
            accuracy: position.coords.accuracy,
            speedKmh: currentSpeed.toFixed(1),
            speedMph: speedMph.toFixed(1),
            isSystemArmed: isSystemArmed,
            timeSinceLastAlert: (currentTime - lastAlertTime) / 1000,
            location: userLocation
        });

        // Update speed display on UI if element exists
        updateSpeedDisplay(speedMph);
        
        // STATE MACHINE: Auto-start, Alert, and Reset logic
        
        // 1. ARM SYSTEM: When speed reaches 10+ mph, system becomes ready for alerts
        if (currentSpeed >= SPEED_THRESHOLD_ARM && !isSystemArmed) {
            isSystemArmed = true;
            consecutiveLowSpeeds = 0;
            console.log(`SYSTEM ARMED: Speed ${speedMph.toFixed(1)} mph >= 10 mph. Ready for fast-food alerts.`);
            updateSystemStatus('armed', speedMph);
            
            // Announce system armed
            if (autoTrackingEnabled) {
                speakText("Location tracking engaged. Ready to alert when approaching fast-food restaurants.");
            }
        }
        
        // 2. RESET SYSTEM: When speed reaches 15+ mph after an alert, reset for next event
        if (currentSpeed >= SPEED_THRESHOLD_RESET) {
            consecutiveHighSpeeds++;
            consecutiveLowSpeeds = 0;
            console.log(`Speed ${speedMph.toFixed(1)} mph >= 15 mph. High speed count: ${consecutiveHighSpeeds}/${HIGH_SPEED_COUNT_THRESHOLD}`);
            
            // Reset tracking after consistent high speeds (driving away from restaurant)
            if (consecutiveHighSpeeds >= HIGH_SPEED_COUNT_THRESHOLD && lastAlertLocation !== null) {
                console.log('SYSTEM RESET: Sustained high speed, clearing last alert for next event');
                lastAlertLocation = null;
                lastAlertTime = 0;
                consecutiveHighSpeeds = 0;
                consecutiveLowSpeeds = 0; // Clear low speed counter so re-arm is required
                isSystemArmed = false; // Disarm system - must reach 10+ mph again to rearm
                updateSystemStatus('reset', speedMph);
                
                // Announce system reset
                if (isTrackingActive) {
                    speakText("Alert reset. Ready for next fast-food location.");
                }
            }
        } else if (currentSpeed < SPEED_THRESHOLD_LOW) {
            // 3. POTENTIAL ALERT: Speed below 10 mph - check if near fast-food restaurant
            consecutiveHighSpeeds = 0;
            consecutiveLowSpeeds++;
            console.log(`Speed ${speedMph.toFixed(1)} mph < 10 mph. Low speed count: ${consecutiveLowSpeeds}/${LOW_SPEED_COUNT_THRESHOLD}`);
            
            // Only trigger alert if system is armed and we have consecutive low speeds
            if (isSystemArmed && consecutiveLowSpeeds >= LOW_SPEED_COUNT_THRESHOLD) {
                console.log('Low speed sustained - checking for nearby fast-food restaurants');
                updateSystemStatus('checking', speedMph);
            }
        } else {
            // Speed between 10-15 mph - maintain current state
            consecutiveHighSpeeds = 0;
            consecutiveLowSpeeds = 0;
        }
        
        // Determine if the user is in a potential parking scenario
        const isParked = currentSpeed < SPEED_THRESHOLD_LOW && consecutiveLowSpeeds >= LOW_SPEED_COUNT_THRESHOLD;
        
        // Send update to server with the correct endpoint path - try both paths for better reliability
        const requestData = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            speed: currentSpeed, // Send speed in km/h
            speed_mph: speedMph, // Also send mph for convenience
            is_parked: isParked, // Set based on speed threshold
            is_system_armed: isSystemArmed, // Include arm state for response handler
            audio_completed: !isAudioPlaying, // Only say completed if audio is not playing
            timestamp: new Date().toISOString(),
            // Send device info for per-device tracking
            device_id: navigator.userAgent + '_' + window.innerWidth + 'x' + window.innerHeight
        };
        
        console.log('Sending location update with data:', requestData);
        
        // Create a snapshot of current state to pass to response handler
        // This avoids closure issues with multiple concurrent requests
        const stateSnapshot = {
            isParked: isParked,
            isSystemArmed: isSystemArmed,
            speedMph: speedMph,
            currentTime: currentTime
        };
        
        // Try each endpoint separately for maximum reliability
        fetch('/location-wellness/api/location-status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData),
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => processLocationResponse(data, stateSnapshot))
        .catch(error => {
            console.log('First endpoint failed, trying second endpoint:', error);
            // Try the second endpoint
            return fetch('/api/location-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(requestData),
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => processLocationResponse(data, stateSnapshot))
            .catch(error => {
                console.log('Second endpoint failed, trying third endpoint:', error);
                // Try the third endpoint
                return fetch('/location-status', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(requestData),
                    credentials: 'same-origin'
                })
                .then(response => response.json())
                .then(data => processLocationResponse(data, stateSnapshot))
                .catch(finalError => {
                    console.error('All endpoints failed:', finalError);
                });
            });
        });
        
        // Helper function to process location response data
        // Uses stateSnapshot to avoid closure issues with concurrent requests
        function processLocationResponse(data, stateSnapshot) {
            console.log('Server response:', data);
            
            // Use values from stateSnapshot (captured at request time) to avoid stale closure issues
            const speedMph = stateSnapshot.speedMph;
            const wasParked = stateSnapshot.isParked;
            const wasArmed = stateSnapshot.isSystemArmed;
            const requestTime = stateSnapshot.currentTime;
            
            // Special case for Raising Cane's - always alert regardless of cooldown
            const isRaisingCanes = data.restaurant_name && data.restaurant_name.toLowerCase().includes('raising cane');
            
            // CRITICAL: Only trigger alert if:
            // 1. System was armed at time of request (reached 10+ mph at some point)
            // 2. Was at low speed (parking/stopped) at time of request
            // 3. Near a fast-food restaurant
            // 4. Cooldown has passed (or it's Raising Cane's)
            const shouldTriggerAlert = 
                wasArmed && 
                wasParked && 
                data.status === 'active' && 
                data.restaurant_name && 
                (requestTime - lastAlertTime > ALERT_COOLDOWN || isRaisingCanes);
            
            if (shouldTriggerAlert) {
                console.log(`ALERT TRIGGERED: System armed, parked at ${speedMph.toFixed(1)} mph, near ${data.restaurant_name}`);
                
                // Update system status to ALERT
                updateSystemStatus('alert', speedMph);

                // Play notification sound
                playNotificationSound();

                // Update UI with restaurant information
                const mindfulEatingSuggestions = document.getElementById('mindful-eating-suggestions');
                mindfulEatingSuggestions.style.display = 'block';
                if (data.suggestions) {
                    updateSuggestionsDisplay(data.suggestions, true);
                }

                // Update alert time and location
                lastAlertTime = currentTime;
                lastAlertLocation = data.restaurant_name;
                const alertLocationDisplay = document.getElementById('alert-location');
                alertLocationDisplay.innerHTML = data.restaurant_name ?
                    `<div class="alert alert-danger">
                        <h3><i class="fas fa-exclamation-triangle me-2"></i>${data.restaurant_name}</h3>
                        <p class="mb-0">Distance: ${data.distance || 'unknown'} meters</p>
                        <p class="small text-muted mb-0">Speed: ${speedMph.toFixed(1)} mph - You appear to be stopping here</p>
                    </div>` : '';
                
                // Create alert message with restaurant name
                const alertText = `Alert: You are near ${data.restaurant_name}. Let's consider some mindful eating suggestions. Take a moment to check your hunger level on a scale of 1 to 10. Consider if you're eating from physical hunger or emotional needs.`;
                
                console.log('Attempting to speak restaurant alert text:', data.restaurant_name);
                
                try {
                    // Use our dedicated speech function for better reliability
                    speakText(alertText);
                    console.log('Restaurant alert speech request sent');
                } catch (error) {
                    console.error('Error triggering speech for restaurant alert:', error);
                    isAudioPlaying = false; // Reset flag in case of error
                }
            } else if (data.status === 'active' && data.restaurant_name && !wasArmed) {
                // Near a restaurant but system not armed - just log, don't alert
                console.log(`Near ${data.restaurant_name} but system not armed (speed not yet reached 10+ mph)`);
            } else if (data.status === 'active' && data.restaurant_name && !wasParked) {
                // Near a restaurant but not slowing down - just log
                console.log(`Near ${data.restaurant_name} but not slowing down (${speedMph.toFixed(1)} mph)`);
            }
        }
    }

    function stopLocationTracking() {
        console.log('Stopping location tracking');

        if (watchId) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
        }

        // Reset all state variables
        isTrackingActive = false;
        isSystemArmed = false;
        lastAlertTime = 0;
        lastAlertLocation = null;
        currentRestaurant = null;
        consecutiveHighSpeeds = 0;
        consecutiveLowSpeeds = 0;

        // Update UI
        document.getElementById('start-location-tracking').style.display = 'block';
        document.getElementById('stop-location-tracking').style.display = 'none';
        document.getElementById('tracking-active-message').style.display = 'none';
        document.getElementById('location-status-active').style.display = 'none';
        document.getElementById('mindful-eating-suggestions').style.display = 'none';
        document.getElementById('alert-location').innerHTML = '';
        
        // Reset status displays
        updateSystemStatus('standby', 0);
        updateSpeedDisplay(0);
    }

    // Event listeners
    if (testApiKeyButton) {
        testApiKeyButton.addEventListener('click', async function() {
            try {
                apiKeyStatus.innerHTML = `
                    <div class="alert alert-info mt-2">
                        <i class="fas fa-spinner fa-spin me-2"></i>Testing API key...
                    </div>
                `;

                const response = await fetch('/location-wellness/api/test-api-key', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const data = await response.json();

                if (data.status === 'success') {
                    apiKeyStatus.innerHTML = `
                        <div class="alert alert-success mt-2">
                            <i class="fas fa-check-circle me-2"></i>API key is valid and working
                        </div>
                    `;
                } else {
                    apiKeyStatus.innerHTML = `
                        <div class="alert alert-danger mt-2">
                            <i class="fas fa-exclamation-circle me-2"></i>${data.message || 'Failed to validate API key'}
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error testing API key:', error);
                apiKeyStatus.innerHTML = `
                    <div class="alert alert-danger mt-2">
                        <i class="fas fa-exclamation-circle me-2"></i>Error testing API key: ${error.message}
                    </div>
                `;
            }
        });
    }

    // Add event listener for Test Places API button
    const testPlacesApiBtn = document.getElementById('test-places-api');
    if (testPlacesApiBtn) {
        testPlacesApiBtn.addEventListener('click', async function() {
            try {
                // Show test results area
                const testResultsArea = document.getElementById('test-results');
                const testOutput = document.getElementById('test-output');
                testResultsArea.style.display = 'block';
                testOutput.innerHTML = 'Testing Places API...';
                
                // Get current location
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        async (position) => {
                            const location = {
                                lat: position.coords.latitude,
                                lng: position.coords.longitude
                            };
                            
                            // Send to server for testing
                            const response = await fetch('/location-wellness/api/test-places', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest'
                                },
                                body: JSON.stringify({
                                    latitude: location.lat,
                                    longitude: location.lng
                                })
                            });
                            
                            const data = await response.json();
                            testOutput.innerHTML = JSON.stringify(data, null, 2);
                        },
                        (error) => {
                            testOutput.innerHTML = `Error getting location: ${error.message}`;
                        },
                        {
                            enableHighAccuracy: true,
                            timeout: 10000,
                            maximumAge: 0
                        }
                    );
                } else {
                    testOutput.innerHTML = 'Geolocation is not supported by your browser';
                }
            } catch (error) {
                console.error('Error testing Places API:', error);
                document.getElementById('test-output').innerHTML = `Error: ${error.message}`;
            }
        });
    }
    
    // Direct test function for Raising Cane's alert - only plays once per session
    function forceRaisingCanesAlert() {
        console.log('Manually forcing Raising Cane\'s alert');
        
        // If speech is in progress, prevent multiple alerts
        if (isAudioPlaying) {
            console.log('Speech already in progress, ignoring duplicate alert request');
            return;
        }
        
        // If test alert already played this session, reset it for another test
        if (testAlertPlayed) {
            console.log('Resetting test alert for another run');
            
            // Cancel any ongoing speech
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
            
            // Reset the audio playing flag
            isAudioPlaying = false;
            
            // Reset the test alert flag
            testAlertPlayed = false;
            
            // Change the button back to its original state
            let alertBtn = document.getElementById('force-raising-canes-alert');
            if (alertBtn) {
                alertBtn.classList.remove('btn-secondary');
                alertBtn.classList.add('btn-warning');
                alertBtn.disabled = false;
                alertBtn.innerHTML = '<i class="fas fa-bolt me-2"></i>Force Raising Cane\'s Alert (Test)';
            }
            
            // Show reset confirmation message
            const alertLocationDisplay = document.getElementById('alert-location');
            alertLocationDisplay.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>Test Reset</h5>
                    <p class="mb-0">The test alert has been reset.</p>
                    <p class="small">You can now run the test again.</p>
                </div>
            `;
            
            // Hide the mindful eating suggestions
            const mindfulEatingSuggestions = document.getElementById('mindful-eating-suggestions');
            if (mindfulEatingSuggestions) {
                mindfulEatingSuggestions.style.display = 'none';
            }
            
            return;
        }
        
        // Mark that we've played the test alert
        testAlertPlayed = true;
        
        // Change button to indicate it can be reset
        let alertBtn = document.getElementById('force-raising-canes-alert');
        if (alertBtn) {
            alertBtn.classList.remove('btn-warning');
            alertBtn.classList.add('btn-secondary');
            alertBtn.innerHTML = '<i class="fas fa-redo me-2"></i>Reset Cane\'s Test Alert';
        }
        
        // Play notification sound
        playNotificationSound();
        
        // Show mindful eating suggestions
        const mindfulEatingSuggestions = document.getElementById('mindful-eating-suggestions');
        mindfulEatingSuggestions.style.display = 'block';
        
        // Update alert display
        const alertLocationDisplay = document.getElementById('alert-location');
        alertLocationDisplay.innerHTML = `
            <div class="alert alert-info">
                <h3><i class="fas fa-location-arrow me-2"></i>Raising Cane's</h3>
                <p class="mb-0">Distance: 10 meters (Manual Test)</p>
                <p class="small text-muted">(One-time test complete)</p>
            </div>
        `;
        
        // Use the speakText function instead of direct speech synthesis
        const alertText = "Alert: You are near Raising Cane's. Let's consider some mindful eating suggestions. Take a moment to check your hunger level on a scale of 1 to 10. Consider if you're eating from physical hunger or emotional needs.";
        console.log('Attempting to speak Raising Canes alert text');
        
        try {
            // Use our dedicated speech function
            speakText(alertText);
            console.log('Raising Canes test alert speech request sent');
        } catch (error) {
            console.error('Error triggering speech for Raising Canes test:', error);
            isAudioPlaying = false; // Reset flag in case of error
        }
    }

    // Add event listeners for tracking buttons
    const startTrackingBtn = document.getElementById('start-location-tracking');
    const stopTrackingBtn = document.getElementById('stop-location-tracking');
    const forceAlertBtn = document.getElementById('force-raising-canes-alert');

    if (startTrackingBtn) {
        startTrackingBtn.addEventListener('click', startLocationTracking);
    }
    if (stopTrackingBtn) {
        stopTrackingBtn.addEventListener('click', stopLocationTracking);
    }
    if (forceAlertBtn) {
        forceAlertBtn.addEventListener('click', forceRaisingCanesAlert);
    }
});