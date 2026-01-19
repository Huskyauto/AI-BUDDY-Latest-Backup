document.addEventListener('DOMContentLoaded', function() {
    // Convert UTC timestamps to local time
    function convertTimestamps() {
        const timestamps = document.querySelectorAll('[data-timestamp]');
        timestamps.forEach(element => {
            const utcTimestamp = element.getAttribute('data-timestamp');
            const date = new Date(utcTimestamp);
            element.textContent = date.toLocaleString();
        });
    }

    // Initial conversion
    convertTimestamps();
});
