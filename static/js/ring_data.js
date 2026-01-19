// Function to format temperature for display
function formatTemperature(celsius) {
    // Use a default value of 36.5°C if no valid temperature is provided
    if (!celsius || isNaN(celsius)) {
        celsius = 36.5;
        console.log('Using default temperature of 36.5°C');
    }
    const fahrenheit = (celsius * 9/5) + 32;
    return `${celsius.toFixed(1)}°C / ${fahrenheit.toFixed(1)}°F`;
}

// Function to format timestamp
function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}

// Add cache prevention headers to fetch requests
function addNoCacheHeaders(headers = {}) {
    return {
        ...headers,
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    };
}

// Update Oura Ring data display
function updateOuraData(data) {
    if (!data) return;

    console.log('Updating Oura data:', data);

    // Update display with null checks and timestamps
    document.querySelector('[data-oura-heart-rate]').textContent = data.heart_rate ? `${data.heart_rate} bpm` : '--';
    
    // Handle HRV value which could be complex object with 'items' array
    let hrvDisplay = '--';
    let hrvFallbackUsed = false;
    
    // Enhanced HRV handling with better null checking
    if (data.heart_rate_variability !== null && data.heart_rate_variability !== undefined) {
        console.log('Raw Oura HRV data:', data.heart_rate_variability);
        
        try {
            // Extra safety - convert string representations of objects to actual objects if needed
            let hrvData = data.heart_rate_variability;
            if (typeof hrvData === 'string' && hrvData.startsWith('{') && hrvData.endsWith('}')) {
                try {
                    console.log('Attempting to parse JSON string as object:', hrvData);
                    hrvData = JSON.parse(hrvData);
                } catch (e) {
                    console.warn('Failed to parse HRV string as JSON:', e);
                }
            }
            
            // Handle [object Object] string representation
            if (typeof hrvData === 'string' && (hrvData === '[object Object]' || hrvData.includes('object'))) {
                console.warn('Detected [object Object] string representation, falling back to Ultrahuman data');
                hrvDisplay = null; // Force fallback to Ultrahuman
            }
            // Complex object handling
            else if (typeof hrvData === 'object' && hrvData !== null) {
                console.log('Processing complex HRV object:', hrvData);
                
                // Handle array of values (items array pattern)
                if (Array.isArray(hrvData)) {
                    const validItems = hrvData.filter(item => item !== null && !isNaN(parseFloat(item)));
                    if (validItems.length > 0) {
                        const avgHrv = validItems.reduce((sum, val) => sum + parseFloat(val), 0) / validItems.length;
                        hrvDisplay = `${avgHrv.toFixed(1)} ms`;
                        console.log(`Calculated average HRV from ${validItems.length} items in array:`, avgHrv);
                    } else {
                        console.warn('No valid items in HRV array:', hrvData);
                    }
                } else if (hrvData.items && Array.isArray(hrvData.items)) {
                    // Process 'items' array property
                    const validItems = hrvData.items.filter(item => item !== null && !isNaN(parseFloat(item)));
                    if (validItems.length > 0) {
                        const avgHrv = validItems.reduce((sum, val) => sum + parseFloat(val), 0) / validItems.length;
                        hrvDisplay = `${avgHrv.toFixed(1)} ms`;
                        console.log(`Calculated average HRV from ${validItems.length} items:`, avgHrv);
                    } else {
                        console.warn('No valid items in HRV array:', hrvData.items);
                        hrvDisplay = null; // Force fallback to Ultrahuman
                    }
                } else if (hrvData.average !== undefined && hrvData.average !== null) {
                    // Use pre-calculated average if available (added by backend)
                    const avgValue = parseFloat(hrvData.average);
                    if (!isNaN(avgValue)) {
                        hrvDisplay = `${avgValue.toFixed(1)} ms`;
                        console.log('Using pre-calculated average HRV:', avgValue);
                    } else {
                        console.warn('Invalid pre-calculated average HRV:', hrvData.average);
                        hrvDisplay = null; // Force fallback to Ultrahuman
                    }
                } else if (hrvData.value !== undefined && hrvData.value !== null) {
                    // Some APIs might use a 'value' property
                    const valueHrv = parseFloat(hrvData.value);
                    if (!isNaN(valueHrv)) {
                        hrvDisplay = `${valueHrv.toFixed(1)} ms`;
                        console.log('Using HRV value property:', valueHrv);
                    } else {
                        console.warn('Invalid HRV value property:', hrvData.value);
                        hrvDisplay = null; // Force fallback to Ultrahuman
                    }
                } else {
                    // If it's an object but doesn't have usable properties, log and force fallback
                    console.warn('Unprocessable HRV object:', hrvData);
                    hrvDisplay = null; // Force fallback to Ultrahuman
                }
            } else if (typeof hrvData === 'number') {
                // Simple numeric value
                hrvDisplay = `${hrvData.toFixed(1)} ms`;
                console.log('Using direct numeric HRV value:', hrvData);
            } else if (typeof hrvData === 'string' && hrvData.trim() !== '') {
                // String value that's not empty
                // Try to parse it as a number if possible
                const parsed = parseFloat(hrvData);
                if (!isNaN(parsed)) {
                    hrvDisplay = `${parsed.toFixed(1)} ms`;
                    console.log('Parsed numeric HRV from string:', parsed);
                } else {
                    // Check if this looks like an object representation
                    if (hrvData.includes('object') || hrvData.includes('[') && hrvData.includes(']')) {
                        console.warn('HRV string appears to be object representation:', hrvData);
                        hrvDisplay = null; // Force fallback to Ultrahuman
                    } else {
                        hrvDisplay = hrvData;
                        console.log('Using string HRV value directly:', hrvData);
                    }
                }
            } else {
                // Unknown or unsupported type
                console.warn('Unsupported HRV data type:', typeof hrvData, hrvData);
                hrvDisplay = null; // Force fallback to Ultrahuman
            }
        } catch (error) {
            console.error('Error processing HRV data:', error);
            hrvDisplay = null; // Force fallback to Ultrahuman
        }
    } else {
        console.log('No HRV data available from Oura ring');
        hrvDisplay = null; // Force fallback to Ultrahuman
    }
    
    // No longer using Ultrahuman data as fallback for Oura
    // If HRV data is not available, just display '--'
    if (hrvDisplay === null) {
        hrvDisplay = '--';
        console.log('No HRV data available from Oura ring, displaying empty value');
    }
    
    // Update the HRV display, add an asterisk if we're using fallback data
    const hrvElement = document.querySelector('[data-oura-hrv]');
    if (hrvElement) {
        if (hrvFallbackUsed) {
            hrvElement.textContent = hrvDisplay + '*';
            hrvElement.title = 'Using Ultrahuman ring data as fallback';
            // Add small data source indicator
            hrvElement.classList.add('fallback-data');
        } else {
            hrvElement.textContent = hrvDisplay;
            hrvElement.title = '';
            hrvElement.classList.remove('fallback-data');
        }
    }
    
    document.querySelector('[data-oura-stress]').textContent = data.stress_level ?? '--';
    document.querySelector('[data-oura-temp]').textContent = formatTemperature(data.skin_temperature);

    // Update last refresh time if element exists
    const timestampElement = document.querySelector('[data-oura-timestamp]');
    if (timestampElement && data.timestamp) {
        timestampElement.textContent = `Last updated: ${formatTimestamp(data.timestamp)}`;
    }
}

// Update Ultrahuman Ring data display
function updateUltrahumanData(data) {
    if (!data) return;

    console.log('Updating Ultrahuman data:', data);

    // Display real values from the API, only fallback if truly missing
    const heartRateElement = document.querySelector('[data-ultrahuman-heart-rate]');
    if (heartRateElement) {
        heartRateElement.textContent = data.heart_rate ? `${data.heart_rate} bpm` : '--';
    }
    
    const hrvElement = document.querySelector('[data-ultrahuman-hrv]');
    if (hrvElement) {
        hrvElement.textContent = data.heart_rate_variability ? `${data.heart_rate_variability} ms` : '--';
    }
    
    // Use real recovery index from API data
    const recoveryElement = document.querySelector('[data-ultrahuman-recovery]');
    if (recoveryElement) {
        recoveryElement.textContent = data.recovery_index ? `${data.recovery_index}` : '--';
    }
    
    // Handle skin temperature with real data
    const tempElement = document.querySelector('[data-ultrahuman-temp]');
    if (tempElement) {
        if (data.skin_temperature) {
            tempElement.textContent = formatTemperature(data.skin_temperature);
        } else {
            tempElement.textContent = '--';
        }
    }
    
    // Add VO2 Max display with real data
    const vo2maxElement = document.querySelector('[data-ultrahuman-vo2max]');
    if (vo2maxElement) {
        vo2maxElement.textContent = data.vo2_max ? `${data.vo2_max}` : '--';
    }

    // Update last refresh time if element exists
    const timestampElement = document.querySelector('[data-ultrahuman-timestamp]');
    if (timestampElement && data.timestamp) {
        timestampElement.textContent = `Last updated: ${formatTimestamp(data.timestamp)}`;
    }
}

// Get severity class for alerts
function getSeverityClass(severity) {
    switch (severity.toLowerCase()) {
        case 'high':
        case 'severe':
            return 'alert-danger';
        case 'moderate':
        case 'warning':
            return 'alert-warning';
        default:
            return 'alert-info';
    }
}

// Function to update biomarker insights display
function updateBiomarkerInsights(insights, alerts) {
    console.log('Updating biomarker insights with:', { insights, alerts });

    const insightsContainer = document.querySelector('#biomarker-insights');
    if (!insightsContainer) {
        console.error('Biomarker insights container not found');
        return;
    }

    // Clear existing content
    insightsContainer.innerHTML = '';

    if (!insights?.alert_summary && !alerts?.length) {
        console.log('No insights or alerts to display');
        insightsContainer.innerHTML = '<p class="text-muted">No significant biomarker patterns detected.</p>';
        return;
    }

    let insightsHTML = '';

    // Display alert summary if present
    if (insights?.alert_summary) {
        console.log('Displaying alert summary:', insights.alert_summary);
        insightsHTML += `
            <div class="alert alert-warning mb-3">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Alert Summary</strong>
                <p class="mb-0 mt-2">${insights.alert_summary}</p>
            </div>
        `;
    }

    // Display current state if present
    if (insights?.current_state) {
        console.log('Displaying current state:', insights.current_state);
        insightsHTML += `
            <div class="alert alert-info mb-3">
                <i class="fas fa-info-circle me-2"></i>
                <strong>Current State Analysis</strong>
                <p class="mb-0 mt-2">${insights.current_state}</p>
            </div>
        `;
    }

    // Display recommendations if present
    if (insights?.primary_recommendations?.length || insights?.secondary_recommendations?.length) {
        insightsHTML += '<div class="recommendations mb-3">';

        if (insights.primary_recommendations?.length) {
            insightsHTML += `
                <div class="alert alert-danger mb-3">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    <strong>Priority Actions</strong>
                    <ul class="list-unstyled mb-0 mt-2">
                        ${insights.primary_recommendations.map(rec => `
                            <li class="mt-2"><i class="fas fa-arrow-right me-2"></i>${rec}</li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }

        if (insights.secondary_recommendations?.length) {
            insightsHTML += `
                <div class="alert alert-success mb-3">
                    <i class="fas fa-check-circle me-2"></i>
                    <strong>Preventive Actions</strong>
                    <ul class="list-unstyled mb-0 mt-2">
                        ${insights.secondary_recommendations.map(rec => `
                            <li class="mt-2"><i class="fas fa-arrow-right me-2"></i>${rec}</li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
        insightsHTML += '</div>';
    }

    // Display monitoring focus if present
    if (insights?.monitoring_focus) {
        insightsHTML += `
            <div class="alert alert-primary mb-3">
                <i class="fas fa-search me-2"></i>
                <strong>Monitoring Focus</strong>
                <p class="mb-0 mt-2">${insights.monitoring_focus}</p>
            </div>
        `;
    }

    console.log('Setting new insights HTML');
    insightsContainer.innerHTML = insightsHTML;
}

// Fetch and update ring data 
async function fetchRingData() {
    // No longer tracking scroll position for auto-restoration
    console.log('Manual refresh - auto-scrolling disabled');

    try {
        console.log('Fetching fresh ring data...');

        // Add timestamp and cache prevention
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/ring-data?_=${timestamp}`, {
            headers: addNoCacheHeaders(),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Received ring data:', data);

        // Use requestAnimationFrame to batch DOM updates
        return new Promise(resolve => {
            requestAnimationFrame(() => {
                if (data.show_ring_data) {
                    // Batch all DOM updates together
                    updateOuraData(data.oura);
                    updateUltrahumanData(data.ultrahuman);
                    updateBiomarkerInsights(data.insights, data.alerts);
                    
                    // Also update refresh indicator
                    const refreshIndicator = document.getElementById('autoRefreshIndicator');
                    if (refreshIndicator) {
                        const now = new Date();
                        const timeString = now.toLocaleTimeString();
                        refreshIndicator.textContent = `Manual refresh: Last updated ${timeString}`;
                        refreshIndicator.style.color = '#007bff'; // Blue for manual refresh
                    }
                } else {
                    const message = data.message || 'Ring data access is currently unavailable.';
                    document.querySelector('#biomarker-insights').innerHTML = `
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>${message}
                        </div>
                    `;
                }
                
                // Auto-scrolling has been disabled
                console.log('Auto-scrolling disabled - keeping user scroll position');
                
                // Resolve the promise immediately, don't wait for scroll
                resolve(data);
            });
        });
    } catch (error) {
        console.error('Failed to fetch ring data:', error);
        
        // Use requestAnimationFrame for error message too
        return new Promise((resolve, reject) => {
            requestAnimationFrame(() => {
                document.querySelector('#biomarker-insights').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>Unable to fetch biomarker data. Please try again later.
                    </div>
                `;
                
                // Auto-scrolling is disabled - no scroll restoration
                console.log('Auto-scrolling disabled - no scroll restoration after error');
                
                // Reject with the original error
                reject(error);
            });
        });
    }
}

// Initialize ring data updates with automatic background refresh
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing ring data updates with automatic background refresh');
    
    // Prevent default scroll restoration that might cause scrolling issues
    if (window.history && window.history.scrollRestoration) {
        window.history.scrollRestoration = 'manual';
    }
    
    // Variables to control automatic refresh
    let isAutoRefreshActive = true;
    let autoRefreshInterval;
    const REFRESH_INTERVAL = 60000; // Refresh every 60 seconds (1 minute)
    
    // Store the scroll position when user manually scrolls
    let userScrollTimeout;
    window.addEventListener('scroll', function() {
        clearTimeout(userScrollTimeout);
        userScrollTimeout = setTimeout(() => {
            window.lastUserScrollPosition = window.scrollY || document.documentElement.scrollTop;
        }, 150);
    });
    
    // Function to fetch data without causing page scroll issues
    const fetchDataNoScroll = () => {
        // Store current scroll before fetch - use multiple methods to ensure we capture the scroll position
        const scrollBeforeFetch = window.lastUserScrollPosition || window.scrollY || document.documentElement.scrollTop;
        
        // Update DOM updates to avoid forcing reflow during async operations
        let pendingData = null;
        
        try {
            console.log('Background refresh - scroll position at', scrollBeforeFetch);
            
            // Add timestamp and cache prevention
            const timestamp = new Date().getTime();
            fetch(`/api/ring-data?_=${timestamp}`, {
                headers: addNoCacheHeaders(),
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received ring data:', data);
                
                // Store data for DOM updates
                pendingData = data;
                
                // Schedule DOM updates using requestAnimationFrame to avoid layout thrashing
                requestAnimationFrame(() => {
                    // Get current scroll position right before update
                    const currentScrollY = window.scrollY || document.documentElement.scrollTop;
                    
                    if (pendingData.show_ring_data) {
                        // Apply updates to DOM in a batch to minimize reflows
                        updateOuraData(pendingData.oura);
                        updateUltrahumanData(pendingData.ultrahuman);
                        updateBiomarkerInsights(pendingData.insights, pendingData.alerts);
                        
                        // Update refresh indicator if it exists
                        const refreshIndicator = document.getElementById('autoRefreshIndicator');
                        if (refreshIndicator) {
                            const now = new Date();
                            const timeString = now.toLocaleTimeString();
                            refreshIndicator.textContent = `Auto-refreshing: Last updated ${timeString}`;
                            refreshIndicator.style.color = '#28a745'; // Green to indicate success
                        }
                    } else {
                        const message = pendingData.message || 'Ring data access is currently unavailable.';
                        const biomarkerInsights = document.querySelector('#biomarker-insights');
                        if (biomarkerInsights) {
                            biomarkerInsights.innerHTML = `
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>${message}
                                </div>
                            `;
                        }
                    }
                    
                    // Auto-scrolling disabled
                    console.log('Auto-scrolling disabled - keeping user scroll position');
                });
            })
            .catch(error => {
                console.error('Failed to fetch ring data:', error);
                
                // Schedule error UI update in requestAnimationFrame
                requestAnimationFrame(() => {
                    const biomarkerInsights = document.querySelector('#biomarker-insights');
                    if (biomarkerInsights) {
                        biomarkerInsights.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle me-2"></i>Unable to fetch biomarker data. Please try again later.
                            </div>
                        `;
                    }
                    
                    // Auto-scrolling disabled
                    console.log('Auto-scrolling disabled - keeping user scroll position');
                });
            });
        } catch (error) {
            console.error('Error in fetch:', error);
            
            // Auto-scrolling disabled
            console.log('Auto-scrolling disabled - keeping user scroll position');
        }
    };
    
    // Start automatic refresh at set intervals
    function startAutoRefresh() {
        console.log(`Starting automatic background refresh every ${REFRESH_INTERVAL/1000} seconds`);
        isAutoRefreshActive = true;
        
        // Clear any existing intervals first
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
        }
        
        // Set up the auto-refresh interval
        autoRefreshInterval = setInterval(() => {
            if (isAutoRefreshActive) {
                console.log('Auto-refreshing biometric data in background...');
                fetchDataNoScroll();
            }
        }, REFRESH_INTERVAL);
        
        // Update UI to show auto-refresh is active
        const refreshIndicator = document.getElementById('autoRefreshIndicator');
        if (refreshIndicator) {
            refreshIndicator.style.color = '#28a745';
            refreshIndicator.innerHTML = '<i class="fas fa-sync-alt fa-spin me-2"></i>Auto-refreshing: Active';
        }
    }
    
    // Create small indicator for auto-refresh status
    const statusDiv = document.createElement('div');
    statusDiv.id = 'autoRefreshStatusDiv';
    statusDiv.className = 'text-center mb-2 mt-2';
    statusDiv.innerHTML = `
        <small id="autoRefreshIndicator" class="text-success">
            <i class="fas fa-sync-alt fa-spin me-2"></i>Auto-refreshing: Initializing...
        </small>
    `;
    
    // Add indicator to the page
    const biomarkerSection = document.querySelector('#biomarker-insights');
    if (biomarkerSection && biomarkerSection.parentNode) {
        biomarkerSection.parentNode.insertBefore(statusDiv, biomarkerSection);
    }
    
    // Initial data load
    console.log('Initial background data load...');
    fetchDataNoScroll();
    
    // Start the automatic background refresh
    startAutoRefresh();
});