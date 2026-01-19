/**
 * Timezone handling utilities for AI-BUDDY
 * This script detects the user's local timezone and formats timestamps accordingly
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get user's timezone
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    console.log('User timezone:', userTimezone);
    
    // Store the user's timezone in a cookie for server-side use
    document.cookie = `user_timezone=${userTimezone}; path=/; max-age=31536000`;
    
    // Process all timestamp elements with the data-timestamp attribute
    function processTimestamps() {
        const timestampElements = document.querySelectorAll('[data-timestamp]');
        console.log('Found timestamp elements:', timestampElements.length);
        
        timestampElements.forEach(element => {
            // Skip if already processed
            if (element.getAttribute('data-timezone-processed') === 'true') return;
            
            const isoTimestamp = element.getAttribute('data-timestamp');
            if (!isoTimestamp) return;
            
            try {
                // Parse the ISO timestamp
                const date = new Date(isoTimestamp);
                if (isNaN(date.getTime())) {
                    console.warn('Invalid date format:', isoTimestamp);
                    return;
                }
                
                // Format in 12-hour format with AM/PM
                const options = { 
                    year: 'numeric',
                    month: '2-digit', 
                    day: '2-digit',
                    hour: '2-digit', 
                    minute: '2-digit',
                    hour12: true
                };
                
                // Format using the browser's local timezone
                const localTimeString = date.toLocaleString(undefined, options);
                
                // Clear all contents and add formatted time
                element.textContent = localTimeString;
                
                // Set a data attribute to mark as processed
                element.setAttribute('data-timezone-processed', 'true');
                
                // Add a tooltip showing the original server time
                element.setAttribute('title', 'Original time: ' + isoTimestamp);
                
                console.log('Converted timestamp:', isoTimestamp, 'to', localTimeString);
            } catch (error) {
                console.error('Error formatting timestamp:', error, 'for element:', element);
            }
        });
    }
    
    // Also look for table cells with date patterns and add data-timestamp attributes
    function detectAndMarkTimestamps() {
        const datePattern = /\d{1,2}\/\d{1,2}\/\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM)/i;
        const tableCells = document.querySelectorAll('td');
        
        let detectedCount = 0;
        
        tableCells.forEach(cell => {
            // Skip if already has timestamp data
            if (cell.hasAttribute('data-timestamp')) return;
            
            const text = cell.textContent.trim();
            if (datePattern.test(text)) {
                try {
                    // Convert to a date object
                    const date = new Date(text);
                    if (!isNaN(date.getTime())) {
                        // Add data-timestamp attribute
                        cell.setAttribute('data-timestamp', date.toISOString());
                        detectedCount++;
                        
                        // Process this cell in the next run
                        setTimeout(() => processTimestamps(), 0);
                    }
                } catch (e) {
                    // Ignore parsing errors
                }
            }
        });
        
        if (detectedCount > 0) {
            console.log('Auto-detected and marked', detectedCount, 'timestamp cells');
        }
    }
    
    // Process timestamps initially
    processTimestamps();
    
    // Then detect unmarked timestamps
    detectAndMarkTimestamps();
    
    // Re-process every 2 seconds in case of dynamic content
    setInterval(processTimestamps, 2000);
});