// Initialize stress monitoring dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeStressMonitoring();
});

function initializeStressMonitoring() {
    // Initialize stress gauge
    const gaugeElement = document.getElementById('stressGauge');

    // Set up real-time updates
    updateStressData();
    setInterval(updateStressData, 30000); // Update every 30 seconds
}

function formatLocalTime(isoTimestamp) {
    try {
        // Create a date object from the UTC timestamp
        const utcDate = new Date(isoTimestamp);

        // Format the date in the user's local timezone
        const options = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit',
            hour12: true,
            timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone // Use browser's timezone
        };

        return new Intl.DateTimeFormat('en-US', options).format(utcDate);
    } catch (error) {
        console.error('Error formatting timestamp:', error);
        return 'Time unavailable';
    }
}

function updateStressData() {
    fetch('/api/ring-data')
        .then(response => response.json())
        .then(data => {
            if (data.show_ring_data) {
                updateDisplay(data);
            } else {
                document.getElementById('stressAlert').textContent = data.message;
                document.getElementById('stressAlert').style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error fetching stress data:', error);
            document.getElementById('stressAlert').textContent = 'Error fetching stress data';
            document.getElementById('stressAlert').style.display = 'block';
        });
}

function updateDisplay(data) {
    // Update current stress level safely
    let stressLevel = 0;
    if (data.oura && typeof data.oura.stress_level === 'number') {
        stressLevel = data.oura.stress_level;
    }
    document.getElementById('currentStress').textContent = `${stressLevel}%`;

    // Update HRV with proper fallback handling and check from current_state.hrv_average if exists
    const hrvElement = document.getElementById('currentHRV');
    let hrvValue = null;
    
    // First try to get HRV from the insights/current_state data since it's more reliable
    if (data.trigger_events) {
        // Search for HRV in trigger events
        for (const event of data.trigger_events) {
            if (event.type === 'hrv' && typeof event.value === 'number') {
                hrvValue = event.value;
                break;
            }
        }
    }
    
    // Next try current_state
    if (hrvValue === null && data.current_state && typeof data.current_state.hrv_average === 'number') {
        hrvValue = data.current_state.hrv_average;
    }
    
    // If still not found, check Oura data
    if (hrvValue === null && data.oura && data.oura.heart_rate_variability) {
        hrvValue = data.oura.heart_rate_variability;
        // Make sure it's a number, not an object
        if (typeof hrvValue === 'object') {
            // Try to get a numeric value from the object
            if (hrvValue.rmssd) {
                hrvValue = hrvValue.rmssd;
            } else if (hrvValue.value) {
                hrvValue = hrvValue.value;
            } else {
                // If we can't extract a value, convert to string and mark as error
                hrvValue = null;
            }
        }
    } 
    
    // Lastly, try Ultrahuman as fallback
    if (hrvValue === null && data.ultrahuman && data.ultrahuman.heart_rate_variability) {
        hrvValue = data.ultrahuman.heart_rate_variability;
        
        // Make sure it's a number, not an object
        if (typeof hrvValue === 'object') {
            // Try to get a numeric value from the object
            if (hrvValue.rmssd) {
                hrvValue = hrvValue.rmssd;
            } else if (hrvValue.value) {
                hrvValue = hrvValue.value;
            } else {
                // If we can't extract a value, convert to string and mark as error
                hrvValue = null;
            }
        }
    }
    
    // Update the UI based on what we found
    if (hrvValue !== null && typeof hrvValue === 'number') {
        // Format as fixed decimal for readability
        const formattedValue = hrvValue.toFixed(1);
        hrvElement.textContent = `${formattedValue}ms`;
        hrvElement.classList.remove('fallback-data');
    } else {
        hrvElement.textContent = '--';
        hrvElement.classList.remove('fallback-data');
    }

    // Update recovery index safely
    let recoveryIndex = "--";
    if (data.ultrahuman && typeof data.ultrahuman.recovery_index === 'number') {
        recoveryIndex = `${data.ultrahuman.recovery_index}%`;
    }
    document.getElementById('recoveryIndex').textContent = recoveryIndex;

    // Update last updated time with localized format
    document.getElementById('lastUpdated').textContent = 
        formatLocalTime(data.last_updated);

    // Update recommendations if available
    if (data.insights) {
        const recommendationsHtml = `
            <h5>${data.insights.alert_summary}</h5>
            <p>${data.insights.current_state}</p>
            <ul>
                ${data.insights.primary_recommendations.map(rec => 
                    `<li>${rec}</li>`).join('')}
            </ul>
        `;
        document.getElementById('recommendationsPanel').innerHTML = recommendationsHtml;
    }

    // Show alerts if stress is high
    const alertElement = document.getElementById('stressAlert');
    if (stressLevel > 70) {
        alertElement.className = 'alert alert-warning';
        alertElement.textContent = 'High stress detected! Consider taking a meditation break.';
        alertElement.style.display = 'block';
    } else {
        alertElement.style.display = 'none';
    }
}